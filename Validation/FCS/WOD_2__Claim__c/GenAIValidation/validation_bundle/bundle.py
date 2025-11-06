# Auto-generated validation bundle
import pandas as pd
import numpy as np
from typing import List, Dict


def _is_blank(value):
    """Salesforce ISBLANK function"""
    if hasattr(value, 'isna'):
        return value.isna() | (value == '')
    return pd.isna(value) or value == ''

def _is_null(value):
    """Salesforce ISNULL function"""
    if hasattr(value, 'isna'):
        return value.isna()
    return pd.isna(value)

def _to_number(value):
    """Salesforce VALUE function"""
    if hasattr(value, 'astype'):
        return pd.to_numeric(value, errors='coerce')
    try:
        return float(value)
    except:
        return 0

def _trim(text):
    """Salesforce TRIM function"""
    if hasattr(text, 'str'):
        return text.str.strip()
    return str(text).strip() if text else ''

def _left(text, num_chars):
    """Salesforce LEFT function"""
    if hasattr(text, 'str'):
        return text.str[:num_chars]
    return str(text)[:num_chars] if text else ''

def _right(text, num_chars):
    """Salesforce RIGHT function"""
    if hasattr(text, 'str'):
        return text.str[-num_chars:]
    return str(text)[-num_chars:] if text else ''

def _mid(text, start_pos, num_chars):
    """Salesforce MID function"""
    if hasattr(text, 'str'):
        return text.str[start_pos-1:start_pos-1+num_chars]
    return str(text)[start_pos-1:start_pos-1+num_chars] if text else ''

def _find(search_text, text):
    """Salesforce FIND function"""
    if hasattr(text, 'str'):
        return text.str.find(search_text) + 1  # Salesforce is 1-indexed
    return str(text).find(str(search_text)) + 1 if text else 0

def _contains(text, search_text):
    """Salesforce CONTAINS function"""
    if hasattr(text, 'str'):
        return text.str.contains(search_text, na=False)
    return str(search_text) in str(text) if text else False

def _today():
    """Salesforce TODAY function"""
    from datetime import date
    return date.today()

def _now():
    """Salesforce NOW function"""
    from datetime import datetime
    return datetime.now()

def _year(date_value):
    """Salesforce YEAR function"""
    if hasattr(date_value, 'dt'):
        return date_value.dt.year
    return pd.to_datetime(date_value).year if date_value else None

def _month(date_value):
    """Salesforce MONTH function"""
    if hasattr(date_value, 'dt'):
        return date_value.dt.month
    return pd.to_datetime(date_value).month if date_value else None

def _day(date_value):
    """Salesforce DAY function"""
    if hasattr(date_value, 'dt'):
        return date_value.dt.day
    return pd.to_datetime(date_value).day if date_value else None

def _and(*conditions):
    """Salesforce AND function"""
    result = conditions[0]
    for condition in conditions[1:]:
        result = result & condition
    return result

def _or(*conditions):
    """Salesforce OR function"""
    result = conditions[0]
    for condition in conditions[1:]:
        result = result | condition
    return result

def _not(condition):
    """Salesforce NOT function"""
    return ~condition

def _if(condition, true_value, false_value):
    """Salesforce IF function"""
    if hasattr(condition, '__len__') and len(condition) > 1:
        return pd.where(condition, true_value, false_value)
    return true_value if condition else false_value

def _begins_with(text, prefix):
    """Salesforce BEGINS function"""
    if hasattr(text, 'str'):
        return text.str.startswith(prefix)
    return str(text).startswith(str(prefix)) if text else False

def _ends_with(text, suffix):
    """Salesforce ENDS function"""
    if hasattr(text, 'str'):
        return text.str.endswith(suffix)
    return str(text).endswith(str(suffix)) if text else False

def _ceiling(number):
    """Salesforce CEILING function"""
    import math
    if hasattr(number, 'apply'):
        return number.apply(math.ceil)
    return math.ceil(number) if number else 0

def _floor(number):
    """Salesforce FLOOR function"""
    import math
    if hasattr(number, 'apply'):
        return number.apply(math.floor)
    return math.floor(number) if number else 0


def validate_MC_PC_PRE_AUTH_COMMENTS_MANDATORY(df):
    """
    Validation Rule: MC_PC_PRE_AUTH_COMMENTS_MANDATORY
    Salesforce Object: WOD_2__Claim__c
    Primary Field: Id
    
    
    Original Apex Formula:
    AND(
OR(
$Permission.WOD_2__DisableSkipTriggerNValidation,
NOT($Permission.WOD_2__SkipTriggerNValidations)
),IF(AND(OR(ISPICKVAL(WOD_2__Claim_Type__c, 'Machine'),ISPICKVAL(WOD_2__Claim_Type__c, 'Part')), WOD_2__Is_Pre_Authorization_Required__c==true,ISBLANK(TRIM( 	WOD_2__Pre_Authorization_Comments__c)) ),true,false))
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results (True = valid, False = invalid)
    """
    # Primary Field: Id
    
    # Import required modules
    import pandas as pd
    import numpy as np
    from datetime import datetime, date
    import math
    
    try:
        # Ensure all required columns exist
        required_columns = []
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"Warning: Missing columns for validation rule 'MC_PC_PRE_AUTH_COMMENTS_MANDATORY': {missing_columns}")
            return pd.Series([False] * len(df))  # Mark all as invalid if columns missing
        
        # Fill NaN values to avoid errors
        df_clean = df.fillna('')
        
        # Apply validation logic
        validation_result = _and( _or( $df['Permission'].df['WOD_2__DisableSkipTriggerNValidation'], _not($df['Permission'].df['WOD_2__SkipTriggerNValidations']) ),_if(_and(_or(_ispickval(df['WOD_2__Claim_Type__c'], 'df['Machine']'),_ispickval(df['WOD_2__Claim_Type__c'], 'df['Part']')), df['WOD_2__Is_Pre_Authorization_Required__c']==true,_is_blank(_trim( df['WOD_2__Pre_Authorization_Comments__c'])) ),true,false))
        
        # Ensure result is a boolean Series
        if not isinstance(validation_result, pd.Series):
            validation_result = pd.Series([bool(validation_result)] * len(df))
        
        # Salesforce validation rules define ERROR conditions (when validation should FAIL)
        # If the formula evaluates to True = Error condition = Record is INVALID
        # If the formula evaluates to False = No error = Record is VALID
        # So we need to invert: True becomes False (invalid), False becomes True (valid)
        
        # Debug: Print sample of validation logic for troubleshooting
        if len(df) > 0:
            sample_value = validation_result.iloc[0] if hasattr(validation_result, 'iloc') else validation_result
            print(f"DEBUG - Rule 'MC_PC_PRE_AUTH_COMMENTS_MANDATORY': Formula result for first record = {sample_value} (True=Error/Invalid, False=NoError/Valid)")
            
            # Additional debugging for ISBLANK scenarios
            if '_is_blank' in str(validation_result):
                sample_field_value = df_clean.iloc[0].get('Id', 'COLUMN_NOT_FOUND') if len(df_clean) > 0 else 'NO_DATA'
                print(f"DEBUG - Rule 'MC_PC_PRE_AUTH_COMMENTS_MANDATORY': Field 'Id' value for first record = '{sample_field_value}'")
                print(f"DEBUG - Rule 'MC_PC_PRE_AUTH_COMMENTS_MANDATORY': Available columns = {list(df.columns)}")
                if 'Id' not in df.columns:
                    print(f"WARNING - Rule 'MC_PC_PRE_AUTH_COMMENTS_MANDATORY': Column 'Id' not found in data! This will cause validation to fail.")
        
        return ~validation_result
        
    except KeyError as e:
        print(f"Warning: Column {e} not found in DataFrame for validation rule 'MC_PC_PRE_AUTH_COMMENTS_MANDATORY'")
        return pd.Series([False] * len(df))  # Mark all as invalid if column missing
    except Exception as e:
        print(f"Warning: Error in validation rule 'MC_PC_PRE_AUTH_COMMENTS_MANDATORY': {e}")
        return pd.Series([False] * len(df))  # Mark all as invalid on error

def validate_MC_PC_PRE_AUTH_REASON_MANDATORY(df):
    """
    Validation Rule: MC_PC_PRE_AUTH_REASON_MANDATORY
    Salesforce Object: WOD_2__Claim__c
    Primary Field: Id
    
    
    Original Apex Formula:
    AND(
OR(
$Permission.WOD_2__DisableSkipTriggerNValidation,
NOT($Permission.WOD_2__SkipTriggerNValidations)
),IF(AND(OR(ISPICKVAL(WOD_2__Claim_Type__c, 'Machine'),ISPICKVAL(WOD_2__Claim_Type__c, 'Part')), WOD_2__Is_Pre_Authorization_Required__c==true,ISPICKVAL(WOD_2__Pre_Authorization_Reason__c,'') ),true,false))
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results (True = valid, False = invalid)
    """
    # Primary Field: Id
    
    # Import required modules
    import pandas as pd
    import numpy as np
    from datetime import datetime, date
    import math
    
    try:
        # Ensure all required columns exist
        required_columns = []
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"Warning: Missing columns for validation rule 'MC_PC_PRE_AUTH_REASON_MANDATORY': {missing_columns}")
            return pd.Series([False] * len(df))  # Mark all as invalid if columns missing
        
        # Fill NaN values to avoid errors
        df_clean = df.fillna('')
        
        # Apply validation logic
        validation_result = _is_blank(df['Id'])
        
        # Ensure result is a boolean Series
        if not isinstance(validation_result, pd.Series):
            validation_result = pd.Series([bool(validation_result)] * len(df))
        
        # Salesforce validation rules define ERROR conditions (when validation should FAIL)
        # If the formula evaluates to True = Error condition = Record is INVALID
        # If the formula evaluates to False = No error = Record is VALID
        # So we need to invert: True becomes False (invalid), False becomes True (valid)
        
        # Debug: Print sample of validation logic for troubleshooting
        if len(df) > 0:
            sample_value = validation_result.iloc[0] if hasattr(validation_result, 'iloc') else validation_result
            print(f"DEBUG - Rule 'MC_PC_PRE_AUTH_REASON_MANDATORY': Formula result for first record = {sample_value} (True=Error/Invalid, False=NoError/Valid)")
            
            # Additional debugging for ISBLANK scenarios
            if '_is_blank' in str(validation_result):
                sample_field_value = df_clean.iloc[0].get('Id', 'COLUMN_NOT_FOUND') if len(df_clean) > 0 else 'NO_DATA'
                print(f"DEBUG - Rule 'MC_PC_PRE_AUTH_REASON_MANDATORY': Field 'Id' value for first record = '{sample_field_value}'")
                print(f"DEBUG - Rule 'MC_PC_PRE_AUTH_REASON_MANDATORY': Available columns = {list(df.columns)}")
                if 'Id' not in df.columns:
                    print(f"WARNING - Rule 'MC_PC_PRE_AUTH_REASON_MANDATORY': Column 'Id' not found in data! This will cause validation to fail.")
        
        return ~validation_result
        
    except KeyError as e:
        print(f"Warning: Column {e} not found in DataFrame for validation rule 'MC_PC_PRE_AUTH_REASON_MANDATORY'")
        return pd.Series([False] * len(df))  # Mark all as invalid if column missing
    except Exception as e:
        print(f"Warning: Error in validation rule 'MC_PC_PRE_AUTH_REASON_MANDATORY': {e}")
        return pd.Series([False] * len(df))  # Mark all as invalid on error

