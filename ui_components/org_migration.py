"""
Org Migration Module - Salesforce to Salesforce Data Migration
Handles data migration between two Salesforce orgs with parent-child relationship resolution
"""

import streamlit as st
import pandas as pd
import json
import os
import io
import time
from datetime import datetime
from pathlib import Path
from simple_salesforce import Salesforce
from typing import Dict, List, Tuple, Optional, Any
from ui_components.soql_lookup_discovery import show_soql_lookup_discovery_ui
from dataload.lookup_resolver import get_candidate_fields_for_lookup
from ui_components.org_migration_rules import validate_business_rules, display_rules_validation_report, apply_rule_fixes_suggestions
from ui_components.org_migration_validation_rules import validate_data_against_validation_rules, display_validation_rules_report
from ui_components.org_migration_salesforce_validation_rules import validate_data_against_salesforce_rules, display_salesforce_validation_rules_report

def extract_detailed_error_message(error_obj: Any) -> str:
    """
    Extract detailed error message from Salesforce bulk API error response
    
    Salesforce returns errors in various formats:
    - Simple string: "error message"
    - List of strings: ["error1", "error2"]
    - Dict with message: {"message": "error", "statusCode": "400"}
    - Dict with fields: {"fields": [...], "message": "error"}
    - Complex nested structures with validation errors
    
    Args:
        error_obj: Error object from Salesforce bulk API response
    
    Returns:
        Detailed error message string
    """
    if error_obj is None:
        return "Unknown error - no error details provided"
    
    # If it's a simple string
    if isinstance(error_obj, str):
        return error_obj if error_obj.strip() else "Unknown error"
    
    # If it's a list of errors
    if isinstance(error_obj, list):
        error_messages = []
        for item in error_obj:
            if isinstance(item, dict):
                # Handle dict items in list
                msg = item.get('message', item.get('error', str(item)))
                error_messages.append(msg)
            else:
                error_messages.append(str(item))
        return " | ".join(filter(None, error_messages)) if error_messages else "Unknown error"
    
    # If it's a dictionary
    if isinstance(error_obj, dict):
        error_parts = []
        
        # Try to get message field
        if 'message' in error_obj:
            error_parts.append(error_obj['message'])
        
        # Try to get error field
        if 'error' in error_obj and error_obj['error'] != error_obj.get('message'):
            error_parts.append(error_obj['error'])
        
        # Try to get statusCode and message together
        if 'statusCode' in error_obj and error_obj['statusCode'] != 200:
            status = error_obj['statusCode']
            if status == 'REQUIRED_FIELD_MISSING':
                error_parts.append("Required field is missing")
            elif status == 'INVALID_FIELD_VALUE':
                error_parts.append("Invalid field value provided")
            elif status == 'INVALID_CROSS_REFERENCE_KEY':
                error_parts.append("Invalid lookup reference (parent record not found or invalid)")
            elif isinstance(status, int) and status >= 400:
                error_parts.append(f"HTTP Error {status}")
            else:
                error_parts.append(f"Error Code: {status}")
        
        # Try to get fields with errors
        if 'fields' in error_obj:
            fields_errors = error_obj['fields']
            if isinstance(fields_errors, list):
                error_parts.append(f"Fields with errors: {', '.join(fields_errors)}")
            else:
                error_parts.append(f"Field error: {fields_errors}")
        
        # Try to get errors array (sometimes nested under different key)
        if 'errors' in error_obj and isinstance(error_obj['errors'], list):
            for err in error_obj['errors']:
                if isinstance(err, dict):
                    err_msg = err.get('message', err.get('error', str(err)))
                    error_parts.append(err_msg)
                else:
                    error_parts.append(str(err))
        
        if error_parts:
            return " | ".join(error_parts)
    
    # Fallback: convert to string
    return str(error_obj) if error_obj else "Unknown error"

def connect_to_salesforce_org(credentials: dict, org_name: str) -> Optional[Salesforce]:
    """
    Connect to a Salesforce organization
    
    Args:
        credentials: Credentials dictionary
        org_name: Name of the organization
    
    Returns:
        Salesforce connection object or None
    """
    try:
        org_creds = credentials.get(org_name, {})
        
        sf_conn = Salesforce(
            username=org_creds['username'],
            password=org_creds['password'],
            security_token=org_creds['security_token'],
            domain=org_creds.get('domain', 'login')
        )
        
        return sf_conn
    except Exception as e:
        st.error(f"❌ Failed to connect to {org_name}: {str(e)}")
        return None


def get_object_fields(sf_conn: Salesforce, object_name: str) -> Dict[str, Any]:
    """
    Get all fields for a Salesforce object with metadata
    
    Args:
        sf_conn: Salesforce connection
        object_name: Name of the Salesforce object
    
    Returns:
        Dictionary of field metadata
    """
    try:
        describe_result = getattr(sf_conn, object_name).describe()
        fields_info = {}
        
        for field in describe_result['fields']:
            fields_info[field['name']] = {
                'label': field['label'],
                'type': field['type'],
                'referenceTo': field.get('referenceTo', []),
                'externalId': field.get('externalId', False),
                'unique': field.get('unique', False),
                'createable': field.get('createable', False),
                'updateable': field.get('updateable', False),
                'nillable': field.get('nillable', True),
                'picklistValues': field.get('picklistValues', [])
            }
        
        return fields_info
    except Exception as e:
        st.error(f"Error retrieving fields for {object_name}: {str(e)}")
        return {}


def identify_external_id_fields(fields_info: Dict) -> List[str]:
    """
    Identify External ID fields in an object
    
    Args:
        fields_info: Field metadata dictionary
    
    Returns:
        List of External ID field names
    """
    external_id_fields = []
    for field_name, field_meta in fields_info.items():
        if field_meta.get('externalId', False):
            external_id_fields.append(field_name)
    
    return external_id_fields


def identify_unique_fields(fields_info: Dict) -> List[str]:
    """
    Identify unique fields in an object (excluding External IDs)
    
    Args:
        fields_info: Field metadata dictionary
    
    Returns:
        List of unique field names
    """
    unique_fields = []
    for field_name, field_meta in fields_info.items():
        if field_meta.get('unique', False) and not field_meta.get('externalId', False):
            unique_fields.append(field_name)
    
    return unique_fields


def identify_lookup_fields(fields_info: Dict, include_system_fields: bool = False) -> List[Dict]:
    """
    Identify lookup/reference fields in an object
    
    Args:
        fields_info: Field metadata dictionary
        include_system_fields: Whether to include system lookup fields (OwnerId, CreatedById, etc.)
    
    Returns:
        List of lookup field information
    """
    # System fields that are typically handled automatically by Salesforce
    system_lookup_fields = {
        'OwnerId',           # Record owner - usually preserved or set to current user
        'CreatedById',       # System-managed, cannot be set during migration
        'LastModifiedById',  # System-managed, cannot be set during migration
        'RecordTypeId',      # Usually handled separately or set as default
        'MasterRecordId',    # Merge tracking - not meaningful for migration
        'LastActivityDate',  # System-calculated
        'LastViewedDate',    # System-managed
        'LastReferencedDate' # System-managed
    }
    
    lookup_fields = []
    system_fields = []
    
    for field_name, field_meta in fields_info.items():
        if field_meta['type'] in ['reference', 'lookup', 'masterdetail'] and field_meta.get('referenceTo'):
            field_info = {
                'field_name': field_name,
                'reference_to': field_meta['referenceTo'],
                'type': field_meta['type'],
                'is_system': field_name in system_lookup_fields
            }
            
            if field_name in system_lookup_fields:
                system_fields.append(field_info)
            else:
                lookup_fields.append(field_info)
    
    # Return based on parameter
    if include_system_fields:
        return lookup_fields + system_fields
    else:
        return lookup_fields


def identify_master_detail_fields(fields_info: Dict) -> List[Dict]:
    """
    Identify ONLY Master-Detail fields (different from generic lookups)
    
    Master-Detail relationships have CRITICAL properties:
    - ALWAYS Required (cannot be NULL)
    - Cascading Delete: deleting parent deletes all children
    - Child inherits parent's Record Type
    - Child's sharing = parent's sharing
    
    Args:
        fields_info: Field metadata dictionary
    
    Returns:
        List of Master-Detail field information with special properties
    """
    master_detail_fields = []
    
    for field_name, field_meta in fields_info.items():
        if field_meta['type'] == 'masterdetail' and field_meta.get('referenceTo'):
            md_field_info = {
                'field_name': field_name,
                'parent_object': field_meta['referenceTo'][0],
                'field_type': 'masterdetail',
                'is_required': True,  # Master-Detail ALWAYS required
                'is_nillable': False,  # Cannot be NULL
                'cascading_delete': True,  # Inherent property
                'inherits_record_type': True,  # Child inherits parent's RT
                'can_be_external_id': False,  # Master-Detail cannot be External ID
                'label': field_meta.get('label', field_name),
                'reference_to': field_meta['referenceTo']
            }
            master_detail_fields.append(md_field_info)
    
    return master_detail_fields


def validate_master_detail_parents_exist(
    source_df: pd.DataFrame,
    target_sf: Salesforce,
    master_detail_configs: Dict,
    progress_callback=None
) -> Dict:
    """
    PRE-MIGRATION VALIDATION: Check if all parent records exist in TARGET org
    
    CRITICAL: Master-Detail children CANNOT be created without existing parents.
    If parents don't exist, migration will FAIL for those records.
    
    Args:
        source_df: Source org data
        target_sf: Target Salesforce connection
        master_detail_configs: Master-Detail resolution configurations
        progress_callback: Optional callback for progress updates
    
    Returns:
        Validation report with:
        - total_parents: Number of unique parent references
        - found: Count of parents found in target org
        - missing: Count of missing parents
        - missing_ids: List of missing parent IDs
        - blocking: Whether any missing parents will BLOCK migration
    """
    validation_results = {
        'overall_status': 'PASS',
        'critical_issues': 0,
        'details': {}
    }
    
    for md_field, config in master_detail_configs.items():
        parent_object = config.get('parent_object')
        if not parent_object:
            continue
        
        # Get unique parent values from source
        if md_field not in source_df.columns:
            continue
        
        unique_parents = source_df[md_field].dropna().unique()
        
        if progress_callback:
            progress_callback(f"Validating {md_field} → {parent_object} ({len(unique_parents)} unique parents)...")
        
        found_count = 0
        missing_parents = []
        errors = []
        
        for parent_value in unique_parents:
            try:
                # Query target org for parent
                query = f"SELECT Id FROM {parent_object} WHERE Id = '{parent_value}' LIMIT 1"
                result = target_sf.query(query)
                
                if result['totalSize'] > 0:
                    found_count += 1
                else:
                    missing_parents.append(str(parent_value))
            except Exception as e:
                errors.append(str(e))
        
        field_validation = {
            'parent_object': parent_object,
            'total_parents': len(unique_parents),
            'found': found_count,
            'missing': len(missing_parents),
            'missing_ids': missing_parents,
            'errors': errors,
            'status': 'PASS' if len(missing_parents) == 0 else 'FAIL'
        }
        
        validation_results['details'][md_field] = field_validation
        
        # Master-Detail is BLOCKING
        if len(missing_parents) > 0:
            validation_results['overall_status'] = 'FAIL'
            validation_results['critical_issues'] += len(missing_parents)
    
    return validation_results


def check_master_detail_record_type_compatibility(
    source_df: pd.DataFrame,
    target_sf: Salesforce,
    master_detail_configs: Dict,
    record_type_mapping: Dict = None,
    progress_callback=None
) -> Dict:
    """
    Check Record Type compatibility for Master-Detail relationships
    
    In Salesforce, Master-Detail children often INHERIT or must match parent's Record Type.
    This validates that the Record Types are compatible.
    
    Args:
        source_df: Source org data
        target_sf: Target Salesforce connection
        master_detail_configs: Master-Detail configurations
        record_type_mapping: Optional mapping of source RT IDs to target RT IDs
        progress_callback: Optional callback for progress updates
    
    Returns:
        Compatibility report with Record Type issues
    """
    compatibility_results = {
        'compatible': 0,
        'incompatible': 0,
        'warnings': [],
        'issues': {}
    }
    
    # This is a simplified check - actual implementation depends on target org setup
    # For now, we flag that Record Type inheritance should be verified
    compatibility_results['warnings'].append(
        "⚠️ Master-Detail children inherit/must match parent Record Type. "
        "Ensure parent Record Types are migrated first and child Record Types are compatible."
    )
    
    return compatibility_results


def resolve_master_detail_relationships_for_migration(
    source_df: pd.DataFrame,
    source_sf: Salesforce,
    master_detail_configs: Dict,
    progress_callback=None,
    strict_mode: bool = True
) -> Tuple[pd.DataFrame, Dict]:
    """
    Resolve Master-Detail relationships with STRICT error handling
    
    **KEY LOGIC**: Query SOURCE org to find parent record IDs, same as data loading.
    
    Unlike Lookups (optional), Master-Detail relationships are MANDATORY.
    If parent not found → child record creation FAILS.
    
    STRICT MODE (default): Fails migration if ANY parent is missing
    PERMISSIVE MODE: Logs warnings but continues (child records with NULL will fail at upload)
    
    Args:
        source_df: DataFrame with source data
        source_sf: Source Salesforce connection
        master_detail_configs: Master-Detail resolution configs
        progress_callback: Optional callback for progress updates
        strict_mode: If True, fail fast when parent not found. If False, continue but warn.
    
    Returns:
        Tuple of (resolved_df, resolution_stats)
        resolution_stats includes:
        - 'unresolved_critical': List of records that CANNOT be migrated
        - 'blocking_issues': Count of records that will fail
    """
    resolved_df = source_df.copy()
    resolution_stats = {
        'total_md_fields': len(master_detail_configs),
        'successfully_resolved': {},
        'unresolved_critical': {},  # BLOCKING issues
        'warnings': [],
        'errors': [],
        'blocking_count': 0
    }
    
    for md_field, config in master_detail_configs.items():
        parent_object = config['parent_object']
        match_strategy = config['match_strategy']
        match_fields = config['match_fields']
        
        if progress_callback:
            progress_callback(f"Resolving Master-Detail: {md_field} → {parent_object}...")
        
        resolved_count = 0
        unresolved_count = 0
        unresolved_records = []
        target_ids = []
        
        for idx, row in resolved_df.iterrows():
            match_values = {field: row.get(field) for field in match_fields}
            
            # Query SOURCE org for parent ID
            source_parent_id = query_source_org_for_parent_id(
                source_sf=source_sf,
                parent_object=parent_object,
                match_strategy=match_strategy,
                match_fields=match_fields,
                match_values=match_values,
                concat_separator=config.get('concat_separator', '_')
            )
            
            if source_parent_id:
                target_ids.append(source_parent_id)
                resolved_count += 1
            else:
                target_ids.append(None)
                unresolved_count += 1
                unresolved_records.append(idx)
                
                if strict_mode:
                    error_msg = f"Row {idx}: Cannot resolve Master-Detail {md_field} - Parent not found in TARGET {parent_object}"
                    resolution_stats['errors'].append(error_msg)
        
        # Update DataFrame
        resolved_df[md_field] = target_ids
        
        # Track statistics
        resolution_stats['successfully_resolved'][md_field] = resolved_count
        resolution_stats['unresolved_critical'][md_field] = {
            'count': unresolved_count,
            'record_indices': unresolved_records,
            'status': 'BLOCKING'  # Master-Detail cannot be NULL
        }
        
        if unresolved_count > 0:
            resolution_stats['blocking_count'] += unresolved_count
            msg = f"🚫 CRITICAL: {md_field} has {unresolved_count} unresolved parents. Child records CANNOT be created."
            resolution_stats['warnings'].append(msg)
    
    return resolved_df, resolution_stats


def check_record_exists_in_target(
    target_sf: Salesforce,
    object_name: str,
    match_strategy: str,
    match_fields: List[str],
    record_values: Dict[str, Any],
    concat_separator: str = '_'
) -> Tuple[bool, Optional[str]]:
    """
    Check if a record already exists in target org based on matching strategy
    
    **PURPOSE**: During field mapping, check if records matching the selected
    External ID/combination/concatenation already exist in target org
    
    Args:
        target_sf: Target Salesforce connection
        object_name: Salesforce object name
        match_strategy: 'external_id' | 'field_combination' | 'field_concatenation'
        match_fields: List of fields to match on
        record_values: Dictionary of field values to check
        concat_separator: Separator for concatenation strategy
    
    Returns:
        Tuple of (exists: bool, salesforce_id: Optional[str])
    """
    try:
        # Get field metadata to know which fields are numbers/dates/booleans
        try:
            object_fields = get_object_fields(target_sf, object_name)
        except:
            object_fields = {}
        
        def format_value_for_soql(field_name: str, value: Any) -> str:
            """Format value based on field type for SOQL query"""
            if not value or (isinstance(value, str) and value.strip() == ''):
                return None
            
            # Check field type from metadata
            field_meta = object_fields.get(field_name, {})
            field_type = field_meta.get('type', 'string').lower()
            
            # Convert value to proper SOQL format
            if field_type in ['number', 'double', 'integer', 'percent', 'currency']:
                # Numeric fields - no quotes
                return str(value)
            elif field_type in ['date', 'datetime']:
                # Date fields - no quotes, format as YYYY-MM-DD
                return str(value)
            elif field_type in ['boolean']:
                # Boolean fields - no quotes, lowercase
                return 'true' if value else 'false'
            else:
                # String, reference, etc - quote and escape
                escaped = str(value).replace("'", "\\'")
                return f"'{escaped}'"
        
        if match_strategy == 'external_id':
            # Single External ID field
            ext_id_field = match_fields[0]
            match_value = record_values.get(ext_id_field)
            
            if not match_value or (isinstance(match_value, str) and match_value.strip() == ''):
                return False, None
            
            formatted_value = format_value_for_soql(ext_id_field, match_value)
            soql_query = f"SELECT Id FROM {object_name} WHERE {ext_id_field} = {formatted_value} LIMIT 1"
            result = target_sf.query(soql_query)
            
            if result['totalSize'] > 0:
                return True, result['records'][0]['Id']
            return False, None
        
        elif match_strategy in ['field_combination', 'field_concatenation']:
            # Both use same logic - check all fields with AND
            conditions = []
            has_all_values = True
            
            for field in match_fields:
                value = record_values.get(field)
                if not value or (isinstance(value, str) and value.strip() == ''):
                    has_all_values = False
                    break
                formatted_value = format_value_for_soql(field, value)
                if formatted_value is None:
                    has_all_values = False
                    break
                conditions.append(f"{field} = {formatted_value}")
            
            if not has_all_values:
                return False, None
            
            where_clause = ' AND '.join(conditions)
            soql_query = f"SELECT Id FROM {object_name} WHERE {where_clause} LIMIT 1"
            result = target_sf.query(soql_query)
            
            if result['totalSize'] > 0:
                return True, result['records'][0]['Id']
            return False, None
        
        return False, None
    
    except Exception as e:
        st.warning(f"⚠️ Error checking record existence: {str(e)}")
        return False, None


