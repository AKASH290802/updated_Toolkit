"""
Org Migration Module - Salesforce to Salesforce Data Migration
Handles data migration between two Salesforce orgs with parent-child relationship resolution
"""

import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
from pathlib import Path
from simple_salesforce import Salesforce
from typing import Dict, List, Tuple, Optional, Any

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
        if match_strategy == 'external_id':
            # Single External ID field
            ext_id_field = match_fields[0]
            match_value = record_values.get(ext_id_field)
            
            if not match_value or (isinstance(match_value, str) and match_value.strip() == ''):
                return False, None
            
            escaped_value = str(match_value).replace("'", "\\'")
            soql_query = f"SELECT Id FROM {object_name} WHERE {ext_id_field} = '{escaped_value}' LIMIT 1"
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
                escaped_value = str(value).replace("'", "\\'")
                conditions.append(f"{field} = '{escaped_value}'")
            
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


def query_target_org_for_parent_id(
    target_sf: Salesforce,
    parent_object: str,
    match_strategy: str,
    match_fields: List[str],
    match_values: Dict[str, Any],
    concat_separator: str = '_'
) -> Optional[str]:
    """
    Query target org to find parent record ID based on matching strategy
    
    **CRITICAL LOGIC**: This queries the TARGET org (not source) to get Salesforce IDs
    that will be used as lookup references in child records
    
    Args:
        target_sf: Target Salesforce connection
        parent_object: Parent object name (e.g., 'Account')
        match_strategy: 'external_id' | 'field_combination' | 'field_concatenation'
        match_fields: List of field names to match on
        match_values: Dictionary of field values from source record
        concat_separator: Separator for concatenation strategy
    
    Returns:
        Salesforce ID from target org, or None if not found
    """
    try:
        if match_strategy == 'external_id':
            # Single External ID field matching
            external_id_field = match_fields[0]
            match_value = match_values.get(external_id_field)
            
            if not match_value or (isinstance(match_value, str) and match_value.strip() == ''):
                return None
            
            # Query target org
            escaped_value = str(match_value).replace("'", "\\'")
            soql_query = f"SELECT Id FROM {parent_object} WHERE {external_id_field} = '{escaped_value}' LIMIT 1"
            result = target_sf.query(soql_query)
            
            if result['totalSize'] > 0:
                return result['records'][0]['Id']
            else:
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
                escaped_value = str(value).replace("'", "\\'")
                conditions.append(f"{field} = '{escaped_value}'")
            
            if not has_all_values:
                return None
            
            # Query target org with combined conditions
            where_clause = ' AND '.join(conditions)
            soql_query = f"SELECT Id FROM {parent_object} WHERE {where_clause} LIMIT 1"
            result = target_sf.query(soql_query)
            
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
                escaped_value = str(value).replace("'", "\\'")
                conditions.append(f"{field} = '{escaped_value}'")
            
            if not has_all_values:
                return None
            
            # Query target org - same as field_combination but logically represents concatenation
            where_clause = ' AND '.join(conditions)
            soql_query = f"SELECT Id FROM {parent_object} WHERE {where_clause} LIMIT 1"
            result = target_sf.query(soql_query)
            
            if result['totalSize'] > 0:
                return result['records'][0]['Id']
            else:
                return None
        
        else:
            st.error(f"Unknown match strategy: {match_strategy}")
            return None
    
    except Exception as e:
        st.warning(f"⚠️ Could not find parent record in target org: {str(e)}")
        return None


