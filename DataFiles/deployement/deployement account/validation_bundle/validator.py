import pandas as pd
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
    results['validate_Updating_Account_Type_Not_Allowed'] = validate_Updating_Account_Type_Not_Allowed(df)
    
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
    print(f"\nTotal records: {len(results)}")
    print(f"Valid records: {results['is_valid'].sum()}")
    print(f"Invalid records: {len(results) - results['is_valid'].sum()}")
