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


def validate_record(row):
    '''Validate a single record (row) and return result dict'''
    import pandas as pd
    df = pd.DataFrame([row])
    rule_results = {}
    errors = []
    is_valid = True
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
