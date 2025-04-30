# MS SQL Server Data Analytics Dashboard

This project connects to a Microsoft SQL Server database, performs data analysis, and displays the results in interactive dashboards.

## Setup Instructions

1. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Create a `.env` file in the project root with your database credentials:
   ```
   DB_SERVER=your_server_name
   DB_NAME=your_database_name
   DB_USERNAME=your_username
   DB_PASSWORD=your_password
   ```

3. Make sure you have the ODBC Driver 17 for SQL Server installed on your system.

4. Test the database connection:
   ```python
   from database import test_connection
   test_connection()
   ```

## Project Structure

- `config.py`: Database configuration settings
- `database.py`: Database connection and query functions
- `requirements.txt`: Project dependencies

## Next Steps

1. Create data analysis scripts in the `analysis` directory
2. Build dashboards using Dash and Plotly
3. Add data visualization components

## Requirements

- Python 3.8+
- ODBC Driver 17 for SQL Server
- Dependencies listed in requirements.txt 