def validate_existing_records_in_target(
    target_sf: Salesforce,
    object_name: str,
    match_strategy: str,
    match_fields: List[str],
    source_data: pd.DataFrame,
    concat_separator: str = '_'
) -> Dict[str, Any]:
    """
    Validate how many source records already exist in target org
    
    **CRITICAL**: This shows users which records will be INSERTED (new) vs
    UPDATED (existing) based on the matching strategy
    
    Args:
        target_sf: Target Salesforce connection
        object_name: Salesforce object name
        match_strategy: Matching strategy
        match_fields: Fields to match on
        source_data: Source data DataFrame
        concat_separator: Separator for concatenation
    
    Returns:
        Dictionary with validation results
    """
    results = {
        'total_records': len(source_data),
        'existing_records': [],
        'new_records': [],
        'invalid_records': [],  # Missing match field values
        'existing_count': 0,
        'new_count': 0,
        'invalid_count': 0
    }
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, row in source_data.iterrows():
        status_text.info(f"🔍 Validating record {idx + 1}/{len(source_data)}...")
        
        # Extract match values
        match_values = {field: row.get(field) for field in match_fields}
        
        # Check if has all required values
        has_all_values = True
        for field in match_fields:
            value = match_values.get(field)
            if pd.isna(value) or (isinstance(value, str) and value.strip() == ''):
                has_all_values = False
                break
        
        if not has_all_values:
            results['invalid_records'].append({
                'index': idx,
                'reason': f"Missing values for: {', '.join(match_fields)}",
                'values': match_values
            })
            results['invalid_count'] += 1
        else:
            # Check if exists in target
            exists, sf_id = check_record_exists_in_target(
                target_sf, object_name, match_strategy, 
                match_fields, match_values, concat_separator
            )
            
            if exists:
                results['existing_records'].append({
                    'index': idx,
                    'salesforce_id': sf_id,
                    'match_values': match_values
                })
                results['existing_count'] += 1
            else:
                results['new_records'].append({
                    'index': idx,
                    'match_values': match_values
                })
                results['new_count'] += 1
        
        progress_bar.progress((idx + 1) / len(source_data))
    
    status_text.empty()
    progress_bar.empty()
    
    return results



def query_source_org_for_parent_id(
    source_sf: Salesforce,
    parent_object: str,
    match_strategy: str,
    match_fields: List[str],
    match_values: Dict[str, Any],
    concat_separator: str = '_'
) -> Optional[str]:
    """
    Query SOURCE org to find parent record ID based on matching strategy
    
    **CRITICAL LOGIC**: This queries the SOURCE org (where data comes from) to get Salesforce IDs.
    These IDs are then used in TARGET org to establish lookup references in child records.
    Same lookup resolution logic as data loading.
    
    Args:
        source_sf: Source Salesforce connection
        parent_object: Parent object name (e.g., 'Account', 'Dealer')
        match_strategy: 'external_id' | 'field_combination' | 'field_concatenation' | 'field_mapping'
        match_fields: List of field names to match on
        match_values: Dictionary of field values from source record
        concat_separator: Separator for concatenation strategy
    
    Returns:
        Salesforce ID from source org, or None if not found
    """
    try:
        # Get field metadata to know which fields are numbers/dates/booleans
        try:
            object_fields = get_object_fields(source_sf, parent_object)
        except:
            object_fields = {}
        
        def format_value_for_soql(field_name: str, value: Any) -> str:
            """Format value based on field type for SOQL query"""
            if not value or (isinstance(value, str) and value.strip() == ''):
                return None
            
            # Check field type from metadata
            field_meta = object_fields.get(field_name, {})
            field_type = field_meta.get('type', 'string').lower()
            
            # Convert value to proper SOQL format
            if field_type in ['number', 'double', 'integer', 'percent', 'currency']:
                # Numeric fields - no quotes
                return str(value)
            elif field_type in ['date', 'datetime']:
                # Date fields - no quotes, format as YYYY-MM-DD
                return str(value)
            elif field_type in ['boolean']:
                # Boolean fields - no quotes, lowercase
                return 'true' if value else 'false'
            else:
                # String, reference, etc - quote and escape
                escaped = str(value).replace("'", "\\'")
                return f"'{escaped}'"
        
        if match_strategy == 'external_id':
            # Single External ID field matching
            external_id_field = match_fields[0]
            match_value = match_values.get(external_id_field)
            
            if not match_value or (isinstance(match_value, str) and match_value.strip() == ''):
                return None
            
            # Query SOURCE org with configured external ID field
            formatted_value = format_value_for_soql(external_id_field, match_value)
            soql_query = f"SELECT Id FROM {parent_object} WHERE {external_id_field} = {formatted_value} LIMIT 1"
            
            try:
                result = source_sf.query(soql_query)
                if result['totalSize'] > 0:
                    return result['records'][0]['Id']
            except Exception as e:
                # Field doesn't exist or query failed - fall back to candidate fields
                pass
            
            # FALLBACK: Try intelligent candidate field selection from metadata
            try:
                candidate_fields = get_candidate_fields_for_lookup(
                    sf_conn=source_sf,
                    parent_object=parent_object
                )
                
                for candidate_field in candidate_fields:
                    if candidate_field == external_id_field:
                        continue  # Already tried
                    
                    try:
                        formatted_value = format_value_for_soql(candidate_field, match_value)
                        query = f"SELECT Id FROM {parent_object} WHERE {candidate_field} = {formatted_value} LIMIT 1"
                        result = source_sf.query(query)
                        if result['totalSize'] > 0:
                            return result['records'][0]['Id']
                    except:
                        continue
            except:
                pass
            
            return None
        
        elif match_strategy == 'field_combination':
            # Multiple fields combined with AND
            conditions = []
            has_all_values = True
            
            for field in match_fields:
                value = match_values.get(field)
                if not value or (isinstance(value, str) and value.strip() == ''):
                    has_all_values = False
                    break
                formatted_value = format_value_for_soql(field, value)
                if formatted_value is None:
                    has_all_values = False
                    break
                conditions.append(f"{field} = {formatted_value}")
            
            if not has_all_values:
                return None
            
            # Query SOURCE org with combined conditions
            where_clause = ' AND '.join(conditions)
            soql_query = f"SELECT Id FROM {parent_object} WHERE {where_clause} LIMIT 1"
            result = source_sf.query(soql_query)
            
            if result['totalSize'] > 0:
                return result['records'][0]['Id']
            else:
                return None
        
        elif match_strategy == 'field_concatenation':
            # Fields concatenated with separator - query by individual fields
            conditions = []
            has_all_values = True
            
            for field in match_fields:
                value = match_values.get(field)
                if not value or (isinstance(value, str) and value.strip() == ''):
                    has_all_values = False
                    break
                formatted_value = format_value_for_soql(field, value)
                if formatted_value is None:
                    has_all_values = False
                    break
                conditions.append(f"{field} = {formatted_value}")
            
            if not has_all_values:
                return None
            
            # Query SOURCE org - same as field_combination but logically represents concatenation
            where_clause = ' AND '.join(conditions)
            soql_query = f"SELECT Id FROM {parent_object} WHERE {where_clause} LIMIT 1"
            result = source_sf.query(soql_query)
            
            if result['totalSize'] > 0:
                return result['records'][0]['Id']
            else:
                return None
        
        elif match_strategy == 'field_mapping':
            # SOQL-discovered relationship fields - treat as external_id strategy
            # This handles fields discovered from SOQL queries like WOD_2__Dealer__r.Dealer_Number__c
            external_id_field = match_fields[0]
            match_value = match_values.get(external_id_field)
            
            if not match_value or (isinstance(match_value, str) and match_value.strip() == ''):
                return None
            
            # Query SOURCE org using the discovered field
            formatted_value = format_value_for_soql(external_id_field, match_value)
            soql_query = f"SELECT Id FROM {parent_object} WHERE {external_id_field} = {formatted_value} LIMIT 1"
            result = source_sf.query(soql_query)
            
            if result['totalSize'] > 0:
                return result['records'][0]['Id']
            else:
                return None
        
        else:
            return None
    
    except Exception as e:
        print(f"⚠️ Could not find parent record in source org {parent_object}: {str(e)}")
        return None


def resolve_lookup_relationships_for_migration(
    source_df: pd.DataFrame,
    source_sf: Salesforce,
    target_sf: Salesforce,
    lookup_configs: Dict[str, Dict],
    progress_callback=None
) -> Tuple[pd.DataFrame, Dict]:
    """
    Resolve lookup relationships for ORG-TO-ORG MIGRATION using 2-step process
    
    **ORG-TO-ORG MIGRATION FLOW**:
    
    For each child record with lookup field:
    1. Read the SOURCE org Salesforce ID from the lookup field (e.g., WOD_2__Dealer__c = "001xx000003DHP1")
    2. Query SOURCE org: Get the unique identifier using that ID
       - SELECT Dealer_Number__c FROM Account WHERE Id = "001xx000003DHP1"
       - Result: Dealer_Number__c = "914021"
    3. Query TARGET org: Find matching parent record using the unique identifier
       - SELECT Id FROM Account WHERE Dealer_Number__c = "914021"
       - Result: Id = "002yy000001ABCD2" (new ID in target org)
    4. Use TARGET org ID in the migrated data
    
    Args:
        source_df: DataFrame with child records (contains lookup field IDs from source org)
        source_sf: Source Salesforce connection (to extract unique identifiers)
        target_sf: Target Salesforce connection (to find new parent IDs)
        lookup_configs: Dictionary mapping lookup fields to resolution config
            Format: {
                'WOD_2__Dealer__c': {
                    'parent_object': 'Account',  # Parent object name
                    'match_strategy': 'external_id' | 'field_combination' | 'field_concatenation',
                    'match_fields': ['Dealer_Number__c']  # Unique identifier field(s) in parent
                }
            }
        progress_callback: Optional callback for progress updates
    
    Returns:
        Tuple of (resolved_df, resolution_stats)
        - resolved_df: DataFrame with lookup fields populated with parent IDs from TARGET org
        - resolution_stats: Statistics about what was resolved
    """
    resolved_df = source_df.copy()
    resolution_stats = {
        'total_lookups': len(lookup_configs),
        'resolved': {},
        'unresolved': {},
        'errors': []
    }
    
    for lookup_field, config in lookup_configs.items():
        parent_object = config['parent_object']
        match_strategy = config['match_strategy']
        match_fields = config['match_fields']  # These are the UNIQUE IDENTIFIER fields in parent
        concat_separator = config.get('concat_separator', '_')
        
        if progress_callback:
            progress_callback(f"Resolving {lookup_field} → {parent_object}...")
        
        resolved_count = 0
        unresolved_count = 0
        
        # Create new column for target org IDs
        target_ids = []
        
        for idx, row in resolved_df.iterrows():
            # STEP 1: Get the SOURCE org parent ID from the lookup field
            source_parent_id = row.get(lookup_field)
            
            if pd.isna(source_parent_id) or str(source_parent_id).strip() == '':
                target_ids.append(None)
                unresolved_count += 1
                continue
            
            source_parent_id = str(source_parent_id).strip()
            
            try:
                # STEP 2: Query SOURCE org to get unique identifier values
                # Example: SELECT Dealer_Number__c FROM Account WHERE Id = "001xx000003DHP1"
                match_fields_str = ', '.join(match_fields)
                source_query = f"SELECT {match_fields_str} FROM {parent_object} WHERE Id = '{source_parent_id}' LIMIT 1"
                
                source_result = source_sf.query(source_query)
                
                if source_result['totalSize'] == 0:
                    target_ids.append(None)
                    unresolved_count += 1
                    if progress_callback:
                        progress_callback(f"⚠️ Parent record {source_parent_id} not found in source org")
                    continue
                
                source_record = source_result['records'][0]
                
                # Extract unique identifier values from source parent record
                match_values = {}
                for field in match_fields:
                    match_values[field] = source_record.get(field)
                
                # STEP 3: Query TARGET org to find matching parent record
                # Build query based on matching strategy
                if match_strategy == 'external_id':
                    # Single field match
                    ext_id_field = match_fields[0]
                    ext_id_value = match_values[ext_id_field]
                    
                    if pd.isna(ext_id_value) or str(ext_id_value).strip() == '':
                        target_ids.append(None)
                        unresolved_count += 1
                        continue
                    
                    ext_id_value = str(ext_id_value).replace("'", "\\'")
                    target_query = f"SELECT Id FROM {parent_object} WHERE {ext_id_field} = '{ext_id_value}' LIMIT 1"
                    
                elif match_strategy in ['field_combination', 'field_concatenation']:
                    # Multiple field match (both strategies use AND condition)
                    conditions = []
                    all_values_present = True
                    
                    for field in match_fields:
                        value = match_values.get(field)
                        if pd.isna(value) or str(value).strip() == '':
                            all_values_present = False
                            break
                        value_str = str(value).replace("'", "\\'")
                        conditions.append(f"{field} = '{value_str}'")
                    
                    if not all_values_present:
                        target_ids.append(None)
                        unresolved_count += 1
                        continue
                    
                    where_clause = ' AND '.join(conditions)
                    target_query = f"SELECT Id FROM {parent_object} WHERE {where_clause} LIMIT 1"
                
                # Execute query against TARGET org
                target_result = target_sf.query(target_query)
                
                if target_result['totalSize'] > 0:
                    target_parent_id = target_result['records'][0]['Id']
                    target_ids.append(target_parent_id)
                    resolved_count += 1
                else:
                    target_ids.append(None)
                    unresolved_count += 1
                    if progress_callback:
                        progress_callback(f"⚠️ Matching record not found in target org for {lookup_field}")
            
            except Exception as e:
                target_ids.append(None)
                unresolved_count += 1
                error_msg = f"Error resolving {lookup_field}: {str(e)}"
                resolution_stats['errors'].append(error_msg)
                if progress_callback:
                    progress_callback(f"❌ {error_msg}")
        
        # Update DataFrame with target org IDs
        resolved_df[lookup_field] = target_ids
        
        # Track statistics
        resolution_stats['resolved'][lookup_field] = resolved_count
        resolution_stats['unresolved'][lookup_field] = unresolved_count
    
    return resolved_df, resolution_stats


def save_field_mapping_config(
    source_org: str,
    target_org: str,
    object_name: str,
    field_mappings: Dict[str, str],
    lookup_configs: Dict[str, Dict]
) -> str:
    """
    Save field mapping configuration to JSON file
    
    Args:
        source_org: Source organization name
        target_org: Target organization name
        object_name: Salesforce object name
        field_mappings: Source field to target field mappings
        lookup_configs: Lookup resolution configurations
    
    Returns:
        Path to saved configuration file
    """
    config_dir = Path('migration_configs')
    config_dir.mkdir(exist_ok=True)
    
    config_data = {
        'source_org': source_org,
        'target_org': target_org,
        'object': object_name,
        'created_date': datetime.now().isoformat(),
        'field_mappings': field_mappings,
        'lookup_configs': lookup_configs
    }
    
    filename = f"{source_org}_to_{target_org}_{object_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    filepath = config_dir / filename
    
    with open(filepath, 'w') as f:
        json.dump(config_data, f, indent=2)
    
    return str(filepath)


def load_field_mapping_config(filepath: str) -> Optional[Dict]:
    """
    Load field mapping configuration from JSON file
    
    Args:
        filepath: Path to configuration file
    
    Returns:
        Configuration dictionary or None
    """
    try:
        with open(filepath, 'r') as f:
            config = json.load(f)
        return config
    except Exception as e:
        st.error(f"Error loading configuration: {str(e)}")
        return None


