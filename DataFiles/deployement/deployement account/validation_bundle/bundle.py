# Auto-generated validation bundle
import pandas as pd


def validate_Updating_Account_Type_Not_Allowed(df):
    """
    Validation Rule: Updating_Account_Type_Not_Allowed
    Salesforce Object: Account
    Field: , , , , , , , , , , , , , 
    Apex Formula:
    NOT(ISNEW()) &&  (  NOT(ISNULL( EDI_Reference_Code__c )) && NOT(ISBLANK(EDI_Reference_Code__c))) &&
ISCHANGED( WOD_2__Warranty_Account_Type__c ) && NOT(ISPICKVAL(WOD_2__Warranty_Account_Type__c,'Supplier'))
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results
    """
    # Python equivalent:
    # - NOT(ISNEW()): Assume all rows are not new (True) unless you have a column indicating new records.
    # - NOT(ISNULL(EDI_Reference_Code__c)) && NOT(ISBLANK(EDI_Reference_Code__c)):
    #   EDI_Reference_Code__c is not None and not empty string
    # - ISCHANGED(WOD_2__Warranty_Account_Type__c): Needs a boolean column 'WOD_2__Warranty_Account_Type__c_changed'
    # - NOT(ISPICKVAL(WOD_2__Warranty_Account_Type__c,'Supplier')): value != 'Supplier'
    # If you don't have 'changed' info, this will always be False.
    return (
        df['EDI_Reference_Code__c'].notna() &
        (df['EDI_Reference_Code__c'] != '') &
        df.get('WOD_2__Warranty_Account_Type__c_changed', False) &
        (df['WOD_2__Warranty_Account_Type__c'] != 'Supplier')
    )
