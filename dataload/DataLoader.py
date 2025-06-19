import pandas as pd
import json
import simple_salesforce as sf
import tkinter
import tkinter.filedialog
import os
import tkinter.simpledialog

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
    win.geometry("600x250")  # Increased window size
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

with open(r'C:\DM_toolkit\Services\linkedservices.json', 'r') as f:
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

# --- Step 2: Select Data File ---
tkinter.Tk().withdraw()  # Hide the root window
file = tkinter.filedialog.askopenfilename(
    title="Select CSV File",
    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
)
if not file:
    raise ValueError("No CSV file selected.")
df = pd.read_csv(file)

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
    win.geometry("400x200")  # Increased window size
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
filtered_objects = []
for name in object_names:
    if name.lower() == 'account' or 'wod' in name.lower():
        filtered_objects.append(name)
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
    win.geometry("800x600")  # Increased window size
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
df.columns = df.columns.str.strip()
df = df.where(pd.notnull(df), None)

external_id_name = None
if operation == 'upsert':
    external_id_name = input("Enter the Salesforce External ID field name to use for upsert (e.g. External_Id__c): ").strip()
    if not external_id_name:
        raise ValueError("No External ID field name provided.")
    if external_id_name not in df.columns:
        raise ValueError(f"{external_id_name} column is missing in the input data.")

root_folder = r'DatFiles'
data_load_folder = os.path.join(root_folder, 'DataLoad')
org_folder = os.path.join(data_load_folder, f'DataLoad_{selected_org}')
object_folder = os.path.join(org_folder, selected_object)
os.makedirs(object_folder, exist_ok=True)

try:
    if operation == 'upsert':
        results = getattr(sf_conn.bulk, selected_object).upsert(df.to_dict('records'), external_id_field=external_id_name)
    else:
        results = getattr(sf_conn.bulk, selected_object).insert(df.to_dict('records'))
    print("Bulk operation results:", len(results))
    success_rows = []
    error_rows = []
    for i, res in enumerate(results):
        row = df.iloc[i].copy()
        if res.get('success'):
            success_rows.append(row)
        else:
            row['errors'] = str(res.get('errors'))
            error_rows.append(row)
    df.to_csv(os.path.join(object_folder, "source.csv"), index=False)
    pd.DataFrame(success_rows).to_csv(os.path.join(object_folder, "success.csv"), index=False)
    pd.DataFrame(error_rows).to_csv(os.path.join(object_folder, "error.csv"), index=False)
    print(f"Results saved to {object_folder}/source.csv, success.csv, and error.csv")
    print(f"Data {operation}ed successfully into Salesforce {selected_object} object.")
except Exception as e:
    print(f"Bulk {operation} failed:", e)