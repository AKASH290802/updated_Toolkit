import pandas as pd
import json
import re
import dataset.Connections as Connections
from dataset.Connections import Org_selection as Org_selection
import tkinter as tk
from tkinter import ttk, messagebox
import os

# Salesforce connection
selected_org = Org_selection.org_select()
SalesForce = Connections.get_salesforce_connection(file_path=r"C:\DM_toolkit\Services\linkedservices.json", org_name=selected_org)
sf = SalesForce

def get_object_list(sf):
    """Fetch a list of object API names from Salesforce."""
    try:
        query = "SELECT DeveloperName FROM EntityDefinition WHERE IsCustomizable = true"
        result = sf.toolingexecute('query?q=' + query.replace('\n', ' ').replace('  ', ' '))
        objects = [record['DeveloperName'] for record in result['records']]
        return sorted(objects)
    except Exception as e:
        print(f"Error fetching object list: {e}")
        fallback = ['Account', 'Lead', 'Opportunity', 'wod_2__claim__c', 'wod_2__financial__c']
        print(f"Using fallback object list: {fallback}")
        return fallback

def select_object_popup(sf):
    """Create a Tkinter popup to select a Salesforce object API name."""
    objects = get_object_list(sf)
    root = tk.Tk()
    root.title("Select Salesforce Object")
    root.geometry("400x120")

    label = ttk.Label(root, text="Choose a Salesforce object:")
    label.pack(pady=10)

    selected_object = tk.StringVar()
    combo = ttk.Combobox(root, textvariable=selected_object, values=objects, width=50)
    combo.pack(pady=5)
    
    def on_type(event):
        """Filter Combobox items based on user input."""
        if event.keysym in ('Up', 'Down', 'Left', 'Right', 'Return', 'Tab'):
            return
        typed = combo.get().strip().lower()
        if not typed:
            combo['values'] = objects
        else:
            filtered = [obj for obj in objects if typed in obj.lower()]
            combo['values'] = filtered
        if combo['values']:
            combo.event_generate('<Down>')

    def on_submit():
        if selected_object.get():
            root.destroy()
        else:
            messagebox.showerror("Error", "Please select an object.")

    combo.bind("<KeyRelease>", on_type)
    combo.bind("<<ComboboxSelected>>", lambda event: on_submit())
    combo.focus_set()

    submit_button = ttk.Button(root, text="Submit", command=on_submit)
    submit_button.pack(pady=5)

    root.mainloop()
    return selected_object.get() if selected_object.get() else None

def parse_field_names(formula):
    """Parse field names from the error condition formula."""
    if not formula or formula == 'N/A':
        return 'N/A'
    field_pattern = r'\b[A-Za-z0-9_]+(__c)?\b'
    fields = re.findall(field_pattern, formula)
    salesforce_keywords = {'AND', 'OR', 'NOT', 'IF', 'ISBLANK', 'LEN', 'ISPICKVAL', 'TRUE', 'FALSE', 'NULL'}
    fields = [f for f in fields if f not in salesforce_keywords and not f.isdigit()]
    return ', '.join(fields) if fields else 'N/A'

def get_validation_rules(sf, object_name):
    """Query Salesforce validation rules for a specific object using the Tooling API."""
    try:
        query = f"""
            SELECT Id, ValidationName, EntityDefinition.DeveloperName, Active
            FROM ValidationRule
            WHERE EntityDefinition.DeveloperName = '{object_name}'
        """
        result = sf.toolingexecute('query?q=' + query.replace('\n', ' ').replace('  ', ' '))
        records = result['records']
        if not records:
            print(f"No validation rules found for object {object_name}.")
            return []

        validation_rules = []
        for record in records:
            try:
                metadata_query = f"SELECT Metadata FROM ValidationRule WHERE Id = '{record['Id']}'"
                metadata_result = sf.toolingexecute('query?q=' + metadata_query.replace('\n', ' ').replace('  ', ' '))
                if not metadata_result or 'records' not in metadata_result or not metadata_result['records']:
                    print(f"No metadata returned for Validation Rule {record['ValidationName']} (Id: {record['Id']})")
                    continue
                metadata = metadata_result['records'][0].get('Metadata', {})
                formula = metadata.get('errorConditionFormula', 'N/A')
                rule_info = {
                    'ValidationName': record['ValidationName'],
                    'ObjectName': record['EntityDefinition']['DeveloperName'],
                    'ErrorConditionFormula': formula,
                    'FieldName': parse_field_names(formula),
                    'Active': record['Active'],
                    'ErrorMessage': metadata.get('errorMessage', 'N/A')
                }
                validation_rules.append(rule_info)
            except Exception as e:
                print(f"Error fetching metadata for Validation Rule {record['ValidationName']} (Id: {record['Id']}): {str(e)}")
                continue
        return validation_rules
    except Exception as e:
        print(f"Failed to query validation rules for object {object_name}: {e}")
        return []

def main():
    """Main function to extract and save validation rules for a selected object."""
    try:
        # Prompt for object name via Tkinter popup
        object_name = select_object_popup(sf)
        if not object_name:
            print("No object selected. Exiting.")
            return

        print(f"Selected Salesforce object: {object_name}")

        # Get validation rules for the specified object
        records = get_validation_rules(sf, object_name)
        
        # Create DataFrame
        if not records:
            print(f"No validation rules found for object {object_name} or an error occurred.")
            df = pd.DataFrame(columns=['ValidationName', 'ErrorConditionFormula', 'FieldName', 'ObjectName', 'Active'])
        else:
            df = pd.DataFrame(records)
            # Print results for verification
            for rule in records:
                print(f"\nValidation Rule: {rule['ValidationName']}")
                print(f"Object: {rule['ObjectName']}")
                print(f"Error Condition Formula: {rule['ErrorConditionFormula']}")
                print(f"Field Name: {rule['FieldName']}")
                print(f"Active: {rule['Active']}")
                print(f"Error Message: {rule['ErrorMessage']}")
                print("-" * 50)

        # Save to CSV
        root_folder = "DataFiles"
        object_folder = os.path.join(root_folder, selected_org, object_name)
        os.makedirs(object_folder, exist_ok=True)
        csv_df = df[['ValidationName', 'ErrorConditionFormula', 'FieldName', 'ObjectName', 'Active']]
        csv_file_path = os.path.join(object_folder, "Formula_validation.csv")
        csv_df.to_csv(csv_file_path, index=False)
        print(f"Validation rules saved to {csv_file_path}")

    except Exception as e:
        print(f"Error in main execution: {e}")

if __name__ == "__main__":
    main()