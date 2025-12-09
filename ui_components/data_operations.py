import streamlit as st
import pandas as pd
import os
import sys
import time
from typing import Dict, Optional
import json
from datetime import datetime

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.append(project_root)

try:
    from .utils import (
        establish_sf_connection, 
        get_salesforce_objects,
        get_object_description,
        display_dataframe_with_download,
        show_processing_status,
        validate_file_upload,
        save_uploaded_file,
        create_progress_tracker,
        load_data_file
    )
    from .etl_engine import ETLEngine
    from .business_rules import BusinessRulesManager
    from .etl_ui_enhancements import ETLUIEnhancements
except ImportError:
    from utils import (
        establish_sf_connection, 
        get_salesforce_objects,
        get_object_description,
        display_dataframe_with_download,
        show_processing_status,
        validate_file_upload,
        save_uploaded_file,
        create_progress_tracker,
        load_data_file
    )
    from etl_engine import ETLEngine
    from business_rules import BusinessRulesManager
    from etl_ui_enhancements import ETLUIEnhancements

def get_external_id_fields(sf_conn, object_name: str):
    """
    Get all external ID fields for a Salesforce object
    """
    try:
        obj_desc = getattr(sf_conn, object_name).describe()
        external_id_fields = []
        
        for field in obj_desc.get('fields', []):
            if field.get('externalId', False) and field.get('updateable', False):
                external_id_fields.append({
                    'name': field['name'],
                    'label': field.get('label', field['name']),
                    'type': field.get('type', 'string')
                })
        
        return external_id_fields
    except Exception as e:
        st.error(f"Error retrieving external ID fields: {str(e)}")
        return []

def get_all_updateable_fields(sf_conn, object_name: str):
    """
    Get all updateable fields for a Salesforce object
    """
    try:
        obj_desc = getattr(sf_conn, object_name).describe()
        updateable_fields = []
        
        for field in obj_desc.get('fields', []):
            if field.get('updateable', False):
                updateable_fields.append({
                    'name': field['name'],
                    'label': field.get('label', field['name']),
                    'type': field.get('type', 'string'),
                    'unique': field.get('unique', False),
                    'externalId': field.get('externalId', False)
                })
        
        return updateable_fields
    except Exception as e:
        st.error(f"Error retrieving updateable fields: {str(e)}")
        return []

def check_field_uniqueness_in_salesforce(sf_conn, object_name: str, field_name: str, sample_values: list):
    """
    Check if a field has unique values in Salesforce by sampling some records
    """
    try:
        if not sample_values or len(sample_values) == 0:
            return True, "No sample values provided"
        
        # Take a sample of unique values to check
        unique_sample = list(set([str(val) for val in sample_values if pd.notna(val) and str(val).strip() != '']))[:10]
        
        if len(unique_sample) == 0:
            return True, "No valid values to check"
        
        # Query Salesforce to check for duplicates
        query_values = "', '".join(unique_sample)
        soql_query = f"SELECT {field_name}, COUNT(Id) cnt FROM {object_name} WHERE {field_name} IN ('{query_values}') GROUP BY {field_name} HAVING COUNT(Id) > 1"
        
        result = sf_conn.query(soql_query)
        duplicates = result.get('records', [])
        
        if len(duplicates) > 0:
            duplicate_values = [rec[field_name] for rec in duplicates]
            return False, f"Found duplicate values in Salesforce: {', '.join(map(str, duplicate_values))}"
        
        return True, "Field values appear to be unique in Salesforce"
        
    except Exception as e:
        # If there's an error (like field doesn't exist), assume it's not suitable for matching
        return False, f"Error checking field uniqueness: {str(e)}"

def handle_single_field_external_id(sf_conn, target_object, df_to_load, external_id_fields, all_updateable_fields, available_data_fields):
    """Handle traditional single field external ID selection"""
    
    # All Salesforce fields for dropdown selection
    sf_field_names = [field['name'] for field in all_updateable_fields]
    
    # Analyze fields for matching suitability (only for fields in data)
    field_analysis = {}
    for field in available_data_fields:
        if field in sf_field_names:  # Only analyze if field exists in Salesforce
            non_null_count = df_to_load[field].count()
            total_count = len(df_to_load)
            unique_count = df_to_load[field].nunique()
            
            field_analysis[field] = {
                'completeness': (non_null_count / total_count) * 100,
                'uniqueness': (unique_count / non_null_count) * 100 if non_null_count > 0 else 0,
                'non_null_count': non_null_count,
                'unique_count': unique_count
            }
    
    # Show external ID information with clear notifications
    if external_id_fields:
        ext_field_names = [field['name'] for field in external_id_fields]
        if len(external_id_fields) == 1:
            st.success(f"🔑 **External ID Found**: {target_object} has **{ext_field_names[0]}** as External ID field")
            st.info(f"🎯 **Auto-Selected**: **{ext_field_names[0]}** has been automatically selected for upsert operation")
        else:
            st.success(f"🔑 **Multiple External IDs Found**: {target_object} has {len(external_id_fields)} external ID fields: {', '.join(ext_field_names)}")
            st.info(f"🎯 **Auto-Selected**: **{ext_field_names[0]}** (first external ID) has been automatically selected for upsert operation")
        st.info("💡 External ID fields are perfect for upsert operations and don't require validation")
    else:
        st.warning(f"⚠️ **No External ID Found**: {target_object} does not have any External ID fields")
        st.info("📝 **What this means**: You'll need to select a field that can uniquely identify records")
        st.info("🔍 **We'll help**: Any field you select will be checked for uniqueness in Salesforce")
        st.info("🎯 **Recommendation**: Choose a field with unique values like Name, Email, or custom unique identifier")
    
    # Show field analysis for matching (only for fields in uploaded data)
    if field_analysis:
        with st.expander("📊 Field Analysis for Record Matching (Data Fields)", expanded=False):
            st.markdown("**Analysis for fields present in your uploaded data:**")
            st.markdown("- ✅ High completeness (few null/empty values)")
            st.markdown("- ✅ High uniqueness (minimal duplicates)")
            st.markdown("- ✅ Values that uniquely identify records")
            
            analysis_df = pd.DataFrame(field_analysis).T
            analysis_df.index.name = 'Field'
            analysis_df = analysis_df.round(1)
            st.dataframe(analysis_df, use_container_width=True)
    
    # Prepare field options with clear organization
    field_options = [""]
    default_field = None
    default_index = 0
    
    if external_id_fields:
        # Object HAS external ID fields
        field_options.extend([field['name'] for field in external_id_fields])
        default_field = external_id_fields[0]['name']
        default_index = 1
        field_options.append("--- Other Salesforce Fields ---")
        
        # Add other Salesforce fields
        external_id_names = [field['name'] for field in external_id_fields]
        other_sf_fields = [field for field in sf_field_names if field not in external_id_names]
        field_options.extend(other_sf_fields)
        
        help_text = "External ID field is pre-selected. You can choose other fields, but they'll be validated for uniqueness."
    else:
        # Object has NO external ID fields
        field_options.extend(sf_field_names)
        help_text = "No External ID fields exist for this object. Please select a field that can uniquely identify records. We'll validate its uniqueness in Salesforce."
    
    # Select matching field with context-appropriate help
    match_field = st.selectbox(
        "Field to Match Records",
        options=field_options,
        index=default_index,
        help=help_text
    )
    
    # Skip separator
    if match_field == "--- Other Salesforce Fields ---":
        match_field = ""
    
    if match_field and match_field != "--- Other Salesforce Fields ---":
        # Check if selected field is external ID
        external_id_names = [field['name'] for field in external_id_fields]
        is_external_id = match_field in external_id_names
        
        # Get field info from Salesforce
        field_info = next((f for f in all_updateable_fields if f['name'] == match_field), None)
        
        if is_external_id:
            # External ID selected - no validation needed
            st.success(f"🔑 **Perfect Choice**: **{match_field}** is an External ID field!")
            st.success(f"✅ **Ready for Upsert**: This field is specifically designed for upsert operations")
            st.info(f"💡 **How it works**: Salesforce will use **{match_field}** to automatically match existing records and insert new ones")
            
            # Show field type
            if field_info:
                st.info(f"📋 Field type: {field_info['type']}")
            
            # Store the match field
            st.session_state.upsert_match_field = match_field
        
        else:
            # Non-external ID field selected - validate uniqueness
            if external_id_fields:
                st.warning(f"⚠️ **Alternative Field Selected**: **{match_field}** is not an External ID field")
                st.info(f"🔍 **Validating**: Checking if **{match_field}** has unique values in Salesforce...")
            else:
                st.info(f"🔍 **Validating Field**: **{match_field}** selected for matching (no External ID available for this object)")
                st.info(f"🔍 **Checking**: Verifying if **{match_field}** has unique values in Salesforce...")
            
            # Check if field exists in uploaded data for sampling
            if match_field in df_to_load.columns:
                # Field exists in data - can check uniqueness with sample values
                with st.spinner(f"Checking if {match_field} values are unique in Salesforce..."):
                    sample_values = df_to_load[match_field].dropna().unique()[:20].tolist()
                    sf_unique, sf_uniqueness_message = check_field_uniqueness_in_salesforce(
                        sf_conn, target_object, match_field, sample_values
                    )
                
                if sf_unique:
                    st.success(f"✅ **Validation Passed**: **{match_field}** appears to be unique in Salesforce!")
                    st.success(f"✅ **Result**: {sf_uniqueness_message}")
                    
                    if not external_id_fields:
                        st.success(f"🎉 **Perfect**: Since {target_object} has no External ID, **{match_field}** will work great for upsert!")
                    
                    # Show data analysis for this field
                    field_stats = field_analysis.get(match_field, {})
                    if field_stats:
                        completeness = field_stats.get('completeness', 0)
                        uniqueness = field_stats.get('uniqueness', 0)
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.info(f"📊 Data Completeness: {completeness:.1f}%")
                        with col2:
                            st.info(f"📊 Data Uniqueness: {uniqueness:.1f}%")
                else:
                    st.error(f"❌ **Validation Failed**: **{match_field}** has duplicate values in Salesforce")
                    st.error(f"❌ **Issue**: {sf_uniqueness_message}")
                    st.warning("⚠️ **Recommendation**: Choose a different field or clean up duplicate data in Salesforce first")
                    return None
            else:
                # Field not in data - can't validate but proceed with warning
                st.warning(f"⚠️ **Field Not in Data**: **{match_field}** is not present in your uploaded data")
                st.info("🔍 **Note**: We can't validate uniqueness without sample data, but the field will be used for matching")
    
    return match_field

def handle_composite_external_id(sf_conn, target_object, df_to_load, available_data_fields):
    """Handle composite external ID (combination of fields) configuration"""
    
    # Exclude system fields and very long text fields for composite keys
    suitable_fields = []
    for field in available_data_fields:
        # Basic filtering - exclude obvious non-key fields
        if not any(exclude_term in field.lower() for exclude_term in ['description', 'comment', 'notes', 'body']):
            suitable_fields.append(field)
    
    st.info("💡 **Composite External ID**: Combines multiple fields to create a unique identifier")
    st.markdown("""
    **Examples:**
    - `FirstName + LastName + Email` for Contact records
    - `AccountName + ProductCode + Date` for Opportunity records
    - `EmployeeID + Department + StartDate` for custom objects
    """)
    
    if len(suitable_fields) < 2:
        st.error("❌ **Insufficient Fields**: Need at least 2 fields for composite external ID")
        return None, None
    
    # Multi-select for composite fields
    selected_fields = st.multiselect(
        "🔗 Select Fields for Composite External ID",
        options=suitable_fields,
        help="Choose 2-4 fields that together uniquely identify records"
    )
    
    if not selected_fields:
        st.info("📝 **Select Fields**: Choose fields to create your composite external ID")
        return None, None
    
    if len(selected_fields) < 2:
        st.warning("⚠️ **Minimum Fields**: Please select at least 2 fields for composite key")
        return None, None
    
    if len(selected_fields) > 4:
        st.warning("⚠️ **Maximum Fields**: Recommend using maximum 4 fields for optimal performance")
    
    # Separator configuration
    st.write("#### ⚙️ Composite Key Configuration")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        separator = st.selectbox(
            "🔗 Field Separator",
            options=["|", "-", "_", "#", "~"],
            index=0,
            help="Character to separate field values in the composite key"
        )
    
    with col2:
        handle_nulls = st.selectbox(
            "🔧 Handle Null Values",
            options=["Skip", "Replace with 'NULL'", "Replace with 'EMPTY'"],
            help="How to handle null/empty values in composite key"
        )
    
    # Preview composite key
    st.write("#### 👀 Composite Key Preview")
    
    try:
        # Create sample composite keys
        preview_df = df_to_load[selected_fields].head(5).copy()
        
        # Handle nulls based on selection
        if handle_nulls == "Replace with 'NULL'":
            preview_df = preview_df.fillna('NULL')
        elif handle_nulls == "Replace with 'EMPTY'":
            preview_df = preview_df.fillna('EMPTY')
        
        # Create composite key column
        if handle_nulls == "Skip":
            # Only include non-null values
            preview_df['Composite_External_ID'] = preview_df.apply(
                lambda row: separator.join([str(val) for val in row if pd.notna(val) and str(val).strip()]), 
                axis=1
            )
        else:
            # Include all values (nulls replaced)
            preview_df['Composite_External_ID'] = preview_df.apply(
                lambda row: separator.join([str(val) for val in row]), 
                axis=1
            )
        
        st.dataframe(preview_df, use_container_width=True)
        
        # Analyze composite key quality
        full_composite_keys = create_composite_key_column(df_to_load, selected_fields, separator, handle_nulls)
        
        # Quality metrics
        total_records = len(df_to_load)
        non_empty_keys = (full_composite_keys != '').sum()
        unique_keys = full_composite_keys.nunique()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            completeness = (non_empty_keys / total_records) * 100
            st.metric("🎯 Completeness", f"{completeness:.1f}%", help="Percentage of non-empty composite keys")
        
        with col2:
            uniqueness = (unique_keys / non_empty_keys) * 100 if non_empty_keys > 0 else 0
            st.metric("🔑 Uniqueness", f"{uniqueness:.1f}%", help="Percentage of unique composite keys")
        
        with col3:
            st.metric("📊 Total Unique Keys", unique_keys, help="Total number of unique composite keys")
        
        # Quality assessment
        if completeness >= 95 and uniqueness >= 95:
            st.success("✅ **Excellent Quality**: Composite key has high completeness and uniqueness")
        elif completeness >= 80 and uniqueness >= 80:
            st.warning("⚠️ **Good Quality**: Composite key is suitable but consider improving data quality")
        else:
            st.error("❌ **Poor Quality**: Composite key may not be suitable for reliable matching")
        
        # Generate composite external ID field name
        composite_field_name = f"CompositeExtID_{separator.join(selected_fields)}"
        composite_field_name = composite_field_name.replace(" ", "").replace(separator, "_")[:40]  # Limit length
        
        # Configuration summary
        with st.expander("⚙️ Configuration Summary", expanded=True):
            st.markdown(f"""
            **🔗 Selected Fields**: {', '.join(selected_fields)}  
            **🔧 Separator**: `{separator}`  
            **🛠️ Null Handling**: {handle_nulls}  
            **🎯 Generated Field Name**: `{composite_field_name}`  
            **📊 Expected Unique Records**: {unique_keys} out of {total_records}
            """)
        
        # Store configuration
        composite_config = {
            'fields': selected_fields,
            'separator': separator,
            'null_handling': handle_nulls,
            'field_name': composite_field_name,
            'quality_metrics': {
                'completeness': completeness,
                'uniqueness': uniqueness,
                'total_records': total_records,
                'unique_keys': unique_keys
            }
        }
        
        return composite_field_name, composite_config
        
    except Exception as e:
        st.error(f"❌ Error creating composite key preview: {str(e)}")
        return None, None

def create_composite_key_column(df, selected_fields, separator, handle_nulls):
    """Create composite key column for the dataframe"""
    df_subset = df[selected_fields].copy()
    
    # Handle nulls based on selection
    if handle_nulls == "Replace with 'NULL'":
        df_subset = df_subset.fillna('NULL')
    elif handle_nulls == "Replace with 'EMPTY'":
        df_subset = df_subset.fillna('EMPTY')
    
    # Create composite key column
    if handle_nulls == "Skip":
        # Only include non-null values
        composite_keys = df_subset.apply(
            lambda row: separator.join([str(val) for val in row if pd.notna(val) and str(val).strip()]), 
            axis=1
        )
    else:
        # Include all values (nulls replaced)
        composite_keys = df_subset.apply(
            lambda row: separator.join([str(val) for val in row]), 
            axis=1
        )
    
    return composite_keys

def show_data_operations(credentials: Dict):
    """Display data operations interface"""
    
    st.title("📥 Data Operations")
    st.markdown("Extract, load, and migrate data between Salesforce, SQL Server, and local files")
    
    if not st.session_state.current_org:
        st.warning("⚠️ Please select an organization from the sidebar to continue.")
        return
    
    # Check for validation completion status
    validation_completed = check_validation_status()
    
    if not validation_completed:
        # Show attractive validation recommendation
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 1.5rem;
            border-radius: 15px;
            color: white;
            margin: 1rem 0 2rem 0;
            text-align: center;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        ">
            <h3 style="margin: 0 0 0.5rem 0; color: white;">🎯 Ready to Ensure Data Quality?</h3>
            <p style="margin: 0.5rem 0; font-size: 1.1rem;">
                Before proceeding with data operations, we highly recommend completing <strong>Data Validation</strong> 
                to ensure your data meets all requirements and avoid processing errors.
            </p>
            <div style="margin-top: 1rem;">
                <span style="font-size: 0.9rem; opacity: 0.9;">
                    ✅ Validate schema compliance &nbsp; | &nbsp; 🔍 Check business rules &nbsp; | &nbsp; 🤖 Use AI validation
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Add action buttons
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🚀 Go to Validation First", type="primary", use_container_width=True):
                st.session_state.active_page = "1️⃣ Validation"
                st.rerun()
            
            st.markdown('<p style="text-align: center; margin-top: 0.5rem; font-size: 0.9rem; color: #666;">Or continue with data operations below (not recommended)</p>', unsafe_allow_html=True)
        
        st.divider()
    
    else:
        # Show success message for completed validation
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
            padding: 1rem 1.5rem;
            border-radius: 10px;
            color: white;
            margin: 0 0 1.5rem 0;
            text-align: center;
            box-shadow: 0 2px 10px rgba(17, 153, 142, 0.3);
        ">
            <h4 style="margin: 0; color: white;">🎉 Excellent! Validation Completed Successfully</h4>
            <p style="margin: 0.5rem 0 0 0; font-size: 1rem;">
                Your data has been validated and is ready for processing. You can now proceed with confidence! 🚀
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    # Establish connection
    sf_conn = establish_sf_connection(credentials, st.session_state.current_org)
    if not sf_conn:
        st.error("❌ Failed to establish Salesforce connection. Please check your credentials.")
        return
    
    # Main tabs for different operations
    tab1, tab2, tab3, tab4 = st.tabs([
        "📤 Data Extraction", 
        "📥 Data Loading", 
        "🔄 SQL Migration",
        "📊 Bulk Operations"
    ])
    
    with tab1:
        show_data_extraction(sf_conn, credentials)
    
    with tab2:
        show_data_loading(sf_conn, credentials)
    
    with tab3:
        show_sql_migration(credentials)
    
    with tab4:
        show_bulk_operations(sf_conn, credentials)

def show_data_extraction(sf_conn, credentials: Dict):
    """Data extraction from various sources"""
    st.subheader("📤 Data Extraction")
    st.markdown("Extract data from Salesforce, SQL, or upload local files")
    
    # Initialize session state for extraction if needed
    if 'sf_extraction_object' not in st.session_state:
        st.session_state.sf_extraction_object = "Select an object..."
    
    # Source selection
    col1, col2 = st.columns([2, 1])
    
    with col1:
        data_source = st.selectbox(
            "Select Data Source",
            ["Salesforce", "SQL Server", "Upload File (CSV/Excel)"],
            key="extraction_source"
        )
    
    with col2:
        st.write("**Current Organization:**")
        st.info(st.session_state.current_org)
    
    st.divider()
    
    if data_source == "Salesforce":
        extract_from_salesforce(sf_conn)
    elif data_source == "SQL Server":
        extract_from_sql(credentials)
    else:
        extract_from_file()

def extract_from_salesforce(sf_conn):
    """Extract data from Salesforce"""
    st.markdown("### 🌩️ Salesforce Data Extraction")
    
    # Connection status
    if not sf_conn:
        st.error("❌ No Salesforce connection available")
        return
    
    with st.container():
        # Object selection section
        st.markdown("#### 📋 Select Object")
        
        with st.spinner("Loading Salesforce objects..."):
            objects = get_salesforce_objects(sf_conn, filter_custom=True)
        
        if not objects:
            st.error("❌ No Salesforce objects found")
            st.markdown("""
            **Possible reasons:**
            - Connection issues with the selected organization
            - Insufficient permissions to view objects
            - Network connectivity problems
            """)
            
            if st.button("🔄 Retry", key="retry_objects"):
                st.rerun()
            return
        
        # Object selection with search
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Define callback function for extraction object selection
            def on_extraction_object_change():
                selected = st.session_state.sf_extraction_object
                if selected and selected != "Select an object...":
                    st.session_state.current_object = selected
                    st.session_state.current_object_source = 'data_extraction'
                else:
                    if hasattr(st.session_state, 'current_object_source') and st.session_state.current_object_source == 'data_extraction':
                        st.session_state.current_object = None
                        st.session_state.current_object_source = None
            
            selected_object = st.selectbox(
                "Choose an object:",
                options=["Select an object..."] + sorted(objects),
                key="sf_extraction_object",
                help="Choose the Salesforce object to extract data from",
                on_change=on_extraction_object_change
            )
        
        with col2:
            if selected_object != "Select an object...":
                if st.button("🔍 Object Info", use_container_width=True):
                    show_object_info(sf_conn, selected_object)
        
        if selected_object == "Select an object...":
            st.info("👆 Please select an object to continue")
            return
        
        # Show success message for valid selection  
        st.success(f"✅ Selected: **{selected_object}**")
        
        # Query options
        st.write("#### Query Configuration")
        
        col_query1, col_query2 = st.columns(2)
        
        with col_query1:
            query_type = st.radio(
                "Query Type",
                ["All Records", "Custom SOQL", "Recent Records"],
                key="sf_query_type"
            )
        
        with col_query2:
            if query_type == "Recent Records":
                days_back = st.number_input(
                    "Days Back",
                    min_value=1,
                    max_value=365,
                    value=30,
                    help="Number of days to look back"
                )
        
        # Custom SOQL query
        if query_type == "Custom SOQL":
            custom_query = st.text_area(
                "SOQL Query",
                value=f"SELECT Id, Name FROM {selected_object} LIMIT 100",
                help="Enter your custom SOQL query"
            )
        
        # Extract button
        if st.button("🚀 Extract Data", type="primary", use_container_width=True):
            extract_salesforce_data(sf_conn, selected_object, query_type, 
                                  days_back if query_type == "Recent Records" else None,
                                  custom_query if query_type == "Custom SOQL" else None)

