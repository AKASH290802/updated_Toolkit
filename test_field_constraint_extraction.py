"""
Test Field and Constraint Extraction from Error Messages
This tests how well the system extracts both field names AND specific constraints from validation rule error messages
"""
import pandas as pd
import re

def extract_field_and_constraints_from_message(error_message: str, rule_name: str = "") -> dict:
    """Extract field names and specific constraints from validation rule error messages"""
    
    analysis = {
        'original_message': error_message,
        'rule_name': rule_name,
        'extracted_fields': [],
        'extracted_constraints': {},
        'constraint_type': 'unknown',
        'validation_logic': 'default'
    }
    
    # Combine text for analysis
    all_text = f"{rule_name} {error_message}".lower()
    
    # 1. EXTRACT FIELD NAMES from error message
    field_extraction_patterns = [
        # Fields in quotes
        r"'([^']+)'\s+(?:field|must|cannot|should|is)",
        r"(?:field|the)\s+'([^']+)'",
        # Field names followed by validation words
        r"([A-Za-z_][A-Za-z0-9_]*)\s+(?:must|cannot|should|is required|is mandatory)",
        # Fields mentioned with "enter" or "provide"
        r"(?:enter|provide|fill|specify)\s+(?:a\s+|an\s+|the\s+)?([A-Za-z_][A-Za-z0-9_]*)",
        # Fields at the beginning of sentences
        r"^([A-Za-z_][A-Za-z0-9_]*)\s+(?:must|cannot|should|is)",
        # Fields with error context
        r"(?:invalid|missing|empty|blank)\s+([A-Za-z_][A-Za-z0-9_]*)",
    ]
    
    for pattern in field_extraction_patterns:
        matches = re.findall(pattern, error_message, re.IGNORECASE)
        for match in matches:
            if match and len(match) > 1:  # Avoid single characters
                analysis['extracted_fields'].append(match.strip())
    
    # Remove duplicates and filter
    analysis['extracted_fields'] = list(set([f for f in analysis['extracted_fields'] if len(f) > 1]))
    
    # 2. EXTRACT SPECIFIC CONSTRAINTS
    
    # A. RANGE CONSTRAINTS
    range_patterns = [
        # "between X and Y"
        r'between\s+(\d+(?:\.\d+)?)\s+and\s+(\d+(?:\.\d+)?)',
        # "from X to Y"
        r'from\s+(\d+(?:\.\d+)?)\s+to\s+(\d+(?:\.\d+)?)',
        # "X to Y" or "X-Y"
        r'(\d+(?:\.\d+)?)\s*(?:to|-)\s*(\d+(?:\.\d+)?)',
    ]
    
    for pattern in range_patterns:
        matches = re.findall(pattern, error_message, re.IGNORECASE)
        if matches:
            for match in matches:
                analysis['constraint_type'] = 'range'
                analysis['extracted_constraints']['min_value'] = float(match[0])
                analysis['extracted_constraints']['max_value'] = float(match[1])
                analysis['validation_logic'] = 'range_check'
    
    # B. MINIMUM/MAXIMUM CONSTRAINTS
    min_patterns = [
        r'(?:minimum|min|at least|greater than)\s+(\d+(?:\.\d+)?)',
        r'must be\s+(\d+(?:\.\d+)?)\s+or\s+(?:more|greater)',
    ]
    
    max_patterns = [
        r'(?:maximum|max|at most|no more than|less than)\s+(\d+(?:\.\d+)?)',
        r'must be\s+(\d+(?:\.\d+)?)\s+or\s+(?:less|fewer)',
    ]
    
    for pattern in min_patterns:
        matches = re.findall(pattern, error_message, re.IGNORECASE)
        if matches:
            analysis['constraint_type'] = 'minimum'
            analysis['extracted_constraints']['min_value'] = float(matches[0])
            analysis['validation_logic'] = 'min_check'
    
    for pattern in max_patterns:
        matches = re.findall(pattern, error_message, re.IGNORECASE)
        if matches:
            if analysis['constraint_type'] == 'minimum':
                analysis['constraint_type'] = 'min_max'
            else:
                analysis['constraint_type'] = 'maximum'
            analysis['extracted_constraints']['max_value'] = float(matches[0])
            analysis['validation_logic'] = 'max_check' if analysis['constraint_type'] == 'maximum' else 'min_max_check'
    
    # C. LENGTH CONSTRAINTS
    length_patterns = [
        # "X characters long", "length of X"
        r'(?:length of|must be)\s+(\d+)\s+characters?',
        r'(\d+)\s+characters?\s+(?:long|maximum|minimum)',
        # "at least X characters"
        r'at least\s+(\d+)\s+characters?',
        # "no more than X characters"
        r'no more than\s+(\d+)\s+characters?',
        # "between X and Y characters"
        r'between\s+(\d+)\s+and\s+(\d+)\s+characters?',
    ]
    
    for pattern in length_patterns:
        matches = re.findall(pattern, error_message, re.IGNORECASE)
        if matches:
            analysis['constraint_type'] = 'length'
            analysis['validation_logic'] = 'length_check'
            if isinstance(matches[0], tuple) and len(matches[0]) == 2:
                # Range like "between X and Y characters"
                analysis['extracted_constraints']['min_length'] = int(matches[0][0])
                analysis['extracted_constraints']['max_length'] = int(matches[0][1])
            else:
                # Single value
                if 'at least' in error_message.lower():
                    analysis['extracted_constraints']['min_length'] = int(matches[0])
                elif 'no more than' in error_message.lower() or 'maximum' in error_message.lower():
                    analysis['extracted_constraints']['max_length'] = int(matches[0])
                else:
                    analysis['extracted_constraints']['exact_length'] = int(matches[0])
    
    # D. FORMAT CONSTRAINTS
    format_patterns = [
        # Email format
        r'(?:valid\s+)?email(?:\s+(?:address|format))?',
        r'@.*\..*format',
        # Phone format
        r'(?:valid\s+)?phone(?:\s+(?:number|format))?',
        r'(?:\d{3}[-.]?)?\d{3}[-.]?\d{4}',
        # Date format
        r'(?:valid\s+)?date(?:\s+format)?',
        r'(?:mm/dd/yyyy|dd/mm/yyyy|yyyy-mm-dd)',
        # Custom patterns
        r'format\s+(?:must be|should be)\s+"([^"]+)"',
        r'pattern\s+"([^"]+)"',
    ]
    
    for pattern in format_patterns:
        matches = re.findall(pattern, error_message, re.IGNORECASE)
        if matches:
            analysis['constraint_type'] = 'format'
            analysis['validation_logic'] = 'format_check'
            if 'email' in pattern:
                analysis['extracted_constraints']['format_type'] = 'email'
            elif 'phone' in pattern:
                analysis['extracted_constraints']['format_type'] = 'phone'
            elif 'date' in pattern:
                analysis['extracted_constraints']['format_type'] = 'date'
            else:
                analysis['extracted_constraints']['format_pattern'] = matches[0] if matches else None
    
    # E. VALUE CONSTRAINTS
    value_patterns = [
        # Specific values
        r'must be\s+"([^"]+)"',
        r'(?:only|should be)\s+(?:"([^"]+)"|([A-Za-z]+))',
        # List of values
        r'(?:one of|must be)\s+(?:the following:?\s*)?(?:"([^"]+)"|([A-Za-z,\s]+))',
        # Prohibited values
        r'cannot be\s+"([^"]+)"',
        r'(?:not|never)\s+(?:"([^"]+)"|([A-Za-z]+))',
    ]
    
    for pattern in value_patterns:
        matches = re.findall(pattern, error_message, re.IGNORECASE)
        if matches:
            analysis['constraint_type'] = 'value'
            analysis['validation_logic'] = 'value_check'
            if 'cannot be' in error_message.lower() or 'not' in error_message.lower():
                analysis['extracted_constraints']['prohibited_values'] = [m for m in matches[0] if m]
            else:
                analysis['extracted_constraints']['allowed_values'] = [m for m in matches[0] if m]
    
    # F. REQUIRED/NOT EMPTY CONSTRAINTS
    if any(keyword in all_text for keyword in ['required', 'mandatory', 'cannot be blank', 'must not be empty']):
        analysis['constraint_type'] = 'required'
        analysis['validation_logic'] = 'not_empty_check'
        analysis['extracted_constraints']['required'] = True
    
    return analysis

