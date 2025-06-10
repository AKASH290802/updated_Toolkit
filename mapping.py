import json
import pandas as pd
import os
import tkinter as tk
from tkinter import ttk
import dataset.Connections as Connections
import dataset.Org_selection as Org_selection

# Establish Salesforce connection
selected_org = Org_selection.org_select()
SalesForce = Connections.get_salesforce_connection(file_path=r"C:\DM_toolkit\Services\linkedservices.json", org_name=selected_org)

# GUI-based input for selecting object
objects = [
    obj['name'] for obj in SalesForce.describe()['sobjects']
    if obj['name'].endswith('__c') or obj['name'].lower() == 'account'
]

object_name = None
print("Select Object from Pop-up Window.")

# GUI function
def on_select(event):
    global object_name
    object_name = combo.get()
    print(f"Selected Salesforce object: {object_name}")
    root.destroy()  # Close window after selection

def on_type(event):
    """Filter Combobox items based on user input without interrupting typing."""
    if event.keysym in ('Up', 'Down', 'Left', 'Right', 'Return', 'Tab'):
        return
    typed = combo.get().strip().lower()
    if not typed:  # If input is empty, show all objects
        combo['values'] = objects
    else:  # Filter objects containing the typed string
        filtered = [obj for obj in objects if typed in obj.lower()]
        combo['values'] = filtered
    if combo['values']:
        combo.event_generate('<Down>')

# Create GUI window
root = tk.Tk()
root.title("Select Salesforce Object")
root.geometry("400x120")
label = ttk.Label(root, text="Choose a Salesforce object:")
label.pack(pady=10)
combo = ttk.Combobox(root, values=objects, width=50)
combo.pack(pady=5)
combo.bind("<<ComboboxSelected>>", on_select)
combo.bind("<KeyRelease>", on_type)
combo.focus_set()
root.mainloop()

# After GUI closes
print(f"Final selected object: {object_name}")

# Function to get field API names for a Salesforce object
def get_salesforce_fields(object_name):
    try:
        # Retrieve object metadata
        schema = getattr(SalesForce, object_name).describe()
        fields = schema['fields']
        # Filter updateable fields, excluding 'id', 'isdeleted', 'sic', 'createdby'
        excluded_keywords = ['id', 'isdeleted', 'sic', 'createdby']
        return [
            field['name'] for field in fields
            if field['updateable'] and not any(keyword.lower() in field['name'].lower() for keyword in excluded_keywords)
        ]
    except Exception as e:
        print(f"Error retrieving fields for {object_name}: {e}")
        return []

# Function to generate DataFrame and JSON mapping
def generate_mapping(object_name):
    try:
        # Get Salesforce field API names
        fields = get_salesforce_fields(object_name)
        if not fields:
            print(f"No updateable fields found for {object_name} after filtering")
            return None, {}

        # Create DataFrame with field API names
        df = pd.DataFrame(fields, columns=['Field_API_Name'])
        print(f"DataFrame for {object_name}:\n{df}")

        # Create mapping where each field maps to itself
        mapping = {field: field for field in fields}

        # Save mapping to JSON file in the object folder
        root_folder = "DataFiles"
        object_folder = os.path.join(root_folder, selected_org, object_name)
        os.makedirs(object_folder, exist_ok=True)
        output_file = os.path.join(object_folder, "mapping.json")
        with open(output_file, 'w') as f:
            json.dump(mapping, f, indent=4)

        print(f"Mapping file created: {output_file}")
        return df, mapping
    except Exception as e:
        print(f"Error generating mapping for {object_name}: {e}")
        return None, {}

# Generate mapping for the selected object
df, mapping = generate_mapping(object_name)