def extract_from_sql(credentials: Dict):
    """Extract data from SQL Server"""
    st.write("### 🗄️ SQL Server Data Extraction")
    
    # Check if SQL connection is selected globally
    if not st.session_state.get('current_sql_connection'):
        st.warning("⚠️ No SQL Server connection selected.")
        st.info("💡 **To use SQL Server:**")
        st.markdown("""
        1. **Select a SQL connection** from the sidebar (🗄️ Select SQL Server Connection)
        2. If no connections are available, go to **Configuration** → **Database Settings**
        3. Add your SQL Server credentials and test the connection
        4. Return here to extract data from your selected database
        """)
        return
    
    # Get the selected SQL connection
    selected_db = st.session_state.current_sql_connection
    sql_connections = {k: v for k, v in credentials.items() if 'sql' in k.lower()}
    
    if selected_db not in sql_connections:
        st.error(f"❌ Selected SQL connection '{selected_db}' not found in credentials")
        return
    
    db_config = sql_connections[selected_db]
    
    # Show current connection info
    st.info(f"🔗 **Connected to:** {selected_db.replace('sql_', '').upper()} ({db_config.get('server', 'Unknown Server')})")
    
    # Connection test section
    col_test1, col_test2 = st.columns([3, 1])
    
    with col_test1:
        st.write("#### Database Connection Status")
    
    with col_test2:
        if st.button("🔍 Test Connection", key="test_current_sql_conn"):
            test_sql_connection(db_config)
    
    # Show connection details
    with st.expander(f"📊 {selected_db.replace('sql_', '').upper()} - Connection Details", expanded=False):
        col_detail1, col_detail2 = st.columns(2)
        
        with col_detail1:
            st.write("**Server:**", db_config.get('server', 'N/A'))
            st.write("**Database:**", db_config.get('database', 'N/A'))
            auth_type = "Windows Authentication" if db_config.get('Trusted_Connection') == 'yes' else "SQL Authentication"
            st.write("**Authentication:**", auth_type)
        
        with col_detail2:
            st.write("**Driver:**", db_config.get('driver', 'N/A'))
            st.write("**Port:**", db_config.get('port', '1433 (default)'))
            st.write("**Encryption:**", db_config.get('encrypt', 'No'))
    
    # Query input section
    st.write("#### SQL Query Builder")
    
    # Quick query templates
    sample_queries = {
        "Show All Tables": "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME",
        "Show Table Columns": "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'your_table_name' ORDER BY ORDINAL_POSITION",
        "Count All Records": "SELECT COUNT(*) as total_records FROM your_table_name",
        "Recent Records": "SELECT TOP 100 * FROM your_table_name ORDER BY created_date DESC",
        "Table Sizes": "SELECT t.TABLE_NAME, SUM(a.total_pages) * 8 AS TotalSpaceKB FROM sys.tables t INNER JOIN sys.indexes i ON t.object_id = i.object_id INNER JOIN sys.partitions p ON i.object_id = p.object_id AND i.index_id = p.index_id INNER JOIN sys.allocation_units a ON p.partition_id = a.container_id WHERE t.is_ms_shipped = 0 GROUP BY t.TABLE_NAME ORDER BY TotalSpaceKB DESC"
    }
    
    col_sql1, col_sql2 = st.columns([2, 1])
    
    with col_sql1:
        sql_query = st.text_area(
            "SQL Query",
            value="SELECT TOP 100 * FROM your_table_name",
            height=200,
            help="Enter your SQL query to extract data"
        )
        
        # Query validation
        if sql_query.strip():
            query_lower = sql_query.lower().strip()
            if query_lower.startswith('select'):
                st.success("✅ Valid SELECT query")
            elif any(word in query_lower for word in ['insert', 'update', 'delete', 'drop', 'create', 'alter']):
                st.error("❌ Only SELECT queries are allowed for data extraction")
            else:
                st.warning("⚠️ Please ensure this is a valid SELECT query")
    
    with col_sql2:
        st.write("**Quick Query Templates:**")
        for name, query in sample_queries.items():
            if st.button(name, key=f"quick_{name}", use_container_width=True):
                st.session_state.sql_query_template = query
                st.rerun()
        
        # Apply template if selected
        if hasattr(st.session_state, 'sql_query_template'):
            sql_query = st.session_state.sql_query_template
            del st.session_state.sql_query_template
    
    # Execute query section
    st.divider()
    
    col_exec1, col_exec2 = st.columns([2, 1])
    
    with col_exec1:
        if st.button("🚀 Execute Query & Extract Data", type="primary", use_container_width=True, disabled=not sql_query.strip()):
            execute_sql_query(db_config, sql_query)
    
    with col_exec2:
        # Quick table browser
        if st.button("📋 Browse Tables", use_container_width=True):
            browse_query = "SELECT TABLE_NAME as 'Available Tables', TABLE_TYPE as 'Type' FROM INFORMATION_SCHEMA.TABLES ORDER BY TABLE_NAME"
            execute_sql_query(db_config, browse_query)

def extract_from_file():
    """Extract data from uploaded file"""
    st.write("### 📁 File Upload")
    
    uploaded_file = st.file_uploader(
        "Choose a file",
        type=['csv', 'xlsx', 'xls', 'psv'],
        help="Upload CSV, Excel, or PSV (Pipe-separated) files"
    )
    
    if uploaded_file:
        if validate_file_upload(uploaded_file):
            # Display file info
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("File Name", uploaded_file.name)
            with col2:
                st.metric("File Size", f"{uploaded_file.size / 1024:.1f} KB")
            with col3:
                file_ext = os.path.splitext(uploaded_file.name)[1]
                st.metric("File Type", file_ext.upper())
            
            # Preview data
            try:
                df = load_data_file(uploaded_file)
                if df is not None:
                    st.write("#### Data Preview")
                    display_dataframe_with_download(df, uploaded_file.name, "File Data Preview")
                    
                    # Save file option
                    if st.button("💾 Save to DataFiles", use_container_width=True):
                        save_path = os.path.join(project_root, 'DataFiles', 
                                               st.session_state.current_org or 'uploads')
                        saved_path = save_uploaded_file(uploaded_file, save_path)
                        if saved_path:
                            st.success(f"✅ File saved to: {saved_path}")
                            show_processing_status("file_upload", f"File {uploaded_file.name} uploaded successfully", "success")
                
            except Exception as e:
                st.error(f"❌ Error reading file: {str(e)}")

def show_data_loading(sf_conn, credentials: Dict):
    """Data loading to various destinations"""
    st.subheader("📥 Data Loading")
    st.markdown("Load data to Salesforce or SQL Server with batch processing")
    
    # Initialize current object state if needed
    if 'current_object' not in st.session_state:
        st.session_state.current_object = None
        st.session_state.current_object_source = None
    
    # Load destination
    col1, col2 = st.columns([2, 1])
    
    with col1:
        load_destination = st.selectbox(
            "Select Destination",
            ["Salesforce", "SQL Server"],
            key="load_destination"
        )
    
    with col2:
        st.write("**Current Object:**")
        # Show object only if it was selected in data loading tab
        if (load_destination == "Salesforce" and 
            st.session_state.get('current_object_source') == 'data_loading' and 
            st.session_state.current_object):
            st.info(f"🎯 {st.session_state.current_object}")
        elif load_destination == "Salesforce":
            # Show the actual selectbox value if it exists
            load_object = st.session_state.get('sf_load_object', 'Select an object...')
            if load_object and load_object != "Select an object...":
                st.info(f"🎯 {load_object}")
            else:
                st.warning("No object selected")
                st.caption("👇 Select target object below")
        else:
            st.info("📋 SQL Server (table will be created)")
    
    st.divider()
    
    if load_destination == "Salesforce":
        load_to_salesforce(sf_conn)
    else:
        load_to_sql(credentials)

def load_to_sql(credentials: Dict):
    """Load data to SQL Server"""
    st.write("### 🗄️ Load to SQL Server")
    
    # Check if SQL connection is selected globally
    if not st.session_state.get('current_sql_connection'):
        st.warning("⚠️ No SQL Server connection selected.")
        st.info("💡 **To use SQL Server:**")
        st.markdown("""
        1. **Select a SQL connection** from the sidebar (🗄️ Select SQL Server Connection)
        2. If no connections are available, go to **Configuration** → **Database Settings**
        3. Add your SQL Server credentials and test the connection
        4. Return here to load data to your selected database
        """)
        return
    
    # Get the selected SQL connection
    selected_db = st.session_state.current_sql_connection
    sql_connections = {k: v for k, v in credentials.items() if 'sql' in k.lower()}
    
    if selected_db not in sql_connections:
        st.error(f"❌ Selected SQL connection '{selected_db}' not found in credentials")
        return
    
    db_config = sql_connections[selected_db]
    
    # Show current connection info
    st.info(f"🔗 **Target Database:** {selected_db.replace('sql_', '').upper()} ({db_config.get('server', 'Unknown Server')})")
    
    # Connection test section
    col_test1, col_test2 = st.columns([3, 1])
    
    with col_test1:
        st.write("#### Database Connection Status")
    
    with col_test2:
        if st.button("🔍 Test Connection", key="test_sql_load_conn"):
            test_sql_connection(db_config)
    
    # Data source selection
    st.write("#### Source Data")
    
    source_option = st.radio(
        "Data Source",
        ["Upload New File", "Select Existing File"],
        key="sql_load_source"
    )
    
    df_to_load = None
    
    if source_option == "Upload New File":
        uploaded_file = st.file_uploader(
            "Choose a file to load",
            type=['csv', 'xlsx', 'xls', 'psv'],
            key="sql_load_upload",
            help="Upload CSV, Excel, or PSV (Pipe-separated) files"
        )
        
        if uploaded_file and validate_file_upload(uploaded_file):
            try:
                df_to_load = load_data_file(uploaded_file)
                if df_to_load is not None:
                    st.success(f"✅ File loaded: {len(df_to_load)} rows, {len(df_to_load.columns)} columns")
                
            except Exception as e:
                st.error(f"❌ Error reading file: {str(e)}")
    
    else:
        # Select existing file
        existing_files = get_existing_files("DataFiles")
        
        if existing_files:
            selected_file = st.selectbox(
                "Select Existing File",
                options=[""] + existing_files,
                key="sql_load_existing"
            )
            
            if selected_file:
                try:
                    file_path = os.path.join(
                        os.path.dirname(os.path.dirname(__file__)),
                        "DataFiles",
                        selected_file
                    )
                    
                    file_ext = os.path.splitext(selected_file)[1].lower()
                    
                    if file_ext == '.csv':
                        df_to_load = pd.read_csv(file_path)
                    elif file_ext == '.psv':
                        df_to_load = pd.read_csv(file_path, sep='|')
                    else:
                        df_to_load = pd.read_excel(file_path)
                    
                    st.success(f"✅ File loaded: {len(df_to_load)} rows, {len(df_to_load.columns)} columns")
                    
                except Exception as e:
                    st.error(f"❌ Error reading file: {str(e)}")
        else:
            st.info("No existing files found in DataFiles directory")
    
    # Show data preview and loading options
    if df_to_load is not None and not df_to_load.empty:
        st.write("#### Data Preview")
        st.dataframe(df_to_load.head(10), use_container_width=True)
        
        # Table configuration
        st.write("#### Table Configuration")
        
        col_table1, col_table2 = st.columns(2)
        
        with col_table1:
            table_name = st.text_input(
                "Table Name",
                value="imported_data",
                help="Name for the SQL Server table"
            )
            
            load_mode = st.selectbox(
                "Load Mode",
                ["Create New Table", "Replace Existing", "Append to Existing"],
                help="How to handle existing tables"
            )
        
        with col_table2:
            schema_name = st.text_input(
                "Schema Name",
                value="dbo",
                help="Database schema (default: dbo)"
            )
            
            batch_size = st.number_input(
                "Batch Size",
                min_value=100,
                max_value=10000,
                value=1000,
                help="Records per batch"
            )
        
        # Advanced options
        with st.expander("⚙️ Advanced Options", expanded=False):
            col_adv1, col_adv2 = st.columns(2)
            
            with col_adv1:
                index_columns = st.multiselect(
                    "Index Columns",
                    options=df_to_load.columns.tolist(),
                    help="Columns to create indexes on"
                )
                
                nullable_columns = st.multiselect(
                    "Nullable Columns",
                    options=df_to_load.columns.tolist(),
                    default=df_to_load.columns.tolist(),
                    help="Columns that can contain NULL values"
                )
            
            with col_adv2:
                include_index = st.checkbox(
                    "Include DataFrame Index",
                    value=False,
                    help="Include pandas DataFrame index as a column"
                )
                
                check_constraints = st.checkbox(
                    "Check Constraints",
                    value=True,
                    help="Enable constraint checking during load"
                )
        
        # Data type mapping preview
        with st.expander("📊 Data Type Mapping", expanded=False):
            type_mapping = []
            for col in df_to_load.columns:
                dtype = str(df_to_load[col].dtype)
                sql_type = map_pandas_to_sql_type(dtype, df_to_load[col])
                
                type_mapping.append({
                    "Column": col,
                    "Pandas Type": dtype,
                    "SQL Server Type": sql_type,
                    "Sample Value": str(df_to_load[col].iloc[0]) if len(df_to_load) > 0 else "N/A"
                })
            
            df_types = pd.DataFrame(type_mapping)
            st.dataframe(df_types, use_container_width=True)
        
        # Load data button
        st.divider()
        
        if st.button("🚀 Load Data to SQL Server", type="primary", use_container_width=True):
            load_data_to_sql_server(
                db_config, 
                df_to_load, 
                table_name, 
                schema_name,
                load_mode, 
                batch_size,
                index_columns,
                nullable_columns,
                include_index,
                check_constraints
            )

