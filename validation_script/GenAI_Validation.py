import sys
sys.path.append(r"C:\DM_toolkit")  # Add project root to sys.path
import pandas as pd
import os
import dataset.Connections as Connections
import dataset.Org_selection as Org_selection
import tkinter as tk
from tkinter import filedialog
import json
import tkinter.ttk as ttk  # Add this import at the top


def select_file():
    # Use filedialog with the VS Code file picker if available, else fallback to Tkinter
    print("Please select the validation formula CSV file:")
    try:
        # VS Code's file picker integration (works if running in VS Code with Python extension)
        import sys
        if "vscode" in sys.modules:
            import builtins
            if hasattr(builtins, "vscode"):
                # VS Code interactive window file picker
                from builtins import vscode
                file_path = vscode.open_file_dialog(title="Select Validation formula file", filters=[("CSV files", "*.csv"), ("All files", "*.*")])
                print("Selected file:", file_path)
                return file_path
    except Exception:
        pass

    # Fallback to Tkinter dialog (will open a native OS window)
    root = tk.Tk()
    root.withdraw()  # Hide the root window
    file_path = filedialog.askopenfilename(
        title="Select Validation formula file",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
    )
    print("Selected file:", file_path)
    return file_path

def select_org_dropdown(orgs):
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

def select_object_dropdown(sf):
    # Get object names (custom + 'Account')
    objects = [
        obj['name'] for obj in sf.describe()['sobjects']
        if obj['name'].endswith('__c') or obj['name'].lower() == 'account'
    ]
    selected_object = {'value': None}
    def on_select(event=None):
        selected_object['value'] = combo.get()
        root.destroy()  # Fix: use root instead of win
    def on_type(event):
        typed = combo.get().strip().lower()
        if not typed:
            combo['values'] = objects
        else:
            filtered = [obj for obj in objects if typed in obj.lower()]
            combo['values'] = filtered
        if combo['values']:
            combo.event_generate('<Down>')
    root = tk.Tk()
    root.title("Select Salesforce Object")
    root.geometry("400x120")
    label = tk.Label(root, text="Choose a Salesforce object:")
    label.pack(pady=10)
    combo = ttk.Combobox(root, values=objects, width=50)
    combo.pack(pady=5)
    combo.bind("<<ComboboxSelected>>", on_select)
    combo.bind("<KeyRelease>", on_type)
    combo.focus_set()
    root.mainloop()
    return selected_object['value']

with open(r'C:\DM_toolkit\Services\linkedservices.json', 'r') as f:
    creds = json.load(f)
orgs = list(creds.keys())
selected_org = select_org_dropdown(orgs)
if not selected_org or selected_org not in creds:
    raise ValueError(f"Org '{selected_org}' not found in credentials file.")

# Connect to Salesforce for object dropdown
# Fix: Use correct argument name for org selection
sf_conn = Connections.get_salesforce_connection(file_path=r"C:\DM_toolkit\Services\linkedservices.json", org_name=selected_org)
object_name = select_object_dropdown(sf_conn)
if not object_name:
    raise ValueError("No Salesforce object selected.")
res = selected_org + "_" + object_name

def safe_func_name(name):
    return "".join(c if c.isalnum() or c == '_' else '_' for c in name.strip())

def build_function_code(name, formula, field, obj):
    func_name = f"validate_{safe_func_name(name)}"
    return f'''
def {func_name}(df):
    """
    Validation Rule: {name}
    Salesforce Object: {obj}
    Field: {field}
    Apex Formula:
    {formula}
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results
    """
    # TODO: Implement Python equivalent of Apex formula
    # Example placeholder - replace with actual formula logic
    return df['{field}'].notna()  # Placeholder logic
'''

root_dir = "DataFiles"
roots = os.path.join(root_dir, selected_org, object_name)  # Now includes object_name