def validate_MC_PurchaseDate_Less_REPAIRDATE_FAILURE(df):
    """
    Validation Rule: MC_PurchaseDate_Less_REPAIRDATE_FAILURE
    Salesforce Object: WOD_2__Claim__c
    Primary Field: Id
    
    
    Original Apex Formula:
    AND(
OR(
$Permission.WOD_2__DisableSkipTriggerNValidation,
NOT($Permission.WOD_2__SkipTriggerNValidations)
),IF(  OR(WOD_2__Date_Of_Purchase__c> WOD_2__Date_Of_Repair__c ,WOD_2__Date_Of_Purchase__c> WOD_2__Date_Of_Failure__c ), true, false))
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results (True = valid, False = invalid)
    """
    # Primary Field: Id
    
    # Import required modules
    import pandas as pd
    import numpy as np
    from datetime import datetime, date
    import math
    
    try:
        # Ensure all required columns exist
        required_columns = []
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"Warning: Missing columns for validation rule 'MC_PurchaseDate_Less_REPAIRDATE_FAILURE': {missing_columns}")
            return pd.Series([False] * len(df))  # Mark all as invalid if columns missing
        
        # Fill NaN values to avoid errors
        df_clean = df.fillna('')
        
        # Apply validation logic
        validation_result = _is_blank(df['Id'])
        
        # Ensure result is a boolean Series
        if not isinstance(validation_result, pd.Series):
            validation_result = pd.Series([bool(validation_result)] * len(df))
        
        # Salesforce validation rules define ERROR conditions (when validation should FAIL)
        # If the formula evaluates to True = Error condition = Record is INVALID
        # If the formula evaluates to False = No error = Record is VALID
        # So we need to invert: True becomes False (invalid), False becomes True (valid)
        
        # Debug: Print sample of validation logic for troubleshooting
        if len(df) > 0:
            sample_value = validation_result.iloc[0] if hasattr(validation_result, 'iloc') else validation_result
            print(f"DEBUG - Rule 'MC_PurchaseDate_Less_REPAIRDATE_FAILURE': Formula result for first record = {sample_value} (True=Error/Invalid, False=NoError/Valid)")
            
            # Additional debugging for ISBLANK scenarios
            if '_is_blank' in str(validation_result):
                sample_field_value = df_clean.iloc[0].get('Id', 'COLUMN_NOT_FOUND') if len(df_clean) > 0 else 'NO_DATA'
                print(f"DEBUG - Rule 'MC_PurchaseDate_Less_REPAIRDATE_FAILURE': Field 'Id' value for first record = '{sample_field_value}'")
                print(f"DEBUG - Rule 'MC_PurchaseDate_Less_REPAIRDATE_FAILURE': Available columns = {list(df.columns)}")
                if 'Id' not in df.columns:
                    print(f"WARNING - Rule 'MC_PurchaseDate_Less_REPAIRDATE_FAILURE': Column 'Id' not found in data! This will cause validation to fail.")
        
        return ~validation_result
        
    except KeyError as e:
        print(f"Warning: Column {e} not found in DataFrame for validation rule 'MC_PurchaseDate_Less_REPAIRDATE_FAILURE'")
        return pd.Series([False] * len(df))  # Mark all as invalid if column missing
    except Exception as e:
        print(f"Warning: Error in validation rule 'MC_PurchaseDate_Less_REPAIRDATE_FAILURE': {e}")
        return pd.Series([False] * len(df))  # Mark all as invalid on error

def validate_OSD_RECEIVEDATE_LESS_TODAY(df):
    """
    Validation Rule: OSD_RECEIVEDATE_LESS_TODAY
    Salesforce Object: WOD_2__Claim__c
    Primary Field: Id
    
    
    Original Apex Formula:
    AND(
OR(
$Permission.WOD_2__DisableSkipTriggerNValidation,
NOT($Permission.WOD_2__SkipTriggerNValidations)
),WOD_2__Received_Date__c > TODAY())
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results (True = valid, False = invalid)
    """
    # Primary Field: Id
    
    # Import required modules
    import pandas as pd
    import numpy as np
    from datetime import datetime, date
    import math
    
    try:
        # Ensure all required columns exist
        required_columns = []
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"Warning: Missing columns for validation rule 'OSD_RECEIVEDATE_LESS_TODAY': {missing_columns}")
            return pd.Series([False] * len(df))  # Mark all as invalid if columns missing
        
        # Fill NaN values to avoid errors
        df_clean = df.fillna('')
        
        # Apply validation logic
        validation_result = _is_blank(df['Id'])
        
        # Ensure result is a boolean Series
        if not isinstance(validation_result, pd.Series):
            validation_result = pd.Series([bool(validation_result)] * len(df))
        
        # Salesforce validation rules define ERROR conditions (when validation should FAIL)
        # If the formula evaluates to True = Error condition = Record is INVALID
        # If the formula evaluates to False = No error = Record is VALID
        # So we need to invert: True becomes False (invalid), False becomes True (valid)
        
        # Debug: Print sample of validation logic for troubleshooting
        if len(df) > 0:
            sample_value = validation_result.iloc[0] if hasattr(validation_result, 'iloc') else validation_result
            print(f"DEBUG - Rule 'OSD_RECEIVEDATE_LESS_TODAY': Formula result for first record = {sample_value} (True=Error/Invalid, False=NoError/Valid)")
            
            # Additional debugging for ISBLANK scenarios
            if '_is_blank' in str(validation_result):
                sample_field_value = df_clean.iloc[0].get('Id', 'COLUMN_NOT_FOUND') if len(df_clean) > 0 else 'NO_DATA'
                print(f"DEBUG - Rule 'OSD_RECEIVEDATE_LESS_TODAY': Field 'Id' value for first record = '{sample_field_value}'")
                print(f"DEBUG - Rule 'OSD_RECEIVEDATE_LESS_TODAY': Available columns = {list(df.columns)}")
                if 'Id' not in df.columns:
                    print(f"WARNING - Rule 'OSD_RECEIVEDATE_LESS_TODAY': Column 'Id' not found in data! This will cause validation to fail.")
        
        return ~validation_result
        
    except KeyError as e:
        print(f"Warning: Column {e} not found in DataFrame for validation rule 'OSD_RECEIVEDATE_LESS_TODAY'")
        return pd.Series([False] * len(df))  # Mark all as invalid if column missing
    except Exception as e:
        print(f"Warning: Error in validation rule 'OSD_RECEIVEDATE_LESS_TODAY': {e}")
        return pd.Series([False] * len(df))  # Mark all as invalid on error

def validate_PC_PART_SNO_MANDATORY(df):
    """
    Validation Rule: PC_PART_SNO_MANDATORY
    Salesforce Object: WOD_2__Claim__c
    Primary Field: Id
    
    
    Original Apex Formula:
    AND(
    OR(
        $Permission.WOD_2__DisableSkipTriggerNValidation,
        NOT($Permission.WOD_2__SkipTriggerNValidations)
    )
    ,OR(
        AND(
            ISPICKVAL(WOD_2__Claim_Type__c, 'Part')
            , ISPICKVAL(WOD_2__Part__r.WOD_2__Track_Type__c, 'Serialized')
            , ISBLANK(WOD_2__Part_Serial_Number__c)
        )
        ,AND(
            ISPICKVAL(WOD_2__Claim_Type__c, 'Part')
            , WOD_2__PartNumber_P2__r.WOD_2__Is_Serialized__c
            , ISBLANK(WOD_2__Part_Serial_Number__c)
        )
    )    
)
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results (True = valid, False = invalid)
    """
    # Primary Field: Id
    
    # Import required modules
    import pandas as pd
    import numpy as np
    from datetime import datetime, date
    import math
    
    try:
        # Ensure all required columns exist
        required_columns = []
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"Warning: Missing columns for validation rule 'PC_PART_SNO_MANDATORY': {missing_columns}")
            return pd.Series([False] * len(df))  # Mark all as invalid if columns missing
        
        # Fill NaN values to avoid errors
        df_clean = df.fillna('')
        
        # Apply validation logic
        validation_result = _and( _or( $df['Permission'].df['WOD_2__DisableSkipTriggerNValidation'], _not($df['Permission'].df['WOD_2__SkipTriggerNValidations']) ) ,_or( _and( _ispickval(df['WOD_2__Claim_Type__c'], 'df['Part']') , _ispickval(df['WOD_2__Part__r'].df['WOD_2__Track_Type__c'], 'df['Serialized']') , _is_blank(df['WOD_2__Part_Serial_Number__c']) ) ,_and( _ispickval(df['WOD_2__Claim_Type__c'], 'df['Part']') , df['WOD_2__PartNumber_P2__r'].df['WOD_2__Is_Serialized__c'] , _is_blank(df['WOD_2__Part_Serial_Number__c']) ) ) )
        
        # Ensure result is a boolean Series
        if not isinstance(validation_result, pd.Series):
            validation_result = pd.Series([bool(validation_result)] * len(df))
        
        # Salesforce validation rules define ERROR conditions (when validation should FAIL)
        # If the formula evaluates to True = Error condition = Record is INVALID
        # If the formula evaluates to False = No error = Record is VALID
        # So we need to invert: True becomes False (invalid), False becomes True (valid)
        
        # Debug: Print sample of validation logic for troubleshooting
        if len(df) > 0:
            sample_value = validation_result.iloc[0] if hasattr(validation_result, 'iloc') else validation_result
            print(f"DEBUG - Rule 'PC_PART_SNO_MANDATORY': Formula result for first record = {sample_value} (True=Error/Invalid, False=NoError/Valid)")
            
            # Additional debugging for ISBLANK scenarios
            if '_is_blank' in str(validation_result):
                sample_field_value = df_clean.iloc[0].get('Id', 'COLUMN_NOT_FOUND') if len(df_clean) > 0 else 'NO_DATA'
                print(f"DEBUG - Rule 'PC_PART_SNO_MANDATORY': Field 'Id' value for first record = '{sample_field_value}'")
                print(f"DEBUG - Rule 'PC_PART_SNO_MANDATORY': Available columns = {list(df.columns)}")
                if 'Id' not in df.columns:
                    print(f"WARNING - Rule 'PC_PART_SNO_MANDATORY': Column 'Id' not found in data! This will cause validation to fail.")
        
        return ~validation_result
        
    except KeyError as e:
        print(f"Warning: Column {e} not found in DataFrame for validation rule 'PC_PART_SNO_MANDATORY'")
        return pd.Series([False] * len(df))  # Mark all as invalid if column missing
    except Exception as e:
        print(f"Warning: Error in validation rule 'PC_PART_SNO_MANDATORY': {e}")
        return pd.Series([False] * len(df))  # Mark all as invalid on error

def validate_PREAUTH_EXPIRY_DATE_CHECK(df):
    """
    Validation Rule: PREAUTH_EXPIRY_DATE_CHECK
    Salesforce Object: WOD_2__Claim__c
    Primary Field: Id
    
    
    Original Apex Formula:
    AND(
OR(
$Permission.WOD_2__DisableSkipTriggerNValidation,
NOT($Permission.WOD_2__SkipTriggerNValidations)
),WOD_2__Pre_Authorization__r.WOD_2__Expiry_Date__c<TODAY())
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results (True = valid, False = invalid)
    """
    # Primary Field: Id
    
    # Import required modules
    import pandas as pd
    import numpy as np
    from datetime import datetime, date
    import math
    
    try:
        # Ensure all required columns exist
        required_columns = []
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"Warning: Missing columns for validation rule 'PREAUTH_EXPIRY_DATE_CHECK': {missing_columns}")
            return pd.Series([False] * len(df))  # Mark all as invalid if columns missing
        
        # Fill NaN values to avoid errors
        df_clean = df.fillna('')
        
        # Apply validation logic
        validation_result = _is_blank(df['Id'])
        
        # Ensure result is a boolean Series
        if not isinstance(validation_result, pd.Series):
            validation_result = pd.Series([bool(validation_result)] * len(df))
        
        # Salesforce validation rules define ERROR conditions (when validation should FAIL)
        # If the formula evaluates to True = Error condition = Record is INVALID
        # If the formula evaluates to False = No error = Record is VALID
        # So we need to invert: True becomes False (invalid), False becomes True (valid)
        
        # Debug: Print sample of validation logic for troubleshooting
        if len(df) > 0:
            sample_value = validation_result.iloc[0] if hasattr(validation_result, 'iloc') else validation_result
            print(f"DEBUG - Rule 'PREAUTH_EXPIRY_DATE_CHECK': Formula result for first record = {sample_value} (True=Error/Invalid, False=NoError/Valid)")
            
            # Additional debugging for ISBLANK scenarios
            if '_is_blank' in str(validation_result):
                sample_field_value = df_clean.iloc[0].get('Id', 'COLUMN_NOT_FOUND') if len(df_clean) > 0 else 'NO_DATA'
                print(f"DEBUG - Rule 'PREAUTH_EXPIRY_DATE_CHECK': Field 'Id' value for first record = '{sample_field_value}'")
                print(f"DEBUG - Rule 'PREAUTH_EXPIRY_DATE_CHECK': Available columns = {list(df.columns)}")
                if 'Id' not in df.columns:
                    print(f"WARNING - Rule 'PREAUTH_EXPIRY_DATE_CHECK': Column 'Id' not found in data! This will cause validation to fail.")
        
        return ~validation_result
        
    except KeyError as e:
        print(f"Warning: Column {e} not found in DataFrame for validation rule 'PREAUTH_EXPIRY_DATE_CHECK'")
        return pd.Series([False] * len(df))  # Mark all as invalid if column missing
    except Exception as e:
        print(f"Warning: Error in validation rule 'PREAUTH_EXPIRY_DATE_CHECK': {e}")
        return pd.Series([False] * len(df))  # Mark all as invalid on error