def load_to_salesforce(sf_conn):
    """Load data to Salesforce"""
    st.write("### 🌩️ Load to Salesforce")
    
    # Initialize session state for data loading if not exists
    if 'sf_load_object' not in st.session_state:
        st.session_state.sf_load_object = "Select an object..."
    
    # Object selection for loading
    objects = get_salesforce_objects(sf_conn, filter_custom=True)
    
    if objects:
        # Define callback function for object selection
        def on_load_object_change():
            selected = st.session_state.sf_load_object
            if selected and selected != "Select an object...":
                st.session_state.current_object = selected
                st.session_state.current_object_source = 'data_loading'
            else:
                if hasattr(st.session_state, 'current_object_source') and st.session_state.current_object_source == 'data_loading':
                    st.session_state.current_object = None
                    st.session_state.current_object_source = None
        
        target_object = st.selectbox(
            "Select Target Object",
            options=["Select an object..."] + objects,
            key="sf_load_object",
            on_change=on_load_object_change
        )
        
        # Handle initial state - if placeholder is selected and this tab previously had an object
        if target_object == "Select an object..." and st.session_state.get('current_object_source') == 'data_loading':
            st.session_state.current_object = None
            st.session_state.current_object_source = None
        
        # Show success message for valid selection
        if target_object and target_object != "Select an object...":
            st.success(f"✅ Target Object: **{target_object}**")
    else:
        st.error("❌ No Salesforce objects found")
        return
    
    if target_object and target_object != "Select an object...":
        # File selection for loading
        st.write("#### Source Data")
        
        # Option to select from existing files or upload new
        source_option = st.radio(
            "Data Source",
            ["Upload New File", "Select Existing File"],
            key="sf_load_source"
        )
        
        df_to_load = None
        
        if source_option == "Upload New File":
            uploaded_file = st.file_uploader(
                "Choose file to load",
                type=['csv', 'xlsx', 'xls', 'psv'],
                key="sf_load_file",
                help="Upload CSV, Excel, or PSV (Pipe-separated) files"
            )
            
            if uploaded_file and validate_file_upload(uploaded_file):
                try:
                    df_to_load = load_data_file(uploaded_file)
                except Exception as e:
                    st.error(f"❌ Error reading file: {str(e)}")
        
        else:
            # Show existing files
            data_files_path = os.path.join(project_root, 'DataFiles')
            existing_files = get_existing_files(data_files_path)
            
            if existing_files:
                selected_file = st.selectbox(
                    "Select Existing File",
                    options=[""] + existing_files,
                    key="sf_existing_file"
                )
                
                if selected_file:
                    try:
                        file_path = os.path.join(data_files_path, selected_file)
                        if selected_file.endswith('.csv'):
                            df_to_load = pd.read_csv(file_path)
                        elif selected_file.endswith('.psv'):
                            df_to_load = pd.read_csv(file_path, sep='|')
                        else:
                            df_to_load = pd.read_excel(file_path)
                    except Exception as e:
                        st.error(f"❌ Error reading file: {str(e)}")
            else:
                st.info("No existing files found in DataFiles folder")
        
        # Show data preview and loading options
        if df_to_load is not None:
            st.write("#### Data Analysis & Mapping")
            
            # Analyze uploaded data
            st.info("🔍 **Analyzing uploaded data...**")
            
            # Data analysis summary
            col_analysis1, col_analysis2, col_analysis3 = st.columns(3)
            
            with col_analysis1:
                st.metric("Total Records", len(df_to_load))
            with col_analysis2:
                st.metric("Total Columns", len(df_to_load.columns))
            with col_analysis3:
                null_percentage = (df_to_load.isnull().sum().sum() / (len(df_to_load) * len(df_to_load.columns)) * 100)
                st.metric("Null Values", f"{null_percentage:.1f}%")
            
            # Data quality issues
            data_issues = analyze_data_quality(df_to_load)
            if data_issues:
                st.warning("⚠️ **Data Quality Issues Found:**")
                for issue in data_issues:
                    st.write(f"• {issue}")
            
            # Show preview
            with st.expander("📊 Data Preview", expanded=False):
                st.dataframe(df_to_load.head(10), use_container_width=True)
            
            # Column Analysis with enhanced data type detection
            with st.expander("📋 Column Analysis", expanded=True):
                col_details = []
                for col in df_to_load.columns:
                    # Enhanced data type detection
                    detected_type = detect_salesforce_data_type(df_to_load[col])
                    sample_values = df_to_load[col].dropna().head(3).tolist()
                    
                    col_info = {
                        'Column': col,
                        'Pandas Type': str(df_to_load[col].dtype),
                        'Detected SF Type': detected_type,
                        'Non-Null Count': df_to_load[col].count(),
                        'Null Count': df_to_load[col].isnull().sum(),
                        'Unique Values': df_to_load[col].nunique(),
                        'Sample Values': ', '.join([str(v) for v in sample_values[:2]]) if sample_values else 'N/A',
                        'Min Length': df_to_load[col].astype(str).str.len().min() if not df_to_load[col].empty else 0,
                        'Max Length': df_to_load[col].astype(str).str.len().max() if not df_to_load[col].empty else 0
                    }
                    col_details.append(col_info)
                
                st.dataframe(pd.DataFrame(col_details), use_container_width=True)
            
            # Enhanced Field Mapping Section with mapping options
            st.write("#### 🗺️ Field Mapping Configuration")
            
            # Get Salesforce object fields
            try:
                sf_object_desc = getattr(sf_conn, target_object).describe()
                sf_fields = [field['name'] for field in sf_object_desc['fields'] if field['createable']]
                
                # Get field types for better mapping
                sf_field_info = {}
                for field in sf_object_desc['fields']:
                    if field['createable']:
                        sf_field_info[field['name']] = {
                            'type': field.get('type', 'string'),
                            'label': field.get('label', field['name']),
                            'length': field.get('length', 0)
                        }
                        
            except Exception as e:
                st.warning(f"Could not retrieve field information: {str(e)}")
                sf_fields = []
                sf_field_info = {}
            
            if sf_fields:
                st.success(f"✅ Found {len(sf_fields)} creatable fields in {target_object}")
                
                # Mapping strategy selection
                st.write("**Choose Mapping Strategy:**")
                mapping_strategy = st.radio(
                    "Mapping Strategy",
                    ["🤖 Auto Detect", "📋 Standard Mapping", "✏️ Custom Mapping"],
                    key="mapping_strategy",
                    help="Choose how to map CSV columns to Salesforce fields"
                )
                
                field_mappings = {}
                
                if mapping_strategy == "🤖 Auto Detect":
                    # Auto detect mappings
                    field_mappings = auto_detect_field_mappings(df_to_load.columns.tolist(), sf_fields, sf_field_info, df_to_load)
                    
                    st.info("🤖 **Auto-detected mappings:**")
                    display_mapping_results(field_mappings, df_to_load, sf_field_info)
                    
                    # Allow user to review and modify
                    if st.checkbox("📝 Review and modify auto-detected mappings"):
                        field_mappings = create_custom_mapping_interface(df_to_load.columns.tolist(), sf_fields, sf_field_info, field_mappings, df_to_load)
                
                elif mapping_strategy == "📋 Standard Mapping":
                    # Standard mapping with common field recognition
                    field_mappings = create_standard_mapping_interface(df_to_load.columns.tolist(), sf_fields, sf_field_info)
                
                else:  # Custom Mapping
                    # Full custom mapping interface
                    field_mappings = create_custom_mapping_interface(df_to_load.columns.tolist(), sf_fields, sf_field_info, None, df_to_load)
                
                # Show mapping summary
                if field_mappings:
                    with st.expander("📋 Mapping Summary", expanded=False):
                        for csv_field, sf_field in field_mappings.items():
                            if sf_field and sf_field != "-- Skip Field --":
                                st.write(f"**{csv_field}** → **{sf_field}**")
                
                # Data transformation preview
                if field_mappings:
                    transformed_df = apply_field_mappings(df_to_load, field_mappings)
                    
                    with st.expander("🔄 Transformed Data Preview", expanded=False):
                        st.dataframe(transformed_df.head(5), use_container_width=True)
                    
                    # Update the dataframe for loading
                    df_to_load = transformed_df
            else:
                st.warning(f"⚠️ Could not retrieve field information for {target_object}")
            
            # Batch configuration
            st.write("#### ⚙️ Loading Configuration")
            
            # Operation explanation
            with st.expander("📖 Operation Types Explained", expanded=False):
                st.markdown("""
                **🆕 Insert**: Creates new records in Salesforce
                - Use when all records are new
                - Do NOT include 'Id' field in your data
                - All records must pass validation rules
                
                **✏️ Update**: Modifies existing records in Salesforce  
                - Use when you want to modify existing records
                - REQUIRES 'Id' field to identify records to update
                - Only updates the fields you provide (partial update)
                
                **🔄 Upsert**: Insert new records OR update existing ones
                - Use when your data contains both new and existing records
                - Requires an External ID field to match records
                - If External ID exists: updates the record
                - If External ID is new: creates a new record
                """)
            
            # Data Status Information
            if df_to_load is not None and not df_to_load.empty:
                with st.expander("📊 Current Data Status", expanded=False):
                    st.write(f"**Records:** {len(df_to_load)}")
                    st.write(f"**Columns:** {', '.join(df_to_load.columns.tolist())}")
                    st.write(f"**Has 'Id' field:** {'✅ Yes' if 'Id' in df_to_load.columns else '❌ No'}")
                    
            col_batch1, col_batch2, col_batch3, col_batch4 = st.columns(4)
            
            with col_batch1:
                batch_size = st.number_input(
                    "Batch Size",
                    min_value=1,
                    max_value=10000,
                    value=2000,
                    help="Number of records per batch"
                )
            
            with col_batch2:
                operation_type = st.selectbox(
                    "Operation",
                    ["Insert", "Update", "Upsert"],
                    help="Type of Salesforce operation"
                )
            
            with col_batch3:
                parallel_batches = st.number_input(
                    "Parallel Batches",
                    min_value=1,
                    max_value=5,
                    value=3,
                    help="Number of parallel batches"
                )
            
            # Additional configuration based on operation type
            match_field = None
            if operation_type == "Upsert":
                st.write("**🔄 Upsert Configuration:**")
                
                if df_to_load is not None and not df_to_load.empty:
                    st.info("📝 **How Upsert Works:** Matches records using your selected strategy. Updates existing records, inserts new records that don't match.")
                    
                    # Step 1: Select matching strategy
                    st.write("#### 🔑 Step 1: Select Matching Strategy")
                    
                    upsert_matching_strategy_display = st.radio(
                        "How do you want to match records for upsert?",
                        options=[
                            "🔑 Single Field Matching",
                            "🔗 Field Combination (Multiple fields together)",
                            "➕ Field Concatenation (Join fields with separator)"
                        ],
                        help="Choose how to uniquely identify existing records in Salesforce",
                        key="upsert_matching_strategy_radio"
                    )
                    
                    st.markdown("---")
                    
                    if upsert_matching_strategy_display == "🔑 Single Field Matching":
                        # Single field matching - can be ANY field
                        st.write("#### 🔑 Select Field for Matching")
                        st.info("💡 Select any unique field to match records. Records with matching values will be updated, others will be inserted.")
                        
                        # Get ALL fields from Salesforce object
                        obj_desc = get_object_description(sf_conn, target_object)
                        
                        if obj_desc:
                            all_sf_fields = [f['name'] for f in obj_desc.get('fields', [])]
                            
                            # Also get external ID fields to highlight them
                            external_id_fields = get_external_id_fields(sf_conn, target_object)
                            
                            # Show info about external ID fields if they exist
                            if external_id_fields:
                                with st.expander("📋 External ID Fields (Recommended for matching)"):
                                    st.write("These fields are marked as External IDs in Salesforce:")
                                    for field in external_id_fields:
                                        st.write(f"• **{field}** ⭐")
                            
                            # Select ANY field for matching
                            match_field = st.selectbox(
                                "Select Field for Matching Records",
                                options=[""] + all_sf_fields,
                                help="Select any field with unique values. Records with matching values will be updated, others inserted.",
                                key="upsert_match_field_select"
                            )
                            
                            if match_field:
                                # Check if this field exists in uploaded data
                                if match_field in df_to_load.columns:
                                    st.success(f"✅ Field '{match_field}' found in your uploaded data")
                                    
                                    # Show data quality for this field
                                    null_count = df_to_load[match_field].isnull().sum()
                                    empty_count = (df_to_load[match_field].astype(str).str.strip() == '').sum()
                                    duplicate_count = df_to_load[match_field].duplicated().sum()
                                    unique_count = df_to_load[match_field].nunique()
                                    records_with_values = len(df_to_load) - null_count - empty_count
                                    
                                    col_up1, col_up2, col_up3, col_up4 = st.columns(4)
                                    with col_up1:
                                        st.metric("Total Records", len(df_to_load))
                                    with col_up2:
                                        st.metric("With Match Value", records_with_values)
                                    with col_up3:
                                        st.metric("Empty (Will Insert)", null_count + empty_count)
                                    with col_up4:
                                        st.metric("Duplicates", duplicate_count)
                                    
                                    st.info(f"ℹ️ Records with empty '{match_field}' will be inserted as new records")
                                    
                                    # Show sample values
                                    with st.expander("👀 Sample Values from Your Data"):
                                        sample_values = df_to_load[match_field].dropna().head(10)
                                        st.write(sample_values.tolist())
                                    
                                    # Store match configuration
                                    st.session_state.upsert_match_field = match_field
                                    st.session_state.upsert_matching_strategy = "external_id"
                                    st.session_state.upsert_match_fields = [match_field]
                                    
                                else:
                                    st.error(f"❌ Field '{match_field}' not found in your uploaded data")
                                    st.info(f"💡 Your data must contain the '{match_field}' column for upsert operation.")
                                    st.warning("⚠️ Add this column to your file or select a different field.")
                        else:
                            st.error("❌ Could not retrieve Salesforce object fields")
                    
                    elif upsert_matching_strategy_display == "🔗 Field Combination (Multiple fields together)":
                        st.write("#### 🔗 Select Fields for Combination Matching")
                        st.info("💡 Select multiple fields that together uniquely identify records. Matching combinations will be updated, others inserted.")
                        st.markdown("**Example:** `First Name` + `Last Name` + `Email` = Unique record")
                        
                        # Get all Salesforce fields for this object
                        obj_desc = get_object_description(sf_conn, target_object)
                        if obj_desc:
                            all_sf_fields = [f['name'] for f in obj_desc.get('fields', [])]
                            
                            # Select multiple fields
                            selected_fields = st.multiselect(
                                "Select Fields for Matching (select 2 or more)",
                                options=all_sf_fields,
                                help="These fields together must uniquely identify records",
                                key="upsert_combination_fields"
                            )
                            
                            if len(selected_fields) >= 2:
                                # Check if all fields exist in uploaded data
                                missing_fields = [f for f in selected_fields if f not in df_to_load.columns]
                                
                                if missing_fields:
                                    st.error(f"❌ Missing fields in uploaded data: {', '.join(missing_fields)}")
                                    st.info("💡 Your uploaded file must contain all selected fields")
                                else:
                                    st.success(f"✅ All {len(selected_fields)} fields found in uploaded data")
                                    
                                    # Show combination preview
                                    st.write("**Preview of Field Combination:**")
                                    preview_df = df_to_load[selected_fields].head(5).copy()
                                    preview_df['Combined Match Key'] = preview_df.apply(
                                        lambda row: ' | '.join([str(row[f]) for f in selected_fields]), axis=1
                                    )
                                    st.dataframe(preview_df, use_container_width=True)
                                    
                                    # Check for duplicates in combination
                                    duplicate_count = df_to_load[selected_fields].duplicated().sum()
                                    unique_count = df_to_load[selected_fields].drop_duplicates().shape[0]
                                    
                                    col_c1, col_c2, col_c3 = st.columns(3)
                                    with col_c1:
                                        st.metric("Total Records", len(df_to_load))
                                    with col_c2:
                                        st.metric("Unique Combinations", unique_count)
                                    with col_c3:
                                        st.metric("Duplicate Combinations", duplicate_count)
                                    
                                    st.info("ℹ️ Matching combinations will be updated, non-matching will be inserted as new records")
                                    
                                    # Store match configuration
                                    st.session_state.upsert_match_field = None
                                    st.session_state.upsert_matching_strategy = "field_combination"
                                    st.session_state.upsert_match_fields = selected_fields
                            
                            elif len(selected_fields) == 1:
                                st.warning("⚠️ Please select at least 2 fields for combination matching")
                        else:
                            st.error("❌ Could not retrieve Salesforce object fields")
                    
                    elif upsert_matching_strategy_display == "➕ Field Concatenation (Join fields with separator)":
                        st.write("#### ➕ Configure Field Concatenation")
                        st.info("💡 Concatenate multiple fields to create a unique match key. Matching values will be updated, others inserted.")
                        st.markdown("**Example:** `FirstName` + `_` + `LastName` = `John_Doe`")
                        
                        # Get all Salesforce fields for this object
                        obj_desc = get_object_description(sf_conn, target_object)
                        if obj_desc:
                            all_sf_fields = [f['name'] for f in obj_desc.get('fields', [])]
                            
                            # Select fields to concatenate
                            concat_fields = st.multiselect(
                                "Select Fields to Concatenate (select 2 or more)",
                                options=all_sf_fields,
                                help="These fields will be joined with a separator",
                                key="upsert_concat_fields"
                            )
                            
                            # Select separator
                            separator_option = st.selectbox(
                                "Select Separator",
                                options=["Underscore (_)", "Hyphen (-)", "Pipe (|)", "Custom"],
                                key="upsert_separator_option"
                            )
                            
                            if separator_option == "Custom":
                                separator = st.text_input(
                                    "Enter Custom Separator",
                                    value="_",
                                    key="upsert_custom_separator"
                                )
                            else:
                                separator_map = {
                                    "Underscore (_)": "_",
                                    "Hyphen (-)": "-",
                                    "Pipe (|)": "|"
                                }
                                separator = separator_map[separator_option]
                            
                            if len(concat_fields) >= 2:
                                # Check if all fields exist in uploaded data
                                missing_fields = [f for f in concat_fields if f not in df_to_load.columns]
                                
                                if missing_fields:
                                    st.error(f"❌ Missing fields in uploaded data: {', '.join(missing_fields)}")
                                    st.info("💡 Your uploaded file must contain all selected fields")
                                else:
                                    st.success(f"✅ All {len(concat_fields)} fields found in uploaded data")
                                    
                                    # Show concatenation preview
                                    st.write(f"**Preview of Concatenation (Separator: '{separator}'):**")
                                    preview_df = df_to_load[concat_fields].head(5).copy()
                                    preview_df['Concatenated Match Key'] = preview_df.apply(
                                        lambda row: separator.join([str(row[f]) for f in concat_fields]), axis=1
                                    )
                                    st.dataframe(preview_df, use_container_width=True)
                                    
                                    # Create temporary concatenated column for analysis
                                    df_concat_check = df_to_load.copy()
                                    df_concat_check['_temp_concat'] = df_concat_check.apply(
                                        lambda row: separator.join([str(row[f]) for f in concat_fields]), axis=1
                                    )
                                    
                                    duplicate_count = df_concat_check['_temp_concat'].duplicated().sum()
                                    unique_count = df_concat_check['_temp_concat'].nunique()
                                    
                                    col_ct1, col_ct2, col_ct3 = st.columns(3)
                                    with col_ct1:
                                        st.metric("Total Records", len(df_to_load))
                                    with col_ct2:
                                        st.metric("Unique Concatenations", unique_count)
                                    with col_ct3:
                                        st.metric("Duplicate Concatenations", duplicate_count)
                                    
                                    st.info("ℹ️ Matching concatenations will be updated, non-matching will be inserted as new records")
                                    
                                    # Store match configuration
                                    st.session_state.upsert_match_field = None
                                    st.session_state.upsert_matching_strategy = "field_concatenation"
                                    st.session_state.upsert_match_fields = concat_fields
                                    st.session_state.upsert_concat_separator = separator
                            
                            elif len(concat_fields) == 1:
                                st.warning("⚠️ Please select at least 2 fields for concatenation")
                        else:
                            st.error("❌ Could not retrieve Salesforce object fields")
                else:
                    st.warning("⚠️ No data available for configuration. Please load data first.")
            
            elif operation_type == "Update":
                st.write("**✏️ Update Operation Configuration:**")
                
                if df_to_load is not None and not df_to_load.empty:
                    st.info("📝 **How Update Works:** Updates existing Salesforce records by matching them using External ID, field combination, or field concatenation.")
                    
                    # Step 1: Select matching strategy
                    st.write("#### 🔑 Step 1: Select Matching Strategy")
                    
                    matching_strategy_display = st.radio(
                        "How do you want to match records for update?",
                        options=[
                            "🔑 Single External ID Field",
                            "🔗 Field Combination (Multiple fields together)",
                            "➕ Field Concatenation (Join fields with separator)"
                        ],
                        help="Choose how to uniquely identify records in Salesforce",
                        key="update_matching_strategy_radio"
                    )
                    
                    st.markdown("---")
                    
                    if matching_strategy_display == "🔑 Single External ID Field":
                        # Single field matching - can be ANY field, not just External IDs
                        st.write("#### 🔑 Select Field for Matching")
                        st.info("💡 Select any unique field to match records. This can be an External ID field or any other unique identifier.")
                        
                        # Get ALL fields from Salesforce object
                        obj_desc = get_object_description(sf_conn, target_object)
                        
                        if obj_desc:
                            all_sf_fields = [f['name'] for f in obj_desc.get('fields', [])]
                            
                            # Also get external ID fields to highlight them
                            external_id_fields = get_external_id_fields(sf_conn, target_object)
                            
                            # Show info about external ID fields if they exist
                            if external_id_fields:
                                with st.expander("📋 External ID Fields (Recommended for matching)"):
                                    st.write("These fields are marked as External IDs in Salesforce:")
                                    for field in external_id_fields:
                                        st.write(f"• **{field}** ⭐")
                            
                            # Select ANY field for matching
                            match_field = st.selectbox(
                                "Select Field for Matching Records",
                                options=[""] + all_sf_fields,
                                help="Select any field with unique values to match records. External ID fields are recommended but any unique field works.",
                                key="update_match_field_select"
                            )
                            
                            if match_field:
                                # Check if this field exists in uploaded data
                                if match_field in df_to_load.columns:
                                    st.success(f"✅ Field '{match_field}' found in your uploaded data")
                                    
                                    # Show data quality for this field
                                    null_count = df_to_load[match_field].isnull().sum()
                                    empty_count = (df_to_load[match_field].astype(str).str.strip() == '').sum()
                                    duplicate_count = df_to_load[match_field].duplicated().sum()
                                    unique_count = df_to_load[match_field].nunique()
                                    
                                    col_u1, col_u2, col_u3, col_u4 = st.columns(4)
                                    with col_u1:
                                        st.metric("Total Records", len(df_to_load))
                                    with col_u2:
                                        st.metric("Unique Values", unique_count)
                                    with col_u3:
                                        st.metric("Empty Values", null_count + empty_count)
                                    with col_u4:
                                        st.metric("Duplicates", duplicate_count)
                                    
                                    # Show sample values
                                    with st.expander("👀 Sample External ID Values from Your Data"):
                                        sample_values = df_to_load[match_field].dropna().head(10)
                                        st.write(sample_values.tolist())
                                    
                                    # Store match configuration
                                    st.session_state.match_field = match_field
                                    st.session_state.update_matching_strategy = "external_id"
                                    st.session_state.update_match_fields = [match_field]
                                    
                                else:
                                    st.error(f"❌ Field '{match_field}' not found in your uploaded data")
                                    st.info(f"💡 Your data must contain the '{match_field}' column with values matching Salesforce records.")
                                    st.warning("⚠️ Add this column to your file or select a different external ID field.")
                    
                    elif matching_strategy_display == "🔗 Field Combination (Multiple fields together)":
                        st.write("#### 🔗 Select Fields for Combination Matching")
                        st.info("💡 Select multiple fields that together uniquely identify records in Salesforce")
                        st.markdown("**Example:** `First Name` + `Last Name` + `Email` = Unique record")
                        
                        # Get all Salesforce fields for this object
                        obj_desc = get_object_description(sf_conn, target_object)
                        if obj_desc:
                            all_sf_fields = [f['name'] for f in obj_desc.get('fields', [])]
                            
                            # Select multiple fields
                            selected_fields = st.multiselect(
                                "Select Fields for Matching (select 2 or more)",
                                options=all_sf_fields,
                                help="These fields together must uniquely identify records",
                                key="update_combination_fields"
                            )
                            
                            if len(selected_fields) >= 2:
                                # Check if all fields exist in uploaded data
                                missing_fields = [f for f in selected_fields if f not in df_to_load.columns]
                                
                                if missing_fields:
                                    st.error(f"❌ Missing fields in uploaded data: {', '.join(missing_fields)}")
                                    st.info("💡 Your uploaded file must contain all selected fields")
                                else:
                                    st.success(f"✅ All {len(selected_fields)} fields found in uploaded data")
                                    
                                    # Show combination preview
                                    st.write("**Preview of Field Combination:**")
                                    preview_df = df_to_load[selected_fields].head(5).copy()
                                    preview_df['Combined Match Key'] = preview_df.apply(
                                        lambda row: ' | '.join([str(row[f]) for f in selected_fields]), axis=1
                                    )
                                    st.dataframe(preview_df, use_container_width=True)
                                    
                                    # Check for duplicates in combination
                                    duplicate_count = df_to_load[selected_fields].duplicated().sum()
                                    unique_count = df_to_load[selected_fields].drop_duplicates().shape[0]
                                    
                                    col_c1, col_c2, col_c3 = st.columns(3)
                                    with col_c1:
                                        st.metric("Total Records", len(df_to_load))
                                    with col_c2:
                                        st.metric("Unique Combinations", unique_count)
                                    with col_c3:
                                        st.metric("Duplicate Combinations", duplicate_count)
                                    
                                    # Store match configuration
                                    st.session_state.match_field = None  # Not using single field
                                    st.session_state.update_matching_strategy = "field_combination"
                                    st.session_state.update_match_fields = selected_fields
                            
                            elif len(selected_fields) == 1:
                                st.warning("⚠️ Please select at least 2 fields for combination matching")
                        else:
                            st.error("❌ Could not retrieve Salesforce object fields")
                    
                    elif matching_strategy_display == "➕ Field Concatenation (Join fields with separator)":
                        st.write("#### ➕ Configure Field Concatenation")
                        st.info("💡 Concatenate multiple fields with a separator to create a unique match key")
                        st.markdown("**Example:** `FirstName` + `_` + `LastName` = `John_Doe`")
                        
                        # Get all Salesforce fields for this object
                        obj_desc = get_object_description(sf_conn, target_object)
                        if obj_desc:
                            all_sf_fields = [f['name'] for f in obj_desc.get('fields', [])]
                            
                            # Select fields to concatenate
                            concat_fields = st.multiselect(
                                "Select Fields to Concatenate (select 2 or more)",
                                options=all_sf_fields,
                                help="These fields will be joined with a separator",
                                key="update_concat_fields"
                            )
                            
                            # Select separator
                            separator_option = st.selectbox(
                                "Select Separator",
                                options=["Underscore (_)", "Hyphen (-)", "Pipe (|)", "Custom"],
                                key="update_separator_option"
                            )
                            
                            if separator_option == "Custom":
                                separator = st.text_input(
                                    "Enter Custom Separator",
                                    value="_",
                                    key="update_custom_separator"
                                )
                            else:
                                separator_map = {
                                    "Underscore (_)": "_",
                                    "Hyphen (-)": "-",
                                    "Pipe (|)": "|"
                                }
                                separator = separator_map[separator_option]
                            
                            if len(concat_fields) >= 2:
                                # Check if all fields exist in uploaded data
                                missing_fields = [f for f in concat_fields if f not in df_to_load.columns]
                                
                                if missing_fields:
                                    st.error(f"❌ Missing fields in uploaded data: {', '.join(missing_fields)}")
                                    st.info("💡 Your uploaded file must contain all selected fields")
                                else:
                                    st.success(f"✅ All {len(concat_fields)} fields found in uploaded data")
                                    
                                    # Show concatenation preview
                                    st.write(f"**Preview of Concatenation (Separator: '{separator}'):**")
                                    preview_df = df_to_load[concat_fields].head(5).copy()
                                    preview_df['Concatenated Match Key'] = preview_df.apply(
                                        lambda row: separator.join([str(row[f]) for f in concat_fields]), axis=1
                                    )
                                    st.dataframe(preview_df, use_container_width=True)
                                    
                                    # Create temporary concatenated column for analysis
                                    df_concat_check = df_to_load.copy()
                                    df_concat_check['_temp_concat'] = df_concat_check.apply(
                                        lambda row: separator.join([str(row[f]) for f in concat_fields]), axis=1
                                    )
                                    
                                    duplicate_count = df_concat_check['_temp_concat'].duplicated().sum()
                                    unique_count = df_concat_check['_temp_concat'].nunique()
                                    
                                    col_ct1, col_ct2, col_ct3 = st.columns(3)
                                    with col_ct1:
                                        st.metric("Total Records", len(df_to_load))
                                    with col_ct2:
                                        st.metric("Unique Concatenations", unique_count)
                                    with col_ct3:
                                        st.metric("Duplicate Concatenations", duplicate_count)
                                    
                                    # Store match configuration
                                    st.session_state.match_field = None  # Not using single field
                                    st.session_state.update_matching_strategy = "field_concatenation"
                                    st.session_state.update_match_fields = concat_fields
                                    st.session_state.update_concat_separator = separator
                            
                            elif len(concat_fields) == 1:
                                st.warning("⚠️ Please select at least 2 fields for concatenation")
                        else:
                            st.error("❌ Could not retrieve Salesforce object fields")
                else:
                    st.warning("⚠️ No data available for validation. Please load data first.")
            
            elif operation_type == "Insert":
                st.write("**🆕 Insert Operation Configuration:**")
                
                if df_to_load is not None and not df_to_load.empty:
                    st.info("📝 **How Insert Works:** Creates new records in Salesforce. Validates uniqueness based on your selected strategy to prevent duplicates.")
                    
                    # Step 1: Select uniqueness validation strategy
                    st.write("#### 🎯 Step 1: Select Uniqueness Validation Strategy")
                    
                    insert_matching_strategy_display = st.radio(
                        "How do you want to ensure uniqueness for insert?",
                        options=[
                            "🔑 Single Field as External ID",
                            "🔗 Field Combination (Multiple fields together)",
                            "➕ Field Concatenation (Join fields with separator)"
                        ],
                        help="Choose how to validate uniqueness and prevent duplicate records in Salesforce",
                        key="insert_matching_strategy_radio"
                    )
                    
                    st.markdown("---")
                    
                    # Get Salesforce metadata for insert
                    obj_desc = get_object_description(sf_conn, target_object)
                    external_id_fields = get_external_id_fields(sf_conn, target_object)
                    
                    if insert_matching_strategy_display == "🔑 Single Field as External ID":
                        st.write("#### 🔑 Single Field Configuration")
                        st.info("💡 Select a field to use as unique identifier. System will check this field doesn't already exist in Salesforce before insert.")
                        
                        if obj_desc:
                            all_sf_fields = [f['name'] for f in obj_desc.get('fields', [])]
                            available_data_fields = list(df_to_load.columns)
                            
                            # Select source and target fields
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.write("**Source Field (from your data):**")
                                source_field = st.selectbox(
                                    "Select field from uploaded data",
                                    options=[""] + available_data_fields,
                                    help="This field contains the unique identifier values",
                                    key="insert_source_field_single"
                                )
                            
                            with col2:
                                st.write("**Target External ID Field (in Salesforce):**")
                                if external_id_fields:
                                    st.info(f"✅ Found {len(external_id_fields)} External ID fields")
                                    target_field = st.selectbox(
                                        "Select Salesforce External ID field",
                                        options=[""] + external_id_fields,
                                        help="This Salesforce field will store the external ID",
                                        key="insert_target_field_single"
                                    )
                                else:
                                    st.warning("⚠️ No External ID fields found. Showing all fields.")
                                    target_field = st.selectbox(
                                        "Select Salesforce field to store external ID",
                                        options=[""] + all_sf_fields,
                                        help="This Salesforce field will store the external ID",
                                        key="insert_target_field_single"
                                    )
                            
                            if source_field and target_field:
                                # Validate source field quality
                                null_count = df_to_load[source_field].isnull().sum()
                                empty_count = (df_to_load[source_field].astype(str).str.strip() == '').sum()
                                duplicate_count = df_to_load[source_field].duplicated().sum()
                                unique_count = df_to_load[source_field].nunique()
                                
                                col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                                with col_m1:
                                    st.metric("Total Records", len(df_to_load))
                                with col_m2:
                                    st.metric("Unique Values", unique_count)
                                with col_m3:
                                    st.metric("Empty Values", null_count + empty_count)
                                with col_m4:
                                    st.metric("Duplicates", duplicate_count)
                                
                                if duplicate_count == 0 and (null_count + empty_count) == 0:
                                    st.success(f"✅ '{source_field}' → '{target_field}': Perfect external ID field!")
                                elif duplicate_count > 0:
                                    st.error(f"❌ '{source_field}' has {duplicate_count} duplicates - not suitable as external ID")
                                elif null_count + empty_count > 0:
                                    st.warning(f"⚠️ '{source_field}' has {null_count + empty_count} empty values")
                                
                                # Store configuration
                                st.session_state.insert_source_field = source_field
                                st.session_state.insert_target_field = target_field
                                st.session_state.insert_match_field = target_field
                                st.session_state.insert_matching_strategy = "external_id"
                                st.session_state.insert_match_fields = [source_field]
                                st.session_state.insert_is_composite = False
                        else:
                            st.error("❌ Could not retrieve Salesforce object fields")
                    
                    elif insert_matching_strategy_display == "🔗 Field Combination (Multiple fields together)":
                        st.write("#### 🔗 Field Combination Configuration")
                        st.info("💡 Select multiple fields that together uniquely identify records. System will check combinations don't already exist in Salesforce.")
                        st.markdown("**Example:** `FirstName` + `LastName` + `Email` = Unique record")
                        
                        if obj_desc:
                            all_sf_fields = [f['name'] for f in obj_desc.get('fields', [])]
                            available_data_fields = list(df_to_load.columns)
                            
                            # Select multiple fields
                            selected_fields = st.multiselect(
                                "Select Fields for Uniqueness Check (select 2 or more)",
                                options=available_data_fields,
                                help="These fields together must uniquely identify records",
                                key="insert_combination_fields"
                            )
                            
                            if len(selected_fields) >= 2:
                                # Check if all fields exist
                                missing_fields = [f for f in selected_fields if f not in df_to_load.columns]
                                
                                if missing_fields:
                                    st.error(f"❌ Missing fields in uploaded data: {', '.join(missing_fields)}")
                                else:
                                    st.success(f"✅ All {len(selected_fields)} fields found in uploaded data")
                                    
                                    # Show combination preview
                                    st.write("**Preview of Field Combination:**")
                                    preview_df = df_to_load[selected_fields].head(5).copy()
                                    preview_df['Combined Match Key'] = preview_df.apply(
                                        lambda row: ' | '.join([str(row[f]) for f in selected_fields]), axis=1
                                    )
                                    st.dataframe(preview_df, use_container_width=True)
                                    
                                    # Check for duplicates in combination
                                    duplicate_count = df_to_load[selected_fields].duplicated().sum()
                                    unique_count = df_to_load[selected_fields].drop_duplicates().shape[0]
                                    
                                    col_c1, col_c2, col_c3 = st.columns(3)
                                    with col_c1:
                                        st.metric("Total Records", len(df_to_load))
                                    with col_c2:
                                        st.metric("Unique Combinations", unique_count)
                                    with col_c3:
                                        st.metric("Duplicate Combinations", duplicate_count)
                                    
                                    # Store configuration
                                    st.session_state.insert_source_field = None
                                    st.session_state.insert_target_field = None
                                    st.session_state.insert_matching_strategy = "field_combination"
                                    st.session_state.insert_match_fields = selected_fields
                                    st.session_state.insert_is_composite = False
                            
                            elif len(selected_fields) == 1:
                                st.warning("⚠️ Please select at least 2 fields for combination")
                        else:
                            st.error("❌ Could not retrieve Salesforce object fields")
                    
                    elif insert_matching_strategy_display == "➕ Field Concatenation (Join fields with separator)":
                        st.write("#### ➕ Field Concatenation Configuration")
                        st.info("💡 Concatenate multiple fields to create a unique identifier. System will check concatenations don't already exist in Salesforce.")
                        st.markdown("**Example:** `FirstName` + `_` + `LastName` = `John_Doe`")
                        
                        if obj_desc:
                            all_sf_fields = [f['name'] for f in obj_desc.get('fields', [])]
                            available_data_fields = list(df_to_load.columns)
                            
                            # Select fields to concatenate
                            concat_fields = st.multiselect(
                                "Select Fields to Concatenate (select 2 or more)",
                                options=available_data_fields,
                                help="These fields will be joined with a separator",
                                key="insert_concat_fields"
                            )
                            
                            # Select separator
                            separator_option = st.selectbox(
                                "Select Separator",
                                options=["Underscore (_)", "Hyphen (-)", "Pipe (|)", "Custom"],
                                key="insert_separator_option"
                            )
                            
                            if separator_option == "Custom":
                                separator = st.text_input(
                                    "Enter Custom Separator",
                                    value="_",
                                    key="insert_custom_separator"
                                )
                            else:
                                separator_map = {
                                    "Underscore (_)": "_",
                                    "Hyphen (-)": "-",
                                    "Pipe (|)": "|"
                                }
                                separator = separator_map[separator_option]
                            
                            if len(concat_fields) >= 2:
                                # Check if all fields exist
                                missing_fields = [f for f in concat_fields if f not in df_to_load.columns]
                                
                                if missing_fields:
                                    st.error(f"❌ Missing fields in uploaded data: {', '.join(missing_fields)}")
                                else:
                                    st.success(f"✅ All {len(concat_fields)} fields found in uploaded data")
                                    
                                    # Show concatenation preview
                                    st.write(f"**Preview of Concatenation (Separator: '{separator}'):**")
                                    preview_df = df_to_load[concat_fields].head(5).copy()
                                    preview_df['Concatenated Match Key'] = preview_df.apply(
                                        lambda row: separator.join([str(row[f]) for f in concat_fields]), axis=1
                                    )
                                    st.dataframe(preview_df, use_container_width=True)
                                    
                                    # Create temporary concatenated column for analysis
                                    df_concat_check = df_to_load.copy()
                                    df_concat_check['_temp_concat'] = df_concat_check.apply(
                                        lambda row: separator.join([str(row[f]) for f in concat_fields]), axis=1
                                    )
                                    
                                    duplicate_count = df_concat_check['_temp_concat'].duplicated().sum()
                                    unique_count = df_concat_check['_temp_concat'].nunique()
                                    
                                    col_ct1, col_ct2, col_ct3 = st.columns(3)
                                    with col_ct1:
                                        st.metric("Total Records", len(df_to_load))
                                    with col_ct2:
                                        st.metric("Unique Concatenations", unique_count)
                                    with col_ct3:
                                        st.metric("Duplicate Concatenations", duplicate_count)
                                    
                                    # Store configuration
                                    st.session_state.insert_source_field = None
                                    st.session_state.insert_target_field = None
                                    st.session_state.insert_matching_strategy = "field_concatenation"
                                    st.session_state.insert_match_fields = concat_fields
                                    st.session_state.insert_concat_separator = separator
                                    st.session_state.insert_is_composite = False
                            
                            elif len(concat_fields) == 1:
                                st.warning("⚠️ Please select at least 2 fields for concatenation")
                        else:
                            st.error("❌ Could not retrieve Salesforce object fields")
                else:
                    st.warning("⚠️ No data available for configuration. Please load data first.")
            
            # Load button with validation
            if st.button("🚀 Start Loading", type="primary", use_container_width=True):
                # Validate operation requirements
                validation_passed = True
                
                # First check if we have data
                if df_to_load is None or df_to_load.empty:
                    st.error("❌ Cannot proceed: No data available for loading. Please upload or select data first.")
                    validation_passed = False
                else:
                    # Get the match field based on operation type
                    if operation_type == "Insert":
                        # Get matching strategy configuration
                        insert_matching_strategy = st.session_state.get('insert_matching_strategy', None)
                        insert_match_fields = st.session_state.get('insert_match_fields', None)
                        
                        if not insert_matching_strategy or not insert_match_fields:
                            st.error("❌ Cannot proceed: Please configure uniqueness validation strategy in Configuration tab.")
                            validation_passed = False
                        else:
                            validation_issues = []
                            
                            if insert_matching_strategy == "external_id":
                                # Single field validation
                                source_field = insert_match_fields[0]
                                target_field = st.session_state.get('insert_target_field')
                                
                                if not target_field:
                                    st.error("❌ Cannot proceed: Target field not configured.")
                                    validation_passed = False
                                else:
                                    st.info(f"🔍 Validating uniqueness using field: '{source_field}'...")
                                    
                                    duplicate_count = df_to_load[source_field].duplicated().sum()
                                    null_count = df_to_load[source_field].isnull().sum()
                                    empty_count = (df_to_load[source_field].astype(str).str.strip() == '').sum()
                                    
                                    if duplicate_count > 0:
                                        st.error(f"❌ Found {duplicate_count} duplicate values in '{source_field}'")
                                        duplicates = df_to_load[df_to_load[source_field].duplicated(keep=False)][source_field].value_counts()
                                        with st.expander("🔍 View Duplicate Values"):
                                            st.write(duplicates)
                                        validation_issues.append(f"{duplicate_count} duplicates")
                                    
                                    if null_count > 0 or empty_count > 0:
                                        st.error(f"❌ Found {null_count + empty_count} empty values in '{source_field}'")
                                        validation_issues.append(f"{null_count + empty_count} empty values")
                                    
                                    # Check if values already exist in Salesforce
                                    if not validation_issues:
                                        st.info(f"🔍 Checking if values already exist in Salesforce field '{target_field}'...")
                                        try:
                                            unique_vals = df_to_load[source_field].unique().tolist()
                                            existing_records = []
                                            batch_size = 200
                                            
                                            for i in range(0, len(unique_vals), batch_size):
                                                batch_vals = unique_vals[i:i + batch_size]
                                                formatted_vals = [f"'{str(v).replace(chr(39), chr(92)+chr(39))}' " for v in batch_vals]
                                                vals_string = ','.join(formatted_vals)
                                                
                                                soql_query = f"SELECT {target_field} FROM {target_object} WHERE {target_field} IN ({vals_string})"
                                                result = sf_conn.query(soql_query)
                                                
                                                if result['totalSize'] > 0:
                                                    existing_records.extend([rec[target_field] for rec in result['records']])
                                            
                                            if existing_records:
                                                st.error(f"❌ Found {len(existing_records)} records already existing in Salesforce with these external ID values")
                                                with st.expander("🔍 View Existing Values"):
                                                    st.write(pd.DataFrame(existing_records, columns=[target_field]))
                                                st.error(f"❌ Cannot proceed: Use Update or Upsert instead.")
                                                validation_passed = False
                                            else:
                                                st.success(f"✅ All {len(unique_vals)} values are unique and ready for insert")
                                        except Exception as e:
                                            st.warning(f"⚠️ Could not verify: {str(e)}")
                                            st.info("💡 Proceeding with insert")
                                
                                if validation_issues:
                                    validation_passed = False
                            
                            elif insert_matching_strategy == "field_combination":
                                # Field Combination validation
                                st.info(f"🔍 Validating Field Combination: {', '.join(insert_match_fields)}...")
                                
                                validation_issues = []
                                
                                # Check for duplicates in combination
                                duplicate_count = df_to_load[insert_match_fields].duplicated().sum()
                                
                                if duplicate_count > 0:
                                    st.error(f"❌ Found {duplicate_count} duplicate field combinations in uploaded file")
                                    duplicates = df_to_load[df_to_load[insert_match_fields].duplicated(keep=False)][insert_match_fields]
                                    with st.expander("🔍 View Duplicate Combinations"):
                                        st.dataframe(duplicates)
                                    validation_issues.append(f"{duplicate_count} duplicate combinations")
                                else:
                                    st.success(f"✅ All field combinations are unique in uploaded file")
                                
                                # Check if combinations already exist in Salesforce
                                if not validation_issues:
                                    st.info(f"🔍 Checking if field combinations already exist in Salesforce...")
                                    try:
                                        # Get unique combinations from uploaded file
                                        unique_combinations = df_to_load[insert_match_fields].drop_duplicates()
                                        existing_records = []
                                        
                                        # Check each unique combination (limit to first 100 for performance)
                                        check_count = min(len(unique_combinations), 100)
                                        
                                        for idx, row in unique_combinations.head(check_count).iterrows():
                                            # Build WHERE clause for this combination
                                            conditions = []
                                            has_all_fields = True
                                            
                                            for field in insert_match_fields:
                                                value = row[field]
                                                if pd.isna(value) or (isinstance(value, str) and value.strip() == ''):
                                                    has_all_fields = False
                                                    break
                                                escaped_value = str(value).replace("'", "\\'")
                                                conditions.append(f"{field} = '{escaped_value}'")
                                            
                                            if not has_all_fields:
                                                continue
                                            
                                            where_clause = ' AND '.join(conditions)
                                            soql_query = f"SELECT Id, {', '.join(insert_match_fields)} FROM {target_object} WHERE {where_clause} LIMIT 1"
                                            result = sf_conn.query(soql_query)
                                            
                                            if result['totalSize'] > 0:
                                                existing_records.append(row.to_dict())
                                        
                                        if existing_records:
                                            st.error(f"❌ Found {len(existing_records)} combinations already existing in Salesforce")
                                            with st.expander("🔍 View Existing Combinations"):
                                                st.dataframe(pd.DataFrame(existing_records))
                                            st.error(f"❌ Cannot proceed: Use Update or Upsert instead.")
                                            validation_passed = False
                                        else:
                                            st.success(f"✅ All {check_count} field combinations are unique and ready for insert")
                                    except Exception as e:
                                        st.warning(f"⚠️ Could not verify: {str(e)}")
                                        st.info("💡 Proceeding with insert - duplicates will be checked during data loading")
                                
                                if validation_issues:
                                    validation_passed = False
                            
                            elif insert_matching_strategy == "field_concatenation":
                                # Field Concatenation validation
                                separator = st.session_state.get('insert_concat_separator', '_')
                                st.info(f"🔍 Validating Field Concatenation: {' {sep} '.join(insert_match_fields).replace('{sep}', separator)}...")
                                
                                validation_issues = []
                                
                                # Create concatenated column
                                df_to_load['_match_key'] = df_to_load.apply(
                                    lambda row: separator.join([str(row[f]) for f in insert_match_fields]), axis=1
                                )
                                
                                # Check for duplicates
                                duplicate_count = df_to_load['_match_key'].duplicated().sum()
                                
                                if duplicate_count > 0:
                                    st.error(f"❌ Found {duplicate_count} duplicate concatenated values")
                                    duplicates = df_to_load[df_to_load['_match_key'].duplicated(keep=False)][insert_match_fields + ['_match_key']]
                                    with st.expander("🔍 View Duplicates"):
                                        st.dataframe(duplicates)
                                    validation_issues.append(f"{duplicate_count} duplicate concatenations")
                                else:
                                    st.success(f"✅ All concatenated values are unique in uploaded file")
                                
                                # Check if concatenated combinations already exist in Salesforce
                                if not validation_issues:
                                    st.info(f"🔍 Checking if concatenated field combinations already exist in Salesforce...")
                                    try:
                                        # Get unique combinations from uploaded file
                                        unique_combinations = df_to_load[insert_match_fields + ['_match_key']].drop_duplicates(subset=['_match_key'])
                                        existing_records = []
                                        
                                        # Check each unique combination (limit to first 100 for performance)
                                        check_count = min(len(unique_combinations), 100)
                                        
                                        for idx, row in unique_combinations.head(check_count).iterrows():
                                            # Build WHERE clause checking all component fields
                                            conditions = []
                                            has_all_fields = True
                                            
                                            for field in insert_match_fields:
                                                value = row[field]
                                                if pd.isna(value) or (isinstance(value, str) and value.strip() == ''):
                                                    has_all_fields = False
                                                    break
                                                escaped_value = str(value).replace("'", "\\'")
                                                conditions.append(f"{field} = '{escaped_value}'")
                                            
                                            if not has_all_fields:
                                                continue
                                            
                                            where_clause = ' AND '.join(conditions)
                                            soql_query = f"SELECT Id, {', '.join(insert_match_fields)} FROM {target_object} WHERE {where_clause} LIMIT 1"
                                            result = sf_conn.query(soql_query)
                                            
                                            if result['totalSize'] > 0:
                                                record_data = row[insert_match_fields].to_dict()
                                                record_data['_match_key'] = row['_match_key']
                                                existing_records.append(record_data)
                                        
                                        if existing_records:
                                            st.error(f"❌ Found {len(existing_records)} concatenated combinations already existing in Salesforce")
                                            with st.expander("🔍 View Existing Concatenations"):
                                                st.dataframe(pd.DataFrame(existing_records))
                                            st.error(f"❌ Cannot proceed: Use Update or Upsert instead.")
                                            validation_passed = False
                                        else:
                                            st.success(f"✅ All {check_count} concatenated combinations are unique and ready for insert")
                                    except Exception as e:
                                        st.warning(f"⚠️ Could not verify: {str(e)}")
                                        st.info("💡 Proceeding with insert - duplicates will be checked during data loading")
                                
                                if validation_issues:
                                    validation_passed = False
                    
                    elif operation_type == "Update":
                        # Get matching strategy from session state
                        matching_strategy = st.session_state.get('update_matching_strategy', None)
                        match_fields = st.session_state.get('update_match_fields', None)
                        
                        if not matching_strategy or not match_fields:
                            st.error("❌ Cannot proceed: Please configure matching strategy in Configuration tab.")
                            validation_passed = False
                        else:
                            validation_issues = []
                            
                            if matching_strategy == "external_id":
                                # Single External ID validation
                                match_field = match_fields[0]
                                st.info(f"🔍 Validating using External ID field: '{match_field}'...")
                                
                                duplicate_count = df_to_load[match_field].duplicated().sum()
                                null_count = df_to_load[match_field].isnull().sum()
                                empty_count = (df_to_load[match_field].astype(str).str.strip() == '').sum()
                                
                                if duplicate_count > 0:
                                    st.error(f"❌ Found {duplicate_count} duplicate values in '{match_field}'")
                                    duplicates = df_to_load[df_to_load[match_field].duplicated(keep=False)][match_field].value_counts()
                                    with st.expander("🔍 View Duplicates"):
                                        st.write(duplicates)
                                    validation_issues.append(f"{duplicate_count} duplicates")
                                
                                if null_count > 0 or empty_count > 0:
                                    total_invalid = null_count + empty_count
                                    st.error(f"❌ Found {total_invalid} records with empty '{match_field}' values")
                                    validation_issues.append(f"{total_invalid} empty values")
                                
                                # Check existence in Salesforce
                                if not validation_issues:
                                    st.info("🔍 Verifying records exist in Salesforce...")
                                    try:
                                        unique_ids = df_to_load[match_field].dropna().unique().tolist()
                                        existing_records = []
                                        batch_size = 200
                                        
                                        for i in range(0, len(unique_ids), batch_size):
                                            batch_ids = unique_ids[i:i + batch_size]
                                            formatted_ids = [f"'{str(id).replace(chr(39), chr(92)+chr(39))}'" for id in batch_ids]
                                            ids_string = ','.join(formatted_ids)
                                            
                                            soql_query = f"SELECT {match_field} FROM {target_object} WHERE {match_field} IN ({ids_string})"
                                            result = sf_conn.query(soql_query)
                                            
                                            if result['totalSize'] > 0:
                                                existing_records.extend([rec[match_field] for rec in result['records']])
                                        
                                        non_existing = set(unique_ids) - set(existing_records)
                                        
                                        if non_existing:
                                            st.error(f"❌ {len(non_existing)} records DO NOT exist in Salesforce")
                                            with st.expander("🔍 View Non-Existing Records"):
                                                st.write(pd.DataFrame(list(non_existing), columns=[match_field]))
                                            st.error("❌ Cannot update non-existing records.")
                                            validation_passed = False
                                        else:
                                            st.success(f"✅ All {len(existing_records)} records found - ready for update")
                                            
                                    except Exception as e:
                                        st.warning(f"⚠️ Could not verify: {str(e)}")
                                        st.info("💡 Proceeding with update")
                            
                            elif matching_strategy == "field_combination":
                                # Field Combination validation
                                st.info(f"🔍 Validating using Field Combination: {', '.join(match_fields)}...")
                                
                                # Check for duplicates in combination
                                duplicate_count = df_to_load[match_fields].duplicated().sum()
                                
                                if duplicate_count > 0:
                                    st.error(f"❌ Found {duplicate_count} duplicate field combinations in uploaded file")
                                    duplicates = df_to_load[df_to_load[match_fields].duplicated(keep=False)][match_fields]
                                    with st.expander("🔍 View Duplicate Combinations"):
                                        st.dataframe(duplicates)
                                    validation_issues.append(f"{duplicate_count} duplicate combinations")
                                
                                # Check if combinations exist in Salesforce
                                if not validation_issues:
                                    st.info("🔍 Verifying field combinations exist in Salesforce...")
                                    try:
                                        # Build SOQL query with multiple field conditions
                                        where_clauses = []
                                        for _, row in df_to_load[match_fields].drop_duplicates().iterrows():
                                            conditions = []
                                            for field in match_fields:
                                                value = row[field]
                                                if pd.notna(value):
                                                    escaped_value = str(value).replace("'", "\\'")
                                                    conditions.append(f"{field} = '{escaped_value}'")
                                            if conditions:
                                                where_clauses.append(f"({' AND '.join(conditions)})")
                                        
                                        # Query in batches
                                        batch_size = 20  # Smaller batches for complex queries
                                        total_found = 0
                                        total_to_check = len(where_clauses)
                                        
                                        for i in range(0, len(where_clauses), batch_size):
                                            batch_clauses = where_clauses[i:i + batch_size]
                                            where_statement = ' OR '.join(batch_clauses)
                                            
                                            soql_query = f"SELECT {', '.join(match_fields)} FROM {target_object} WHERE {where_statement}"
                                            result = sf_conn.query(soql_query)
                                            total_found += result['totalSize']
                                        
                                        if total_found < total_to_check:
                                            st.error(f"❌ Only {total_found}/{total_to_check} field combinations exist in Salesforce")
                                            st.error("❌ Some records cannot be matched. Cannot proceed with update.")
                                            validation_passed = False
                                        else:
                                            st.success(f"✅ All {total_found} field combinations found - ready for update")
                                            
                                    except Exception as e:
                                        st.warning(f"⚠️ Could not verify: {str(e)}")
                                        st.info("💡 Proceeding with update")
                            
                            elif matching_strategy == "field_concatenation":
                                # Field Concatenation validation
                                separator = st.session_state.get('update_concat_separator', '_')
                                st.info(f"🔍 Validating using Field Concatenation: {' {sep} '.join(match_fields).replace('{sep}', separator)}...")
                                
                                # Create concatenated column
                                df_to_load['_match_key'] = df_to_load.apply(
                                    lambda row: separator.join([str(row[f]) for f in match_fields]), axis=1
                                )
                                
                                # Check for duplicates
                                duplicate_count = df_to_load['_match_key'].duplicated().sum()
                                
                                if duplicate_count > 0:
                                    st.error(f"❌ Found {duplicate_count} duplicate concatenated values")
                                    duplicates = df_to_load[df_to_load['_match_key'].duplicated(keep=False)][match_fields + ['_match_key']]
                                    with st.expander("🔍 View Duplicates"):
                                        st.dataframe(duplicates)
                                    validation_issues.append(f"{duplicate_count} duplicates")
                                
                                # Check if concatenated values exist in Salesforce
                                if not validation_issues:
                                    st.info("🔍 Verifying concatenated field combinations exist in Salesforce...")
                                    try:
                                        # Similar to field combination but checking concatenated values
                                        where_clauses = []
                                        for _, row in df_to_load[match_fields].drop_duplicates().iterrows():
                                            conditions = []
                                            for field in match_fields:
                                                value = row[field]
                                                if pd.notna(value):
                                                    escaped_value = str(value).replace("'", "\\'")
                                                    conditions.append(f"{field} = '{escaped_value}'")
                                            if conditions:
                                                where_clauses.append(f"({' AND '.join(conditions)})")
                                        
                                        batch_size = 20
                                        total_found = 0
                                        total_to_check = len(where_clauses)
                                        
                                        for i in range(0, len(where_clauses), batch_size):
                                            batch_clauses = where_clauses[i:i + batch_size]
                                            where_statement = ' OR '.join(batch_clauses)
                                            
                                            soql_query = f"SELECT {', '.join(match_fields)} FROM {target_object} WHERE {where_statement}"
                                            result = sf_conn.query(soql_query)
                                            total_found += result['totalSize']
                                        
                                        if total_found < total_to_check:
                                            st.error(f"❌ Only {total_found}/{total_to_check} records exist in Salesforce")
                                            st.error("❌ Some concatenated combinations cannot be matched. Cannot proceed.")
                                            validation_passed = False
                                        else:
                                            st.success(f"✅ All {total_found} concatenated combinations found - ready for update")
                                            
                                    except Exception as e:
                                        st.warning(f"⚠️ Could not verify: {str(e)}")
                                        st.info("💡 Proceeding with update")
                            
                            if validation_issues:
                                st.error(f"❌ Fix these issues: {', '.join(validation_issues)}")
                                validation_passed = False
                    
                    elif operation_type == "Upsert":
                        # Get matching strategy from session state
                        upsert_matching_strategy = st.session_state.get('upsert_matching_strategy', None)
                        upsert_match_fields = st.session_state.get('upsert_match_fields', None)
                        
                        if not upsert_matching_strategy or not upsert_match_fields:
                            st.error("❌ Cannot proceed: Please configure matching strategy in Configuration tab.")
                            validation_passed = False
                        else:
                            validation_issues = []
                            
                            if upsert_matching_strategy == "external_id":
                                # Single Field validation
                                match_field = upsert_match_fields[0]
                                st.info(f"🔍 Validating using field: '{match_field}'...")
                                
                                duplicate_count = df_to_load[match_field].duplicated().sum()
                                null_count = df_to_load[match_field].isnull().sum()
                                empty_count = (df_to_load[match_field].astype(str).str.strip() == '').sum()
                                
                                # Critical: Duplicates block upsert
                                if duplicate_count > 0:
                                    st.error(f"❌ Found {duplicate_count} duplicate values in '{match_field}'")
                                    duplicates = df_to_load[df_to_load[match_field].duplicated(keep=False)][match_field].value_counts()
                                    with st.expander("🔍 View Duplicates"):
                                        st.write(duplicates)
                                    st.error("❌ Cannot proceed: Each value must appear only once in your file.")
                                    validation_passed = False
                                else:
                                    # Info: Empty values will be inserted
                                    if null_count > 0 or empty_count > 0:
                                        total_empty = null_count + empty_count
                                        st.info(f"ℹ️ {total_empty} records have empty '{match_field}' (will be inserted as new)")
                                    
                                    # Query to show split
                                    try:
                                        st.info("🔍 Checking which records exist in Salesforce...")
                                        unique_ids = df_to_load[match_field].dropna().unique().tolist()
                                        existing_records = []
                                        batch_size = 200
                                        
                                        for i in range(0, len(unique_ids), batch_size):
                                            batch_ids = unique_ids[i:i + batch_size]
                                            formatted_ids = [f"'{str(id).replace(chr(39), chr(92)+chr(39))}'" for id in batch_ids]
                                            ids_string = ','.join(formatted_ids)
                                            
                                            soql_query = f"SELECT {match_field} FROM {target_object} WHERE {match_field} IN ({ids_string})"
                                            result = sf_conn.query(soql_query)
                                            
                                            if result['totalSize'] > 0:
                                                existing_records.extend([rec[match_field] for rec in result['records']])
                                        
                                        new_records_count = len(unique_ids) - len(existing_records) + (null_count + empty_count)
                                        
                                        col_u1, col_u2 = st.columns(2)
                                        with col_u1:
                                            st.info(f"🔄 **Will UPDATE**: {len(existing_records)} existing records")
                                        with col_u2:
                                            st.info(f"🆕 **Will INSERT**: {new_records_count} new records")
                                        
                                        st.success(f"✅ Ready for upsert: {len(existing_records)} updates + {new_records_count} inserts")
                                        
                                    except Exception as e:
                                        st.warning(f"⚠️ Could not query: {str(e)}")
                                        st.info("💡 Proceeding with upsert")
                            
                            elif upsert_matching_strategy == "field_combination":
                                # Field Combination validation
                                st.info(f"🔍 Validating using Field Combination: {', '.join(upsert_match_fields)}...")
                                
                                # Check for duplicates in combination
                                duplicate_count = df_to_load[upsert_match_fields].duplicated().sum()
                                
                                if duplicate_count > 0:
                                    st.error(f"❌ Found {duplicate_count} duplicate field combinations in uploaded file")
                                    duplicates = df_to_load[df_to_load[upsert_match_fields].duplicated(keep=False)][upsert_match_fields]
                                    with st.expander("🔍 View Duplicate Combinations"):
                                        st.dataframe(duplicates)
                                    st.error("❌ Cannot proceed: Each field combination must appear only once.")
                                    validation_passed = False
                                else:
                                    # Query to show split
                                    try:
                                        st.info("🔍 Checking which field combinations exist in Salesforce...")
                                        where_clauses = []
                                        for _, row in df_to_load[upsert_match_fields].drop_duplicates().iterrows():
                                            conditions = []
                                            for field in upsert_match_fields:
                                                value = row[field]
                                                if pd.notna(value):
                                                    escaped_value = str(value).replace("'", "\\'")
                                                    conditions.append(f"{field} = '{escaped_value}'")
                                            if conditions:
                                                where_clauses.append(f"({' AND '.join(conditions)})")
                                        
                                        batch_size = 20
                                        total_found = 0
                                        
                                        for i in range(0, len(where_clauses), batch_size):
                                            batch_clauses = where_clauses[i:i + batch_size]
                                            where_statement = ' OR '.join(batch_clauses)
                                            
                                            soql_query = f"SELECT {', '.join(upsert_match_fields)} FROM {target_object} WHERE {where_statement}"
                                            result = sf_conn.query(soql_query)
                                            total_found += result['totalSize']
                                        
                                        new_records_count = len(where_clauses) - total_found
                                        
                                        col_u1, col_u2 = st.columns(2)
                                        with col_u1:
                                            st.info(f"🔄 **Will UPDATE**: {total_found} existing combinations")
                                        with col_u2:
                                            st.info(f"🆕 **Will INSERT**: {new_records_count} new combinations")
                                        
                                        st.success(f"✅ Ready for upsert: {total_found} updates + {new_records_count} inserts")
                                        
                                    except Exception as e:
                                        st.warning(f"⚠️ Could not verify: {str(e)}")
                                        st.info("💡 Proceeding with upsert")
                            
                            elif upsert_matching_strategy == "field_concatenation":
                                # Field Concatenation validation
                                separator = st.session_state.get('upsert_concat_separator', '_')
                                st.info(f"🔍 Validating using Field Concatenation: {' {sep} '.join(upsert_match_fields).replace('{sep}', separator)}...")
                                
                                # Create concatenated column
                                df_to_load['_match_key'] = df_to_load.apply(
                                    lambda row: separator.join([str(row[f]) for f in upsert_match_fields]), axis=1
                                )
                                
                                # Check for duplicates
                                duplicate_count = df_to_load['_match_key'].duplicated().sum()
                                
                                if duplicate_count > 0:
                                    st.error(f"❌ Found {duplicate_count} duplicate concatenated values")
                                    duplicates = df_to_load[df_to_load['_match_key'].duplicated(keep=False)][upsert_match_fields + ['_match_key']]
                                    with st.expander("🔍 View Duplicates"):
                                        st.dataframe(duplicates)
                                    st.error("❌ Cannot proceed: Each concatenated value must appear only once.")
                                    validation_passed = False
                                else:
                                    # Query to show split
                                    try:
                                        st.info("🔍 Checking which concatenated combinations exist in Salesforce...")
                                        where_clauses = []
                                        for _, row in df_to_load[upsert_match_fields].drop_duplicates().iterrows():
                                            conditions = []
                                            for field in upsert_match_fields:
                                                value = row[field]
                                                if pd.notna(value):
                                                    escaped_value = str(value).replace("'", "\\'")
                                                    conditions.append(f"{field} = '{escaped_value}'")
                                            if conditions:
                                                where_clauses.append(f"({' AND '.join(conditions)})")
                                        
                                        batch_size = 20
                                        total_found = 0
                                        
                                        for i in range(0, len(where_clauses), batch_size):
                                            batch_clauses = where_clauses[i:i + batch_size]
                                            where_statement = ' OR '.join(batch_clauses)
                                            
                                            soql_query = f"SELECT {', '.join(upsert_match_fields)} FROM {target_object} WHERE {where_statement}"
                                            result = sf_conn.query(soql_query)
                                            total_found += result['totalSize']
                                        
                                        new_records_count = len(where_clauses) - total_found
                                        
                                        col_u1, col_u2 = st.columns(2)
                                        with col_u1:
                                            st.info(f"🔄 **Will UPDATE**: {total_found} existing records")
                                        with col_u2:
                                            st.info(f"🆕 **Will INSERT**: {new_records_count} new records")
                                        
                                        st.success(f"✅ Ready for upsert: {total_found} updates + {new_records_count} inserts")
                                        
                                    except Exception as e:
                                        st.warning(f"⚠️ Could not verify: {str(e)}")
                                        st.info("💡 Proceeding with upsert")
                
                if validation_passed:
                    # Get additional parameters for different operations
                    insert_match_field = st.session_state.get('insert_match_field', None) if operation_type == "Insert" else None
                    update_match_field = st.session_state.get('match_field', None) if operation_type == "Update" else None
                    upsert_match_field = st.session_state.get('upsert_match_field', None) if operation_type == "Upsert" else None
                    
                    # Get UPDATE matching strategy parameters
                    update_matching_strategy = st.session_state.get('update_matching_strategy', None) if operation_type == "Update" else None
                    update_match_fields = st.session_state.get('update_match_fields', None) if operation_type == "Update" else None
                    update_concat_separator = st.session_state.get('update_concat_separator', None) if operation_type == "Update" else None
                    
                    # Get UPSERT matching strategy parameters
                    upsert_matching_strategy = st.session_state.get('upsert_matching_strategy', None) if operation_type == "Upsert" else None
                    upsert_match_fields = st.session_state.get('upsert_match_fields', None) if operation_type == "Upsert" else None
                    upsert_concat_separator = st.session_state.get('upsert_concat_separator', None) if operation_type == "Upsert" else None
                    
                    load_data_to_salesforce(sf_conn, df_to_load, target_object, 
                                          operation_type, batch_size, parallel_batches, 
                                          upsert_match_field, update_match_field, insert_match_field,
                                          update_matching_strategy, update_match_fields, update_concat_separator,
                                          upsert_matching_strategy, upsert_match_fields, upsert_concat_separator)

