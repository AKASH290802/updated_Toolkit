org = ['fcs2', 'dinesh','deployement']

def org_select():
    print(f"Available Salesforce organizations: {org}")
    select_org = input("Enter the org name: ").lower()
    if select_org not in org:
        raise Exception(f"Invalid Salesforce organization: {select_org}")
    else:
        print(f"Valid Salesforce organization: {select_org}")
    return select_org