def validate_PREAUTH_FULFILLED_CHECK(df):
    """
    Validation Rule: PREAUTH_FULFILLED_CHECK
    Salesforce Object: WOD_2__Claim__c
    Primary Field: Id
    
    
    Original Apex Formula:
    AND(
OR(
$Permission.WOD_2__DisableSkipTriggerNValidation,
NOT($Permission.WOD_2__SkipTriggerNValidations)
),WOD_2__Pre_Authorization__r.WOD_2__Fulfilled__c == true)
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results (True = valid, False = invalid)
    """
    # Primary Field: Id
    
    # Import required modules
    import pandas as pd
    import numpy as np
    from datetime import datetime, date
    import math
    
    try:
        # Ensure all required columns exist
        required_columns = []
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"Warning: Missing columns for validation rule 'PREAUTH_FULFILLED_CHECK': {missing_columns}")
            return pd.Series([False] * len(df))  # Mark all as invalid if columns missing
        
        # Fill NaN values to avoid errors
        df_clean = df.fillna('')
        
        # Apply validation logic
        validation_result = _is_blank(df['Id'])
        
        # Ensure result is a boolean Series
        if not isinstance(validation_result, pd.Series):
            validation_result = pd.Series([bool(validation_result)] * len(df))
        
        # Salesforce validation rules define ERROR conditions (when validation should FAIL)
        # If the formula evaluates to True = Error condition = Record is INVALID
        # If the formula evaluates to False = No error = Record is VALID
        # So we need to invert: True becomes False (invalid), False becomes True (valid)
        
        # Debug: Print sample of validation logic for troubleshooting
        if len(df) > 0:
            sample_value = validation_result.iloc[0] if hasattr(validation_result, 'iloc') else validation_result
            print(f"DEBUG - Rule 'PREAUTH_FULFILLED_CHECK': Formula result for first record = {sample_value} (True=Error/Invalid, False=NoError/Valid)")
            
            # Additional debugging for ISBLANK scenarios
            if '_is_blank' in str(validation_result):
                sample_field_value = df_clean.iloc[0].get('Id', 'COLUMN_NOT_FOUND') if len(df_clean) > 0 else 'NO_DATA'
                print(f"DEBUG - Rule 'PREAUTH_FULFILLED_CHECK': Field 'Id' value for first record = '{sample_field_value}'")
                print(f"DEBUG - Rule 'PREAUTH_FULFILLED_CHECK': Available columns = {list(df.columns)}")
                if 'Id' not in df.columns:
                    print(f"WARNING - Rule 'PREAUTH_FULFILLED_CHECK': Column 'Id' not found in data! This will cause validation to fail.")
        
        return ~validation_result
        
    except KeyError as e:
        print(f"Warning: Column {e} not found in DataFrame for validation rule 'PREAUTH_FULFILLED_CHECK'")
        return pd.Series([False] * len(df))  # Mark all as invalid if column missing
    except Exception as e:
        print(f"Warning: Error in validation rule 'PREAUTH_FULFILLED_CHECK': {e}")
        return pd.Series([False] * len(df))  # Mark all as invalid on error

def validate_Claim_Is_Locked(df):
    """
    Validation Rule: Claim_Is_Locked
    Salesforce Object: WOD_2__Claim__c
    Primary Field: Id
    
    
    Original Apex Formula:
    If(AND(KBT_Is_Locked__c, PRIORVALUE(KBT_Is_Locked__c), NOT($User.KBT_Do_Not_Validate__c) ),
true,false)
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results (True = valid, False = invalid)
    """
    # Primary Field: Id
    
    # Import required modules
    import pandas as pd
    import numpy as np
    from datetime import datetime, date
    import math
    
    try:
        # Ensure all required columns exist
        required_columns = []
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"Warning: Missing columns for validation rule 'Claim_Is_Locked': {missing_columns}")
            return pd.Series([False] * len(df))  # Mark all as invalid if columns missing
        
        # Fill NaN values to avoid errors
        df_clean = df.fillna('')
        
        # Apply validation logic
        validation_result = _is_blank(df['Id'])
        
        # Ensure result is a boolean Series
        if not isinstance(validation_result, pd.Series):
            validation_result = pd.Series([bool(validation_result)] * len(df))
        
        # Salesforce validation rules define ERROR conditions (when validation should FAIL)
        # If the formula evaluates to True = Error condition = Record is INVALID
        # If the formula evaluates to False = No error = Record is VALID
        # So we need to invert: True becomes False (invalid), False becomes True (valid)
        
        # Debug: Print sample of validation logic for troubleshooting
        if len(df) > 0:
            sample_value = validation_result.iloc[0] if hasattr(validation_result, 'iloc') else validation_result
            print(f"DEBUG - Rule 'Claim_Is_Locked': Formula result for first record = {sample_value} (True=Error/Invalid, False=NoError/Valid)")
            
            # Additional debugging for ISBLANK scenarios
            if '_is_blank' in str(validation_result):
                sample_field_value = df_clean.iloc[0].get('Id', 'COLUMN_NOT_FOUND') if len(df_clean) > 0 else 'NO_DATA'
                print(f"DEBUG - Rule 'Claim_Is_Locked': Field 'Id' value for first record = '{sample_field_value}'")
                print(f"DEBUG - Rule 'Claim_Is_Locked': Available columns = {list(df.columns)}")
                if 'Id' not in df.columns:
                    print(f"WARNING - Rule 'Claim_Is_Locked': Column 'Id' not found in data! This will cause validation to fail.")
        
        return ~validation_result
        
    except KeyError as e:
        print(f"Warning: Column {e} not found in DataFrame for validation rule 'Claim_Is_Locked'")
        return pd.Series([False] * len(df))  # Mark all as invalid if column missing
    except Exception as e:
        print(f"Warning: Error in validation rule 'Claim_Is_Locked': {e}")
        return pd.Series([False] * len(df))  # Mark all as invalid on error

def validate_Failure_Date_validation_rule(df):
    """
    Validation Rule: Failure_Date_validation_rule
    Salesforce Object: WOD_2__Claim__c
    Primary Field: Id
    
    
    Original Apex Formula:
    IF(AND(OR(ISPICKVAL(WOD_2__Claim_Type__c, 'Machine'),ISPICKVAL(WOD_2__Claim_Type__c, 'Part')),    KBT_FirstUseDate__c  > WOD_2__Date_Of_Failure__c
) ,true,false)
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results (True = valid, False = invalid)
    """
    # Primary Field: Id
    
    # Import required modules
    import pandas as pd
    import numpy as np
    from datetime import datetime, date
    import math
    
    try:
        # Ensure all required columns exist
        required_columns = []
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"Warning: Missing columns for validation rule 'Failure_Date_validation_rule': {missing_columns}")
            return pd.Series([False] * len(df))  # Mark all as invalid if columns missing
        
        # Fill NaN values to avoid errors
        df_clean = df.fillna('')
        
        # Apply validation logic
        validation_result = _is_blank(df['Id'])
        
        # Ensure result is a boolean Series
        if not isinstance(validation_result, pd.Series):
            validation_result = pd.Series([bool(validation_result)] * len(df))
        
        # Salesforce validation rules define ERROR conditions (when validation should FAIL)
        # If the formula evaluates to True = Error condition = Record is INVALID
        # If the formula evaluates to False = No error = Record is VALID
        # So we need to invert: True becomes False (invalid), False becomes True (valid)
        
        # Debug: Print sample of validation logic for troubleshooting
        if len(df) > 0:
            sample_value = validation_result.iloc[0] if hasattr(validation_result, 'iloc') else validation_result
            print(f"DEBUG - Rule 'Failure_Date_validation_rule': Formula result for first record = {sample_value} (True=Error/Invalid, False=NoError/Valid)")
            
            # Additional debugging for ISBLANK scenarios
            if '_is_blank' in str(validation_result):
                sample_field_value = df_clean.iloc[0].get('Id', 'COLUMN_NOT_FOUND') if len(df_clean) > 0 else 'NO_DATA'
                print(f"DEBUG - Rule 'Failure_Date_validation_rule': Field 'Id' value for first record = '{sample_field_value}'")
                print(f"DEBUG - Rule 'Failure_Date_validation_rule': Available columns = {list(df.columns)}")
                if 'Id' not in df.columns:
                    print(f"WARNING - Rule 'Failure_Date_validation_rule': Column 'Id' not found in data! This will cause validation to fail.")
        
        return ~validation_result
        
    except KeyError as e:
        print(f"Warning: Column {e} not found in DataFrame for validation rule 'Failure_Date_validation_rule'")
        return pd.Series([False] * len(df))  # Mark all as invalid if column missing
    except Exception as e:
        print(f"Warning: Error in validation rule 'Failure_Date_validation_rule': {e}")
        return pd.Series([False] * len(df))  # Mark all as invalid on error

def validate_Goodwill_Type_Is_Missing(df):
    """
    Validation Rule: Goodwill_Type_Is_Missing
    Salesforce Object: WOD_2__Claim__c
    Primary Field: Id
    
    
    Original Apex Formula:
    if(KBT_Goodwill_Claim__c =true, If(ISPICKVAL( KBT_Goodwill_Type__c ,''),true,false),false)
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results (True = valid, False = invalid)
    """
    # Primary Field: Id
    
    # Import required modules
    import pandas as pd
    import numpy as np
    from datetime import datetime, date
    import math
    
    try:
        # Ensure all required columns exist
        required_columns = []
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"Warning: Missing columns for validation rule 'Goodwill_Type_Is_Missing': {missing_columns}")
            return pd.Series([False] * len(df))  # Mark all as invalid if columns missing
        
        # Fill NaN values to avoid errors
        df_clean = df.fillna('')
        
        # Apply validation logic
        validation_result = _is_blank(df['Id'])
        
        # Ensure result is a boolean Series
        if not isinstance(validation_result, pd.Series):
            validation_result = pd.Series([bool(validation_result)] * len(df))
        
        # Salesforce validation rules define ERROR conditions (when validation should FAIL)
        # If the formula evaluates to True = Error condition = Record is INVALID
        # If the formula evaluates to False = No error = Record is VALID
        # So we need to invert: True becomes False (invalid), False becomes True (valid)
        
        # Debug: Print sample of validation logic for troubleshooting
        if len(df) > 0:
            sample_value = validation_result.iloc[0] if hasattr(validation_result, 'iloc') else validation_result
            print(f"DEBUG - Rule 'Goodwill_Type_Is_Missing': Formula result for first record = {sample_value} (True=Error/Invalid, False=NoError/Valid)")
            
            # Additional debugging for ISBLANK scenarios
            if '_is_blank' in str(validation_result):
                sample_field_value = df_clean.iloc[0].get('Id', 'COLUMN_NOT_FOUND') if len(df_clean) > 0 else 'NO_DATA'
                print(f"DEBUG - Rule 'Goodwill_Type_Is_Missing': Field 'Id' value for first record = '{sample_field_value}'")
                print(f"DEBUG - Rule 'Goodwill_Type_Is_Missing': Available columns = {list(df.columns)}")
                if 'Id' not in df.columns:
                    print(f"WARNING - Rule 'Goodwill_Type_Is_Missing': Column 'Id' not found in data! This will cause validation to fail.")
        
        return ~validation_result
        
    except KeyError as e:
        print(f"Warning: Column {e} not found in DataFrame for validation rule 'Goodwill_Type_Is_Missing'")
        return pd.Series([False] * len(df))  # Mark all as invalid if column missing
    except Exception as e:
        print(f"Warning: Error in validation rule 'Goodwill_Type_Is_Missing': {e}")
        return pd.Series([False] * len(df))  # Mark all as invalid on error

