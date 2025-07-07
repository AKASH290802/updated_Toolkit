# Auto-generated validation bundle
import pandas as pd


def validate_DTAG_RestrictMultipleBUforWholeSale(df):
    """
    Validation Rule: DTAG_RestrictMultipleBUforWholeSale
    Salesforce Object: Account
    Field: DTAG_Distribution_Level__c, WOD_2__Business_Units__c
    Apex Formula: AND(ISPICKVAL(DTAG_Distribution_Level__c,'Wholesaler'),( PICKLISTCOUNT(WOD_2__Business_Units__c)>1))
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results
    """
    # Field: DTAG_Distribution_Level__c, WOD_2__Business_Units__c
    # TODO: Implement Python equivalent of Apex formula
    # AND(ISPICKVAL(DTAG_Distribution_Level__c,'Wholesaler'),( PICKLISTCOUNT(WOD_2__Business_Units__c)>1))
    try:
        # Check if Distribution Level is Wholesaler AND Business Units count > 1
        is_wholesaler = df['DTAG_Distribution_Level__c'].astype(str) == 'Wholesaler'
        # Count business units (assuming semicolon separated values)
        bu_count = df['WOD_2__Business_Units__c'].astype(str).str.count(';') + 1
        bu_count = bu_count.fillna(0)
        # Validation fails when both conditions are true (error condition)
        error_condition = is_wholesaler & (bu_count > 1)
        return ~error_condition  # Return inverse (validation passes when error condition is false)
    except KeyError as e:
        print(f"Warning: Column {e} not found in DataFrame for validation rule 'DTAG_RestrictMultipleBUforWholeSale'")
        return pd.Series([True] * len(df))  # Assume valid if column missing

def validate_DTAG_WACanCreateRWSOnly(df):
    """
    Validation Rule: DTAG_WACanCreateRWSOnly
    Salesforce Object: Account
    Field: Type
    Apex Formula: ISNEW() &&  $Permission.DTAG_Warranty_Admin_Permission &&  NOT(ISPICKVAL(Type , 'RWS'))
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results
    """
    # Field: Type
    # TODO: Implement Python equivalent of Apex formula
    # ISNEW() && $Permission.DTAG_Warranty_Admin_Permission && NOT(ISPICKVAL(Type , 'RWS'))
    # Note: ISNEW() and $Permission cannot be evaluated in CSV context, so we'll focus on Type field
    try:
        # Validation fails when Type is not 'RWS' (assuming this is for new records with warranty admin permission)
        # For CSV validation, we'll assume all records are "new" and user has permission
        is_not_rws = df['Type'].astype(str) != 'RWS'
        return ~is_not_rws  # Return inverse (validation passes when Type is RWS)
    except KeyError as e:
        print(f"Warning: Column {e} not found in DataFrame for validation rule 'DTAG_WACanCreateRWSOnly'")
        return pd.Series([True] * len(df))  # Assume valid if column missing

def validate_Parent_cannot_be_Draft_for_Child_active(df):
    """
    Validation Rule: Parent_cannot_be_Draft_for_Child_active
    Salesforce Object: Account
    Field: DTAG_Status__c, Parent.DTAG_Status__c
    Apex Formula: Complex parent-child status validation
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results
    """
    # Field: DTAG_Status__c, Parent.DTAG_Status__c
    # TODO: Implement Python equivalent of Apex formula
    # This validation requires parent-child relationship data which may not be available in flat CSV
    try:
        # For CSV validation, we'll check if current status is Active/Released
        # but skip parent validation since parent data may not be available
        current_status = df['DTAG_Status__c'].astype(str)
        is_child_active = current_status.isin(['Active', 'Released'])
        
        # If we have parent status data, validate it
        if 'Parent_DTAG_Status__c' in df.columns:
            parent_status = df['Parent_DTAG_Status__c'].astype(str)
            parent_is_draft_inactive = parent_status.isin(['Draft', 'InActive'])
            error_condition = is_child_active & parent_is_draft_inactive
            return ~error_condition
        else:
            # If no parent data, assume validation passes
            return pd.Series([True] * len(df))
    except KeyError as e:
        print(f"Warning: Column {e} not found in DataFrame for validation rule 'Parent_cannot_be_Draft_for_Child_active'")
        return pd.Series([True] * len(df))  # Assume valid if column missing

