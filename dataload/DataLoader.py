import sys
import os
# Get the project root directory dynamically
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)  # Add project root to sys.path
import pandas as pd
import json
import simple_salesforce as sf
import tkinter
import tkinter.filedialog
import tkinter.messagebox
import os
import tkinter.simpledialog
import dataset.Connections as Connections
from dataload.batch_config import select_batch_and_parallel_settings, simple_batch_size_dialog
import concurrent.futures
import threading
import time
import datetime
import csv

# --- Step 1: Select Salesforce Org ---
def select_org(orgs):
    import tkinter as tk
    selected = {'value': None}
    def on_select():
        selected['value'] = var.get()
        win.destroy()
    root = tk.Tk()
    root.withdraw()
    win = tk.Toplevel()
    win.title("Select Salesforce Org")
    win.geometry("600x250")
    win.grab_set()
    tk.Label(win, text="Select Salesforce Org:").pack(pady=20)
    var = tk.StringVar(win)
    var.set(orgs[0])
    dropdown = tk.OptionMenu(win, var, *orgs)
    dropdown.config(width=60)
    dropdown.pack(padx=20, pady=20)
    btn = tk.Button(win, text="Select", command=on_select)
    btn.pack(pady=20)
    win.wait_window()
    root.destroy()
    return selected['value']

with open(os.path.join(project_root, 'Services', 'linkedservices.json'), 'r') as f:
    creds = json.load(f)
orgs = list(creds.keys())
selected_org = select_org(orgs)
if not selected_org or selected_org not in creds:
    raise ValueError(f"Org '{selected_org}' not found in credentials file.")

sf_conn = sf.Salesforce(
    username=creds[selected_org]['username'],
    password=creds[selected_org]['password'],
    security_token=creds[selected_org]['security_token'],
    domain=creds[selected_org]['domain']
)

# --- Ask user for data source ---
def select_data_source():
    import tkinter as tk
    selected = {'value': None}
    def on_select():
        selected['value'] = var.get()
        win.destroy()
    root = tk.Tk()
    root.withdraw()
    win = tk.Toplevel()
    win.title("Select Data Source")
    win.geometry("400x200")
    win.grab_set()
    tk.Label(win, text="Select data source:").pack(pady=20)
    var = tk.StringVar(win)
    var.set("file")
    dropdown = tk.OptionMenu(win, var, "file", "sql")
    dropdown.config(width=30)
    dropdown.pack(padx=20, pady=20)
    btn = tk.Button(win, text="Select", command=on_select)
    btn.pack(pady=20)
    win.wait_window()
    root.destroy()
    return selected['value']

data_source = select_data_source()

if data_source == "sql":
    # Use Connections.get_sql_connection for SQL connection
    sql_conn, engine = Connections.get_sql_connection()
    query = tkinter.simpledialog.askstring("SQL Query", "Enter SQL query to fetch data:")
    if not query:
        raise ValueError("No SQL query provided.")
    df = pd.read_sql(query, engine)