def validate_KBT_MC_PC_CAUSAL_MANDATORY(df):
    """
    Validation Rule: KBT_MC_PC_CAUSAL_MANDATORY
    Salesforce Object: WOD_2__Claim__c
    Primary Field: Id
    
    
    Original Apex Formula:
    IF(AND(OR(
ISPICKVAL(WOD_2__Claim_Type__c, 'Machine'),
ISPICKVAL(WOD_2__Claim_Type__c, 'Part'),
ISPICKVAL(WOD_2__Claim_Type__c, 'Claim Template'),
ISPICKVAL(WOD_2__Claim_Type__c, 'Field Modification')
),
ISBLANK(WOD_2__Causal_Part_Number__c),
NOT(ISPICKVAL(WOD_2__Claim_Status__c , 'Initial Draft')),
NOT(ISPICKVAL(KBT_Claim_Source_System__c, 'RBOX'))
),
TRUE , FALSE
)
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results (True = valid, False = invalid)
    """
    # Primary Field: Id
    
    # Import required modules
    import pandas as pd
    import numpy as np
    from datetime import datetime, date
    import math
    
    try:
        # Ensure all required columns exist
        required_columns = []
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"Warning: Missing columns for validation rule 'KBT_MC_PC_CAUSAL_MANDATORY': {missing_columns}")
            return pd.Series([False] * len(df))  # Mark all as invalid if columns missing
        
        # Fill NaN values to avoid errors
        df_clean = df.fillna('')
        
        # Apply validation logic
        validation_result = _if(_and(_or( _ispickval(df['WOD_2__Claim_Type__c'], 'df['Machine']'), _ispickval(df['WOD_2__Claim_Type__c'], 'df['Part']'), _ispickval(df['WOD_2__Claim_Type__c'], 'df['Claim'] df['Template']'), _ispickval(df['WOD_2__Claim_Type__c'], 'df['Field'] df['Modification']') ), _is_blank(df['WOD_2__Causal_Part_Number__c']), _not(_ispickval(df['WOD_2__Claim_Status__c'] , 'df['Initial'] df['Draft']')), _not(_ispickval(df['KBT_Claim_Source_System__c'], 'df['RBOX']')) ), TRUE , FALSE )
        
        # Ensure result is a boolean Series
        if not isinstance(validation_result, pd.Series):
            validation_result = pd.Series([bool(validation_result)] * len(df))
        
        # Salesforce validation rules define ERROR conditions (when validation should FAIL)
        # If the formula evaluates to True = Error condition = Record is INVALID
        # If the formula evaluates to False = No error = Record is VALID
        # So we need to invert: True becomes False (invalid), False becomes True (valid)
        
        # Debug: Print sample of validation logic for troubleshooting
        if len(df) > 0:
            sample_value = validation_result.iloc[0] if hasattr(validation_result, 'iloc') else validation_result
            print(f"DEBUG - Rule 'KBT_MC_PC_CAUSAL_MANDATORY': Formula result for first record = {sample_value} (True=Error/Invalid, False=NoError/Valid)")
            
            # Additional debugging for ISBLANK scenarios
            if '_is_blank' in str(validation_result):
                sample_field_value = df_clean.iloc[0].get('Id', 'COLUMN_NOT_FOUND') if len(df_clean) > 0 else 'NO_DATA'
                print(f"DEBUG - Rule 'KBT_MC_PC_CAUSAL_MANDATORY': Field 'Id' value for first record = '{sample_field_value}'")
                print(f"DEBUG - Rule 'KBT_MC_PC_CAUSAL_MANDATORY': Available columns = {list(df.columns)}")
                if 'Id' not in df.columns:
                    print(f"WARNING - Rule 'KBT_MC_PC_CAUSAL_MANDATORY': Column 'Id' not found in data! This will cause validation to fail.")
        
        return ~validation_result
        
    except KeyError as e:
        print(f"Warning: Column {e} not found in DataFrame for validation rule 'KBT_MC_PC_CAUSAL_MANDATORY'")
        return pd.Series([False] * len(df))  # Mark all as invalid if column missing
    except Exception as e:
        print(f"Warning: Error in validation rule 'KBT_MC_PC_CAUSAL_MANDATORY': {e}")
        return pd.Series([False] * len(df))  # Mark all as invalid on error

def validate_KBT_MC_PC_INVENTORY_MANDATORY(df):
    """
    Validation Rule: KBT_MC_PC_INVENTORY_MANDATORY
    Salesforce Object: WOD_2__Claim__c
    Primary Field: Id
    
    
    Original Apex Formula:
    IF(OR(AND(ISPICKVAL(WOD_2__Claim_Type__c, 'Machine'), ISBLANK(WOD_2__Inventory__c), NOT(ISPICKVAL( WOD_2__Claim_Status__c , 'Initial Draft'))),AND(ISPICKVAL(WOD_2__Claim_Type__c, 'Part'), ISBLANK(WOD_2__Inventory__c), ISPICKVAL(WOD_2__Host_NonHost__c, 'Installed on OEM machine'), NOT( ISPICKVAL( WOD_2__Claim_Status__c , 'Initial Draft') ))),true,false)
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results (True = valid, False = invalid)
    """
    # Primary Field: Id
    
    # Import required modules
    import pandas as pd
    import numpy as np
    from datetime import datetime, date
    import math
    
    try:
        # Ensure all required columns exist
        required_columns = []
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"Warning: Missing columns for validation rule 'KBT_MC_PC_INVENTORY_MANDATORY': {missing_columns}")
            return pd.Series([False] * len(df))  # Mark all as invalid if columns missing
        
        # Fill NaN values to avoid errors
        df_clean = df.fillna('')
        
        # Apply validation logic
        validation_result = _if(_or(_and(_ispickval(df['WOD_2__Claim_Type__c'], 'df['Machine']'), _is_blank(df['WOD_2__Inventory__c']), _not(_ispickval( df['WOD_2__Claim_Status__c'] , 'df['Initial'] df['Draft']'))),_and(_ispickval(df['WOD_2__Claim_Type__c'], 'df['Part']'), _is_blank(df['WOD_2__Inventory__c']), _ispickval(df['WOD_2__Host_NonHost__c'], 'df['Installed'] df['on'] df['OEM'] df['machine']'), _not( _ispickval( df['WOD_2__Claim_Status__c'] , 'df['Initial'] df['Draft']') ))),true,false)
        
        # Ensure result is a boolean Series
        if not isinstance(validation_result, pd.Series):
            validation_result = pd.Series([bool(validation_result)] * len(df))
        
        # Salesforce validation rules define ERROR conditions (when validation should FAIL)
        # If the formula evaluates to True = Error condition = Record is INVALID
        # If the formula evaluates to False = No error = Record is VALID
        # So we need to invert: True becomes False (invalid), False becomes True (valid)
        
        # Debug: Print sample of validation logic for troubleshooting
        if len(df) > 0:
            sample_value = validation_result.iloc[0] if hasattr(validation_result, 'iloc') else validation_result
            print(f"DEBUG - Rule 'KBT_MC_PC_INVENTORY_MANDATORY': Formula result for first record = {sample_value} (True=Error/Invalid, False=NoError/Valid)")
            
            # Additional debugging for ISBLANK scenarios
            if '_is_blank' in str(validation_result):
                sample_field_value = df_clean.iloc[0].get('Id', 'COLUMN_NOT_FOUND') if len(df_clean) > 0 else 'NO_DATA'
                print(f"DEBUG - Rule 'KBT_MC_PC_INVENTORY_MANDATORY': Field 'Id' value for first record = '{sample_field_value}'")
                print(f"DEBUG - Rule 'KBT_MC_PC_INVENTORY_MANDATORY': Available columns = {list(df.columns)}")
                if 'Id' not in df.columns:
                    print(f"WARNING - Rule 'KBT_MC_PC_INVENTORY_MANDATORY': Column 'Id' not found in data! This will cause validation to fail.")
        
        return ~validation_result
        
    except KeyError as e:
        print(f"Warning: Column {e} not found in DataFrame for validation rule 'KBT_MC_PC_INVENTORY_MANDATORY'")
        return pd.Series([False] * len(df))  # Mark all as invalid if column missing
    except Exception as e:
        print(f"Warning: Error in validation rule 'KBT_MC_PC_INVENTORY_MANDATORY': {e}")
        return pd.Series([False] * len(df))  # Mark all as invalid on error

def validate_Incomplete_Mandotory_Fields(df):
    """
    Validation Rule: Incomplete_Mandotory_Fields
    Salesforce Object: WOD_2__Claim__c
    Primary Field: Id
    
    
    Original Apex Formula:
    IF(
    ISPICKVAL(WOD_2__Claim_Type__c, "Claim Template"),
    null,
    
    OR(
        ISBLANK(WOD_2__Account__c),
        ISBLANK(WOD_2__Date_Of_Failure__c),
        ISBLANK(WOD_2__Date_Of_Repair__c)
    )
)
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results (True = valid, False = invalid)
    """
    # Primary Field: Id
    
    # Import required modules
    import pandas as pd
    import numpy as np
    from datetime import datetime, date
    import math
    
    try:
        # Ensure all required columns exist
        required_columns = []
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"Warning: Missing columns for validation rule 'Incomplete_Mandotory_Fields': {missing_columns}")
            return pd.Series([False] * len(df))  # Mark all as invalid if columns missing
        
        # Fill NaN values to avoid errors
        df_clean = df.fillna('')
        
        # Apply validation logic
        validation_result = _if( _ispickval(df['WOD_2__Claim_Type__c'], "df['Claim'] df['Template']"), df['null'], _or( _is_blank(df['WOD_2__Account__c']), _is_blank(df['WOD_2__Date_Of_Failure__c']), _is_blank(df['WOD_2__Date_Of_Repair__c']) ) )
        
        # Ensure result is a boolean Series
        if not isinstance(validation_result, pd.Series):
            validation_result = pd.Series([bool(validation_result)] * len(df))
        
        # Salesforce validation rules define ERROR conditions (when validation should FAIL)
        # If the formula evaluates to True = Error condition = Record is INVALID
        # If the formula evaluates to False = No error = Record is VALID
        # So we need to invert: True becomes False (invalid), False becomes True (valid)
        
        # Debug: Print sample of validation logic for troubleshooting
        if len(df) > 0:
            sample_value = validation_result.iloc[0] if hasattr(validation_result, 'iloc') else validation_result
            print(f"DEBUG - Rule 'Incomplete_Mandotory_Fields': Formula result for first record = {sample_value} (True=Error/Invalid, False=NoError/Valid)")
            
            # Additional debugging for ISBLANK scenarios
            if '_is_blank' in str(validation_result):
                sample_field_value = df_clean.iloc[0].get('Id', 'COLUMN_NOT_FOUND') if len(df_clean) > 0 else 'NO_DATA'
                print(f"DEBUG - Rule 'Incomplete_Mandotory_Fields': Field 'Id' value for first record = '{sample_field_value}'")
                print(f"DEBUG - Rule 'Incomplete_Mandotory_Fields': Available columns = {list(df.columns)}")
                if 'Id' not in df.columns:
                    print(f"WARNING - Rule 'Incomplete_Mandotory_Fields': Column 'Id' not found in data! This will cause validation to fail.")
        
        return ~validation_result
        
    except KeyError as e:
        print(f"Warning: Column {e} not found in DataFrame for validation rule 'Incomplete_Mandotory_Fields'")
        return pd.Series([False] * len(df))  # Mark all as invalid if column missing
    except Exception as e:
        print(f"Warning: Error in validation rule 'Incomplete_Mandotory_Fields': {e}")
        return pd.Series([False] * len(df))  # Mark all as invalid on error

