"""
Test to verify rule display messages are removed from custom validation UI
"""
import sys
import os
sys.path.append(os.path.dirname(__file__))

import pandas as pd
import streamlit as st
from unittest.mock import patch, MagicMock
import io

# Import the validation function
from ui_components.validation_operations import run_custom_validation

def test_rule_display_removal():
    """Test that rule display messages are no longer shown"""
    
    print("=== TESTING RULE DISPLAY REMOVAL ===\n")
    
    # Create test data
    test_data = pd.DataFrame({
        'Name': ['Test Account 1', 'Test Account 2'],
        'Phone': ['1234567890', '0987654321']
    })
    
    # Create test rules with problematic formulas
    test_rules = [
        {
            'FullName': 'CLM_NonSerializedPartCannotHaveSerialNo',
            'ValidationFormula': 'FORMULA_NOT_ACCESSIBLE_VIA_API',
            'ErrorMessage': 'Non-serialized parts cannot have serial numbers',
            'source': 'sf_validation_client'
        },
        {
            'FullName': 'GW_REASON_MANDATORY', 
            'ValidationFormula': 'FORMULA_NOT_ACCESSIBLE_VIA_API',
            'ErrorMessage': 'Reason is mandatory',
            'source': 'sf_validation_client'
        },
        {
            'FullName': 'MC_PC_ACCOUNT_MANDATORY',
            'ValidationFormula': 'FORMULA_NOT_ACCESSIBLE_VIA_API', 
            'ErrorMessage': 'Account is mandatory',
            'source': 'sf_validation_client'
        }
    ]
    
    # Capture streamlit output
    captured_messages = []
    
    def capture_write(message):
        captured_messages.append(str(message))
        print(f"Captured: {message}")
    
    def capture_info(message):
        captured_messages.append(str(message))
        print(f"Info: {message}")
        
    def capture_error(message):
        captured_messages.append(str(message))
        print(f"Error: {message}")
    
    # Mock streamlit functions to capture output
    with patch('streamlit.write', side_effect=capture_write), \
         patch('streamlit.info', side_effect=capture_info), \
         patch('streamlit.error', side_effect=capture_error), \
         patch('streamlit.success') as mock_success, \
         patch('streamlit.warning') as mock_warning, \
         patch('streamlit.progress') as mock_progress, \
         patch('streamlit.container') as mock_container, \
         patch('streamlit.columns') as mock_columns:
        
        # Mock container and columns
        mock_container.return_value.__enter__ = MagicMock()
        mock_container.return_value.__exit__ = MagicMock()
        mock_columns.return_value = [MagicMock(), MagicMock()]
        
        try:
            print("Running custom validation with test rules...")
            run_custom_validation('Account', test_data, test_rules)
            print("✅ Custom validation completed without errors")
        except Exception as e:
            print(f"❌ Error during validation: {str(e)}")
    
    # Check for problematic messages
    all_output = ' '.join(captured_messages)
    
    problematic_patterns = [
        'Rule 1:',
        'Rule 2:', 
        'Rule 3:',
        'CLM_NonSerializedPartCannotHaveSerialNo (Source: sf_validation_client)',
        'GW_REASON_MANDATORY (Source: sf_validation_client)',
        'MC_PC_ACCOUNT_MANDATORY (Source: sf_validation_client)',
        '⚠️ Not accessible via API',
        'Formula: ⚠️ Not accessible via API'
    ]
    
    found_problems = []
    for pattern in problematic_patterns:
        if pattern in all_output:
            found_problems.append(pattern)
    
    print(f"\n=== TEST RESULTS ===")
    print(f"Total captured messages: {len(captured_messages)}")
    print(f"Problematic patterns found: {len(found_problems)}")
    
    if found_problems:
        print(f"\n❌ STILL DISPLAYING UNWANTED MESSAGES:")
        for problem in found_problems:
            print(f"   - {problem}")
        return False
    else:
        print(f"\n✅ SUCCESS: No unwanted rule display messages found!")
        print(f"✅ UI is now clean - rule details are processed silently")
        return True

if __name__ == "__main__":
    success = test_rule_display_removal()
    if success:
        print(f"\n🎉 RULE DISPLAY REMOVAL SUCCESSFUL!")
    else:
        print(f"\n⚠️ Some messages still need to be removed")