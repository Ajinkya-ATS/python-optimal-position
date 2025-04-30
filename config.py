import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Database configuration
DB_CONFIG = {
    'server': os.getenv('DB_SERVER', 'your_server_name'),
    'database': os.getenv('DB_NAME', 'your_database_name'),
    'username': os.getenv('DB_USERNAME', 'your_username'),
    'password': os.getenv('DB_PASSWORD', 'your_password'),
    'driver': '{ODBC Driver 17 for SQL Server}'
}

# Connection string
def get_connection_string():
    return f"DRIVER={DB_CONFIG['driver']};SERVER={DB_CONFIG['server']};DATABASE={DB_CONFIG['database']};UID={DB_CONFIG['username']};PWD={DB_CONFIG['password']}" 