def show_sql_migration(credentials: Dict):
    """SQL migration operations"""
    st.subheader("🔄 SQL Migration")
    st.markdown("Migrate data from Salesforce or files to SQL Server")
    
    # SQL connection selection
    sql_connections = {k: v for k, v in credentials.items() if 'sql' in k.lower()}
    
    if not sql_connections:
        st.warning("⚠️ No SQL Server connections configured.")
        return
    
    target_db = st.selectbox(
        "Select Target Database",
        options=[""] + list(sql_connections.keys()),
        key="sql_migration_target"
    )
    
    if target_db:
        # Migration source
        migration_source = st.radio(
            "Migration Source",
            ["From Salesforce", "From File"],
            key="migration_source"
        )
        
        if migration_source == "From Salesforce":
            migrate_from_salesforce_to_sql(credentials, target_db)
        else:
            migrate_from_file_to_sql(credentials, target_db)

def show_bulk_operations(sf_conn, credentials: Dict):
    """Bulk operations interface"""
    st.subheader("📊 Bulk Operations")
    st.markdown("Perform bulk operations across multiple objects or organizations")
    
    # Bulk operation type
    bulk_operation = st.selectbox(
        "Select Bulk Operation",
        [
            "Multi-Object Extraction",
            "Batch Data Loading", 
            "Cross-Org Migration",
            "Bulk Validation"
        ],
        key="bulk_operation_type"
    )
    
    if bulk_operation == "Multi-Object Extraction":
        show_multi_object_extraction(sf_conn)
    elif bulk_operation == "Batch Data Loading":
        show_batch_data_loading(sf_conn)
    elif bulk_operation == "Cross-Org Migration":
        show_cross_org_migration(credentials)
    else:
        show_bulk_validation(sf_conn)

