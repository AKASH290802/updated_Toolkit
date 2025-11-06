#!/usr/bin/env python3
"""
Test script to verify bundle generation works correctly
"""

import pandas as pd
import os
import sys

# Add the validation_script directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'validation_script'))

from GenAI_Validation import generate_validation_bundle_from_dataframe

def test_bundle_generation():
    """Test bundle generation with a simple validation rule"""
    
    # Create a simple test validation rule
    test_data = {
        'ValidationName': ['Name_Not_Empty'],
        'ErrorConditionFormula': ['ISBLANK(Name)'],
        'FieldName': ['Name'],
        'ObjectName': ['Account'],
        'Active': [True]
    }
    
    validation_df = pd.DataFrame(test_data)
    
    print("=" * 60)
    print("TESTING BUNDLE GENERATION")
    print("=" * 60)
    print(f"Test validation rule: {validation_df.to_dict('records')}")
    
    # Generate bundle
    output_dir = os.path.join(os.getcwd(), "test_validation_bundle")
    try:
        bundle_path, validator_path, num_functions = generate_validation_bundle_from_dataframe(
            validation_df, 
            "TestOrg", 
            "Account", 
            output_dir
        )
        
        print(f"\nBundle generation result:")
        print(f"  Bundle path: {bundle_path}")
        print(f"  Validator path: {validator_path}")
        print(f"  Number of functions: {num_functions}")
        
        if bundle_path and os.path.exists(bundle_path):
            print(f"\n✅ Bundle file created successfully")
            
            # Read and analyze the bundle content
            with open(bundle_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            print(f"Bundle file size: {len(content)} characters")
            
            # Check for required functions
            has_validate_record = "def validate_record" in content
            has_validate_dataframe = "def validate_dataframe" in content
            has_individual_function = "def validate_Name_Not_Empty" in content
            has_helper_functions = "_is_blank" in content
            
            print(f"\nBundle content analysis:")
            print(f"  ✅ Individual validation function: {has_individual_function}")
            print(f"  ✅ Helper functions (_is_blank): {has_helper_functions}")
            print(f"  ✅ validate_record function: {has_validate_record}")
            print(f"  ✅ validate_dataframe function: {has_validate_dataframe}")
            
            if has_validate_record and has_validate_dataframe:
                print(f"\n🎉 Bundle generation SUCCESS - all required functions present")
                
                # Test the bundle with sample data
                test_validation_functionality(bundle_path)
                
            else:
                print(f"\n❌ Bundle generation FAILED - missing required functions")
                print(f"Bundle content (last 500 chars):")
                print(content[-500:])
                
        else:
            print(f"\n❌ Bundle file not created or not found")
            
    except Exception as e:
        print(f"\n❌ Bundle generation failed with error: {e}")
        import traceback
        traceback.print_exc()

def test_validation_functionality(bundle_path):
    """Test that the generated bundle actually works for validation"""
    
    print(f"\n" + "=" * 60)
    print("TESTING BUNDLE FUNCTIONALITY")
    print("=" * 60)
    
    try:
        # Import the bundle dynamically
        import importlib.util
        spec = importlib.util.spec_from_file_location("test_bundle", bundle_path)
        bundle_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bundle_module)
        
        # Create test data with blank and non-blank names
        test_data = pd.DataFrame({
            'Name': ['John Doe', '', 'Jane Smith', None, 'Bob Wilson'],
            'Id': ['001', '002', '003', '004', '005']
        })
        
        print(f"Test data:")
        print(test_data)
        print(f"\nExpected results for ISBLANK(Name) validation:")
        print(f"  John Doe: VALID (has name)")
        print(f"  '' (empty): INVALID (blank name)")
        print(f"  Jane Smith: VALID (has name)")
        print(f"  None: INVALID (null name)")
        print(f"  Bob Wilson: VALID (has name)")
        
        # Test validate_dataframe function
        if hasattr(bundle_module, 'validate_dataframe'):
            print(f"\n🔄 Running validation...")
            valid_df, invalid_df, validation_results = bundle_module.validate_dataframe(test_data)
            
            print(f"\nValidation Results:")
            print(f"  Total records: {len(test_data)}")
            print(f"  Valid records: {len(valid_df)}")
            print(f"  Invalid records: {len(invalid_df)}")
            
            print(f"\nValid records:")
            if len(valid_df) > 0:
                print(valid_df[['Name', 'Id']].to_string(index=False))
            else:
                print("  None")
                
            print(f"\nInvalid records:")
            if len(invalid_df) > 0:
                print(invalid_df[['Name', 'Id']].to_string(index=False))
            else:
                print("  None")
            
            # Check if results are correct
            expected_invalid_count = 2  # Empty string and None
            expected_valid_count = 3    # John Doe, Jane Smith, Bob Wilson
            
            if len(invalid_df) == expected_invalid_count and len(valid_df) == expected_valid_count:
                print(f"\n🎉 VALIDATION TEST PASSED - Results are correct!")
            else:
                print(f"\n❌ VALIDATION TEST FAILED - Results are incorrect!")
                print(f"  Expected: {expected_valid_count} valid, {expected_invalid_count} invalid")
                print(f"  Actual: {len(valid_df)} valid, {len(invalid_df)} invalid")
                
                # Show detailed validation results
                print(f"\nDetailed validation results:")
                for result in validation_results:
                    name_value = test_data.iloc[result['index']]['Name']
                    print(f"  Row {result['index']} (Name='{name_value}'): is_valid={result['is_valid']}, errors={result['errors']}")
        else:
            print(f"\n❌ validate_dataframe function not found in bundle")
            
    except Exception as e:
        print(f"\n❌ Bundle functionality test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_bundle_generation()