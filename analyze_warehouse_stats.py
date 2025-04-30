import pyodbc
import pandas as pd
from datetime import datetime
import numpy as np

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
        PRODUCT_NAME,
        PRODUCT_VARIANT_NAME,
        PRODUCT_VARIANT_CODE,
        QUANTITY,
        AREA_NAME,
        FLOOR_NAME,
        RACK_NAME,
        RACK_SIDE,
        RACK_COLUMN,
        POSITION_NUMBER_IN_RACK,
        PALLET_STATUS_NAME,
        LOAD_DATETIME,
        MFG_DATE,
        MFG_SHIFT,
        BATCH_NUMBER,
        VENDOR_CODE,
        PART_IDENTIFICATION_CODE
    FROM 
        ats_wms_current_stock_details
    """
    
    # Execute query and convert to DataFrame
    df = pd.read_sql(stock_query, conn)
    
    # Convert datetime columns
    df['LOAD_DATETIME'] = pd.to_datetime(df['LOAD_DATETIME'])
    df['MFG_DATE'] = pd.to_datetime(df['MFG_DATE'])
    df['DAYS_IN_STOCK'] = (datetime.now() - df['LOAD_DATETIME']).dt.days
    
    # Generate comprehensive report
    print("\n=== WAREHOUSE INVENTORY ANALYSIS REPORT ===")
    print("=" * 40)
    
    print("\n1. OVERALL STATISTICS")
    print("-" * 20)
    print(f"Total Number of Pallets: {len(df)}")
    print(f"Total Quantity in Stock: {df['QUANTITY'].sum()}")
    print(f"Number of Unique Products: {df['PRODUCT_NAME'].nunique()}")
    print(f"Number of Product Variants: {df['PRODUCT_VARIANT_NAME'].nunique()}")
    
    print("\n2. PALLET STATUS BREAKDOWN")
    print("-" * 20)
    status_breakdown = df['PALLET_STATUS_NAME'].value_counts()
    for status, count in status_breakdown.items():
        print(f"{status}: {count} pallets ({(count/len(df)*100):.1f}%)")
    
    print("\n3. PRODUCT-WISE ANALYSIS")
    print("-" * 20)
    product_analysis = df.groupby('PRODUCT_NAME').agg({
        'QUANTITY': ['sum', 'mean'],
        'PALLET_INFORMATION_ID': 'count'
    }).round(2)
    product_analysis.columns = ['Total Quantity', 'Average Quantity per Pallet', 'Number of Pallets']
    print(product_analysis)
    
    print("\n4. STORAGE LOCATION ANALYSIS")
    print("-" * 20)
    area_analysis = df.groupby('AREA_NAME').agg({
        'PALLET_INFORMATION_ID': 'count',
        'QUANTITY': 'sum'
    }).round(2)
    print("\nArea-wise Distribution:")
    print(area_analysis)
    
    print("\n5. AGE ANALYSIS")
    print("-" * 20)
    # Create age bins
    bins = [0, 7, 30, 90, 180, 365, float('inf')]
    labels = ['< 7 days', '7-30 days', '31-90 days', '91-180 days', '181-365 days', '> 365 days']
    df['AGE_GROUP'] = pd.cut(df['DAYS_IN_STOCK'], bins=bins, labels=labels)
    age_analysis = df['AGE_GROUP'].value_counts().sort_index()
    print("Stock Age Distribution:")
    for age, count in age_analysis.items():
        print(f"{age}: {count} pallets ({(count/len(df)*100):.1f}%)")
    
    print("\n6. MANUFACTURING SHIFT ANALYSIS")
    print("-" * 20)
    shift_analysis = df['MFG_SHIFT'].value_counts()
    print("Manufacturing Shift Distribution:")
    for shift, count in shift_analysis.items():
        print(f"Shift {shift}: {count} pallets ({(count/len(df)*100):.1f}%)")
    
    print("\n7. RACK UTILIZATION")
    print("-" * 20)
    rack_analysis = df.groupby(['AREA_NAME', 'RACK_NAME']).agg({
        'PALLET_INFORMATION_ID': 'count',
        'QUANTITY': 'sum'
    }).round(2)
    print("\nRack-wise Utilization:")
    print(rack_analysis)
    
    print("\n8. CRITICAL METRICS")
    print("-" * 20)
    full_pallets = len(df[df['PALLET_STATUS_NAME'] == 'FULL'])
    empty_pallets = len(df[df['PALLET_STATUS_NAME'] == 'EMPTY'])
    old_stock = len(df[df['DAYS_IN_STOCK'] > 180])
    print(f"Full Pallets: {full_pallets}")
    print(f"Empty Pallets: {empty_pallets}")
    print(f"Stock > 180 days old: {old_stock} pallets")
    
    # Close the connection
    conn.close()
    print("\nConnection closed successfully.")
    
except pyodbc.Error as e:
    print(f"Error: {e}")
except Exception as e:
    print(f"Error generating report: {e}") 