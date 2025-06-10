import pandas as pd
import dataset.Connections as Connections
from sqlalchemy import text, inspect
import re
import logging
import tkinter as tk
from tkinter import simpledialog, filedialog

# Configure logging (console only, no file)
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',  # Clean format, no timestamp
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# load data into sql using salesforce query or excel/csv file using dataframe
load_mechanism = input("Enter the load mechanism (salesforce/file): ").lower()
if load_mechanism not in ['salesforce', 'file']:
    logger.error("Invalid load mechanism. Please enter 'salesforce' or 'file'.")
    raise ValueError("Invalid load mechanism")

if load_mechanism == 'file':
    root = tk.Tk()
    root.withdraw()  # Hide the root window
    file_path = filedialog.askopenfilename(
        title="Select data file",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
    )
    if not file_path:
        logger.error("No file path provided.")
        raise ValueError("File path cannot be empty")
    df = pd.read_csv(file_path) if file_path.endswith('.csv') else pd.read_excel(file_path)
    logger.info(f"Data loaded from {file_path} with {len(df)} records")
    table_name = input("Enter table name:   ")
    sql_conn, sql_engine = Connections.get_sql_connection()
    try:
        df.to_sql(name=table_name, con=sql_engine, if_exists='replace', index=False)
    except Exception as e:
        logger.error(f"Error writing to SQL table: {e}")
        raise
elif load_mechanism == 'salesforce':

    # Get Salesforce connection
    try:
        salesforce = Connections.get_salesforce_connection()
        logger.info("Salesforce connection established")
    except Exception as e:
        logger.error(f"Failed to connect to Salesforce: {e}")
        raise

    # Salesforce query
    query = input("Enter your Query: ")
    # logger.info(f"Executing query: {query}")

    def extract_table_name(query: str) -> str:
        match = re.search(r'\bfrom\s+([^\s;]+)', query, re.IGNORECASE)
        if match:
            table = match.group(1).strip()
            table = table.replace('__c', '').replace('__', '_')
            logger.info(f"Table name: {table}")
            return table
        logger.error("Could not extract table name from query")
        raise ValueError("Invalid query: table name not found")

    # Extract table name
    table_name = extract_table_name(query)

    # Fetch Salesforce data
    try:
        salesforce_data = salesforce.query_all(query)
        df = pd.DataFrame(salesforce_data['records']).drop(columns='attributes', errors='ignore')
        logger.info(f"Fetched {len(df)} records from Salesforce")
    except Exception as e:
        logger.error(f"Failed to fetch Salesforce data: {e}")
        raise

# Get SQL connection and engine
try:
    sql_conn, sql_engine = Connections.get_sql_connection()
    logger.info("SQL Server connection established")
except Exception as e:
    logger.error(f"Failed to connect to SQL Server: {e}")
    raise

# Check if table exists, create if it doesn't
inspector = inspect(sql_engine)
if not inspector.has_table(table_name):
    logger.info(f"Creating table {table_name}...")
    try:
        df.to_sql(table_name, con=sql_engine, if_exists='replace', index=False)
        logger.info(f"Table {table_name} created and {len(df)} records loaded successfully")
    except Exception as e:
        logger.error(f"Failed to create table: {e}")
        raise
else:
    try:
        sql_conn.execute(text(f"TRUNCATE TABLE {table_name}"))
        sql_conn.commit()
        logger.info(f"Table {table_name} truncated successfully")
    except Exception as e:
        logger.error(f"Error truncating table {table_name} failed: {e}")
        raise
    
    try:
        df.to_sql(table_name, con=sql_engine, if_exists='append', index=False)
        logger.info(f"{len(df)} successfully loaded to {table_name} records into table {table_name} successfully")
    except Exception as e:
        logger.error(f"Error loading data to {table_name} failed: {e}")
        raise

# Close the connection
try:
    sql_conn.close()
    sql_engine.dispose()
    logger.info("SQL connection closed")
except Exception as e:
    logger.error(f"Error closing SQL connection failed: {e}")