def resolve_lookup_relationships_for_migration(
    source_df: pd.DataFrame,
    target_sf: Salesforce,
    lookup_configs: Dict[str, Dict],
    progress_callback=None
) -> Tuple[pd.DataFrame, Dict]:
    """
    Resolve lookup relationships by querying TARGET org for parent IDs
    
    **KEY LOGIC**:
    1. For each child record, extract parent identifying values (External ID/combination/concatenation)
    2. Query TARGET org to find matching parent record
    3. Get parent's Salesforce ID from TARGET org
    4. Replace lookup field value with TARGET org's Salesforce ID
    
    Args:
        source_df: DataFrame with source data
        target_sf: Target Salesforce connection
        lookup_configs: Dictionary mapping lookup fields to resolution config
            Format: {
                'ParentAccountId': {
                    'parent_object': 'Account',
                    'match_strategy': 'external_id' | 'field_combination' | 'field_concatenation',
                    'match_fields': ['External_ID__c'] or ['FirstName', 'LastName'],
                    'concat_separator': '_'  # only for concatenation
                }
            }
        progress_callback: Optional callback for progress updates
    
    Returns:
        Tuple of (resolved_df, resolution_stats)
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
        match_fields = config['match_fields']
        concat_separator = config.get('concat_separator', '_')
        
        if progress_callback:
            progress_callback(f"Resolving {lookup_field} → {parent_object}...")
        
        resolved_count = 0
        unresolved_count = 0
        
        # Create new column for target org IDs
        target_ids = []
        
        for idx, row in resolved_df.iterrows():
            # Extract match values from current row
            match_values = {field: row.get(field) for field in match_fields}
            
            # Query target org for parent ID
            target_parent_id = query_target_org_for_parent_id(
                target_sf=target_sf,
                parent_object=parent_object,
                match_strategy=match_strategy,
                match_fields=match_fields,
                match_values=match_values,
                concat_separator=concat_separator
            )
            
            if target_parent_id:
                target_ids.append(target_parent_id)
                resolved_count += 1
            else:
                target_ids.append(None)
                unresolved_count += 1
        
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
    tab1, tab2, tab3, tab4 = st.tabs([
        "1️⃣ Configuration",
        "2️⃣ Field Mapping",
        "3️⃣ Lookup Resolution",
        "4️⃣ Execute Migration"
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
                
                # Auto-mapping button
                col1, col2, col3 = st.columns([2, 2, 2])
                with col1:
                    if st.button("🤖 Auto-Map Matching Fields", help="Automatically map fields with identical names"):
                        auto_mappings = {}
                        for src_field in source_fields.keys():
                            if src_field in target_fields:
                                auto_mappings[src_field] = src_field
                        st.session_state.migration_field_mappings = auto_mappings
                        st.success(f"✅ Auto-mapped {len(auto_mappings)} fields")
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
                
                for src_field, src_meta in source_fields.items():
                    # Skip system fields
                    if src_field in ['Id', 'CreatedById', 'CreatedDate', 'LastModifiedById', 'LastModifiedDate', 'SystemModstamp']:
                        continue
                    
                    current_mapping = st.session_state.migration_field_mappings.get(src_field, "-- Skip --")
                    
                    # Apply filters
                    if show_mapped_only and current_mapping == "-- Skip --":
                        continue
                    if show_unmapped_only and current_mapping != "-- Skip --":
                        continue
                    
                    # Get compatible target fields (same data type)
                    compatible_targets = ["-- Skip --"]
                    for tgt_field, tgt_meta in target_fields.items():
                        if tgt_meta['type'] == src_meta['type'] or \
                           (src_meta['type'] in ['string', 'textarea'] and tgt_meta['type'] in ['string', 'textarea']):
                            compatible_targets.append(tgt_field)
                    
                    mapping_data.append({
                        'source_field': src_field,
                        'source_type': src_meta['type'],
                        'source_label': src_meta['label'],
                        'compatible_targets': compatible_targets,
                        'current_mapping': current_mapping if current_mapping in compatible_targets else "-- Skip --"
                    })
                
                # Display mappings
                st.markdown(f"**Total Mappings**: {len([m for m in st.session_state.migration_field_mappings.values() if m != '-- Skip --'])} / {len(source_fields)}")
                
                for i, mapping in enumerate(mapping_data):
                    col1, col2, col3 = st.columns([2, 1, 2])
                    
                    with col1:
                        st.text(f"📤 {mapping['source_field']}")
                        st.caption(f"{mapping['source_label']} ({mapping['source_type']})")
                    
                    with col2:
                        st.markdown("<p style='text-align: center; font-size: 24px;'>→</p>", unsafe_allow_html=True)
                    
                    with col3:
                        selected_target = st.selectbox(
                            "Target Field",
                            options=mapping['compatible_targets'],
                            index=mapping['compatible_targets'].index(mapping['current_mapping']),
                            key=f"field_map_{i}",
                            label_visibility="collapsed"
                        )
                        
                        if selected_target != "-- Skip --":
                            st.session_state.migration_field_mappings[mapping['source_field']] = selected_target
                            st.caption(f"✅ {target_fields[selected_target]['label']} ({target_fields[selected_target]['type']})")
                        else:
                            if mapping['source_field'] in st.session_state.migration_field_mappings:
                                del st.session_state.migration_field_mappings[mapping['source_field']]
                    
                    if i < len(mapping_data) - 1:
                        st.markdown("---")
                
                # Summary
                st.markdown("---")
                col1, col2, col3 = st.columns(3)
                with col1:
                    mapped_count = len([m for m in st.session_state.migration_field_mappings.values() if m != "-- Skip --"])
                    st.metric("✅ Mapped Fields", mapped_count)
                with col2:
                    unmapped_count = len(source_fields) - mapped_count
                    st.metric("⚠️ Unmapped Fields", unmapped_count)
                with col3:
                    st.metric("📊 Total Source Fields", len(source_fields))
    
    # ============================================================================
    # TAB 3: LOOKUP RESOLUTION & RECORD MATCHING
    # ============================================================================
    with tab3:
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
                                
                                st.info(f"💡 Will query TARGET org: `SELECT Id FROM {parent_object} WHERE {selected_ext_id} = <value>`")
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
                                st.info(f"💡 Will query TARGET org: `SELECT Id FROM {parent_object} WHERE {where_clause}`")
                        
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
                                st.info(f"💡 Concatenated value: `{concat_example}`")
                                st.info(f"💡 Will query TARGET org: `SELECT Id FROM {parent_object} WHERE {where_clause}`")
                    
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
    # TAB 4: EXECUTE MIGRATION
    # ============================================================================
    with tab4:
        st.subheader("🚀 Execute Migration")
        
        if not st.session_state.migration_object:
            st.warning("⚠️ Please complete configuration in previous tabs first.")
            return
        
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
        
        # Check lookup configurations
        source_fields = get_object_fields(st.session_state.source_sf_conn, st.session_state.migration_object)
        lookup_fields = identify_lookup_fields(source_fields)
        
        if lookup_fields:
            configured_lookups = len(st.session_state.migration_lookup_configs)
            total_lookups = len(lookup_fields)
            
            if configured_lookups == total_lookups:
                st.success(f"✅ All {total_lookups} lookup field(s) configured")
            else:
                st.warning(f"⚠️ {configured_lookups}/{total_lookups} lookup field(s) configured")
                st.info("💡 Unconfigured lookup fields will be set to NULL")
        
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
            
            extract_filter = st.text_area(
                "SOQL WHERE Clause (optional):",
                placeholder="Type != 'Test' AND CreatedDate > 2024-01-01",
                help="Filter records to extract from source org"
            )
            
            max_records = st.number_input(
                "Maximum Records to Extract:",
                min_value=100,
                max_value=100000,
                value=10000,
                step=1000,
                help="Limit number of records for testing"
            )
            
            st.markdown("---")
            
            # Check Existing Records button
            if st.button("🔍 Check Existing Records in Target Org", help="Validate which records already exist before migration"):
                if not st.session_state.get('migration_main_match_strategy'):
                    st.error("❌ Please configure Main Object Matching Strategy in Lookup Resolution tab first")
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
                
                # Check if validation was completed
                if not st.session_state.get('validation_completed'):
                    st.warning("⚠️ Recommendation: Run 'Check Existing Records' first to see which records will be inserted vs updated")
                    if not st.checkbox("I understand - proceed without validation check"):
                        st.stop()
                
                try:
                    # Extract from source
                    st.info("📤 Step 1/5: Extracting data from source org...")
                    
                    source_sf = st.session_state.source_sf_conn
                    object_name = st.session_state.migration_object
                    
                    # Build SOQL query
                    field_list = list(st.session_state.migration_field_mappings.keys())
                    
                    # Add main object match fields
                    if st.session_state.get('migration_main_match_fields'):
                        field_list.extend(st.session_state.migration_main_match_fields)
                    
                    # Add lookup match fields
                    for lookup_config in st.session_state.migration_lookup_configs.values():
                        field_list.extend(lookup_config['match_fields'])
                    
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
                    
                    # Check existing records again (final check)
                    if st.session_state.get('migration_main_match_strategy'):
                        st.info("🔍 Step 3/5: Final check for existing records in TARGET org...")
                        
                        final_validation = validate_existing_records_in_target(
                            target_sf=target_sf,
                            object_name=object_name,
                            match_strategy=st.session_state.migration_main_match_strategy,
                            match_fields=st.session_state.migration_main_match_fields,
                            source_data=mapped_data,
                            concat_separator=st.session_state.get('migration_main_concat_separator', '_')
                        )
                        
                        st.success(f"✅ Validation: {final_validation['new_count']} new, {final_validation['existing_count']} existing")
                        
                        if migration_operation == "INSERT" and final_validation['existing_count'] > 0:
                            st.error(f"❌ Cannot INSERT: {final_validation['existing_count']} records already exist in target org")
                            st.info("💡 Use UPSERT operation instead, or filter out existing records")
                            st.stop()
                    
                    # Resolve lookups
                    st.info("🔗 Step 4/5: Resolving lookup relationships in TARGET org...")
                    
                    target_sf = st.session_state.target_sf_conn
                    
                    progress_text = st.empty()
                    resolved_data, resolution_stats = resolve_lookup_relationships_for_migration(
                        source_df=mapped_data,
                        target_sf=target_sf,
                        lookup_configs=st.session_state.migration_lookup_configs,
                        progress_callback=lambda msg: progress_text.info(msg)
                    )
                    
                    st.success(f"✅ Resolved lookups:")
                    for lookup_field, count in resolution_stats['resolved'].items():
                        st.write(f"   • {lookup_field}: {count} resolved, {resolution_stats['unresolved'][lookup_field]} unresolved")
                    
                    # Load to target
                    st.info("📥 Step 5/5: Loading data to target org...")
                    
                    # Remove null lookup fields
                    for lookup_field in st.session_state.migration_lookup_configs.keys():
                        if lookup_field in resolved_data.columns:
                            resolved_data[lookup_field] = resolved_data[lookup_field].where(pd.notna(resolved_data[lookup_field]), None)
                    
                    # Final filter: Keep ONLY target field names (mapped fields + resolved lookups)
                    # This ensures no unmapped/auto-generated fields (like Id) are sent to target
                    target_field_names = list(st.session_state.migration_field_mappings.values())
                    target_field_names = [f for f in target_field_names if f != "-- Skip --"]
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
                            
                            for r in result:
                                if r['success']:
                                    success_count += 1
                                else:
                                    error_count += 1
                        
                        except Exception as e:
                            st.error(f"Batch {i+1} failed: {str(e)}")
                            error_count += len(batch)
                        
                        progress_bar.progress((i + 1) / len(batches))
                    
                    st.markdown("---")
                    st.markdown("### 📊 Migration Results")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("✅ Success", success_count)
                    with col2:
                        st.metric("❌ Failed", error_count)
                    with col3:
                        st.metric("📊 Total", len(records))
                    
                    if success_count > 0:
                        st.success(f"🎉 Migration completed! {success_count}/{len(records)} records migrated successfully")
                    
                except Exception as e:
                    st.error(f"❌ Migration failed: {str(e)}")
                    st.exception(e)
        else:
            st.error("❌ Please complete all configurations before executing migration")


if __name__ == "__main__":
    st.set_page_config(page_title="Org Migration", page_icon="🔄", layout="wide")
    
    # Load credentials for testing
    try:
        with open('../Services/linkedservices.json', 'r') as f:
            credentials = json.load(f)
        show_org_migration(credentials)
    except Exception as e:
        st.error(f"Error: {str(e)}")