# Helper functions
def show_object_info(sf_conn, object_name: str):
    """Display Salesforce object information"""
    try:
        obj_desc = getattr(sf_conn, object_name).describe()
        
        with st.expander(f"📋 {object_name} Object Details", expanded=True):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Label:** {obj_desc.get('label', 'N/A')}")
                st.write(f"**API Name:** {obj_desc.get('name', 'N/A')}")
                st.write(f"**Type:** {'Custom' if obj_desc.get('custom') else 'Standard'}")
            
            with col2:
                st.write(f"**Creatable:** {'Yes' if obj_desc.get('createable') else 'No'}")
                st.write(f"**Updateable:** {'Yes' if obj_desc.get('updateable') else 'No'}")
                st.write(f"**Deletable:** {'Yes' if obj_desc.get('deletable') else 'No'}")
            
            # Show some fields
            fields = obj_desc.get('fields', [])
            st.write(f"**Total Fields:** {len(fields)}")
            
            if st.checkbox("Show Field Details"):
                field_data = []
                for field in fields[:20]:  # Show first 20 fields
                    field_data.append({
                        "Field Name": field.get('name', ''),
                        "Label": field.get('label', ''),
                        "Type": field.get('type', ''),
                        "Required": field.get('nillable', True) == False
                    })
                
                if field_data:
                    df_fields = pd.DataFrame(field_data)
                    st.dataframe(df_fields, use_container_width=True)
                    
    except Exception as e:
        st.error(f"❌ Error getting object info: {str(e)}")

def extract_salesforce_data(sf_conn, object_name: str, query_type: str, days_back: Optional[int] = None, custom_query: Optional[str] = None):
    """Extract data from Salesforce"""
    try:
        with st.spinner("Extracting data from Salesforce..."):
            
            if query_type == "Custom SOQL" and custom_query:
                query = custom_query
            elif query_type == "Recent Records" and days_back:
                query = f"SELECT Id, Name FROM {object_name} WHERE CreatedDate = LAST_N_DAYS:{days_back}"
            else:
                # Get all records (limited)
                query = f"SELECT Id, Name FROM {object_name} LIMIT 1000"
            
            # Execute query
            result = sf_conn.query_all(query)
            records = result['records']
            
            if records:
                # Remove Salesforce metadata
                clean_records = []
                for record in records:
                    clean_record = {k: v for k, v in record.items() if k != 'attributes'}
                    clean_records.append(clean_record)
                
                df = pd.DataFrame(clean_records)
                
                # Display results
                st.success(f"✅ Extracted {len(df)} records from {object_name}")
                display_dataframe_with_download(df, f"{object_name}_extract.csv", 
                                              f"Extracted Data from {object_name}")
                
                # Save to DataFiles
                save_dir = os.path.join(project_root, 'DataFiles', st.session_state.current_org, object_name, 'extract', 'salesforce')
                os.makedirs(save_dir, exist_ok=True)
                
                save_path = os.path.join(save_dir, f"{object_name}.csv")
                df.to_csv(save_path, index=False)
                
                show_processing_status("sf_extract", f"Extracted {len(df)} records from {object_name}", "success")
                
            else:
                st.warning("⚠️ No records found matching the criteria")
                
    except Exception as e:
        st.error(f"❌ Error extracting data: {str(e)}")
        show_processing_status("sf_extract", f"Failed to extract from {object_name}: {str(e)}", "error")

def get_existing_files(directory: str) -> list:
    """Get list of existing data files"""
    files = []
    try:
        for root, dirs, filenames in os.walk(directory):
            for filename in filenames:
                if filename.endswith(('.csv', '.xlsx', '.xls', '.psv')):
                    # Get relative path from DataFiles directory
                    rel_path = os.path.relpath(os.path.join(root, filename), directory)
                    files.append(rel_path)
    except Exception:
        pass
    
    return sorted(files)

def test_sql_connection(db_config: Dict):
    """Test SQL connection with enhanced feedback"""
    try:
        import pyodbc
        
        with st.spinner("Testing SQL Server connection..."):
            # Build connection string based on enhanced config
            connection_string = f"DRIVER={db_config['driver']};SERVER={db_config['server']};DATABASE={db_config['database']}"
            
            # Add port if specified
            if db_config.get('port') and db_config.get('port') != '1433':
                if '\\' not in db_config['server']:  # Only add port if not using named instance
                    connection_string = f"DRIVER={db_config['driver']};SERVER={db_config['server']},{db_config['port']};DATABASE={db_config['database']}"
            
            # Add authentication
            if db_config.get('Trusted_Connection') == 'yes':
                connection_string += ";Trusted_Connection=yes"
            else:
                connection_string += f";UID={db_config['username']};PWD={db_config['password']}"
            
            # Add enhanced settings if available
            if db_config.get('encrypt'):
                connection_string += f";Encrypt={db_config['encrypt']}"
            
            if db_config.get('trust_server_cert'):
                connection_string += ";TrustServerCertificate=yes"
            
            if db_config.get('connection_timeout'):
                connection_string += f";Connection Timeout={db_config['connection_timeout']}"
            
            if db_config.get('application_name'):
                connection_string += f";APP={db_config['application_name']}"
            
            # Test connection
            with pyodbc.connect(connection_string) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT @@VERSION as sql_version, DB_NAME() as current_db, SYSTEM_USER as current_user, COUNT(*) as table_count FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'")
                result = cursor.fetchone()
                
                if result:
                    st.success("✅ **SQL Server connection successful!**")
                    
                    # Show connection details
                    col1, col2 = st.columns(2)
                    with col1:
                        st.info(f"**Database:** {result.current_db}")
                        st.info(f"**Connected User:** {result.current_user}")
                    
                    with col2:
                        st.info(f"**Tables Available:** {result.table_count}")
                        st.info("**Status:** ✅ Ready for queries")
                    
                    show_processing_status("sql_connection_test", "SQL Server connection successful", "success")
                else:
                    st.error("❌ Database connection failed")
                    
    except ImportError:
        st.error("❌ **pyodbc module not installed**")
        st.code("pip install pyodbc", language="bash")
    except Exception as e:
        st.error(f"❌ **SQL Server connection failed**")
        
        error_msg = str(e)
        if "Login failed" in error_msg:
            st.warning("🔐 **Authentication Issue:** Check username and password")
        elif "server was not found" in error_msg:
            st.warning("🌐 **Server Issue:** Check server address and port") 
        else:
            st.warning(f"**Error:** {error_msg}")

def execute_sql_query(db_config: Dict, query: str):
    """Execute SQL query with enhanced connection handling"""
    try:
        import pyodbc
        
        # Build connection string (same as test_sql_connection)
        connection_string = f"DRIVER={db_config['driver']};SERVER={db_config['server']};DATABASE={db_config['database']}"
        
        # Add port if specified
        if db_config.get('port') and db_config.get('port') != '1433':
            if '\\' not in db_config['server']:
                connection_string = f"DRIVER={db_config['driver']};SERVER={db_config['server']},{db_config['port']};DATABASE={db_config['database']}"
        
        # Add authentication
        if db_config.get('Trusted_Connection') == 'yes':
            connection_string += ";Trusted_Connection=yes"
        else:
            connection_string += f";UID={db_config['username']};PWD={db_config['password']}"
        
        # Add enhanced settings
        if db_config.get('encrypt'):
            connection_string += f";Encrypt={db_config['encrypt']}"
        
        if db_config.get('trust_server_cert'):
            connection_string += ";TrustServerCertificate=yes"
        
        if db_config.get('connection_timeout'):
            connection_string += f";Connection Timeout={db_config['connection_timeout']}"
        
        if db_config.get('application_name'):
            connection_string += f";APP={db_config['application_name']}"
        
        # Add command timeout if available
        command_timeout = db_config.get('command_timeout', 300)
        
        with st.spinner("Executing SQL query..."):
            with pyodbc.connect(connection_string) as conn:
                # Set command timeout
                conn.timeout = command_timeout
                
                df = pd.read_sql(query, conn)
                
                if not df.empty:
                    st.success(f"✅ **Query executed successfully!** {len(df)} rows returned.")
                    
                    # Show query statistics
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Rows", len(df))
                    with col2:
                        st.metric("Columns", len(df.columns))
                    with col3:
                        st.metric("Size", f"{df.memory_usage(deep=True).sum() / 1024:.1f} KB")
                    
                    # Display results with download option
                    display_dataframe_with_download(df, "sql_query_result.csv", "SQL Query Results")
                else:
                    st.info("✅ Query executed successfully but returned no data.")
                    
                show_processing_status("sql_query", "SQL query executed successfully", "success")
                
    except ImportError:
        st.error("❌ **pyodbc module not installed**")
        st.code("pip install pyodbc", language="bash")
    except Exception as e:
        st.error(f"❌ **Query execution failed**")
        st.warning(f"**Error:** {str(e)}")
        show_processing_status("sql_query", f"SQL query failed: {str(e)}", "error")

