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

# --- Ask for mapping file ---
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
    print('Using all columns as-is (no mapping file provided)')
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

# --- Step 5: Select Salesforce Object ---
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
    tk.Label(win, text="Type to filter, then select Salesforce object for transformation:").pack(pady=10)
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

# --- Step 6: Validate Lookup Fields ---
# Get the object's field metadata
object_metadata = getattr(sf_conn, selected_object).describe()
lookup_fields = {}
for field in object_metadata['fields']:
    if field['type'] in ['reference'] and field['name'] in df_mapped.columns:
        lookup_fields[field['name']] = field['referenceTo'][0] if field['referenceTo'] else None

# --- Step 7: Prompt for Lookup Field Matching ---
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

# --- Step 8: Automatically Resolve Lookup Values ---
def show_lookup_preview(df, lookup_field, resolved_count, total_lookups, current_lookup_num):
    """Show data preview after each lookup resolution"""
    import tkinter as tk
    from tkinter import ttk
    
    user_choice = {'value': None}
    
    def on_next():
        user_choice['value'] = 'next'
        preview_win.destroy()
    
    def on_cancel():
        user_choice['value'] = 'cancel'
        preview_win.destroy()
    
    root = tk.Tk()
    root.withdraw()
    
    preview_win = tk.Toplevel()
    preview_win.title(f"Lookup Resolution Preview - {lookup_field}")
    preview_win.geometry("1000x700")
    preview_win.grab_set()
    
    # Header info
    header_frame = tk.Frame(preview_win)
    header_frame.pack(pady=10, padx=20, fill=tk.X)
    
    tk.Label(header_frame, text=f"Lookup Resolution Progress: {current_lookup_num}/{total_lookups}", 
             font=("Arial", 14, "bold")).pack()
    tk.Label(header_frame, text=f"Field: {lookup_field} | Resolved: {resolved_count} values", 
             font=("Arial", 12)).pack()
    tk.Label(header_frame, text="Preview of data after lookup resolution:", 
             font=("Arial", 10)).pack(pady=(5,0))
    
    # Data preview frame
    data_frame = tk.Frame(preview_win)
    data_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
    
    # Create Treeview for data display
    columns = list(df.columns)
    tree = ttk.Treeview(data_frame, columns=columns, show='headings', height=20)
    
    # Configure column headings and widths
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=120, minwidth=80)
        # Highlight the lookup field
        if col == lookup_field:
            tree.heading(col, text=f"🔍 {col}")
    
    # Add scrollbars
    v_scrollbar = ttk.Scrollbar(data_frame, orient=tk.VERTICAL, command=tree.yview)
    h_scrollbar = ttk.Scrollbar(data_frame, orient=tk.HORIZONTAL, command=tree.xview)
    tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
    
    # Pack scrollbars and treeview
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
    
    # Add data to treeview (first 100 rows)
    preview_df = df.head(100)
    for idx, row in preview_df.iterrows():
        values = [str(val) if val is not None else '' for val in row.values]
        tree.insert('', tk.END, values=values)
    
    # Button frame
    button_frame = tk.Frame(preview_win)
    button_frame.pack(pady=20)
    
    # Next button (green) or Finish if last lookup
    button_text = "Finish Lookups" if current_lookup_num == total_lookups else "Next Lookup"
    next_btn = tk.Button(button_frame, text=button_text, 
                        command=on_next, bg="#4CAF50", fg="white", 
                        font=("Arial", 12, "bold"), width=20, height=2)
    next_btn.pack(side=tk.LEFT, padx=20)
    
    # Cancel button (red)
    cancel_btn = tk.Button(button_frame, text="Cancel", 
                          command=on_cancel, bg="#f44336", fg="white", 
                          font=("Arial", 12, "bold"), width=20, height=2)
    cancel_btn.pack(side=tk.LEFT, padx=20)
    
    # Additional info
    info_frame = tk.Frame(preview_win)
    info_frame.pack(pady=(0,10))
    tk.Label(info_frame, text=f"Showing first 100 rows | Lookup field '{lookup_field}' is highlighted", 
             font=("Arial", 9), fg="gray").pack()
    
    preview_win.wait_window()
    root.destroy()
    
    return user_choice['value']

