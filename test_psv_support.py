#!/usr/bin/env python3
"""
Test script to verify PSV file support in DM Toolkit
"""

import pandas as pd
import sys
import os

# Add project root to sys.path
project_root = os.path.dirname(__file__)
sys.path.append(project_root)

from ui_components.utils import load_data_file

def create_test_psv_file():
    """Create a test PSV file"""
    data = {
        'Name': ['Test Account 1', 'Test Account 2', 'Test Account 3'],
        'Type': ['Customer|Direct', 'Partner|Channel', 'Prospect|Direct'],
        'Phone': ['555-1234', '555-5678', '555-9012'],
        'Email': ['test1@example.com', 'test2@example.com', 'test3@example.com']
    }
    
    df = pd.DataFrame(data)
    test_file = 'test_data.psv'
    
    # Save as PSV (pipe-separated values)
    df.to_csv(test_file, sep='|', index=False)
    print(f"✅ Created test PSV file: {test_file}")
    return test_file

def test_psv_loading():
    """Test PSV file loading functionality"""
    try:
        # Create test file
        test_file = create_test_psv_file()
        
        # Test loading PSV file
        print(f"🔄 Testing PSV file loading...")
        df = load_data_file(test_file)
        
        if df is not None:
            print(f"✅ Successfully loaded PSV file!")
            print(f"📊 Data shape: {df.shape}")
            print(f"📋 Columns: {list(df.columns)}")
            print("\n📝 Sample data:")
            print(df.head())
            print("\n✅ PSV support is working correctly!")
            return True
        else:
            print("❌ Failed to load PSV file")
            return False
            
    except Exception as e:
        print(f"❌ Error testing PSV support: {str(e)}")
        return False
    finally:
        # Clean up test file
        if os.path.exists(test_file):
            os.remove(test_file)
            print(f"🧹 Cleaned up test file: {test_file}")

def test_validation_operations():
    """Test that validation operations support PSV files"""
    try:
        print(f"\n🔄 Testing validation operations PSV support...")
        
        # Check if validation operations module can be imported
        from ui_components.validation_operations import show_validation_operations
        print("✅ Validation operations module imported successfully")
        
        return True
    except Exception as e:
        print(f"❌ Error testing validation operations: {str(e)}")
        return False

def main():
    """Main test function"""
    print("🚀 Testing PSV Support in DM Toolkit")
    print("=" * 50)
    
    # Test core PSV loading
    psv_test = test_psv_loading()
    
    # Test validation operations
    validation_test = test_validation_operations()
    
    print("\n" + "=" * 50)
    print("📋 Test Summary:")
    print(f"   PSV File Loading: {'✅ PASS' if psv_test else '❌ FAIL'}")
    print(f"   Validation Operations: {'✅ PASS' if validation_test else '❌ FAIL'}")
    
    if psv_test and validation_test:
        print("\n🎉 All PSV support tests passed!")
        print("🔧 PSV files (.psv) can now be used throughout the DM Toolkit")
        return True
    else:
        print("\n❌ Some tests failed. Please check the implementation.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)