def load_data_to_salesforce(sf_conn, df: pd.DataFrame, target_object: str, operation: str, batch_size: int, parallel_batches: int, upsert_match_field: str = None, update_match_field: str = None, insert_match_field: str = None, update_matching_strategy: str = None, update_match_fields: list = None, update_concat_separator: str = None, upsert_matching_strategy: str = None, upsert_match_fields: list = None, upsert_concat_separator: str = None):
    """Load data to Salesforce with batch processing and external ID-based duplicate detection
    
    Args:
        sf_conn: Salesforce connection
        df: DataFrame to load
        target_object: Target Salesforce object
        operation: insert/update/upsert
        batch_size: Records per batch
        parallel_batches: Number of parallel batches
        upsert_match_field: Field for upsert matching (legacy single field)
        update_match_field: Field for update matching (single external ID strategy)
        insert_match_field: External ID field for insert tracking
        update_matching_strategy: Strategy for UPDATE operation ('external_id', 'field_combination', 'field_concatenation')
        update_match_fields: List of fields to use for UPDATE field combination/concatenation matching
        update_concat_separator: Separator for UPDATE field concatenation strategy
        upsert_matching_strategy: Strategy for UPSERT operation ('external_id', 'field_combination', 'field_concatenation')
        upsert_match_fields: List of fields to use for UPSERT field combination/concatenation matching
        upsert_concat_separator: Separator for UPSERT field concatenation strategy
    """
    try:
        total_records = len(df)
        
        # Progress tracking
        progress_steps = [
            "Preparing data",
            "Creating batches", 
            "Processing batches",
            "Finalizing results"
        ]
        
        progress_container = st.container()
        
        with progress_container:
            create_progress_tracker(progress_steps, 1)
        
        # Resolve lookup fields before cleaning data (with enhanced statistics)
        st.info("🔄 Resolving lookup fields...")
        lookup_result = resolve_lookup_fields(sf_conn, df, target_object, return_stats=True)
        
        # Handle different return formats
        if lookup_result is None:
            df_with_lookups = None
            lookup_fields = {}
            lookup_count_summary = {}
        elif isinstance(lookup_result, tuple):
            df_with_lookups, lookup_fields, lookup_count_summary = lookup_result
        else:
            # Fallback for compatibility
            df_with_lookups = lookup_result
            lookup_fields = {}
            lookup_count_summary = {}
        
        # Check if lookup resolution failed due to empty parent objects or pending selections
        if df_with_lookups is None:
            st.warning("⚠️ **Cannot proceed with data loading**")
            
            st.info("💡 **Possible reasons:**")
            with st.expander("🔍 Troubleshooting Guide"):
                st.write("**1. Empty Parent Object:**")
                st.write("   • Parent object has no records at all")
                st.write("   • Solution: Add data to parent object first")
                st.write("")
                st.write("**2. Pending User Selections:**") 
                st.write("   • Multiple parent records found with same name")
                st.write("   • Solution: Make selections above and try again")
                st.write("")
                st.write("**3. Core Logic Applied:**")
                st.write("   • System checks if parent object has ANY data")
                st.write("   • If parent object is empty → Block child uploads")
                st.write("   • If parent object has data → Allow uploads (with warnings for missing specific records)")
            
            show_processing_status("data_load", "Data loading blocked: Parent object validation required", "error")
            return
        
        # Generate composite keys or rename fields for INSERT operation only
        if operation.lower() == "insert":
            is_composite = st.session_state.get('insert_is_composite', False)
            
            if is_composite and st.session_state.get('composite_external_id_insert'):
                # Generate composite key for INSERT
                st.info("🔗 Generating composite external ID for insert operation...")
                composite_config = st.session_state.composite_external_id_insert
                
                # Create composite key column
                composite_keys = create_composite_key_column(
                    df_with_lookups,
                    composite_config['fields'],
                    composite_config['separator'],
                    composite_config['null_handling']
                )
                
                # Add composite key column with Salesforce target field name
                target_field = composite_config['target_field']
                df_with_lookups[target_field] = composite_keys
                st.success(f"✅ Generated composite external ID in field: {target_field}")
                
            elif not is_composite:
                # Rename single source field to target field for INSERT
                source_field = st.session_state.get('insert_source_field')
                target_field = st.session_state.get('insert_target_field')
                
                if source_field and target_field and source_field in df_with_lookups.columns:
                    if source_field != target_field:
                        # Copy source field to target field name
                        df_with_lookups[target_field] = df_with_lookups[source_field]
                        st.success(f"✅ Mapped '{source_field}' → '{target_field}' for external ID")
        
        # For UPDATE and UPSERT, the external ID field should already exist in the data
        
        # Clean data before conversion - FIX FOR NaN ERROR
        df_cleaned = clean_dataframe_for_salesforce(df_with_lookups)
        
        # Convert DataFrame to records
        records = df_cleaned.to_dict('records')
        
        with progress_container:
            create_progress_tracker(progress_steps, 2)
        
        # Create batches
        batches = [records[i:i + batch_size] for i in range(0, len(records), batch_size)]
        
        st.info(f"Processing {total_records} records in {len(batches)} batches")
        
        # Process batches with detailed result tracking
        success_records = []
        failed_records = []
        success_count = 0
        error_count = 0
        
        batch_progress = st.progress(0)
        batch_status = st.empty()
        
        for i, batch in enumerate(batches):
            batch_status.info(f"Processing batch {i + 1} of {len(batches)}...")
            
            try:
                if operation.lower() == "insert":
                    # Insert operation - validate uniqueness before inserting
                    insert_matching_strategy = st.session_state.get('insert_matching_strategy', None)
                    insert_match_fields = st.session_state.get('insert_match_fields', None)
                    target_field = st.session_state.get('insert_target_field', insert_match_field)
                    
                    # Check for duplicates in Salesforce before inserting
                    validated_insert_batch = []
                    duplicate_inserts = []
                    
                    st.info(f"🔍 Batch {i + 1}: Validating {len(batch)} records for uniqueness in Salesforce...")
                    
                    if insert_matching_strategy == "field_combination" and insert_match_fields:
                        # Field combination validation
                        source_fields = insert_match_fields
                        
                        for record in batch:
                                # Build WHERE clause for composite fields
                                conditions = []
                                has_all_fields = True
                                
                                for field in source_fields:
                                    value = record.get(field)
                                    if not value or (isinstance(value, str) and value.strip() == ''):
                                        has_all_fields = False
                                        break
                                    escaped_value = str(value).replace("'", "\\'")
                                    conditions.append(f"{field} = '{escaped_value}'")
                                
                                if not has_all_fields:
                                    # Cannot validate incomplete records - skip insert
                                    combination_str = ' | '.join([f"{f}={record.get(f)}" for f in source_fields])
                                    duplicate_inserts.append({
                                        'record': record,
                                        'reason': f"Incomplete combination: {combination_str}"
                                    })
                                    continue
                                
                                try:
                                    # Check if combination already exists
                                    where_clause = ' AND '.join(conditions)
                                    check_query = f"SELECT Id FROM {target_object} WHERE {where_clause} LIMIT 1"
                                    check_result = sf_conn.query(check_query)
                                    
                                    if check_result['totalSize'] > 0:
                                        # Duplicate found
                                        combination_str = ' | '.join([f"{f}={record.get(f)}" for f in source_fields])
                                        duplicate_inserts.append({
                                            'record': record,
                                            'reason': f"Duplicate combination already exists: {combination_str}"
                                        })
                                    else:
                                        # Safe to insert
                                        validated_insert_batch.append(record)
                                except Exception as e:
                                    st.warning(f"⚠️ Could not verify uniqueness: {str(e)}")
                                    validated_insert_batch.append(record)  # Proceed with insert
                    
                    elif insert_matching_strategy == "field_concatenation" and insert_match_fields:
                        # Field concatenation validation
                        source_fields = insert_match_fields
                        
                        for record in batch:
                            # Build WHERE clause for concatenated fields
                            conditions = []
                            has_all_fields = True
                            
                            for field in source_fields:
                                value = record.get(field)
                                if not value or (isinstance(value, str) and value.strip() == ''):
                                    has_all_fields = False
                                    break
                                escaped_value = str(value).replace("'", "\\'")
                                conditions.append(f"{field} = '{escaped_value}'")
                            
                            if not has_all_fields:
                                # Cannot validate incomplete records - skip insert
                                combination_str = ' | '.join([f"{f}={record.get(f)}" for f in source_fields])
                                duplicate_inserts.append({
                                    'record': record,
                                    'reason': f"Incomplete concatenation: {combination_str}"
                                })
                                continue
                            
                            try:
                                # Check if concatenation already exists
                                where_clause = ' AND '.join(conditions)
                                check_query = f"SELECT Id FROM {target_object} WHERE {where_clause} LIMIT 1"
                                check_result = sf_conn.query(check_query)
                                
                                if check_result['totalSize'] > 0:
                                    # Duplicate found
                                    separator = st.session_state.get('insert_concat_separator', '_')
                                    concat_value = separator.join([str(record.get(f)) for f in source_fields])
                                    duplicate_inserts.append({
                                        'record': record,
                                        'reason': f"Duplicate concatenation already exists: {concat_value}"
                                    })
                                else:
                                    # Safe to insert
                                    validated_insert_batch.append(record)
                            except Exception as e:
                                st.warning(f"⚠️ Could not verify uniqueness: {str(e)}")
                                validated_insert_batch.append(record)  # Proceed with insert
                    
                    elif insert_matching_strategy == "external_id" and insert_match_fields:
                        # Single field validation
                        source_field = insert_match_fields[0]
                        
                        if source_field and target_field:
                            for record in batch:
                                match_value = record.get(source_field)
                                
                                if not match_value or str(match_value).strip() == '':
                                    # Empty value - cannot validate
                                    duplicate_inserts.append({
                                        'record': record,
                                        'reason': f"Empty {source_field} value"
                                    })
                                    continue
                                
                                try:
                                    # Check if value already exists in target field
                                    escaped_value = str(match_value).replace("'", "\\'")
                                    check_query = f"SELECT Id FROM {target_object} WHERE {target_field} = '{escaped_value}' LIMIT 1"
                                    check_result = sf_conn.query(check_query)
                                    
                                    if check_result['totalSize'] > 0:
                                        # Duplicate found
                                        duplicate_inserts.append({
                                            'record': record,
                                            'reason': f"Duplicate {target_field} already exists: {match_value}"
                                        })
                                    else:
                                        # Safe to insert
                                        validated_insert_batch.append(record)
                                except Exception as e:
                                    st.warning(f"⚠️ Could not verify uniqueness for {match_value}: {str(e)}")
                                    validated_insert_batch.append(record)  # Proceed with insert
                    else:
                        # No matching strategy configured - insert all (should not happen with proper validation)
                        st.warning("⚠️ No uniqueness validation strategy configured - proceeding without validation")
                        validated_insert_batch = batch
                    
                    # Show duplicate warnings
                    if duplicate_inserts:
                        st.error(f"❌ Batch {i + 1}: Found {len(duplicate_inserts)} duplicate/invalid records - INSERT FAILED")
                        with st.expander("🔍 View Duplicate/Invalid Records"):
                            for dup in duplicate_inserts[:20]:  # Show first 20
                                st.write(f"• {dup['reason']}")
                            if len(duplicate_inserts) > 20:
                                st.write(f"... and {len(duplicate_inserts) - 20} more")
                        st.error("❌ Cannot proceed with INSERT - duplicates found in Salesforce. Use UPDATE or UPSERT instead.")
                        
                        # Stop processing this batch
                        continue
                    
                    # Proceed with insert only if all records are unique
                    if validated_insert_batch:
                        st.info(f"🆕 Batch {i + 1}: Inserting {len(validated_insert_batch)} unique records (populating external ID: '{target_field}')")
                        result = getattr(sf_conn.bulk, target_object).insert(validated_insert_batch)
                    else:
                        st.error(f"❌ Batch {i + 1}: No records to insert - all were duplicates")
                        continue
                elif operation.lower() == "update":
                    # Handle different matching strategies
                    update_batch = []
                    unmatched_records = []
                    
                    if update_matching_strategy == "external_id":
                        # Original single external ID matching
                        if not update_match_field:
                            raise ValueError("Update operation requires a match field to be specified.")
                        
                        for record in batch:
                            match_value = record.get(update_match_field)
                            
                            if not match_value or str(match_value).strip() == '':
                                unmatched_records.append(record)
                                continue
                            
                            try:
                                escaped_value = str(match_value).replace("'", "\\'")
                                soql_query = f"SELECT Id FROM {target_object} WHERE {update_match_field} = '{escaped_value}' LIMIT 1"
                                
                                query_result = sf_conn.query(soql_query)
                                
                                if query_result['totalSize'] > 0:
                                    record['Id'] = query_result['records'][0]['Id']
                                    update_batch.append(record)
                                else:
                                    unmatched_records.append(record)
                                    
                            except Exception as e:
                                st.warning(f"⚠️ Error querying for match value '{match_value}': {str(e)}")
                                unmatched_records.append(record)
                    
                    elif update_matching_strategy == "field_combination":
                        # Field combination matching
                        if not update_match_fields:
                            raise ValueError("Update operation with field combination requires match fields.")
                        
                        for record in batch:
                            try:
                                # Build WHERE clause with all match fields
                                conditions = []
                                skip_record = False
                                
                                for field in update_match_fields:
                                    value = record.get(field)
                                    if not value or (isinstance(value, str) and value.strip() == ''):
                                        skip_record = True
                                        break
                                    escaped_value = str(value).replace("'", "\\'")
                                    conditions.append(f"{field} = '{escaped_value}'")
                                
                                if skip_record:
                                    unmatched_records.append(record)
                                    continue
                                
                                where_clause = ' AND '.join(conditions)
                                soql_query = f"SELECT Id FROM {target_object} WHERE {where_clause} LIMIT 1"
                                
                                query_result = sf_conn.query(soql_query)
                                
                                if query_result['totalSize'] > 0:
                                    record['Id'] = query_result['records'][0]['Id']
                                    update_batch.append(record)
                                else:
                                    unmatched_records.append(record)
                                    
                            except Exception as e:
                                st.warning(f"⚠️ Error querying for field combination: {str(e)}")
                                unmatched_records.append(record)
                    
                    elif update_matching_strategy == "field_concatenation":
                        # Field concatenation matching
                        if not update_match_fields or not update_concat_separator:
                            raise ValueError("Update operation with concatenation requires match fields and separator.")
                        
                        for record in batch:
                            try:
                                # Build WHERE clause with all match fields (same as combination)
                                conditions = []
                                skip_record = False
                                
                                for field in update_match_fields:
                                    value = record.get(field)
                                    if not value or (isinstance(value, str) and value.strip() == ''):
                                        skip_record = True
                                        break
                                    escaped_value = str(value).replace("'", "\\'")
                                    conditions.append(f"{field} = '{escaped_value}'")
                                
                                if skip_record:
                                    unmatched_records.append(record)
                                    continue
                                
                                where_clause = ' AND '.join(conditions)
                                soql_query = f"SELECT Id FROM {target_object} WHERE {where_clause} LIMIT 1"
                                
                                query_result = sf_conn.query(soql_query)
                                
                                if query_result['totalSize'] > 0:
                                    record['Id'] = query_result['records'][0]['Id']
                                    update_batch.append(record)
                                else:
                                    unmatched_records.append(record)
                                    
                            except Exception as e:
                                st.warning(f"⚠️ Error querying for concatenated fields: {str(e)}")
                                unmatched_records.append(record)
                    
                    if unmatched_records:
                        st.warning(f"⚠️ Batch {i + 1}: {len(unmatched_records)} records could not be matched to existing Salesforce records")
                    
                    if update_batch:
                        st.info(f"📝 Batch {i + 1}: Updating {len(update_batch)} matched records")
                        result = getattr(sf_conn.bulk, target_object).update(update_batch)
                    else:
                        st.error(f"❌ Batch {i + 1}: No records could be matched for update")
                        continue
                else:  # upsert
                    # Split records into update and insert batches based on whether they exist in Salesforce
                    update_batch = []
                    insert_batch = []
                    unprocessable_records = []
                    
                    if upsert_matching_strategy == "external_id":
                        # Original single field matching
                        if not upsert_match_field:
                            raise ValueError("Upsert operation requires a match field to be specified.")
                        
                        for record in batch:
                            match_value = record.get(upsert_match_field)
                            
                            # Records with no match value go to insert
                            if not match_value or str(match_value).strip() == '':
                                insert_batch.append(record)
                                continue
                            
                            try:
                                # Query Salesforce to check if record exists
                                escaped_value = str(match_value).replace("'", "\\'")
                                soql_query = f"SELECT Id FROM {target_object} WHERE {upsert_match_field} = '{escaped_value}' LIMIT 1"
                                
                                query_result = sf_conn.query(soql_query)
                                
                                if query_result['totalSize'] > 0:
                                    # Record exists - add to update batch
                                    record['Id'] = query_result['records'][0]['Id']
                                    update_batch.append(record)
                                else:
                                    # Record doesn't exist - add to insert batch
                                    insert_batch.append(record)
                                    
                            except Exception as e:
                                st.warning(f"⚠️ Error querying for match value '{match_value}': {str(e)}")
                                unprocessable_records.append(record)
                    
                    elif upsert_matching_strategy == "field_combination":
                        # Field combination matching
                        if not upsert_match_fields:
                            raise ValueError("Upsert operation with field combination requires match fields.")
                        
                        for record in batch:
                            try:
                                # Build WHERE clause with all match fields
                                conditions = []
                                has_all_fields = True
                                
                                for field in upsert_match_fields:
                                    value = record.get(field)
                                    if not value or (isinstance(value, str) and value.strip() == ''):
                                        has_all_fields = False
                                        break
                                    escaped_value = str(value).replace("'", "\\'")
                                    conditions.append(f"{field} = '{escaped_value}'")
                                
                                # Records with incomplete field combinations go to insert
                                if not has_all_fields:
                                    insert_batch.append(record)
                                    continue
                                
                                where_clause = ' AND '.join(conditions)
                                soql_query = f"SELECT Id FROM {target_object} WHERE {where_clause} LIMIT 1"
                                
                                query_result = sf_conn.query(soql_query)
                                
                                if query_result['totalSize'] > 0:
                                    # Record exists - add to update batch
                                    record['Id'] = query_result['records'][0]['Id']
                                    update_batch.append(record)
                                else:
                                    # Record doesn't exist - add to insert batch
                                    insert_batch.append(record)
                                    
                            except Exception as e:
                                st.warning(f"⚠️ Error querying for field combination: {str(e)}")
                                unprocessable_records.append(record)
                    
                    elif upsert_matching_strategy == "field_concatenation":
                        # Field concatenation matching
                        if not upsert_match_fields or not upsert_concat_separator:
                            raise ValueError("Upsert operation with concatenation requires match fields and separator.")
                        
                        for record in batch:
                            try:
                                # Build WHERE clause with all match fields
                                conditions = []
                                has_all_fields = True
                                
                                for field in upsert_match_fields:
                                    value = record.get(field)
                                    if not value or (isinstance(value, str) and value.strip() == ''):
                                        has_all_fields = False
                                        break
                                    escaped_value = str(value).replace("'", "\\'")
                                    conditions.append(f"{field} = '{escaped_value}'")
                                
                                # Records with incomplete field combinations go to insert
                                if not has_all_fields:
                                    insert_batch.append(record)
                                    continue
                                
                                where_clause = ' AND '.join(conditions)
                                soql_query = f"SELECT Id FROM {target_object} WHERE {where_clause} LIMIT 1"
                                
                                query_result = sf_conn.query(soql_query)
                                
                                if query_result['totalSize'] > 0:
                                    # Record exists - add to update batch
                                    record['Id'] = query_result['records'][0]['Id']
                                    update_batch.append(record)
                                else:
                                    # Record doesn't exist - add to insert batch
                                    insert_batch.append(record)
                                    
                            except Exception as e:
                                st.warning(f"⚠️ Error querying for concatenated fields: {str(e)}")
                                unprocessable_records.append(record)
                    
                    # Process updates first
                    update_results = []
                    if update_batch:
                        st.info(f"🔄 Batch {i + 1}: Updating {len(update_batch)} existing records")
                        try:
                            update_results = getattr(sf_conn.bulk, target_object).update(update_batch)
                        except Exception as e:
                            st.error(f"❌ Error updating records in batch {i + 1}: {str(e)}")
                            update_results = []
                    
                    # Validate insert batch before inserting - check for duplicates in Salesforce
                    validated_insert_batch = []
                    duplicate_inserts = []
                    
                    if insert_batch:
                        st.info(f"🔍 Batch {i + 1}: Validating {len(insert_batch)} records before insert...")
                        
                        if upsert_matching_strategy == "external_id" and upsert_match_fields:
                            # Single field validation
                            match_field = upsert_match_fields[0]
                            
                            for record in insert_batch:
                                match_value = record.get(match_field)
                                
                                # Records with empty values can be inserted (no way to check uniqueness)
                                if not match_value or str(match_value).strip() == '':
                                    validated_insert_batch.append(record)
                                    continue
                                
                                try:
                                    # Check if this value already exists in Salesforce
                                    escaped_value = str(match_value).replace("'", "\\'")
                                    check_query = f"SELECT Id FROM {target_object} WHERE {match_field} = '{escaped_value}' LIMIT 1"
                                    check_result = sf_conn.query(check_query)
                                    
                                    if check_result['totalSize'] > 0:
                                        # Duplicate found - skip insert
                                        duplicate_inserts.append({
                                            'record': record,
                                            'reason': f"Duplicate {match_field}: {match_value}"
                                        })
                                    else:
                                        # Safe to insert
                                        validated_insert_batch.append(record)
                                except Exception as e:
                                    st.warning(f"⚠️ Could not verify uniqueness for {match_value}: {str(e)}")
                                    validated_insert_batch.append(record)  # Proceed with insert
                        
                        elif upsert_matching_strategy in ["field_combination", "field_concatenation"] and upsert_match_fields:
                            # Field combination/concatenation validation
                            
                            for record in insert_batch:
                                # Build WHERE clause for this record
                                conditions = []
                                has_all_fields = True
                                
                                for field in upsert_match_fields:
                                    value = record.get(field)
                                    if not value or (isinstance(value, str) and value.strip() == ''):
                                        has_all_fields = False
                                        break
                                    escaped_value = str(value).replace("'", "\\'")
                                    conditions.append(f"{field} = '{escaped_value}'")
                                
                                # Records with incomplete combinations can be inserted
                                if not has_all_fields:
                                    validated_insert_batch.append(record)
                                    continue
                                
                                try:
                                    # Check if this combination already exists in Salesforce
                                    where_clause = ' AND '.join(conditions)
                                    check_query = f"SELECT Id FROM {target_object} WHERE {where_clause} LIMIT 1"
                                    check_result = sf_conn.query(check_query)
                                    
                                    if check_result['totalSize'] > 0:
                                        # Duplicate combination found - skip insert
                                        combination_str = ' | '.join([f"{f}={record.get(f)}" for f in upsert_match_fields])
                                        duplicate_inserts.append({
                                            'record': record,
                                            'reason': f"Duplicate combination: {combination_str}"
                                        })
                                    else:
                                        # Safe to insert
                                        validated_insert_batch.append(record)
                                except Exception as e:
                                    st.warning(f"⚠️ Could not verify uniqueness: {str(e)}")
                                    validated_insert_batch.append(record)  # Proceed with insert
                        else:
                            # No validation strategy - insert all
                            validated_insert_batch = insert_batch
                        
                        # Show duplicate warnings
                        if duplicate_inserts:
                            st.warning(f"⚠️ Batch {i + 1}: Skipping {len(duplicate_inserts)} records - already exist in Salesforce")
                            with st.expander("🔍 View Duplicate Records"):
                                for dup in duplicate_inserts[:10]:  # Show first 10
                                    st.write(f"• {dup['reason']}")
                                if len(duplicate_inserts) > 10:
                                    st.write(f"... and {len(duplicate_inserts) - 10} more")
                    
                    # Process inserts with validated batch
                    insert_results = []
                    if validated_insert_batch:
                        st.info(f"🆕 Batch {i + 1}: Inserting {len(validated_insert_batch)} new unique records")
                        try:
                            insert_results = getattr(sf_conn.bulk, target_object).insert(validated_insert_batch)
                        except Exception as e:
                            st.error(f"❌ Error inserting records in batch {i + 1}: {str(e)}")
                            insert_results = []
                    elif insert_batch:
                        st.info(f"ℹ️ Batch {i + 1}: All {len(insert_batch)} insert records were duplicates - skipped")
                    
                    # Combine results for processing
                    result = update_results + insert_results
                    
                    if unprocessable_records:
                        st.warning(f"⚠️ Batch {i + 1}: {len(unprocessable_records)} records could not be processed due to query errors")
                
                # Process each record result with original data
                for j, record_result in enumerate(result):
                    original_record = batch[j]
                    
                    if record_result.get('success', False):
                        success_records.append({
                            'id': record_result.get('id', 'N/A'),
                            'original_data': original_record,
                            'batch_number': i + 1,
                            'operation': operation
                        })
                        success_count += 1
                    else:
                        # Capture error details
                        errors = record_result.get('errors', [])
                        error_messages = []
                        
                        for error in errors:
                            error_msg = f"{error.get('statusCode', 'UNKNOWN_ERROR')}: {error.get('message', 'No error message provided')}"
                            if 'fields' in error and error['fields']:
                                error_msg += f" (Fields: {', '.join(error['fields'])})"
                            error_messages.append(error_msg)
                        
                        failed_records.append({
                            'original_data': original_record,
                            'errors': error_messages,
                            'batch_number': i + 1,
                            'operation': operation,
                            'error_summary': '; '.join(error_messages) if error_messages else 'Unknown error'
                        })
                        error_count += 1
                
                # Update progress
                batch_progress.progress((i + 1) / len(batches))
                
            except Exception as e:
                st.error(f"❌ Error processing batch {i + 1}: {str(e)}")
                # Add all batch records as failed due to batch error
                for record in batch:
                    failed_records.append({
                        'original_data': record,
                        'errors': [f"Batch processing error: {str(e)}"],
                        'batch_number': i + 1,
                        'operation': operation,
                        'error_summary': f"Batch error: {str(e)}"
                    })
                    error_count += 1
        
        batch_status.empty()
        
        with progress_container:
            create_progress_tracker(progress_steps, 4)
        
        # Show comprehensive results
        if error_count == 0:
            st.success(f"🎉 **Data loading completed successfully!** All {total_records} records were {operation.lower()}ed successfully.")
        elif success_count > 0:
            st.warning(f"⚠️ **Data loading completed with some errors.** {success_count} records succeeded, {error_count} records failed.")
        else:
            st.error(f"❌ **Data loading failed.** No records were successfully {operation.lower()}ed.")
        
        # Results summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Records", total_records)
        with col2:
            st.metric("✅ Successful", success_count, delta=f"{(success_count/total_records)*100:.1f}%")
        with col3:
            st.metric("❌ Failed", error_count, delta=f"{(error_count/total_records)*100:.1f}%", delta_color="inverse")
        with col4:
            success_rate = (success_count / total_records) * 100 if total_records > 0 else 0
            st.metric("Success Rate", f"{success_rate:.1f}%")
        
        # Display detailed results
        display_operation_results(success_records, failed_records, operation, target_object)
        
        show_processing_status("sf_load", f"Loaded {success_count}/{total_records} records to {target_object}", 
                             "success" if error_count == 0 else "warning")
        
    except Exception as e:
        st.error(f"❌ Data loading failed: {str(e)}")
        show_processing_status("sf_load", f"Data loading to {target_object} failed: {str(e)}", "error")

# Placeholder functions for bulk operations
def show_multi_object_extraction(sf_conn):
    """Multi-object extraction interface"""
    st.write("🔄 Multi-object extraction feature coming soon...")

def show_batch_data_loading(sf_conn):
    """Batch data loading interface"""
    st.write("🔄 Batch data loading feature coming soon...")

def show_cross_org_migration(credentials: Dict):
    """Cross-org migration interface"""
    st.write("🔄 Cross-org migration feature coming soon...")

def show_bulk_validation(sf_conn):
    """Bulk validation interface"""
    st.write("🔄 Bulk validation feature coming soon...")

def migrate_from_salesforce_to_sql(credentials: Dict, target_db: str):
    """Migrate from Salesforce to SQL"""
    st.write("🔄 Salesforce to SQL migration feature coming soon...")

def migrate_from_file_to_sql(credentials: Dict, target_db: str):
    """Migrate from file to SQL"""
    st.write("🔄 File to SQL migration feature coming soon...")

# ================================
# SQL SERVER HELPER FUNCTIONS
# ================================

def map_pandas_to_sql_type(pandas_dtype: str, column_data) -> str:
    """Map pandas data types to SQL Server data types"""
    dtype_lower = pandas_dtype.lower()
    
    if 'int' in dtype_lower:
        max_val = column_data.max() if not column_data.empty else 0
        if max_val <= 127:
            return "TINYINT"
        elif max_val <= 32767:
            return "SMALLINT"
        elif max_val <= 2147483647:
            return "INT"
        else:
            return "BIGINT"
    
    elif 'float' in dtype_lower or 'double' in dtype_lower:
        return "FLOAT"
    
    elif 'bool' in dtype_lower:
        return "BIT"
    
    elif 'datetime' in dtype_lower or 'timestamp' in dtype_lower:
        return "DATETIME2"
    
    elif 'object' in dtype_lower or 'string' in dtype_lower:
        if not column_data.empty:
            max_length = column_data.astype(str).str.len().max()
            if max_length <= 50:
                return f"VARCHAR({max(max_length * 2, 50)})"
            elif max_length <= 255:
                return f"VARCHAR({max_length * 2})"
            elif max_length <= 4000:
                return f"VARCHAR({max_length})"
            else:
                return "TEXT"
        else:
            return "VARCHAR(255)"
    
    else:
        return "VARCHAR(255)"

def load_data_to_sql_server(db_config: Dict, df: pd.DataFrame, table_name: str, schema_name: str,
                           load_mode: str, batch_size: int, index_columns: list, 
                           nullable_columns: list, include_index: bool, check_constraints: bool):
    """Load data to SQL Server with advanced options"""
    try:
        import pyodbc
        from sqlalchemy import create_engine, text
        import urllib.parse
        
        # Show loading progress
        progress_container = st.container()
        status_container = st.container()
        
        with progress_container:
            progress_bar = st.progress(0)
            status_text = st.empty()
        
        with status_container:
            st.write("#### Loading Progress")
        
        # Step 1: Establish connection
        status_text.text("🔗 Establishing database connection...")
        progress_bar.progress(10)
        
        # Build connection string
        connection_string = f"DRIVER={db_config['driver']};SERVER={db_config['server']};DATABASE={db_config['database']}"
        
        if db_config.get('port') and db_config.get('port') != '1433':
            if '\\' not in db_config['server']:
                connection_string = f"DRIVER={db_config['driver']};SERVER={db_config['server']},{db_config['port']};DATABASE={db_config['database']}"
        
        if db_config.get('Trusted_Connection') == 'yes':
            connection_string += ";Trusted_Connection=yes"
        else:
            connection_string += f";UID={db_config['username']};PWD={db_config['password']}"
        
        if db_config.get('encrypt'):
            connection_string += f";Encrypt={db_config['encrypt']}"
        
        if db_config.get('trust_server_cert'):
            connection_string += ";TrustServerCertificate=yes"
        
        # Create SQLAlchemy engine
        sqlalchemy_conn_str = f"mssql+pyodbc:///?odbc_connect={urllib.parse.quote_plus(connection_string)}"
        engine = create_engine(sqlalchemy_conn_str, echo=False)
        
        # Step 2: Prepare data
        status_text.text("📊 Preparing data for loading...")
        progress_bar.progress(20)
        
        # Clean data
        df_clean = df.copy()
        
        # Handle null values for non-nullable columns
        for col in df_clean.columns:
            if col not in nullable_columns:
                if df_clean[col].dtype == 'object':
                    df_clean[col] = df_clean[col].fillna('')
                elif df_clean[col].dtype in ['int64', 'float64']:
                    df_clean[col] = df_clean[col].fillna(0)
                elif df_clean[col].dtype == 'bool':
                    df_clean[col] = df_clean[col].fillna(False)
        
        # Step 3: Handle existing table
        status_text.text("🔍 Checking table existence...")
        progress_bar.progress(30)
        
        full_table_name = f"[{schema_name}].[{table_name}]"
        
        # Check if table exists
        with engine.connect() as conn:
            result = conn.execute(text(f"""
                SELECT COUNT(*) as table_exists 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_SCHEMA = '{schema_name}' AND TABLE_NAME = '{table_name}'
            """))
            table_exists = result.fetchone()[0] > 0
        
        # Handle load mode
        if_exists_param = 'fail'
        
        if load_mode == "Create New Table":
            if table_exists:
                st.error(f"❌ Table {full_table_name} already exists! Use 'Replace Existing' or 'Append to Existing' mode.")
                return
            if_exists_param = 'fail'
        
        elif load_mode == "Replace Existing":
            if_exists_param = 'replace'
            status_text.text("🗑️ Replacing existing table...")
            progress_bar.progress(40)
        
        elif load_mode == "Append to Existing":
            if not table_exists:
                st.error(f"❌ Table {full_table_name} does not exist! Use 'Create New Table' mode.")
                return
            if_exists_param = 'append'
            status_text.text("➕ Appending to existing table...")
            progress_bar.progress(40)
        
        # Step 4: Load data
        status_text.text(f"📥 Loading {len(df_clean)} records to SQL Server...")
        progress_bar.progress(60)
        
        # Load data to SQL Server
        df_clean.to_sql(
            name=table_name,
            con=engine,
            schema=schema_name,
            if_exists=if_exists_param,
            index=include_index,
            index_label='df_index' if include_index else None,
            chunksize=batch_size,
            method='multi'
        )
        
        # Step 5: Create indexes if specified
        if index_columns and load_mode != "Append to Existing":
            status_text.text("🔧 Creating indexes...")
            progress_bar.progress(80)
            
            with engine.connect() as conn:
                for i, col in enumerate(index_columns):
                    try:
                        index_name = f"IX_{table_name}_{col}"
                        create_index_sql = f"CREATE INDEX [{index_name}] ON {full_table_name} ([{col}])"
                        conn.execute(text(create_index_sql))
                        conn.commit()
                    except Exception as e:
                        st.warning(f"⚠️ Could not create index on column '{col}': {str(e)}")
        
        # Step 6: Final verification
        status_text.text("✅ Verifying data load...")
        progress_bar.progress(90)
        
        # Get final row count
        with engine.connect() as conn:
            result = conn.execute(text(f"SELECT COUNT(*) as row_count FROM {full_table_name}"))
            final_count = result.fetchone()[0]
        
        # Complete
        progress_bar.progress(100)
        status_text.text("🎉 Data loading completed successfully!")
        
        # Show success summary
        st.success(f"✅ **Data loading completed successfully!**")
        
        col_summary1, col_summary2, col_summary3 = st.columns(3)
        
        with col_summary1:
            st.metric("Records Loaded", f"{len(df_clean):,}")
        
        with col_summary2:
            st.metric("Target Table", f"{schema_name}.{table_name}")
        
        with col_summary3:
            st.metric("Final Row Count", f"{final_count:,}")
        
        # Show additional details
        with st.expander("📊 Loading Details", expanded=False):
            st.write(f"**Source:** {len(df_clean)} rows, {len(df_clean.columns)} columns")
            st.write(f"**Target:** {db_config.get('server', 'Unknown')} - {db_config.get('database', 'Unknown')}")
            st.write(f"**Load Mode:** {load_mode}")
            st.write(f"**Batch Size:** {batch_size:,} records")
            if index_columns:
                st.write(f"**Indexes Created:** {', '.join(index_columns)}")
        
        show_processing_status("sql_data_load", f"Successfully loaded {len(df_clean)} records to {table_name}", "success")
        
        # Clean up
        engine.dispose()
        
    except ImportError as e:
        st.error("❌ **Missing required modules**")
        st.code("pip install pyodbc sqlalchemy", language="bash")
        
    except Exception as e:
        st.error(f"❌ **Data loading failed**")
        st.warning(f"**Error:** {str(e)}")
        
        # Show troubleshooting tips
        with st.expander("🔧 Troubleshooting Tips", expanded=True):
            st.markdown("""
            **Common Solutions:**
            
            1. **Permission Issues:**
               - Ensure database user has CREATE TABLE permissions
               - Check if schema exists and is accessible
               - Verify database write permissions
            
            2. **Data Type Issues:**
               - Check column data types and lengths
               - Look for invalid characters or formats
               - Consider data cleaning before loading
            
            3. **Connection Issues:**
               - Verify database connection in Configuration
               - Check network connectivity
               - Ensure database is online and accessible
            
            4. **Table Issues:**
               - Verify schema name is correct
               - Check if table name conflicts with existing objects
               - Ensure table structure matches data
            """)
        
        show_processing_status("sql_data_load", f"Failed to load data: {str(e)}", "error")

