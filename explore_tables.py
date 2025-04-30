import pyodbc
import pandas as pd

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
    
    # Get list of all tables
    tables_query = """
    SELECT 
        t.TABLE_NAME,
        t.TABLE_TYPE,
        c.COLUMN_NAME,
        c.DATA_TYPE,
        c.CHARACTER_MAXIMUM_LENGTH,
        c.IS_NULLABLE
    FROM 
        INFORMATION_SCHEMA.TABLES t
    JOIN 
        INFORMATION_SCHEMA.COLUMNS c ON t.TABLE_NAME = c.TABLE_NAME
    WHERE 
        t.TABLE_TYPE = 'BASE TABLE'
    ORDER BY 
        t.TABLE_NAME, c.ORDINAL_POSITION
    """
    
    # Execute query and convert to DataFrame
    df = pd.read_sql(tables_query, conn)
    
    # Print table information
    print("Tables in the database:")
    print("=======================")
    
    # Group by table name and print information
    for table_name in df['TABLE_NAME'].unique():
        table_data = df[df['TABLE_NAME'] == table_name]
        print(f"\nTable: {table_name}")
        print("Columns:")
        for _, row in table_data.iterrows():
            print(f"  - {row['COLUMN_NAME']} ({row['DATA_TYPE']})")
        
        # Show sample data
        sample_query = f"SELECT TOP 5 * FROM {table_name}"
        try:
            sample_df = pd.read_sql(sample_query, conn)
            print("\nSample data:")
            print(sample_df)
            print("\n" + "="*50)
        except Exception as e:
            print(f"Could not fetch sample data: {e}")
            print("\n" + "="*50)
    
    # Close the connection
    conn.close()
    print("\nConnection closed successfully.")
    
except pyodbc.Error as e:
    print(f"Error: {e}") 