# --- Step 8: Automatically Resolve Lookup Values ---
def show_lookup_preview(df, lookup_field, resolved_count, total_lookups, current_lookup_num, related_object, field_names):
    """Show data preview after each lookup resolution with option to reselect lookup field"""
    import tkinter as tk
    from tkinter import ttk
    
    user_choice = {'value': None}
    
    def on_next():
        user_choice['value'] = 'next'
        preview_win.destroy()
    
    def on_cancel():
        user_choice['value'] = 'cancel'
        preview_win.destroy()
    
    def on_select_lookup_field():
        user_choice['value'] = 'reselect'
        preview_win.destroy()
    
    root = tk.Tk()
    root.withdraw()
    
    preview_win = tk.Toplevel()
    preview_win.title(f"Lookup Resolution Preview - {lookup_field}")
    preview_win.geometry("1200x800")
    preview_win.grab_set()
    
    # Header info
    header_frame = tk.Frame(preview_win)
    header_frame.pack(pady=10, padx=20, fill=tk.X)
    
    tk.Label(header_frame, text=f"Lookup Resolution Progress: {current_lookup_num}/{total_lookups}", 
             font=("Arial", 14, "bold")).pack()
    tk.Label(header_frame, text=f"Field: {lookup_field} | Related Object: {related_object}", 
             font=("Arial", 12)).pack()
    tk.Label(header_frame, text=f"Resolved: {resolved_count} values", 
             font=("Arial", 12), fg="green").pack()
    tk.Label(header_frame, text="Preview of data after lookup resolution:", 
             font=("Arial", 10)).pack(pady=(5,0))
    
    # Data preview frame
    data_frame = tk.Frame(preview_win)
    data_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
    
    # Create Treeview for data display
    columns = list(df.columns)
    tree = ttk.Treeview(data_frame, columns=columns, show='headings', height=20)
    
    # Configure column headings and widths
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=120, minwidth=80)
        # Highlight the lookup field
        if col == lookup_field:
            tree.heading(col, text=f"🔍 {col}")
    
    # Add scrollbars
    v_scrollbar = ttk.Scrollbar(data_frame, orient=tk.VERTICAL, command=tree.yview)
    h_scrollbar = ttk.Scrollbar(data_frame, orient=tk.HORIZONTAL, command=tree.xview)
    tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
    
    # Pack scrollbars and treeview
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
    
    # Add data to treeview (first 100 rows)
    preview_df = df.head(100)
    for idx, row in preview_df.iterrows():
        values = [str(val) if val is not None else '' for val in row.values]
        tree.insert('', tk.END, values=values)
    
    # Button frame
    button_frame = tk.Frame(preview_win)
    button_frame.pack(pady=20)
    
    # Next button (green) - Changes to "Save Transformed Data" for last lookup
    button_text = "Save Transformed Data" if current_lookup_num == total_lookups else "Next Lookup"
    next_btn = tk.Button(button_frame, text=button_text, 
                        command=on_next, bg="#4CAF50", fg="white", 
                        font=("Arial", 11, "bold"), width=20, height=2)
    next_btn.pack(side=tk.LEFT, padx=10)
    
    # Reselect Lookup Field button (orange)
    select_field_btn = tk.Button(button_frame, text="Reselect Lookup Field", 
                                command=on_select_lookup_field, bg="#FF9800", fg="white", 
                                font=("Arial", 11, "bold"), width=20, height=2)
    select_field_btn.pack(side=tk.LEFT, padx=10)
    
    # Cancel button (red)
    cancel_btn = tk.Button(button_frame, text="Cancel", 
                          command=on_cancel, bg="#f44336", fg="white", 
                          font=("Arial", 11, "bold"), width=20, height=2)
    cancel_btn.pack(side=tk.LEFT, padx=10)
    
    # Additional info
    info_frame = tk.Frame(preview_win)
    info_frame.pack(pady=(0,10))
    tk.Label(info_frame, text=f"Showing first 100 rows | Lookup field '{lookup_field}' is highlighted", 
             font=("Arial", 9), fg="gray").pack()
    if current_lookup_num == total_lookups:
        tk.Label(info_frame, text="Click 'Save Transformed Data' when satisfied, or 'Reselect Lookup Field' to change match field", 
                 font=("Arial", 9), fg="blue").pack()
    else:
        tk.Label(info_frame, text="Click 'Next Lookup' when satisfied, or 'Reselect Lookup Field' to change match field", 
                 font=("Arial", 9), fg="blue").pack()
    
    preview_win.wait_window()
    root.destroy()
    
    return user_choice['value']