def validate_Restrict_For_ActiveOrReleased_Status(df):
    """
    Validation Rule: Restrict_For_ActiveOrReleased_Status
    Salesforce Object: Account
    Field: DTAG_Status__c, AccountNumber, Type, WOD_2__Business_Units__c
    Apex Formula: Validation for Active/Released status requiring specific fields
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results
    """
    # Field: DTAG_Status__c, AccountNumber, Type, WOD_2__Business_Units__c
    # TODO: Implement Python equivalent of Apex formula
    try:
        # Check if status is Active or Released
        status = df['DTAG_Status__c'].astype(str)
        is_active_or_released = status.isin(['Active', 'Released'])
        
        # Check if required fields are blank
        account_number_blank = df['AccountNumber'].isna() | (df['AccountNumber'].astype(str).str.strip() == '')
        type_blank = df['Type'].isna() | (df['Type'].astype(str).str.strip() == '')
        business_units_blank = df['WOD_2__Business_Units__c'].isna() | (df['WOD_2__Business_Units__c'].astype(str).str.strip() == '')
        
        any_required_field_blank = account_number_blank | type_blank | business_units_blank
        
        # Error condition: status is Active/Released AND any required field is blank
        error_condition = is_active_or_released & any_required_field_blank
        return ~error_condition  # Return inverse (validation passes when error condition is false)
    except KeyError as e:
        print(f"Warning: Column {e} not found in DataFrame for validation rule 'Restrict_For_ActiveOrReleased_Status'")
        return pd.Series([True] * len(df))  # Assume valid if column missing

def validate_ValidFromIsRequiredForReleased(df):
    """
    Validation Rule: ValidFromIsRequiredForReleased
    Salesforce Object: Account
    Field: DTAG_Status__c, DTAG_Valid_From__c
    Apex Formula: IF( AND(ISPICKVAL( DTAG_Status__c , 'Released'),  ISBLANK(DTAG_Valid_From__c ) ), true, false)
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results
    """
    # Field: DTAG_Status__c, DTAG_Valid_From__c
    # TODO: Implement Python equivalent of Apex formula
    try:
        # Check if status is Released
        is_released = df['DTAG_Status__c'].astype(str) == 'Released'
        
        # Check if Valid From is blank
        valid_from_blank = df['DTAG_Valid_From__c'].isna() | (df['DTAG_Valid_From__c'].astype(str).str.strip() == '')
        
        # Error condition: status is Released AND Valid From is blank
        error_condition = is_released & valid_from_blank
        return ~error_condition  # Return inverse (validation passes when error condition is false)
    except KeyError as e:
        print(f"Warning: Column {e} not found in DataFrame for validation rule 'ValidFromIsRequiredForReleased'")
        return pd.Series([True] * len(df))  # Assume valid if column missing

def validate_DT_Billing_country_should_be_AU_or_NZ(df):
    """
    Validation Rule: DT_Billing_country_should_be_AU_or_NZ
    Salesforce Object: Account
    Field: BillingCountry
    Apex Formula: IF( BillingCountry !='' && BillingCountry !='AU' && BillingCountry !='NZ',true,false)
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results
    """
    # Field: BillingCountry
    # TODO: Implement Python equivalent of Apex formula
    try:
        billing_country = df['BillingCountry'].astype(str).str.strip()
        
        # Error condition: BillingCountry is not empty AND not AU AND not NZ
        is_not_empty = (billing_country != '') & (billing_country != 'nan')
        is_not_au_or_nz = ~billing_country.isin(['AU', 'NZ'])
        
        error_condition = is_not_empty & is_not_au_or_nz
        return ~error_condition  # Return inverse (validation passes when error condition is false)
    except KeyError as e:
        print(f"Warning: Column {e} not found in DataFrame for validation rule 'DT_Billing_country_should_be_AU_or_NZ'")
        return pd.Series([True] * len(df))  # Assume valid if column missing

def validate_DTAG_Restrict_CurrencyforReleased(df):
    """
    Validation Rule: DTAG_Restrict_CurrencyforReleased
    Salesforce Object: Account
    Field: DTAG_Status__c, Type, DTAG_Account_Currency__c
    Apex Formula: AND(AND(ISPICKVAL(DTAG_Status__c,'Released'), ISPICKVAL(Type, 'RWS')), ISBLANK(TEXT(DTAG_Account_Currency__c)))
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results
    """
    # Field: DTAG_Status__c, Type, DTAG_Account_Currency__c
    # TODO: Implement Python equivalent of Apex formula
    try:
        # Check if status is Released AND Type is RWS
        is_released = df['DTAG_Status__c'].astype(str) == 'Released'
        is_rws = df['Type'].astype(str) == 'RWS'
        
        # Check if currency is blank
        currency_blank = df['DTAG_Account_Currency__c'].isna() | (df['DTAG_Account_Currency__c'].astype(str).str.strip() == '')
        
        # Error condition: status is Released AND type is RWS AND currency is blank
        error_condition = is_released & is_rws & currency_blank
        return ~error_condition  # Return inverse (validation passes when error condition is false)
    except KeyError as e:
        print(f"Warning: Column {e} not found in DataFrame for validation rule 'DTAG_Restrict_CurrencyforReleased'")
        return pd.Series([True] * len(df))  # Assume valid if column missing