def test_field_constraint_extraction():
    """Test extraction of fields and constraints from various error messages"""
    
    print("=" * 80)
    print("TESTING FIELD AND CONSTRAINT EXTRACTION FROM ERROR MESSAGES")
    print("=" * 80)
    
    # Test cases with various error message patterns
    test_messages = [
        {
            'rule_name': 'Account_Name_Required',
            'message': 'Account Name is required and cannot be blank',
            'expected_field': 'Account Name',
            'expected_constraint': 'required'
        },
        {
            'rule_name': 'Age_Range_Validation',
            'message': 'Age must be between 18 and 65 years',
            'expected_field': 'Age',
            'expected_constraint': 'range: 18-65'
        },
        {
            'rule_name': 'Email_Format_Rule',
            'message': 'Please enter a valid email address format',
            'expected_field': 'email',
            'expected_constraint': 'email format'
        },
        {
            'rule_name': 'Phone_Length_Rule',
            'message': 'Phone number must be at least 10 characters long',
            'expected_field': 'Phone',
            'expected_constraint': 'min length: 10'
        },
        {
            'rule_name': 'Status_Value_Rule',
            'message': 'Status must be one of "Active", "Inactive", or "Pending"',
            'expected_field': 'Status',
            'expected_constraint': 'allowed values'
        },
        {
            'rule_name': 'Salary_Minimum_Rule',
            'message': 'Salary must be at least 30000 for this position',
            'expected_field': 'Salary',
            'expected_constraint': 'minimum: 30000'
        },
        {
            'rule_name': 'Code_Length_Rule',
            'message': 'Product code length must be between 5 and 12 characters',
            'expected_field': 'Product code',
            'expected_constraint': 'length: 5-12'
        },
        {
            'rule_name': 'Date_Format_Rule',
            'message': 'Start Date must be in valid date format (MM/DD/YYYY)',
            'expected_field': 'Start Date',
            'expected_constraint': 'date format'
        },
        {
            'rule_name': 'Complex_Business_Rule',
            'message': 'Annual Revenue cannot exceed 1000000 when Company Type is "Small Business"',
            'expected_field': 'Annual Revenue',
            'expected_constraint': 'conditional max: 1000000'
        },
        {
            'rule_name': 'Custom_Pattern_Rule',
            'message': 'SKU format must be "ABC-123" pattern with 3 letters, dash, and 3 numbers',
            'expected_field': 'SKU',
            'expected_constraint': 'custom pattern'
        }
    ]
    
    print("Test Cases:")
    for i, test in enumerate(test_messages, 1):
        print(f"{i:2d}. {test['rule_name']}: '{test['message']}'")
    
    print(f"\\n" + "="*60)
    print("EXTRACTION RESULTS")
    print("="*60)
    
    extraction_success_count = 0
    total_tests = len(test_messages)
    
    for i, test in enumerate(test_messages, 1):
        print(f"\\n📋 Test {i}: {test['rule_name']}")
        print(f"   Message: '{test['message']}'")
        
        result = extract_field_and_constraints_from_message(test['message'], test['rule_name'])
        
        print(f"   ✅ Extracted Fields: {result['extracted_fields']}")
        print(f"   🎯 Constraint Type: {result['constraint_type']}")
        print(f"   📐 Constraints: {result['extracted_constraints']}")
        print(f"   🔧 Validation Logic: {result['validation_logic']}")
        
        # Check if extraction was successful
        field_found = any(field.lower() in test['expected_field'].lower() or 
                         test['expected_field'].lower() in field.lower() 
                         for field in result['extracted_fields'])
        
        constraint_found = result['constraint_type'] != 'unknown' and len(result['extracted_constraints']) > 0
        
        if field_found and constraint_found:
            extraction_success_count += 1
            print(f"   ✅ SUCCESS: Both field and constraint extracted")
        elif field_found:
            print(f"   ⚠️  PARTIAL: Field found but constraint extraction needs improvement")
        elif constraint_found:
            print(f"   ⚠️  PARTIAL: Constraint found but field extraction needs improvement")
        else:
            print(f"   ❌ FAILED: Neither field nor constraint properly extracted")
    
    # Summary
    print(f"\\n" + "="*60)
    print("EXTRACTION SUMMARY")
    print("="*60)
    print(f"Total tests: {total_tests}")
    print(f"Successful extractions: {extraction_success_count}")
    print(f"Success rate: {(extraction_success_count/total_tests*100):.1f}%")
    
    if extraction_success_count < total_tests:
        print(f"\\n❌ GAPS IDENTIFIED:")
        print(f"   • Field extraction patterns need enhancement")
        print(f"   • Constraint detection logic needs improvement")
        print(f"   • More sophisticated parsing required")
    else:
        print(f"\\n✅ ALL EXTRACTION TESTS PASSED!")
    
    return extraction_success_count == total_tests

