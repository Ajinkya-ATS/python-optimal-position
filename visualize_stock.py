import pyodbc
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import numpy as np

# Set the style for better looking plots
plt.style.use('ggplot')
sns.set_palette("husl")

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
        QUANTITY,
        AREA_NAME,
        FLOOR_NAME,
        RACK_NAME,
        PALLET_STATUS_NAME,
        LOAD_DATETIME,
        MFG_DATE,
        MFG_SHIFT
    FROM 
        ats_wms_current_stock_details
    """
    
    # Execute query and convert to DataFrame
    df = pd.read_sql(stock_query, conn)
    
    # Convert datetime columns
    df['LOAD_DATETIME'] = pd.to_datetime(df['LOAD_DATETIME'])
    df['DAYS_IN_STOCK'] = (datetime.now() - df['LOAD_DATETIME']).dt.days
    
    # Create a figure with multiple subplots
    plt.figure(figsize=(20, 15))
    
    # 1. Product Distribution Pie Chart
    plt.subplot(2, 2, 1)
    product_counts = df['PRODUCT_NAME'].value_counts()
    plt.pie(product_counts, labels=product_counts.index, autopct='%1.1f%%', startangle=90)
    plt.title('Product Distribution by Number of Pallets')
    plt.axis('equal')
    
    # 2. Status Distribution Bar Chart
    plt.subplot(2, 2, 2)
    status_counts = df['PALLET_STATUS_NAME'].value_counts()
    sns.barplot(x=status_counts.index, y=status_counts.values)
    plt.title('Pallet Status Distribution')
    plt.xticks(rotation=45)
    plt.ylabel('Number of Pallets')
    
    # 3. Stock Age Distribution
    plt.subplot(2, 2, 3)
    # Group days into bins for better visualization
    bins = [0, 30, 60, 90, 180, 365]
    labels = ['0-30 days', '31-60 days', '61-90 days', '91-180 days', '>180 days']
    df['AGE_GROUP'] = pd.cut(df['DAYS_IN_STOCK'], bins=bins, labels=labels)
    age_distribution = df['AGE_GROUP'].value_counts().sort_index()
    sns.barplot(x=age_distribution.index, y=age_distribution.values)
    plt.title('Stock Age Distribution')
    plt.xticks(rotation=45)
    plt.ylabel('Number of Pallets')
    
    # 4. Area-wise Stock Distribution
    plt.subplot(2, 2, 4)
    area_stock = df.groupby('AREA_NAME')['QUANTITY'].sum()
    sns.barplot(x=area_stock.index, y=area_stock.values)
    plt.title('Stock Quantity by Area')
    plt.ylabel('Total Quantity')
    
    # Adjust layout and save the figure
    plt.tight_layout()
    plt.savefig('stock_analysis.png')
    print("Visualization saved as 'stock_analysis.png'")
    
    # Create additional visualizations
    plt.figure(figsize=(15, 10))
    
    # 5. Floor-wise Stock Distribution
    plt.subplot(2, 1, 1)
    floor_stock = df.groupby('FLOOR_NAME')['QUANTITY'].sum()
    sns.barplot(x=floor_stock.index, y=floor_stock.values)
    plt.title('Stock Quantity by Floor')
    plt.ylabel('Total Quantity')
    plt.xticks(rotation=45)
    
    # 6. Manufacturing Shift Distribution
    plt.subplot(2, 1, 2)
    shift_distribution = df['MFG_SHIFT'].value_counts()
    sns.barplot(x=shift_distribution.index, y=shift_distribution.values)
    plt.title('Manufacturing Shift Distribution')
    plt.ylabel('Number of Pallets')
    
    plt.tight_layout()
    plt.savefig('additional_analysis.png')
    print("Additional visualizations saved as 'additional_analysis.png'")
    
    # Close the connection
    conn.close()
    print("\nConnection closed successfully.")
    
except pyodbc.Error as e:
    print(f"Error: {e}")
except Exception as e:
    print(f"Error creating visualizations: {e}") 