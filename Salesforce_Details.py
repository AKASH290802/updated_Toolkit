import dataset.Connections as Connections
import dataset.Org_selection as Org_selection
import pandas as pd
import requests
import os
import tkinter as tk
from tkinter import ttk

selected_org = Org_selection.org_select()
SalesForce = Connections.get_salesforce_connection(file_path=r"C:\DM_toolkit\Services\linkedservices.json", org_name=selected_org)
session_id = SalesForce.session_id
instance_url = SalesForce.sf_instance

# GUI based input of select object
#  list of all the objects
objects = [
    obj['name'] for obj in SalesForce.describe()['sobjects']
    if obj['name'].endswith('__c') or obj['name'].lower() == 'account'
]

object_name=None
print("Select Object from Pop-up Window.")
# GUI function
def on_select(event):
    global object_name
    object_name = combo.get()
    print(f"Selected Salesforce object: {object_name}")
    root.destroy()  # Close window after selection (optional)

def on_type(event):
    """Filter Combobox items based on user input without interrupting typing."""
    # Ignore non-character keys (e.g., arrow keys, Enter)
    if event.keysym in ('Up', 'Down', 'Left', 'Right', 'Return', 'Tab'):
        return
    typed = combo.get().strip().lower()
    if not typed:  # If input is empty, show all objects
        combo['values'] = objects
    else:  # Filter objects containing the typed string
        filtered = [obj for obj in objects if typed in obj.lower()]
        combo['values'] = filtered
    # Keep dropdown open only if there are filtered results
    if combo['values']:
        combo.event_generate('<Down>')
# Create GUI window
root = tk.Tk()
root.title("Select Salesforce Object")
root.geometry("400x120")

label = ttk.Label(root, text="Choose a Salesforce object:")
label.pack(pady=10)
# Combobox is now editable (no state="readonly")
combo = ttk.Combobox(root, values=objects, width=50)
combo.pack(pady=5)
combo.bind("<<ComboboxSelected>>", on_select)
combo.bind("<KeyRelease>", on_type)  # Filter on typing
combo.focus_set()  # Set focus for immediate typing

root.mainloop()

# After GUI closes
print(f"Final selected object: {object_name}")


# === Describe Fields ===
fields_info = []
schema = getattr(SalesForce, object_name).describe()
for field in schema['fields']:
    picklist_values = [p['value'] for p in field.get('picklistValues', []) if not p.get('inactive', False)]
    fields_info.append({
        'Field Name': field['name'],
        'Label': field['label'],
        'Type': field['type'],
        'Required': not field['nillable'],
        'Unique': field.get('unique', False),
        'Picklist Values': ", ".join(picklist_values)
    })

fields_df = pd.DataFrame(fields_info)

# === Fetch Validation Rules using Tooling API ===
headers = {
    'Authorization': f'Bearer {session_id}',
    'Content-Type': 'application/json'
}

val_url = f"https://{instance_url}/services/data/v59.0/tooling/query"
val_query = f"SELECT Id, ValidationName, ErrorDisplayField, ErrorMessage, Active, Description, EntityDefinition.QualifiedApiName FROM ValidationRule WHERE EntityDefinition.QualifiedApiName = '{object_name}'"
val_resp = requests.get(val_url, headers=headers, params={'q': val_query})
val_rules = val_resp.json().get('records', [])

validation_data = [{
    'Rule Name': v['ValidationName'],
    'Error Field': v['ErrorDisplayField'],
    'Error Message': v['ErrorMessage'],
    'Active': v['Active'],
    'Description': v.get('Description', '')
} for v in val_rules]

validation_df = pd.DataFrame(validation_data)

# === Fetch Triggers (names only) ===
trigger_query = f"SELECT Name, TableEnumOrId, Status FROM ApexTrigger WHERE TableEnumOrId = '{object_name}'"
trigger_resp = requests.get(val_url, headers=headers, params={'q': trigger_query})
triggers = trigger_resp.json().get('records', [])

trigger_data = [{
    'Trigger Name': t['Name'],
    'Status': t['Status']
} for t in triggers]

trigger_df = pd.DataFrame(trigger_data)

# === Write to Excel ===
root_folder = "DataFiles"
object_folder = os.path.join(root_folder,selected_org, object_name)

excel_file_name = selected_org+"_"+object_name+"_details.xlsx"
excel_file_path = os.path.join(object_folder, excel_file_name)

os.makedirs(object_folder, exist_ok=True)

with pd.ExcelWriter(excel_file_path, engine='openpyxl') as writer:
    fields_df.to_excel(writer, sheet_name=object_name, index=False)
    if not validation_df.empty:
        validation_df.to_excel(writer, sheet_name="Validation", index=False)
    if not trigger_df.empty:
        trigger_df.to_excel(writer, sheet_name="Triggers", index=False)
fields_df.to_csv(os.path.join(object_folder, "details.csv"), index=False)
validation_df.to_csv(os.path.join(object_folder, "validation.csv"), index=False)
print(f"\nExcel file created: {excel_file_path}")