def select_lookup_match_field(lookup_field, related_object, field_names, current_selection):
    """Allow user to select/change the lookup match field"""
    import tkinter as tk
    from tkinter import ttk
    
    selected_field = {'value': None, 'action': 'cancel'}
    
    def on_select():
        selected_field['value'] = combo.get()
        selected_field['action'] = 'select'
        field_win.destroy()
    
    def on_cancel():
        selected_field['value'] = current_selection
        selected_field['action'] = 'cancel'
        field_win.destroy()
    
    root = tk.Tk()
    root.withdraw()
    
    field_win = tk.Toplevel()
    field_win.title(f"Select Match Field for {lookup_field}")
    field_win.geometry("700x300")
    field_win.grab_set()
    
    # Header
    header_frame = tk.Frame(field_win)
    header_frame.pack(pady=20, padx=20, fill=tk.X)
    
    tk.Label(header_frame, text=f"Select Match Field for Lookup: {lookup_field}", 
             font=("Arial", 14, "bold")).pack()
    tk.Label(header_frame, text=f"Related Object: {related_object}", 
             font=("Arial", 12)).pack(pady=5)
    tk.Label(header_frame, text="Choose which field in the related object to match against:", 
             font=("Arial", 10)).pack()
    
    # Field selection
    selection_frame = tk.Frame(field_win)
    selection_frame.pack(pady=20, padx=20, fill=tk.X)
    
    tk.Label(selection_frame, text="Available fields:", font=("Arial", 10, "bold")).pack(anchor=tk.W)
    
    combo = ttk.Combobox(selection_frame, values=field_names, width=60, font=("Arial", 11))
    combo.set(current_selection)
    combo.pack(pady=10, anchor=tk.W)
    
    # Current selection info
    info_frame = tk.Frame(field_win)
    info_frame.pack(pady=10, padx=20, fill=tk.X)
    tk.Label(info_frame, text=f"Current selection: {current_selection}", 
             font=("Arial", 10), fg="blue").pack(anchor=tk.W)
    
    # Instructions
    instruction_frame = tk.Frame(field_win)
    instruction_frame.pack(pady=5, padx=20, fill=tk.X)
    tk.Label(instruction_frame, text="Select a field from the dropdown and click 'Select' to use it for matching", 
             font=("Arial", 9), fg="gray").pack(anchor=tk.W)
    tk.Label(instruction_frame, text="Click 'Cancel' to keep the current field unchanged", 
             font=("Arial", 9), fg="gray").pack(anchor=tk.W)
    
    # Buttons
    button_frame = tk.Frame(field_win)
    button_frame.pack(pady=20)
    
    tk.Button(button_frame, text="Select", command=on_select, 
             bg="#4CAF50", fg="white", font=("Arial", 11, "bold"), width=15).pack(side=tk.LEFT, padx=10)
    tk.Button(button_frame, text="Cancel", command=on_cancel, 
             bg="#f44336", fg="white", font=("Arial", 11, "bold"), width=15).pack(side=tk.LEFT, padx=10)
    
    field_win.wait_window()
    root.destroy()
    
    return selected_field['value'], selected_field['action']

print("Processing lookup fields...")
lookup_count_summary = {}
current_lookup_num = 0
total_lookups = len(lookup_fields)

