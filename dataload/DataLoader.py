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

# --- Batch Size Selection ---
batch_size = 10000  # Default batch size
if len(df_mapped) > 10000:
    def select_batch_size():
        import tkinter as tk
        selected = {'value': None}
        def on_select():
            try:
                size = int(entry.get())
                if size > 0:
                    selected['value'] = size
                    win.destroy()
                else:
                    tkinter.messagebox.showerror("Invalid Input", "Batch size must be greater than 0")
            except ValueError:
                tkinter.messagebox.showerror("Invalid Input", "Please enter a valid number")
        
        root = tk.Tk()
        root.withdraw()
        win = tk.Toplevel()
        win.title("Select Batch Size")
        win.geometry("400x200")
        win.grab_set()
        tk.Label(win, text=f"You have {len(df_mapped)} records.").pack(pady=10)
        tk.Label(win, text="Enter batch size for processing:").pack(pady=5)
        entry = tk.Entry(win, width=20)
        entry.insert(0, "10000")  # Default value
        entry.pack(pady=10)
        entry.focus_set()
        btn = tk.Button(win, text="OK", command=on_select)
        btn.pack(pady=20)
        win.wait_window()
        root.destroy()
        return selected['value']
    
    user_batch_size = select_batch_size()
    if user_batch_size:
        batch_size = user_batch_size
    else:
        raise ValueError("No batch size selected.")
    
    print(f"Processing {len(df_mapped)} records in batches of {batch_size}")
else:
    print(f"Processing {len(df_mapped)} records (single batch)")

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

# Function to process data in batches
def process_in_batches(df_data, batch_size, operation, external_id_name=None):
    """Process DataFrame in batches and return combined results"""
    total_records = len(df_data)
    num_batches = (total_records + batch_size - 1) // batch_size  # Ceiling division
    
    all_success_rows = []
    all_error_rows = []
    batch_results = []
    
    print(f"Processing {total_records} records in {num_batches} batches...")
    
    for batch_num in range(num_batches):
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, total_records)
        batch_df = df_data.iloc[start_idx:end_idx].copy()
        
        print(f"Processing Batch {batch_num + 1}/{num_batches} ({len(batch_df)} records)...")
        
        # Convert batch to records
        batch_records = batch_df.to_dict('records')
        
        try:
            # Perform bulk operation for this batch
            if operation == 'upsert':
                results = getattr(sf_conn.bulk, selected_object).upsert(batch_records, external_id_field=external_id_name)
            else:
                results = getattr(sf_conn.bulk, selected_object).insert(batch_records)
            
            # Process results for this batch
            batch_success_rows = []
            batch_error_rows = []
            
            for i, res in enumerate(results):
                row = batch_df.iloc[i].copy()
                if res.get('success'):
                    batch_success_rows.append(row)
                    all_success_rows.append(row)
                else:
                    row['errors'] = str(res.get('errors'))
                    batch_error_rows.append(row)
                    all_error_rows.append(row)
            
            # Save batch-specific files
            batch_file_prefix = f"{selected_object}_Batch{batch_num + 1}"
            
            # Save batch source data
            batch_df.to_csv(os.path.join(batches_folder, f"{batch_file_prefix}_source.csv"), index=False)
            
            # Save batch results
            if batch_success_rows:
                pd.DataFrame(batch_success_rows).to_csv(os.path.join(batches_folder, f"{batch_file_prefix}_success.csv"), index=False)
            
            if batch_error_rows:
                pd.DataFrame(batch_error_rows).to_csv(os.path.join(batches_folder, f"{batch_file_prefix}_error.csv"), index=False)
            
            batch_results.append({
                'batch_num': batch_num + 1,
                'total_records': len(batch_df),
                'success_count': len(batch_success_rows),
                'error_count': len(batch_error_rows)
            })
            
            print(f"Batch {batch_num + 1} completed: {len(batch_success_rows)} success, {len(batch_error_rows)} errors")
            
        except Exception as e:
            print(f"Batch {batch_num + 1} failed: {e}")
            # Mark all records in this batch as errors
            for i in range(len(batch_df)):
                row = batch_df.iloc[i].copy()
                row['errors'] = f"Batch processing failed: {str(e)}"
                all_error_rows.append(row)
            
            batch_results.append({
                'batch_num': batch_num + 1,
                'total_records': len(batch_df),
                'success_count': 0,
                'error_count': len(batch_df)
            })
    
    return all_success_rows, all_error_rows, batch_results

try:
    print(f"Starting {operation} operation for {len(df_mapped)} records...")
    
    # Process data in batches
    success_rows, error_rows, batch_results = process_in_batches(df_mapped, batch_size, operation, external_id_name)
    
    # Print batch summary
    print("\nBatch Processing Summary:")
    for batch_info in batch_results:
        print(f"Batch {batch_info['batch_num']}: {batch_info['success_count']} success, {batch_info['error_count']} errors out of {batch_info['total_records']} records")
    
    total_success = len(success_rows)
    total_errors = len(error_rows)
    print(f"\nOverall Results: {total_success} success, {total_errors} errors out of {len(df_mapped)} total records")
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
    
    if error_rows:
        tkinter.messagebox.showwarning(
            "Load Completed with Errors",
            f"{len(error_rows)} out of {len(df_mapped)} records failed to load.\n\n"
            f"Check {object_folder}/error.csv for details.\n"
            f"Batch details available in {batches_folder}/"
        )
    else:
        tkinter.messagebox.showinfo(
            "Load Completed Successfully",
            f"All {len(df_mapped)} records {operation}ed successfully into Salesforce {selected_object} object.\n\n"
            f"Processed in {len(batch_results)} batch(es).\n"
            f"Results saved to {object_folder}/"
        )
except Exception as e:
    tkinter.messagebox.showerror(
        "Bulk Load Failed",
        f"Bulk {operation} failed: {e}"
    )
    raise