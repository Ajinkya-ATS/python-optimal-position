import pyodbc
import pandas as pd
from config import get_connection_string

def get_connection():
    """Create and return a database connection"""
    try:
        conn = pyodbc.connect(get_connection_string())
        return conn
    except pyodbc.Error as e:
        print(f"Error connecting to database: {e}")
        raise

def execute_query(query, params=None):
    """Execute a SQL query and return results as a pandas DataFrame"""
    try:
        with get_connection() as conn:
            if params:
                df = pd.read_sql(query, conn, params=params)
            else:
                df = pd.read_sql(query, conn)
            return df
    except Exception as e:
        print(f"Error executing query: {e}")
        raise

def test_connection():
    """Test the database connection"""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            return result[0] == 1
    except Exception as e:
        print(f"Connection test failed: {e}")
        return False 