#!/usr/bin/env python3

import re

def extract_fields_from_code(func_source):
    """Extract field names from function source code"""
    fields = []
    
    # Pattern 1: df['FieldName'] or df["FieldName"]
    field_pattern1 = re.findall(r"df\s*\[\s*['\"]([^'\"]+)['\"]\s*\]", func_source)
    fields.extend(field_pattern1)
    
    # Pattern 2: _is_blank(df['FieldName']) and similar function calls
    field_pattern2 = re.findall(r"_is_blank\s*\(\s*df\s*\[\s*['\"]([^'\"]+)['\"]\s*\]\s*\)", func_source)
    fields.extend(field_pattern2)
    
    # Remove duplicates and filter
    fields = list(set(fields))
    exclude_words = ['True', 'False', 'None', 'index', 'columns', 'fillna', 'astype', 'str']
    fields = [f for f in fields if f not in exclude_words and len(f) > 1]
    
    return fields[:5]

# Test cases
test_code1 = """
    validation_result = _is_blank(df['Name'])
    if not isinstance(validation_result, pd.Series):
        validation_result = pd.Series([bool(validation_result)] * len(df))
"""

test_code2 = """
    validation_result = _is_blank(df['Phone'])
    if not isinstance(validation_result, pd.Series):
        validation_result = pd.Series([bool(validation_result)] * len(df))
"""

print("Field extraction test results:")
print("Test 1 (Name validation):", extract_fields_from_code(test_code1))
print("Test 2 (Phone validation):", extract_fields_from_code(test_code2))

# Test with actual bundle content
with open(r"c:\DM_toolkit\Validation\AkashDev\Account\GenAIValidation\validation_bundle\bundle.py", 'r') as f:
    bundle_content = f.read()

# Extract fields from entire bundle
all_fields = extract_fields_from_code(bundle_content)
print("Fields from entire bundle:", all_fields)