import dataset.Connections as Connections
import pandas as pd
import dataset.Org_selection as Org_selection
import tkinter as tk
from tkinter import filedialog, ttk
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Valid data sources
SOURCES = ['excel/csv', 'sql', 'salesforce']

def validate_choice(choice, valid_options):
    """Validate user choice against valid options."""
    choice = choice.lower()
    if choice not in [opt.lower() for opt in valid_options]:
        raise ValueError(f"Invalid choice: {choice}. Valid options: {valid_options}")
    return choice

def select_salesforce_object(salesforce_conn):
    """Display a Tkinter Combobox to select a Salesforce object."""
    # Fetch Salesforce objects (custom objects ending in __c or Account)
    objects = [
        obj['name'] for obj in salesforce_conn.describe()['sobjects']
        if obj['name'].endswith('__c') or obj['name'].lower() == 'account'
    ]
    
    selected_object = None
    
    def on_select(event):
        nonlocal selected_object
        selected_object = combo.get()
        logger.info(f"Selected Salesforce object: {selected_object}")
        root.destroy()

    # Create GUI window
    root = tk.Tk()
    root.title("Select Salesforce Object")
    root.geometry("400x120")

    label = ttk.Label(root, text="Choose a Salesforce object:")
    label.pack(pady=10)

    combo = ttk.Combobox(root, values=objects, state="readonly", width=50)
    combo.pack(pady=5)
    combo.bind("<<ComboboxSelected>>", on_select)

    root.mainloop()
    
    if not selected_object:
        raise ValueError("No Salesforce object selected")
    
    return selected_object

def main():
    sql_engine = None
    try:
        # Select organization
        selected_org = Org_selection.org_select()
        logger.info(f"Selected organization: {selected_org}")

        # Get connections
        credentials_path = os.getenv("CREDENTIALS_PATH", r"C:\DM_toolkit\Services\linkedservices.json")
        if not os.path.exists(credentials_path):
            raise FileNotFoundError(f"Credentials file not found: {credentials_path}")
        
        salesforce_conn = Connections.get_salesforce_connection(file_path=credentials_path, org_name=selected_org)
        sql_conn, sql_engine = Connections.get_sql_connection(file_path=credentials_path)

        # Select Salesforce object via GUI
        object_name = select_salesforce_object(salesforce_conn)

        # Select data source
        print(f"Available data sources: {SOURCES}")
        choice = validate_choice(input("Enter the data source (Excel/csv, SQL, Salesforce): "), SOURCES)

        # Fetch data based on source
        if choice == 'excel/csv':
            root = tk.Tk()
            root.withdraw()
            file_path = filedialog.askopenfilename(title="Select a CSV file", filetypes=[("CSV files", "*.csv")])
            if not file_path:
                raise ValueError("No file selected")
            df = pd.read_csv(file_path)
            logger.info(f"DataFrame created from {file_path}")

        elif choice == 'sql':
            check_query = input("Do you have a query? (Yes/No): ").lower()
            if check_query == 'no':
                sql_query = f"SELECT * FROM stg.[{object_name}]"
            else:
                sql_query = input("Enter your SQL query: ").strip()
            df = Connections.run_sql_query(sql_engine, sql_query)
            logger.info(f"SQL query executed: {sql_query}")
            if df.empty:
                logger.warning("SQL query returned no data")

        elif choice == 'salesforce':
            check_query = input("Do you have a query? (Yes/No): ").lower()
            if check_query == 'no':
                sf_query = f"SELECT Id, Name FROM {object_name}"
            else:
                sf_query = input("Enter your Salesforce query: ").strip()
            sf_result = Connections.run_salesforce_query(salesforce_conn, sf_query)
            df = pd.DataFrame(sf_result['records']).drop(columns='attributes', errors='ignore')
            logger.info(f"Salesforce query executed: {sf_query}")
            if df.empty:
                logger.warning("Salesforce query returned no data")

        # Save DataFrame
        root_folder = "DataFiles"
        object_folder = os.path.join(root_folder, selected_org, object_name)
        csv_file_name = f"{choice}_{selected_org}__{object_name}.csv"
        csv_file_path = os.path.join(object_folder, csv_file_name)

        os.makedirs(object_folder, exist_ok=True)
        df.to_csv(csv_file_path, index=False)
        logger.info(f"DataFrame saved to {csv_file_path}")

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise
    finally:
        if sql_engine:
            sql_engine.dispose()
            logger.info("SQL engine disposed")

if __name__ == "__main__":
    main()