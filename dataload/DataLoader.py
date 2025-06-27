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
    file = tkinter.filedialog.askopenfilename(
        title="Select CSV or Excel File",
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


def ask_for_mapping():
    import tkinter as tk
    selected = {'value': None}
    def on_yes():
        selected['value'] = 'yes'
        win.destroy()
    def on_no():
        selected['value'] = 'no'
        win.destroy()
    root = tk.Tk()
    root.withdraw()
    win = tk.Toplevel()
    win.title("Mapping File")
    win.geometry("400x150")
    win.grab_set()
    tk.Label(win, text="Do you have a mapping file?").pack(pady=20)
    button_frame = tk.Frame(win)
    button_frame.pack(pady=20)
    tk.Button(button_frame, text="Yes", command=on_yes, width=10).pack(side=tk.LEFT, padx=10)
    tk.Button(button_frame, text="No", command=on_no, width=10).pack(side=tk.LEFT, padx=10)
    win.wait_window()
    root.destroy()
    return selected['value']

mapping_files = ask_for_mapping()
if mapping_files=='yes':
# --- Step 3: Select Mapping File ---
    # Set default directory to mapping_logs folder
    default_mapping_dir = os.path.join(project_root, 'mapping_logs')
    
    mapping_file = tkinter.filedialog.askopenfilename(
        title="Select Mapping JSON File",
        initialdir=default_mapping_dir,
        filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
    )
    if not mapping_file:
        raise ValueError("No mapping file selected.")

    try:
        with open(mapping_file, 'r') as f:
            mapping = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        raise ValueError(f"Error reading mapping file: {e}")
    
    # --- Step 4: Apply Mapping ---
    # Filter mapping to only include columns that exist in the input DataFrame
    filtered_mapping = {k: v for k, v in mapping.items() if k in df.columns}
else:
    print('run mapping.py to create mapping file')
    # If no mapping file, use all columns as-is
    mapping = {}
    filtered_mapping = {col: col for col in df.columns}
if not filtered_mapping:
    raise ValueError("None of the columns in the mapping file match the columns in the data file.")

# Rename DataFrame columns based on the filtered mapping
try:
    df_mapped = df.rename(columns=filtered_mapping)
    # Keep only the columns that were mapped
    df_mapped = df_mapped[list(filtered_mapping.values())]
except Exception as e:
    raise ValueError(f"Error applying mapping: {e}")

# Log ignored mappings
ignored_mappings = [k for k in mapping.keys() if k not in df.columns]
if ignored_mappings:
    tkinter.messagebox.showwarning(
        "Ignored Mappings",
        f"The following columns in the mapping file were ignored as they are not in the data file: {', '.join(ignored_mappings)}"
    )

# --- Step 5: Select Operation (insert/upsert) ---
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

# --- Step 6: Select Salesforce Object ---
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

# --- Step 7: Validate Lookup Fields ---
# Get the object's field metadata
object_metadata = getattr(sf_conn, selected_object).describe()
lookup_fields = {}
for field in object_metadata['fields']:
    if field['type'] in ['reference'] and field['name'] in df_mapped.columns:
        lookup_fields[field['name']] = field['referenceTo'][0] if field['referenceTo'] else None

# --- Step 8: Prompt for Lookup Field Matching ---
lookup_match_fields = {}
for lookup_field, related_object in lookup_fields.items():
    if related_object:
        # Get the related object's metadata to list available fields
        try:
            related_metadata = getattr(sf_conn, related_object).describe()
            field_names = [f['name'] for f in related_metadata['fields']]
        except Exception as e:
            tkinter.messagebox.showerror(
                "Metadata Error",
                f"Failed to retrieve metadata for {related_object}: {e}"
            )
            raise
        root = tkinter.Tk()
        root.withdraw()
        # Use a dropdown for match_field selection for each lookup field
        match_field = {'value': None}
        def on_select_dropdown():
            match_field['value'] = combo.get()
            win.destroy()
        win = tkinter.Toplevel()
        win.title(f"Select Match Field for {lookup_field}")
        win.geometry("600x200")
        win.grab_set()
        label = tkinter.Label(win, text=f"Select the field on {related_object} to match values for {lookup_field}:")
        label.pack(pady=10)
        from tkinter import ttk
        combo = ttk.Combobox(win, values=field_names, width=60)
        combo.set('Name' if 'Name' in field_names else field_names[0])
        combo.pack(pady=10)
        btn = tkinter.Button(win, text="Select", command=on_select_dropdown)
        btn.pack(pady=20)
        win.wait_window()
        root.destroy()
        selected_match_field = match_field['value']
        if not selected_match_field:
            raise ValueError(f"No matching field provided for {lookup_field}")
        if selected_match_field not in field_names:
            raise ValueError(f"Invalid field '{selected_match_field}' for {related_object}. Choose from: {', '.join(field_names)}")
        lookup_match_fields[lookup_field] = selected_match_field

# --- Step 9: Automatically Resolve Lookup Values ---
# This loop will handle all lookup fields, one by one, using the mapping selected above.
for lookup_field, related_object in lookup_fields.items():
    if lookup_field in df_mapped.columns and related_object:
        match_field = lookup_match_fields.get(lookup_field, 'Name')
        unique_values = df_mapped[lookup_field].dropna().unique()
        for value in unique_values:
            # Check if the value is already a valid Salesforce ID (15 or 18 characters)
            if isinstance(value, str) and len(value) in [15, 18] and value.isalnum():
                continue
            # Query Salesforce for the ID using the specified field
            try:
                # Escape single quotes in the value to prevent SOQL injection
                escaped_value = str(value).replace("'", "\\'")
                result = sf_conn.query(f"SELECT Id FROM {related_object} WHERE {match_field} = '{escaped_value}'")
                if result['records']:
                    salesforce_id = result['records'][0]['Id']
                    df_mapped.loc[df_mapped[lookup_field] == value, lookup_field] = salesforce_id
                else:
                    tkinter.messagebox.showerror(
                        "Lookup Field Error",
                        f"No record found in {related_object} with {match_field} = '{value}' for lookup field '{lookup_field}'."
                    )
                    raise ValueError(f"No record found in {related_object} for {match_field} = '{value}'")
            except Exception as e:
                tkinter.messagebox.showerror(
                    "Lookup Field Error",
                    f"Failed to map '{value}' for lookup field '{lookup_field}' in {related_object}: {e}"
                )
                raise

# --- Step 10: Prepare Data and Perform Load ---
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