elif data_source == "file":
    tkinter.Tk().withdraw()
    # Set default directory to DataLoader_Logs folder
    default_data_dir = os.path.join(project_root, 'DataLoader_Logs')
    file = tkinter.filedialog.askopenfilename(
        title="Select CSV or Excel File",
        initialdir=default_data_dir,
        filetypes=[("CSV files", "*.csv"), ("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
    )
    if not file:
        raise ValueError("No data file selected.")
    try:
        if file.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(file)
        elif file.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            raise ValueError("Unsupported file format. Please select a CSV or Excel file.")
        
        # Validate that we have data
        if df.empty:
            raise ValueError("The selected file is empty.")
        
        print(f"Loaded {len(df)} rows and {len(df.columns)} columns from data file.")
    except Exception as e:
        raise ValueError(f"Error reading data file: {e}")
else:
    raise ValueError("Invalid data source selected.")

# Use data as-is (no mapping needed for pre-transformed data)
df_mapped = df.copy()

# --- Step 3: Select Operation (insert/upsert) ---
def select_operation():
    import tkinter as tk
    selected = {'value': None}
    def on_select():
        selected['value'] = var.get()
        win.destroy()
    root = tk.Tk()
    root.withdraw()
    win = tk.Toplevel()
    win.title("Select Operation")
    win.geometry("400x200")
    win.grab_set()
    tk.Label(win, text="Select operation:").pack(pady=20)
    var = tk.StringVar(win)
    var.set("insert")
    dropdown = tk.OptionMenu(win, var, "insert", "upsert")
    dropdown.config(width=30)
    dropdown.pack(padx=20, pady=20)
    btn = tk.Button(win, text="Select", command=on_select)
    btn.pack(pady=20)
    win.wait_window()
    root.destroy()
    return selected['value']

operation = select_operation()
if operation not in ['insert', 'upsert']:
    raise ValueError("Operation must be 'insert' or 'upsert'.")

# --- Step 4: Select Salesforce Object ---
object_list = list(sf_conn.describe()['sobjects'])
object_names = [obj['name'] for obj in object_list]
filtered_objects = [name for name in object_names if name.lower() == 'account' or 'wod' in name.lower()]
filtered_objects.sort()
if not filtered_objects:
    raise ValueError("No eligible Salesforce objects found (Account or objects containing 'wod').")

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

selected_object = select_salesforce_object(filtered_objects)
if not selected_object or selected_object not in filtered_objects:
    raise ValueError("No valid Salesforce object selected.")
print(f"Selected Salesforce object: {selected_object}")

# --- Step 5: Prepare Data and Perform Load ---
df_mapped.columns = df_mapped.columns.str.strip()

# Clean the data to handle NaN, infinity, and other problematic values
def clean_dataframe_for_salesforce(df):
    """Clean DataFrame to make it JSON compliant for Salesforce"""
    df_clean = df.copy()
    
    # Replace NaN, inf, -inf with None
    df_clean = df_clean.replace([float('inf'), float('-inf')], None)
    df_clean = df_clean.where(pd.notnull(df_clean), None)
    
    # Convert numpy data types to Python native types
    for col in df_clean.columns:
        if df_clean[col].dtype == 'object':
            # Handle string columns - convert NaN to None and strip whitespace
            df_clean[col] = df_clean[col].apply(
                lambda x: str(x).strip() if pd.notnull(x) and str(x).strip() != 'nan' and str(x).strip() != '' else None
            )
        elif pd.api.types.is_numeric_dtype(df_clean[col]):
            # Handle numeric columns - ensure they're JSON compliant
            if pd.api.types.is_integer_dtype(df_clean[col]):
                # Convert to nullable integer, then to regular int where possible
                df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
                df_clean[col] = df_clean[col].apply(lambda x: int(x) if pd.notnull(x) and x == x else None)
            else:
                # Convert to float, handling NaN
                df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
                df_clean[col] = df_clean[col].apply(lambda x: float(x) if pd.notnull(x) and x == x and abs(x) != float('inf') else None)
        elif pd.api.types.is_datetime64_any_dtype(df_clean[col]):
            # Handle datetime columns
            df_clean[col] = df_clean[col].dt.strftime('%Y-%m-%dT%H:%M:%S.%fZ').where(pd.notnull(df_clean[col]), None)
        elif pd.api.types.is_bool_dtype(df_clean[col]):
            # Handle boolean columns
            df_clean[col] = df_clean[col].apply(lambda x: bool(x) if pd.notnull(x) else None)
    
    return df_clean

df_mapped = clean_dataframe_for_salesforce(df_mapped)

# Additional validation - check for any remaining problematic values
def validate_json_compliance(df):
    """Validate that DataFrame can be converted to JSON"""
    try:
        test_records = df.head(1).to_dict('records')
        json.dumps(test_records, allow_nan=False)
        return True
    except (ValueError, TypeError) as e:
        print(f"Data validation failed: {e}")
        
        # Try to identify problematic columns
        for col in df.columns:
            try:
                test_data = df[col].head(5).to_list()
                json.dumps(test_data, allow_nan=False)
            except (ValueError, TypeError) as col_error:
                print(f"  - Column '{col}' contains problematic values: {col_error}")
                print(f"    Sample values: {df[col].head(5).to_list()}")
                print(f"    Data type: {df[col].dtype}")
                print(f"    Unique values (first 10): {df[col].unique()[:10]}")
        
        return False

if not validate_json_compliance(df_mapped):
    raise ValueError("Data contains values that are not JSON compliant. Please check your data for NaN, infinity, or other problematic values.")

# --- Data Preview and Confirmation ---
def show_data_preview(df, selected_object):
    """Show data preview with Load/Cancel options and customizable preview settings"""
    import tkinter as tk
    from tkinter import ttk
    
    user_choice = {'value': None}
    preview_rows = {'value': 100}  # Default 100 rows
    selected_fields = {'value': list(df.columns)}  # Default all fields
    
    def show_settings():
        """Show settings dialog for preview customization"""
        settings_choice = {'rows': 100, 'fields': list(df.columns)}
        
        def on_settings_ok():
            try:
                # Get number of rows
                rows = int(rows_entry.get())
                if rows <= 0:
                    tkinter.messagebox.showerror("Invalid Input", "Number of rows must be greater than 0")
                    return
                if rows > len(df):
                    rows = len(df)
                    tkinter.messagebox.showinfo("Info", f"Adjusted to maximum available rows: {len(df)}")
                
                settings_choice['rows'] = rows
                
                # Get selected fields
                selected_indices = fields_listbox.curselection()
                if not selected_indices:
                    tkinter.messagebox.showerror("Invalid Selection", "Please select at least one field")
                    return
                
                selected_fields_list = [fields_listbox.get(i) for i in selected_indices]
                settings_choice['fields'] = selected_fields_list
                
                settings_win.destroy()
                
            except ValueError:
                tkinter.messagebox.showerror("Invalid Input", "Please enter a valid number for rows")
        
        def on_settings_cancel():
            settings_win.destroy()
        
        def select_all_fields():
            fields_listbox.select_set(0, tk.END)
        
        def clear_all_fields():
            fields_listbox.selection_clear(0, tk.END)
        
        settings_win = tk.Toplevel()
        settings_win.title("Preview Settings")
        settings_win.geometry("500x600")
        settings_win.grab_set()
        
        # Rows setting
        rows_frame = tk.Frame(settings_win)
        rows_frame.pack(pady=10, padx=20, fill=tk.X)
        tk.Label(rows_frame, text="Number of rows to preview:", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        rows_entry = tk.Entry(rows_frame, width=10)
        rows_entry.insert(0, str(preview_rows['value']))
        rows_entry.pack(anchor=tk.W, pady=5)
        tk.Label(rows_frame, text=f"(Maximum available: {len(df)})", font=("Arial", 9), fg="gray").pack(anchor=tk.W)
        
        # Fields setting
        fields_frame = tk.Frame(settings_win)
        fields_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        tk.Label(fields_frame, text="Select fields to preview:", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        
        # Fields listbox with scrollbar
        listbox_frame = tk.Frame(fields_frame)
        listbox_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        fields_listbox = tk.Listbox(listbox_frame, selectmode=tk.EXTENDED, height=15)
        fields_scrollbar = tk.Scrollbar(listbox_frame, orient=tk.VERTICAL, command=fields_listbox.yview)
        fields_listbox.configure(yscrollcommand=fields_scrollbar.set)
        
        for field in df.columns:
            fields_listbox.insert(tk.END, field)
        
        # Select all fields by default
        fields_listbox.select_set(0, tk.END)
        
        fields_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        fields_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Selection buttons
        selection_frame = tk.Frame(fields_frame)
        selection_frame.pack(fill=tk.X, pady=5)
        tk.Button(selection_frame, text="Select All", command=select_all_fields, width=12).pack(side=tk.LEFT, padx=5)
        tk.Button(selection_frame, text="Clear All", command=clear_all_fields, width=12).pack(side=tk.LEFT, padx=5)
        
        # Control buttons
        button_frame = tk.Frame(settings_win)
        button_frame.pack(pady=20)
        tk.Button(button_frame, text="OK", command=on_settings_ok, bg="#4CAF50", fg="white", 
                 font=("Arial", 10, "bold"), width=12).pack(side=tk.LEFT, padx=10)
        tk.Button(button_frame, text="Cancel", command=on_settings_cancel, bg="#f44336", fg="white", 
                 font=("Arial", 10, "bold"), width=12).pack(side=tk.LEFT, padx=10)
        
        settings_win.wait_window()
        return settings_choice
    
    def refresh_preview():
        """Refresh the preview with current settings"""
        settings = show_settings()
        if settings:
            preview_rows['value'] = settings['rows']
            selected_fields['value'] = settings['fields']
            update_preview_display()
    
    def update_preview_display():
        """Update the preview display with current settings"""
        # Clear existing items
        for item in tree.get_children():
            tree.delete(item)
        
        # Update tree columns
        tree.configure(columns=selected_fields['value'])
        
        # Configure column headings and widths
        for col in selected_fields['value']:
            tree.heading(col, text=col)
            tree.column(col, width=120, minwidth=80)
        
        # Add data to treeview
        preview_df = df[selected_fields['value']].head(preview_rows['value'])
        for idx, row in preview_df.iterrows():
            # Convert row values to strings and handle None values
            values = [str(val) if val is not None else '' for val in row.values]
            tree.insert('', tk.END, values=values)
        
        # Update info labels
        records_label.config(text=f"Total Records: {len(df)} | Showing: {len(preview_df)} rows | Columns: {len(selected_fields['value'])}")
        preview_label.config(text=f"Showing first {preview_rows['value']} rows of {len(selected_fields['value'])} selected columns")
    
    def on_load():
        user_choice['value'] = 'load'
        preview_win.destroy()
    
    def on_cancel():
        user_choice['value'] = 'cancel'
        preview_win.destroy()
    
    root = tk.Tk()
    root.withdraw()
    
    preview_win = tk.Toplevel()
    preview_win.title("Data Preview - Confirm Load")
    preview_win.geometry("1200x800")
    preview_win.grab_set()
    
    # Header info
    header_frame = tk.Frame(preview_win)
    header_frame.pack(pady=10, padx=20, fill=tk.X)
    
    tk.Label(header_frame, text=f"Data Preview for Salesforce Object: {selected_object}", 
             font=("Arial", 14, "bold")).pack()
    
    # Dynamic info labels
    records_label = tk.Label(header_frame, text=f"Total Records: {len(df)} | Showing: {preview_rows['value']} rows | Columns: {len(df.columns)}", 
                            font=("Arial", 10))
    records_label.pack()
    
    preview_label = tk.Label(header_frame, text=f"Showing first {preview_rows['value']} rows of {len(selected_fields['value'])} selected columns", 
                            font=("Arial", 10))
    preview_label.pack(pady=(5,0))
    
    # Settings button
    settings_frame = tk.Frame(preview_win)
    settings_frame.pack(pady=5)
    tk.Button(settings_frame, text="Customize Preview (Rows/Fields)", command=refresh_preview, 
             bg="#2196F3", fg="white", font=("Arial", 10, "bold")).pack()
    
    # Data preview frame
    data_frame = tk.Frame(preview_win)
    data_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
    
    # Create Treeview for data display
    tree = ttk.Treeview(data_frame, columns=list(df.columns), show='headings', height=20)
    
    # Configure column headings and widths
    for col in df.columns:
        tree.heading(col, text=col)
        tree.column(col, width=120, minwidth=80)
    
    # Add scrollbars
    v_scrollbar = ttk.Scrollbar(data_frame, orient=tk.VERTICAL, command=tree.yview)
    h_scrollbar = ttk.Scrollbar(data_frame, orient=tk.HORIZONTAL, command=tree.xview)
    tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
    
    # Pack scrollbars and treeview
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
    
    # Initial data load
    update_preview_display()
    
    # Button frame
    button_frame = tk.Frame(preview_win)
    button_frame.pack(pady=20)
    
    # Load button (green)
    load_btn = tk.Button(button_frame, text="Load Data to Salesforce", 
                        command=on_load, bg="#4CAF50", fg="white", 
                        font=("Arial", 12, "bold"), width=20, height=2)
    load_btn.pack(side=tk.LEFT, padx=20)
    
    # Cancel button (red)
    cancel_btn = tk.Button(button_frame, text="Cancel", 
                          command=on_cancel, bg="#f44336", fg="white", 
                          font=("Arial", 12, "bold"), width=20, height=2)
    cancel_btn.pack(side=tk.LEFT, padx=20)
    
    preview_win.wait_window()
    root.destroy()
    
    return user_choice['value']

# Show data preview and get user confirmation
print(f"Preparing data preview for {len(df_mapped)} records...")
user_decision = show_data_preview(df_mapped, selected_object)

if user_decision != 'load':
    print("=" * 60)
    print("✗ DATA LOADING CANCELLED BY USER")
    print("✗ User cancelled the data loading operation.")
    print("✗ No data was loaded to Salesforce.")
    print("=" * 60)
    exit()

print("✓ User confirmed data loading. Proceeding...")

# --- Batch Size and Parallel Processing Selection ---
batch_size = 10000  # Default batch size
parallel_batches = 1  # Default sequential processing

if len(df_mapped) > 5000:  # Show advanced settings for larger datasets
    batch_settings = select_batch_and_parallel_settings(len(df_mapped))
    
    # Check if user cancelled
    if batch_settings.get('cancelled', True):
        print("=" * 60)
        print("✗ BATCH PROCESSING CANCELLED BY USER")
        print("✗ User cancelled the batch processing configuration.")
        print("✗ Operation aborted.")
        print("=" * 60)
        exit()
    
    batch_size = batch_settings['batch_size']
    parallel_batches = batch_settings['parallel_batches']
    
    total_batches = (len(df_mapped) + batch_size - 1) // batch_size
    print(f"Processing {len(df_mapped):,} records in {total_batches} batches of {batch_size:,} records each")
    if parallel_batches > 1:
        print(f"Using parallel processing: {parallel_batches} batches simultaneously")
    else:
        print("Using sequential processing")
        
elif len(df_mapped) > 10000:  # Simple batch size dialog for medium datasets
    user_batch_size = simple_batch_size_dialog(len(df_mapped))
    if user_batch_size:
        batch_size = user_batch_size
        print(f"Processing {len(df_mapped):,} records in batches of {batch_size:,}")
    else:
        print("=" * 60)
        print("✗ BATCH SIZE SELECTION CANCELLED")
        print("✗ No batch size selected.")
        print("✗ Operation aborted.")
        print("=" * 60)
        exit()
else:
    print(f"Processing {len(df_mapped):,} records (single batch)")
    parallel_batches = 1

external_id_name = None
if operation == 'upsert':
    root = tkinter.Tk()
    root.withdraw()
    from tkinter import ttk
    selectable_columns = [col for col in df_mapped.columns if col.lower() != 'id']
    selected = {'value': None}
    def on_select_dropdown():
        selected['value'] = combo.get()
        win.destroy()
    win = tkinter.Toplevel()
    win.title("Select External ID Field")
    win.geometry("600x200")
    win.grab_set()
    label = tkinter.Label(win, text="Select the Salesforce External ID field for upsert (Id cannot be used):")
    label.pack(pady=10)
    combo = ttk.Combobox(win, values=selectable_columns, width=60)
    if selectable_columns:
        combo.set(selectable_columns[0])
    combo.pack(pady=10)
    btn = tkinter.Button(win, text="Select", command=on_select_dropdown)
    btn.pack(pady=20)
    win.wait_window()
    root.destroy()
    external_id_name = selected['value']
    if not external_id_name:
        raise ValueError("No External ID field name provided.")
    if external_id_name not in df_mapped.columns:
        raise ValueError(f"{external_id_name} column is missing in the mapped data.")

root_folder = r'DataLoader_Logs'
data_load_folder = os.path.join(root_folder, 'DataLoad')
org_folder = os.path.join(data_load_folder, f'DataLoad_{selected_org}')
object_folder = os.path.join(org_folder, selected_object)
batches_folder = os.path.join(object_folder, 'Batches')
os.makedirs(object_folder, exist_ok=True)
os.makedirs(batches_folder, exist_ok=True)

# Function to create detailed log file
def create_processing_log(start_time, end_time, total_records, success_count, error_count, 
                         batch_results, operation, selected_object, selected_org, object_folder):
    """Create a comprehensive CSV log file with processing details"""
    
    # Calculate processing metrics
    processing_duration = end_time - start_time
    unprocessed_count = total_records - success_count - error_count
    success_rate = (success_count / total_records * 100) if total_records > 0 else 0
    error_rate = (error_count / total_records * 100) if total_records > 0 else 0
    
    # Create summary log file
    summary_log_file = os.path.join(object_folder, "processing_summary.csv")
    
    with open(summary_log_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        
        # Write header
        writer.writerow([
            'Start_Time', 'End_Time', 'Processing_Duration_Seconds', 'Processing_Duration_Formatted',
            'Total_Records', 'Total_Success', 'Total_Errors', 'Total_Unprocessed',
            'Success_Rate_Percent', 'Error_Rate_Percent', 'Operation', 'Salesforce_Object', 
            'Salesforce_Org', 'Total_Batches', 'Parallel_Processing', 'Log_Generated_At'
        ])
        
        # Format times for readability
        start_time_str = datetime.datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S')
        end_time_str = datetime.datetime.fromtimestamp(end_time).strftime('%Y-%m-%d %H:%M:%S')
        duration_formatted = str(datetime.timedelta(seconds=int(processing_duration)))
        log_generated_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Determine if parallel processing was used
        parallel_used = any(batch.get('processing_time', 0) > 0 for batch in batch_results) and len(batch_results) > 1
        
        # Write summary data
        writer.writerow([
            start_time_str, end_time_str, f"{processing_duration:.2f}", duration_formatted,
            total_records, success_count, error_count, unprocessed_count,
            f"{success_rate:.2f}", f"{error_rate:.2f}", operation, selected_object,
            selected_org, len(batch_results), parallel_used, log_generated_at
        ])
    
    # Create detailed batch log file
    batch_log_file = os.path.join(object_folder, "batch_processing_details.csv")
    
    with open(batch_log_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        
        # Write header
        writer.writerow([
            'Batch_Number', 'Batch_Records', 'Batch_Success', 'Batch_Errors', 
            'Batch_Processing_Time_Seconds', 'Batch_Success_Rate_Percent', 
            'Batch_Error_Rate_Percent', 'Batch_Status', 'Error_Details'
        ])
        
        # Write batch details
        for batch in batch_results:
            batch_success_rate = (batch['success_count'] / batch['total_records'] * 100) if batch['total_records'] > 0 else 0
            batch_error_rate = (batch['error_count'] / batch['total_records'] * 100) if batch['total_records'] > 0 else 0
            batch_status = "SUCCESS" if batch['error_count'] == 0 else "PARTIAL" if batch['success_count'] > 0 else "FAILED"
            error_details = batch.get('error', '') if 'error' in batch else ''
            
            writer.writerow([
                batch['batch_num'], batch['total_records'], batch['success_count'], 
                batch['error_count'], f"{batch.get('processing_time', 0):.2f}",
                f"{batch_success_rate:.2f}", f"{batch_error_rate:.2f}", 
                batch_status, error_details
            ])
    
    return summary_log_file, batch_log_file

# Function to process data in batches with parallel processing support
def create_sf_connection(org_creds):
    """Create a new Salesforce connection for thread safety"""
    return sf.Salesforce(
        username=org_creds['username'],
        password=org_creds['password'],
        security_token=org_creds['security_token'],
        domain=org_creds['domain']
    )

def process_single_batch(batch_data, batch_num, operation, external_id_name, selected_object, org_creds, batches_folder):
    """Process a single batch - designed to be thread-safe"""
    try:
        # Create new SF connection for this thread
        thread_sf_conn = create_sf_connection(org_creds)
        
        batch_df, start_time = batch_data
        print(f"[Batch {batch_num}] Starting processing of {len(batch_df)} records...")
        
        # Convert batch to records
        batch_records = batch_df.to_dict('records')
        
        # Perform bulk operation for this batch
        if operation == 'upsert':
            results = getattr(thread_sf_conn.bulk, selected_object).upsert(batch_records, external_id_field=external_id_name)
        else:
            results = getattr(thread_sf_conn.bulk, selected_object).insert(batch_records)
        
        # Process results for this batch
        batch_success_rows = []
        batch_error_rows = []
        
        for i, res in enumerate(results):
            row = batch_df.iloc[i].copy()
            if res.get('success'):
                batch_success_rows.append(row)
            else:
                row['errors'] = str(res.get('errors'))
                batch_error_rows.append(row)
        
        # Save batch-specific files
        batch_file_prefix = f"{selected_object}_Batch{batch_num}"
        
        # Save batch source data
        batch_df.to_csv(os.path.join(batches_folder, f"{batch_file_prefix}_source.csv"), index=False)
        
        # Save batch results
        if batch_success_rows:
            pd.DataFrame(batch_success_rows).to_csv(os.path.join(batches_folder, f"{batch_file_prefix}_success.csv"), index=False)
        
        if batch_error_rows:
            pd.DataFrame(batch_error_rows).to_csv(os.path.join(batches_folder, f"{batch_file_prefix}_error.csv"), index=False)
        
        processing_time = time.time() - start_time
        print(f"[Batch {batch_num}] Completed in {processing_time:.2f}s: {len(batch_success_rows)} success, {len(batch_error_rows)} errors")
        
        return {
            'batch_num': batch_num,
            'total_records': len(batch_df),
            'success_count': len(batch_success_rows),
            'error_count': len(batch_error_rows),
            'success_rows': batch_success_rows,
            'error_rows': batch_error_rows,
            'processing_time': processing_time
        }
        
    except Exception as e:
        processing_time = time.time() - start_time if 'start_time' in locals() else 0
        print(f"[Batch {batch_num}] Failed in {processing_time:.2f}s: {e}")
        
        # Mark all records in this batch as errors
        error_rows = []
        for i in range(len(batch_df)):
            row = batch_df.iloc[i].copy()
            row['errors'] = f"Batch processing failed: {str(e)}"
            error_rows.append(row)
        
        return {
            'batch_num': batch_num,
            'total_records': len(batch_df),
            'success_count': 0,
            'error_count': len(batch_df),
            'success_rows': [],
            'error_rows': error_rows,
            'processing_time': processing_time,
            'error': str(e)
        }

def process_in_batches(df_data, batch_size, operation, parallel_batches=1, external_id_name=None):
    """Process DataFrame in batches with optional parallel processing support"""
    total_records = len(df_data)
    num_batches = (total_records + batch_size - 1) // batch_size  # Ceiling division
    
    all_success_rows = []
    all_error_rows = []
    batch_results = []
    
    print(f"Processing {total_records:,} records in {num_batches} batches...")
    if parallel_batches > 1:
        print(f"Using parallel processing with {parallel_batches} simultaneous batches")
    else:
        print("Using sequential processing")
    
    # Get org credentials for thread-safe connections
    org_creds = creds[selected_org]
    
    if parallel_batches == 1:
        # Sequential processing (traditional method)
        for batch_num in range(num_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, total_records)
            batch_df = df_data.iloc[start_idx:end_idx].copy()
            
            print(f"Processing Batch {batch_num + 1}/{num_batches} ({len(batch_df)} records)...")
            
            batch_data = (batch_df, time.time())
            result = process_single_batch(batch_data, batch_num + 1, operation, external_id_name, 
                                        selected_object, org_creds, batches_folder)
            
            # Collect results
            all_success_rows.extend(result['success_rows'])
            all_error_rows.extend(result['error_rows'])
            batch_results.append(result)
    else:
        # Parallel processing
        print(f"Preparing {num_batches} batches for parallel processing...")
        
        # Prepare batch data
        batch_data_list = []
        for batch_num in range(num_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, total_records)
            batch_df = df_data.iloc[start_idx:end_idx].copy()
            batch_data_list.append((batch_df, time.time()))
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel_batches) as executor:
            # Submit all batches
            future_to_batch = {}
            for i, batch_data in enumerate(batch_data_list):
                batch_num = i + 1
                future = executor.submit(process_single_batch, batch_data, batch_num, operation, 
                                       external_id_name, selected_object, org_creds, batches_folder)
                future_to_batch[future] = batch_num
            
            # Collect results as they complete
            completed_batches = 0
            for future in concurrent.futures.as_completed(future_to_batch):
                batch_num = future_to_batch[future]
                completed_batches += 1
                
                try:
                    result = future.result()
                    
                    # Collect results
                    all_success_rows.extend(result['success_rows'])
                    all_error_rows.extend(result['error_rows'])
                    batch_results.append(result)
                    
                    print(f"Completed {completed_batches}/{num_batches} batches - Batch {batch_num}: {result['success_count']} success, {result['error_count']} errors")
                    
                except Exception as e:
                    print(f"Batch {batch_num} execution failed: {str(e)}")
                    # Create error result for failed batch
                    batch_df = batch_data_list[batch_num - 1][0]
                    error_rows = []
                    for i in range(len(batch_df)):
                        row = batch_df.iloc[i].copy()
                        row['errors'] = f"Thread execution failed: {str(e)}"
                        error_rows.append(row)
                    
                    error_result = {
                        'batch_num': batch_num,
                        'total_records': len(batch_df),
                        'success_count': 0,
                        'error_count': len(batch_df),
                        'success_rows': [],
                        'error_rows': error_rows,
                        'processing_time': 0,
                        'error': str(e)
                    }
                    
                    all_error_rows.extend(error_result['error_rows'])
                    batch_results.append(error_result)
    
    # Sort batch results by batch number for consistent reporting
    batch_results.sort(key=lambda x: x['batch_num'])
    
    return all_success_rows, all_error_rows, batch_results

try:
    print(f"Starting {operation} operation for {len(df_mapped)} records...")
    
    # Record start time for logging
    operation_start_time = time.time()
    operation_start_timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"Operation started at: {operation_start_timestamp}")
    
    # Process data in batches with optional parallel processing
    success_rows, error_rows, batch_results = process_in_batches(
        df_mapped, batch_size, operation, parallel_batches, external_id_name
    )
    
    # Record end time for logging
    operation_end_time = time.time()
    operation_end_timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"Operation completed at: {operation_end_timestamp}")
    
    # Print batch summary
    print("\nBatch Processing Summary:")
    total_processing_time = sum(batch_info.get('processing_time', 0) for batch_info in batch_results)
    for batch_info in batch_results:
        processing_time = batch_info.get('processing_time', 0)
        print(f"Batch {batch_info['batch_num']}: {batch_info['success_count']} success, {batch_info['error_count']} errors "
              f"out of {batch_info['total_records']} records ({processing_time:.2f}s)")
    
    total_success = len(success_rows)
    total_errors = len(error_rows)
    total_unprocessed = len(df_mapped) - total_success - total_errors
    avg_batch_time = total_processing_time / len(batch_results) if batch_results else 0
    
    print(f"\nOverall Results: {total_success:,} success, {total_errors:,} errors, {total_unprocessed:,} unprocessed out of {len(df_mapped):,} total records")
    print(f"Average batch processing time: {avg_batch_time:.2f} seconds")
    print(f"Total operation time: {operation_end_time - operation_start_time:.2f} seconds")
    if parallel_batches > 1:
        print(f"Parallel processing used: {parallel_batches} simultaneous batches")
    # Save consolidated files
    df.to_csv(os.path.join(object_folder, "raw.csv"), index=False)
    df_mapped.to_csv(os.path.join(object_folder, "transformed_file.csv"), index=False)
    df_mapped.to_csv(os.path.join(object_folder, "source.csv"), index=False)
    
    if success_rows:
        pd.DataFrame(success_rows).to_csv(os.path.join(object_folder, "success.csv"), index=False)
    else:
        # Create empty success file
        pd.DataFrame(columns=df_mapped.columns).to_csv(os.path.join(object_folder, "success.csv"), index=False)
    
    if error_rows:
        pd.DataFrame(error_rows).to_csv(os.path.join(object_folder, "error.csv"), index=False)
    else:
        # Create empty error file
        error_columns = list(df_mapped.columns) + ['errors']
        pd.DataFrame(columns=error_columns).to_csv(os.path.join(object_folder, "error.csv"), index=False)
    
    print(f"Results saved to {object_folder}/")
    print(f"Batch details saved to {batches_folder}/")
    
    # Generate comprehensive log files
    print("Generating processing log files...")
    try:
        summary_log_file, batch_log_file = create_processing_log(
            operation_start_time, operation_end_time, len(df_mapped), 
            total_success, total_errors, batch_results, operation, 
            selected_object, selected_org, object_folder
        )
        print(f"Processing summary log saved to: {summary_log_file}")
        print(f"Batch details log saved to: {batch_log_file}")
    except Exception as log_error:
        print(f"Warning: Failed to generate log files: {log_error}")
    
    # Calculate final processing metrics for display
    processing_duration = operation_end_time - operation_start_time
    success_rate = (total_success / len(df_mapped) * 100) if len(df_mapped) > 0 else 0
    
    print(f"\n{'='*60}")
    print(f"PROCESSING COMPLETED SUCCESSFULLY")
    print(f"{'='*60}")
    print(f"Start Time: {operation_start_timestamp}")
    print(f"End Time: {operation_end_timestamp}")
    print(f"Duration: {processing_duration:.2f} seconds ({datetime.timedelta(seconds=int(processing_duration))})")
    print(f"Success Rate: {success_rate:.2f}%")
    print(f"Records Processed: {total_success + total_errors:,} / {len(df_mapped):,}")
    print(f"{'='*60}")
    
    if error_rows:
        tkinter.messagebox.showwarning(
            "Load Completed with Errors",
            f"{len(error_rows):,} out of {len(df_mapped):,} records failed to load.\n\n"
            f"Check {object_folder}/error.csv for details.\n"
            f"Batch details available in {batches_folder}/\n"
            f"Processing logs saved to {object_folder}/\n"
            f"Processing method: {'Parallel' if parallel_batches > 1 else 'Sequential'}"
        )
    else:
        parallel_info = f"({parallel_batches} parallel batches)" if parallel_batches > 1 else "(sequential)"
        tkinter.messagebox.showinfo(
            "Load Completed Successfully",
            f"All {len(df_mapped):,} records {operation}ed successfully into Salesforce {selected_object} object.\n\n"
            f"Processed in {len(batch_results)} batch(es) {parallel_info}.\n"
            f"Results and logs saved to {object_folder}/"
        )
except Exception as e:
    tkinter.messagebox.showerror(
        "Bulk Load Failed",
        f"Bulk {operation} failed: {e}"
    )
    raise