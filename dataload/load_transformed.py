"""
Simplified Data loader for Pre-Transformed CSV Files
====================================================

This script loads already transformed CSV files directly to Salesforce.
It assumes the data has already been processed by the transformation script.

Steps:
1. Select Salesforce org
2. Select pre-transformed CSV file
3. Auto-detect Salesforce object from file path (with manual fallback)
4. Select operation (insert/upsert)
5. Select batch size (if > 10,000 records)
6. Select external ID (if upsert operation)
7. Load data to Salesforce with batch processing

No mapping or transformation is performed - data is loaded as-is.
"""

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

print("=== Simplified Data Loader for Pre-Transformed Files ===")
print("This script loads already transformed CSV files directly to Salesforce.")
print("No mapping or transformation will be performed.\n")

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

print(f"✓ Connected to Salesforce org: {selected_org}")

sf_conn = sf.Salesforce(
    username=creds[selected_org]['username'],
    password=creds[selected_org]['password'],
    security_token=creds[selected_org]['security_token'],
    domain=creds[selected_org]['domain']
)

# --- Step 2: Select Transformed Data File ---
tkinter.Tk().withdraw()
# Set default directory to DataLoader_Logs/dataload
default_data_dir = os.path.join(project_root, 'DataLoader_Logs', 'dataload')

file = tkinter.filedialog.askopenfilename(
    title="Select Pre-Transformed Data File",
    initialdir=default_data_dir,
    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
)

if not file:
    raise ValueError("No data file selected.")

try:
    df_transformed = pd.read_csv(file)
    
    # Validate that we have data
    if df_transformed.empty:
        raise ValueError("The selected file is empty.")
    
    print(f"✓ Loaded {len(df_transformed)} rows and {len(df_transformed.columns)} columns from transformed file.")
    print(f"✓ File: {os.path.basename(file)}")
except Exception as e:
    raise ValueError(f"Error reading data file: {e}")

# --- Step 3: Auto-detect Salesforce Object from file path ---
def detect_object_from_path(file_path):
    """Auto-detect Salesforce object from file path"""
    # Extract the folder structure to find object name
    path_parts = file_path.replace('\\', '/').split('/')
    
    # Look for object name in path (usually second to last folder)
    for i, part in enumerate(path_parts):
        if part == 'dataload' and i + 2 < len(path_parts):
            # Pattern: .../dataload/{org}/{object}/...
            potential_object = path_parts[i + 2]
            return potential_object
        elif 'DataLoad_' in part and i + 1 < len(path_parts):
            # Pattern: .../DataLoad_{org}/{object}/...
            potential_object = path_parts[i + 1]
            return potential_object
    
    # Fallback: try to extract from filename
    filename = os.path.basename(file_path)
    if 'transformed' in filename:
        # Remove 'transformed' and common extensions to get object name
        object_name = filename.replace('transformed', '').replace('.csv', '').strip('_')
        if object_name:
            return object_name
    
    return None

detected_object = detect_object_from_path(file)
if detected_object:
    print(f"✓ Auto-detected Salesforce object: {detected_object}")
else:
    print("⚠ Could not auto-detect object from file path")

# Validate that the detected object exists in Salesforce
object_list = list(sf_conn.describe()['sobjects'])
object_names = [obj['name'] for obj in object_list]

if detected_object and detected_object in object_names:
    selected_object = detected_object
    print(f"✓ Confirmed Salesforce object: {selected_object}")
else:
    # If auto-detection fails, show a simple dropdown with common objects
    print("Auto-detection failed, please select the object manually...")
    filtered_objects = [name for name in object_names if name.lower() == 'account' or 'wod' in name.lower()]
    filtered_objects.sort()
    
    if not filtered_objects:
        raise ValueError("No eligible Salesforce objects found (Account or objects containing 'wod').")
    
    def select_salesforce_object(object_list):
        import tkinter as tk
        selected = {'value': None}
        def on_select():
            selected['value'] = var.get()
            win.destroy()
        root = tk.Tk()
        root.withdraw()
        win = tk.Toplevel()
        win.title("Select Salesforce Object")
        win.geometry("600x250")
        win.grab_set()
        tk.Label(win, text="Auto-detection failed. Please select Salesforce object:").pack(pady=20)
        var = tk.StringVar(win)
        var.set(object_list[0])
        dropdown = tk.OptionMenu(win, var, *object_list)
        dropdown.config(width=60)
        dropdown.pack(padx=20, pady=20)
        btn = tk.Button(win, text="Select", command=on_select)
        btn.pack(pady=20)
        win.wait_window()
        root.destroy()
        return selected['value']
    
    selected_object = select_salesforce_object(filtered_objects)
    if not selected_object:
        raise ValueError("No Salesforce object selected.")
    print(f"✓ Selected Salesforce object: {selected_object}")