def apply_extracted_constraint_validation(row: pd.Series, field_name: str, constraints: dict, constraint_type: str) -> bool:
    """Apply validation based on extracted constraints"""
    
    if not field_name or field_name not in row.index:
        return True
    
    field_value = row[field_name]
    
    # Handle empty values
    if pd.isna(field_value) or str(field_value).strip() == '':
        if constraints.get('required', False):
            return False  # Required field is empty
        else:
            return True  # Empty is okay for non-required fields
    
    value_str = str(field_value).strip()
    
    # Apply constraint-specific validation
    if constraint_type == 'range':
        try:
            num_value = float(value_str)
            min_val = constraints.get('min_value')
            max_val = constraints.get('max_value')
            if min_val is not None and max_val is not None:
                return min_val <= num_value <= max_val
        except:
            return False
    
    elif constraint_type == 'minimum':
        try:
            num_value = float(value_str)
            min_val = constraints.get('min_value')
            return num_value >= min_val if min_val is not None else True
        except:
            return False
    
    elif constraint_type == 'maximum':
        try:
            num_value = float(value_str)
            max_val = constraints.get('max_value')
            return num_value <= max_val if max_val is not None else True
        except:
            return False
    
    elif constraint_type == 'length':
        length = len(value_str)
        min_len = constraints.get('min_length')
        max_len = constraints.get('max_length')
        exact_len = constraints.get('exact_length')
        
        if exact_len is not None:
            return length == exact_len
        
        if min_len is not None and length < min_len:
            return False
        
        if max_len is not None and length > max_len:
            return False
        
        return True
    
    elif constraint_type == 'format':
        format_type = constraints.get('format_type')
        if format_type == 'email':
            return '@' in value_str and '.' in value_str.split('@')[-1]
        elif format_type == 'phone':
            digits = re.sub(r'[^\\d]', '', value_str)
            return len(digits) >= 10
        elif format_type == 'date':
            try:
                from datetime import datetime
                import dateutil.parser
                dateutil.parser.parse(value_str)
                return True
            except:
                return False
    
    elif constraint_type == 'value':
        allowed_values = constraints.get('allowed_values', [])
        prohibited_values = constraints.get('prohibited_values', [])
        
        if allowed_values and value_str not in allowed_values:
            return False
        
        if prohibited_values and value_str in prohibited_values:
            return False
    
    elif constraint_type == 'required':
        return not (pd.isna(field_value) or str(field_value).strip() == '')
    
    return True

if __name__ == "__main__":
    print("Testing Field and Constraint Extraction from Error Messages\\n")
    
    extraction_success = test_field_constraint_extraction()
    
    print(f"\\n" + "=" * 80)
    print("CONCLUSION")
    print("=" * 80)
    
    if extraction_success:
        print("✅ Current extraction logic is comprehensive")
        print("✅ Both fields and constraints are properly detected")
    else:
        print("❌ Extraction logic needs enhancement")
        print("💡 Recommendations:")
        print("   1. Add more field name extraction patterns")
        print("   2. Enhance constraint detection for complex rules")
        print("   3. Improve pattern matching for business logic")
        print("   4. Add support for conditional constraints")
    
    print("=" * 80)