def validate_KBT_PC_PART_MANDATORY(df):
    """
    Validation Rule: KBT_PC_PART_MANDATORY
    Salesforce Object: WOD_2__Claim__c
    Primary Field: Id
    
    
    Original Apex Formula:
    IF(AND(AND(ISPICKVAL(WOD_2__Claim_Type__c, 'Part'), ISBLANK(WOD_2__Part__c )), NOT(ISPICKVAL(WOD_2__Claim_Status__c , "Initial Draft")),NOT(ISPICKVAL( KBT_Claim_Source_System__c  , "RBOX"))), true, false)
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results (True = valid, False = invalid)
    """
    # Primary Field: Id
    
    # Import required modules
    import pandas as pd
    import numpy as np
    from datetime import datetime, date
    import math
    
    try:
        # Ensure all required columns exist
        required_columns = []
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"Warning: Missing columns for validation rule 'KBT_PC_PART_MANDATORY': {missing_columns}")
            return pd.Series([False] * len(df))  # Mark all as invalid if columns missing
        
        # Fill NaN values to avoid errors
        df_clean = df.fillna('')
        
        # Apply validation logic
        validation_result = _if(_and(_and(_ispickval(df['WOD_2__Claim_Type__c'], 'df['Part']'), _is_blank(df['WOD_2__Part__c'] )), _not(_ispickval(df['WOD_2__Claim_Status__c'] , "df['Initial'] df['Draft']")),_not(_ispickval( df['KBT_Claim_Source_System__c'] , "df['RBOX']"))), true, false)
        
        # Ensure result is a boolean Series
        if not isinstance(validation_result, pd.Series):
            validation_result = pd.Series([bool(validation_result)] * len(df))
        
        # Salesforce validation rules define ERROR conditions (when validation should FAIL)
        # If the formula evaluates to True = Error condition = Record is INVALID
        # If the formula evaluates to False = No error = Record is VALID
        # So we need to invert: True becomes False (invalid), False becomes True (valid)
        
        # Debug: Print sample of validation logic for troubleshooting
        if len(df) > 0:
            sample_value = validation_result.iloc[0] if hasattr(validation_result, 'iloc') else validation_result
            print(f"DEBUG - Rule 'KBT_PC_PART_MANDATORY': Formula result for first record = {sample_value} (True=Error/Invalid, False=NoError/Valid)")
            
            # Additional debugging for ISBLANK scenarios
            if '_is_blank' in str(validation_result):
                sample_field_value = df_clean.iloc[0].get('Id', 'COLUMN_NOT_FOUND') if len(df_clean) > 0 else 'NO_DATA'
                print(f"DEBUG - Rule 'KBT_PC_PART_MANDATORY': Field 'Id' value for first record = '{sample_field_value}'")
                print(f"DEBUG - Rule 'KBT_PC_PART_MANDATORY': Available columns = {list(df.columns)}")
                if 'Id' not in df.columns:
                    print(f"WARNING - Rule 'KBT_PC_PART_MANDATORY': Column 'Id' not found in data! This will cause validation to fail.")
        
        return ~validation_result
        
    except KeyError as e:
        print(f"Warning: Column {e} not found in DataFrame for validation rule 'KBT_PC_PART_MANDATORY'")
        return pd.Series([False] * len(df))  # Mark all as invalid if column missing
    except Exception as e:
        print(f"Warning: Error in validation rule 'KBT_PC_PART_MANDATORY': {e}")
        return pd.Series([False] * len(df))  # Mark all as invalid on error

def validate_KBT_PC_PURCHASEDATE_MANDATORY(df):
    """
    Validation Rule: KBT_PC_PURCHASEDATE_MANDATORY
    Salesforce Object: WOD_2__Claim__c
    Primary Field: Id
    
    
    Original Apex Formula:
    IF(AND(AND(ISPICKVAL(WOD_2__Claim_Type__c, 'Part'), ISBLANK(  WOD_2__Date_Of_Purchase__c )), NOT(ISPICKVAL(WOD_2__Claim_Status__c , "Initial Draft")),NOT(ISPICKVAL( KBT_Claim_Source_System__c  , "RBOX"))), true, false)
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results (True = valid, False = invalid)
    """
    # Primary Field: Id
    
    # Import required modules
    import pandas as pd
    import numpy as np
    from datetime import datetime, date
    import math
    
    try:
        # Ensure all required columns exist
        required_columns = []
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"Warning: Missing columns for validation rule 'KBT_PC_PURCHASEDATE_MANDATORY': {missing_columns}")
            return pd.Series([False] * len(df))  # Mark all as invalid if columns missing
        
        # Fill NaN values to avoid errors
        df_clean = df.fillna('')
        
        # Apply validation logic
        validation_result = _if(_and(_and(_ispickval(df['WOD_2__Claim_Type__c'], 'df['Part']'), _is_blank( df['WOD_2__Date_Of_Purchase__c'] )), _not(_ispickval(df['WOD_2__Claim_Status__c'] , "df['Initial'] df['Draft']")),_not(_ispickval( df['KBT_Claim_Source_System__c'] , "df['RBOX']"))), true, false)
        
        # Ensure result is a boolean Series
        if not isinstance(validation_result, pd.Series):
            validation_result = pd.Series([bool(validation_result)] * len(df))
        
        # Salesforce validation rules define ERROR conditions (when validation should FAIL)
        # If the formula evaluates to True = Error condition = Record is INVALID
        # If the formula evaluates to False = No error = Record is VALID
        # So we need to invert: True becomes False (invalid), False becomes True (valid)
        
        # Debug: Print sample of validation logic for troubleshooting
        if len(df) > 0:
            sample_value = validation_result.iloc[0] if hasattr(validation_result, 'iloc') else validation_result
            print(f"DEBUG - Rule 'KBT_PC_PURCHASEDATE_MANDATORY': Formula result for first record = {sample_value} (True=Error/Invalid, False=NoError/Valid)")
            
            # Additional debugging for ISBLANK scenarios
            if '_is_blank' in str(validation_result):
                sample_field_value = df_clean.iloc[0].get('Id', 'COLUMN_NOT_FOUND') if len(df_clean) > 0 else 'NO_DATA'
                print(f"DEBUG - Rule 'KBT_PC_PURCHASEDATE_MANDATORY': Field 'Id' value for first record = '{sample_field_value}'")
                print(f"DEBUG - Rule 'KBT_PC_PURCHASEDATE_MANDATORY': Available columns = {list(df.columns)}")
                if 'Id' not in df.columns:
                    print(f"WARNING - Rule 'KBT_PC_PURCHASEDATE_MANDATORY': Column 'Id' not found in data! This will cause validation to fail.")
        
        return ~validation_result
        
    except KeyError as e:
        print(f"Warning: Column {e} not found in DataFrame for validation rule 'KBT_PC_PURCHASEDATE_MANDATORY'")
        return pd.Series([False] * len(df))  # Mark all as invalid if column missing
    except Exception as e:
        print(f"Warning: Error in validation rule 'KBT_PC_PURCHASEDATE_MANDATORY': {e}")
        return pd.Series([False] * len(df))  # Mark all as invalid on error

def validate_MC_PC_CAUSAL_CLAIM_TEMPLATE_MANDATORY(df):
    """
    Validation Rule: MC_PC_CAUSAL_CLAIM_TEMPLATE_MANDATORY
    Salesforce Object: WOD_2__Claim__c
    Primary Field: Id
    
    
    Original Apex Formula:
    AND(
        OR(
            $Permission.WOD_2__DisableSkipTriggerNValidation,
            NOT($Permission.WOD_2__SkipTriggerNValidations)
        ),
        IF(
            AND(
                ISPICKVAL(WOD_2__Claim_Type__c, 'Claim Template'),
                ISBLANK(WOD_2__Causal_Part_Number__c),
                ISBLANK(WOD_2__CausalPartNumber_P2__c)
            ),
            true,
            false
        )
    )
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results (True = valid, False = invalid)
    """
    # Primary Field: Id
    
    # Import required modules
    import pandas as pd
    import numpy as np
    from datetime import datetime, date
    import math
    
    try:
        # Ensure all required columns exist
        required_columns = []
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"Warning: Missing columns for validation rule 'MC_PC_CAUSAL_CLAIM_TEMPLATE_MANDATORY': {missing_columns}")
            return pd.Series([False] * len(df))  # Mark all as invalid if columns missing
        
        # Fill NaN values to avoid errors
        df_clean = df.fillna('')
        
        # Apply validation logic
        validation_result = _and( _or( $df['Permission'].df['WOD_2__DisableSkipTriggerNValidation'], _not($df['Permission'].df['WOD_2__SkipTriggerNValidations']) ), _if( _and( _ispickval(df['WOD_2__Claim_Type__c'], 'df['Claim'] df['Template']'), _is_blank(df['WOD_2__Causal_Part_Number__c']), _is_blank(df['WOD_2__CausalPartNumber_P2__c']) ), true, false ) )
        
        # Ensure result is a boolean Series
        if not isinstance(validation_result, pd.Series):
            validation_result = pd.Series([bool(validation_result)] * len(df))
        
        # Salesforce validation rules define ERROR conditions (when validation should FAIL)
        # If the formula evaluates to True = Error condition = Record is INVALID
        # If the formula evaluates to False = No error = Record is VALID
        # So we need to invert: True becomes False (invalid), False becomes True (valid)
        
        # Debug: Print sample of validation logic for troubleshooting
        if len(df) > 0:
            sample_value = validation_result.iloc[0] if hasattr(validation_result, 'iloc') else validation_result
            print(f"DEBUG - Rule 'MC_PC_CAUSAL_CLAIM_TEMPLATE_MANDATORY': Formula result for first record = {sample_value} (True=Error/Invalid, False=NoError/Valid)")
            
            # Additional debugging for ISBLANK scenarios
            if '_is_blank' in str(validation_result):
                sample_field_value = df_clean.iloc[0].get('Id', 'COLUMN_NOT_FOUND') if len(df_clean) > 0 else 'NO_DATA'
                print(f"DEBUG - Rule 'MC_PC_CAUSAL_CLAIM_TEMPLATE_MANDATORY': Field 'Id' value for first record = '{sample_field_value}'")
                print(f"DEBUG - Rule 'MC_PC_CAUSAL_CLAIM_TEMPLATE_MANDATORY': Available columns = {list(df.columns)}")
                if 'Id' not in df.columns:
                    print(f"WARNING - Rule 'MC_PC_CAUSAL_CLAIM_TEMPLATE_MANDATORY': Column 'Id' not found in data! This will cause validation to fail.")
        
        return ~validation_result
        
    except KeyError as e:
        print(f"Warning: Column {e} not found in DataFrame for validation rule 'MC_PC_CAUSAL_CLAIM_TEMPLATE_MANDATORY'")
        return pd.Series([False] * len(df))  # Mark all as invalid if column missing
    except Exception as e:
        print(f"Warning: Error in validation rule 'MC_PC_CAUSAL_CLAIM_TEMPLATE_MANDATORY': {e}")
        return pd.Series([False] * len(df))  # Mark all as invalid on error

