import pyodbc
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import numpy as np

# Set style for better-looking plots
plt.style.use('ggplot')
plt.rcParams['figure.figsize'] = (15, 10)
plt.rcParams['font.size'] = 10

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
    
    # Query to get data
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
        PALLET_STATUS_NAME,
        LOAD_DATETIME,
        MFG_DATE,
        MFG_SHIFT
    FROM 
        ats_wms_current_stock_details
    """
    
    # Execute query and convert to DataFrame
    df = pd.read_sql(stock_query, conn)
    df['LOAD_DATETIME'] = pd.to_datetime(df['LOAD_DATETIME'])
    df['DAYS_IN_STOCK'] = (datetime.now() - df['LOAD_DATETIME']).dt.days
    
    # Create subplots
    fig = plt.figure(figsize=(20, 25))
    
    # 1. Pallet Status Distribution (Pie Chart)
    plt.subplot(3, 2, 1)
    status_counts = df['PALLET_STATUS_NAME'].value_counts()
    colors = ['#ff9999', '#66b3ff', '#99ff99']
    plt.pie(status_counts, labels=status_counts.index, autopct='%1.1f%%', 
            colors=colors, startangle=90)
    plt.title('Pallet Status Distribution')
    
    # 2. Product Distribution (Bar Chart)
    plt.subplot(3, 2, 2)
    product_counts = df.groupby('PRODUCT_NAME').agg({
        'PALLET_INFORMATION_ID': 'count',
        'QUANTITY': 'sum'
    })
    product_counts.plot(kind='bar', ax=plt.gca())
    plt.title('Product Distribution')
    plt.xlabel('Product Name')
    plt.xticks(rotation=45)
    plt.legend(['Number of Pallets', 'Total Quantity'])
    
    # 3. Age Analysis (Histogram)
    plt.subplot(3, 2, 3)
    bins = [0, 7, 30, 90, 180, 365]
    labels = ['< 7 days', '7-30 days', '31-90 days', '91-180 days', '181-365 days']
    df['AGE_GROUP'] = pd.cut(df['DAYS_IN_STOCK'], bins=bins, labels=labels)
    age_dist = df['AGE_GROUP'].value_counts().sort_index()
    sns.barplot(x=age_dist.index, y=age_dist.values)
    plt.title('Stock Age Distribution')
    plt.xlabel('Age Group')
    plt.ylabel('Number of Pallets')
    plt.xticks(rotation=45)
    
    # 4. Area-wise Distribution (Bar Chart)
    plt.subplot(3, 2, 4)
    area_analysis = df.groupby('AREA_NAME').agg({
        'PALLET_INFORMATION_ID': 'count',
        'QUANTITY': 'sum'
    })
    area_analysis.plot(kind='bar', ax=plt.gca())
    plt.title('Area-wise Distribution')
    plt.xlabel('Area')
    plt.ylabel('Count')
    plt.legend(['Number of Pallets', 'Total Quantity'])
    
    # 5. Manufacturing Shift Distribution (Bar Chart)
    plt.subplot(3, 2, 5)
    shift_dist = df['MFG_SHIFT'].value_counts().sort_index()
    sns.barplot(x=shift_dist.index, y=shift_dist.values)
    plt.title('Manufacturing Shift Distribution')
    plt.xlabel('Shift')
    plt.ylabel('Number of Pallets')
    
    # 6. Floor-wise Distribution (Heatmap)
    plt.subplot(3, 2, 6)
    floor_area_pivot = pd.pivot_table(
        df, 
        values='QUANTITY',
        index='FLOOR_NAME',
        columns='AREA_NAME',
        aggfunc='sum',
        fill_value=0
    )
    sns.heatmap(floor_area_pivot, annot=True, fmt='.0f', cmap='YlOrRd')
    plt.title('Floor-wise Quantity Distribution by Area')
    
    # Adjust layout and save
    plt.tight_layout(pad=3.0)
    plt.savefig('warehouse_analysis_dashboard.png', dpi=300, bbox_inches='tight')
    print("Dashboard saved as 'warehouse_analysis_dashboard.png'")
    
    # Create a second figure for detailed rack analysis
    plt.figure(figsize=(20, 10))
    
    # Rack Utilization Heatmap
    rack_pivot = pd.pivot_table(
        df,
        values='QUANTITY',
        index='RACK_NAME',
        columns='AREA_NAME',
        aggfunc='sum',
        fill_value=0
    )
    
    plt.subplot(1, 1, 1)
    sns.heatmap(rack_pivot, annot=True, fmt='.0f', cmap='YlOrRd')
    plt.title('Rack Utilization Heatmap')
    
    plt.tight_layout()
    plt.savefig('rack_analysis.png', dpi=300, bbox_inches='tight')
    print("Rack analysis saved as 'rack_analysis.png'")
    
    # Close the connection
    conn.close()
    print("\nConnection closed successfully.")
    
except pyodbc.Error as e:
    print(f"Error: {e}")
except Exception as e:
    print(f"Error creating visualizations: {e}")
finally:
    plt.close('all') 