# ================================
# NEW FUNCTIONS FOR ENHANCED DATA LOADING
# ================================

def resolve_lookup_fields(sf_conn, df: pd.DataFrame, target_object: str, return_stats: bool = False) -> pd.DataFrame:
    """Resolve lookup field values to Salesforce record IDs and validate picklist API names
    
    Args:
        sf_conn: Salesforce connection
        df: DataFrame to process
        target_object: Salesforce object name
        return_stats: If True, returns (df, lookup_fields, lookup_counts) tuple
        
    Returns:
        DataFrame or tuple based on return_stats parameter
    """
    df_resolved = df.copy()
    lookup_count_summary = {}
    
    try:
        # Get object metadata to identify lookup and picklist fields
        object_desc = getattr(sf_conn, target_object).describe()
        lookup_fields = {}
        picklist_fields = {}
        
        # Find lookup and picklist fields in the data
        for field in object_desc['fields']:
            field_name = field['name']
            
            if field_name in df.columns:
                if field['type'] == 'reference':
                    # This is a lookup field in our data
                    referenced_objects = field.get('referenceTo', [])
                    if referenced_objects:
                        lookup_fields[field_name] = {
                            'referenced_object': referenced_objects[0],  # Take first referenced object
                            'label': field.get('label', field_name)
                        }
                
                elif field['type'] in ['picklist', 'multipicklist']:
                    # This is a picklist field in our data
                    picklist_values = field.get('picklistValues', [])
                    if picklist_values:
                        api_names = {}
                        labels = {}
                        for pv in picklist_values:
                            if not pv.get('inactive', False):
                                api_name = pv.get('valueName', pv.get('value', ''))
                                label = pv.get('label', pv.get('value', ''))
                                api_names[api_name] = label
                                labels[label] = api_name
                        
                        picklist_fields[field_name] = {
                            'api_names': api_names,  # API name -> Label mapping
                            'labels': labels,        # Label -> API name mapping
                            'type': field['type']
                        }
        
        # Process picklist fields first - validate API names
        if picklist_fields:
            st.info(f"🎯 Found {len(picklist_fields)} picklist field(s) to validate: {', '.join(picklist_fields.keys())}")
            
            for field_name, field_info in picklist_fields.items():
                st.info(f"🔍 Validating picklist API names for {field_name}")
                
                # Get unique values from the data (should be API names)
                unique_values = df_resolved[field_name].dropna().unique()
                valid_api_names = list(field_info['api_names'].keys())
                
                invalid_values = []
                valid_count = 0
                
                for value in unique_values:
                    if pd.isna(value) or str(value).strip() == '':
                        continue
                        
                    str_value = str(value).strip()
                    
                    # Check if the value is a valid API name
                    if str_value in valid_api_names:
                        valid_count += 1
                        # API name is valid - it will be sent as-is to Salesforce
                        st.success(f"   ✅ '{str_value}' is valid API name")
                    else:
                        # Invalid API name
                        invalid_values.append(str_value)
                        st.error(f"   ❌ '{str_value}' is NOT a valid API name")
                
                if invalid_values:
                    st.error(f"🚫 **INVALID PICKLIST API NAMES FOUND**")
                    st.error(f"**Field:** {field_name}")
                    st.error(f"**Invalid values:** {', '.join(invalid_values)}")
                    st.error(f"**Valid API names:** {', '.join(valid_api_names)}")
                    
                    with st.expander(f"🔧 Fix Picklist Values for {field_name}"):
                        st.write("**Your file contains invalid picklist API names.**")
                        st.write("")
                        st.write("**📝 Requirements:**")
                        st.write(f"• File should contain API names (not labels)")
                        st.write(f"• Valid API names for {field_name}: {', '.join(valid_api_names)}")
                        st.write("")
                        st.write("**✅ Solution:**")
                        st.write("1. **Update your data file** to use valid API names")
                        st.write("2. **Replace invalid values** with correct API names")
                        st.write("3. **Re-upload the corrected file**")
                        
                        st.info("💡 **Note:** API names are used for data loading, but Salesforce UI will display the corresponding labels")
                    
                    return None  # Block upload due to invalid picklist values
                
                else:
                    st.success(f"✅ All {valid_count} picklist values are valid API names for {field_name}")
        
        # Process lookup fields (existing logic)
        if not lookup_fields:
            if not picklist_fields:
                st.info("📝 No lookup or picklist fields detected in your data.")
            return df_resolved
        
        st.info(f"🔍 Found {len(lookup_fields)} lookup field(s) to resolve: {', '.join(lookup_fields.keys())}")
        
        # Resolve each lookup field
        for field_name, field_info in lookup_fields.items():
            referenced_object = field_info['referenced_object']
            
            st.info(f"🔄 Resolving {field_name} → {referenced_object}")
            
            # SMART VALIDATION: Check if parent object has ANY data
            try:
                # Fixed: Remove LIMIT from COUNT query (Salesforce doesn't allow LIMIT with aggregates)
                parent_count_query = f"SELECT COUNT(Id) FROM {referenced_object}"
                parent_count_result = sf_conn.query(parent_count_query)
                parent_record_count = parent_count_result['totalSize']
                
                if parent_record_count == 0:
                    # Parent object is completely empty - this is the error condition
                    st.error(f"❌ **PARENT OBJECT IS EMPTY**")
                    st.error(f"**Child Object:** {target_object}")
                    st.error(f"**Parent Object:** {referenced_object}")
                    st.error(f"**Lookup Field:** {field_name}")
                    
                    with st.expander(f"🚨 No Data in Parent Object: {referenced_object}"):
                        child_record_count = len(df_resolved[df_resolved[field_name].notna()])
                        st.write(f"**Problem:** {referenced_object} object has no records")
                        st.write(f"**Impact:** Cannot upload {child_record_count} child records with lookup relationships")
                        st.write(f"**Child records need:** Valid parent records to reference")
                        
                        st.error("**🚫 Data Integrity Issue:**")
                        st.write("• Child records cannot exist without parent records")
                        st.write(f"• {referenced_object} object must have data before child uploads")
                        st.write("• Lookup relationships would be invalid")
                        
                        st.info("**✅ Solution:**")
                        st.write(f"1. **Add data to {referenced_object} object first**")
                        st.write(f"   - Create at least one {referenced_object} record in Salesforce")
                        st.write(f"   - Ensure parent records exist before uploading child data")
                        st.write(f"2. **Verify parent object setup**")
                        st.write(f"   - Check if {referenced_object} object is properly configured")
                        st.write(f"   - Confirm object permissions and access")
                        st.write(f"3. **Upload in correct sequence**")
                        st.write(f"   - First: Upload {referenced_object} records")
                        st.write(f"   - Then: Upload {target_object} records")
                    
                    st.error(f"🚫 **CANNOT UPLOAD CHILD RECORDS**")
                    st.error(f"The {referenced_object} object is empty. Child records need parent records to reference.")
                    return None  # Block the upload
                
                else:
                    # Parent object has data - proceed with normal lookup resolution
                    st.success(f"✅ Parent object {referenced_object} has {parent_record_count} record(s) - proceeding with lookup resolution")
                    
            except Exception as e:
                st.warning(f"⚠️ Could not verify parent object data: {str(e)}")
                # Continue with normal processing if we can't check parent count
            
            # Get unique values to resolve
            unique_values = df_resolved[field_name].dropna().unique()
            
            if len(unique_values) == 0:
                continue
                
            # Create lookup mapping
            lookup_mapping = {}
            unresolved_values = []
            
            for value in unique_values:
                if pd.isna(value) or str(value).strip() == '':
                    continue
                    
                escaped_value = str(value).replace("'", "\\'")
                
                # Try multiple fields that might contain the lookup value
                possible_fields = ['Name', 'Code__c', 'External_Id__c', 'Code', 'Number__c']
                record_found = False
                
                for lookup_field in possible_fields:
                    try:
                        # Query the referenced object - CHECK FOR DUPLICATES
                        soql = f"SELECT Id, Name FROM {referenced_object} WHERE {lookup_field} = '{escaped_value}'"
                        result = sf_conn.query(soql)
                        
                        if result['totalSize'] > 0:
                            # Check for duplicate parent records
                            if result['totalSize'] > 1:
                                # Multiple records found - let user choose
                                duplicate_records = result['records']
                                
                                st.warning(f"⚠️ **MULTIPLE PARENT RECORDS FOUND**")
                                st.info(f"**Field:** {field_name}")
                                st.info(f"**Value:** '{value}'")
                                st.info(f"**Parent Object:** {referenced_object}")
                                st.info(f"**Found {result['totalSize']} records with the same {lookup_field}**")
                                
                                # Create user selection interface
                                st.write(f"**Please select which parent record to use for '{value}':**")
                                
                                # Create selection options
                                selection_options = []
                                option_labels = []
                                
                                for i, record in enumerate(duplicate_records):
                                    record_id = record['Id']
                                    record_name = record.get('Name', 'Unknown')
                                    option_label = f"{record_name} (ID: {record_id})"
                                    selection_options.append(record_id)
                                    option_labels.append(option_label)
                                
                                # Use session state key for this specific lookup value
                                session_key = f"duplicate_selection_{field_name}_{value}_{hash(str(duplicate_records))}"
                                
                                selected_option = st.selectbox(
                                    f"Choose parent record for '{value}':",
                                    options=selection_options,
                                    format_func=lambda x: next(label for i, label in enumerate(option_labels) if selection_options[i] == x),
                                    key=session_key,
                                    help=f"Select which {referenced_object} record should be the parent for child records with {field_name} = '{value}'"
                                )
                                
                                if selected_option:
                                    # User has made a selection
                                    selected_record = next(rec for rec in duplicate_records if rec['Id'] == selected_option)
                                    selected_name = selected_record.get('Name', str(value))
                                    
                                    lookup_mapping[value] = selected_option
                                    record_found = True
                                    
                                    st.success(f"✅ Selected '{value}' → {selected_name} ({selected_option})")
                                    
                                    # Show impact information
                                    affected_records = df_resolved[df_resolved[field_name] == value].shape[0]
                                    st.info(f"📊 This selection will affect {affected_records} child record(s)")
                                    
                                    break
                                else:
                                    # No selection made yet - add to pending
                                    st.warning(f"⏳ Please select a parent record for '{value}' to continue")
                                    unresolved_values.append(f"{value} (PENDING USER SELECTION)")
                                    record_found = False
                                    break
                            else:
                                # Single record found - this is correct
                                record_id = result['records'][0]['Id']
                                record_name = result['records'][0].get('Name', str(value))
                                lookup_mapping[value] = record_id
                                record_found = True
                                st.success(f"✅ Resolved '{value}' → {record_name} ({record_id})")
                                break
                    except Exception as e:
                        # Try next field
                        continue
                
                if not record_found:
                    # Check if this is because parent record doesn't exist at all
                    unresolved_values.append(f"{value} (MISSING PARENT RECORD)")
            
            # Apply the mapping
            if lookup_mapping:
                df_resolved[field_name] = df_resolved[field_name].map(lookup_mapping).fillna(df_resolved[field_name])
                resolved_count = sum(1 for v in df_resolved[field_name] if v in lookup_mapping.values())
                st.success(f"📊 Resolved {len(lookup_mapping)} values for {field_name} (affecting {resolved_count} records)")
                
                # Track lookup counts for enhanced validation
                lookup_count_summary[field_name] = len(lookup_mapping)
            
            # Report unresolved values
            if unresolved_values:
                # Categorize different types of resolution failures
                pending_selections = [v for v in unresolved_values if "PENDING USER SELECTION" in str(v)]
                missing_individual_records = [v for v in unresolved_values if "MISSING PARENT RECORD" in str(v)]
                other_errors = [v for v in unresolved_values if "PENDING USER SELECTION" not in str(v) and "MISSING PARENT RECORD" not in str(v)]
                
                if missing_individual_records:
                    st.warning(f"⚠️ **Some Parent Records Not Found**")
                    st.warning(f"**Field:** {field_name}")
                    st.warning(f"**Parent Object:** {referenced_object} (has data, but missing specific records)")
                    
                    # Show detailed missing individual record information
                    with st.expander(f"🔍 Missing Individual Parent Records"):
                        st.write("**These specific parent records were not found:**")
                        missing_values = [v.split(" (MISSING")[0] for v in missing_individual_records]
                        for i, val in enumerate(missing_values, 1):
                            affected_count = df_resolved[df_resolved[field_name] == val].shape[0]
                            st.write(f"{i}. **'{val}'** - affects {affected_count} child record(s)")
                        
                        st.info("**📝 Note:** Parent object has data, but these specific records don't exist")
                        st.write("**Options:**")
                        st.write(f"1. Create these missing {referenced_object} records")
                        st.write("2. Update child data to reference existing parent records")
                        st.write("3. Check spelling/format of parent record names")
                        st.write("4. Use existing Salesforce record IDs instead")
                    
                    # Calculate total impact
                    total_affected = 0
                    for val in missing_values:
                        count = df_resolved[df_resolved[field_name] == val].shape[0]
                        total_affected += count
                    
                    st.warning(f"📊 **Child records with missing parent references: {total_affected}**")
                    st.info("💡 **These can be fixed by creating the missing parent records or updating references**")
                
                if pending_selections:
                    st.warning(f"⏳ **PENDING USER SELECTIONS**")
                    st.warning(f"**Field:** {field_name}")
                    st.warning(f"**Values requiring selection:** {len(pending_selections)}")
                    st.info("📋 **Please make selections above to continue with data loading**")
                    st.info("Once all parent records are selected, the system will proceed with loading.")
                    
                    # Show affected child records count
                    pending_values = [v.split(" (PENDING")[0] for v in pending_selections]
                    total_affected = 0
                    for val in pending_values:
                        count = df_resolved[df_resolved[field_name] == val].shape[0]
                        total_affected += count
                        st.write(f"  • '{val}': {count} child record(s) waiting")
                    
                    st.info(f"📊 **Total child records waiting for parent selection: {total_affected}**")
                
                if other_errors:
                    st.warning(f"⚠️ Could not resolve {len(other_errors)} values for {field_name}: {other_errors[:5]}{'...' if len(other_errors) > 5 else ''}")
                    
                    with st.expander(f"🔍 Troubleshooting {field_name} resolution"):
                        st.write(f"**Referenced Object:** {referenced_object}")
                        st.write(f"**Unresolved Values:** {other_errors}")
                        st.write("**Possible solutions:**")
                        st.write("1. Ensure the values exist in the referenced object")
                        st.write("2. Check if the lookup field uses a different field (not Name/Code)")
                        st.write("3. Verify spelling and exact match")
                        st.write("4. Consider using the actual Salesforce record IDs instead")
                
                # Only block loading for pending selections (user needs to choose)
                # Allow loading even with missing individual records (with warnings)
                if pending_selections:
                    st.info("🔄 **Ready to proceed once all parent selections are made**")
                    st.info("The system will wait for your selections before continuing with data loading.")
                    if return_stats:
                        return None, lookup_fields, lookup_count_summary
                    return None  # Return None to indicate selections needed
        
        if return_stats:
            return df_resolved, lookup_fields, lookup_count_summary
        return df_resolved
        
    except Exception as e:
        st.error(f"❌ Error resolving lookup fields: {str(e)}")
        if return_stats:
            return df, {}, {}
        return df


def clean_dataframe_for_salesforce(df: pd.DataFrame) -> pd.DataFrame:
    """Clean DataFrame to make it compatible with Salesforce API (fixes NaN JSON error)"""
    df_cleaned = df.copy()
    
    # Replace NaN values with appropriate defaults
    for col in df_cleaned.columns:
        if df_cleaned[col].dtype in ['float64', 'float32']:
            # For numeric columns, replace NaN with None (becomes null in JSON)
            df_cleaned[col] = df_cleaned[col].where(pd.notna(df_cleaned[col]), None)
        elif df_cleaned[col].dtype == 'object':
            # For text columns, replace NaN with empty string or None
            df_cleaned[col] = df_cleaned[col].where(pd.notna(df_cleaned[col]), None)
        elif df_cleaned[col].dtype in ['datetime64[ns]', 'datetime64[ns, UTC]']:
            # For datetime columns, replace NaN with None
            df_cleaned[col] = df_cleaned[col].where(pd.notna(df_cleaned[col]), None)
    
    # Convert datetime columns to string format for Salesforce
    datetime_cols = df_cleaned.select_dtypes(include=['datetime64[ns]', 'datetime64[ns, UTC]']).columns
    for col in datetime_cols:
        df_cleaned[col] = df_cleaned[col].dt.strftime('%Y-%m-%d %H:%M:%S').where(pd.notna(df_cleaned[col]), None)
    
    return df_cleaned

def analyze_data_quality(df: pd.DataFrame) -> list:
    """Analyze data quality and return list of issues"""
    issues = []
    
    # Check for high null percentage
    for col in df.columns:
        null_percentage = (df[col].isnull().sum() / len(df)) * 100
        if null_percentage > 50:
            issues.append(f"Column '{col}' has {null_percentage:.1f}% null values")
    
    # Check for duplicate rows
    duplicate_count = df.duplicated().sum()
    if duplicate_count > 0:
        issues.append(f"{duplicate_count} duplicate rows found")
    
    # Check for very long text values (Salesforce limits)
    text_cols = df.select_dtypes(include=['object']).columns
    for col in text_cols:
        max_length = df[col].astype(str).str.len().max()
        if max_length > 255:
            issues.append(f"Column '{col}' has values longer than 255 characters (max: {max_length})")
    
    # Check for potential data type issues
    for col in df.columns:
        if df[col].dtype == 'object':
            # Check if numeric-looking data is stored as text
            try:
                pd.to_numeric(df[col].dropna())
                issues.append(f"Column '{col}' contains numeric data stored as text")
            except:
                pass
    
    return issues

def find_suggested_mapping(csv_column: str, sf_fields: list) -> str:
    """Find suggested Salesforce field mapping based on column name"""
    csv_lower = csv_column.lower().replace('_', '').replace(' ', '')
    
    # Common mappings
    common_mappings = {
        'id': 'Id',
        'name': 'Name', 
        'accountname': 'Name',
        'companyname': 'Name',
        'email': 'Email',
        'phone': 'Phone',
        'website': 'Website',
        'description': 'Description',
        'type': 'Type',
        'industry': 'Industry',
        'billingstreet': 'BillingStreet',
        'billingcity': 'BillingCity',
        'billingstate': 'BillingState',
        'billingcountry': 'BillingCountry',
        'billingpostalcode': 'BillingPostalCode'
    }
    
    # Check exact matches first
    if csv_lower in common_mappings and common_mappings[csv_lower] in sf_fields:
        return common_mappings[csv_lower]
    
    # Check partial matches
    for sf_field in sf_fields:
        if csv_lower in sf_field.lower() or sf_field.lower() in csv_lower:
            return sf_field
    
    return "-- Skip Field --"

def apply_field_mappings(df: pd.DataFrame, field_mappings: dict) -> pd.DataFrame:
    """Apply field mappings to transform DataFrame"""
    transformed_df = pd.DataFrame()
    
    for csv_col, sf_field in field_mappings.items():
        if sf_field and sf_field != "-- Skip Field --":
            transformed_df[sf_field] = df[csv_col]
    
    return transformed_df

def detect_salesforce_data_type(series: pd.Series) -> str:
    """Detect appropriate Salesforce data type for a pandas Series"""
    # Remove null values for analysis
    clean_series = series.dropna()
    
    if clean_series.empty:
        return "Text"
    
    # Check if all values are numeric
    try:
        numeric_series = pd.to_numeric(clean_series, errors='coerce')
        if not numeric_series.isna().any():
            # Check if integers
            if all(float(x).is_integer() for x in clean_series if pd.notna(x)):
                return "Number (Integer)"
            else:
                return "Number (Decimal)"
    except:
        pass
    
    # Check for boolean values
    unique_values = set(str(v).lower() for v in clean_series.unique())
    if unique_values.issubset({'true', 'false', '1', '0', 'yes', 'no'}):
        return "Checkbox (Boolean)"
    
    # Check for date/datetime patterns
    try:
        pd.to_datetime(clean_series, errors='raise')
        return "Date/DateTime"
    except:
        pass
    
    # Check for email pattern
    if clean_series.astype(str).str.contains('@.*\\.', na=False).any():
        return "Email"
    
    # Check for phone pattern
    if clean_series.astype(str).str.contains(r'[\d\-\(\)\+\s]{10,}', na=False).any():
        return "Phone"
    
    # Check for URL pattern
    if clean_series.astype(str).str.contains(r'https?://', na=False).any():
        return "URL"
    
    # Check text length for appropriate text type
    max_length = clean_series.astype(str).str.len().max()
    if max_length <= 80:
        return "Text (Short)"
    elif max_length <= 255:
        return "Text (Medium)"
    elif max_length <= 32000:
        return "Text (Long)"
    else:
        return "Text Area (Rich)"

def auto_detect_field_mappings(csv_columns: list, sf_fields: list, sf_field_info: dict, df: pd.DataFrame) -> dict:
    """Auto-detect field mappings using intelligent matching"""
    mappings = {}
    
    for csv_col in csv_columns:
        best_match = find_best_field_match(csv_col, sf_fields, sf_field_info, df[csv_col])
        mappings[csv_col] = best_match
    
    return mappings

def find_best_field_match(csv_column: str, sf_fields: list, sf_field_info: dict, series: pd.Series) -> str:
    """Find the best Salesforce field match for a CSV column"""
    csv_lower = csv_column.lower().replace('_', '').replace(' ', '').replace('-', '')
    detected_type = detect_salesforce_data_type(series)
    
    # Priority matching rules
    matches = []
    
    # Exact name matches (highest priority)
    for sf_field in sf_fields:
        sf_lower = sf_field.lower().replace('_', '').replace(' ', '').replace('-', '')
        if csv_lower == sf_lower:
            matches.append((sf_field, 100))
    
    # Common field mappings
    common_mappings = {
        'id': ['Id', 'External_Id__c'],
        'name': ['Name', 'Account_Name__c', 'Full_Name__c'],
        'accountname': ['Name'],
        'companyname': ['Name'],
        'email': ['Email', 'Email__c', 'PersonEmail'],
        'phone': ['Phone', 'Phone__c', 'MobilePhone'],
        'website': ['Website', 'Website__c'],
        'description': ['Description', 'Description__c'],
        'type': ['Type', 'Type__c'],
        'industry': ['Industry', 'Industry__c'],
        'billingstreet': ['BillingStreet'],
        'billingcity': ['BillingCity'],
        'billingstate': ['BillingState'],
        'billingcountry': ['BillingCountry'],
        'billingpostalcode': ['BillingPostalCode'],
        'shippingstreet': ['ShippingStreet'],
        'shippingcity': ['ShippingCity'],
        'shippingstate': ['ShippingState'],
        'shippingcountry': ['ShippingCountry'],
        'shippingpostalcode': ['ShippingPostalCode']
    }
    
    if csv_lower in common_mappings:
        for sf_field in common_mappings[csv_lower]:
            if sf_field in sf_fields:
                matches.append((sf_field, 90))
    
    # Partial name matches
    for sf_field in sf_fields:
        sf_lower = sf_field.lower()
        if csv_lower in sf_lower or sf_lower.replace('__c', '') in csv_lower:
            matches.append((sf_field, 70))
    
    # Type-based matching
    for sf_field in sf_fields:
        sf_info = sf_field_info.get(sf_field, {})
        sf_type = sf_info.get('type', '').lower()
        
        # Match by data type
        if detected_type.startswith("Number") and sf_type in ['double', 'currency', 'percent', 'int']:
            matches.append((sf_field, 50))
        elif detected_type == "Checkbox (Boolean)" and sf_type == 'boolean':
            matches.append((sf_field, 60))
        elif detected_type.startswith("Date") and sf_type in ['date', 'datetime']:
            matches.append((sf_field, 60))
        elif detected_type == "Email" and sf_type == 'email':
            matches.append((sf_field, 80))
        elif detected_type == "Phone" and sf_type == 'phone':
            matches.append((sf_field, 80))
        elif detected_type == "URL" and sf_type == 'url':
            matches.append((sf_field, 80))
    
    # Return best match or skip if no good match
    if matches:
        best_match = max(matches, key=lambda x: x[1])
        if best_match[1] >= 50:  # Minimum confidence threshold
            return best_match[0]
    
    return "-- Skip Field --"

