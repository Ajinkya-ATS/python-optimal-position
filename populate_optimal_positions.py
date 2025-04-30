import pyodbc
import json
import pandas as pd

# Database credentials
server = 'ATSINDIA3D39\\SQLEXPRESS'
database = 'ats_wms_mahindra_battery_db'
username = 'ats-india'
password = 'Ats123*'
driver = '{ODBC Driver 17 for SQL Server}'

# Create connection string
conn_str = f"DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password}"

def populate_optimal_positions():
    try:
        # Connect to the database
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        print("Successfully connected to the database!\n")

        # Read the optimal positions data from JSON
        with open('optimal_positions.json', 'r') as f:
            optimal_data = json.load(f)

        # Process each product type (BEV and S230)
        for product_type in ['BEV', 'S230']:
            print(f"\nProcessing {product_type} positions...")
            
            # Get the optimal positions for this product type
            positions = optimal_data['optimal_positions'][product_type]
            
            for pos in positions:
                # Update the view with proximity score and nearby products
                update_query = """
                UPDATE ats_wms_optimal_positions
                SET 
                    proximity_score = ?,
                    nearby_products = ?
                WHERE 
                    POSITION_ID = ?
                """
                
                cursor.execute(update_query, 
                             pos['proximity_score'],
                             str(pos['nearby_products']),
                             pos['position_id'])
            
            print(f"Updated {len(positions)} positions for {product_type}")

        # Commit the changes
        conn.commit()
        print("\nAll optimal positions have been updated successfully!")

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

if __name__ == "__main__":
    populate_optimal_positions() 