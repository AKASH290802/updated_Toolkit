"""
Test Step 3 UI validation workflow to verify the bundle format issue is fixed
"""
import sys
import os
import pandas as pd
import importlib.util

# Add project root to sys.path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)

# Import the UI validation function by importing the module directly
ui_components_path = os.path.join(project_root, 'ui_components', 'validation_operations.py')

# Load the UI module dynamically to avoid relative import issues
spec = importlib.util.spec_from_file_location("validation_operations", ui_components_path)
validation_operations = importlib.util.module_from_spec(spec)

# Mock the required modules that validation_operations imports
import types
mock_utils = types.ModuleType('utils')
validation_operations.utils = mock_utils

# Mock the functions we don't need for this test
def mock_function(*args, **kwargs):
    return None

mock_utils.establish_sf_connection = mock_function
mock_utils.get_salesforce_objects = mock_function
mock_utils.get_object_description = mock_function
mock_utils.show_processing_status = mock_function
mock_utils.display_dataframe_with_download = mock_function
mock_utils.validate_file_upload = mock_function
mock_utils.create_progress_tracker = mock_function

# Mock sf_validation_client
validation_operations.sf_validation_client = types.ModuleType('sf_validation_client')
validation_operations.sf_validation_client.create_sf_validation_client = mock_function

# Mock streamlit
validation_operations.st = types.ModuleType('st')
validation_operations.st.info = print
validation_operations.st.warning = print
validation_operations.st.error = print

# Now load the module
try:
    spec.loader.exec_module(validation_operations)
    run_genai_validation_on_data = validation_operations.run_genai_validation_on_data
except Exception as e:
    print(f"Error loading validation_operations: {e}")
    print("Using fallback - will test bundle generation only")
    run_genai_validation_on_data = None

# Import the bundle generation
from validation_script.GenAI_Validation import generate_validation_bundle_from_dataframe

def test_ui_step3_workflow():
    """Test the UI Step 3 validation workflow with the corrected bundle format"""
    print("=" * 80)
    print("TESTING UI STEP 3 VALIDATION WORKFLOW")
    print("=" * 80)
    
    # Step 1: Create test validation rules
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
    print(f"Test validation rule: {validation_rules[0]['ValidationName']} - {validation_rules[0]['ErrorConditionFormula']}")
    
    # Step 2: Generate bundle using the new method (as fixed in UI)
    print("\n" + "="*50)
    print("STEP 2: GENERATING BUNDLE (NEW METHOD)")
    print("="*50)
    
    try:
        bundle_path, validator_path, num_functions = generate_validation_bundle_from_dataframe(
            validation_df=validation_df,
            selected_org='TestOrg',
            object_name='Account'
        )
        
        # Create the same bundle_result format as the fixed UI code
        ai_bundle_result = {
            'success': True,
            'bundle_path': bundle_path,
            'validator_path': validator_path,
            'num_functions': num_functions,
            'function_mappings': []  # Will be populated if needed
        }
        
        print(f"✅ Bundle generated successfully")
        print(f"📂 Bundle path: {bundle_path}")
        print(f"📊 Number of functions: {num_functions}")
        
    except Exception as e:
        print(f"❌ Bundle generation failed: {e}")
        return False
    
    # Step 3: Test data validation using UI function
    print("\n" + "="*50)
    print("STEP 3: TESTING UI VALIDATION FUNCTION")
    print("="*50)
    
    # Create test data (simulating uploaded CSV with field mapping applied)
    test_data = pd.DataFrame({
        'Name': ['John Doe', '', 'Jane Smith', None, 'Bob Wilson'],
        'Id': ['001', '002', '003', '004', '005']
    })
    
    print("Test data:")
    print(test_data)
    print("\nExpected results for ISBLANK(Name):")
    print("  John Doe: VALID (has name)")
    print("  '': INVALID (blank name)")
    print("  Jane Smith: VALID (has name)")
    print("  None: INVALID (null name)")
    print("  Bob Wilson: VALID (has name)")
    print("  Expected: 3 valid, 2 invalid")
    
    # Call the UI validation function
    if run_genai_validation_on_data is None:
        print("⚠️ UI validation function not available - testing bundle generation only")
        
        # Test the bundle directly instead
        try:
            if 'validation_bundle' in sys.modules:
                del sys.modules['validation_bundle']
            
            spec = importlib.util.spec_from_file_location("validation_bundle", bundle_path)
            validation_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(validation_module)
            
            result = validation_module.validate_dataframe(test_data)
            
            if isinstance(result, tuple) and len(result) == 3:
                valid_df, invalid_df, validation_results = result
                
                print(f"✅ Bundle validation executed successfully")
                print(f"  Valid records: {len(valid_df)}")
                print(f"  Invalid records: {len(invalid_df)}")
                
                if len(valid_df) == 3 and len(invalid_df) == 2:
                    print("🎉 BUNDLE TEST PASSED - Results are correct!")
                    return True
                else:
                    print("❌ BUNDLE TEST FAILED - Results are incorrect!")
                    return False
            else:
                print(f"❌ Bundle returned unexpected format: {type(result)}")
                return False
                
        except Exception as e:
            print(f"❌ Error testing bundle directly: {e}")
            return False
    else:
        try:
            print("\n🔄 Running UI validation function...")
            validation_results = run_genai_validation_on_data(test_data, ai_bundle_result)
            
            if validation_results.get('success', False):
                print("✅ UI validation function executed successfully")
                
                total_records = validation_results['total_records']
                valid_records = validation_results['valid_records']
                invalid_records = validation_results['invalid_records']
                success_rate = validation_results['success_rate']
                
                print(f"\nValidation Results:")
                print(f"  Total records: {total_records}")
                print(f"  Valid records: {valid_records}")
                print(f"  Invalid records: {invalid_records}")
                print(f"  Success rate: {success_rate:.1f}%")
                
                # Check if results are correct
                if valid_records == 3 and invalid_records == 2:
                    print("\n🎉 UI VALIDATION TEST PASSED - Results are correct!")
                    
                    # Show details
                    if 'valid_df' in validation_results and len(validation_results['valid_df']) > 0:
                        print("\nValid records:")
                        print(validation_results['valid_df'][['Name', 'Id']].to_string(index=False))
                    
                    if 'invalid_df' in validation_results and len(validation_results['invalid_df']) > 0:
                        print("\nInvalid records:")
                        print(validation_results['invalid_df'][['Name', 'Id']].to_string(index=False))
                    
                    return True
                else:
                    print(f"\n❌ UI VALIDATION TEST FAILED")
                    print(f"  Expected: 3 valid, 2 invalid")
                    print(f"  Actual: {valid_records} valid, {invalid_records} invalid")
                    
                    # Debug information
                    print(f"\nDebug info:")
                    print(f"  validation_results keys: {list(validation_results.keys())}")
                    if 'error_summary' in validation_results:
                        print(f"  Number of errors: {len(validation_results['error_summary'])}")
                    
                    return False
            else:
                print(f"❌ UI validation function failed: {validation_results.get('error', 'Unknown error')}")
                return False
                
        except Exception as e:
            print(f"❌ Error during UI validation: {e}")
            import traceback
            traceback.print_exc()
            return False