def display_mapping_results(field_mappings: dict, df: pd.DataFrame, sf_field_info: dict):
    """Display auto-detected mapping results in a nice format"""
    mapping_results = []
    
    for csv_col, sf_field in field_mappings.items():
        if sf_field != "-- Skip Field --":
            sf_info = sf_field_info.get(sf_field, {})
            detected_type = detect_salesforce_data_type(df[csv_col])
            
            result = {
                'CSV Column': csv_col,
                'Mapped to SF Field': sf_field,
                'SF Field Type': sf_info.get('type', 'Unknown'),
                'Detected Data Type': detected_type,
                'Sample Data': ', '.join([str(v) for v in df[csv_col].dropna().head(2).tolist()]),
                'Status': '✅ Mapped' if sf_field != "-- Skip Field --" else '⏭️ Skipped'
            }
        else:
            result = {
                'CSV Column': csv_col,
                'Mapped to SF Field': 'Skipped',
                'SF Field Type': 'N/A',
                'Detected Data Type': detect_salesforce_data_type(df[csv_col]),
                'Sample Data': ', '.join([str(v) for v in df[csv_col].dropna().head(2).tolist()]),
                'Status': '⏭️ Skipped'
            }
        mapping_results.append(result)
    
    st.dataframe(pd.DataFrame(mapping_results), use_container_width=True)

def create_standard_mapping_interface(csv_columns: list, sf_fields: list, sf_field_info: dict) -> dict:
    """Create standard mapping interface with common patterns"""
    st.write("**📋 Standard Field Mapping:**")
    st.info("Using common field naming patterns for automatic mapping suggestions")
    
    field_mappings = {}
    sf_field_options = ["-- Skip Field --"] + sf_fields
    
    # Create mapping interface with smart defaults
    for csv_col in csv_columns:
        col1, col2, col3 = st.columns([2, 3, 2])
        
        with col1:
            st.write(f"**{csv_col}**")
        
        with col2:
            # Find suggested mapping using standard patterns
            suggested_field = find_suggested_mapping(csv_col, sf_fields)
            default_index = 0
            
            if suggested_field in sf_field_options:
                default_index = sf_field_options.index(suggested_field)
            
            mapped_field = st.selectbox(
                f"Map to:",
                options=sf_field_options,
                index=default_index,
                key=f"std_mapping_{csv_col}",
                label_visibility="collapsed"
            )
            field_mappings[csv_col] = mapped_field
        
        with col3:
            if mapped_field != "-- Skip Field --":
                sf_info = sf_field_info.get(mapped_field, {})
                st.caption(f"Type: {sf_info.get('type', 'Unknown')}")
    
    return field_mappings

def create_custom_mapping_interface(csv_columns: list, sf_fields: list, sf_field_info: dict, existing_mappings: dict = None, sample_data: pd.DataFrame = None) -> dict:
    """Create custom mapping interface with full control"""
    st.markdown("## 🔗 CSV Column to Salesforce Field Mapping")
    st.info("📋 Map your CSV columns to Salesforce Object fields for accurate data loading")
    
    if existing_mappings is None:
        existing_mappings = {}
    
    field_mappings = {}
    
    # Create Salesforce field options with labels
    sf_field_options = ["⚠️ No mapping"] + [f"{field_name} ({sf_field_info.get(field_name, {}).get('label', field_name)})" for field_name in sf_fields]
    sf_field_names = [""] + sf_fields
    
    st.markdown("**🎯 Column Mapping Configuration:**")
    
    # Create mapping table headers
    col1, col2, col3 = st.columns([2, 3, 2])
    
    with col1:
        st.markdown("**CSV Column**")
    with col2:
        st.markdown("**Maps to Salesforce Field**")
    with col3:
        st.markdown("**Sample Data**")
    
    st.divider()
    
    # Create detailed mapping interface for each column
    for i, csv_col in enumerate(csv_columns):
        col1, col2, col3 = st.columns([2, 3, 2])
        
        with col1:
            st.write(f"**{csv_col}**")
        
        with col2:
            # Get existing mapping or suggest new one
            current_mapping = existing_mappings.get(csv_col, "")
            
            # Auto-suggest mapping if no existing mapping
            if not current_mapping:
                current_mapping = find_suggested_mapping(csv_col, sf_fields)
            
            # Find index for current mapping
            current_index = 0
            if current_mapping and current_mapping in sf_field_names:
                current_index = sf_field_names.index(current_mapping)
            
            selected_mapping = st.selectbox(
                f"Field mapping for {csv_col}",
                options=sf_field_options,
                index=current_index,
                key=f"custom_mapping_{i}_{csv_col}",
                label_visibility="collapsed"
            )
            
            # Store the mapping
            if selected_mapping != "⚠️ No mapping":
                field_name = selected_mapping.split(" (")[0]
                field_mappings[csv_col] = field_name
            else:
                field_mappings[csv_col] = "-- Skip Field --"
        
        with col3:
            # Show sample data if available
            if sample_data is not None and csv_col in sample_data.columns:
                try:
                    # Get first non-null value as sample
                    sample_series = sample_data[csv_col].dropna()
                    if not sample_series.empty:
                        sample_value = str(sample_series.iloc[0])
                        # Truncate long values
                        if len(sample_value) > 20:
                            sample_value = sample_value[:20] + "..."
                        st.write(f"`{sample_value}`")
                    else:
                        st.caption("No data")
                except Exception:
                    st.caption("No data")
            else:
                st.caption("No sample data")
    
    return field_mappings

def display_operation_results(success_records: list, failed_records: list, operation: str, target_object: str):
    """Display detailed results of the Salesforce operation"""
    
    st.write("---")
    st.write("### 📊 Detailed Operation Results")
    
    # Create tabs for success and failure details
    if success_records and failed_records:
        tab1, tab2, tab3 = st.tabs(["✅ Successful Records", "❌ Failed Records", "📋 Summary Report"])
    elif success_records:
        tab1, tab3 = st.tabs(["✅ Successful Records", "📋 Summary Report"])
        tab2 = None
    elif failed_records:
        tab2, tab3 = st.tabs(["❌ Failed Records", "📋 Summary Report"])
        tab1 = None
    else:
        st.warning("No operation results to display.")
        return
    
    # Successful records tab
    if success_records and 'tab1' in locals():
        with tab1:
            st.write(f"**{len(success_records)} records successfully {operation.lower()}ed:**")
            
            # Create DataFrame for successful records
            success_data = []
            for i, record in enumerate(success_records[:100]):  # Limit to first 100 for display
                row = {
                    'Record #': i + 1,
                    'Salesforce ID': record['id'],
                    'Batch': record['batch_number'],
                    'Operation': record['operation']
                }
                
                # Add first few fields from original data for reference
                original_data = record['original_data']
                field_count = 0
                for key, value in original_data.items():
                    if field_count < 3:  # Show first 3 fields
                        row[f'{key}'] = str(value)[:50] + ('...' if len(str(value)) > 50 else '')
                        field_count += 1
                
                success_data.append(row)
            
            if success_data:
                success_df = pd.DataFrame(success_data)
                st.dataframe(success_df, use_container_width=True, hide_index=True)
                
                if len(success_records) > 100:
                    st.info(f"Showing first 100 successful records. Total successful: {len(success_records)}")
                
                # Download option for successful records
                if st.button("📥 Download Successful Records", key="download_success"):
                    download_success_records(success_records, operation, target_object)
    
    # Failed records tab
    if failed_records and 'tab2' in locals():
        with tab2:
            st.write(f"**{len(failed_records)} records failed to {operation.lower()}:**")
            
            # Group failures by error type
            error_groups = {}
            for record in failed_records:
                error_summary = record['error_summary']
                if error_summary not in error_groups:
                    error_groups[error_summary] = []
                error_groups[error_summary].append(record)
            
            # Show error summary
            st.write("**Error Summary:**")
            for error_type, records in error_groups.items():
                st.error(f"**{error_type}** - {len(records)} record(s)")
            
            st.write("---")
            
            # Create DataFrame for failed records
            failed_data = []
            for i, record in enumerate(failed_records[:100]):  # Limit to first 100 for display
                row = {
                    'Record #': i + 1,
                    'Batch': record['batch_number'],
                    'Error Summary': record['error_summary'][:100] + ('...' if len(record['error_summary']) > 100 else ''),
                    'Full Error Details': ' | '.join(record['errors'])
                }
                
                # Add first few fields from original data for reference
                original_data = record['original_data']
                field_count = 0
                for key, value in original_data.items():
                    if field_count < 2:  # Show first 2 fields for failed records
                        row[f'{key}'] = str(value)[:30] + ('...' if len(str(value)) > 30 else '')
                        field_count += 1
                
                failed_data.append(row)
            
            if failed_data:
                failed_df = pd.DataFrame(failed_data)
                st.dataframe(failed_df, use_container_width=True, hide_index=True)
                
                if len(failed_records) > 100:
                    st.info(f"Showing first 100 failed records. Total failed: {len(failed_records)}")
                
                # Download option for failed records
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("📥 Download Failed Records", key="download_failed"):
                        download_failed_records(failed_records, operation, target_object)
                
                with col2:
                    if st.button("🔄 Generate Retry File", key="generate_retry"):
                        generate_retry_file(failed_records, target_object)
    
    # Summary report tab
    if 'tab3' in locals():
        with tab3:
            st.write("**📋 Complete Operation Summary:**")
            
            # Operation summary
            total_records = len(success_records) + len(failed_records)
            success_rate = (len(success_records) / total_records * 100) if total_records > 0 else 0
            
            summary_data = {
                'Metric': [
                    'Total Records Processed',
                    'Successful Operations',
                    'Failed Operations', 
                    'Success Rate',
                    'Operation Type',
                    'Target Object',
                    'Processing Time'
                ],
                'Value': [
                    total_records,
                    len(success_records),
                    len(failed_records),
                    f"{success_rate:.2f}%",
                    operation.title(),
                    target_object,
                    'Completed'
                ]
            }
            
            summary_df = pd.DataFrame(summary_data)
            st.dataframe(summary_df, use_container_width=True, hide_index=True)
            
            # Error breakdown if there are failures
            if failed_records:
                st.write("**Error Breakdown:**")
                error_summary = {}
                for record in failed_records:
                    error_type = record['error_summary'].split(':')[0] if ':' in record['error_summary'] else record['error_summary']
                    error_summary[error_type] = error_summary.get(error_type, 0) + 1
                
                error_df = pd.DataFrame(list(error_summary.items()), columns=['Error Type', 'Count'])
                error_df = error_df.sort_values('Count', ascending=False)
                st.dataframe(error_df, use_container_width=True, hide_index=True)
            
            # Recommendations
            st.write("**💡 Recommendations:**")
            if len(failed_records) == 0:
                st.success("✅ Perfect! All records were processed successfully.")
            elif success_rate >= 90:
                st.info("✨ Great success rate! Review the few failed records and retry if needed.")
            elif success_rate >= 70:
                st.warning("⚠️ Good success rate but some issues found. Review error patterns and data quality.")
            else:
                st.error("🔍 Many records failed. Review data format, field mappings, and validation rules.")

def download_success_records(success_records: list, operation: str, target_object: str):
    """Create download for successful records"""
    try:
        # Create DataFrame with successful records and their Salesforce IDs
        download_data = []
        for record in success_records:
            row = record['original_data'].copy()
            row['Salesforce_ID'] = record['id']
            row['Operation'] = record['operation']
            row['Batch_Number'] = record['batch_number']
            download_data.append(row)
        
        if download_data:
            df = pd.DataFrame(download_data)
            csv = df.to_csv(index=False)
            
            st.download_button(
                label="📥 Download Successful Records CSV",
                data=csv,
                file_name=f"{target_object}_successful_{operation}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="download_success_csv"
            )
            st.success("✅ Successful records file prepared for download!")
    except Exception as e:
        st.error(f"❌ Error preparing download: {str(e)}")

def download_failed_records(failed_records: list, operation: str, target_object: str):
    """Create download for failed records with error details"""
    try:
        # Create DataFrame with failed records and error information
        download_data = []
        for record in failed_records:
            row = record['original_data'].copy()
            row['Error_Summary'] = record['error_summary']
            row['Full_Error_Details'] = ' | '.join(record['errors'])
            row['Batch_Number'] = record['batch_number']
            row['Failed_Operation'] = record['operation']
            download_data.append(row)
        
        if download_data:
            df = pd.DataFrame(download_data)
            csv = df.to_csv(index=False)
            
            st.download_button(
                label="📥 Download Failed Records CSV",
                data=csv,
                file_name=f"{target_object}_failed_{operation}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="download_failed_csv"
            )
            st.success("✅ Failed records file prepared for download!")
    except Exception as e:
        st.error(f"❌ Error preparing download: {str(e)}")

def generate_retry_file(failed_records: list, target_object: str):
    """Generate a clean file for retrying failed records"""
    try:
        # Create DataFrame with only the original data (no error information)
        retry_data = []
        for record in failed_records:
            retry_data.append(record['original_data'])
        
        if retry_data:
            df = pd.DataFrame(retry_data)
            csv = df.to_csv(index=False)
            
            st.download_button(
                label="🔄 Download Retry File (Clean Data)",
                data=csv,
                file_name=f"{target_object}_retry_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="download_retry_csv"
            )
            st.success("✅ Retry file prepared! Fix the data issues and re-upload this file.")
    except Exception as e:
        st.error(f"❌ Error preparing retry file: {str(e)}")

def check_validation_status():
    """Check if user has completed validation for current org and objects"""
    try:
        if not st.session_state.get('current_org'):
            return False
        
        # Check if there are recent validation results
        validation_base_dir = os.path.join(project_root, 'Validation', st.session_state.current_org)
        
        if not os.path.exists(validation_base_dir):
            return False
        
        # Look for recent validation activities (schema, custom, or GenAI validation)
        recent_validation_found = False
        
        # Check for validation results in the last 24 hours
        from datetime import datetime, timedelta
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        for root, dirs, files in os.walk(validation_base_dir):
            for file in files:
                if file.endswith(('_results.json', '_validation.json', '_bundle.py')):
                    file_path = os.path.join(root, file)
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                    
                    if file_mtime > cutoff_time:
                        recent_validation_found = True
                        break
            
            if recent_validation_found:
                break
        
        # Also check session state for completed validations
        if st.session_state.get('validation_completed', False):
            return True
        
        return recent_validation_found
    
    except Exception as e:
        # If any error occurs, assume validation not completed
        return False


def show_data_operations_help():
    """Display help information for data operations"""
    st.markdown("""
    ###  Data Operations Help
    
    This section provides comprehensive data processing capabilities:
    
    ####  Basic Operations
    - **Extract**: Pull data from Salesforce objects
    - **Load**: Upload CSV files to Salesforce  
    - **Transform**: Clean and prepare data for migration
    - **SQL Migration**: Transfer data between SQL databases
    - **Bulk Operations**: Handle large-scale data operations
    
    ####  Quick Start
    1. Select your Salesforce org and objects
    2. Choose your operation type (Extract/Load/SQL Migration/Bulk)
    3. Upload data or configure extraction
    4. Review and process your data
    5. Monitor processing and download results
    
    For detailed documentation, check the Documentation folder.
    """)


def resolve_lookup_fields_with_mapping(sf_conn, df: pd.DataFrame, target_object: str, field_mappings: dict, return_stats: bool = False):
    """Enhanced lookup field resolution with field mapping support
    
    Args:
        sf_conn: Salesforce connection
        df: DataFrame to process
        target_object: Salesforce object name
        field_mappings: Dict mapping CSV columns to Salesforce field names
        return_stats: If True, returns (df, lookup_fields, lookup_counts) tuple
        
    Returns:
        DataFrame or tuple based on return_stats parameter
    """
    df_resolved = df.copy()
    lookup_count_summary = {}
    
    try:
        # Get object metadata to identify lookup and picklist fields
        object_desc = getattr(sf_conn, target_object).describe()
        lookup_fields = {}
        picklist_fields = {}
        
        # Create reverse mapping (Salesforce field -> CSV column)
        reverse_mappings = {sf_field: csv_col for csv_col, sf_field in field_mappings.items()}
        
        # Find lookup and picklist fields using field mappings
        for field in object_desc['fields']:
            field_name = field['name']
            
            # Check if this Salesforce field is mapped to a CSV column
            if field_name in reverse_mappings:
                csv_column = reverse_mappings[field_name]
                
                if field['type'] == 'reference':
                    # This is a lookup field that's mapped
                    referenced_objects = field.get('referenceTo', [])
                    if referenced_objects:
                        lookup_fields[csv_column] = {
                            'referenced_object': referenced_objects[0],  # Take first referenced object
                            'label': field.get('label', field_name),
                            'sf_field_name': field_name
                        }
                
                elif field['type'] in ['picklist', 'multipicklist']:
                    # This is a picklist field that's mapped
                    picklist_values = field.get('picklistValues', [])
                    if picklist_values:
                        api_names = {}
                        labels = {}
                        for pv in picklist_values:
                            if not pv.get('inactive', False):
                                api_name = pv.get('valueName', pv.get('value', ''))
                                label = pv.get('label', pv.get('value', ''))
                                api_names[api_name] = label
                                labels[label] = api_name
                        
                        picklist_fields[csv_column] = {
                            'api_names': api_names,  # API name -> Label mapping
                            'labels': labels,        # Label -> API name mapping
                            'type': field['type'],
                            'sf_field_name': field_name
                        }
        
        # Display detected fields
        if lookup_fields or picklist_fields:
            st.success(f"✅ **Field Detection Results:**")
            if lookup_fields:
                st.info(f"🔗 **Lookup fields detected:** {len(lookup_fields)} field(s)")
                for csv_col, field_info in lookup_fields.items():
                    st.write(f"   • {csv_col} → {field_info['sf_field_name']} (references {field_info['referenced_object']})")
            
            if picklist_fields:
                st.info(f"📋 **Picklist fields detected:** {len(picklist_fields)} field(s)")
                for csv_col, field_info in picklist_fields.items():
                    st.write(f"   • {csv_col} → {field_info['sf_field_name']} ({len(field_info['api_names'])} options)")
        
        # Process picklist fields first - validate API names
        if picklist_fields:
            st.info(f"🎯 Validating {len(picklist_fields)} picklist field(s)...")
            
            for csv_column, field_info in picklist_fields.items():
                st.info(f"🔍 Validating picklist API names for {csv_column} → {field_info['sf_field_name']}")
                
                # Get unique values from the data (should be API names)
                unique_values = df_resolved[csv_column].dropna().unique()
                valid_api_names = list(field_info['api_names'].keys())
                
                # Validate each value
                invalid_values = []
                valid_count = 0
                
                for value in unique_values:
                    value_str = str(value).strip()
                    if value_str and value_str not in valid_api_names:
                        invalid_values.append(value_str)
                    elif value_str:
                        valid_count += 1
                
                if invalid_values:
                    st.error(f"🚫 **INVALID PICKLIST API NAMES FOUND**")
                    st.error(f"**CSV Column:** {csv_column}")
                    st.error(f"**Salesforce Field:** {field_info['sf_field_name']}")
                    st.error(f"**Invalid values:** {', '.join(invalid_values)}")
                    st.error(f"**Valid API names:** {', '.join(valid_api_names[:10])}{'...' if len(valid_api_names) > 10 else ''}")
                    
                    with st.expander(f"🔧 Fix Picklist Values for {csv_column}"):
                        st.write("**Your file contains invalid picklist API names.**")
                        st.write("")
                        st.write("**📝 Requirements:**")
                        st.write(f"• File should contain API names (not labels)")
                        st.write(f"• Valid API names for {field_info['sf_field_name']}: {', '.join(valid_api_names[:10])}{'...' if len(valid_api_names) > 10 else ''}")
                        st.write("")
                        st.write("**✅ Solution:**")
                        st.write("1. **Update your data file** to use valid API names")
                        st.write("2. **Replace invalid values** with correct API names")
                        st.write("3. **Re-upload the corrected file**")
                        
                        st.info("💡 **Note:** API names are used for data loading, but Salesforce UI will display the corresponding labels")
                    
                    return None  # Block processing due to invalid picklist values
                
                else:
                    st.success(f"\u2705 All {valid_count} picklist values are valid API names for {csv_column}")
        
        # Process lookup fields with field mapping
        if not lookup_fields:
            if not picklist_fields:
                st.info("📝 No lookup or picklist fields detected in your field mappings.")
                st.info("💡 Make sure you've mapped CSV columns to Salesforce lookup/picklist fields")
            if return_stats:
                return df_resolved, {}, {}
            return df_resolved
        
        st.info(f"🔍 Processing {len(lookup_fields)} lookup field(s)...")
        
        # Resolve each lookup field using mapped column names
        for csv_column, field_info in lookup_fields.items():
            referenced_object = field_info['referenced_object']
            sf_field_name = field_info['sf_field_name']
            
            st.info(f"🔄 Resolving {csv_column} → {sf_field_name} → {referenced_object}")
            
            # Check if parent object has data
            try:
                parent_count_query = f"SELECT COUNT(Id) FROM {referenced_object}"
                parent_count_result = sf_conn.query(parent_count_query)
                parent_record_count = parent_count_result['records'][0]['expr0'] if parent_count_result['records'] else 0
                
                if parent_record_count == 0:
                    st.error(f"❌ **CRITICAL ERROR - No parent records found**")
                    st.error(f"**Parent Object:** {referenced_object}")
                    st.error(f"**Issue:** The parent object {referenced_object} contains no records")
                    st.error(f"**Impact:** Cannot resolve lookup values for {csv_column}")
                    
                    with st.expander(f"🔧 Fix Missing Parent Records"):
                        st.write("**The parent object has no data to reference.**")
                        st.write("")
                        st.write("**✅ Solutions:**")
                        st.write(f"1. **Load parent data first** - Insert records into {referenced_object}")
                        st.write(f"2. **Verify object name** - Ensure {referenced_object} is the correct parent object")
                        st.write(f"3. **Check permissions** - Verify you have access to {referenced_object} records")
                        st.write("")
                        st.write("**📝 Recommended Order:**")
                        st.write(f"1. Load data into {referenced_object} first")
                        st.write(f"2. Then load data into {target_object} with lookup references")
                    
                    return None
                
                else:
                    st.success(f"✅ Found {parent_record_count:,} records in {referenced_object}")
                    
            except Exception as count_error:
                st.warning(f"⚠️ Could not verify parent object data: {str(count_error)}")
            
            # Get unique values to resolve from the CSV column
            unique_values = df_resolved[csv_column].dropna().unique()
            
            if len(unique_values) == 0:
                st.info(f"📝 No values to resolve for {csv_column}")
                continue
                
            # Create lookup mapping
            lookup_mapping = {}
            unresolved_values = []
            
            for value in unique_values:
                if pd.isna(value) or str(value).strip() == '':
                    continue
                    
                escaped_value = str(value).replace("'", "\\'")
                
                # Try multiple fields that might contain the lookup value
                possible_fields = ['Name', 'Code__c', 'External_Id__c', 'Code', 'Number__c']
                record_found = False
                
                for lookup_field in possible_fields:
                    try:
                        # Query the referenced object
                        soql = f"SELECT Id, Name FROM {referenced_object} WHERE {lookup_field} = '{escaped_value}'"
                        result = sf_conn.query(soql)
                        
                        if result['totalSize'] > 0:
                            record_id = result['records'][0]['Id']
                            record_name = result['records'][0].get('Name', str(value))
                            lookup_mapping[value] = record_id
                            record_found = True
                            st.success(f"✅ Resolved '{value}' → {record_name} ({record_id})")
                            break
                    except Exception as e:
                        # Try next field
                        continue
                
                if not record_found:
                    unresolved_values.append(f"{value} (MISSING PARENT RECORD)")
            
            # Apply the mapping to the CSV column
            if lookup_mapping:
                df_resolved[csv_column] = df_resolved[csv_column].map(lookup_mapping).fillna(df_resolved[csv_column])
                resolved_count = sum(1 for v in df_resolved[csv_column] if v in lookup_mapping.values())
                st.success(f"📊 Resolved {len(lookup_mapping)} values for {csv_column} (affecting {resolved_count} records)")
                
                # Track lookup counts for reporting
                lookup_count_summary[csv_column] = len(lookup_mapping)
            
            # Report unresolved values
            if unresolved_values:
                st.warning(f"⚠️ **{len(unresolved_values)} values could not be resolved for {csv_column}:**")
                for unresolved in unresolved_values[:10]:  # Show first 10
                    st.write(f"   • {unresolved}")
                if len(unresolved_values) > 10:
                    st.write(f"   ... and {len(unresolved_values) - 10} more")
        
        # Return results
        if return_stats:
            return df_resolved, lookup_fields, lookup_count_summary
        return df_resolved
        
    except Exception as e:
        st.error(f"❌ Error in lookup field resolution: {str(e)}")
        st.exception(e)
        if return_stats:
            return df, {}, {}
        return df
