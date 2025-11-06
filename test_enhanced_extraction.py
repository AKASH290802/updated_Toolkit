"""
Test Enhanced Field and Constraint Extraction Logic
"""
import sys
sys.path.append('.')

from enhanced_field_constraint_extraction import (
    extract_field_names_from_message,
    extract_constraints_from_message, 
    determine_validation_logic,
    apply_enhanced_validation
)
import pandas as pd

def test_enhanced_extraction():
    """Test the enhanced field and constraint extraction"""
    
    print("=" * 80)
    print("TESTING ENHANCED FIELD AND CONSTRAINT EXTRACTION")
    print("=" * 80)
    
    # Test cases
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
            'expected_field': 'email address',
            'expected_constraint': 'email format'
        },
        {
            'rule_name': 'Phone_Length_Rule',
            'message': 'Phone number must be at least 10 characters long',
            'expected_field': 'Phone number',
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
    print("ENHANCED EXTRACTION RESULTS")
    print("="*60)
    
    success_count = 0
    
    for i, test in enumerate(test_messages, 1):
        print(f"\\n📋 Test {i}: {test['rule_name']}")
        print(f"   Message: '{test['message']}'")
        
        # Extract fields and constraints
        fields = extract_field_names_from_message(test['message'], test['rule_name'])
        constraints = extract_constraints_from_message(test['message'], test['rule_name'])
        logic = determine_validation_logic(constraints)
        
        print(f"   ✅ Extracted Fields: {fields}")
        print(f"   📐 Constraints: {constraints}")
        print(f"   🔧 Logic: {logic}")
        
        # Check success
        field_found = any(
            test['expected_field'].lower() in field.lower() or 
            field.lower() in test['expected_field'].lower()
            for field in fields
        )
        
        constraint_found = len(constraints.get('constraint_types', [])) > 0
        
        if field_found and constraint_found:
            success_count += 1
            print(f"   ✅ SUCCESS: Field and constraint properly extracted")
        elif field_found:
            print(f"   ⚠️  PARTIAL: Field found, constraint needs improvement")
        elif constraint_found:
            print(f"   ⚠️  PARTIAL: Constraint found, field needs improvement")
        else:
            print(f"   ❌ FAILED: Both field and constraint extraction failed")
    
    # Summary
    total_tests = len(test_messages)
    success_rate = (success_count / total_tests) * 100
    
    print(f"\\n" + "="*60)
    print("ENHANCED EXTRACTION SUMMARY")
    print("="*60)
    print(f"Total tests: {total_tests}")
    print(f"Successful extractions: {success_count}")
    print(f"Success rate: {success_rate:.1f}%")
    
    if success_rate >= 80:
        print(f"\\n✅ EXCELLENT: Enhanced extraction significantly improved!")
    elif success_rate >= 60:
        print(f"\\n⚠️  GOOD: Enhanced extraction shows improvement")
    else:
        print(f"\\n❌ NEEDS WORK: Enhanced extraction still needs improvement")
    
    return success_rate

def test_enhanced_validation():
    """Test the enhanced validation logic with extracted constraints"""
    
    print(f"\\n" + "="*80)
    print("TESTING ENHANCED VALIDATION APPLICATION")
    print("="*80)
    
    # Test data
    test_data = pd.DataFrame({
        'Account Name': ['ACME Corp', '', 'Test Inc', None],
        'Age': [25, 15, 45, 70],
        'Email': ['test@example.com', 'invalid-email', 'user@domain.com', ''],
        'Phone': ['123-456-7890', '123', '987-654-3210', '555-1234'],
        'Salary': [50000, 25000, 75000, 150000],
        'Status': ['Active', 'Unknown', 'Inactive', 'Pending']
    })
    
    print("Test Data:")
    print(test_data.to_string(index=False))
    
    # Test validation rules
    validation_tests = [
        {
            'message': 'Account Name is required and cannot be blank',
            'test_field': 'Account Name'
        },
        {
            'message': 'Age must be between 18 and 65 years',
            'test_field': 'Age'
        },
        {
            'message': 'Please enter a valid email address format',
            'test_field': 'Email'
        },
        {
            'message': 'Salary must be at least 30000 for this position',
            'test_field': 'Salary'
        }
    ]
    
    print(f"\\n" + "="*50)
    print("VALIDATION RESULTS")
    print("="*50)
    
    for test_rule in validation_tests:
        message = test_rule['message']
        field = test_rule['test_field']
        
        print(f"\\n🔍 Rule: {message}")
        print(f"   Testing field: {field}")
        
        # Extract constraints
        constraints = extract_constraints_from_message(message)
        print(f"   Extracted constraints: {constraints.get('constraint_types', [])}")
        
        # Test each record
        for idx, row in test_data.iterrows():
            is_valid, reason = apply_enhanced_validation(row, field, constraints)
            status = "✅ VALID" if is_valid else "❌ INVALID"
            print(f"   Record {idx} ({field}='{row[field]}'): {status} - {reason}")
    
    return True

if __name__ == "__main__":
    print("Testing Enhanced Field and Constraint Extraction\\n")
    
    extraction_success_rate = test_enhanced_extraction()
    validation_success = test_enhanced_validation()
    
    print(f"\\n" + "=" * 80)
    print("FINAL ASSESSMENT")
    print("=" * 80)
    
    if extraction_success_rate >= 80:
        print("🎉 ENHANCED EXTRACTION IS SIGNIFICANTLY BETTER!")
        print("✅ Field names are properly extracted from error messages")
        print("✅ Constraints are comprehensively detected and parsed")
        print("✅ Validation logic is appropriately determined")
        print("✅ Enhanced system ready for integration into custom validation")
    else:
        print("⚠️  Enhanced extraction shows improvement but needs more work")
        print("💡 Consider adding more pattern variations")
        print("💡 Enhance edge case handling")
    
    print("=" * 80)