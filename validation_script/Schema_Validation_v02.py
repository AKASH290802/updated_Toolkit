import pandas as pd
import re
import os
import sys
from uuid import uuid4
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import dataset.Org_selection as Org_selection

# Configure paths
rootfolder = "DataFiles"
object_name = input("Enter object name:   ")
selected_org = Org_selection.org_select()
object_folder = os.path.join(rootfolder, selected_org, object_name)
details_path = os.path.join(object_folder, "details.csv")
file_name=input("enter file name: ")
data_path = os.path.join(object_folder, file_name)

# data_path = os.path.join(object_folder, f'sql_{selected_org}__{object_name}.csv')

# Load the CSV files
mapping_df = pd.read_csv(details_path)
# Use low_memory=False to handle mixed for types warning
data_df = pd.read_csv(data_path, low_memory=False)

# Initialize the Issues column
data_df['Issues'] = ''

# Helper function to validate email format
def is_valid_email(email):
    # Handle non-string inputs (e.g., bool, float, etc.)
    if pd.isna(email) or email == '':
        return True  # Allow null/empty if not required
    # Convert to string to handle non-string types like bool
    email_str = str(email).strip()
    if email_str.lower() in ['true', 'false', '']:  # Skip boolean-like strings
        return True
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(email_regex, email_str))

# Validation 1 & 3: Check for required fields (mapping.csv Required == True)
required_fields = mapping_df[mapping_df['Required'] == True]['Field Name'].tolist()
for field in required_fields:
    if field in data_df.columns:
        # Check for null values in required fields
        null_rows = data_df[field].isna() | (data_df[field] == '')
        if null_rows.any():
            data_df.loc[null_rows, 'Issues'] = data_df.loc[null_rows, 'Issues'] + f"Required field '{field}' data is missing; "

# Validation 2: Check if all fields in data.csv are present in mapping.csv
data_fields = data_df.columns.tolist()
missing_fields = [field for field in data_fields if field not in mapping_df['Field Name'].tolist() and field != 'Issues']
if missing_fields:
    print(f"Fields in sql_{selected_org}__{object_name}.csv not present in Mapping.csv: {missing_fields}")
else:
    print(f"All fields in sql_{selected_org}__{object_name}.csv are present in Mapping.csv")

# Validation 4: Email validation for columns containing 'email' in their name
email_columns = [col for col in data_df.columns if 'email' in col.lower()]
for email_col in email_columns:
    invalid_emails = data_df[email_col].apply(lambda x: not is_valid_email(x))
    if invalid_emails.any():
        data_df.loc[invalid_emails, 'Issues'] = data_df.loc[invalid_emails, 'Issues'] + f"Invalid email format in '{email_col}'; "

# Validation 5: Check for unique fields (mapping.csv Unique == True)
unique_fields = mapping_df[mapping_df['Unique'] == True]['Field Name'].tolist()
for field in unique_fields:
    if field in data_df.columns:
        # Check for duplicate values (ignoring NaN)
        duplicates = data_df[field].duplicated(keep=False) & data_df[field].notna()
        if duplicates.any():
            data_df.loc[duplicates, 'Issues'] = data_df.loc[duplicates, 'Issues'] + f"Duplicate value in unique field '{field}'; "

# Validation 6: Check picklist values
picklist_fields = mapping_df[mapping_df['Type'] == 'picklist'][['Field Name', 'Picklist Values']].dropna()
for _, row in picklist_fields.iterrows():
    field = row['Field Name']
    valid_values = [val.strip() for val in row['Picklist Values'].split(',') if val.strip()]
    if field in data_df.columns:
        # Check if values in data.csv are in the valid picklist values (ignoring NaN)
        invalid_values = data_df[field].apply(lambda x: str(x).strip() not in valid_values if pd.notna(x) and str(x).strip() != '' else False)
        if invalid_values.any():
            data_df.loc[invalid_values, 'Issues'] = data_df.loc[invalid_values, 'Issues'] + f"Invalid picklist value in '{field}'; "

# Clean up Issues column (remove trailing semicolons and spaces)
data_df['Issues'] = data_df['Issues'].str.rstrip('; ')

# Check number of rows with issues
issues_count = len(data_df[data_df['Issues'] != ''])
print(f"Number of rows with issues: {issues_count}")

# Save the validated data
if issues_count <= 900000:
    # Save to single validated CSV
    validated_path = os.path.join(object_folder, f'{object_name}_Validated.csv')
    data_df.to_csv(validated_path, index=False)
    print(f"Validation complete. Output saved to '{validated_path}'")
else:
    # Create new folder named object_name
    split_folder = os.path.join(object_folder, object_name)
    os.makedirs(split_folder, exist_ok=True)
    
    # Save main file (complete dataset)
    main_file_path = os.path.join(split_folder, f'{object_name}_Validated.csv')
    data_df.to_csv(main_file_path, index=False)
    print(f"Main file saved to '{main_file_path}'")
    
    # Calculate number of files (500,000 records per file)
    records = len(data_df)
    file_count = records // 500000 + (1 if records % 500000 else 0)
    print(f"Splitting {records} records into {file_count} files")
    
    # Split and save files
    for i in range(file_count):
        start_idx = i * 500000
        end_idx = min((i + 1) * 500000, records)
        split_df = data_df.iloc[start_idx:end_idx]
        split_file_path = os.path.join(split_folder, f'{object_name}{i + 1}.csv')
        split_df.to_csv(split_file_path, index=False)
        print(f"Saved file {i + 1} with {len(split_df)} records to '{split_file_path}'")

# Return the required columns from data_df
required_cols = mapping_df[mapping_df['Required'] == True]['Field Name'].tolist()
if all(col in data_df.columns for col in required_cols):
    print("All required fields are present")
    output_df = data_df[required_cols + ['Issues']]
else:
    missing_required = [col for col in required_cols if col not in data_df.columns]
    print(f"Missing required fields: {missing_required}")
    output_df = None

# Display the first few rows of the output (for verification)
if output_df is not None:
    print(output_df.head())