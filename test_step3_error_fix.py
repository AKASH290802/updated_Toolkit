"""
Test the Step 3 UI fix for the 'No validation functions found in AI bundle' error
"""
import sys
import os
import pandas as pd

# Add project root to sys.path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)

from validation_script.GenAI_Validation import generate_validation_bundle_from_dataframe

def test_ai_bundle_result_format():
    """Test that the AI bundle result format works with Step 3 validation"""
    print("=" * 80)
    print("TESTING AI BUNDLE RESULT FORMAT FOR STEP 3")
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
    
    # Step 2: Generate bundle (simulating Step 2 UI)
    print("\n" + "="*50)
    print("STEP 2: GENERATING BUNDLE WITH NEW FORMAT")
    print("="*50)
    
    try:
        bundle_path, validator_path, num_functions = generate_validation_bundle_from_dataframe(
            validation_df=validation_df,
            selected_org='TestOrg',
            object_name='Account'
        )
        
        # Create the same bundle_result format as Step 2 UI
        ai_bundle_result = {
            'success': True,
            'bundle_path': bundle_path,
            'validator_path': validator_path,
            'num_functions': num_functions,
            'function_mappings': []  # Empty as in the fixed Step 2 code
        }
        
        print(f"✅ Bundle generated successfully")
        print(f"📂 Bundle path: {bundle_path}")
        print(f"📊 Number of functions: {num_functions}")
        print(f"📋 Function mappings: {ai_bundle_result['function_mappings']}")
        
    except Exception as e:
        print(f"❌ Bundle generation failed: {e}")
        return False
    
    # Step 3: Test the validation check logic (simulating Step 3 UI)
    print("\n" + "="*50)
    print("STEP 3: TESTING VALIDATION CHECK LOGIC")
    print("="*50)
    
    # Simulate the check from run_genai_validation_on_data
    function_mappings = ai_bundle_result.get('function_mappings', [])
    bundle_path = ai_bundle_result.get('bundle_path')
    num_functions = ai_bundle_result.get('num_functions', 0)
    
    print(f"function_mappings: {function_mappings} (length: {len(function_mappings)})")
    print(f"num_functions: {num_functions}")
    print(f"bundle_path exists: {os.path.exists(bundle_path) if bundle_path else False}")
    
    # Test the NEW validation logic (fixed)
    if not function_mappings and num_functions == 0:
        print("❌ NEW LOGIC: No validation functions found in AI bundle")
        return False
    else:
        print("✅ NEW LOGIC: Validation functions found in AI bundle")
    
    # Test the OLD validation logic (would fail)
    if not function_mappings:
        print("❌ OLD LOGIC: Would fail with 'No validation functions found in AI bundle'")
    else:
        print("✅ OLD LOGIC: Would pass")
    
    if not bundle_path or not os.path.exists(bundle_path):
        print("❌ Bundle file check failed")
        return False
    else:
        print("✅ Bundle file exists and is accessible")
    
    # Step 4: Test actual validation (if everything passes)
    print("\n" + "="*50)
    print("STEP 4: TESTING ACTUAL VALIDATION")
    print("="*50)
    
    # Create test data
    test_data = pd.DataFrame({
        'Name': ['John Doe', '', 'Jane Smith'],
        'Id': ['001', '002', '003']
    })
    
    print("Test data:")
    print(test_data)
    
    # Import and test the bundle directly
    try:
        import importlib.util
        
        if 'validation_bundle' in sys.modules:
            del sys.modules['validation_bundle']
        
        spec = importlib.util.spec_from_file_location("validation_bundle", bundle_path)
        validation_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(validation_module)
        
        # Check that validation functions exist
        has_validate_dataframe = hasattr(validation_module, 'validate_dataframe')
        has_validate_record = hasattr(validation_module, 'validate_record')
        
        print(f"Bundle contains validate_dataframe: {has_validate_dataframe}")
        print(f"Bundle contains validate_record: {has_validate_record}")
        
        if not has_validate_dataframe:
            print("❌ Bundle missing validate_dataframe function")
            return False
        
        # Run validation
        result = validation_module.validate_dataframe(test_data)
        
        if isinstance(result, tuple) and len(result) == 3:
            valid_df, invalid_df, validation_results = result
            
            print(f"✅ Validation executed successfully")
            print(f"  Valid records: {len(valid_df)}")
            print(f"  Invalid records: {len(invalid_df)}")
            
            # Expected: John Doe and Jane Smith valid, empty string invalid
            if len(valid_df) == 2 and len(invalid_df) == 1:
                print("🎉 VALIDATION RESULTS CORRECT!")
                return True
            else:
                print(f"❌ Validation results incorrect. Expected: 2 valid, 1 invalid")
                return False
        else:
            print(f"❌ Bundle returned unexpected format: {type(result)}")
            return False
            
    except Exception as e:
        print(f"❌ Error during validation test: {e}")
        import traceback
        traceback.print_exc()
        return False

def simulate_step3_error_scenario():
    """Simulate the specific error scenario that was occurring"""
    print("\n" + "=" * 80)
    print("SIMULATING ORIGINAL STEP 3 ERROR SCENARIO")
    print("=" * 80)
    
    # Simulate old bundle result format (before fix)
    old_bundle_result = {
        'success': True,
        'bundle_path': 'some/path/bundle.py',
        'function_mappings': []  # Empty, which caused the error
        # Note: num_functions field was missing
    }
    
    print("Old bundle result format:")
    print(f"  function_mappings: {old_bundle_result.get('function_mappings', [])}")
    print(f"  num_functions: {old_bundle_result.get('num_functions', 'MISSING')}")
    
    # Test old validation logic
    function_mappings = old_bundle_result.get('function_mappings', [])
    
    if not function_mappings:
        print("❌ OLD LOGIC: 'No validation functions found in AI bundle' - This was the error!")
    
    # Test new validation logic  
    num_functions = old_bundle_result.get('num_functions', 0)
    
    if not function_mappings and num_functions == 0:
        print("❌ NEW LOGIC: Would still fail for old bundle format (expected)")
    
    # Simulate new bundle result format (after fix)
    new_bundle_result = {
        'success': True,
        'bundle_path': 'some/path/bundle.py',
        'function_mappings': [],  # Still empty
        'num_functions': 1  # But now we have this field!
    }
    
    print("\nNew bundle result format:")
    print(f"  function_mappings: {new_bundle_result.get('function_mappings', [])}")
    print(f"  num_functions: {new_bundle_result.get('num_functions', 'MISSING')}")
    
    # Test new validation logic with new format
    function_mappings = new_bundle_result.get('function_mappings', [])
    num_functions = new_bundle_result.get('num_functions', 0)
    
    if not function_mappings and num_functions == 0:
        print("❌ NEW LOGIC: Would fail")
    else:
        print("✅ NEW LOGIC: Passes! num_functions > 0 allows validation to proceed")

if __name__ == "__main__":
    print("Testing the Step 3 'No validation functions found' fix...\n")
    
    success = test_ai_bundle_result_format()
    
    if success:
        print("\n🎉 STEP 3 FIX SUCCESSFUL - No more 'No validation functions found' error!")
    else:
        print("\n❌ Step 3 fix needs more work")
    
    # Show the before/after scenario
    simulate_step3_error_scenario()