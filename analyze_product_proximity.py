import pyodbc
import pandas as pd
import numpy as np
import json
import sys
import subprocess
import os

# Database credentials
server = 'ATSINDIA3D39\\SQLEXPRESS'
database = 'ats_wms_mahindra_battery_db'
username = 'ats-india'
password = 'Ats123*'
driver = '{ODBC Driver 17 for SQL Server}'

# Create connection string
conn_str = f"DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password}"

def calculate_proximity_score(empty_pos, product_positions, db_connection):
    """Calculate proximity score for an empty position relative to existing product positions
    incorporating all validation constraints"""
    if len(product_positions) == 0:
        return 0
    
    try:
        # Initialize base score
        base_score = 0
        
        # 1. Check if Infeed Mission Already Exists
        cursor = db_connection.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM ats_wms_infeed_mission_runtime_details 
            WHERE AREA_ID = ? AND 
            (INFEED_MISSION_STATUS = 'READY' OR INFEED_MISSION_STATUS = 'IN_PROGRESS')
            AND INFEED_MISSION_IS_DELETED = 0
        """, (empty_pos['AREA_ID'],))
        existing_missions = cursor.fetchone()[0]
        if existing_missions > 0:
            return 0  # Skip if there are existing missions
        
        # 2. Check Pallet Details and Infeed Mission Generation (only if we have a pallet)
        if 'PALLET_CODE' in empty_pos and pd.notna(empty_pos['PALLET_CODE']):
            cursor.execute("""
                SELECT IS_INFEED_MISSION_GENERATED 
                FROM ats_wms_current_stock_details 
                WHERE PALLET_CODE = ? AND PALLET_INFORMATION_ID = ?
            """, (empty_pos['PALLET_CODE'], empty_pos['PALLET_INFORMATION_ID']))
            pallet_info = cursor.fetchone()
            if not pallet_info or pallet_info[0] != 0:
                return 0  # Skip if mission already generated
        
        # 3. Active Floor Availability Check
        cursor.execute("""
            SELECT COUNT(*) FROM ats_wms_master_floor_details 
            WHERE FLOOR_ID = ? AND FLOOR_IS_ACTIVE = 1 AND FLOOR_IS_DELETED = 0
        """, (empty_pos['FLOOR_ID'],))
        active_floors = cursor.fetchone()[0]
        if active_floors == 0:
            return 0  # Skip if no active floors
        
        # 4. Rack Active Status Check
        cursor.execute("""
            SELECT RACK_IS_ACTIVE, RACK_IS_DELETED FROM ats_wms_master_rack_details 
            WHERE RACK_ID = ?
        """, (empty_pos['RACK_ID'],))
        rack_info = cursor.fetchone()
        if not rack_info or rack_info[0] != 1 or rack_info[1] != 0:
            return 0  # Skip if rack is not active or is deleted
        
        # 5. Mission Conflict Check
        cursor.execute("""
            SELECT COUNT(*) FROM (
                SELECT 1 AS mission_count FROM ats_wms_infeed_mission_runtime_details WHERE RACK_ID = ? AND 
                (INFEED_MISSION_STATUS = 'READY' OR INFEED_MISSION_STATUS = 'IN_PROGRESS')
                AND INFEED_MISSION_IS_DELETED = 0
                UNION
                SELECT 1 AS mission_count FROM ats_wms_outfeed_mission_runtime_details WHERE RACK_ID = ? AND 
                (OUTFEED_MISSION_STATUS = 'READY' OR OUTFEED_MISSION_STATUS = 'IN_PROGRESS')
                AND OUTFEED_MISSION_IS_DELETED = 0
                UNION
                SELECT 1 AS mission_count FROM ats_wms_transfer_pallet_mission_runtime_details WHERE RACK_ID = ? AND 
                (TRANSFER_MISSION_STATUS = 'READY' OR TRANSFER_MISSION_STATUS = 'IN_PROGRESS')
                AND TRANSFER_MISSION_IS_DELETED = 0
            ) AS missions
        """, (empty_pos['RACK_ID'], empty_pos['RACK_ID'], empty_pos['RACK_ID']))
        conflicting_missions = cursor.fetchone()[0]
        if conflicting_missions > 0:
            return 0  # Skip if there are conflicting missions
        
        # 6. Front Position Validation
        cursor.execute("""
            SELECT COUNT(*) FROM ats_wms_master_position_details 
            WHERE POSITION_NUMBER_IN_RACK < ? AND RACK_ID = ? AND 
            (POSITION_IS_EMPTY = 0 OR POSITION_IS_ALLOCATED = 1)
            AND POSITION_IS_ACTIVE = 1 AND POSITION_IS_DELETED = 0
        """, (empty_pos['POSITION_NUMBER_IN_RACK'], empty_pos['RACK_ID']))
        front_positions_blocked = cursor.fetchone()[0]
        if front_positions_blocked > 0:
            return 0  # Skip if front positions are blocked
        
        # Calculate base distance score
        empty_coords = np.array([
            int(empty_pos['RACK_ID']),
            int(empty_pos['POSITION_NUMBER_IN_RACK'])
        ])
        
        # Calculate scores for each product position
        scores = []
        for _, pos in product_positions.iterrows():
            pos_coords = np.array([
                int(pos['RACK_ID']),
                int(pos['POSITION_NUMBER_IN_RACK'])
            ])
            
            # Calculate base distance (using Manhattan distance)
            distance = np.sum(np.abs(empty_coords - pos_coords))
            
            # Calculate position similarity factors with weights
            same_area = pos['AREA_ID'] == empty_pos['AREA_ID']
            same_floor = pos['FLOOR_ID'] == empty_pos['FLOOR_ID']
            same_rack = pos['RACK_ID'] == empty_pos['RACK_ID']
            same_product = pos['PRODUCT_VARIANT_CODE'] == empty_pos['PRODUCT_VARIANT_CODE']
            same_quality = pos['QUALITY_STATUS'] == empty_pos['QUALITY_STATUS']
            
            # Calculate score with weighted bonuses
            base_score = 1 / (1 + distance)  # This will always be positive
            multiplier = 1.0
            
            # Apply weighted bonuses based on constraints
            if same_area:
                multiplier *= 1.5  # Area proximity bonus
            if same_floor:
                multiplier *= 2.0  # Floor proximity bonus
            if same_rack:
                multiplier *= 3.0  # Rack proximity bonus
            if same_product:
                multiplier *= 2.5  # Same product bonus
            if same_quality:
                multiplier *= 2.0  # Same quality status bonus
                
            final_score = base_score * multiplier
            scores.append(final_score)
        
        # Return the average score if all validations pass
        return sum(scores) / len(scores) if scores else 0
        
    except (ValueError, TypeError) as e:
        print(f"Error calculating proximity score: {e}")
        return 0
    finally:
        cursor.close()

def generate_floor_report(df):
    """Generate a text-based report of floor information and empty positions"""
    try:
        # Create output directory if it doesn't exist
        os.makedirs('reports', exist_ok=True)
        
        # Initialize report content
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("WAREHOUSE FLOOR REPORT")
        report_lines.append("=" * 80)
        report_lines.append("\n")
        
        # Group data by floor, handling None values
        floors = df['FLOOR_NAME'].dropna().unique()
        floors = sorted(floors, key=lambda x: int(x.split('-')[1]) if x and '-' in x else 0)
        
        for floor in floors:
            floor_data = df[df['FLOOR_NAME'] == floor]
            
            # Count positions by type
            total_positions = len(floor_data)
            empty_positions = len(floor_data[floor_data['PALLET_STATUS_NAME'] == 'EMPTY'])
            bev_positions = len(floor_data[floor_data['PRODUCT_NAME'] == 'BEV'])
            s230_positions = len(floor_data[floor_data['PRODUCT_NAME'] == 'S230'])
            
            # Add floor summary
            report_lines.append(f"\n{floor} Summary:")
            report_lines.append("-" * 40)
            report_lines.append(f"Total Positions: {total_positions}")
            report_lines.append(f"Empty Positions: {empty_positions}")
            report_lines.append(f"BEV Positions: {bev_positions}")
            report_lines.append(f"S230 Positions: {s230_positions}")
            
            # Add empty positions detail
            if empty_positions > 0:
                report_lines.append("\nEmpty Positions Detail:")
                empty_pos = floor_data[floor_data['PALLET_STATUS_NAME'] == 'EMPTY']
                for _, pos in empty_pos.iterrows():
                    report_lines.append(
                        f"  Area: {pos['AREA_NAME']}, "
                        f"Rack: {pos['RACK_COLUMN']}, "
                        f"Position: {pos['POSITION_NUMBER_IN_RACK']}, "
                        f"Side: {pos['RACK_SIDE']}"
                    )
            
            # Add BEV positions detail
            if bev_positions > 0:
                report_lines.append("\nBEV Positions Detail:")
                bev_pos = floor_data[floor_data['PRODUCT_NAME'] == 'BEV']
                for _, pos in bev_pos.iterrows():
                    report_lines.append(
                        f"  Area: {pos['AREA_NAME']}, "
                        f"Rack: {pos['RACK_COLUMN']}, "
                        f"Position: {pos['POSITION_NUMBER_IN_RACK']}, "
                        f"Side: {pos['RACK_SIDE']}, "
                        f"Quantity: {pos['QUANTITY']}"
                    )
            
            # Add S230 positions detail
            if s230_positions > 0:
                report_lines.append("\nS230 Positions Detail:")
                s230_pos = floor_data[floor_data['PRODUCT_NAME'] == 'S230']
                for _, pos in s230_pos.iterrows():
                    report_lines.append(
                        f"  Area: {pos['AREA_NAME']}, "
                        f"Rack: {pos['RACK_COLUMN']}, "
                        f"Position: {pos['POSITION_NUMBER_IN_RACK']}, "
                        f"Side: {pos['RACK_SIDE']}, "
                        f"Quantity: {pos['QUANTITY']}"
                    )
            
            report_lines.append("\n" + "=" * 80)
        
        # Save report to file
        report_file = 'reports/floor_report.txt'
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_lines))
        
        print(f"\nReport saved to {os.path.abspath(report_file)}")
        
        # Also print the report to console
        print('\n'.join(report_lines))
        
    except Exception as e:
        print(f"Error generating report: {e}")
        import traceback
        traceback.print_exc()

def find_optimal_positions():
    """Find optimal positions based on proximity to existing products"""
    try:
        # Connect to the database
        print("Connecting to database...")
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        print("Successfully connected to the database!\n")
        
        # Query to get occupied positions with product info
        occupied_positions_query = """
        SELECT 
            mp.POSITION_ID,
            mp.POSITION_NAME,
            mp.POSITION_NUMBER_IN_RACK,
            mp.RACK_ID,
            mp.AREA_ID,
            mp.FLOOR_ID,
            cs.PRODUCT_NAME,
            cs.PRODUCT_VARIANT_CODE,
            cs.QUALITY_STATUS,
            cs.PALLET_CODE,
            cs.PALLET_INFORMATION_ID
        FROM 
            ats_wms_master_position_details mp
            LEFT JOIN ats_wms_current_stock_details cs ON mp.POSITION_ID = cs.POSITION_ID
        WHERE 
            mp.POSITION_IS_ACTIVE = 1
            AND mp.POSITION_IS_DELETED = 0
            AND cs.PRODUCT_NAME IS NOT NULL
        """
        
        # Query to get empty positions
        empty_positions_query = """
        SELECT 
            mp.POSITION_ID,
            mp.POSITION_NAME,
            mp.POSITION_NUMBER_IN_RACK,
            mp.RACK_ID,
            mp.AREA_ID,
            mp.FLOOR_ID,
            mp.POSITION_IS_EMPTY,
            mp.POSITION_IS_ALLOCATED,
            cs.PRODUCT_VARIANT_CODE,
            cs.QUALITY_STATUS
        FROM 
            ats_wms_master_position_details mp
            LEFT JOIN ats_wms_current_stock_details cs ON mp.POSITION_ID = cs.POSITION_ID
        WHERE 
            mp.POSITION_IS_ACTIVE = 1
            AND mp.POSITION_IS_DELETED = 0
            AND mp.POSITION_IS_EMPTY = 1
            AND mp.POSITION_IS_ALLOCATED = 0
        """
        
        # Execute queries and convert to DataFrames
        print("Getting occupied positions...")
        occupied_df = pd.read_sql(occupied_positions_query, conn)
        print(f"Found {len(occupied_df)} occupied positions")
        
        print("\nGetting empty positions...")
        empty_df = pd.read_sql(empty_positions_query, conn)
        print(f"Found {len(empty_df)} empty positions")
        
        if len(occupied_df) == 0:
            print("\nNo occupied positions found!")
            return
            
        # Create a dictionary to store optimal positions for each product type
        optimal_positions = {
            "BEV": [],
            "S230": []
        }
        
        # Calculate proximity scores for each empty position
        for _, empty_pos in empty_df.iterrows():
            # Calculate score for BEV products
            bev_positions = occupied_df[occupied_df['PRODUCT_NAME'] == 'BEV']
            bev_score = calculate_proximity_score(empty_pos, bev_positions, conn)
            
            # Calculate score for S230 products
            s230_positions = occupied_df[occupied_df['PRODUCT_NAME'] == 'S230']
            s230_score = calculate_proximity_score(empty_pos, s230_positions, conn)
            
            # Add position to optimal positions if it has a positive score
            if bev_score > 0:
                position_data = {
                    "position_id": empty_pos['POSITION_ID'],
                    "position_name": empty_pos['POSITION_NAME'],
                    "rack_id": empty_pos['RACK_ID'],
                    "area_id": empty_pos['AREA_ID'],
                    "floor_id": empty_pos['FLOOR_ID'],
                    "position_number": empty_pos['POSITION_NUMBER_IN_RACK'],
                    "proximity_score": bev_score,
                    "nearby_products": len(bev_positions)
                }
                optimal_positions["BEV"].append(position_data)
                
            if s230_score > 0:
                position_data = {
                    "position_id": empty_pos['POSITION_ID'],
                    "position_name": empty_pos['POSITION_NAME'],
                    "rack_id": empty_pos['RACK_ID'],
                    "area_id": empty_pos['AREA_ID'],
                    "floor_id": empty_pos['FLOOR_ID'],
                    "position_number": empty_pos['POSITION_NUMBER_IN_RACK'],
                    "proximity_score": s230_score,
                    "nearby_products": len(s230_positions)
                }
                optimal_positions["S230"].append(position_data)
        
        # Sort positions by score for each product type
        for product_type in ['BEV', 'S230']:
            optimal_positions[product_type].sort(key=lambda x: x['proximity_score'], reverse=True)
        
        # Save to JSON
        output_data = {
            "total_occupied_positions": len(occupied_df),
            "total_empty_positions": len(empty_df),
            "optimal_positions": optimal_positions
        }
        
        with open('optimal_positions.json', 'w') as f:
            json.dump(output_data, f, indent=4)
        print(f"\nOptimal positions saved to 'optimal_positions.json'")
        
        # Print summary
        print("\nSummary of optimal positions found:")
        for product_type in ['BEV', 'S230']:
            print(f"\n{product_type}:")
            product_positions = occupied_df[occupied_df['PRODUCT_NAME'] == product_type]
            print(f"Total occupied positions: {len(product_positions)}")
            print(f"Optimal empty positions: {len(optimal_positions[product_type])}")
            if len(optimal_positions[product_type]) > 0:
                print("\nTop 5 optimal positions:")
                for pos in optimal_positions[product_type][:5]:
                    print(f"Position: {pos['position_name']}, Score: {pos['proximity_score']:.4f}, "
                          f"Nearby products: {pos['nearby_products']}")
        
        # Close the connection
        cursor.close()
        conn.close()
        print("\nConnection closed successfully.")
        
    except pyodbc.Error as e:
        print(f"Database Error: {e}")
    except Exception as e:
        print(f"Error in main execution: {e}")
        import traceback
        traceback.print_exc()

def get_table_schema(db_connection, table_name):
    """Get schema information for a given table"""
    cursor = db_connection.cursor()
    try:
        cursor.execute(f"""
            SELECT 
                COLUMN_NAME,
                DATA_TYPE,
                IS_NULLABLE,
                COLUMN_DEFAULT
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = ?
            ORDER BY ORDINAL_POSITION
        """, (table_name,))
        
        columns = cursor.fetchall()
        schema = {
            'table_name': table_name,
            'columns': []
        }
        
        for col in columns:
            schema['columns'].append({
                'name': col[0],
                'type': col[1],
                'nullable': col[2],
                'default': col[3]
            })
            
        return schema
    finally:
        cursor.close()

def analyze_tables():
    """Analyze all relevant tables and their schemas"""
    try:
        # Connect to the database
        print("Connecting to database...")
        conn = pyodbc.connect(conn_str)
        print("Successfully connected to the database!\n")
        
        # List of tables we need to analyze
        tables = [
            'ats_wms_master_position_details',
            'ats_wms_current_stock_details',
            'ats_wms_infeed_mission_runtime_details',
            'ats_wms_outfeed_mission_runtime_details',
            'ats_wms_transfer_mission_runtime_details',
            'ats_wms_pallet_information',
            'ats_wms_master_floor_details',
            'ats_wms_master_rack_details'
        ]
        
        # Get schema for each table
        print("Analyzing table schemas...")
        schemas = {}
        for table in tables:
            print(f"\nAnalyzing {table}...")
            schema = get_table_schema(conn, table)
            schemas[table] = schema
            
            # Print column information
            print(f"\nColumns in {table}:")
            for col in schema['columns']:
                print(f"  - {col['name']} ({col['type']}) {'NULL' if col['nullable'] == 'YES' else 'NOT NULL'}")
        
        # Save schemas to file for reference
        with open('table_schemas.json', 'w') as f:
            json.dump(schemas, f, indent=4)
        print("\nTable schemas saved to 'table_schemas.json'")
        
        # Close the connection
        conn.close()
        print("\nConnection closed successfully.")
        
        return schemas
        
    except pyodbc.Error as e:
        print(f"Database Error: {e}")
    except Exception as e:
        print(f"Error in schema analysis: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # First analyze the tables
    schemas = analyze_tables()
    
    # Then proceed with finding optimal positions
    if schemas:
        find_optimal_positions() 