def validate_First_UseDate_Mandatory(df):
    """
    Validation Rule: First_UseDate_Mandatory
    Salesforce Object: WOD_2__Claim__c
    Primary Field: Id
    
    
    Original Apex Formula:
    AND(
    ISPICKVAL(KBT_Inventory_Type__c, 'Retail'),
    ISBLANK(KBT_FirstUseDate__c)
)
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results (True = valid, False = invalid)
    """
    # Primary Field: Id
    
    # Import required modules
    import pandas as pd
    import numpy as np
    from datetime import datetime, date
    import math
    
    try:
        # Ensure all required columns exist
        required_columns = []
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"Warning: Missing columns for validation rule 'First_UseDate_Mandatory': {missing_columns}")
            return pd.Series([False] * len(df))  # Mark all as invalid if columns missing
        
        # Fill NaN values to avoid errors
        df_clean = df.fillna('')
        
        # Apply validation logic
        validation_result = _and( _ispickval(df['KBT_Inventory_Type__c'], 'df['Retail']'), _is_blank(df['KBT_FirstUseDate__c']) )
        
        # Ensure result is a boolean Series
        if not isinstance(validation_result, pd.Series):
            validation_result = pd.Series([bool(validation_result)] * len(df))
        
        # Salesforce validation rules define ERROR conditions (when validation should FAIL)
        # If the formula evaluates to True = Error condition = Record is INVALID
        # If the formula evaluates to False = No error = Record is VALID
        # So we need to invert: True becomes False (invalid), False becomes True (valid)
        
        # Debug: Print sample of validation logic for troubleshooting
        if len(df) > 0:
            sample_value = validation_result.iloc[0] if hasattr(validation_result, 'iloc') else validation_result
            print(f"DEBUG - Rule 'First_UseDate_Mandatory': Formula result for first record = {sample_value} (True=Error/Invalid, False=NoError/Valid)")
            
            # Additional debugging for ISBLANK scenarios
            if '_is_blank' in str(validation_result):
                sample_field_value = df_clean.iloc[0].get('Id', 'COLUMN_NOT_FOUND') if len(df_clean) > 0 else 'NO_DATA'
                print(f"DEBUG - Rule 'First_UseDate_Mandatory': Field 'Id' value for first record = '{sample_field_value}'")
                print(f"DEBUG - Rule 'First_UseDate_Mandatory': Available columns = {list(df.columns)}")
                if 'Id' not in df.columns:
                    print(f"WARNING - Rule 'First_UseDate_Mandatory': Column 'Id' not found in data! This will cause validation to fail.")
        
        return ~validation_result
        
    except KeyError as e:
        print(f"Warning: Column {e} not found in DataFrame for validation rule 'First_UseDate_Mandatory'")
        return pd.Series([False] * len(df))  # Mark all as invalid if column missing
    except Exception as e:
        print(f"Warning: Error in validation rule 'First_UseDate_Mandatory': {e}")
        return pd.Series([False] * len(df))  # Mark all as invalid on error

def validate_KBT_HinpoSeriesCode_Mandatory(df):
    """
    Validation Rule: KBT_HinpoSeriesCode_Mandatory
    Salesforce Object: WOD_2__Claim__c
    Primary Field: Id
    
    
    Original Apex Formula:
    AND(
    NOT(ISBLANK(WOD_2__Inventory__r.WOD_2__Item__c)),
    NOT(ISBLANK(WOD_2__Inventory__r.WOD_2__Item__r.WOD_2__Parent_Product__c)),
    WOD_2__Inventory__r.WOD_2__Item__r.WOD_2__Parent_Product__r.KBT_HinpoSeriesCode__c  = "121",
    ISBLANK(KBT_Shipping_Company__c),
    ISBLANK(KBT_Reference_tracking_number__c)
)
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results (True = valid, False = invalid)
    """
    # Primary Field: Id
    
    # Import required modules
    import pandas as pd
    import numpy as np
    from datetime import datetime, date
    import math
    
    try:
        # Ensure all required columns exist
        required_columns = []
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"Warning: Missing columns for validation rule 'KBT_HinpoSeriesCode_Mandatory': {missing_columns}")
            return pd.Series([False] * len(df))  # Mark all as invalid if columns missing
        
        # Fill NaN values to avoid errors
        df_clean = df.fillna('')
        
        # Apply validation logic
        validation_result = _and( _not(_is_blank(df['WOD_2__Inventory__r'].df['WOD_2__Item__c'])), _not(_is_blank(df['WOD_2__Inventory__r'].df['WOD_2__Item__r'].df['WOD_2__Parent_Product__c'])), df['WOD_2__Inventory__r'].df['WOD_2__Item__r'].df['WOD_2__Parent_Product__r'].df['KBT_HinpoSeriesCode__c'] == "121", _is_blank(df['KBT_Shipping_Company__c']), _is_blank(df['KBT_Reference_tracking_number__c']) )
        
        # Ensure result is a boolean Series
        if not isinstance(validation_result, pd.Series):
            validation_result = pd.Series([bool(validation_result)] * len(df))
        
        # Salesforce validation rules define ERROR conditions (when validation should FAIL)
        # If the formula evaluates to True = Error condition = Record is INVALID
        # If the formula evaluates to False = No error = Record is VALID
        # So we need to invert: True becomes False (invalid), False becomes True (valid)
        
        # Debug: Print sample of validation logic for troubleshooting
        if len(df) > 0:
            sample_value = validation_result.iloc[0] if hasattr(validation_result, 'iloc') else validation_result
            print(f"DEBUG - Rule 'KBT_HinpoSeriesCode_Mandatory': Formula result for first record = {sample_value} (True=Error/Invalid, False=NoError/Valid)")
            
            # Additional debugging for ISBLANK scenarios
            if '_is_blank' in str(validation_result):
                sample_field_value = df_clean.iloc[0].get('Id', 'COLUMN_NOT_FOUND') if len(df_clean) > 0 else 'NO_DATA'
                print(f"DEBUG - Rule 'KBT_HinpoSeriesCode_Mandatory': Field 'Id' value for first record = '{sample_field_value}'")
                print(f"DEBUG - Rule 'KBT_HinpoSeriesCode_Mandatory': Available columns = {list(df.columns)}")
                if 'Id' not in df.columns:
                    print(f"WARNING - Rule 'KBT_HinpoSeriesCode_Mandatory': Column 'Id' not found in data! This will cause validation to fail.")
        
        return ~validation_result
        
    except KeyError as e:
        print(f"Warning: Column {e} not found in DataFrame for validation rule 'KBT_HinpoSeriesCode_Mandatory'")
        return pd.Series([False] * len(df))  # Mark all as invalid if column missing
    except Exception as e:
        print(f"Warning: Error in validation rule 'KBT_HinpoSeriesCode_Mandatory': {e}")
        return pd.Series([False] * len(df))  # Mark all as invalid on error

def validate_ShippingCompany_and_Ref_Num_Mandatory(df):
    """
    Validation Rule: ShippingCompany_and_Ref_Num_Mandatory
    Salesforce Object: WOD_2__Claim__c
    Primary Field: Id
    
    
    Original Apex Formula:
    AND( NOT(ISPICKVAL( WOD_2__Claim_Status__c ,'Initial Draft')),
KBT_Hinpo_Code__c  = "121",OR(
ISBLANK(KBT_Shipping_Company__c),
ISBLANK(KBT_Reference_tracking_number__c))
)
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results (True = valid, False = invalid)
    """
    # Primary Field: Id
    
    # Import required modules
    import pandas as pd
    import numpy as np
    from datetime import datetime, date
    import math
    
    try:
        # Ensure all required columns exist
        required_columns = []
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"Warning: Missing columns for validation rule 'ShippingCompany_and_Ref_Num_Mandatory': {missing_columns}")
            return pd.Series([False] * len(df))  # Mark all as invalid if columns missing
        
        # Fill NaN values to avoid errors
        df_clean = df.fillna('')
        
        # Apply validation logic
        validation_result = _and( _not(_ispickval( df['WOD_2__Claim_Status__c'] ,'df['Initial'] df['Draft']')), df['KBT_Hinpo_Code__c'] == "121",_or( _is_blank(df['KBT_Shipping_Company__c']), _is_blank(df['KBT_Reference_tracking_number__c'])) )
        
        # Ensure result is a boolean Series
        if not isinstance(validation_result, pd.Series):
            validation_result = pd.Series([bool(validation_result)] * len(df))
        
        # Salesforce validation rules define ERROR conditions (when validation should FAIL)
        # If the formula evaluates to True = Error condition = Record is INVALID
        # If the formula evaluates to False = No error = Record is VALID
        # So we need to invert: True becomes False (invalid), False becomes True (valid)
        
        # Debug: Print sample of validation logic for troubleshooting
        if len(df) > 0:
            sample_value = validation_result.iloc[0] if hasattr(validation_result, 'iloc') else validation_result
            print(f"DEBUG - Rule 'ShippingCompany_and_Ref_Num_Mandatory': Formula result for first record = {sample_value} (True=Error/Invalid, False=NoError/Valid)")
            
            # Additional debugging for ISBLANK scenarios
            if '_is_blank' in str(validation_result):
                sample_field_value = df_clean.iloc[0].get('Id', 'COLUMN_NOT_FOUND') if len(df_clean) > 0 else 'NO_DATA'
                print(f"DEBUG - Rule 'ShippingCompany_and_Ref_Num_Mandatory': Field 'Id' value for first record = '{sample_field_value}'")
                print(f"DEBUG - Rule 'ShippingCompany_and_Ref_Num_Mandatory': Available columns = {list(df.columns)}")
                if 'Id' not in df.columns:
                    print(f"WARNING - Rule 'ShippingCompany_and_Ref_Num_Mandatory': Column 'Id' not found in data! This will cause validation to fail.")
        
        return ~validation_result
        
    except KeyError as e:
        print(f"Warning: Column {e} not found in DataFrame for validation rule 'ShippingCompany_and_Ref_Num_Mandatory'")
        return pd.Series([False] * len(df))  # Mark all as invalid if column missing
    except Exception as e:
        print(f"Warning: Error in validation rule 'ShippingCompany_and_Ref_Num_Mandatory': {e}")
        return pd.Series([False] * len(df))  # Mark all as invalid on error