for lookup_field, related_object in lookup_fields.items():
    if lookup_field in df_mapped.columns and related_object:
        current_lookup_num += 1
        print(f"Resolving lookup field {current_lookup_num}/{total_lookups}: {lookup_field} -> {related_object}")
        
        # Get field metadata for reselection option
        try:
            related_metadata = getattr(sf_conn, related_object).describe()
            field_names = [f['name'] for f in related_metadata['fields']]
        except Exception as e:
            print(f"Error getting metadata for {related_object}: {e}")
            field_names = ['Name']  # Fallback
        
        # Initial match field selection
        match_field = lookup_match_fields.get(lookup_field, 'Name')
        
        # Store original values for reprocessing
        original_values = df_mapped[lookup_field].copy()
        
        # Process lookup resolution in a continuous loop
        while True:
            # Reset to original values before each processing attempt
            df_mapped[lookup_field] = original_values.copy()
            
            unique_values = df_mapped[lookup_field].dropna().unique()
            lookup_count = 0
            
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
                        lookup_count += 1
                    else:
                        print(f"Warning: No record found in {related_object} with {match_field} = '{value}'")
                        # Continue processing instead of raising error
                except Exception as e:
                    print(f"Error processing lookup value '{value}': {e}")
                    # Continue processing instead of raising error
            
            print(f"Resolved {lookup_count} lookup values for {lookup_field} using {match_field}")
            lookup_count_summary[lookup_field] = lookup_count
            
            # Show preview with options
            if total_lookups > 0:
                user_decision = show_lookup_preview(df_mapped, lookup_field, lookup_count, total_lookups, 
                                                  current_lookup_num, related_object, field_names)
                
                if user_decision == 'cancel':
                    print("=" * 60)
                    print("✗ LOOKUP PROCESSING CANCELLED BY USER")
                    print("✗ User cancelled the lookup resolution process.")
                    print("✗ Operation aborted.")
                    print("=" * 60)
                    exit()
                elif user_decision == 'reselect':
                    # Allow user to reselect the lookup field
                    new_match_field, action = select_lookup_match_field(lookup_field, related_object, field_names, match_field)
                    if action == 'select' and new_match_field and new_match_field != match_field:
                        print(f"User changed match field from '{match_field}' to '{new_match_field}' for {lookup_field}")
                        match_field = new_match_field
                        lookup_match_fields[lookup_field] = match_field
                        # Continue loop to reprocess with new match field
                        continue
                    elif action == 'select' and new_match_field == match_field:
                        print(f"User confirmed current match field '{match_field}' for {lookup_field}")
                        # Continue loop to show preview again
                        continue
                    else:
                        print(f"User cancelled field selection, keeping match field '{match_field}' for {lookup_field}")
                        # Continue loop to show preview again
                        continue
                elif user_decision == 'next':
                    # If this is the last lookup and user clicked "Save Transformed Data", proceed to save
                    if current_lookup_num == total_lookups:
                        print(f"✓ User confirmed final lookup resolution. Proceeding to save transformed data...")
                        break  # Exit the reselection loop and proceed to save
                    else:
                        print(f"✓ User confirmed lookup resolution for {lookup_field}. Continuing to next lookup...")
                        break  # Continue to next lookup field
            else:
                break  # No preview needed if no lookups

if lookup_fields:
    print(f"\nLookup Resolution Summary:")
    for field, count in lookup_count_summary.items():
        print(f"- {field}: {count} values resolved")

# --- Step 9: Clean Data for Salesforce ---
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

print("Cleaning data for Salesforce compatibility...")
df_mapped.columns = df_mapped.columns.str.strip()
df_transformed = clean_dataframe_for_salesforce(df_mapped)

# --- Step 10: Validate JSON Compliance ---
def validate_json_compliance(df):
    """Validate that DataFrame can be converted to JSON"""
    try:
        test_records = df.head(1).to_dict('records')
        json.dumps(test_records, allow_nan=False)
        return True
    except (ValueError, TypeError) as e:
        print(f"Data validation failed: {e}")
        return False

if not validate_json_compliance(df_transformed):
    print("Warning: Data contains values that may not be JSON compliant.")