def save_migration_execution_log(
    source_org: str,
    target_org: str,
    object_name: str,
    field_mappings: Dict[str, str],
    lookup_configs: Dict[str, Dict],
    main_match_strategy: str,
    main_match_fields: List[str],
    migration_operation: str,
    total_records: int,
    success_count: int,
    error_count: int,
    execution_time: float
) -> str:
    """
    Save migration execution history log
    
    Args:
        source_org: Source organization name
        target_org: Target organization name
        object_name: Salesforce object name
        field_mappings: Source field to target field mappings
        lookup_configs: Lookup resolution configurations
        main_match_strategy: Main object matching strategy
        main_match_fields: Fields used for matching
        migration_operation: INSERT/UPSERT/UPDATE
        total_records: Total records processed
        success_count: Successfully migrated records
        error_count: Failed records
        execution_time: Time taken in seconds
    
    Returns:
        Path to saved log file
    """
    log_dir = Path('migration_logs')
    log_dir.mkdir(exist_ok=True)
    
    log_data = {
        'source_org': source_org,
        'target_org': target_org,
        'object': object_name,
        'execution_date': datetime.now().isoformat(),
        'execution_time_seconds': round(execution_time, 2),
        'migration_operation': migration_operation,
        'main_match_strategy': main_match_strategy,
        'main_match_fields': main_match_fields,
        'field_mappings': field_mappings,
        'field_mapping_count': len(field_mappings),
        'lookup_configs': lookup_configs,
        'lookup_count': len(lookup_configs),
        'results': {
            'total_records': total_records,
            'success_count': success_count,
            'error_count': error_count,
            'success_rate': round((success_count / total_records * 100) if total_records > 0 else 0, 2)
        }
    }
    
    filename = f"{source_org}_to_{target_org}_{object_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    filepath = log_dir / filename
    
    with open(filepath, 'w') as f:
        json.dump(log_data, f, indent=2)
    
    return str(filepath)


def get_migration_history() -> List[Dict]:
    """
    Get all migration execution history logs
    
    Returns:
        List of migration history records
    """
    log_dir = Path('migration_logs')
    if not log_dir.exists():
        return []
    
    history = []
    for log_file in sorted(log_dir.glob('*.json'), reverse=True):  # Most recent first
        try:
            with open(log_file, 'r') as f:
                log_data = json.load(f)
                log_data['log_file'] = str(log_file)
                history.append(log_data)
        except Exception as e:
            print(f"Error reading log file {log_file}: {str(e)}")
    
    return history