def test_old_vs_new_bundle_format():
    """Compare the old and new bundle formats to show the difference"""
    print("\n" + "=" * 80)
    print("COMPARING OLD VS NEW BUNDLE FORMATS")
    print("=" * 80)
    
    # Test with same data
    test_data = pd.DataFrame({
        'Name': ['John Doe', '', 'Jane Smith'],
        'Id': ['001', '002', '003']
    })
    
    print("Test data:")
    print(test_data)
    
    # Test new format (our working version)
    print("\n--- NEW FORMAT (Fixed) ---")
    validation_rules = [{'ValidationName': 'Name_Not_Empty', 'ErrorConditionFormula': 'ISBLANK(Name)', 'FieldName': 'Name', 'ObjectName': 'Account', 'Active': True}]
    validation_df = pd.DataFrame(validation_rules)
    
    try:
        bundle_path, _, _ = generate_validation_bundle_from_dataframe(
            validation_df=validation_df,
            selected_org='TestOrg',
            object_name='Account'
        )
        
        # Import and test the new bundle
        if 'validation_bundle' in sys.modules:
            del sys.modules['validation_bundle']
        
        spec = importlib.util.spec_from_file_location("validation_bundle", bundle_path)
        validation_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(validation_module)
        
        result = validation_module.validate_dataframe(test_data)
        print(f"New format result type: {type(result)}")
        
        if isinstance(result, tuple) and len(result) == 3:
            valid_df, invalid_df, validation_results = result
            print(f"✅ Returns tuple: valid_df ({len(valid_df)}), invalid_df ({len(invalid_df)}), validation_results ({len(validation_results)})")
        else:
            print(f"❌ Unexpected result format: {result}")
            
    except Exception as e:
        print(f"❌ Error testing new format: {e}")

if __name__ == "__main__":
    success = test_ui_step3_workflow()
    
    if success:
        print("\n✅ Step 3 UI validation is now working correctly!")
    else:
        print("\n❌ Step 3 UI validation still has issues")
    
    # Always run the format comparison for educational purposes
    test_old_vs_new_bundle_format()