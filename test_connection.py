import pyodbc

# Database credentials
server = 'ATSINDIA3D39\\SQLEXPRESS'
database = 'ats_wms_mahindra_battery_db'
username = 'ats-india'
password = 'Ats123*'
driver = '{ODBC Driver 17 for SQL Server}'

# Create connection string
conn_str = f"DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password}"

try:
    # Attempt to connect
    conn = pyodbc.connect(conn_str)
    print("Successfully connected to the database!")
    
    # Test a simple query
    cursor = conn.cursor()
    cursor.execute("SELECT 1")
    result = cursor.fetchone()
    print(f"Test query result: {result[0]}")
    
    # Close the connection
    conn.close()
    print("Connection closed successfully.")
    
except pyodbc.Error as e:
    print(f"Error connecting to database: {e}")
    print("\nTroubleshooting tips:")
    print("1. Verify the server name is correct")
    print("2. Check if the SQL Server is running")
    print("3. Ensure the username and password are correct")
    print("4. Make sure the database exists")
    print("5. Check if your IP is allowed to connect to the server") 