def show_org_migration(credentials: dict):
    """
    Main function to display Org Migration interface
    
    Args:
        credentials: Dictionary of Salesforce credentials
    """
    st.title("🔄 Org Migration - Salesforce to Salesforce")
    st.markdown("---")
    
    # Initialize session state for migration
    if 'migration_source_org' not in st.session_state:
        st.session_state.migration_source_org = None
    if 'migration_target_org' not in st.session_state:
        st.session_state.migration_target_org = None
    if 'migration_object' not in st.session_state:
        st.session_state.migration_object = None
    if 'migration_field_mappings' not in st.session_state:
        st.session_state.migration_field_mappings = {}
    if 'migration_lookup_configs' not in st.session_state:
        st.session_state.migration_lookup_configs = {}
    
    # Create tabs
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
        "1️⃣ Configuration",
        "2️⃣ Field Mapping",
        "3️⃣ Pre-Migration Validation",
        "4️⃣ Business Rules",
        "5️⃣ Data Quality",
        "6️⃣ Lookup Resolution",
        "7️⃣ Data Preview",
        "8️⃣ Execute Migration",
        "📋 Migration History"
    ])
    
    # ============================================================================
    # TAB 1: CONFIGURATION
    # ============================================================================
    with tab1:
        st.subheader("📋 Migration Configuration")
        
        # Get available orgs
        available_orgs = [k for k, v in credentials.items() if 'username' in v]
        
        if len(available_orgs) < 2:
            st.error("❌ You need at least 2 Salesforce orgs configured to use migration feature.")
            st.info("💡 Go to Configuration tab to add more organizations.")
            return
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 📤 Source Organization")
            source_org = st.selectbox(
                "Select Source Org (Extract FROM)",
                options=["-- Select Source Org --"] + available_orgs,
                key='migration_source_selector'
            )
            
            if source_org != "-- Select Source Org --":
                st.session_state.migration_source_org = source_org
                
                # Connect to source org
                if 'source_sf_conn' not in st.session_state or st.session_state.get('last_source_org') != source_org:
                    with st.spinner(f"Connecting to {source_org}..."):
                        source_sf = connect_to_salesforce_org(credentials, source_org)
                        if source_sf:
                            st.session_state.source_sf_conn = source_sf
                            st.session_state.last_source_org = source_org
                            st.success(f"✅ Connected to {source_org}")
                        else:
                            st.error(f"❌ Failed to connect to {source_org}")
                else:
                    st.success(f"✅ Connected to {source_org}")
        
        with col2:
            st.markdown("#### 📥 Target Organization")
            target_org = st.selectbox(
                "Select Target Org (Load TO)",
                options=["-- Select Target Org --"] + [org for org in available_orgs if org != source_org],
                key='migration_target_selector'
            )
            
            if target_org != "-- Select Target Org --":
                st.session_state.migration_target_org = target_org
                
                # Connect to target org
                if 'target_sf_conn' not in st.session_state or st.session_state.get('last_target_org') != target_org:
                    with st.spinner(f"Connecting to {target_org}..."):
                        target_sf = connect_to_salesforce_org(credentials, target_org)
                        if target_sf:
                            st.session_state.target_sf_conn = target_sf
                            st.session_state.last_target_org = target_org
                            st.success(f"✅ Connected to {target_org}")
                        else:
                            st.error(f"❌ Failed to connect to {target_org}")
                else:
                    st.success(f"✅ Connected to {target_org}")
        
        # Object selection
        if st.session_state.migration_source_org and st.session_state.migration_target_org:
            st.markdown("---")
            st.markdown("#### 🎯 Select Salesforce Object")
            
            if 'source_sf_conn' in st.session_state:
                try:
                    # Get objects from source org
                    source_sf = st.session_state.source_sf_conn
                    objects_describe = source_sf.describe()
                    
                    object_names = [obj['name'] for obj in objects_describe['sobjects'] 
                                  if obj['createable'] and obj['queryable']]
                    object_names.sort()
                    
                    selected_object = st.selectbox(
                        "Choose object to migrate:",
                        options=["-- Select Object --"] + object_names,
                        key='migration_object_selector'
                    )
                    
                    if selected_object != "-- Select Object --":
                        # Reset mappings if object changed (since fields are different)
                        if st.session_state.migration_object != selected_object:
                            st.session_state.migration_field_mappings = {}
                        
                        st.session_state.migration_object = selected_object
                        st.success(f"✅ Selected object: **{selected_object}**")
                        
                        # Show migration summary
                        st.info(f"🔄 **Migration Path**: {source_org} ({selected_object}) → {target_org} ({selected_object})")
                
                except Exception as e:
                    st.error(f"Error retrieving objects: {str(e)}")
    
    # ============================================================================
    # TAB 2: FIELD MAPPING
    # ============================================================================
    with tab2:
        st.subheader("🗺️ Field Mapping Configuration")
        
        if not st.session_state.migration_object:
            st.warning("⚠️ Please configure Source/Target orgs and select an object in Configuration tab first.")
            return
        
        object_name = st.session_state.migration_object
        
        if 'source_sf_conn' in st.session_state and 'target_sf_conn' in st.session_state:
            source_sf = st.session_state.source_sf_conn
            target_sf = st.session_state.target_sf_conn
            
            with st.spinner(f"Loading field metadata for {object_name}..."):
                source_fields = get_object_fields(source_sf, object_name)
                target_fields = get_object_fields(target_sf, object_name)
            
            if source_fields and target_fields:
                st.success(f"✅ Loaded {len(source_fields)} source fields and {len(target_fields)} target fields")
                
                # Field selection mode
                st.markdown("### 🎯 Field Selection Mode")
                
                field_selection_mode = st.radio(
                    "Choose how to select source fields for mapping:",
                    options=["📋 Select from All Fields", "✍️ Use SOQL Query"],
                    horizontal=True,
                    help="Select all fields or specify fields via SOQL query"
                )
                
                # Initialize filtered source fields
                filtered_source_fields = {}
                
                if field_selection_mode == "✍️ Use SOQL Query":
                    st.markdown("#### ✍️ Enter SOQL Query")
                    st.info("💡 Enter a SOQL query to select fields AND filter records. The WHERE clause will be used during migration!")
                    
                    soql_query = st.text_area(
                        "SOQL Query:",
                        value=st.session_state.get('migration_soql_query', f"SELECT Id, Name FROM {object_name}"),
                        height=150,
                        help="Example: SELECT Id, Name, Email FROM Account WHERE Industry = 'Technology' AND AnnualRevenue > 1000000",
                        key="soql_query_input"
                    )
                    
                    if st.button("🔍 Parse Fields from Query", key="parse_soql"):
                        try:
                            # Extract field names from SOQL query
                            import re
                            
                            # Simple SOQL parser - extract fields between SELECT and FROM
                            select_pattern = r'SELECT\s+(.*?)\s+FROM'
                            match = re.search(select_pattern, soql_query, re.IGNORECASE | re.DOTALL)
                            
                            if match:
                                fields_str = match.group(1)
                                # Split by comma and clean up
                                field_names = [f.strip() for f in fields_str.split(',')]
                                
                                # Handle relationship queries (e.g., Account.Name or WOD_2__Dealer__r.Dealer_Number__c)
                                parsed_fields = []
                                relationship_fields_map = {}  # Track relationship fields separately
                                
                                for field in field_names:
                                    original_field = field
                                    # Remove any functions or aliases
                                    field = field.split(' AS ')[0].strip()
                                    field = field.split('(')[-1].replace(')', '').strip()
                                    
                                    # Check if it's a relationship field (contains __r. or contains .)
                                    if '.' in field:
                                        # Keep the full relationship path for relationship fields
                                        if '__r.' in field:
                                            # Custom object relationship: WOD_2__Dealer__r.Dealer_Number__c
                                            parsed_fields.append(field)
                                            relationship_fields_map[field] = True
                                        else:
                                            # Standard relationship: Account.Name → take last part
                                            last_part = field.split('.')[-1]
                                            parsed_fields.append(last_part)
                                    else:
                                        parsed_fields.append(field)
                                
                                # Filter source_fields to include both regular and relationship fields
                                for field_name in parsed_fields:
                                    # Check if it's a relationship field
                                    if '__r.' in field_name:
                                        # For relationship fields, store them as-is (they'll be handled specially)
                                        filtered_source_fields[field_name] = {
                                            'name': field_name,
                                            'type': 'reference',
                                            'is_relationship_field': True
                                        }
                                    elif field_name in source_fields:
                                        filtered_source_fields[field_name] = source_fields[field_name]
                                
                                # Extract WHERE clause if present
                                where_pattern = r'WHERE\s+(.+?)(?:ORDER BY|LIMIT|GROUP BY|$)'
                                where_match = re.search(where_pattern, soql_query, re.IGNORECASE | re.DOTALL)
                                where_clause = where_match.group(1).strip() if where_match else None
                                
                                if filtered_source_fields:
                                    st.session_state.migration_soql_query = soql_query
                                    st.session_state.migration_filtered_fields = filtered_source_fields
                                    st.session_state.migration_where_clause = where_clause  # Store WHERE clause
                                    st.session_state.migration_using_soql_mode = True  # Flag to indicate SOQL mode
                                    st.session_state.migration_relationship_fields = relationship_fields_map  # Track relationship fields
                                    
                                    st.success(f"✅ Parsed {len(filtered_source_fields)} fields from query")
                                    
                                    # Show regular fields
                                    regular_fields = [f for f in filtered_source_fields.keys() if '__r.' not in f]
                                    if regular_fields:
                                        st.write(f"**Regular Fields:** {', '.join(regular_fields)}")
                                    
                                    # Show relationship fields
                                    rel_fields = [f for f in filtered_source_fields.keys() if '__r.' in f]
                                    if rel_fields:
                                        st.write(f"**Relationship Fields:** {', '.join(rel_fields)}")
                                    
                                    if where_clause:
                                        st.success(f"✅ WHERE clause detected: `{where_clause}`")
                                        st.info("💡 This WHERE clause will be applied during migration to filter source records")
                                    else:
                                        st.info("ℹ️ No WHERE clause found - all records will be extracted")
                                else:
                                    st.error("❌ No valid fields found in query")
                            else:
                                st.error("❌ Could not parse SOQL query. Ensure it has SELECT ... FROM format")
                                
                        except Exception as e:
                            st.error(f"❌ Error parsing SOQL query: {str(e)}")
                            st.info("💡 Example format: SELECT Id, Name, Email FROM Account")
                    
                    # Use filtered fields if available
                    if 'migration_filtered_fields' in st.session_state:
                        filtered_source_fields = st.session_state.migration_filtered_fields
                        st.info(f"📋 Using {len(filtered_source_fields)} fields from SOQL query")
                    else:
                        st.warning("⚠️ Click 'Parse Fields from Query' to extract fields")
                
                else:
                    # Use all fields mode
                    filtered_source_fields = source_fields
                    st.session_state.migration_using_soql_mode = False  # Not using SOQL mode
                    st.session_state.migration_where_clause = None  # Clear WHERE clause
                    st.info(f"📋 Using all {len(source_fields)} available fields from {object_name}")
                
                st.markdown("---")
                
                # Only show mapping interface if we have fields to map
                if filtered_source_fields:
                    # Show current mapping status
                    with st.expander("📊 Current Mapping Status", expanded=False):
                        current_mappings = {k: v for k, v in st.session_state.migration_field_mappings.items() if v != "-- Skip --"}
                        if current_mappings:
                            mapping_df = pd.DataFrame([
                                {'Source Field': k, 'Target Field': v} 
                                for k, v in current_mappings.items()
                            ])
                            st.dataframe(mapping_df, use_container_width=True)
                            st.caption(f"✅ {len(current_mappings)} fields mapped, {len(filtered_source_fields) - len(current_mappings)} unmapped")
                        else:
                            st.info("ℹ️ No fields mapped yet. Use Auto Map or manually select target fields below.")
                    
                    # Auto-mapping and template buttons
                    col1, col2, col3 = st.columns([2, 2, 2])
                    
                    with col1:
                        if st.button("🤖 Auto Map Fields", help="Automatically map clear field matches. Ambiguous fields are left unmapped.", use_container_width=True):
                            if not filtered_source_fields:
                                st.error("❌ No source fields available. Please select fields using one of the methods above.")
                            else:
                                auto_mappings = {}
                                unmapped_reason = {'relationship_fields': 0, 'type_mismatch': 0, 'not_in_target': 0}
                                
                                for src_field, src_meta in filtered_source_fields.items():
                                    # Skip relationship fields (potential confusion - require manual mapping)
                                    if '__r.' in src_field or src_meta.get('is_relationship_field', False):
                                        unmapped_reason['relationship_fields'] += 1
                                        continue
                                    
                                    # Skip if field doesn't exist in target
                                    if src_field not in target_fields:
                                        unmapped_reason['not_in_target'] += 1
                                        continue
                                    
                                    # Check type compatibility (to avoid confusion)
                                    src_type = src_meta.get('type', '')
                                    tgt_type = target_fields[src_field].get('type', '')
                                    
                                    # Skip if types are incompatible (except for flexible text types)
                                    type_compatible = (
                                        src_type == tgt_type or
                                        (src_type in ['string', 'textarea'] and tgt_type in ['string', 'textarea'])
                                    )
                                    
                                    if not type_compatible:
                                        unmapped_reason['type_mismatch'] += 1
                                        continue
                                    
                                    # All clear - safe to auto-map
                                    auto_mappings[src_field] = src_field
                                
                                # Update session state with mappings
                                st.session_state.migration_field_mappings.update(auto_mappings)
                                
                                # Display results
                                if auto_mappings:
                                    st.success(f"✅ Auto-mapped {len(auto_mappings)} fields")
                                else:
                                    st.warning("⚠️ No clear field matches found to auto-map")
                                
                                # Show details of skipped fields
                                total_skipped = sum(unmapped_reason.values())
                                if total_skipped > 0:
                                    skip_details = []
                                    if unmapped_reason['relationship_fields'] > 0:
                                        skip_details.append(f"{unmapped_reason['relationship_fields']} relationship fields (require manual mapping)")
                                    if unmapped_reason['not_in_target'] > 0:
                                        skip_details.append(f"{unmapped_reason['not_in_target']} fields not in target")
                                    if unmapped_reason['type_mismatch'] > 0:
                                        skip_details.append(f"{unmapped_reason['type_mismatch']} fields with type mismatches")
                                    st.info(f"ℹ️ Left unmapped: {', '.join(skip_details)}")
                                
                                st.rerun()
                    
                    with col2:
                        if st.button("💾 Save Mapping Template"):
                            if st.session_state.migration_field_mappings:
                                filepath = save_field_mapping_config(
                                    st.session_state.migration_source_org,
                                    st.session_state.migration_target_org,
                                    object_name,
                                    st.session_state.migration_field_mappings,
                                    st.session_state.migration_lookup_configs
                                )
                                st.success(f"✅ Saved to: {filepath}")
                            else:
                                st.warning("⚠️ No mappings to save")
                    
                    with col3:
                        # Load mapping template
                        config_dir = Path('migration_configs')
                        if config_dir.exists():
                            config_files = list(config_dir.glob('*.json'))
                            if config_files:
                                selected_config = st.selectbox(
                                    "Load Template:",
                                    options=["-- New Mapping --"] + [f.name for f in config_files]
                                )
                                if selected_config != "-- New Mapping --":
                                    loaded_config = load_field_mapping_config(config_dir / selected_config)
                                    if loaded_config:
                                        st.session_state.migration_field_mappings = loaded_config.get('field_mappings', {})
                                        st.session_state.migration_lookup_configs = loaded_config.get('lookup_configs', {})
                                        st.success(f"✅ Loaded template: {selected_config}")
                                        st.rerun()
                    
                    st.markdown("---")
                    
                    # Field mapping interface
                st.markdown("### 🔗 Field Mappings")
                
                # Filter options
                col1, col2 = st.columns(2)
                with col1:
                    show_mapped_only = st.checkbox("Show Mapped Fields Only", value=False)
                with col2:
                    show_unmapped_only = st.checkbox("Show Unmapped Fields Only", value=False)
                
                # Create mapping interface
                mapping_data = []
                
                for src_field, src_meta in filtered_source_fields.items():
                    # Skip system fields
                    if src_field in ['Id', 'CreatedById', 'CreatedDate', 'LastModifiedById', 'LastModifiedDate', 'SystemModstamp']:
                        continue
                
                    # Check if this is a relationship field (contains __r.)
                    is_relationship_field = '__r.' in src_field or src_meta.get('is_relationship_field', False)
                    
                    # Get compatible target fields (same data type)
                    compatible_targets = ["-- Skip --"]  # Always include Skip as first option
                    
                    if is_relationship_field:
                        # For relationship fields, show all fields in target (they can be mapped to lookup fields)
                        # Extract the field name from relationship path
                        rel_field_name = src_field.split('.')[-1] if '.' in src_field else src_field
                        
                        # Add exact match first
                        if rel_field_name in target_fields:
                            compatible_targets.append(rel_field_name)
                        
                        # Add all other fields (user may want to map to a different field)
                        for tgt_field in target_fields.keys():
                            if tgt_field not in compatible_targets and tgt_field not in ['Id', 'CreatedById', 'CreatedDate', 'LastModifiedById', 'LastModifiedDate']:
                                compatible_targets.append(tgt_field)
                        
                        # Field label for relationship fields
                        field_label = f"🔗 {src_field}"
                    else:
                        # FIRST: Always add fields with EXACT NAME MATCH (for auto-mapping to work)
                        if src_field in target_fields:
                            compatible_targets.append(src_field)
                        
                        # SECOND: Add fields with matching data type
                        for tgt_field, tgt_meta in target_fields.items():
                            if tgt_field != src_field:  # Skip if already added by name match
                                if tgt_meta['type'] == src_meta['type'] or \
                                   (src_meta['type'] in ['string', 'textarea'] and tgt_meta['type'] in ['string', 'textarea']):
                                    if tgt_field not in compatible_targets:
                                        compatible_targets.append(tgt_field)
                        
                        field_label = src_field
                    
                    # Get current mapping from session state
                    current_mapping = st.session_state.migration_field_mappings.get(src_field, "-- Skip --")
                    
                    # Apply filters
                    if show_mapped_only and current_mapping == "-- Skip --":
                        continue
                    if show_unmapped_only and current_mapping != "-- Skip --":
                        continue
                    
                    mapping_data.append({
                        'source_field': src_field,
                        'source_type': src_meta.get('type', 'reference'),
                        'source_label': src_meta.get('label', src_field),
                        'compatible_targets': compatible_targets,
                        'current_mapping': current_mapping,
                        'is_relationship_field': is_relationship_field,
                        'display_label': field_label
                    })
                
                # Display mappings
                st.markdown(f"**Total Mappings**: {len([m for m in st.session_state.migration_field_mappings.values() if m != '-- Skip --'])} / {len(filtered_source_fields)}")
                
                for i, mapping in enumerate(mapping_data):
                    col1, col2, col3 = st.columns([2, 1, 2])
                    
                    with col1:
                        # Use display label for relationship fields
                        display_label = mapping.get('display_label', mapping['source_field'])
                        st.text(display_label)
                        st.caption(f"{mapping['source_label']} ({mapping['source_type']})")
                        
                        # Add note for relationship fields
                        if mapping.get('is_relationship_field', False):
                            st.info("🔗 Relationship Field - Extracted from SOQL query", icon="ℹ️")
                    
                    with col2:
                        st.markdown("<p style='text-align: center; font-size: 24px;'>→</p>", unsafe_allow_html=True)
                    
                    with col3:
                        # Get current mapping and compatible targets
                        current_map = mapping['current_mapping']
                        compatible_list = mapping['compatible_targets']
                        
                        # Ensure current mapping is in the list
                        if current_map not in compatible_list:
                            compatible_list = [current_map] + compatible_list if current_map != "-- Skip --" else compatible_list
                        
                        # Find the index of current mapping
                        try:
                            default_index = compatible_list.index(current_map)
                        except ValueError:
                            default_index = 0
                        
                        # Use dynamic key that changes when mapping changes - forces Streamlit to refresh selectbox display
                        widget_key = f"field_map_{mapping['source_field']}_{current_map}"
                        
                        selected_target = st.selectbox(
                            "Target Field",
                            options=compatible_list,
                            index=default_index,
                            key=widget_key,
                            label_visibility="collapsed"
                        )
                        
                        # Update session state when selection changes
                        if selected_target != "-- Skip --":
                            st.session_state.migration_field_mappings[mapping['source_field']] = selected_target
                            # Get target field metadata and display
                            if selected_target in target_fields:
                                tgt_meta = target_fields[selected_target]
                                st.caption(f"✅ {tgt_meta['label']} ({tgt_meta['type']})")
                            else:
                                st.caption(f"✅ {selected_target}")
                        else:
                            # Remove mapping if Skip is selected
                            if mapping['source_field'] in st.session_state.migration_field_mappings:
                                del st.session_state.migration_field_mappings[mapping['source_field']]
                    
                    if i < len(mapping_data) - 1:
                        st.markdown("---")
                
                # Summary
                st.markdown("---")
                col1, col2, col3 = st.columns(3)
                with col1:
                    # Count ONLY mappings for currently selected source fields
                    current_source_fields = list(filtered_source_fields.keys())
                    mapped_count = len([
                        field for field in current_source_fields 
                        if field in st.session_state.migration_field_mappings 
                        and st.session_state.migration_field_mappings[field] != "-- Skip --"
                    ])
                    st.metric("✅ Mapped Fields", mapped_count)
                with col2:
                    # Unmapped = Total source fields - Mapped fields
                    total_selected = len(current_source_fields)
                    unmapped_count = total_selected - mapped_count
                    st.metric("⚠️ Unmapped Fields", unmapped_count)
                with col3:
                    st.metric("📊 Total Source Fields", total_selected)
            else:
                st.info("💡 Please select fields using one of the methods above to start mapping")
    
    # ============================================================================
    # TAB 3: PRE-MIGRATION VALIDATION (NEW)
    # ============================================================================
    with tab3:
        st.subheader("✅ Pre-Migration Schema Validation")
        st.markdown("""
        **Validate data against target org schema BEFORE migration**
        
        This validation checks:
        - ✓ Required fields are present in all records
        - ✓ Data types are compatible with target org
        - ✓ Picklist values are valid in target org
        - ✓ Field values don't exceed max length
        """)
        
        if not st.session_state.migration_object:
            st.warning("⚠️ Please configure Source/Target orgs and select an object in Configuration tab first.")
        
        elif 'target_sf_conn' not in st.session_state:
            st.warning("⚠️ Please select target organization in Configuration tab first.")
        
        else:
            target_sf = st.session_state.target_sf_conn
            object_name = st.session_state.migration_object
            
            # Get field mappings if configured
            field_mappings = st.session_state.get('migration_field_mappings', {})
            
            # Show validation steps
            st.markdown("### 📊 Validation Steps")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.info("1️⃣ **Load Data**\nSelect source data to validate")
            with col2:
                st.info("2️⃣ **Configure**\nReview validation settings")
            with col3:
                st.info("3️⃣ **Validate**\nRun validation checks")
            
            st.divider()
            
            # Step 1: Load data for validation
            st.markdown("### Step 1️⃣: Load Data for Validation")
            
            try:
                from ui_components.data_hub.integration import has_data, get_data_from_hub, show_data_source_info
                data_hub_available = has_data()
            except ImportError:
                data_hub_available = False
            
            data_source = "none"
            validation_data = None
            
            if data_hub_available:
                data_source_option = st.radio(
                    "Data Source:",
                    ["Use Data Hub", "Upload File"],
                    key="migration_validation_source",
                    horizontal=True
                )
            else:
                data_source_option = "Upload File"
            
            if data_source_option == "Use Data Hub" and data_hub_available:
                st.success("📊 Data Hub has an active dataset available!")
                show_data_source_info()
                
                if st.button("✅ Load from Data Hub", use_container_width=True, key="migration_load_from_hub"):
                    validation_data = get_data_from_hub()
                    if validation_data is not None:
                        st.success(f"✅ Data loaded from Hub: {len(validation_data)} rows")
                        data_source = "hub"
                        st.session_state.migration_validation_data = validation_data
            
            else:
                uploaded_file = st.file_uploader(
                    "Upload data file for validation",
                    type=['csv', 'xlsx', 'xls', 'psv'],
                    key="migration_validation_upload"
                )
                
                if uploaded_file:
                    try:
                        # Import load function
                        from .utils import load_data_file
                        validation_data = load_data_file(uploaded_file)
                        
                        if validation_data is not None:
                            st.success(f"✅ Loaded {len(validation_data)} records with {len(validation_data.columns)} columns")
                            data_source = "upload"
                            st.session_state.migration_validation_data = validation_data
                        else:
                            st.error("❌ Could not load file")
                    except Exception as e:
                        st.error(f"❌ Error loading file: {str(e)}")
            
            # Step 2: Review validation settings
            if validation_data is not None or 'migration_validation_data' in st.session_state:
                if validation_data is None:
                    validation_data = st.session_state.migration_validation_data
                
                st.divider()
                st.markdown("### Step 2️⃣: Validation Settings")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Records to validate:** {len(validation_data)}")
                with col2:
                    st.write(f"**Fields in data:** {len(validation_data.columns)}")
                
                # Show which fields will be validated
                field_mappings = st.session_state.get('migration_field_mappings', {})
                filtered_fields = st.session_state.get('migration_filtered_fields', {})
                using_soql_mode = st.session_state.get('migration_using_soql_mode', False)
                
                if field_mappings:
                    # Count mappings ONLY for the selected/filtered fields (from SOQL or all fields mode)
                    if filtered_fields:
                        # Count mappings for the SELECTED fields only
                        selected_field_names = list(filtered_fields.keys())
                        mapped_count = len([
                            field for field in selected_field_names
                            if field in field_mappings and field_mappings[field] != "-- Skip --"
                        ])
                        total_selected = len(selected_field_names)
                        mode_info = "SOQL Query" if using_soql_mode else "All Fields"
                        st.info(f"ℹ️ **Validation Scope:** {mapped_count}/{total_selected} fields from {mode_info} mode are mapped and will be validated.")
                        st.caption("💡 **Note:** Read-only fields (formulas, system fields, roll-up summaries) are automatically skipped. Required fields without values will be flagged.")
                    else:
                        # Fallback: show all non-skip mappings
                        mapped_count = len([f for f in field_mappings.values() if f != "-- Skip --"])
                        st.info(f"ℹ️ **Validation Scope:** {mapped_count} mapped fields from Field Mapping tab will be validated.")
                        st.caption("💡 **Note:** Read-only fields (formulas, system fields, roll-up summaries) are automatically skipped.")
                else:
                    st.warning("⚠️ **No field mappings found.** Validation will check all fields in the uploaded data. Complete Field Mapping tab (TAB 2) for precise validation of specific fields.")
                
                # Validation options
                validation_options = st.multiselect(
                    "Select validations to run:",
                    ["Required Fields", "Data Types", "Picklist Values", "Field Length"],
                    default=["Required Fields", "Data Types", "Picklist Values"],
                    key="migration_validation_options"
                )
                
                st.divider()
                
                # Step 3: Run validation
                st.markdown("### Step 3️⃣: Run Validation")
                
                if st.button("🚀 Run Schema Validation", type="primary", use_container_width=True, key="run_migration_validation"):
                    # Import validation module
                    try:
                        from ui_components.org_migration_validation import (
                            validate_required_fields,
                            validate_data_types,
                            validate_picklist_values,
                            validate_field_length,
                            display_validation_report
                        )
                        
                        validation_results = {}
                        
                        # Run selected validations
                        if "Required Fields" in validation_options:
                            with st.spinner("Checking required fields..."):
                                validation_results['required_fields'] = validate_required_fields(
                                    validation_data, target_sf, object_name, field_mappings
                                )
                        
                        if "Data Types" in validation_options:
                            with st.spinner("Checking data types..."):
                                validation_results['data_types'] = validate_data_types(
                                    validation_data, target_sf, object_name, field_mappings
                                )
                        
                        if "Picklist Values" in validation_options:
                            with st.spinner("Checking picklist values..."):
                                validation_results['picklist_values'] = validate_picklist_values(
                                    validation_data, target_sf, object_name, field_mappings
                                )
                        
                        if "Field Length" in validation_options:
                            with st.spinner("Checking field lengths..."):
                                validation_results['field_length'] = validate_field_length(
                                    validation_data, target_sf, object_name, field_mappings
                                )
                        
                        # Store results
                        st.session_state.migration_validation_results = validation_results
                        
                        # Display results
                        st.divider()
                        st.markdown("### 📋 Validation Results")
                        
                        all_passed = all(r.get('passed', False) for r in validation_results.values())
                        
                        if all_passed:
                            st.success(f"✅ **ALL VALIDATIONS PASSED** - {len(validation_data)} records ready to migrate")
                        else:
                            st.warning(f"⚠️ **VALIDATION ISSUES FOUND** - Review issues below before migrating")
                        
                        st.divider()
                        
                        # Show detailed results
                        for validation_type, result in validation_results.items():
                            if result.get('error'):
                                st.error(f"Error in {validation_type}: {result['error']}")
                            else:
                                passed = result.get('passed', False)
                                status = "✅ PASSED" if passed else "❌ FAILED"
                                
                                with st.expander(f"{status} - {validation_type.replace('_', ' ').title()}", expanded=not passed):
                                    if validation_type == 'required_fields':
                                        if result['required_fields'] > 0:
                                            st.write(f"**Total required fields:** {result['required_fields']}")
                                            st.write(f"**Fields with issues:** {result['missing_in_data']}")
                                            
                                            if result['missing_fields']:
                                                st.write("**Affected fields:**")
                                                for field in result['missing_fields']:
                                                    st.write(f"  • `{field['field']}` - {field['missing_count']} records missing")
                                    
                                    elif validation_type == 'data_types':
                                        if result.get('issues', 0) > 0:
                                            st.write(f"**Type compatibility issues:** {result['issues']}")
                                            for r in result.get('results', []):
                                                if not r.get('compatible'):
                                                    st.write(f"  • `{r['source_field']}` → `{r['target_field']}` ({r['target_type']})")
                                    
                                    elif validation_type == 'picklist_values':
                                        if result.get('picklist_fields'):
                                            for r in result['picklist_fields']:
                                                if r['invalid_values']:
                                                    st.write(f"  • `{r['field']}` - Invalid values: {', '.join(list(r['invalid_values'])[:5])}")
                                    
                                    elif validation_type == 'field_length':
                                        if result.get('violations', 0) > 0:
                                            st.write(f"**Field length violations:** {result['violations']}")
                                            for r in result.get('results', []):
                                                st.write(f"  • `{r['field']}` (max: {r['max_length']}) - {r['exceed_count']} exceeding")
                        
                        st.divider()
                        
                        # Next steps
                        if all_passed:
                            st.success("✅ **Ready to proceed with migration!**")
                            st.info("Click '4️⃣ Business Rules', '5️⃣ Data Quality', '6️⃣ Lookup Resolution', and '7️⃣ Data Preview' tabs to complete pre-flight checks")
                        else:
                            st.warning("⚠️ **Review and fix issues before proceeding**")
                            st.info("After fixing issues, re-upload data and run validation again")
                    
                    except Exception as e:
                        st.error(f"❌ Error running validation: {str(e)}")
                        st.exception(e)
    
    # ============================================================================
    # TAB 4: BUSINESS RULES VALIDATION
    # ============================================================================
    with tab4:
        st.subheader("📏 Business Rules Validation")
        st.markdown("""
        Validate that your data complies with business rules defined in the target Salesforce org.
        This includes field dependencies, conditional requirements, value ranges, and duplicate detection.
        """)
        
        try:
            from ui_components.data_hub.integration import has_data, get_data_from_hub, show_data_source_info
            data_hub_available = has_data()
        except ImportError:
            data_hub_available = False
        
        # Step 1: Load data for validation
        st.markdown("### Step 1️⃣: Load Data for Rules Validation")
        
        rules_data = None
        
        if data_hub_available:
            rules_source = st.radio(
                "Data Source:",
                ["Use Data Hub", "Upload File"],
                key="rules_validation_source",
                horizontal=True
            )
        else:
            rules_source = "Upload File"
        
        if rules_source == "Use Data Hub" and data_hub_available:
            if st.button("✅ Load from Data Hub", key="rules_load_hub"):
                try:
                    rules_data = get_data_from_hub()
                    st.session_state.rules_validation_data = rules_data
                    st.success(f"✅ Loaded {len(rules_data)} records from Data Hub")
                except Exception as e:
                    st.error(f"❌ Error loading from Data Hub: {str(e)}")
        
        elif rules_source == "Upload File":
            uploaded_file = st.file_uploader(
                "Upload data file for rules validation:",
                type=['csv', 'xlsx', 'xls', 'psv'],
                key="rules_validation_file"
            )
            
            if uploaded_file:
                try:
                    from .utils import load_data_file
                    rules_data = load_data_file(uploaded_file)
                    st.session_state.rules_validation_data = rules_data
                    st.success(f"✅ Loaded {len(rules_data)} records from file")
                except Exception as e:
                    st.error(f"❌ Error reading file: {str(e)}")
        
        # Use previously loaded data if available
        if rules_data is None and 'rules_validation_data' in st.session_state:
            rules_data = st.session_state.rules_validation_data
            st.info(f"ℹ️ Using previously loaded data ({len(rules_data)} records)")
        
        if rules_data is not None:
            st.success(f"✅ Data loaded: {rules_data.shape[0]} rows × {rules_data.shape[1]} columns")
            
            # Step 2: Configure business rules
            st.markdown("### Step 2️⃣: Configure Business Rules")
            
            rules_config = {}
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Field Dependencies")
                enable_dependencies = st.checkbox(
                    "Check field dependencies",
                    value=True,
                    key="check_dependencies"
                )
                st.caption("Validates that dependent fields are populated when parent fields have values")
            
            with col2:
                st.subheader("Target Org Validation Rules")
                enable_validation_rules = st.checkbox(
                    "Check target org validation rules",
                    value=True,
                    key="check_validation_rules"
                )
                st.caption("Validates data against validation rules defined in target org")
            
            col3, col4 = st.columns(2)
            
            with col3:
                st.subheader("Conditional Requirements")
                enable_conditionals = st.checkbox(
                    "Check conditional requirements",
                    value=True,
                    key="check_conditionals"
                )
                st.caption("Validates that required fields are populated based on field values")
            
            with col4:
                st.subheader("Duplicate Detection")
                enable_duplicates = st.checkbox(
                    "Check for duplicates",
                    value=True,
                    key="check_duplicates"
                )
                st.caption("Identifies potential duplicate records")
            
            # Optional: Define duplicate key fields
            if enable_duplicates:
                st.markdown("#### Duplicate Key Fields")
                available_cols = list(rules_data.columns)
                duplicate_keys = st.multiselect(
                    "Select fields to identify duplicates (leave empty for auto-detection):",
                    available_cols,
                    key="duplicate_key_fields"
                )
                if duplicate_keys:
                    rules_config['duplicate_key_fields'] = duplicate_keys
            
            # Step 3: Run validation
            st.markdown("### Step 3️⃣: Run Business Rules Validation")
            
            if st.button("🚀 Run Business Rules Validation", key="run_rules_validation"):
                with st.spinner("🔍 Validating business rules..."):
                    try:
                        # Get source connection for field dependencies
                        if 'source_sf_conn' not in st.session_state:
                            st.error("❌ Source org not connected. Please configure in first tab.")
                        else:
                            source_conn = st.session_state.source_sf_conn
                            target_conn = st.session_state.target_sf_conn
                            object_name = st.session_state.migration_object
                            
                            validation_results = {}
                            
                            # Run custom business rules validation
                            validation_results['custom_rules'] = validate_business_rules(
                                rules_data,
                                object_name,
                                source_conn,
                                rules_config
                            )
                            
                            # Run target org validation rules check (actual Salesforce ValidationRules)
                            if enable_validation_rules:
                                with st.spinner("Extracting ValidationRules from target org..."):
                                    # Try to get actual Salesforce ValidationRules with formula evaluation
                                    validation_results['salesforce_rules'] = validate_data_against_salesforce_rules(
                                        rules_data,
                                        target_conn,
                                        object_name
                                    )
                            
                            # Store results in session
                            st.session_state.business_rules_validation = validation_results
                            
                            # Display results
                            st.success("✅ Validation complete!")
                            
                            # Display custom rules results
                            st.markdown("#### 📏 Custom Business Rules")
                            display_rules_validation_report(validation_results['custom_rules'], rules_data)
                            
                            # Display target org validation rules results
                            if enable_validation_rules and 'salesforce_rules' in validation_results:
                                sf_rules_result = validation_results['salesforce_rules']
                                
                                # Check if ValidationRules were actually extracted
                                if sf_rules_result.get('total_rules', 0) > 0:
                                    st.divider()
                                    st.markdown("#### 🏢 Salesforce ValidationRules (from Target Org)")
                                    display_salesforce_validation_rules_report(sf_rules_result, rules_data)
                                else:
                                    st.divider()
                                    st.markdown("#### 🏢 Salesforce ValidationRules (from Target Org)")
                                    st.info("ℹ️ No ValidationRules found for this object, or ValidationRules API not available. Using field-level validation as fallback.")
                                    # Fall back to field-level validation
                                    fallback_rules = validate_data_against_validation_rules(
                                        rules_data,
                                        target_conn,
                                        object_name
                                    )
                                    display_validation_rules_report(fallback_rules, rules_data)
                            
                            # Show fix suggestions for custom rules
                            if validation_results['custom_rules'].get('failed', 0) > 0:
                                suggestions = apply_rule_fixes_suggestions(validation_results['custom_rules'])
                                if suggestions:
                                    st.markdown("### 💡 Suggested Fixes")
                                    for suggestion in suggestions:
                                        st.write(suggestion)
                    
                    except Exception as e:
                        st.error(f"❌ Error running validation: {str(e)}")
                        st.exception(e)
            
            # Show previous results if available
            if 'business_rules_validation' in st.session_state:
                with st.expander("📊 Previous Validation Results", expanded=False):
                    prev_results = st.session_state.business_rules_validation
                    
                    # Show custom rules results
                    if 'custom_rules' in prev_results:
                        st.markdown("#### 📏 Custom Business Rules")
                        display_rules_validation_report(prev_results['custom_rules'], rules_data)
                    
                    # Show Salesforce ValidationRules results
                    if 'salesforce_rules' in prev_results:
                        st.divider()
                        st.markdown("#### 🏢 Salesforce ValidationRules (from Target Org)")
                        display_salesforce_validation_rules_report(prev_results['salesforce_rules'], rules_data)
        
        else:
            st.info("📤 Please load data in Step 1 to proceed with business rules validation")
    
    # ============================================================================
    # TAB 5: DATA QUALITY CHECKS
    # ============================================================================
    with tab5:
        st.subheader("🔍 Data Quality Checks")
        st.markdown("""
        Comprehensive data quality validation including duplicate detection, 
        referential integrity, completeness, and consistency checks.
        """)
        
        try:
            from ui_components.data_hub.integration import has_data, get_data_from_hub, show_data_source_info
            data_hub_available = has_data()
        except ImportError:
            data_hub_available = False
        
        # Step 1: Load data for quality checks
        st.markdown("### Step 1️⃣: Load Data for Quality Checks")
        
        quality_data = None
        
        if data_hub_available:
            quality_source = st.radio(
                "Data Source:",
                ["Use Data Hub", "Upload File"],
                key="quality_check_source",
                horizontal=True
            )
        else:
            quality_source = "Upload File"
        
        if quality_source == "Use Data Hub" and data_hub_available:
            if st.button("✅ Load from Data Hub", key="quality_load_hub"):
                try:
                    quality_data = get_data_from_hub()
                    st.session_state.quality_check_data = quality_data
                    st.success(f"✅ Loaded {len(quality_data)} records from Data Hub")
                except Exception as e:
                    st.error(f"❌ Error loading from Data Hub: {str(e)}")
        
        elif quality_source == "Upload File":
            quality_file = st.file_uploader(
                "Upload CSV, XLSX, XLS, or PSV file for quality checks:",
                type=['csv', 'xlsx', 'xls', 'psv'],
                key="quality_check_file"
            )
            
            if quality_file:
                try:
                    quality_data = pd.read_csv(quality_file)
                    st.session_state.quality_check_data = quality_data
                    st.success(f"✅ Loaded {len(quality_data)} records from file")
                except Exception as e:
                    st.error(f"❌ Error reading file: {str(e)}")
        
        # Use previously loaded data if available
        if quality_data is None and 'quality_check_data' in st.session_state:
            quality_data = st.session_state.quality_check_data
            st.info(f"ℹ️ Using previously loaded data ({len(quality_data)} records)")
        
        if quality_data is not None:
            st.success(f"✅ Data loaded: {quality_data.shape[0]} rows × {quality_data.shape[1]} columns")
            
            # Step 2: Configure quality checks
            st.markdown("### Step 2️⃣: Configure Quality Checks")
            
            quality_config = {}
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Duplicate Detection")
                enable_dup_check = st.checkbox(
                    "Check for duplicates",
                    value=True,
                    key="enable_dup_check"
                )
                st.caption("Identifies records with identical key field values")
                
                if enable_dup_check:
                    quality_config['check_duplicates'] = True
                    available_cols = list(quality_data.columns)
                    dup_keys = st.multiselect(
                        "Select duplicate key fields:",
                        available_cols,
                        key="dup_key_fields"
                    )
                    if dup_keys:
                        quality_config['duplicate_key_fields'] = dup_keys
            
            with col2:
                st.subheader("Completeness")
                enable_complete_check = st.checkbox(
                    "Check completeness",
                    value=True,
                    key="enable_complete_check"
                )
                st.caption("Validates required fields are populated")
                
                if enable_complete_check:
                    quality_config['check_completeness'] = True
                    available_cols = list(quality_data.columns)
                    required_fields = st.multiselect(
                        "Select required fields:",
                        available_cols,
                        key="required_fields_quality"
                    )
                    if required_fields:
                        quality_config['required_fields'] = required_fields
                    
                    threshold = st.slider(
                        "Completeness threshold (%)",
                        0, 100, 80, 10,
                        key="completeness_threshold"
                    )
                    quality_config['completeness_threshold'] = threshold / 100
            
            col3, col4 = st.columns(2)
            
            with col3:
                st.subheader("Consistency")
                enable_consistency = st.checkbox(
                    "Check consistency",
                    value=True,
                    key="enable_consistency"
                )
                st.caption("Validates format and pattern compliance")
                
                if enable_consistency:
                    quality_config['check_consistency'] = True
                    consistency_rules = {}
                    
                    # Email fields
                    email_cols = st.multiselect(
                        "Email fields to validate:",
                        list(quality_data.columns),
                        key="email_fields_quality"
                    )
                    if email_cols:
                        consistency_rules['email_fields'] = email_cols
                    
                    # Phone fields
                    phone_cols = st.multiselect(
                        "Phone fields to validate:",
                        list(quality_data.columns),
                        key="phone_fields_quality"
                    )
                    if phone_cols:
                        consistency_rules['phone_fields'] = phone_cols
                    
                    # Date fields
                    date_cols = st.multiselect(
                        "Date fields to validate:",
                        list(quality_data.columns),
                        key="date_fields_quality"
                    )
                    if date_cols:
                        consistency_rules['date_fields'] = date_cols
                    
                    if consistency_rules:
                        quality_config['consistency_rules'] = consistency_rules
            
            with col4:
                st.subheader("Referential Integrity")
                enable_ref_integrity = st.checkbox(
                    "Check referential integrity",
                    value=False,
                    key="enable_ref_integrity"
                )
                st.caption("Validates lookup field references exist")
                
                if enable_ref_integrity:
                    quality_config['check_referential_integrity'] = True
                    st.info("ℹ️ Configure lookup field mappings if needed")
            
            # Step 3: Run checks
            st.markdown("### Step 3️⃣: Run Data Quality Checks")
            
            if st.button("🚀 Run Quality Checks", key="run_quality_checks"):
                with st.spinner("🔍 Running data quality checks..."):
                    try:
                        from ui_components.org_migration_quality import run_all_quality_checks, display_quality_report, generate_quality_recommendations
                        
                        if 'source_sf_conn' not in st.session_state:
                            st.error("❌ Source org not connected. Please configure in first tab.")
                        else:
                            source_conn = st.session_state.source_sf_conn
                            
                            # Run all quality checks
                            quality_results = run_all_quality_checks(
                                quality_data,
                                source_conn,
                                quality_config
                            )
                            
                            # Store results in session
                            st.session_state.quality_check_results = quality_results
                            
                            st.success("✅ Quality checks complete!")
                            
                            # Display results
                            display_quality_report(quality_results, quality_data)
                            
                            # Show recommendations
                            if not quality_results.get('pass', True):
                                recommendations = generate_quality_recommendations(quality_results)
                                if recommendations:
                                    st.markdown("### 💡 Recommendations")
                                    for rec in recommendations:
                                        st.write(rec)
                    
                    except Exception as e:
                        st.error(f"❌ Error running quality checks: {str(e)}")
                        st.exception(e)
            
            # Show previous results if available
            if 'quality_check_results' in st.session_state:
                with st.expander("📊 Previous Quality Check Results", expanded=False):
                    from ui_components.org_migration_quality import display_quality_report
                    display_quality_report(
                        st.session_state.quality_check_results,
                        quality_data
                    )
        
        else:
            st.info("📤 Please load data in Step 1 to proceed with quality checks")
    
    # ============================================================================
    # TAB 6: LOOKUP RESOLUTION & RECORD MATCHING
    # ============================================================================
    with tab6:
        st.subheader("🔗 Lookup Field Resolution & Record Matching Configuration")
        st.markdown("""
        **Configure two critical aspects:**
        1. **Main Object Matching**: How to identify if records already exist in target org
        2. **Lookup Resolution**: How to resolve parent-child relationships during migration
        """)
        
        if not st.session_state.migration_object:
            st.warning("⚠️ Please configure Source/Target orgs and select an object in Configuration tab first.")
            return
        
        object_name = st.session_state.migration_object
        
        if 'source_sf_conn' in st.session_state and 'target_sf_conn' in st.session_state:
            source_sf = st.session_state.source_sf_conn
            target_sf = st.session_state.target_sf_conn
            
            # Get field metadata for TARGET org
            target_object_fields = get_object_fields(target_sf, object_name)
            external_id_fields = identify_external_id_fields(target_object_fields)
            unique_fields = identify_unique_fields(target_object_fields)
            all_target_fields = list(target_object_fields.keys())
            
            # ========================================================================
            # SECTION 1: MAIN OBJECT MATCHING STRATEGY
            # ========================================================================
            st.markdown("### 🎯 Main Object Matching Strategy")
            st.markdown("""
            **CRITICAL**: Define how to check if records already exist in TARGET org.
            This determines whether records will be INSERTED (new) or UPDATED (existing).
            """)
            
            with st.expander("ℹ️ Why This Matters", expanded=False):
                st.markdown("""
                When migrating data:
                - **Records created via data file** → Usually have External ID
                - **Records created in Salesforce UI** → May NOT have External ID
                
                Solution: Use External ID, unique field, or combination/concatenation of fields
                to match records regardless of how they were created.
                """)
            
            st.info(f"📊 Target {object_name} has {len(external_id_fields)} External ID(s), {len(unique_fields)} unique field(s)")
            
            # Matching strategy selection
            main_match_strategy = st.radio(
                "How to match records in target org:",
                options=[
                    "external_id - Single External ID Field",
                    "unique_field - Single Unique Field",
                    "field_combination - Multiple Fields (AND)",
                    "field_concatenation - Concatenated Fields"
                ],
                key="main_match_strategy",
                help="Choose how to identify if a record already exists in target org"
            )
            
            strategy_key = main_match_strategy.split(" - ")[0]
            
            # Initialize session state for main matching
            if 'migration_main_match_strategy' not in st.session_state:
                st.session_state.migration_main_match_strategy = None
            if 'migration_main_match_fields' not in st.session_state:
                st.session_state.migration_main_match_fields = []
            
            if strategy_key == "external_id":
                if external_id_fields:
                    selected_ext_id = st.selectbox(
                        "Select External ID Field:",
                        options=external_id_fields,
                        key="main_external_id"
                    )
                    
                    st.session_state.migration_main_match_strategy = 'external_id'
                    st.session_state.migration_main_match_fields = [selected_ext_id]
                    
                    st.success(f"✅ Will match records using: **{selected_ext_id}**")
                    st.code(f"SELECT Id FROM {object_name} WHERE {selected_ext_id} = <value>", language="sql")
                else:
                    st.error(f"❌ No External ID fields found in target {object_name}")
            
            elif strategy_key == "unique_field":
                if unique_fields:
                    selected_unique = st.selectbox(
                        "Select Unique Field:",
                        options=unique_fields,
                        key="main_unique_field"
                    )
                    
                    st.session_state.migration_main_match_strategy = 'external_id'  # Same logic as external_id
                    st.session_state.migration_main_match_fields = [selected_unique]
                    
                    st.success(f"✅ Will match records using: **{selected_unique}**")
                    st.code(f"SELECT Id FROM {object_name} WHERE {selected_unique} = <value>", language="sql")
                else:
                    st.warning(f"⚠️ No unique fields found. Try field combination.")
            
            elif strategy_key == "field_combination":
                selected_combo_fields = st.multiselect(
                    "Select Fields to Combine (AND condition):",
                    options=all_target_fields,
                    key="main_combo_fields",
                    help="All selected fields must match to identify a record"
                )
                
                if selected_combo_fields:
                    st.session_state.migration_main_match_strategy = 'field_combination'
                    st.session_state.migration_main_match_fields = selected_combo_fields
                    
                    st.success(f"✅ Will match records using combination: **{', '.join(selected_combo_fields)}**")
                    where_clause = " AND ".join([f"{f} = <value>" for f in selected_combo_fields])
                    st.code(f"SELECT Id FROM {object_name} WHERE {where_clause}", language="sql")
            
            elif strategy_key == "field_concatenation":
                selected_concat_fields = st.multiselect(
                    "Select Fields to Concatenate:",
                    options=all_target_fields,
                    key="main_concat_fields"
                )
                
                concat_sep = st.text_input(
                    "Concatenation Separator:",
                    value="_",
                    key="main_concat_sep"
                )
                
                if selected_concat_fields:
                    st.session_state.migration_main_match_strategy = 'field_concatenation'
                    st.session_state.migration_main_match_fields = selected_concat_fields
                    st.session_state.migration_main_concat_separator = concat_sep
                    
                    concat_example = concat_sep.join([f"<{f}>" for f in selected_concat_fields])
                    st.success(f"✅ Will match records using concatenation: **{concat_example}**")
                    where_clause = " AND ".join([f"{f} = <value>" for f in selected_concat_fields])
                    st.code(f"SELECT Id FROM {object_name} WHERE {where_clause}", language="sql")
            
            st.markdown("---")
            
            # ========================================================================
            # SECTION 2: LOOKUP FIELD RESOLUTION
            # ========================================================================
            st.markdown("### 🔗 Lookup Field Resolution (Parent Objects)")
            st.markdown("Configure how to find parent records in TARGET org for each lookup field.")
            
            # Auto-discovery vs manual configuration tabs
            lookup_config_mode = st.radio(
                "Choose Lookup Configuration Approach:",
                options=[
                    "🔍 Auto-Discover from SOQL",
                    "⚙️ Manual Configuration"
                ],
                help="Auto-discover uses SOQL queries | Manual: Configure each lookup field individually",
                key="lookup_config_mode"
            )
            
            if lookup_config_mode == "🔍 Auto-Discover from SOQL":
                st.markdown("---")
                with st.container():
                    try:
                        discovered_configs = show_soql_lookup_discovery_ui(source_sf, target_sf)
                        
                        if discovered_configs:
                            # Apply to session state
                            st.session_state.migration_lookup_configs.update(discovered_configs)
                            st.success("✅ Lookup configurations updated from SOQL discovery")
                            
                            # Show summary
                            with st.expander("📋 View Applied Configurations", expanded=True):
                                for lookup_field, config in discovered_configs.items():
                                    st.write(f"• **{lookup_field}** → {config['parent_object']}")
                    except ImportError:
                        st.error("❌ SOQL lookup discovery module not found")
                    except Exception as e:
                        st.error(f"❌ Error in auto-discovery: {str(e)}")
            
            st.markdown("---")
            st.markdown("### ⚙️ Manual Lookup Field Configuration")
            st.info("💡 Or manually configure each lookup field using the options below.")
            
            with st.expander("ℹ️ About Lookup Fields", expanded=False):
                st.markdown("""
                **Business Lookup Fields** (User-Defined):
                - Parent/child relationships in your data model
                - Example: AccountId, ContactId, CustomParent__c
                - ✅ **MUST be configured** for proper migration
                
                **System Lookup Fields** (Salesforce-Managed):
                - OwnerId, CreatedById, LastModifiedById, RecordTypeId
                - ⚙️ Usually handled automatically by Salesforce
                - ⚠️ CreatedById, LastModifiedById **cannot be set** during migration
                - 💡 OwnerId defaults to current user if not specified
                """)
            
            # Get field metadata
            source_fields = get_object_fields(source_sf, object_name)
            
            # Identify lookup fields (excluding system fields by default)
            business_lookup_fields = identify_lookup_fields(source_fields, include_system_fields=False)
            all_lookup_fields = identify_lookup_fields(source_fields, include_system_fields=True)
            system_lookup_count = len(all_lookup_fields) - len(business_lookup_fields)
            
            # Show filter options
            col1, col2 = st.columns([3, 1])
            with col1:
                show_system_fields = st.checkbox(
                    f"Show System Lookup Fields ({system_lookup_count})",
                    value=False,
                    help="System fields like OwnerId, CreatedById are usually handled automatically"
                )
            
            # Select which lookup fields to display
            if show_system_fields:
                lookup_fields = all_lookup_fields
                st.info(f"📊 Showing all {len(lookup_fields)} lookup fields (including {system_lookup_count} system fields)")
            else:
                lookup_fields = business_lookup_fields
                if len(business_lookup_fields) > 0:
                    st.success(f"✅ Found {len(business_lookup_fields)} business lookup field(s)")
                else:
                    st.info("ℹ️ No business lookup fields found (only system fields exist)")
            
            # Show system field guidance if they exist
            if system_lookup_count > 0 and not show_system_fields:
                st.info(f"💡 {system_lookup_count} system lookup field(s) hidden. These are typically auto-handled by Salesforce.")
            
            if not lookup_fields:
                st.info("ℹ️ No lookup fields found in this object.")
                return
            
            st.success(f"✅ Found {len(lookup_fields)} lookup field(s)")
            
            # Configure each lookup field
            for i, lookup_info in enumerate(lookup_fields):
                lookup_field = lookup_info['field_name']
                parent_objects = lookup_info['reference_to']
                parent_object = parent_objects[0] if parent_objects else "Unknown"
                is_system_field = lookup_info.get('is_system', False)
                
                # Build expander title with system field indicator
                expander_title = f"🔗 {lookup_field} → {parent_object}"
                if is_system_field:
                    expander_title += " ⚙️ (System Field)"
                
                with st.expander(expander_title, expanded=not is_system_field):
                    st.markdown(f"**Lookup Type**: {lookup_info['type']}")
                    st.markdown(f"**Parent Object**: {parent_object}")
                    
                    # Show special guidance for system fields
                    if is_system_field:
                        if lookup_field in ['CreatedById', 'LastModifiedById']:
                            st.warning("⚠️ **System-Managed Field**: This field is automatically set by Salesforce and **cannot be modified** during migration.")
                            st.info("💡 **Action**: Skip configuration - Salesforce will set this automatically")
                            continue  # Skip configuration for these fields
                        
                        elif lookup_field == 'OwnerId':
                            st.info("💡 **Default Behavior**: If not configured, records will be owned by the user running the migration")
                            st.markdown("**Options**:")
                            st.markdown("- Configure matching to preserve original owner (e.g., match by Email)")
                            st.markdown("- Skip configuration to use default (current user)")
                        
                        elif lookup_field == 'RecordTypeId':
                            st.info("💡 **Default Behavior**: Uses the default Record Type if not specified")
                            st.markdown("**Options**:")
                            st.markdown("- Configure matching by DeveloperName or Name")
                            st.markdown("- Skip configuration to use default Record Type")
                        
                        elif lookup_field == 'MasterRecordId':
                            st.warning("⚠️ **Not Applicable for Migration**: This field tracks merged records and should not be migrated")
                            st.info("💡 **Action**: Skip configuration")
                            continue  # Skip configuration
                    
                    # Add skip option
                    col1, col2 = st.columns([3, 1])
                    with col2:
                        skip_field = st.checkbox(f"Skip {lookup_field}", value=is_system_field, key=f"skip_lookup_{i}")
                    
                    if skip_field:
                        st.info(f"⏭️ {lookup_field} will be skipped during migration")
                        # Remove from config if exists
                        if lookup_field in st.session_state.migration_lookup_configs:
                            del st.session_state.migration_lookup_configs[lookup_field]
                        continue
                    
                    # Get parent object fields from TARGET org
                    try:
                        parent_fields = get_object_fields(target_sf, parent_object)
                        external_id_fields = identify_external_id_fields(parent_fields)
                        unique_fields = identify_unique_fields(parent_fields)
                        all_fields = list(parent_fields.keys())
                        
                        st.markdown(f"✅ Parent object has {len(external_id_fields)} External ID field(s), {len(unique_fields)} unique field(s)")
                        
                        # Matching strategy selection
                        matching_strategy = st.radio(
                            f"Matching Strategy for {lookup_field}:",
                            options=[
                                "external_id - Single External ID Field",
                                "field_combination - Multiple Fields (AND)",
                                "field_concatenation - Concatenated Fields"
                            ],
                            key=f"lookup_strategy_{i}",
                            help="Choose how to match parent records in target org"
                        )
                        
                        strategy_key = matching_strategy.split(" - ")[0]
                        
                        if strategy_key == "external_id":
                            # Single External ID
                            if external_id_fields:
                                selected_ext_id = st.selectbox(
                                    "Select External ID Field:",
                                    options=external_id_fields,
                                    key=f"lookup_extid_{i}"
                                )
                                
                                st.session_state.migration_lookup_configs[lookup_field] = {
                                    'parent_object': parent_object,
                                    'match_strategy': 'external_id',
                                    'match_fields': [selected_ext_id]
                                }
                                
                                st.info(f"""
                                💡 **Lookup Resolution Process:**
                                1. Read SOURCE ID: `{lookup_field} = <SOURCE_ORG_ID>`
                                2. Query SOURCE: `SELECT {selected_ext_id} FROM {parent_object} WHERE Id = <SOURCE_ORG_ID>`
                                3. Query TARGET: `SELECT Id FROM {parent_object} WHERE {selected_ext_id} = <value>`
                                4. Use TARGET ID in migrated data
                                """)
                            else:
                                st.warning(f"⚠️ No External ID fields found in {parent_object}. Use field combination or concatenation.")
                        
                        elif strategy_key == "field_combination":
                            # Multiple fields
                            selected_fields = st.multiselect(
                                "Select Fields to Combine (AND condition):",
                                options=all_fields,
                                key=f"lookup_combo_{i}",
                                help="All selected fields must match in target org"
                            )
                            
                            if selected_fields:
                                st.session_state.migration_lookup_configs[lookup_field] = {
                                    'parent_object': parent_object,
                                    'match_strategy': 'field_combination',
                                    'match_fields': selected_fields
                                }
                                
                                where_clause = " AND ".join([f"{f} = <value>" for f in selected_fields])
                                st.info(f"""
                                💡 **Lookup Resolution Process:**
                                1. Read SOURCE ID: `{lookup_field} = <SOURCE_ORG_ID>`
                                2. Query SOURCE: `SELECT {', '.join(selected_fields)} FROM {parent_object} WHERE Id = <SOURCE_ORG_ID>`
                                3. Query TARGET: `SELECT Id FROM {parent_object} WHERE {where_clause}`
                                4. Use TARGET ID in migrated data
                                """)
                        
                        elif strategy_key == "field_concatenation":
                            # Concatenated fields
                            selected_fields = st.multiselect(
                                "Select Fields to Concatenate:",
                                options=all_fields,
                                key=f"lookup_concat_{i}",
                                help="Fields will be checked together in target org"
                            )
                            
                            separator = st.text_input(
                                "Concatenation Separator:",
                                value="_",
                                key=f"lookup_sep_{i}"
                            )
                            
                            if selected_fields:
                                st.session_state.migration_lookup_configs[lookup_field] = {
                                    'parent_object': parent_object,
                                    'match_strategy': 'field_concatenation',
                                    'match_fields': selected_fields,
                                    'concat_separator': separator
                                }
                                
                                concat_example = separator.join([f"<{f}>" for f in selected_fields])
                                where_clause = " AND ".join([f"{f} = <value>" for f in selected_fields])
                                st.info(f"""
                                💡 **Lookup Resolution Process:**
                                1. Read SOURCE ID: `{lookup_field} = <SOURCE_ORG_ID>`
                                2. Query SOURCE: `SELECT {', '.join(selected_fields)} FROM {parent_object} WHERE Id = <SOURCE_ORG_ID>`
                                3. Query TARGET: `SELECT Id FROM {parent_object} WHERE {where_clause}`
                                4. Fields combined as: `{concat_example}`
                                5. Use TARGET ID in migrated data
                                """)
                    
                    except Exception as e:
                        st.error(f"Error loading parent object metadata: {str(e)}")
            
            # Summary
            st.markdown("---")
            st.markdown("### 📊 Lookup Resolution Summary")
            
            if st.session_state.migration_lookup_configs:
                for lookup_field, config in st.session_state.migration_lookup_configs.items():
                    st.success(f"✅ **{lookup_field}** → {config['parent_object']} (Strategy: {config['match_strategy']})")
                    st.caption(f"   Match Fields: {', '.join(config['match_fields'])}")
            else:
                st.warning("⚠️ No lookup configurations defined yet")
    
    # ============================================================================
    # TAB 7: DATA PREVIEW & REVIEW
    # ============================================================================
    with tab7:
        st.subheader("👁️ Data Preview & Migration Readiness")
        st.markdown("""
        Review your migration data and verify all pre-flight checks before executing the migration.
        """)
        
        # Check if we have data from any validation tab
        preview_data = None
        data_source = "Unknown"
        
        if 'migration_validation_data' in st.session_state:
            preview_data = st.session_state.migration_validation_data
            data_source = "Pre-Migration Validation"
        elif 'rules_validation_data' in st.session_state:
            preview_data = st.session_state.rules_validation_data
            data_source = "Business Rules Validation"
        elif 'quality_check_data' in st.session_state:
            preview_data = st.session_state.quality_check_data
            data_source = "Data Quality Checks"
        elif 'migration_data' in st.session_state:
            preview_data = st.session_state.migration_data
            data_source = "Migration Execution"
        
        if preview_data is not None:
            st.info(f"ℹ️ Data Source: **{data_source}**")
            
            # Tabs for different views
            view_tab1, view_tab2, view_tab3, view_tab4 = st.tabs([
                "📊 Overview",
                "🎯 Sample Records",
                "✅ Pre-Flight Checks",
                "📋 Validation Summary"
            ])
            
            with view_tab1:
                st.markdown("### Data Overview")
                try:
                    from ui_components.org_migration_preview import display_data_overview
                    display_data_overview(preview_data)
                except Exception as e:
                    st.error(f"Error displaying overview: {str(e)}")
            
            with view_tab2:
                st.markdown("### Random Sample Records")
                num_samples = st.slider("Number of samples to display:", 1, 20, 5)
                try:
                    from ui_components.org_migration_preview import display_data_samples
                    display_data_samples(preview_data, num_samples)
                except Exception as e:
                    st.error(f"Error displaying samples: {str(e)}")
            
            with view_tab3:
                st.markdown("### Pre-Flight Validation Checks")
                try:
                    from ui_components.org_migration_preview import check_pre_flight_validations, display_migration_readiness
                    
                    # Get configuration for checks
                    required_cols = st.session_state.get('migration_field_mappings', {}).keys()
                    pf_config = {
                        'required_columns': list(required_cols),
                        'critical_fields': list(required_cols)[:5],  # First 5 required fields
                        'expected_field_count': len(preview_data.columns),
                        'max_size_mb': 500
                    }
                    
                    # Run pre-flight checks
                    pf_results = check_pre_flight_validations(preview_data, pf_config)
                    
                    # Display readiness status
                    is_ready = display_migration_readiness(st.session_state)
                    
                    # Display pre-flight check results
                    col1, col2 = st.columns([1, 2])
                    with col1:
                        st.metric("Checks Passed", f"{pf_results['passed_checks']}/{pf_results['total_checks']}")
                    with col2:
                        if pf_results['blocking_issues']:
                            st.error(f"**Blocking Issues:** {len(pf_results['blocking_issues'])}")
                            for issue in pf_results['blocking_issues']:
                                st.write(f"  ❌ {issue}")
                        elif pf_results['warnings']:
                            st.warning(f"**Warnings:** {len(pf_results['warnings'])}")
                            for warning in pf_results['warnings']:
                                st.write(f"  ⚠️ {warning}")
                        else:
                            st.success("✅ All pre-flight checks passed!")
                
                except Exception as e:
                    st.error(f"Error running pre-flight checks: {str(e)}")
            
            with view_tab4:
                st.markdown("### Validation Summary")
                try:
                    from ui_components.org_migration_preview import display_validation_summary, summarize_validation_findings
                    
                    # Display validation status
                    validation_status = display_validation_summary(st.session_state)
                    
                    st.divider()
                    
                    # Summary of findings
                    findings = summarize_validation_findings(st.session_state)
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Issues Found", findings['total_issues'])
                    with col2:
                        st.metric("Risk Level", findings['overall_risk'])
                    with col3:
                        status_icon = "🟢" if findings['overall_risk'] == 'LOW' else "🟡" if findings['overall_risk'] == 'MEDIUM' else "🔴"
                        st.write(f"{status_icon} **Migration Risk: {findings['overall_risk']}**")
                    
                    # Display issues
                    if findings['blocking_issues']:
                        st.error("**Blocking Issues (Must Fix):**")
                        for issue in findings['blocking_issues']:
                            st.write(f"  ❌ {issue}")
                    
                    if findings['warnings']:
                        st.warning("**Warnings (Review):**")
                        for warning in findings['warnings']:
                            st.write(f"  ⚠️ {warning}")
                    
                    if not findings['blocking_issues'] and not findings['warnings']:
                        st.success("✅ No issues found - ready for migration!")
                
                except Exception as e:
                    st.error(f"Error displaying validation summary: {str(e)}")
            
            st.divider()
            
            # Final actions
            st.markdown("### Next Steps")
            col1, col2 = st.columns(2)
            
            with col1:
                if not preview_data.empty:
                    # Download data preview
                    csv_buffer = preview_data.head(100).to_csv(index=False)
                    st.download_button(
                        label="📥 Download Data Sample (first 100 rows)",
                        data=csv_buffer,
                        file_name=f"migration_preview_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
            
            with col2:
                if st.session_state.get('migration_object'):
                    st.info("Click '8️⃣ Execute Migration' to proceed with the migration")
        
        else:
            st.info("📤 Load data through the validation tabs (Pre-Migration, Business Rules, or Data Quality) to preview it here")
    
    # ============================================================================
    # TAB 8: EXECUTE MIGRATION
    # ============================================================================
    with tab8:
        st.subheader("🚀 Execute Migration")
        
        if not st.session_state.migration_object:
            st.warning("⚠️ Please complete configuration in previous tabs first.")
            return
        
        # Show configuration summary
        if st.session_state.get('migration_using_soql_mode'):
            st.info("📋 **Mode:** SOQL Query-based field selection" + 
                   (f" with WHERE filter: `{st.session_state.get('migration_where_clause')}`" 
                    if st.session_state.get('migration_where_clause') else ""))
        else:
            st.info("📋 **Mode:** Manual field mapping")
        
        # Validation
        st.markdown("### ✅ Pre-Migration Validation")
        
        validation_passed = True
        
        # Check connections
        if 'source_sf_conn' not in st.session_state or 'target_sf_conn' not in st.session_state:
            st.error("❌ Source or Target org not connected")
            validation_passed = False
        else:
            st.success("✅ Source and Target orgs connected")
        
        # Check field mappings
        if not st.session_state.migration_field_mappings:
            st.warning("⚠️ No field mappings configured")
            validation_passed = False
        else:
            mapped_count = len([m for m in st.session_state.migration_field_mappings.values() if m != "-- Skip --"])
            st.success(f"✅ {mapped_count} fields mapped")
        
        # Check lookup configurations - ONLY for fields being migrated
        st.markdown("### 🔗 Lookup Fields Check")
        
        # Get ALL fields from source object
        source_fields = get_object_fields(st.session_state.source_sf_conn, st.session_state.migration_object)
        all_lookup_fields = identify_lookup_fields(source_fields)
        
        # Get ONLY the fields being migrated (from field mappings)
        migrated_fields = list(st.session_state.migration_field_mappings.keys())
        
        # Extract field names from lookup field dicts and check if any MIGRATED fields are lookup fields
        lookup_field_names = [field['field_name'] for field in all_lookup_fields]
        lookup_fields_in_migration = [f for f in migrated_fields if f in lookup_field_names]
        
        if lookup_fields_in_migration:
            # Migrated fields include lookups - check if configured
            st.info(f"📍 Detected {len(lookup_fields_in_migration)} lookup field(s) in migrated fields: {', '.join(lookup_fields_in_migration)}")
            
            configured_lookups = len(st.session_state.migration_lookup_configs)
            total_lookups = len(lookup_fields_in_migration)
            
            if configured_lookups == total_lookups:
                st.success(f"✅ All {total_lookups} lookup field(s) configured")
            else:
                st.warning(f"⚠️ {configured_lookups}/{total_lookups} lookup field(s) configured")
                st.info("💡 Unconfigured lookup fields will be set to NULL")
        else:
            # No lookups in migrated fields - no lookup configuration needed
            st.success(f"✅ No lookup fields in selected fields - will proceed to migration directly")
        
        st.markdown("---")
        
        if validation_passed:
            st.markdown("### 🎯 Migration Options")
            
            col1, col2 = st.columns(2)
            
            with col1:
                migration_operation = st.radio(
                    "Migration Operation:",
                    options=["INSERT", "UPSERT", "UPDATE"],
                    help="Choose how to load data into target org"
                )
            
            with col2:
                batch_size = st.number_input(
                    "Batch Size:",
                    min_value=50,
                    max_value=2000,
                    value=500,
                    step=50,
                    help="Number of records per batch"
                )
            
            # Extract options
            st.markdown("### 📤 Data Extraction from Source Org")
            
            # Check if SOQL mode was used with WHERE clause
            if st.session_state.get('migration_using_soql_mode') and st.session_state.get('migration_where_clause'):
                st.success(f"✅ Using WHERE clause from SOQL query (Field Mapping tab)")
                st.code(st.session_state.migration_where_clause, language="sql")
                st.info("💡 This filter will be automatically applied during extraction")
                extract_filter = st.session_state.migration_where_clause
                
                # Option to override
                if st.checkbox("Override with different filter"):
                    extract_filter = st.text_area(
                        "Custom SOQL WHERE Clause:",
                        value=st.session_state.migration_where_clause,
                        placeholder="Type != 'Test' AND CreatedDate > 2024-01-01",
                        help="Override the WHERE clause from SOQL query"
                    )
            else:
                extract_filter = st.text_area(
                    "SOQL WHERE Clause (optional):",
                    placeholder="Type != 'Test' AND CreatedDate > 2024-01-01",
                    help="Filter records to extract from source org. Example: Industry = 'Technology' AND AnnualRevenue > 1000000"
                )
            
            max_records = st.number_input(
                "Maximum Records to Extract:",
                min_value=1,
                max_value=100000,
                value=10000,
                step=100,
                help="Specify how many records to extract (1 to 100,000)"
            )
            
            # Show extraction preview
            st.markdown("#### 📋 Extraction Preview")
            
            preview_fields = list(st.session_state.migration_field_mappings.keys())
            if st.session_state.get('migration_main_match_fields'):
                preview_fields.extend(st.session_state.migration_main_match_fields)
            
            preview_soql = f"SELECT {', '.join(list(set(preview_fields))[:5])}{'...' if len(set(preview_fields)) > 5 else ''} FROM {st.session_state.migration_object}"
            if extract_filter:
                preview_soql += f" WHERE {extract_filter}"
            preview_soql += f" LIMIT {max_records}"
            
            st.code(preview_soql, language="sql")
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Fields to Extract", len(set(preview_fields)))
            with col2:
                st.metric("Record Limit", f"{max_records:,}")
            
            if extract_filter:
                st.success(f"✅ Filter applied: {len(extract_filter)} characters")
            else:
                st.info("ℹ️ No filter - will extract all available records (up to limit)")
            
            st.markdown("---")
            
            # Show message based on migration_operation
            if migration_operation == "INSERT":
                st.info("📌 **INSERT Mode:** Check for existing records to avoid duplicate insertion.")
            else:
                st.warning(f"📌 **{migration_operation} Mode:** Existing records will be {migration_operation}D. Validating duplicates is recommended.")
            
            st.markdown("---")
            
            # Check Existing Records button (available for all operations)
            if st.button("🔍 Check Existing Records in Target Org", help="Detect which records already exist to prevent duplicates"):
                if not st.session_state.get('migration_main_match_strategy'):
                    st.error("❌ Please configure Main Object Matching Strategy in Lookup Resolution tab first to check for duplicates")
                else:
                    st.markdown("### 🔍 Checking Existing Records")
                    
                    try:
                        source_sf = st.session_state.source_sf_conn
                        target_sf = st.session_state.target_sf_conn
                        object_name = st.session_state.migration_object
                        
                        # Extract sample data from source
                        st.info("📤 Extracting sample data from source org...")
                        
                        match_fields = st.session_state.migration_main_match_fields
                        field_list = list(set(list(st.session_state.migration_field_mappings.keys()) + match_fields))
                        
                        soql = f"SELECT {', '.join(field_list)} FROM {object_name}"
                        if extract_filter:
                            soql += f" WHERE {extract_filter}"
                        soql += f" LIMIT {min(max_records, 1000)}"  # Sample check
                        
                        result = source_sf.query(soql)
                        source_data = pd.DataFrame(result['records']).drop(columns=['attributes'], errors='ignore')
                        
                        # Filter to keep only mapped fields (exclude unmapped/auto-generated fields like Id)
                        mapped_source_fields = [src for src, tgt in st.session_state.migration_field_mappings.items() 
                                                if tgt != "-- Skip --"]
                        fields_to_keep = list(set(mapped_source_fields + match_fields))
                        fields_to_keep = [f for f in fields_to_keep if f in source_data.columns]
                        source_data = source_data[fields_to_keep]
                        
                        st.success(f"✅ Extracted {len(source_data)} records for validation (keeping only {len(fields_to_keep)} mapped fields)")
                        
                        # Validate existing records
                        st.info("🔍 Checking which records already exist in target org...")
                        
                        validation_results = validate_existing_records_in_target(
                            target_sf=target_sf,
                            object_name=object_name,
                            match_strategy=st.session_state.migration_main_match_strategy,
                            match_fields=st.session_state.migration_main_match_fields,
                            source_data=source_data,
                            concat_separator=st.session_state.get('migration_main_concat_separator', '_')
                        )
                        
                        # Display results
                        st.markdown("---")
                        st.markdown("### 📊 Validation Results")
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("🆕 New Records", validation_results['new_count'])
                            st.caption("Will be INSERTED")
                        with col2:
                            st.metric("♻️ Existing Records", validation_results['existing_count'])
                            st.caption("Will be UPDATED/SKIPPED")
                        with col3:
                            st.metric("⚠️ Invalid Records", validation_results['invalid_count'])
                            st.caption("Missing match field values")
                        
                        # Show existing records details
                        if validation_results['existing_count'] > 0:
                            with st.expander(f"📋 View {validation_results['existing_count']} Existing Records", expanded=False):
                                st.warning(f"⚠️ These records already exist in target org and will be {'UPDATED' if migration_operation == 'UPSERT' or migration_operation == 'UPDATE' else 'SKIPPED'}:")
                                
                                existing_df = pd.DataFrame(validation_results['existing_records'])
                                st.dataframe(existing_df[['salesforce_id', 'match_values']].head(50))
                                
                                if len(validation_results['existing_records']) > 50:
                                    st.info(f"Showing first 50 of {len(validation_results['existing_records'])} existing records")
                        
                        # Show new records
                        if validation_results['new_count'] > 0:
                            st.success(f"✅ {validation_results['new_count']} records will be inserted as new records")
                        
                        # Show invalid records
                        if validation_results['invalid_count'] > 0:
                            with st.expander(f"⚠️ View {validation_results['invalid_count']} Invalid Records", expanded=False):
                                st.error("These records have missing values in match fields and cannot be processed:")
                                invalid_df = pd.DataFrame(validation_results['invalid_records'])
                                st.dataframe(invalid_df)
                        
                        # Store validation results in session state
                        st.session_state['validation_results'] = validation_results
                        st.session_state['validation_completed'] = True
                        
                    except Exception as e:
                        st.error(f"❌ Validation failed: {str(e)}")
                        st.exception(e)
            
            st.markdown("---")
            
            # Execute button
            if st.button("🚀 Start Migration", type="primary"):
                st.markdown("### 📊 Migration Progress")
                
                # Start timing
                import time
                start_time = time.time()
                
                # Check if validation was completed or needed
                if migration_operation in ["UPSERT", "UPDATE"]:
                    # For UPSERT/UPDATE, validation is strongly recommended
                    if not st.session_state.get('validation_completed'):
                        st.warning("⚠️ Recommendation: Run 'Check Existing Records' first to see which records will be inserted vs updated")
                        if not st.checkbox("I understand - proceed without validation check"):
                            st.stop()
                else:
                    # For INSERT, recommend validation to avoid duplicates
                    if not st.session_state.get('validation_completed'):
                        st.info("ℹ️ INSERT Mode: It's recommended to check for existing records to avoid duplicate insertion")
                        if not st.checkbox("I understand - proceed with validation (or skip if already checked)"):
                            st.stop()
                    else:
                        st.success("✅ Validation completed - will insert only new records")
                
                try:
                    # Extract from source
                    st.info("📤 Step 1/5: Extracting data from source org...")
                    
                    source_sf = st.session_state.source_sf_conn
                    object_name = st.session_state.migration_object
                    
                    # Build SOQL query
                    field_list = list(st.session_state.migration_field_mappings.keys())
                    
                    # Add main object match fields (for duplicate checking in target)
                    if st.session_state.get('migration_main_match_fields'):
                        field_list.extend(st.session_state.migration_main_match_fields)
                    
                    # NOTE: Do NOT add lookup match fields here!
                    # Lookup match fields are parent object fields, not source object fields
                    # We'll use the lookup field (e.g., WOD_2__Dealer__c) ID to fetch them from parent
                    
                    # Add lookup fields themselves (the reference/lookup fields)
                    for lookup_field in st.session_state.migration_lookup_configs.keys():
                        if lookup_field not in field_list:
                            field_list.append(lookup_field)
                    
                    field_list = list(set(field_list))  # Remove duplicates
                    
                    soql = f"SELECT {', '.join(field_list)} FROM {object_name}"
                    if extract_filter:
                        soql += f" WHERE {extract_filter}"
                    soql += f" LIMIT {max_records}"
                    
                    st.code(soql, language="sql")
                    
                    result = source_sf.query(soql)
                    source_data = pd.DataFrame(result['records']).drop(columns=['attributes'], errors='ignore')
                    
                    st.success(f"✅ Extracted {len(source_data)} records from source org")
                    
                    # Apply field mappings
                    st.info("🗺️ Step 2/5: Applying field mappings and filtering to ONLY mapped fields...")
                    
                    # Get only mapped fields (exclude unmapped and auto-generated fields like Id)
                    mapped_fields = {src: tgt for src, tgt in st.session_state.migration_field_mappings.items() 
                                     if tgt != "-- Skip --"}
                    
                    # Build list of fields to keep: mapped fields + match fields + lookup match fields
                    fields_to_keep = list(mapped_fields.keys())
                    
                    # Add main object match fields (needed for validation)
                    if st.session_state.get('migration_main_match_fields'):
                        fields_to_keep.extend(st.session_state.migration_main_match_fields)
                    
                    # Add lookup match fields (needed for lookup resolution)
                    for lookup_config in st.session_state.migration_lookup_configs.values():
                        fields_to_keep.extend(lookup_config['match_fields'])
                    
                    fields_to_keep = list(set(fields_to_keep))  # Remove duplicates
                    fields_to_keep = [f for f in fields_to_keep if f in source_data.columns]  # Keep only existing columns
                    
                    # Filter source_data to keep ONLY the fields we need
                    mapped_data = source_data[fields_to_keep].copy()
                    
                    # Rename source fields to target field names
                    for source_field, target_field in mapped_fields.items():
                        if source_field in mapped_data.columns and source_field != target_field:
                            mapped_data.rename(columns={source_field: target_field}, inplace=True)
                    
                    st.success(f"✅ Applied field mappings: Keeping only {len(mapped_fields)} mapped fields (excluded unmapped/auto-generated fields)")
                    
                    # Check existing records (needed for all operations to detect duplicates)
                    if st.session_state.get('migration_main_match_strategy'):
                        st.info("🔍 Step 3/5: Checking for existing records in TARGET org...")
                        
                        final_validation = validate_existing_records_in_target(
                            target_sf=target_sf,
                            object_name=object_name,
                            match_strategy=st.session_state.migration_main_match_strategy,
                            match_fields=st.session_state.migration_main_match_fields,
                            source_data=mapped_data,
                            concat_separator=st.session_state.get('migration_main_concat_separator', '_')
                        )
                        
                        st.success(f"✅ Validation: {final_validation['new_count']} new, {final_validation['existing_count']} existing")
                        
                        # Handle duplicates based on operation type
                        if migration_operation == "INSERT" and final_validation['existing_count'] > 0:
                            st.warning(f"⚠️ Found {final_validation['existing_count']} duplicate records that already exist in target")
                            
                            # For INSERT, filter out duplicates
                            st.info(f"ℹ️ INSERT Mode: Will insert only {final_validation['new_count']} new records (skipping {final_validation['existing_count']} duplicates)")
                            
                            # Get indices of new records only
                            new_record_indices = [r['index'] for r in final_validation['new_records']]
                            mapped_data = mapped_data.iloc[new_record_indices].reset_index(drop=True)
                            
                            if len(mapped_data) == 0:
                                st.error("❌ No new records to insert - all records already exist in target org")
                                st.stop()
                            
                            st.success(f"✅ Prepared {len(mapped_data)} new records for insertion")
                        
                        elif migration_operation == "UPSERT" and final_validation['existing_count'] > 0:
                            st.info(f"ℹ️ UPSERT Mode: Will update {final_validation['existing_count']} existing records and insert {final_validation['new_count']} new ones")
                        
                        elif migration_operation == "UPDATE" and final_validation['new_count'] > 0:
                            st.warning(f"⚠️ UPDATE Mode: {final_validation['new_count']} records don't exist in target - they will be skipped")
                            # Filter to keep only existing records
                            existing_record_indices = [r['index'] for r in final_validation['existing_records']]
                            mapped_data = mapped_data.iloc[existing_record_indices].reset_index(drop=True)
                            
                            if len(mapped_data) == 0:
                                st.error("❌ No existing records to update")
                                st.stop()
                            
                            st.success(f"✅ Prepared {len(mapped_data)} records for update")
                    else:
                        st.info("ℹ️ Skipping duplicate check (match strategy not configured)")
                    
                    # Conditional: Resolve lookups only if lookup fields exist
                    if st.session_state.migration_lookup_configs:
                        # Lookup fields exist - Resolution is MANDATORY
                        st.info("🔗 Step 4/5: Resolving lookup relationships (2-step process: Extract from SOURCE → Find in TARGET)...")
                        
                        source_sf = st.session_state.source_sf_conn
                        target_sf = st.session_state.target_sf_conn
                        
                        progress_text = st.empty()
                        resolved_data, resolution_stats = resolve_lookup_relationships_for_migration(
                            source_df=mapped_data,
                            source_sf=source_sf,
                            target_sf=target_sf,
                            lookup_configs=st.session_state.migration_lookup_configs,
                            progress_callback=lambda msg: progress_text.info(msg)
                        )
                        
                        st.success(f"✅ Resolved lookups:")
                        for lookup_field, count in resolution_stats['resolved'].items():
                            st.write(f"   • {lookup_field}: {count} resolved, {resolution_stats['unresolved'][lookup_field]} unresolved")
                        
                        # Load to target
                        st.info("📥 Step 5/5: Loading data to target org...")
                    else:
                        # No lookup fields exist - Skip lookup resolution, proceed directly to migration
                        st.success("✅ **No lookup fields detected** in selected fields - Proceeding directly to migration")
                        resolved_data = mapped_data.copy()  # Use mapped data as-is
                        
                        # Load to target
                        st.info("📥 Step 4/4: Loading data to target org...")
                    
                    # Remove null lookup fields (only if lookups exist)
                    if st.session_state.migration_lookup_configs:
                        for lookup_field in st.session_state.migration_lookup_configs.keys():
                            if lookup_field in resolved_data.columns:
                                resolved_data[lookup_field] = resolved_data[lookup_field].where(pd.notna(resolved_data[lookup_field]), None)
                    
                    # Final filter: Keep ONLY target field names (mapped fields + resolved lookups)
                    # This ensures no unmapped/auto-generated fields (like Id) are sent to target
                    target_field_names = list(st.session_state.migration_field_mappings.values())
                    target_field_names = [f for f in target_field_names if f != "-- Skip --"]
                    if st.session_state.migration_lookup_configs:  # Only add lookup fields if they exist
                        target_field_names.extend(st.session_state.migration_lookup_configs.keys())  # Add lookup fields
                    target_field_names = list(set(target_field_names))  # Remove duplicates
                    
                    # Keep only columns that exist in resolved_data and are in target field names
                    final_fields = [f for f in target_field_names if f in resolved_data.columns]
                    resolved_data = resolved_data[final_fields]
                    
                    st.info(f"📋 Sending {len(final_fields)} fields to target org: {', '.join(sorted(final_fields))}")
                    
                    # Convert to records
                    records = resolved_data.to_dict('records')
                    
                    # Execute migration
                    batches = [records[i:i + batch_size] for i in range(0, len(records), batch_size)]
                    
                    success_count = 0
                    error_count = 0
                    error_details = []  # Store detailed error information
                    success_details = []  # Store success details
                    
                    progress_bar = st.progress(0)
                    
                    for i, batch in enumerate(batches):
                        try:
                            if migration_operation == "INSERT":
                                result = getattr(target_sf.bulk, object_name).insert(batch)
                            elif migration_operation == "UPSERT":
                                # Requires external ID field
                                ext_id_field = list(st.session_state.migration_lookup_configs.values())[0]['match_fields'][0]
                                result = getattr(target_sf.bulk, object_name).upsert(batch, ext_id_field)
                            elif migration_operation == "UPDATE":
                                result = getattr(target_sf.bulk, object_name).update(batch)
                            
                            for idx, r in enumerate(result):
                                if r['success']:
                                    success_count += 1
                                    success_details.append({
                                        'record_index': len(success_details) + error_count,
                                        'salesforce_id': r.get('id', 'N/A'),
                                        'operation': migration_operation
                                    })
                                else:
                                    error_count += 1
                                    # Extract detailed error information using helper function
                                    # Try multiple possible error field locations
                                    error_message = extract_detailed_error_message(r.get('error'))
                                    
                                    # If no error found, check other possible fields
                                    if error_message == "Unknown error - no error details provided":
                                        # Try common alternative field names
                                        for alt_field in ['errors', 'errorMessage', 'message', 'err']:
                                            if alt_field in r and r[alt_field]:
                                                error_message = extract_detailed_error_message(r[alt_field])
                                                if error_message != "Unknown error - no error details provided":
                                                    break
                                    
                                    error_details.append({
                                        'record_index': idx + (i * batch_size),
                                        'error': error_message,
                                        'record_data': batch[idx],
                                        'operation': migration_operation,
                                        'raw_error': r.get('error'),  # Store raw error for debugging
                                        'complete_response': dict(r)  # Store complete response for debugging
                                    })
                        
                        except Exception as e:
                            st.error(f"Batch {i+1} failed: {str(e)}")
                            error_count += len(batch)
                            for idx, rec in enumerate(batch):
                                error_details.append({
                                    'record_index': idx + (i * batch_size),
                                    'error': str(e),
                                    'record_data': rec,
                                    'operation': migration_operation
                                })
                        
                        progress_bar.progress((i + 1) / len(batches))
                    
                    st.markdown("---")
                    st.markdown("### 📊 Migration Results")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("✅ Success", success_count, delta=f"{(success_count / len(records) * 100):.1f}%" if len(records) > 0 else "0%")
                    with col2:
                        st.metric("❌ Failed", error_count, delta=f"{(error_count / len(records) * 100):.1f}%" if len(records) > 0 else "0%")
                    with col3:
                        st.metric("📊 Total", len(records))
                    
                    st.divider()
                    
                    # Display Success Details if any
                    if success_count > 0:
                        st.success(f"✅ {success_count} records successfully {migration_operation.lower()}ed")
                        
                        # Create success summary table if success_details exists
                        if 'success_details' in locals() and success_details:
                            success_df = pd.DataFrame([
                                {
                                    'Record #': d['record_index'] + 1,
                                    'Salesforce ID': d['salesforce_id'],
                                    'Operation': d['operation']
                                }
                                for d in success_details[:20]  # Show first 20
                            ])
                            
                            with st.expander(f"View Success Details ({len(success_details)} total)", expanded=False):
                                st.dataframe(success_df, use_container_width=True, hide_index=True)
                                if len(success_details) > 20:
                                    st.info(f"Showing 20 of {len(success_details)} successful records")
                    
                    # Display Error Details if any
                    if error_count > 0 and 'error_details' in locals() and error_details:
                        st.error(f"❌ {error_count} records failed to {migration_operation.lower()}")
                        
                        # Create error summary table
                        error_summary = []
                        for d in error_details:
                            error_summary.append({
                                'Record #': d['record_index'] + 1,
                                'Error Reason': d['error'][:100] + '...' if len(d['error']) > 100 else d['error'],
                                'Operation': d['operation']
                            })
                        
                        error_df = pd.DataFrame(error_summary)
                        
                        with st.expander(f"📋 View Error Details ({len(error_details)} total)", expanded=True):
                            st.dataframe(error_df, use_container_width=True, hide_index=True)
                            
                            # Show detailed error information for each failed record
                            st.subheader("🔍 Detailed Error Information")
                            
                            for idx, err in enumerate(error_details):
                                with st.expander(f"Record #{err['record_index'] + 1}: {err['error'][:80]}..."):
                                    col1, col2 = st.columns([1, 2])
                                    
                                    with col1:
                                        st.write("**Error Message:**")
                                        st.error(err['error'])
                                        
                                        # Show raw error for debugging if available
                                        if 'raw_error' in err and err['raw_error']:
                                            with st.expander("🔧 Raw Error Field (for debugging)"):
                                                st.code(json.dumps(err['raw_error'], indent=2), language="json")
                                        
                                        # Show complete response for debugging
                                        if 'complete_response' in err:
                                            with st.expander("📊 Complete Salesforce Response (for debugging)"):
                                                st.info("This shows all fields returned by Salesforce for this record:")
                                                st.code(json.dumps(err['complete_response'], indent=2, default=str), language="json")
                                    
                                    with col2:
                                        st.write("**Record Data:**")
                                        st.json(err['record_data'])
                                
                                if idx >= 9:  # Show first 10 detailed errors
                                    st.info(f"Showing 10 of {len(error_details)} errors. Download CSV for complete list.")
                                    break
                        
                        # Add export option for errors
                        st.divider()
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            error_export_df = pd.DataFrame([
                                {
                                    'Record #': d['record_index'] + 1,
                                    'Error': d['error'],
                                    'Operation': d['operation'],
                                    **d['record_data']
                                }
                                for d in error_details
                            ])
                            
                            csv_buffer = io.StringIO()
                            error_export_df.to_csv(csv_buffer, index=False)
                            
                            st.download_button(
                                label="📥 Download Failed Records (CSV)",
                                data=csv_buffer.getvalue(),
                                file_name=f"failed_records_{migration_operation}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv"
                            )
                        
                        with col2:
                            # Log error details to file
                            log_content = f"""Migration Error Report
=====================
Object: {st.session_state.migration_object}
Operation: {migration_operation}
Source Org: {st.session_state.migration_source_org}
Target Org: {st.session_state.migration_target_org}
Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Total Failed Records: {len(error_details)}

Error Details:
"""
                            for err in error_details:
                                log_content += f"\n\nRecord #{err['record_index'] + 1}:\n"
                                log_content += f"Error: {err['error']}\n"
                                log_content += f"Data: {json.dumps(err['record_data'], indent=2)}\n"
                                
                                # Add complete response details for debugging
                                if 'complete_response' in err:
                                    log_content += f"\nComplete Salesforce Response:\n"
                                    log_content += json.dumps(err['complete_response'], indent=2, default=str)
                                    log_content += "\n"
                            
                            st.download_button(
                                label="📄 Download Error Log (TXT)",
                                data=log_content,
                                file_name=f"migration_errors_{migration_operation}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                                mime="text/plain"
                            )
                    
                    if success_count > 0:
                        st.success(f"🎉 Migration completed! {success_count}/{len(records)} records migrated successfully")
                        
                        # Save migration execution log
                        try:
                            execution_time = time.time() - start_time
                            log_path = save_migration_execution_log(
                                source_org=st.session_state.migration_source_org,
                                target_org=st.session_state.migration_target_org,
                                object_name=st.session_state.migration_object,
                                field_mappings=st.session_state.migration_field_mappings,
                                lookup_configs=st.session_state.migration_lookup_configs,
                                main_match_strategy=st.session_state.get('migration_main_match_strategy', 'Not configured'),
                                main_match_fields=st.session_state.get('migration_main_match_fields', []),
                                migration_operation=migration_operation,
                                total_records=len(records),
                                success_count=success_count,
                                error_count=error_count,
                                execution_time=execution_time
                            )
                            st.info(f"📝 Migration history saved: {Path(log_path).name}")
                        except Exception as log_error:
                            st.warning(f"⚠️ Could not save migration log: {str(log_error)}")
                    
                except Exception as e:
                    st.error(f"❌ Migration failed: {str(e)}")
                    st.exception(e)
        else:
            st.error("❌ Please complete all configurations before executing migration")
    
    # ============================================================================
    # TAB 9: MIGRATION HISTORY
    # ============================================================================
    with tab9:
        st.subheader("📋 Migration History & Summary")
        st.markdown("View past migration executions, configurations, and results")
        
        # Get migration history
        history = get_migration_history()
        
        if not history:
            st.info("📭 No migration history found. Complete a migration to see it here!")
            st.markdown("---")
            st.markdown("""
            **What you'll see here after running migrations:**
            - ✅ Source and Target organizations
            - 📦 Objects migrated
            - 🗺️ Field mappings used
            - 🔗 Lookup resolution configurations
            - 📊 Success rates and statistics
            - ⏱️ Execution times
            - 🔄 Ability to reload past configurations
            """)
        else:
            # Summary metrics
            st.markdown("### 📊 Migration Summary")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Migrations", len(history))
            
            with col2:
                total_records = sum(h['results']['total_records'] for h in history)
                st.metric("Total Records Migrated", f"{total_records:,}")
            
            with col3:
                unique_objects = len(set(h['object'] for h in history))
                st.metric("Objects Migrated", unique_objects)
            
            with col4:
                avg_success_rate = sum(h['results']['success_rate'] for h in history) / len(history)
                st.metric("Avg Success Rate", f"{avg_success_rate:.1f}%")
            
            st.markdown("---")
            
            # Filters
            st.markdown("### 🔍 Filter Migration History")
            col_filter1, col_filter2, col_filter3 = st.columns(3)
            
            with col_filter1:
                all_sources = sorted(set(h['source_org'] for h in history))
                filter_source = st.selectbox("Filter by Source Org", ["All"] + all_sources)
            
            with col_filter2:
                all_targets = sorted(set(h['target_org'] for h in history))
                filter_target = st.selectbox("Filter by Target Org", ["All"] + all_targets)
            
            with col_filter3:
                all_objects = sorted(set(h['object'] for h in history))
                filter_object = st.selectbox("Filter by Object", ["All"] + all_objects)
            
            # Apply filters
            filtered_history = history
            if filter_source != "All":
                filtered_history = [h for h in filtered_history if h['source_org'] == filter_source]
            if filter_target != "All":
                filtered_history = [h for h in filtered_history if h['target_org'] == filter_target]
            if filter_object != "All":
                filtered_history = [h for h in filtered_history if h['object'] == filter_object]
            
            st.markdown(f"### 📜 Migration Records ({len(filtered_history)} found)")
            
            # Display migration records
            for i, migration in enumerate(filtered_history):
                execution_date = datetime.fromisoformat(migration['execution_date']).strftime("%Y-%m-%d %H:%M:%S")
                success_rate = migration['results']['success_rate']
                
                # Color code success rate
                if success_rate >= 95:
                    status_color = "🟢"
                elif success_rate >= 80:
                    status_color = "🟡"
                else:
                    status_color = "🔴"
                
                with st.expander(
                    f"{status_color} {execution_date} | {migration['source_org']} → {migration['target_org']} | {migration['object']} | {success_rate}% success",
                    expanded=False
                ):
                    # Migration Overview
                    st.markdown("#### 📊 Migration Overview")
                    
                    col_detail1, col_detail2, col_detail3 = st.columns(3)
                    
                    with col_detail1:
                        st.markdown(f"""
                        **Source Org:** {migration['source_org']}  
                        **Target Org:** {migration['target_org']}  
                        **Object:** {migration['object']}
                        """)
                    
                    with col_detail2:
                        st.markdown(f"""
                        **Operation:** {migration['migration_operation']}  
                        **Execution Time:** {migration['execution_time_seconds']}s  
                        **Date:** {execution_date}
                        """)
                    
                    with col_detail3:
                        st.markdown(f"""
                        **Total Records:** {migration['results']['total_records']:,}  
                        **Success:** {migration['results']['success_count']:,}  
                        **Errors:** {migration['results']['error_count']:,}
                        """)
                    
                    st.markdown("---")
                    
                    # Matching Strategy
                    st.markdown("#### 🎯 Record Matching Configuration")
                    st.markdown(f"""
                    - **Strategy:** {migration['main_match_strategy']}  
                    - **Match Fields:** {', '.join(migration['main_match_fields']) if migration['main_match_fields'] else 'None'}
                    """)
                    
                    # Field Mappings
                    st.markdown("#### 🗺️ Field Mappings")
                    st.write(f"**{migration['field_mapping_count']} fields mapped:**")
                    
                    # Display field mappings in a clean table
                    if migration['field_mappings']:
                        mapping_df = pd.DataFrame([
                            {"Source Field": src, "→": "→", "Target Field": tgt}
                            for src, tgt in migration['field_mappings'].items()
                        ])
                        st.dataframe(mapping_df, use_container_width=True, hide_index=True)
                    
                    # Lookup Configurations
                    if migration['lookup_configs']:
                        st.markdown("#### 🔗 Lookup Resolution")
                        st.write(f"**{migration['lookup_count']} lookup field(s) configured:**")
                        
                        for lookup_field, lookup_config in migration['lookup_configs'].items():
                            st.markdown(f"""
                            **{lookup_field}:**
                            - Parent Object: `{lookup_config.get('parent_object', 'N/A')}`
                            - Match Strategy: `{lookup_config.get('match_strategy', 'N/A')}`
                            - Match Fields: `{', '.join(lookup_config.get('match_fields', []))}`
                            """)
                    
                    st.markdown("---")
                    
                    # Action buttons
                    col_action1, col_action2 = st.columns(2)
                    
                    with col_action1:
                        if st.button(f"🔄 Reload This Configuration", key=f"reload_{i}"):
                            # Load configuration into session state
                            st.session_state.migration_source_org = migration['source_org']
                            st.session_state.migration_target_org = migration['target_org']
                            st.session_state.migration_object = migration['object']
                            st.session_state.migration_field_mappings = migration['field_mappings']
                            st.session_state.migration_lookup_configs = migration['lookup_configs']
                            st.session_state.migration_main_match_strategy = migration['main_match_strategy']
                            st.session_state.migration_main_match_fields = migration['main_match_fields']
                            
                            st.success("✅ Configuration loaded! Go to Configuration tab to review and modify.")
                            st.rerun()
                    
                    with col_action2:
                        # Download configuration as JSON
                        config_json = json.dumps(migration, indent=2)
                        st.download_button(
                            label="📥 Download Configuration",
                            data=config_json,
                            file_name=f"migration_config_{migration['object']}_{datetime.now().strftime('%Y%m%d')}.json",
                            mime="application/json",
                            key=f"download_{i}"
                        )


if __name__ == "__main__":
    st.set_page_config(page_title="Org Migration", page_icon="🔄", layout="wide")
    
    # Load credentials for testing
    try:
        with open('../Services/linkedservices.json', 'r') as f:
            credentials = json.load(f)
        show_org_migration(credentials)
    except Exception as e:
        st.error(f"Error: {str(e)}")