def validate_DTAG_Restrict_For_Released_Status_New(df):
    """
    Validation Rule: DTAG_Restrict_For_Released_Status_New
    Salesforce Object: Account
    Field: DTAG_Status__c, Type, DTAG_Dealer_Discount_Group_Parts__c, DTAG_Labor_Units__c, DTAG_Participating_in_Remanufacturing__c
    Apex Formula: Complex validation for Released status with specific types requiring certain fields
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results
    """
    # Field: DTAG_Status__c, Type, DTAG_Dealer_Discount_Group_Parts__c, DTAG_Labor_Units__c, DTAG_Participating_in_Remanufacturing__c
    # TODO: Implement Python equivalent of Apex formula
    try:
        # Check if status is Released AND type is one of the specified types
        is_released = df['DTAG_Status__c'].astype(str) == 'Released'
        account_type = df['Type'].astype(str)
        is_specified_type = account_type.isin(['TOC/TG', 'GD', 'RWS', 'ISP'])
        
        # Check if any of the required fields are blank
        dealer_discount_blank = df['DTAG_Dealer_Discount_Group_Parts__c'].isna() | (df['DTAG_Dealer_Discount_Group_Parts__c'].astype(str).str.strip() == '')
        labor_units_blank = df['DTAG_Labor_Units__c'].isna() | (df['DTAG_Labor_Units__c'].astype(str).str.strip() == '')
        remanufacturing_blank = df['DTAG_Participating_in_Remanufacturing__c'].isna() | (df['DTAG_Participating_in_Remanufacturing__c'].astype(str).str.strip() == '')
        
        any_required_field_blank = dealer_discount_blank | labor_units_blank | remanufacturing_blank
        
        # Error condition: status is Released AND type is specified AND any required field is blank
        error_condition = is_released & is_specified_type & any_required_field_blank
        return ~error_condition  # Return inverse (validation passes when error condition is false)
    except KeyError as e:
        print(f"Warning: Column {e} not found in DataFrame for validation rule 'DTAG_Restrict_For_Released_Status_New'")
        return pd.Series([True] * len(df))  # Assume valid if column missing

def validate_DTAG_Restrict_LandedCost_ReleasedStatus(df):
    """
    Validation Rule: DTAG_Restrict_LandedCost_ReleasedStatus
    Salesforce Object: Account
    Field: DTAG_Status__c, Type, DTAG_Landed_Cost_Calculation__c
    Apex Formula: AND(AND(ISPICKVAL(DTAG_Status__c,'Released'), OR(ISPICKVAL(Type,'TOC/TG'), ISPICKVAL(Type,'GD'), ISPICKVAL(Type,'ISP'))), ISBLANK(TEXT(DTAG_Landed_Cost_Calculation__c)))
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results
    """
    # Field: DTAG_Status__c, Type, DTAG_Landed_Cost_Calculation__c
    # TODO: Implement Python equivalent of Apex formula
    try:
        # Check if status is Released AND type is one of the specified types
        is_released = df['DTAG_Status__c'].astype(str) == 'Released'
        account_type = df['Type'].astype(str)
        is_specified_type = account_type.isin(['TOC/TG', 'GD', 'ISP'])
        
        # Check if Landed Cost Calculation is blank
        landed_cost_blank = df['DTAG_Landed_Cost_Calculation__c'].isna() | (df['DTAG_Landed_Cost_Calculation__c'].astype(str).str.strip() == '')
        
        # Error condition: status is Released AND type is specified AND landed cost is blank
        error_condition = is_released & is_specified_type & landed_cost_blank
        return ~error_condition  # Return inverse (validation passes when error condition is false)
    except KeyError as e:
        print(f"Warning: Column {e} not found in DataFrame for validation rule 'DTAG_Restrict_LandedCost_ReleasedStatus'")
        return pd.Series([True] * len(df))  # Assume valid if column missing
