"""
Debug Test - Check if Enhanced Validation is Properly Detecting Invalid Records
"""
import sys
import os
sys.path.append(os.path.dirname(__file__))

import pandas as pd
import streamlit as st
from unittest.mock import patch
import io

# Import the validation function
from ui_components.validation_operations import apply_basic_validation

def test_validation_detection():
    """Test if validation properly detects invalid records"""
    
    print("=== ENHANCED VALIDATION DEBUG TEST ===\n")
    
    # Test scenarios that should FAIL validation
    test_cases = [
        {
            "name": "Required Field - Empty Value",
            "rule": {
                "FullName": "Test_Required_Field",
                "ErrorMessage": "Account Name is required and cannot be blank",
                "ErrorDisplayField": "Name",
                "field_mappings": {"Name": "account_name"}
            },
            "data": {"account_name": ""},  # EMPTY - Should FAIL
            "expected": False
        },
        {
            "name": "Age Range - Too Young", 
            "rule": {
                "FullName": "Age_Range_Validation",
                "ErrorMessage": "Age must be between 18 and 65 years old",
                "ErrorDisplayField": "Age",
                "field_mappings": {"Age": "age"}
            },
            "data": {"age": 15},  # TOO YOUNG - Should FAIL
            "expected": False
        },
        {
            "name": "Phone Length - Too Short",
            "rule": {
                "FullName": "Phone_Length_Validation", 
                "ErrorMessage": "Phone number must be at least 10 characters long",
                "ErrorDisplayField": "Phone",
                "field_mappings": {"Phone": "phone"}
            },
            "data": {"phone": "123456"},  # TOO SHORT - Should FAIL
            "expected": False
        },
        {
            "name": "Email Format - Invalid",
            "rule": {
                "FullName": "Email_Format_Validation",
                "ErrorMessage": "Please enter a valid email address format",
                "ErrorDisplayField": "Email", 
                "field_mappings": {"Email": "email"}
            },
            "data": {"email": "invalid-email"},  # INVALID FORMAT - Should FAIL
            "expected": False
        },
        {
            "name": "Salary Minimum - Too Low",
            "rule": {
                "FullName": "Salary_Minimum_Validation",
                "ErrorMessage": "Salary must be at least 30000 dollars",
                "ErrorDisplayField": "Salary",
                "field_mappings": {"Salary": "salary"}
            },
            "data": {"salary": 25000},  # TOO LOW - Should FAIL
            "expected": False
        }
    ]
    
    # Test scenarios that should PASS validation
    valid_test_cases = [
        {
            "name": "Required Field - Has Value",
            "rule": {
                "FullName": "Test_Required_Field",
                "ErrorMessage": "Account Name is required and cannot be blank",
                "ErrorDisplayField": "Name",
                "field_mappings": {"Name": "account_name"}
            },
            "data": {"account_name": "ACME Corp"},  # HAS VALUE - Should PASS
            "expected": True
        },
        {
            "name": "Age Range - Valid Age",
            "rule": {
                "FullName": "Age_Range_Validation", 
                "ErrorMessage": "Age must be between 18 and 65 years old",
                "ErrorDisplayField": "Age",
                "field_mappings": {"Age": "age"}
            },
            "data": {"age": 25},  # VALID AGE - Should PASS
            "expected": True
        }
    ]
    
    all_tests = test_cases + valid_test_cases
    results = []
    
    # Capture Streamlit output
    with patch('streamlit.write') as mock_write, \
         patch('streamlit.warning') as mock_warning, \
         patch('streamlit.exception') as mock_exception:
        
        for i, test_case in enumerate(all_tests, 1):
            print(f"\n{i}. Testing: {test_case['name']}")
            print(f"   Rule: {test_case['rule']['ErrorMessage']}")
            print(f"   Data: {test_case['data']}")
            print(f"   Expected: {'PASS' if test_case['expected'] else 'FAIL'}")
            
            # Create test data row
            row = pd.Series(test_case["data"])
            
            # Apply validation
            try:
                actual_result = apply_basic_validation(row, test_case["rule"])
                success = actual_result == test_case["expected"]
                
                print(f"   Actual: {'PASS' if actual_result else 'FAIL'}")
                print(f"   ✅ Test: {'SUCCESS' if success else 'FAILED'}")
                
                # Check streamlit outputs
                st_outputs = [str(call.args[0]) for call in mock_write.call_args_list if call.args]
                if st_outputs:
                    print(f"   Validation Details: {st_outputs[-1] if st_outputs else 'None'}")
                
                results.append({
                    "test": test_case["name"],
                    "expected": test_case["expected"],
                    "actual": actual_result,
                    "success": success,
                    "details": st_outputs[-1] if st_outputs else "No details"
                })
                
                # Clear mock calls for next test
                mock_write.reset_mock()
                mock_warning.reset_mock()
                mock_exception.reset_mock()
                
            except Exception as e:
                print(f"   ❌ ERROR: {str(e)}")
                results.append({
                    "test": test_case["name"],
                    "expected": test_case["expected"],
                    "actual": None,
                    "success": False,
                    "details": f"Error: {str(e)}"
                })
    
    # Summary
    print(f"\n=== VALIDATION TEST SUMMARY ===")
    passed = sum(1 for r in results if r["success"])
    total = len(results)
    print(f"Tests Passed: {passed}/{total} ({passed/total*100:.1f}%)")
    
    # Check if validation is working properly
    failing_tests = [r for r in results if not r["success"]]
    if failing_tests:
        print(f"\n❌ ISSUES FOUND:")
        for test in failing_tests:
            print(f"   - {test['test']}: Expected {'PASS' if test['expected'] else 'FAIL'}, Got {'PASS' if test['actual'] else 'FAIL'}")
            print(f"     Details: {test['details']}")
    
    # Check if all records are going to valid (the main complaint)
    invalid_should_fail = [r for r in results[:5] if not r["expected"]]  # First 5 should fail
    all_marked_valid = all(r["actual"] for r in invalid_should_fail if r["actual"] is not None)
    
    if all_marked_valid:
        print(f"\n🚨 MAIN ISSUE CONFIRMED: All records marked as VALID even when they should FAIL")
        print(f"   This suggests the validation logic is not properly detecting constraints")
    else:
        print(f"\n✅ VALIDATION WORKING: Some records correctly marked as INVALID")
    
    return results

if __name__ == "__main__":
    results = test_validation_detection()