# --- Final Data Preview Before Saving ---
def show_final_preview(df, selected_object):
    """Show final data preview before saving transformed data"""
    import tkinter as tk
    from tkinter import ttk
    
    user_choice = {'value': None}
    
    def on_save():
        user_choice['value'] = 'save'
        preview_win.destroy()
    
    def on_cancel():
        user_choice['value'] = 'cancel'
        preview_win.destroy()
    
    root = tk.Tk()
    root.withdraw()
    
    preview_win = tk.Toplevel()
    preview_win.title("Final Data Preview - Confirm Save")
    preview_win.geometry("1200x800")
    preview_win.grab_set()
    
    # Header info
    header_frame = tk.Frame(preview_win)
    header_frame.pack(pady=10, padx=20, fill=tk.X)
    
    tk.Label(header_frame, text=f"Final Transformed Data Preview", 
             font=("Arial", 16, "bold")).pack()
    tk.Label(header_frame, text=f"Target Object: {selected_object} | Total Records: {len(df)} | Columns: {len(df.columns)}", 
             font=("Arial", 12)).pack()
    tk.Label(header_frame, text="Review the final transformed data below and confirm to save:", 
             font=("Arial", 10)).pack(pady=(5,0))
    
    # Summary frame
    summary_frame = tk.Frame(preview_win)
    summary_frame.pack(pady=5, padx=20, fill=tk.X)
    
    summary_text = "✓ Data cleaned and JSON validated"
    if lookup_fields:
        summary_text += f" | ✓ {len(lookup_fields)} lookup field(s) resolved"
    
    tk.Label(summary_frame, text=summary_text, font=("Arial", 10), fg="green").pack()
    
    # Data preview frame
    data_frame = tk.Frame(preview_win)
    data_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
    
    # Create Treeview for data display
    columns = list(df.columns)
    tree = ttk.Treeview(data_frame, columns=columns, show='headings', height=20)
    
    # Configure column headings and widths
    for col in columns:
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
    
    # Add data to treeview (first 100 rows)
    preview_df = df.head(100)
    for idx, row in preview_df.iterrows():
        values = [str(val) if val is not None else '' for val in row.values]
        tree.insert('', tk.END, values=values)
    
    # Button frame
    button_frame = tk.Frame(preview_win)
    button_frame.pack(pady=20)
    
    # Save button (green)
    save_btn = tk.Button(button_frame, text="Save Transformed Data", 
                        command=on_save, bg="#4CAF50", fg="white", 
                        font=("Arial", 12, "bold"), width=20, height=2)
    save_btn.pack(side=tk.LEFT, padx=20)
    
    # Cancel button (red)
    cancel_btn = tk.Button(button_frame, text="Cancel", 
                          command=on_cancel, bg="#f44336", fg="white", 
                          font=("Arial", 12, "bold"), width=20, height=2)
    cancel_btn.pack(side=tk.LEFT, padx=20)
    
    # Additional info
    info_frame = tk.Frame(preview_win)
    info_frame.pack(pady=(0,10))
    tk.Label(info_frame, text="Showing first 100 rows | All transformations and lookups completed", 
             font=("Arial", 9), fg="gray").pack()
    
    preview_win.wait_window()
    root.destroy()
    
    return user_choice['value']

print("Preparing final data preview...")
user_decision = show_final_preview(df_transformed, selected_object)

if user_decision != 'save':
    print("=" * 60)
    print("✗ OPERATION ABORTED BY USER")
    print("✗ User denied saving the transformed data.")
    print("✗ No files were saved. Operation cancelled.")
    print("=" * 60)
    exit()

print("✓ User confirmed saving transformed data. Proceeding...")

# --- Step 11: Save Transformed Data ---
# Create folder structure: DataLoad_Logs/dataload/dataload_{selectedorg}/{objectname}/
root_folder = 'DataLoader_Logs'
dataload_folder = os.path.join(root_folder, 'dataload')
org_folder = os.path.join(dataload_folder, f'dataload_{selected_org}')
object_folder = os.path.join(org_folder, selected_object)
os.makedirs(object_folder, exist_ok=True)

# Save transformed data
transformed_file_path = os.path.join(object_folder, 'transformed.csv')
df_transformed.to_csv(transformed_file_path, index=False)

print(f"\nTransformation completed successfully!")
print(f"Transformed data saved to: {transformed_file_path}")
print(f"Total records: {len(df_transformed)}")
print(f"Total columns: {len(df_transformed.columns)}")

if lookup_fields:
    print(f"Processed {len(lookup_fields)} lookup field(s): {list(lookup_fields.keys())}")
    total_resolved = sum(lookup_count_summary.values()) if 'lookup_count_summary' in locals() else 0
    print(f"Total lookup values resolved: {total_resolved}")

# Show completion dialog
lookup_summary = ""
if lookup_fields:
    total_resolved = sum(lookup_count_summary.values()) if 'lookup_count_summary' in locals() else 0
    lookup_summary = f"Lookup fields resolved: {len(lookup_fields)}\nTotal values resolved: {total_resolved}\n\n"

tkinter.messagebox.showinfo(
    "Transformation Completed Successfully",
    f"Data transformation completed successfully!\n\n"
    f"Records processed: {len(df_transformed)}\n"
    f"Columns: {len(df_transformed.columns)}\n"
    f"{lookup_summary}"
    f"Transformed file saved to:\n{transformed_file_path}"
)

print(f"\nFile locations:")
print(f"- Transformed data: {transformed_file_path}")
print(f"- Folder structure: {object_folder}")
