import pandas as pd
from bundle import *
import tkinter as tk
from tkinter import filedialog

def select_file():
    root = tk.Tk()
    root.withdraw()  # Hide the root window

    file_path = filedialog.askopenfilename(
        title="Select data file",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
    )

    print("Selected file:", file_path)
    return file_path


def validate_all(data_csv):
    """
    Validates all records in data_csv using all validation functions
    Returns a DataFrame with validation results
    """
    df = pd.read_csv(data_csv)
    df = df.fillna('')  # Fill NaN values with empty strings
    results = pd.DataFrame(index=df.index)
    
    # Apply each validation function
    results['validate_CampaignMachineAgeLimit'] = validate_CampaignMachineAgeLimit(df)
    results['validate_CampaignUsageLimit'] = validate_CampaignUsageLimit(df)
    results['validate_Comments_are_Mandatory'] = validate_Comments_are_Mandatory(df)
    results['validate_MC_PC_FAILUREDATE_LESSOREQUAL_TODAY'] = validate_MC_PC_FAILUREDATE_LESSOREQUAL_TODAY(df)
    results['validate_Out_of_warranty_on_Parts_Claim'] = validate_Out_of_warranty_on_Parts_Claim(df)
    results['validate_Unit_Usage_Flow_Validation'] = validate_Unit_Usage_Flow_Validation(df)
    results['validate_OSD_RECEIVEDATE_LESS_TODAY'] = validate_OSD_RECEIVEDATE_LESS_TODAY(df)
    results['validate_PREAUTH_EXPIRY_DATE_CHECK'] = validate_PREAUTH_EXPIRY_DATE_CHECK(df)
    results['validate_PREAUTH_FULFILLED_CHECK'] = validate_PREAUTH_FULFILLED_CHECK(df)
    results['validate_CLM_NonSerializedPartCannotHaveSerialNo'] = validate_CLM_NonSerializedPartCannotHaveSerialNo(df)
    results['validate_GW_REASON_MANDATORY'] = validate_GW_REASON_MANDATORY(df)
    results['validate_MC_PC_ACCOUNT_MANDATORY'] = validate_MC_PC_ACCOUNT_MANDATORY(df)
    results['validate_MC_PC_CAUSAL_MANDATORY'] = validate_MC_PC_CAUSAL_MANDATORY(df)
    results['validate_MC_PC_CAUSAL_PART_SNO_MANDATORY'] = validate_MC_PC_CAUSAL_PART_SNO_MANDATORY(df)
    results['validate_MC_PC_FAILUREDATE_LESS_REPAIRDATE'] = validate_MC_PC_FAILUREDATE_LESS_REPAIRDATE(df)
    results['validate_MC_PC_FAILUREDATE_MANDATORY'] = validate_MC_PC_FAILUREDATE_MANDATORY(df)
    results['validate_MC_PC_INVENTORY_MANDATORY'] = validate_MC_PC_INVENTORY_MANDATORY(df)
    results['validate_MC_PC_PRE_AUTH_COMMENTS_MANDATORY'] = validate_MC_PC_PRE_AUTH_COMMENTS_MANDATORY(df)
    results['validate_MC_PC_PRE_AUTH_REASON_MANDATORY'] = validate_MC_PC_PRE_AUTH_REASON_MANDATORY(df)
    results['validate_MC_PC_REPAIRDATE_MANDATORY'] = validate_MC_PC_REPAIRDATE_MANDATORY(df)
    results['validate_MC_PurchaseDate_Less_REPAIRDATE_FAILURE'] = validate_MC_PurchaseDate_Less_REPAIRDATE_FAILURE(df)
    results['validate_PC_PART_MANDATORY'] = validate_PC_PART_MANDATORY(df)
    results['validate_PC_PART_SNO_MANDATORY'] = validate_PC_PART_SNO_MANDATORY(df)
    results['validate_PC_PURCHASEDATE_MANDATORY'] = validate_PC_PURCHASEDATE_MANDATORY(df)
    results['validate_MC_PC_CAUSAL_CLAIM_TEMPLATE_MANDATORY'] = validate_MC_PC_CAUSAL_CLAIM_TEMPLATE_MANDATORY(df)
    results['validate_BU_Authorization'] = validate_BU_Authorization(df)
    results['validate_Mandatory_Failure_Information_fields'] = validate_Mandatory_Failure_Information_fields(df)
    results['validate_Parts_claim_sub_type_madnatory_for_CE'] = validate_Parts_claim_sub_type_madnatory_for_CE(df)
    results['validate_Unit_is_Scrapped'] = validate_Unit_is_Scrapped(df)
    results['validate_Unit_is_Stolen'] = validate_Unit_is_Stolen(df)
    results['validate_Usage_Limit_on_Service_Campaign'] = validate_Usage_Limit_on_Service_Campaign(df)
    results['validate_repair_date_cant_be_in_feature'] = validate_repair_date_cant_be_in_feature(df)
    results['validate_Warranty_Coverage_Check_for_Camp_Claims'] = validate_Warranty_Coverage_Check_for_Camp_Claims(df)
    
    # Add summary column
    results['is_valid'] = results.all(axis=1)
    df['is_valid'] = results['is_valid']
    # Add 'issue' column: validation name if failed, else empty string
    failed_cols = [col for col in results.columns if col != 'is_valid']
    df['issue'] = results[failed_cols].apply(lambda row: ', '.join([col for col in failed_cols if not row[col]]), axis=1)
    df.to_csv('validData.csv', index=False)  # Save results back to CSV
    return results

if __name__ == "__main__":
    data_csv = select_file()
    results = validate_all(data_csv)
    print("Validation Results:")
    print(results)
    print(f"\nTotal records: {len(results)}")
    print(f"Valid records: {results['is_valid'].sum()}")
    print(f"Invalid records: {len(results) - results['is_valid'].sum()}")
