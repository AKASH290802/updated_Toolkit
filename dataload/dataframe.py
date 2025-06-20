import sys
sys.path.append(r"C:\DM_toolkit")  # Add project root to sys.path
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

def select_salesforce_object(object_list):
    import tkinter as tk
    selected = {'value': None}
    def on_select(event=None):
        sel = listbox.curselection()
        if sel:
            selected['value'] = listbox.get(sel[0])
            win.destroy()
    def on_filter(*args):
        filter_text = filter_var.get().lower()
        listbox.delete(0, tk.END)
        for obj in object_list:
            if filter_text in obj.lower():
                listbox.insert(tk.END, obj)
    root = tk.Tk()
    root.withdraw()
    win = tk.Toplevel()
    win.title("Salesforce Object Selection")
    win.geometry("800x600")
    win.grab_set()
    tk.Label(win, text="Type to filter, then select Salesforce object to load to:").pack(pady=10)
    filter_var = tk.StringVar()
    filter_var.trace_add('write', on_filter)
    filter_entry = tk.Entry(win, textvariable=filter_var, width=80)
    filter_entry.pack(padx=20, pady=10)
    filter_entry.focus_set()
    listbox = tk.Listbox(win, selectmode=tk.SINGLE, width=100, height=30)
    for obj in object_list:
        listbox.insert(tk.END, obj)
    listbox.pack(padx=20, pady=10, fill=tk.BOTH, expand=True)
    listbox.bind('<Double-1>', on_select)
    listbox.bind('<Return>', on_select)
    btn = tk.Button(win, text="Select", command=on_select)
    btn.pack(pady=20)
    win.wait_window()
    root.destroy()
    return selected['value']

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
        object_list = list(salesforce_conn.describe()['sobjects'])
        object_names = [obj['name'] for obj in object_list]
        filtered_objects = [name for name in object_names if name.lower() == 'account' or 'wod' in name.lower()]
        filtered_objects.sort()
        if not filtered_objects:
            raise ValueError("No eligible Salesforce objects found (Account or objects containing 'wod').")
        object_name = select_salesforce_object(filtered_objects)

        # Select data source using a dropdown
        def on_select_source():
            nonlocal choice
            choice = var.get()
            win.destroy()
        choice = None
        root = tk.Tk()
        root.withdraw()
        win = tk.Toplevel()
        win.title("Select Data Source")
        win.geometry("400x200")
        win.grab_set()
        tk.Label(win, text="Select the data source:").pack(pady=20)
        var = tk.StringVar(win)
        var.set(SOURCES[0])
        dropdown = tk.OptionMenu(win, var, *SOURCES)
        dropdown.config(width=30)
        dropdown.pack(padx=20, pady=20)
        btn = tk.Button(win, text="Select", command=on_select_source)
        btn.pack(pady=20)
        win.wait_window()
        root.destroy()
        choice = validate_choice(choice, SOURCES)

        # Fetch data based on source
        if choice == 'excel/csv':
            root = tk.Tk()
            root.withdraw()
            file_path = filedialog.askopenfilename(title="Select a CSV or Excel file", filetypes=[("CSV files", "*.csv"), ("Excel files", "*.xlsx;*.xls"), ("All files", "*.*")])
            if not file_path:
                raise ValueError("No file selected")
            if file_path.endswith('.xlsx'):
                try:
                    df = pd.read_excel(file_path)
                except Exception as e:
                    logger.error(f"Failed to read .xlsx file: {e}")
                    raise
            elif file_path.endswith('.xls'):
                try:
                    df = pd.read_excel(file_path)
                except Exception as e:
                    logger.error(f"Failed to read .xls file: {e}")
                    raise
            elif file_path.endswith('.csv'):
                try:
                    df = pd.read_csv(file_path)
                except UnicodeDecodeError:
                    df = pd.read_csv(file_path, encoding='latin1')
            else:
                raise ValueError("Unsupported file format. Please select a CSV or Excel file.")
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