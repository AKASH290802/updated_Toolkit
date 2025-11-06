"""
Test the complete GenAI validation workflow from Step 2 to Step 3
to verify data validation is working correctly
"""
import sys
import os
import pandas as pd
import importlib.util

# Add project root to sys.path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)

from validation_script.GenAI_Validation import generate_validation_bundle_from_dataframe

def test_step2_to_step3_workflow():
    """Test the complete GenAI validation workflow"""
    print("=" * 80)
    print("TESTING COMPLETE GENAI VALIDATION WORKFLOW (STEP 2 → STEP 3)")
    print("=" * 80)
    
    # Step 1: Simulate validation rules extraction (like from Step 1)
    validation_rules = [
        {
            'ValidationName': 'Name_Not_Empty',
            'ErrorConditionFormula': 'ISBLANK(Name)',
            'FieldName': 'Name',
            'ObjectName': 'Account',
            'Active': True
        },
        {
            'ValidationName': 'Phone_Required',
            'ErrorConditionFormula': 'ISBLANK(Phone)',
            'FieldName': 'Phone',
            'ObjectName': 'Account',
            'Active': True
        }
    ]
    
    print(f"Step 1 - Validation rules to test: {len(validation_rules)}")
    for rule in validation_rules:
        print(f"  • {rule['ValidationName']}: {rule['ErrorConditionFormula']}")
    
    # Step 2: Generate validation bundle (simulating AI bundle generation)
    print("\n" + "="*50)
    print("STEP 2: GENERATING VALIDATION BUNDLE")
    print("="*50)
    
    # Create test validation rules DataFrame
    validation_df = pd.DataFrame(validation_rules)
    
    try:
        bundle_path, validator_path, num_functions = generate_validation_bundle_from_dataframe(
            validation_df=validation_df,
            selected_org='TestOrg',  # Add required parameter
            object_name='Account'
        )
        
        ai_bundle_result = {
            'success': True,
            'bundle_path': bundle_path,
            'validator_path': validator_path,
            'num_functions': num_functions
        }
        
        print(f"✅ Bundle generation result: bundle_path={bundle_path}, num_functions={num_functions}")
        
        if not ai_bundle_result.get('success', False):
            print(f"❌ Bundle generation failed: {ai_bundle_result.get('error', 'Unknown error')}")
            return False
        
        bundle_path = ai_bundle_result.get('bundle_path')
        print(f"📂 Bundle file: {bundle_path}")
        
        if bundle_path and os.path.exists(bundle_path):
            bundle_size = os.path.getsize(bundle_path)
            print(f"📊 Bundle size: {bundle_size} bytes")
        else:
            print(f"❌ Bundle file not found: {bundle_path}")
            return False
            
    except Exception as e:
        print(f"❌ Error generating bundle: {e}")
        return False
    
    # Step 3: Test validation on sample data
    print("\n" + "="*50)
    print("STEP 3: TESTING DATA VALIDATION")
    print("="*50)
    
    # Create test data (simulating uploaded CSV)
    test_data = pd.DataFrame({
        'Name': ['John Doe', '', 'Jane Smith', None, 'Bob Wilson'],
        'Phone': ['123-456-7890', '987-654-3210', '', None, '555-123-4567'],
        'Id': ['001', '002', '003', '004', '005']
    })
    
    print("Test data:")
    print(test_data)
    print("\nExpected results:")
    print("  Row 0 (John Doe, 123-456-7890): VALID (both fields have values)")
    print("  Row 1 ('', 987-654-3210): INVALID (name is blank)")
    print("  Row 2 (Jane Smith, ''): INVALID (phone is blank)")
    print("  Row 3 (None, None): INVALID (both fields are null)")
    print("  Row 4 (Bob Wilson, 555-123-4567): VALID (both fields have values)")
    print("  Expected: 2 valid, 3 invalid")
    
    # Import and use the validation bundle (simulating Step 3 logic)
    try:
        # Clean up any existing module to avoid conflicts
        if 'validation_bundle' in sys.modules:
            del sys.modules['validation_bundle']
        
        spec = importlib.util.spec_from_file_location("validation_bundle", bundle_path)
        validation_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(validation_module)
        
        # Check what functions are available
        available_functions = [name for name in dir(validation_module) if callable(getattr(validation_module, name)) and not name.startswith('_')]
        print(f"\n🔍 Bundle contains {len(available_functions)} functions: {', '.join(available_functions)}")
        
        # Check for required functions
        has_validate_dataframe = hasattr(validation_module, 'validate_dataframe')
        has_validate_record = hasattr(validation_module, 'validate_record')
        print(f"🔍 validate_dataframe={has_validate_dataframe}, validate_record={has_validate_record}")
        
        if not has_validate_dataframe:
            print("❌ validate_dataframe function missing from bundle")
            return False
        
        # Run validation using the bundle
        print("\n🔄 Running validation...")
        result = validation_module.validate_dataframe(test_data)
        
        if isinstance(result, tuple) and len(result) == 3:
            valid_df, invalid_df, validation_results = result
            print("✅ Using new bundle format with tuple return")
        else:
            print("❌ Bundle returned unexpected format")
            print(f"Result type: {type(result)}")
            print(f"Result: {result}")
            return False
        
        # Analyze results
        print(f"\nValidation Results:")
        print(f"  Total records: {len(test_data)}")
        print(f"  Valid records: {len(valid_df)}")
        print(f"  Invalid records: {len(invalid_df)}")
        
        print(f"\nValid records:")
        if len(valid_df) > 0:
            print(valid_df[['Name', 'Phone', 'Id']].to_string(index=False))
        else:
            print("  None")
        
        print(f"\nInvalid records:")
        if len(invalid_df) > 0:
            print(invalid_df[['Name', 'Phone', 'Id']].to_string(index=False))
        else:
            print("  None")
        
        # Detailed validation results
        print(f"\nDetailed validation results:")
        for i, result in enumerate(validation_results):
            record_data = test_data.iloc[i]
            print(f"  Row {i} (Name='{record_data['Name']}', Phone='{record_data['Phone']}'): "
                  f"is_valid={result['is_valid']}, errors={result['errors']}")
        
        # Check if results match expectations
        expected_valid = 2
        expected_invalid = 3
        actual_valid = len(valid_df)
        actual_invalid = len(invalid_df)
        
        if actual_valid == expected_valid and actual_invalid == expected_invalid:
            print("\n🎉 VALIDATION TEST PASSED - Results are correct!")
            return True
        else:
            print(f"\n❌ VALIDATION TEST FAILED - Results are incorrect!")
            print(f"  Expected: {expected_valid} valid, {expected_invalid} invalid")
            print(f"  Actual: {actual_valid} valid, {actual_invalid} invalid")
            return False
            
    except Exception as e:
        print(f"❌ Error during validation: {e}")
        import traceback
        traceback.print_exc()
        return False