def validate_record(row):
    '''Validate a single record (row) and return result dict'''
    import pandas as pd
    df = pd.DataFrame([row])
    rule_results = {}
    errors = []
    is_valid = True
    try:
        print(f"DEBUG validate_record: Calling validate_MC_PC_PRE_AUTH_COMMENTS_MANDATORY on row data")
        func_result = validate_MC_PC_PRE_AUTH_COMMENTS_MANDATORY(df)
        if hasattr(func_result, 'iloc'):
            rule_results['validate_MC_PC_PRE_AUTH_COMMENTS_MANDATORY'] = bool(func_result.iloc[0])
        else:
            rule_results['validate_MC_PC_PRE_AUTH_COMMENTS_MANDATORY'] = bool(func_result)
        print(f"DEBUG validate_record: validate_MC_PC_PRE_AUTH_COMMENTS_MANDATORY returned {rule_results['validate_MC_PC_PRE_AUTH_COMMENTS_MANDATORY']}")
        if not rule_results['validate_MC_PC_PRE_AUTH_COMMENTS_MANDATORY']:
            errors.append('validate_MC_PC_PRE_AUTH_COMMENTS_MANDATORY')
            print(f"DEBUG validate_record: Added validate_MC_PC_PRE_AUTH_COMMENTS_MANDATORY to errors list")
    except Exception as e:
        print(f"ERROR validate_record: validate_MC_PC_PRE_AUTH_COMMENTS_MANDATORY failed with error: {str(e)}")
        rule_results['validate_MC_PC_PRE_AUTH_COMMENTS_MANDATORY'] = False
        errors.append(f'validate_MC_PC_PRE_AUTH_COMMENTS_MANDATORY (error: {str(e)})')
    try:
        print(f"DEBUG validate_record: Calling validate_MC_PC_PRE_AUTH_REASON_MANDATORY on row data")
        func_result = validate_MC_PC_PRE_AUTH_REASON_MANDATORY(df)
        if hasattr(func_result, 'iloc'):
            rule_results['validate_MC_PC_PRE_AUTH_REASON_MANDATORY'] = bool(func_result.iloc[0])
        else:
            rule_results['validate_MC_PC_PRE_AUTH_REASON_MANDATORY'] = bool(func_result)
        print(f"DEBUG validate_record: validate_MC_PC_PRE_AUTH_REASON_MANDATORY returned {rule_results['validate_MC_PC_PRE_AUTH_REASON_MANDATORY']}")
        if not rule_results['validate_MC_PC_PRE_AUTH_REASON_MANDATORY']:
            errors.append('validate_MC_PC_PRE_AUTH_REASON_MANDATORY')
            print(f"DEBUG validate_record: Added validate_MC_PC_PRE_AUTH_REASON_MANDATORY to errors list")
    except Exception as e:
        print(f"ERROR validate_record: validate_MC_PC_PRE_AUTH_REASON_MANDATORY failed with error: {str(e)}")
        rule_results['validate_MC_PC_PRE_AUTH_REASON_MANDATORY'] = False
        errors.append(f'validate_MC_PC_PRE_AUTH_REASON_MANDATORY (error: {str(e)})')
    try:
        print(f"DEBUG validate_record: Calling validate_MC_PurchaseDate_Less_REPAIRDATE_FAILURE on row data")
        func_result = validate_MC_PurchaseDate_Less_REPAIRDATE_FAILURE(df)
        if hasattr(func_result, 'iloc'):
            rule_results['validate_MC_PurchaseDate_Less_REPAIRDATE_FAILURE'] = bool(func_result.iloc[0])
        else:
            rule_results['validate_MC_PurchaseDate_Less_REPAIRDATE_FAILURE'] = bool(func_result)
        print(f"DEBUG validate_record: validate_MC_PurchaseDate_Less_REPAIRDATE_FAILURE returned {rule_results['validate_MC_PurchaseDate_Less_REPAIRDATE_FAILURE']}")
        if not rule_results['validate_MC_PurchaseDate_Less_REPAIRDATE_FAILURE']:
            errors.append('validate_MC_PurchaseDate_Less_REPAIRDATE_FAILURE')
            print(f"DEBUG validate_record: Added validate_MC_PurchaseDate_Less_REPAIRDATE_FAILURE to errors list")
    except Exception as e:
        print(f"ERROR validate_record: validate_MC_PurchaseDate_Less_REPAIRDATE_FAILURE failed with error: {str(e)}")
        rule_results['validate_MC_PurchaseDate_Less_REPAIRDATE_FAILURE'] = False
        errors.append(f'validate_MC_PurchaseDate_Less_REPAIRDATE_FAILURE (error: {str(e)})')
    try:
        print(f"DEBUG validate_record: Calling validate_OSD_RECEIVEDATE_LESS_TODAY on row data")
        func_result = validate_OSD_RECEIVEDATE_LESS_TODAY(df)
        if hasattr(func_result, 'iloc'):
            rule_results['validate_OSD_RECEIVEDATE_LESS_TODAY'] = bool(func_result.iloc[0])
        else:
            rule_results['validate_OSD_RECEIVEDATE_LESS_TODAY'] = bool(func_result)
        print(f"DEBUG validate_record: validate_OSD_RECEIVEDATE_LESS_TODAY returned {rule_results['validate_OSD_RECEIVEDATE_LESS_TODAY']}")
        if not rule_results['validate_OSD_RECEIVEDATE_LESS_TODAY']:
            errors.append('validate_OSD_RECEIVEDATE_LESS_TODAY')
            print(f"DEBUG validate_record: Added validate_OSD_RECEIVEDATE_LESS_TODAY to errors list")
    except Exception as e:
        print(f"ERROR validate_record: validate_OSD_RECEIVEDATE_LESS_TODAY failed with error: {str(e)}")
        rule_results['validate_OSD_RECEIVEDATE_LESS_TODAY'] = False
        errors.append(f'validate_OSD_RECEIVEDATE_LESS_TODAY (error: {str(e)})')
    try:
        print(f"DEBUG validate_record: Calling validate_PC_PART_SNO_MANDATORY on row data")
        func_result = validate_PC_PART_SNO_MANDATORY(df)
        if hasattr(func_result, 'iloc'):
            rule_results['validate_PC_PART_SNO_MANDATORY'] = bool(func_result.iloc[0])
        else:
            rule_results['validate_PC_PART_SNO_MANDATORY'] = bool(func_result)
        print(f"DEBUG validate_record: validate_PC_PART_SNO_MANDATORY returned {rule_results['validate_PC_PART_SNO_MANDATORY']}")
        if not rule_results['validate_PC_PART_SNO_MANDATORY']:
            errors.append('validate_PC_PART_SNO_MANDATORY')
            print(f"DEBUG validate_record: Added validate_PC_PART_SNO_MANDATORY to errors list")
    except Exception as e:
        print(f"ERROR validate_record: validate_PC_PART_SNO_MANDATORY failed with error: {str(e)}")
        rule_results['validate_PC_PART_SNO_MANDATORY'] = False
        errors.append(f'validate_PC_PART_SNO_MANDATORY (error: {str(e)})')
    try:
        print(f"DEBUG validate_record: Calling validate_PREAUTH_EXPIRY_DATE_CHECK on row data")
        func_result = validate_PREAUTH_EXPIRY_DATE_CHECK(df)
        if hasattr(func_result, 'iloc'):
            rule_results['validate_PREAUTH_EXPIRY_DATE_CHECK'] = bool(func_result.iloc[0])
        else:
            rule_results['validate_PREAUTH_EXPIRY_DATE_CHECK'] = bool(func_result)
        print(f"DEBUG validate_record: validate_PREAUTH_EXPIRY_DATE_CHECK returned {rule_results['validate_PREAUTH_EXPIRY_DATE_CHECK']}")
        if not rule_results['validate_PREAUTH_EXPIRY_DATE_CHECK']:
            errors.append('validate_PREAUTH_EXPIRY_DATE_CHECK')
            print(f"DEBUG validate_record: Added validate_PREAUTH_EXPIRY_DATE_CHECK to errors list")
    except Exception as e:
        print(f"ERROR validate_record: validate_PREAUTH_EXPIRY_DATE_CHECK failed with error: {str(e)}")
        rule_results['validate_PREAUTH_EXPIRY_DATE_CHECK'] = False
        errors.append(f'validate_PREAUTH_EXPIRY_DATE_CHECK (error: {str(e)})')
    try:
        print(f"DEBUG validate_record: Calling validate_PREAUTH_FULFILLED_CHECK on row data")
        func_result = validate_PREAUTH_FULFILLED_CHECK(df)
        if hasattr(func_result, 'iloc'):
            rule_results['validate_PREAUTH_FULFILLED_CHECK'] = bool(func_result.iloc[0])
        else:
            rule_results['validate_PREAUTH_FULFILLED_CHECK'] = bool(func_result)
        print(f"DEBUG validate_record: validate_PREAUTH_FULFILLED_CHECK returned {rule_results['validate_PREAUTH_FULFILLED_CHECK']}")
        if not rule_results['validate_PREAUTH_FULFILLED_CHECK']:
            errors.append('validate_PREAUTH_FULFILLED_CHECK')
            print(f"DEBUG validate_record: Added validate_PREAUTH_FULFILLED_CHECK to errors list")
    except Exception as e:
        print(f"ERROR validate_record: validate_PREAUTH_FULFILLED_CHECK failed with error: {str(e)}")
        rule_results['validate_PREAUTH_FULFILLED_CHECK'] = False
        errors.append(f'validate_PREAUTH_FULFILLED_CHECK (error: {str(e)})')
    try:
        print(f"DEBUG validate_record: Calling validate_Claim_Is_Locked on row data")
        func_result = validate_Claim_Is_Locked(df)
        if hasattr(func_result, 'iloc'):
            rule_results['validate_Claim_Is_Locked'] = bool(func_result.iloc[0])
        else:
            rule_results['validate_Claim_Is_Locked'] = bool(func_result)
        print(f"DEBUG validate_record: validate_Claim_Is_Locked returned {rule_results['validate_Claim_Is_Locked']}")
        if not rule_results['validate_Claim_Is_Locked']:
            errors.append('validate_Claim_Is_Locked')
            print(f"DEBUG validate_record: Added validate_Claim_Is_Locked to errors list")
    except Exception as e:
        print(f"ERROR validate_record: validate_Claim_Is_Locked failed with error: {str(e)}")
        rule_results['validate_Claim_Is_Locked'] = False
        errors.append(f'validate_Claim_Is_Locked (error: {str(e)})')
    try:
        print(f"DEBUG validate_record: Calling validate_Failure_Date_validation_rule on row data")
        func_result = validate_Failure_Date_validation_rule(df)
        if hasattr(func_result, 'iloc'):
            rule_results['validate_Failure_Date_validation_rule'] = bool(func_result.iloc[0])
        else:
            rule_results['validate_Failure_Date_validation_rule'] = bool(func_result)
        print(f"DEBUG validate_record: validate_Failure_Date_validation_rule returned {rule_results['validate_Failure_Date_validation_rule']}")
        if not rule_results['validate_Failure_Date_validation_rule']:
            errors.append('validate_Failure_Date_validation_rule')
            print(f"DEBUG validate_record: Added validate_Failure_Date_validation_rule to errors list")
    except Exception as e:
        print(f"ERROR validate_record: validate_Failure_Date_validation_rule failed with error: {str(e)}")
        rule_results['validate_Failure_Date_validation_rule'] = False
        errors.append(f'validate_Failure_Date_validation_rule (error: {str(e)})')
    try:
        print(f"DEBUG validate_record: Calling validate_Goodwill_Type_Is_Missing on row data")
        func_result = validate_Goodwill_Type_Is_Missing(df)
        if hasattr(func_result, 'iloc'):
            rule_results['validate_Goodwill_Type_Is_Missing'] = bool(func_result.iloc[0])
        else:
            rule_results['validate_Goodwill_Type_Is_Missing'] = bool(func_result)
        print(f"DEBUG validate_record: validate_Goodwill_Type_Is_Missing returned {rule_results['validate_Goodwill_Type_Is_Missing']}")
        if not rule_results['validate_Goodwill_Type_Is_Missing']:
            errors.append('validate_Goodwill_Type_Is_Missing')
            print(f"DEBUG validate_record: Added validate_Goodwill_Type_Is_Missing to errors list")
    except Exception as e:
        print(f"ERROR validate_record: validate_Goodwill_Type_Is_Missing failed with error: {str(e)}")
        rule_results['validate_Goodwill_Type_Is_Missing'] = False
        errors.append(f'validate_Goodwill_Type_Is_Missing (error: {str(e)})')
    try:
        print(f"DEBUG validate_record: Calling validate_KBT_MC_PC_CAUSAL_MANDATORY on row data")
        func_result = validate_KBT_MC_PC_CAUSAL_MANDATORY(df)
        if hasattr(func_result, 'iloc'):
            rule_results['validate_KBT_MC_PC_CAUSAL_MANDATORY'] = bool(func_result.iloc[0])
        else:
            rule_results['validate_KBT_MC_PC_CAUSAL_MANDATORY'] = bool(func_result)
        print(f"DEBUG validate_record: validate_KBT_MC_PC_CAUSAL_MANDATORY returned {rule_results['validate_KBT_MC_PC_CAUSAL_MANDATORY']}")
        if not rule_results['validate_KBT_MC_PC_CAUSAL_MANDATORY']:
            errors.append('validate_KBT_MC_PC_CAUSAL_MANDATORY')
            print(f"DEBUG validate_record: Added validate_KBT_MC_PC_CAUSAL_MANDATORY to errors list")
    except Exception as e:
        print(f"ERROR validate_record: validate_KBT_MC_PC_CAUSAL_MANDATORY failed with error: {str(e)}")
        rule_results['validate_KBT_MC_PC_CAUSAL_MANDATORY'] = False
        errors.append(f'validate_KBT_MC_PC_CAUSAL_MANDATORY (error: {str(e)})')
    try:
        print(f"DEBUG validate_record: Calling validate_KBT_MC_PC_INVENTORY_MANDATORY on row data")
        func_result = validate_KBT_MC_PC_INVENTORY_MANDATORY(df)
        if hasattr(func_result, 'iloc'):
            rule_results['validate_KBT_MC_PC_INVENTORY_MANDATORY'] = bool(func_result.iloc[0])
        else:
            rule_results['validate_KBT_MC_PC_INVENTORY_MANDATORY'] = bool(func_result)
        print(f"DEBUG validate_record: validate_KBT_MC_PC_INVENTORY_MANDATORY returned {rule_results['validate_KBT_MC_PC_INVENTORY_MANDATORY']}")
        if not rule_results['validate_KBT_MC_PC_INVENTORY_MANDATORY']:
            errors.append('validate_KBT_MC_PC_INVENTORY_MANDATORY')
            print(f"DEBUG validate_record: Added validate_KBT_MC_PC_INVENTORY_MANDATORY to errors list")
    except Exception as e:
        print(f"ERROR validate_record: validate_KBT_MC_PC_INVENTORY_MANDATORY failed with error: {str(e)}")
        rule_results['validate_KBT_MC_PC_INVENTORY_MANDATORY'] = False
        errors.append(f'validate_KBT_MC_PC_INVENTORY_MANDATORY (error: {str(e)})')
    try:
        print(f"DEBUG validate_record: Calling validate_Incomplete_Mandotory_Fields on row data")
        func_result = validate_Incomplete_Mandotory_Fields(df)
        if hasattr(func_result, 'iloc'):
            rule_results['validate_Incomplete_Mandotory_Fields'] = bool(func_result.iloc[0])
        else:
            rule_results['validate_Incomplete_Mandotory_Fields'] = bool(func_result)
        print(f"DEBUG validate_record: validate_Incomplete_Mandotory_Fields returned {rule_results['validate_Incomplete_Mandotory_Fields']}")
        if not rule_results['validate_Incomplete_Mandotory_Fields']:
            errors.append('validate_Incomplete_Mandotory_Fields')
            print(f"DEBUG validate_record: Added validate_Incomplete_Mandotory_Fields to errors list")
    except Exception as e:
        print(f"ERROR validate_record: validate_Incomplete_Mandotory_Fields failed with error: {str(e)}")
        rule_results['validate_Incomplete_Mandotory_Fields'] = False
        errors.append(f'validate_Incomplete_Mandotory_Fields (error: {str(e)})')
    try:
        print(f"DEBUG validate_record: Calling validate_KBT_PC_PART_MANDATORY on row data")
        func_result = validate_KBT_PC_PART_MANDATORY(df)
        if hasattr(func_result, 'iloc'):
            rule_results['validate_KBT_PC_PART_MANDATORY'] = bool(func_result.iloc[0])
        else:
            rule_results['validate_KBT_PC_PART_MANDATORY'] = bool(func_result)
        print(f"DEBUG validate_record: validate_KBT_PC_PART_MANDATORY returned {rule_results['validate_KBT_PC_PART_MANDATORY']}")
        if not rule_results['validate_KBT_PC_PART_MANDATORY']:
            errors.append('validate_KBT_PC_PART_MANDATORY')
            print(f"DEBUG validate_record: Added validate_KBT_PC_PART_MANDATORY to errors list")
    except Exception as e:
        print(f"ERROR validate_record: validate_KBT_PC_PART_MANDATORY failed with error: {str(e)}")
        rule_results['validate_KBT_PC_PART_MANDATORY'] = False
        errors.append(f'validate_KBT_PC_PART_MANDATORY (error: {str(e)})')
    try:
        print(f"DEBUG validate_record: Calling validate_KBT_PC_PURCHASEDATE_MANDATORY on row data")
        func_result = validate_KBT_PC_PURCHASEDATE_MANDATORY(df)
        if hasattr(func_result, 'iloc'):
            rule_results['validate_KBT_PC_PURCHASEDATE_MANDATORY'] = bool(func_result.iloc[0])
        else:
            rule_results['validate_KBT_PC_PURCHASEDATE_MANDATORY'] = bool(func_result)
        print(f"DEBUG validate_record: validate_KBT_PC_PURCHASEDATE_MANDATORY returned {rule_results['validate_KBT_PC_PURCHASEDATE_MANDATORY']}")
        if not rule_results['validate_KBT_PC_PURCHASEDATE_MANDATORY']:
            errors.append('validate_KBT_PC_PURCHASEDATE_MANDATORY')
            print(f"DEBUG validate_record: Added validate_KBT_PC_PURCHASEDATE_MANDATORY to errors list")
    except Exception as e:
        print(f"ERROR validate_record: validate_KBT_PC_PURCHASEDATE_MANDATORY failed with error: {str(e)}")
        rule_results['validate_KBT_PC_PURCHASEDATE_MANDATORY'] = False
        errors.append(f'validate_KBT_PC_PURCHASEDATE_MANDATORY (error: {str(e)})')
    try:
        print(f"DEBUG validate_record: Calling validate_MC_PC_CAUSAL_CLAIM_TEMPLATE_MANDATORY on row data")
        func_result = validate_MC_PC_CAUSAL_CLAIM_TEMPLATE_MANDATORY(df)
        if hasattr(func_result, 'iloc'):
            rule_results['validate_MC_PC_CAUSAL_CLAIM_TEMPLATE_MANDATORY'] = bool(func_result.iloc[0])
        else:
            rule_results['validate_MC_PC_CAUSAL_CLAIM_TEMPLATE_MANDATORY'] = bool(func_result)
        print(f"DEBUG validate_record: validate_MC_PC_CAUSAL_CLAIM_TEMPLATE_MANDATORY returned {rule_results['validate_MC_PC_CAUSAL_CLAIM_TEMPLATE_MANDATORY']}")
        if not rule_results['validate_MC_PC_CAUSAL_CLAIM_TEMPLATE_MANDATORY']:
            errors.append('validate_MC_PC_CAUSAL_CLAIM_TEMPLATE_MANDATORY')
            print(f"DEBUG validate_record: Added validate_MC_PC_CAUSAL_CLAIM_TEMPLATE_MANDATORY to errors list")
    except Exception as e:
        print(f"ERROR validate_record: validate_MC_PC_CAUSAL_CLAIM_TEMPLATE_MANDATORY failed with error: {str(e)}")
        rule_results['validate_MC_PC_CAUSAL_CLAIM_TEMPLATE_MANDATORY'] = False
        errors.append(f'validate_MC_PC_CAUSAL_CLAIM_TEMPLATE_MANDATORY (error: {str(e)})')
    try:
        print(f"DEBUG validate_record: Calling validate_First_UseDate_Mandatory on row data")
        func_result = validate_First_UseDate_Mandatory(df)
        if hasattr(func_result, 'iloc'):
            rule_results['validate_First_UseDate_Mandatory'] = bool(func_result.iloc[0])
        else:
            rule_results['validate_First_UseDate_Mandatory'] = bool(func_result)
        print(f"DEBUG validate_record: validate_First_UseDate_Mandatory returned {rule_results['validate_First_UseDate_Mandatory']}")
        if not rule_results['validate_First_UseDate_Mandatory']:
            errors.append('validate_First_UseDate_Mandatory')
            print(f"DEBUG validate_record: Added validate_First_UseDate_Mandatory to errors list")
    except Exception as e:
        print(f"ERROR validate_record: validate_First_UseDate_Mandatory failed with error: {str(e)}")
        rule_results['validate_First_UseDate_Mandatory'] = False
        errors.append(f'validate_First_UseDate_Mandatory (error: {str(e)})')
    try:
        print(f"DEBUG validate_record: Calling validate_KBT_HinpoSeriesCode_Mandatory on row data")
        func_result = validate_KBT_HinpoSeriesCode_Mandatory(df)
        if hasattr(func_result, 'iloc'):
            rule_results['validate_KBT_HinpoSeriesCode_Mandatory'] = bool(func_result.iloc[0])
        else:
            rule_results['validate_KBT_HinpoSeriesCode_Mandatory'] = bool(func_result)
        print(f"DEBUG validate_record: validate_KBT_HinpoSeriesCode_Mandatory returned {rule_results['validate_KBT_HinpoSeriesCode_Mandatory']}")
        if not rule_results['validate_KBT_HinpoSeriesCode_Mandatory']:
            errors.append('validate_KBT_HinpoSeriesCode_Mandatory')
            print(f"DEBUG validate_record: Added validate_KBT_HinpoSeriesCode_Mandatory to errors list")
    except Exception as e:
        print(f"ERROR validate_record: validate_KBT_HinpoSeriesCode_Mandatory failed with error: {str(e)}")
        rule_results['validate_KBT_HinpoSeriesCode_Mandatory'] = False
        errors.append(f'validate_KBT_HinpoSeriesCode_Mandatory (error: {str(e)})')
    try:
        print(f"DEBUG validate_record: Calling validate_ShippingCompany_and_Ref_Num_Mandatory on row data")
        func_result = validate_ShippingCompany_and_Ref_Num_Mandatory(df)
        if hasattr(func_result, 'iloc'):
            rule_results['validate_ShippingCompany_and_Ref_Num_Mandatory'] = bool(func_result.iloc[0])
        else:
            rule_results['validate_ShippingCompany_and_Ref_Num_Mandatory'] = bool(func_result)
        print(f"DEBUG validate_record: validate_ShippingCompany_and_Ref_Num_Mandatory returned {rule_results['validate_ShippingCompany_and_Ref_Num_Mandatory']}")
        if not rule_results['validate_ShippingCompany_and_Ref_Num_Mandatory']:
            errors.append('validate_ShippingCompany_and_Ref_Num_Mandatory')
            print(f"DEBUG validate_record: Added validate_ShippingCompany_and_Ref_Num_Mandatory to errors list")
    except Exception as e:
        print(f"ERROR validate_record: validate_ShippingCompany_and_Ref_Num_Mandatory failed with error: {str(e)}")
        rule_results['validate_ShippingCompany_and_Ref_Num_Mandatory'] = False
        errors.append(f'validate_ShippingCompany_and_Ref_Num_Mandatory (error: {str(e)})')
    if errors:
        is_valid = False
        print(f"DEBUG validate_record: Record INVALID due to errors: {errors}")
    else:
        print(f"DEBUG validate_record: Record VALID - all rules passed")
    print(f"DEBUG validate_record: Final result - is_valid: {is_valid}, errors: {errors}")
    return {'is_valid': is_valid, 'errors': errors, 'rule_results': rule_results}

def validate_dataframe(df):
    '''Validate all records in a DataFrame'''
    valid_idx = []
    invalid_idx = []
    validation_results = []
    for idx, row in df.iterrows():
        result = validate_record(row)
        result['index'] = idx
        validation_results.append(result)
        if result['is_valid']:
            valid_idx.append(idx)
        else:
            invalid_idx.append(idx)
    valid_df = df.loc[valid_idx].copy()
    invalid_df = df.loc[invalid_idx].copy()
    return valid_df, invalid_df, validation_results