def generate_validation_bundle(validation_csv, output_dir=None):
    # Place validation_bundle inside selected org/object
    if output_dir is None:
        output_dir = os.path.join(roots, "validation_bundle")
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(roots, "ValidatedData"), exist_ok=True)
    df = pd.read_csv(validation_csv)
    
    bundle_content = "# Auto-generated validation bundle\nimport pandas as pd\n\n"
    validation_functions = []

    for _, row in df.iterrows():
        if str(row.get("Active", "")).lower() not in ["true", "1"]:
            continue

        name = row.get("ValidationName", "UnnamedRule")
        formula = row.get("ErrorConditionFormula", "")
        field = row.get("FieldName", "")
        obj = row.get("ObjectName", "")
        
        func_code = build_function_code(name, formula, field, obj)
        bundle_content += func_code
        validation_functions.append(f"validate_{safe_func_name(name)}")

    # Write bundle file
    bundle_path = os.path.join(output_dir, "bundle.py")
    with open(bundle_path, "w", encoding="utf-8") as f:
        f.write(bundle_content)

    # Create validator script
    validator_content = f'''import pandas as pd
from bundle import *
import tkinter as tk
from tkinter import filedialog
import os

def select_file():
    root = tk.Tk()
    root.withdraw()  # Hide the root window

    file_path = filedialog.askopenfilename(
        title="Select data file",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
    )

    print("Selected file:", file_path)
    return file_path


def validate_all(data_csv):
    """
    Validates all records in data_csv using all validation functions
    Returns a DataFrame with validation results
    """
    df = pd.read_csv(data_csv)
    gf=pd.read_csv(data_csv)
    df = df.fillna('')  # Fill NaN values with empty strings
    results = pd.DataFrame(index=df.index)
    
    # Apply each validation function
{chr(10).join(f"    results['{func}'] = {func}(df)" for func in validation_functions)}
    
    # Add summary column
    results['is_valid'] = results.all(axis=1)
    df['is_valid'] = results['is_valid']
    # Add 'issue' column: validation name if failed, else empty string
    failed_cols = [col for col in results.columns if col != 'is_valid']
    df['issue'] = results[failed_cols].apply(lambda row: ', '.join([col for col in failed_cols if not row[col]]), axis=1)

    # Save to validatedData folder one level above validation_bundle
    root_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'validatedData'))
    os.makedirs(root_folder, exist_ok=True)
    df.to_csv(os.path.join(root_folder, 'validatedData.csv'), index=False)
    suc_df = df[df['is_valid']]
    fail_df = df[~df['is_valid']]
    suc_df.to_csv(os.path.join(root_folder, 'success.csv'), index=False)
    fail_df.to_csv(os.path.join(root_folder, 'failure.csv'), index=False)
    gf.to_csv(os.path.join(root_folder, 'SchemaValidatedData.csv'), index=False)  # Save results back to CSV
    return results


if __name__ == "__main__":
    data_csv = select_file()
    results = validate_all(data_csv)
    print("Validation Results:")
    print(results)
    print(f"\\nTotal records: {{len(results)}}")
    print(f"Valid records: {{results['is_valid'].sum()}}")
    print(f"Invalid records: {{len(results) - results['is_valid'].sum()}}")
'''

    validator_path = os.path.join(output_dir, "validator.py")
    with open(validator_path, "w", encoding="utf-8") as f:
        f.write(validator_content)

    print(f"\n✅ Created validation bundle in '{output_dir}' folder")
    print(f"📄 bundle.py: Contains all validation functions")
    print(f"📄 validator.py: Applies all validations to data.csv")
    print(f"📊 {len(validation_functions)} validation functions generated")
    print("\nTo use:")
    print(f"1. Implement actual validation logic in {bundle_path}")
    print(f"2. Run validator.py to validate data.csv")

if __name__ == "__main__":
    print("Welcome to the Validation Bundle Generator!\n please select the file from outside of VS Code")
    print(f"Selected Org: {selected_org}")
    validation_csv = select_file()
    generate_validation_bundle(validation_csv)