def simulate_step3_with_field_mapping():
    """Simulate Step 3 with field mapping like in the UI"""
    print("\n" + "="*80)
    print("TESTING STEP 3 WITH FIELD MAPPING (UI SIMULATION)")
    print("="*80)
    
    # Simulate CSV data with different column names
    csv_data = pd.DataFrame({
        'Customer_Name': ['John Doe', '', 'Jane Smith', None, 'Bob Wilson'],
        'Contact_Phone': ['123-456-7890', '987-654-3210', '', None, '555-123-4567'],
        'Record_ID': ['001', '002', '003', '004', '005']
    })
    
    print("Original CSV data (with CSV column names):")
    print(csv_data)
    
    # Simulate field mapping (CSV columns → Salesforce fields)
    field_mappings = {
        'Customer_Name': 'Name',
        'Contact_Phone': 'Phone',
        'Record_ID': 'Id'
    }
    
    print(f"\nField mappings: {field_mappings}")
    
    # Apply field mapping (like in Step 3)
    mapped_df = csv_data.copy()
    for csv_col, sf_field in field_mappings.items():
        if csv_col != sf_field:
            mapped_df[sf_field] = mapped_df[csv_col]
    
    print("\nMapped data (with Salesforce field names):")
    mapped_columns = list(field_mappings.values())
    print(mapped_df[mapped_columns])
    
    # Now test validation on mapped data
    # (This would use the same bundle from the previous test)
    print("\n🔄 Testing validation on mapped data...")
    
    # Get the bundle path from the previous test
    validation_rules = [
        {
            'ValidationName': 'Name_Not_Empty',
            'ErrorConditionFormula': 'ISBLANK(Name)',
            'FieldName': 'Name',
            'ObjectName': 'Account',
            'Active': True
        }
    ]
    
    validation_df = pd.DataFrame(validation_rules)
    bundle_path, validator_path, num_functions = generate_validation_bundle_from_dataframe(
        validation_df=validation_df,
        selected_org='TestOrg',  # Add required parameter
        object_name='Account'
    )
    
    ai_bundle_result = {
        'success': True,
        'bundle_path': bundle_path,
        'validator_path': validator_path,
        'num_functions': num_functions
    }
    
    bundle_path = ai_bundle_result.get('bundle_path')
    
    try:
        # Import the validation bundle
        if 'validation_bundle' in sys.modules:
            del sys.modules['validation_bundle']
        
        spec = importlib.util.spec_from_file_location("validation_bundle", bundle_path)
        validation_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(validation_module)
        
        # Run validation on mapped data
        result = validation_module.validate_dataframe(mapped_df[mapped_columns])
        
        if isinstance(result, tuple) and len(result) == 3:
            valid_df, invalid_df, validation_results = result
            
            print(f"Results with field mapping:")
            print(f"  Valid records: {len(valid_df)}")
            print(f"  Invalid records: {len(invalid_df)}")
            
            # Check if mapping affected the results
            if len(valid_df) == 3 and len(invalid_df) == 2:  # Expected for name validation only
                print("✅ Field mapping validation successful!")
            else:
                print("❌ Field mapping validation failed!")
                print(f"Expected: 3 valid, 2 invalid (name validation only)")
                print(f"Actual: {len(valid_df)} valid, {len(invalid_df)} invalid")
        
    except Exception as e:
        print(f"❌ Error during field mapping validation: {e}")

if __name__ == "__main__":
    success = test_step2_to_step3_workflow()
    
    if success:
        simulate_step3_with_field_mapping()
    else:
        print("\n❌ Step 2 to Step 3 workflow failed, skipping field mapping test")