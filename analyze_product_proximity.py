import pyodbc
import pandas as pd
import numpy as np
import json
import sys
import subprocess
import os
from datetime import datetime

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
        
        # 7. Alarm Rack Check
        cursor.execute("""
            SELECT IS_ALARM_RACK FROM ats_wms_master_position_details 
            WHERE POSITION_ID = ?
        """, (empty_pos['POSITION_ID'],))
        is_alarm_rack = cursor.fetchone()[0]
        if is_alarm_rack == 1:
            return 0  # Skip if it's an alarm rack
        
        # 8. Quality Status Check
        if 'QUALITY_STATUS' in empty_pos and pd.notna(empty_pos['QUALITY_STATUS']):
            cursor.execute("""
                SELECT COUNT(*) FROM ats_wms_current_stock_details 
                WHERE POSITION_ID = ? AND QUALITY_STATUS = ?
            """, (empty_pos['POSITION_ID'], empty_pos['QUALITY_STATUS']))
            quality_matches = cursor.fetchone()[0]
            if quality_matches == 0:
                return 0  # Skip if quality status doesn't match
        
        # 9. Product Variant Compatibility Check
        if 'PRODUCT_VARIANT_CODE' in empty_pos and pd.notna(empty_pos['PRODUCT_VARIANT_CODE']):
            cursor.execute("""
                SELECT COUNT(*) FROM ats_wms_current_stock_details 
                WHERE POSITION_ID = ? AND PRODUCT_VARIANT_CODE = ?
            """, (empty_pos['POSITION_ID'], empty_pos['PRODUCT_VARIANT_CODE']))
            variant_matches = cursor.fetchone()[0]
            if variant_matches == 0:
                return 0  # Skip if product variant doesn't match
        
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
        
        # Query to get empty positions with area and floor details
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
            mp.POSITION_IS_ACTIVE,
            mp.IS_MATERIAL_LOADED,
            mp.IS_MANUAL_DISPATCH,
            mp.POSITION_IS_DELETED,
            cs.PRODUCT_VARIANT_CODE,
            cs.QUALITY_STATUS,
            ma.AREA_NAME,
            mf.FLOOR_NAME
        FROM 
            ats_wms_master_position_details mp
            LEFT JOIN ats_wms_current_stock_details cs ON mp.POSITION_ID = cs.POSITION_ID
            LEFT JOIN ats_wms_master_area_details ma ON mp.AREA_ID = ma.AREA_ID
            LEFT JOIN ats_wms_master_floor_details mf ON mp.FLOOR_ID = mf.FLOOR_ID
        WHERE 
            mp.POSITION_IS_ACTIVE = 1
            AND mp.POSITION_IS_DELETED = 0
            AND (
                -- Regular empty positions (not allocated and empty)
                (mp.POSITION_IS_ALLOCATED = 0 AND mp.POSITION_IS_EMPTY = 1)
                OR
                -- Dead cells (allocated, active, no material, empty, manual dispatch, not deleted)
                (mp.POSITION_IS_ALLOCATED = 1 
                 AND mp.POSITION_IS_ACTIVE = 1 
                 AND mp.IS_MATERIAL_LOADED = 0 
                 AND mp.POSITION_IS_EMPTY = 1 
                 AND mp.IS_MANUAL_DISPATCH = 1 
                 AND mp.POSITION_IS_DELETED = 0)
            )
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
            
        # Calculate current product distribution
        bev_count = len(occupied_df[occupied_df['PRODUCT_NAME'] == 'BEV'])
        s230_count = len(occupied_df[occupied_df['PRODUCT_NAME'] == 'S230'])
        total_products = bev_count + s230_count
        
        if total_products == 0:
            print("\nNo BEV or S230 products found!")
            return
            
        # Calculate target distribution ratios
        bev_ratio = bev_count / total_products
        s230_ratio = s230_count / total_products
        
        print(f"\nCurrent distribution:")
        print(f"BEV: {bev_count} positions ({bev_ratio:.2%})")
        print(f"S230: {s230_count} positions ({s230_ratio:.2%})")
        
        # Clear existing optimal positions
        cursor.execute("DELETE FROM ats_wms_optimal_position")
        conn.commit()
        print("\nCleared existing optimal positions")
        
        # Calculate proximity scores for each empty position
        position_scores = []
        for _, empty_pos in empty_df.iterrows():
            # Calculate score for BEV products
            bev_positions = occupied_df[occupied_df['PRODUCT_NAME'] == 'BEV']
            bev_score = calculate_proximity_score(empty_pos, bev_positions, conn)
            
            # Calculate score for S230 products
            s230_positions = occupied_df[occupied_df['PRODUCT_NAME'] == 'S230']
            s230_score = calculate_proximity_score(empty_pos, s230_positions, conn)
            
            if bev_score > 0 or s230_score > 0:
                position_scores.append({
                    'position': empty_pos,
                    'bev_score': bev_score,
                    's230_score': s230_score,
                    'area_id': empty_pos['AREA_ID'],
                    'floor_id': empty_pos['FLOOR_ID']
                })
        
        # Sort positions by area, floor, and then by combined score
        position_scores.sort(key=lambda x: (
            x['area_id'],  # Primary sort by area
            x['floor_id'],  # Secondary sort by floor
            -max(x['bev_score'], x['s230_score'])  # Tertiary sort by highest score (descending)
        ))
        
        # Calculate target allocations
        total_empty = len(position_scores)
        target_bev = int(total_empty * bev_ratio)
        target_s230 = int(total_empty * s230_ratio)
        
        print(f"\nTarget allocations:")
        print(f"BEV: {target_bev} positions")
        print(f"S230: {target_s230} positions")
        
        # Allocate positions based on scores and target ratios
        bev_allocated = 0
        s230_allocated = 0
        
        # Track current area and floor for logging
        current_area = None
        current_floor = None
        
        for score_data in position_scores:
            empty_pos = score_data['position']
            bev_score = score_data['bev_score']
            s230_score = score_data['s230_score']
            
            # Log area and floor changes
            if current_area != empty_pos['AREA_ID'] or current_floor != empty_pos['FLOOR_ID']:
                current_area = empty_pos['AREA_ID']
                current_floor = empty_pos['FLOOR_ID']
                print(f"\nProcessing Area {empty_pos['AREA_NAME']}, Floor {empty_pos['FLOOR_NAME']}")
            
            # Get additional position details
            cursor.execute("""
                SELECT 
                    mp.POSITION_NAME,
                    mr.RACK_NAME,
                    mf.FLOOR_NAME,
                    ma.AREA_NAME
                FROM 
                    ats_wms_master_position_details mp
                    LEFT JOIN ats_wms_master_rack_details mr ON mp.RACK_ID = mr.RACK_ID
                    LEFT JOIN ats_wms_master_floor_details mf ON mp.FLOOR_ID = mf.FLOOR_ID
                    LEFT JOIN ats_wms_master_area_details ma ON mp.AREA_ID = ma.AREA_ID
                WHERE 
                    mp.POSITION_ID = ?
            """, (empty_pos['POSITION_ID'],))
            
            pos_details = cursor.fetchone()
            
            # Determine which product to allocate based on scores and target ratios
            if bev_score > 0 and bev_allocated < target_bev and (bev_score >= s230_score or s230_allocated >= target_s230):
                # Insert BEV position
                insert_query = """
                INSERT INTO ats_wms_optimal_position (
                    PRODUCT_VARIANT_CODE,
                    POSITION_ID,
                    POSITION_NAME,
                    RACK_ID,
                    RACK_NAME,
                    FLOOR_ID,
                    FLOOR_NAME,
                    AREA_ID,
                    AREA_NAME,
                    CDATETIME,
                    USER_ID,
                    USER_NAME,
                    IS_ACTIVE,
                    IS_DELETED
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                
                cursor.execute(insert_query, 
                             'BEV',
                             empty_pos['POSITION_ID'],
                             pos_details[0] if pos_details else None,
                             empty_pos['RACK_ID'],
                             pos_details[1] if pos_details else None,
                             empty_pos['FLOOR_ID'],
                             pos_details[2] if pos_details else None,
                             empty_pos['AREA_ID'],
                             pos_details[3] if pos_details else None,
                             datetime.now(),
                             1,
                             'System',
                             1,
                             0
                             )
                bev_allocated += 1
                print(f"  Allocated position {empty_pos['POSITION_NAME']} to BEV")
                
            elif s230_score > 0 and s230_allocated < target_s230 and (s230_score > bev_score or bev_allocated >= target_bev):
                # Insert S230 position
                insert_query = """
                INSERT INTO ats_wms_optimal_position (
                    PRODUCT_VARIANT_CODE,
                    POSITION_ID,
                    POSITION_NAME,
                    RACK_ID,
                    RACK_NAME,
                    FLOOR_ID,
                    FLOOR_NAME,
                    AREA_ID,
                    AREA_NAME,
                    CDATETIME,
                    USER_ID,
                    USER_NAME,
                    IS_ACTIVE,
                    IS_DELETED
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                
                cursor.execute(insert_query, 
                             'S230',
                             empty_pos['POSITION_ID'],
                             pos_details[0] if pos_details else None,
                             empty_pos['RACK_ID'],
                             pos_details[1] if pos_details else None,
                             empty_pos['FLOOR_ID'],
                             pos_details[2] if pos_details else None,
                             empty_pos['AREA_ID'],
                             pos_details[3] if pos_details else None,
                             datetime.now(),
                             1,
                             'System',
                             1,
                             0
                             )
                s230_allocated += 1
                print(f"  Allocated position {empty_pos['POSITION_NAME']} to S230")
        
        # Commit the changes
        conn.commit()
        print("\nAll optimal positions have been inserted successfully!")
        
        # Print summary
        cursor.execute("""
            SELECT PRODUCT_VARIANT_CODE, COUNT(*) 
            FROM ats_wms_optimal_position 
            GROUP BY PRODUCT_VARIANT_CODE
        """)
        summary = cursor.fetchall()
        print("\nSummary of optimal positions inserted:")
        for product_type, count in summary:
            print(f"{product_type}: {count} positions")
        
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