# Auto-generated validation bundle
import pandas as pd


def validate_Units_of_Measure_Validation(df):
    """
    Validation Rule: Units_of_Measure_Validation
    Salesforce Object: Warranty_Product
    Field: , , , , , , , , , , , , , , , , , , , , , , , , , , , , , 
    Apex Formula:
    IF( 
				OR(
								 		ISPICKVAL(WOD_2__Units_Of_Measure__c,''),
									ISPICKVAL(WOD_2__Units_Of_Measure__c,'EA'),
								ISPICKVAL(WOD_2__Units_Of_Measure__c,'Gallons'),
								ISPICKVAL(WOD_2__Units_Of_Measure__c,'Miles'),
								ISPICKVAL(WOD_2__Units_Of_Measure__c,'Hours'),
								ISPICKVAL(WOD_2__Units_Of_Measure__c,'MIT'),
								ISPICKVAL(WOD_2__Units_Of_Measure__c,'H'),
								ISPICKVAL(WOD_2__Units_Of_Measure__c,'GAL'),
								ISPICKVAL(WOD_2__Units_Of_Measure__c,'M')
						)  
				, 
	   FALSE,
				TRUE			
	)
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results
    """
    allowed_values = [
        '', 'EA', 'Gallons', 'Miles', 'Hours', 'MIT', 'H', 'GAL', 'M'
    ]
    col = df['WOD_2__Units_Of_Measure__c'].fillna('')
    return col.isin(allowed_values)
