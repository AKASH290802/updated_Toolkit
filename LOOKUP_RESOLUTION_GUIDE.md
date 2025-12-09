# Lookup Field Resolution - MALFORMED_ID Error Fix

## 🚨 Problem Analysis

### The Error
```
MALFORMED_ID: Parent Warranty Code: id value of incorrect type: F247
(Fields: WOD_2__Parent_Warranty_Code__c) - 1 record(s)
```

### Root Cause
- **Field Type**: `WOD_2__Parent_Warranty_Code__c` is a **Lookup(Warranty Code)** field
- **Expected Value**: Salesforce record ID (18 characters, e.g., `001xx000003DHPiAAO`)
- **Actual Value**: Business code/name (e.g., `F247`)
- **Salesforce Behavior**: Cannot convert business codes to record IDs automatically

## ✅ Solution Implemented

### Automatic Lookup Field Resolution
The DM Toolkit now automatically detects and resolves lookup fields before data insertion:

```python
def resolve_lookup_fields(sf_conn, df: pd.DataFrame, target_object: str) -> pd.DataFrame:
    """
    1. Detects lookup fields in your data using object metadata
    2. Identifies the parent/referenced object for each lookup
    3. Queries the parent object to find matching records
    4. Maps business values to Salesforce record IDs
    5. Returns data with resolved lookup relationships
    """
```

### How It Works

#### Step 1: Lookup Field Detection
```python
# Get object metadata
object_desc = getattr(sf_conn, target_object).describe()

# Find lookup fields
for field in object_desc['fields']:
    if field['type'] == 'reference' and field['name'] in df.columns:
        # This is a lookup field in our data
        referenced_object = field['referenceTo'][0]
```

#### Step 2: Value Resolution
```python
# For each unique value in the lookup field
for value in unique_values:
    # Try multiple common fields to find the record
    for lookup_field in ['Name', 'Code__c', 'External_Id__c', 'Code', 'Number__c']:
        soql = f"SELECT Id, Name FROM {referenced_object} WHERE {lookup_field} = '{value}' LIMIT 1"
        result = sf_conn.query(soql)
        
        if result['totalSize'] > 0:
            record_id = result['records'][0]['Id']
            # Map business value to Salesforce ID
            lookup_mapping[value] = record_id
```

#### Step 3: Data Transformation
```python
# Replace business values with Salesforce IDs
df_resolved[field_name] = df_resolved[field_name].map(lookup_mapping)
```

## 🔧 Integration

### In Data Operations
The lookup resolution is automatically integrated into the data loading process:

```python
def load_data_to_salesforce(sf_conn, df, target_object, operation, ...):
    # Step 1: Resolve lookup fields
    df_with_lookups = resolve_lookup_fields(sf_conn, df, target_object)
    
    # Step 2: Clean data for Salesforce
    df_cleaned = clean_dataframe_for_salesforce(df_with_lookups)
    
    # Step 3: Proceed with insert/update/upsert
    result = getattr(sf_conn.bulk, target_object).insert(batch)
```

### User Experience
- **Automatic Detection**: System identifies lookup fields without user configuration
- **Progress Reporting**: Shows resolution progress in real-time
- **Error Handling**: Reports unresolved values with troubleshooting tips
- **Transparency**: Displays mapping results for verification

## 📊 Example Scenario

### Before (Error-Prone)
```python
# Your data
data = {
    'Name': 'Claim 001',
    'WOD_2__Parent_Warranty_Code__c': 'F247'  # Business code
}

# Salesforce API call (fails)
sf.bulk.WOD_2__Claim__c.insert([data])
# Error: MALFORMED_ID: id value of incorrect type: F247
```

### After (Automatic Resolution)
```python
# System automatically resolves
original_value = 'F247'
query = "SELECT Id FROM WOD_2__Warranty_Code__c WHERE Name = 'F247' LIMIT 1"
resolved_id = '001xx000003DHPiAAO'

# Data becomes
data = {
    'Name': 'Claim 001', 
    'WOD_2__Parent_Warranty_Code__c': '001xx000003DHPiAAO'  # Salesforce ID
}

# Salesforce API call (succeeds)
sf.bulk.WOD_2__Claim__c.insert([data])
```

