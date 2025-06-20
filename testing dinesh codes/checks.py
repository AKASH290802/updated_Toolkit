import pandas as pd
import tkinter as tk
from tkinter import ttk

df=pd.read_excel(r"C:\Users\dinesh.verma\Downloads\DamageCodeDAtaLoad.xls", engine='xlrd')  # Use xlrd for .xls files
columns = list(df.columns)

# Create main Tkinter window
root = tk.Tk()
root.title("Column Selector")
root.geometry("300x100")

# Variable to store selected column
select_col = tk.StringVar(root)
select_col.set(columns[0] if columns else "No columns")  # Default value

# Function to print selected column
def print_selected_column(*args):
    print(f"Selected column: {select_col.get()}")

# Create menu bar
menubar = tk.Menu(root)
root.config(menu=menubar)

# Create Columns menu
columns_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Columns", menu=columns_menu)

# Add column names to menu
for col in columns:
    columns_menu.add_radiobutton(
        label=col,
        value=col,
        variable=select_col,
        command=print_selected_column
    )

# Trace changes to select_col
select_col.trace_add("write", print_selected_column)

# Start the main loop
root.mainloop()