print(f"✓ Target Salesforce object: {selected_object}")

# --- Step 4: Select Operation (insert/upsert) ---
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
print(f"✓ Selected operation: {operation}")

# --- Step 5: Batch Size Selection ---
batch_size = 10000  # Default batch size
if len(df_transformed) > 10000:
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
        tk.Label(win, text=f"You have {len(df_transformed)} records.").pack(pady=10)
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
    
    print(f"✓ Processing {len(df_transformed)} records in batches of {batch_size}")
else:
    print(f"✓ Processing {len(df_transformed)} records (single batch)")

# --- Step 6: External ID for Upsert (if needed) ---
external_id_name = None
if operation == 'upsert':
    root = tkinter.Tk()
    root.withdraw()
    from tkinter import ttk
    selectable_columns = [col for col in df_transformed.columns if col.lower() != 'id']
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
    if external_id_name not in df_transformed.columns:
        raise ValueError(f"{external_id_name} column is missing in the transformed data.")
    print(f"✓ External ID field: {external_id_name}")

# --- Step 7: Create Output Folders ---
root_folder = r'DataLoader_Logs'
data_load_folder = os.path.join(root_folder, 'DataLoad')
org_folder = os.path.join(data_load_folder, f'DataLoad_{selected_org}')
object_folder = os.path.join(org_folder, selected_object)
batches_folder = os.path.join(object_folder, 'Batches')
os.makedirs(object_folder, exist_ok=True)
os.makedirs(batches_folder, exist_ok=True)

# --- Step 8: Batch Processing Function ---
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

# --- Step 9: Execute Batch Processing ---
# Quick validation for JSON compliance
try:
    test_records = df_transformed.head(1).to_dict('records')
    json.dumps(test_records, allow_nan=False)
except (ValueError, TypeError) as e:
    raise ValueError(f"Data contains values that are not JSON compliant: {e}")

try:
    print(f"Starting {operation} operation for {len(df_transformed)} records...")
    
    # Process data in batches
    success_rows, error_rows, batch_results = process_in_batches(df_transformed, batch_size, operation, external_id_name)
    
    # Print batch summary
    print("\nBatch Processing Summary:")
    for batch_info in batch_results:
        print(f"Batch {batch_info['batch_num']}: {batch_info['success_count']} success, {batch_info['error_count']} errors out of {batch_info['total_records']} records")
    
    total_success = len(success_rows)
    total_errors = len(error_rows)
    print(f"\nOverall Results: {total_success} success, {total_errors} errors out of {len(df_transformed)} total records")
    
    # Save consolidated files
    df_transformed.to_csv(os.path.join(object_folder, "source.csv"), index=False)
    
    if success_rows:
        pd.DataFrame(success_rows).to_csv(os.path.join(object_folder, "success.csv"), index=False)
    else:
        # Create empty success file
        pd.DataFrame(columns=df_transformed.columns).to_csv(os.path.join(object_folder, "success.csv"), index=False)
    
    if error_rows:
        pd.DataFrame(error_rows).to_csv(os.path.join(object_folder, "error.csv"), index=False)
    else:
        # Create empty error file
        error_columns = list(df_transformed.columns) + ['errors']
        pd.DataFrame(columns=error_columns).to_csv(os.path.join(object_folder, "error.csv"), index=False)
    
    print(f"Results saved to {object_folder}/")
    print(f"Batch details saved to {batches_folder}/")
    
    if error_rows:
        tkinter.messagebox.showwarning(
            "Load Completed with Errors",
            f"{len(error_rows)} out of {len(df_transformed)} records failed to load.\n\n"
            f"Check {object_folder}/error.csv for details.\n"
            f"Batch details available in {batches_folder}/"
        )
    else:
        tkinter.messagebox.showinfo(
            "Load Completed Successfully",
            f"All {len(df_transformed)} records {operation}ed successfully into Salesforce {selected_object} object.\n\n"
            f"Processed in {len(batch_results)} batch(es).\n"
            f"Results saved to {object_folder}/"
        )
    
    print("=" * 60)
    print("✓ LOAD COMPLETED SUCCESSFULLY")
    print(f"✓ Org: {selected_org}")
    print(f"✓ Object: {selected_object}")
    print(f"✓ Operation: {operation}")
    print(f"✓ Records: {len(df_transformed)} total, {len(success_rows)} success, {len(error_rows)} errors")
    print(f"✓ Results saved to: {object_folder}/")
    print("=" * 60)
    
except Exception as e:
    print("=" * 60)
    print("✗ LOAD FAILED")
    print(f"✗ Error: {e}")
    print("=" * 60)
    tkinter.messagebox.showerror(
        "Bulk Load Failed",
        f"Bulk {operation} failed: {e}"
    )
    raise
