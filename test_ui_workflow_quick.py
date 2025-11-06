"""
Quick test to verify the complete Step 2 → Step 3 UI workflow works without errors
"""
import sys
import os
import pandas as pd

# Add project root to sys.path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)

from validation_script.GenAI_Validation import generate_validation_bundle_from_dataframe

def test_complete_ui_workflow():
    """Test the complete UI workflow to ensure no errors"""
    print("=" * 60)
    print("TESTING COMPLETE UI WORKFLOW (STEP 2 → STEP 3)")
    print("=" * 60)
    
    # Simulate validation rules from Step 1
    validation_rules_df = pd.DataFrame([{
        'ValidationName': 'Name_Required', 
        'ErrorConditionFormula': 'ISBLANK(Name)',
        'FieldName': 'Name',
        'ObjectName': 'Account', 
        'Active': True
    }])
    
    print("Step 1 - Validation rules extracted:")
    print(f"  Rule: {validation_rules_df.iloc[0]['ValidationName']}")
    print(f"  Formula: {validation_rules_df.iloc[0]['ErrorConditionFormula']}")
    
    # STEP 2: Bundle Generation (Fixed UI Code)
    print("\nStep 2 - AI Bundle Generation:")
    try:
        bundle_path, validator_path, num_functions = generate_validation_bundle_from_dataframe(
            validation_df=validation_rules_df,
            selected_org='TestOrg',
            object_name='Account'
        )
        
        ai_bundle_result = {
            'success': True,
            'bundle_path': bundle_path,
            'validator_path': validator_path,
            'num_functions': num_functions,
            'function_mappings': []
        }
        
        print(f"  ✅ Bundle generated: {num_functions} functions")
        print(f"  📂 Path: {bundle_path}")
        
    except Exception as e:
        print(f"  ❌ Bundle generation failed: {e}")
        return False
    
    # STEP 3: Data Validation (Fixed UI Code)
    print("\nStep 3 - Data Validation:")
    
    # Simulate uploaded CSV data with field mapping applied
    mapped_data = pd.DataFrame({
        'Name': ['Alice', '', 'Bob', None, 'Carol'],
        'Id': ['001', '002', '003', '004', '005']
    })
    
    print(f"  📊 Test data: {len(mapped_data)} records")
    print(f"  Expected: 3 valid (Alice, Bob, Carol), 2 invalid (empty, None)")
    
    # Test the fixed validation check logic
    function_mappings = ai_bundle_result.get('function_mappings', [])
    bundle_path = ai_bundle_result.get('bundle_path')
    num_functions = ai_bundle_result.get('num_functions', 0)
    
    # NEW LOGIC (fixed)
    if not function_mappings and num_functions == 0:
        print("  ❌ No validation functions found in AI bundle")
        return False
    
    if not bundle_path or not os.path.exists(bundle_path):
        print("  ❌ AI bundle file not found")
        return False
        
    print("  ✅ Validation checks passed")
    
    # Test bundle execution
    try:
        import importlib.util
        
        if 'validation_bundle' in sys.modules:
            del sys.modules['validation_bundle']
        
        spec = importlib.util.spec_from_file_location("validation_bundle", bundle_path)
        validation_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(validation_module)
        
        if not hasattr(validation_module, 'validate_dataframe'):
            print("  ❌ Bundle missing validate_dataframe function")
            return False
        
        result = validation_module.validate_dataframe(mapped_data)
        
        if isinstance(result, tuple) and len(result) == 3:
            valid_df, invalid_df, validation_results = result
            
            print(f"  ✅ Validation completed")
            print(f"    Valid records: {len(valid_df)}")
            print(f"    Invalid records: {len(invalid_df)}")
            
            # Check results
            if len(valid_df) == 3 and len(invalid_df) == 2:
                print("  🎉 Results are correct!")
                return True
            else:
                print(f"  ❌ Results incorrect - Expected: 3 valid, 2 invalid")
                return False
        else:
            print(f"  ❌ Unexpected result format: {type(result)}")
            return False
            
    except Exception as e:
        print(f"  ❌ Validation execution failed: {e}")
        return False

if __name__ == "__main__":
    success = test_complete_ui_workflow()
    
    if success:
        print("\n🎉 COMPLETE UI WORKFLOW TEST PASSED!")
        print("✅ Step 2 → Step 3 integration working correctly")
        print("✅ No more 'No validation functions found' error")
        print("✅ Validation results are accurate")
    else:
        print("\n❌ UI workflow test failed - needs investigation")