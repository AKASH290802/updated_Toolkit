import tkinter as tk
from tkinter import ttk
import Connections as Connections  # Your module to get Salesforce connection

# Connect to Salesforce
sf = Connections.get_salesforce_connection()

# Get object names (custom + 'Account')
objects = [
    obj['name'] for obj in sf.describe()['sobjects']
    if obj['name'].endswith('__c') or obj['name'].lower() == 'account'
]

selected_object = None  # This will store the selected object

# GUI function
def on_select(event):
    global selected_object
    selected_object = combo.get()
    print(f"Selected Salesforce object: {selected_object}")
    root.destroy()  # Close window after selection (optional)

# Create GUI window
root = tk.Tk()
root.title("Select Salesforce Object")
root.geometry("400x120")

label = ttk.Label(root, text="Choose a Salesforce object:")
label.pack(pady=10)

combo = ttk.Combobox(root, values=objects, state="readonly", width=50)
combo.pack(pady=5)
combo.bind("<<ComboboxSelected>>", on_select)

root.mainloop()

# After GUI closes
print(f"Final selected object: {selected_object}")