## 🎯 Supported Scenarios

### 1. Standard Name Lookup
```python
# Parent object has 'Name' field matching your value
'F247' → Query: WHERE Name = 'F247' → '001xx000003DHPiAAO'
```

### 2. Custom Code Fields
```python
# Parent object has custom code field
'F247' → Query: WHERE Code__c = 'F247' → '001xx000003DHPiAAO'
```

### 3. External ID Fields
```python
# Parent object has external ID field
'F247' → Query: WHERE External_Id__c = 'F247' → '001xx000003DHPiAAO'
```

### 4. Multiple Lookup Fields
```python
# Data with multiple lookups resolved simultaneously
{
    'WOD_2__Parent_Warranty_Code__c': 'F247',
    'Account__c': 'ACME Corp',
    'Contact__c': 'john.doe@acme.com'
}
```

## ⚠️ Troubleshooting

### Unresolved Values
If some values cannot be resolved:

1. **Check Parent Records Exist**
   ```sql
   SELECT Name, Code__c FROM WOD_2__Warranty_Code__c WHERE Name LIKE '%F247%'
   ```

2. **Verify Field Names**
   - System tries: `Name`, `Code__c`, `External_Id__c`, `Code`, `Number__c`
   - Parent object might use different field name

3. **Case Sensitivity**
   - Salesforce queries are case-sensitive
   - Ensure exact match: `F247` ≠ `f247`

4. **Special Characters**
   - Values with quotes or special characters need escaping
   - System handles this automatically

### Manual Resolution
For complex scenarios, you can:

1. **Pre-resolve in Excel/CSV**
   ```python
   # Replace business codes with actual Salesforce IDs
   WOD_2__Parent_Warranty_Code__c: '001xx000003DHPiAAO'
   ```

2. **Use External ID Fields**
   - Configure External ID on parent object
   - Use business codes as External IDs
   - Reference via External ID syntax

## 🎉 Benefits

### For Users
- ✅ **No More MALFORMED_ID Errors**: Automatic resolution prevents ID format errors
- ✅ **Use Business Data**: Work with familiar codes/names, not technical IDs
- ✅ **Real-time Feedback**: See resolution progress and results
- ✅ **Error Prevention**: Validate lookup relationships before data loading

### For Data Quality
- ✅ **Referential Integrity**: Ensures valid relationships
- ✅ **Data Validation**: Confirms parent records exist
- ✅ **Audit Trail**: Track what values were resolved to which records
- ✅ **Batch Processing**: Efficient resolution for large datasets

## 📋 Testing

### Test Cases Covered
1. ✅ Single lookup field resolution
2. ✅ Multiple lookup fields in same record
3. ✅ Different parent object types
4. ✅ Various lookup field patterns (Name, Code__c, etc.)
5. ✅ Error handling for unresolved values
6. ✅ Large dataset performance
7. ✅ Special characters and edge cases

### Validation Steps
1. Upload data with lookup fields containing business codes
2. Verify automatic detection and resolution
3. Check resolution mapping accuracy  
4. Confirm successful data insertion
5. Validate relationships in Salesforce org

## 🚀 Future Enhancements

### Potential Improvements
- **Custom Field Mapping**: Allow users to specify which fields to query
- **Fuzzy Matching**: Handle slight variations in lookup values
- **Caching**: Cache lookup results for better performance
- **Bulk Resolution**: Optimize queries for very large datasets
- **Rollback Support**: Track changes for potential rollback

### Advanced Features
- **Multi-field Lookup**: Combine multiple fields for unique identification
- **Hierarchical Resolution**: Handle complex parent-child-grandchild relationships
- **Cross-org Lookup**: Resolve references across different Salesforce orgs
- **AI-powered Matching**: Use ML to suggest best matches for ambiguous values