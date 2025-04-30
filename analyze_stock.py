import pyodbc
import pandas as pd
from datetime import datetime

# Database credentials
server = 'ATSINDIA3D39\\SQLEXPRESS'
database = 'ats_wms_mahindra_battery_db'
username = 'ats-india'
password = 'Ats123*'
driver = '{ODBC Driver 17 for SQL Server}'

# Create connection string
conn_str = f"DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password}"

try:
    # Connect to the database
    conn = pyodbc.connect(conn_str)
    print("Successfully connected to the database!\n")
    
    # Query to get all data from current stock details
    stock_query = """
    SELECT 
        PALLET_INFORMATION_ID,
        PALLET_CODE,
        PRODUCT_ID,
        PRODUCT_NAME,
        PRODUCT_VARIANT_ID,
        PRODUCT_VARIANT_NAME,
        PRODUCT_VARIANT_CODE,
        BATCH_NUMBER,
        MODEL_NUMBER,
        QUANTITY,
        POSITION_ID,
        POSITION_NAME,
        AREA_ID,
        AREA_NAME,
        FLOOR_ID,
        FLOOR_NAME,
        RACK_ID,
        RACK_NAME,
        RACK_SIDE,
        RACK_COLUMN,
        POSITION_NUMBER_IN_RACK,
        PALLET_STATUS_ID,
        PALLET_STATUS_NAME,
        LOAD_DATETIME,
        EXPIRY_DATE,
        MFG_DATE,
        MFG_SHIFT,
        SERIAL_NUMBER,
        VENDOR_CODE,
        PART_IDENTIFICATION_CODE
    FROM 
        ats_wms_current_stock_details
    """
    
    # Execute query and convert to DataFrame
    df = pd.read_sql(stock_query, conn)
    
    # Basic Analysis
    print("\n=== Basic Stock Analysis ===")
    print(f"Total number of pallets: {len(df)}")
    print(f"Total quantity across all pallets: {df['QUANTITY'].sum()}")
    
    # Product-wise Analysis
    product_analysis = df.groupby('PRODUCT_NAME').agg({
        'QUANTITY': 'sum',
        'PALLET_INFORMATION_ID': 'count'
    }).rename(columns={
        'PALLET_INFORMATION_ID': 'Number of Pallets',
        'QUANTITY': 'Total Quantity'
    })
    
    print("\n=== Product-wise Analysis ===")
    print(product_analysis)
    
    # Location-wise Analysis
    location_analysis = df.groupby(['AREA_NAME', 'FLOOR_NAME', 'RACK_NAME']).agg({
        'QUANTITY': 'sum',
        'PALLET_INFORMATION_ID': 'count'
    }).rename(columns={
        'PALLET_INFORMATION_ID': 'Number of Pallets',
        'QUANTITY': 'Total Quantity'
    })
    
    print("\n=== Location-wise Analysis ===")
    print(location_analysis)
    
    # Status-wise Analysis
    status_analysis = df.groupby('PALLET_STATUS_NAME').agg({
        'QUANTITY': 'sum',
        'PALLET_INFORMATION_ID': 'count'
    }).rename(columns={
        'PALLET_INFORMATION_ID': 'Number of Pallets',
        'QUANTITY': 'Total Quantity'
    })
    
    print("\n=== Status-wise Analysis ===")
    print(status_analysis)
    
    # Age Analysis (based on LOAD_DATETIME)
    if 'LOAD_DATETIME' in df.columns:
        df['LOAD_DATETIME'] = pd.to_datetime(df['LOAD_DATETIME'])
        df['DAYS_IN_STOCK'] = (datetime.now() - df['LOAD_DATETIME']).dt.days
        
        age_analysis = df.groupby('DAYS_IN_STOCK').agg({
            'PALLET_INFORMATION_ID': 'count',
            'QUANTITY': 'sum'
        }).rename(columns={
            'PALLET_INFORMATION_ID': 'Number of Pallets',
            'QUANTITY': 'Total Quantity'
        })
        
        print("\n=== Age Analysis ===")
        print(age_analysis)
    
    # Close the connection
    conn.close()
    print("\nConnection closed successfully.")
    
except pyodbc.Error as e:
    print(f"Error: {e}") 