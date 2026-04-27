"""
Data Hub UI Components
======================
Streamlit interface for Data Hub functionality
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Optional, Dict, Any
from .data_hub import DataHub
from .data_source_handler import DataSourceHandler


def show_data_hub_interface(sf_conn=None):
    """
    Display complete Data Hub interface
    
    Args:
        sf_conn: Optional Salesforce connection object for SOQL queries
    """
    st.title("📊 Data Hub - Centralized Data Management")
    
    st.info("""
    **Data Hub** is the central repository for all your data in the DM Toolkit.
    - Upload CSV/Excel files
    - Query Salesforce directly via SOQL
    - Reuse data across all modules (Validation, Data Operations, etc.)
    - No need to upload the same data multiple times!
    """)
    
    # Initialize or get Data Hub from session
    if 'data_hub' not in st.session_state:
        st.session_state.data_hub = DataHub()
    
    data_hub = st.session_state.data_hub
    
    # Create tabs for different sections
    tab1, tab2, tab3, tab4 = st.tabs(["📥 Load Data", "💾 Manage Datasets", "📋 Active Dataset", "📊 Operation History"])
    
    # ==================== TAB 1: LOAD DATA ====================
    with tab1:
        st.header("Load Data Into Hub")
        
        load_method = st.radio(
            "Select Data Source:",
            options=["📄 Upload File", "⚙️ Query Salesforce"],
            horizontal=True
        )
        
        if load_method == "📄 Upload File":
            _show_file_upload_section(data_hub)
        
        else:  # Salesforce SOQL
            _show_soql_section(data_hub, sf_conn)
    
    # ==================== TAB 2: MANAGE DATASETS ====================
    with tab2:
        st.header("Manage Cached Datasets")
        _show_dataset_management(data_hub)
    
    # ==================== TAB 3: ACTIVE DATASET ====================
    with tab3:
        st.header("Active Dataset Preview")
        _show_active_dataset_preview(data_hub)
    
    # ==================== TAB 4: OPERATION HISTORY ====================
    with tab4:
        st.header("📊 Operation History")
        st.markdown("""
        Complete audit trail of ALL operations performed in the toolkit.
        Tracks: Data loads, validations, data quality checks, migrations, and more.
        
        **Operations tracked by:**
        - ✅ Organization (Source & Target)
        - ✅ Object (Account, Opportunity, Custom Objects, etc.)
        - ✅ Operation Type (Load, Validation, Quality Check, Migration, etc.)
        - ✅ Status (Success, Failure, Partial)
        - ✅ Validation Results (Pass/Fail counts)
        - ✅ Timestamp & User Info
        """)
        
        try:
            from .operation_manager import get_operation_manager
            
            op_manager = get_operation_manager()
            
            # Step 1: Show statistics
            st.markdown("### 📈 Operation Statistics")
            
            stats = op_manager.get_operation_stats()
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Operations", stats['total_operations'])
            with col2:
                st.metric("Total Records", stats['total_records_processed'])
            with col3:
                st.metric("Validation Passed", stats['total_validation_passed'])
            with col4:
                st.metric("Validation Failed", stats['total_validation_failed'])
            
            st.markdown("---")
            
            # Step 2: Filters with cascading dropdowns
            st.markdown("### 🔍 Filter Operations")
            
            col1, col2, col3, col4 = st.columns(4)
            
            # Get available Salesforce orgs from credentials file
            available_orgs = _get_available_salesforce_orgs()
            
            with col1:
                if len(available_orgs) == 0:
                    st.warning("⚠️ No Salesforce organizations configured in linkedservices.json")
                    org_filter = None
                else:
                    org_filter = st.selectbox(
                        "Organization:",
                        available_orgs,
                        key="history_org_filter",
                        help="Select a Salesforce organization to view operations"
                    )
            
            # Get objects based on selected org - CASCADING DROPDOWN
            with col2:
                if org_filter is None:
                    st.info("Select an organization first")
                    object_filter = None
                else:
                    # Get objects from the selected org
                    org_objects = _get_objects_for_org(org_filter)
                    
                    if len(org_objects) == 0:
                        st.info(f"No objects found for {org_filter}. Check Salesforce connection.")
                        object_filter = None
                    else:
                        object_filter = st.selectbox(
                            "Object:",
                            org_objects,
                            key="history_object_filter",
                            help=f"Objects available in {org_filter}"
                        )
            
            with col3:
                op_type_filter = st.selectbox(
                    "Operation Type:",
                    ["All", "SOQL_Query", "File_Upload", "Data_Load", "Validation_Check_Business_Rules", "Validation_Check_Data_Quality", "Validation_Check_Schema", "Migration_Execute", "Lookup_Resolution"],
                    key="history_op_type_filter",
                    help="Select operation type or 'All' to see all types"
                )
            with col4:
                status_filter = st.selectbox(
                    "Status:",
                    ["All", "COMPLETE", "FAILED"],
                    key="history_status_filter",
                    help="Filter by operation status"
                )
            
            # Debug info (optional - can remove later)
            with st.expander("🔧 Debug Info", expanded=False):
                st.write(f"**Selected Org:** {org_filter}")
                st.write(f"**Selected Object:** {object_filter}")
                st.write(f"**Selected Operation Type:** {op_type_filter}")
                st.write(f"**Selected Status:** {status_filter}")
                if org_filter:
                    st.write(f"**Available Objects for {org_filter}:** {op_manager.get_unique_objects_for_org(org_filter)}")
            
            # Apply filters - only query if org and object are selected
            if org_filter is None:
                st.warning("📭 Please select an organization to view operations.")
                history = []
            elif object_filter is None:
                st.warning(f"📭 No objects available for {org_filter}. Please select another organization or upload data first.")
                history = []
            else:
                history = op_manager.get_operation_history(
                    org_filter=org_filter,
                    object_filter=object_filter,
                    operation_type_filter=None if op_type_filter == "All" else op_type_filter,
                    status_filter=None if status_filter == "All" else status_filter
                )
            
            st.markdown("---")
            
            # Step 3: Display operations as table
            if history:
                st.markdown(f"### 📋 Operations ({len(history)} found)")
                
                # Convert to display format
                display_data = []
                for op in history:
                    display_data.append({
                        "Operation ID": op['operation_id'],
                        "Date/Time": op['timestamp'][:19],  # Remove seconds
                        "Type": op['operation_type'].replace('_', ' '),
                        "Source Org": op.get('source_org', '-'),
                        "Target Org": op.get('target_org', '-'),
                        "Object": op['object_name'],
                        "Records": op['record_count'],
                        "Validation": op.get('validation_status', '-'),
                        "Status": "✅" if op['status'] == "COMPLETE" else "❌"
                    })
                
                df_display = pd.DataFrame(display_data)
                st.dataframe(df_display, use_container_width=True, hide_index=True)
                
                st.markdown("---")
                
                # Step 4: View operation details
                st.markdown("### 📂 View Operation Details")
                
                selected_op_id = st.selectbox(
                    "Select operation to view:",
                    [op['operation_id'] for op in history],
                    key="selected_operation"
                )
                
                if selected_op_id:
                    try:
                        data, operation = op_manager.retrieve_operation_data(selected_op_id)
                        
                        # Display metadata
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.subheader("📋 Operation Metadata")
                            metadata_display = {
                                "Operation ID": operation['operation_id'],
                                "Timestamp": operation['timestamp'],
                                "Type": operation['operation_type'],
                                "Source Org": operation.get('source_org', '-'),
                                "Target Org": operation.get('target_org', '-'),
                                "Object": operation['object_name'],
                                "Total Records": operation['record_count'],
                                "Validation Status": operation.get('validation_status', '-'),
                                "Passed": operation.get('validation_passed', 0),
                                "Failed": operation.get('validation_failed', 0),
                                "Created By": operation.get('created_by', '-'),
                                "Notes": operation.get('notes', '-')
                            }
                            
                            for key, value in metadata_display.items():
                                st.text(f"{key}: {value}")
                            
                            if operation.get('query'):
                                st.subheader("🔍 SOQL Query")
                                st.code(operation['query'], language='sql')
                            
                            if operation.get('file_uploaded'):
                                st.subheader("📁 File Uploaded")
                                st.text(f"File: {operation['file_uploaded']}")
                        
                        with col2:
                            st.subheader("📊 Data Preview")
                            
                            st.write(f"Rows: {len(data)} | Columns: {len(data.columns)}")
                            
                            # Show data statistics
                            if len(data) > 0:
                                st.caption("Column Statistics:")
                                st.dataframe(
                                    data.describe(include='all').T,
                                    use_container_width=True
                                )
                        
                        st.markdown("---")
                        
                        # Display full data
                        st.subheader("📈 Full Data")
                        st.dataframe(data, use_container_width=True)
                        
                        # Download buttons
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            csv_data = data.to_csv(index=False)
                            st.download_button(
                                "📥 Download as CSV",
                                csv_data,
                                f"{selected_op_id}_data.csv",
                                "text/csv",
                                key=f"download_csv_{selected_op_id}"
                            )
                        
                        with col2:
                            try:
                                import io
                                buffer = io.BytesIO()
                                data.to_excel(buffer, index=False, engine='openpyxl')
                                excel_data = buffer.getvalue()
                                
                                st.download_button(
                                    "📥 Download as Excel",
                                    excel_data,
                                    f"{selected_op_id}_data.xlsx",
                                    "application/vnd.ms-excel",
                                    key=f"download_xlsx_{selected_op_id}"
                                )
                            except:
                                st.caption("💡 Excel export requires openpyxl")
                        
                        with col3:
                            if st.button(
                                "🗑️ Delete Operation",
                                key=f"delete_{selected_op_id}"
                            ):
                                if op_manager.delete_operation(selected_op_id):
                                    st.success(f"✅ Deleted operation {selected_op_id}")
                                    st.rerun()
                                else:
                                    st.error("❌ Could not delete operation")
                    
                    except FileNotFoundError as e:
                        st.warning(f"⚠️ Data file not found: {str(e)}")
                    except Exception as e:
                        st.error(f"❌ Error loading operation data: {str(e)}")
            
            else:
                st.info("📭 No operations found matching your filters.")
                st.markdown("""
                **Get Started:**
                1. Use **📥 Load Data** tab to upload a file or query Salesforce
                2. Operations will appear here for future reference
                3. View, filter, and download historical data anytime!
                """)
            
            # Step 5: Export history
            st.markdown("---")
            st.markdown("### 📤 Export History")
            
            if st.button("📥 Export All Operations to CSV", key="export_history"):
                try:
                    csv_file = op_manager.export_history_to_csv("operation_history.csv")
                    with open(csv_file, 'r') as f:
                        st.download_button(
                            "Download History CSV",
                            f.read(),
                            "operation_history.csv",
                            "text/csv"
                        )
                    st.success("✅ History exported!")
                except Exception as e:
                    st.error(f"❌ Error exporting history: {str(e)}")
        
        except ImportError as e:
            st.error(f"❌ Could not load Operation Manager: {str(e)}")
            st.info("💡 Make sure operation_manager.py is properly installed")
        except Exception as e:
            st.error(f"❌ Error in Data Operations tab: {str(e)}")
    
    st.divider()
    
    # Quick stats
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📦 Cached Datasets", data_hub.get_dataset_count())
    with col2:
        if data_hub.has_active_dataset():
            active_info = data_hub.get_active_dataset_info()
            st.metric("🎯 Active Dataset", active_info['name'])
        else:
            st.metric("🎯 Active Dataset", "None")
    with col3:
        if data_hub.has_active_dataset():
            active_info = data_hub.get_active_dataset_info()
            st.metric("📊 Rows", active_info['metadata']['row_count'])
        else:
            st.metric("📊 Rows", "0")


def _show_file_upload_section(data_hub: DataHub):
    """File upload section"""
    st.subheader("📄 Upload File (CSV, PSV, or Excel)")
    
    # File upload
    uploaded_file = st.file_uploader(
        "Choose a file",
        type=['csv', 'psv', 'xlsx', 'xls'],
        help="Upload a CSV, PSV (pipe-separated), or Excel file with your data"
    )
    
    if uploaded_file is not None:
        # Dataset naming
        col1, col2 = st.columns([2, 1])
        with col1:
            dataset_name = st.text_input(
                "Dataset Name:",
                value=uploaded_file.name.split('.')[0],
                help="Descriptive name for this dataset"
            )
        with col2:
            st.write("")  # Spacing
            load_btn = st.button("✅ Load into Hub", type="primary", use_container_width=True)
        
        if load_btn and dataset_name.strip():
            with st.spinner("⏳ Processing file..."):
                # Load file
                df, load_msg = DataSourceHandler.load_from_file(uploaded_file)
                
                if df is not None:
                    # Validate
                    is_valid, val_msg = DataSourceHandler.validate_dataframe(df)
                    st.info(val_msg)
                    
                    if is_valid:
                        # Add to hub
                        dataset_id = data_hub.add_dataset(
                            df=df,
                            dataset_name=dataset_name,
                            source_type='file_upload',
                            source_details={
                                'file_name': uploaded_file.name,
                                'file_size_kb': uploaded_file.size / 1024
                            },
                            set_active=True
                        )
                        
                        st.success(f"✅ Dataset '{dataset_name}' loaded successfully!")
                        st.info(f" Dataset ID: `{dataset_id}`")
                        st.balloons()
                else:
                    st.error(load_msg)
        
        elif load_btn and not dataset_name.strip():
            st.warning("⚠️ Please enter a dataset name")


def _show_soql_section(data_hub: DataHub, sf_conn):
    """SOQL query section"""
    st.subheader("⚙️ Query Salesforce via SOQL")
    
    if sf_conn is None:
        st.warning("⚠️ Salesforce connection not available. Please configure connection first.")
        return
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        object_name = st.text_input(
            "Object Name:",
            placeholder="e.g., Account, WOD_2__Rates_Details__c",
            help="Name of the Salesforce object to query"
        )
    
    with col2:
        dataset_name = st.text_input(
            "Dataset Name:",
            value=object_name if object_name else "SOQL_Query",
            help="Name for this dataset in the hub"
        )
    
    # SOQL Query editor
    soql_query = st.text_area(
        "SOQL Query:",
        height=150,
        placeholder="SELECT Id, Name, Field1__c FROM WOD_2__Rates_Details__c LIMIT 1000",
        help="""
        Write your SOQL query here. Examples:
        - SELECT Id, Name FROM Account LIMIT 100
        - SELECT Id, Amount, StageName FROM Opportunity WHERE IsClosed = false
        - SELECT Id, Name, Amount__c FROM WOD_2__Rates_Details__c WHERE Status__c = 'Active'
        """
    )
    
    # Query limits info
    col1, col2, col3 = st.columns(3)
    with col1:
        limit = st.number_input("Record Limit:", min_value=10, max_value=50000, value=1000, step=100)
    with col2:
        st.write("")  # Spacing
    with col3:
        st.write("")  # Spacing
    
    # Execute button
    execute_btn = st.button("🚀 Execute SOQL", type="primary", use_container_width=True)
    
    if execute_btn:
        if not object_name.strip():
            st.error("❌ Please enter an object name")
        elif not soql_query.strip():
            st.error("❌ Please enter a SOQL query")
        elif not dataset_name.strip():
            st.error("❌ Please enter a dataset name")
        else:
            # Add limit if not already in query
            query = soql_query.strip()
            if "LIMIT" not in query.upper():
                query += f" LIMIT {limit}"
            
            with st.spinner("🔄 Executing SOQL query..."):
                df, query_msg = DataSourceHandler.load_from_soql(
                    sf_conn,
                    query,
                    object_name
                )
                
                st.info(query_msg)
                
                if df is not None:
                    # Validate
                    is_valid, val_msg = DataSourceHandler.validate_dataframe(df)
                    
                    if is_valid:
                        # Preview
                        st.success("✅ Query executed successfully!")
                        st.write("**Preview (first 5 rows):**")
                        st.dataframe(df.head(), use_container_width=True)
                        
                        # Add to hub
                        if st.button("✅ Add to Hub", type="primary"):
                            dataset_id = data_hub.add_dataset(
                                df=df,
                                dataset_name=dataset_name,
                                source_type='salesforce_soql',
                                source_details={
                                    'object_name': object_name,
                                    'soql_query': query,
                                    'record_count': len(df)
                                },
                                set_active=True
                            )
                            
                            st.success(f"✅ Dataset '{dataset_name}' added to hub!")
                            st.info(f"📦 Dataset ID: `{dataset_id}`")
                            st.balloons()
                    else:
                        st.error(val_msg)


def _show_dataset_management(data_hub: DataHub):
    """Dataset management interface"""
    datasets = data_hub.list_datasets()
    
    if not datasets:
        st.info("📭 No datasets cached yet. Load data from the '📥 Load Data' tab.")
        return
    
    st.write(f"**Total Datasets: {len(datasets)}**")
    st.divider()
    
    for dataset_info in datasets:
        dataset_id = dataset_info['id']
        name = dataset_info['name']
        metadata = dataset_info['metadata']
        is_active = dataset_info['is_active']
        
        # Create container for each dataset
        with st.container():
            col1, col2, col3, col4, col5 = st.columns([2, 2, 1, 1, 1])
            
            with col1:
                # Dataset name with active indicator
                if is_active:
                    st.markdown(f"**🎯 {name}** (Active)")
                else:
                    st.markdown(f"**📦 {name}**")
            
            with col2:
                # Source info
                source_type = metadata['source_type']
                if source_type == 'file_upload':
                    source_icon = "📄"
                elif source_type == 'salesforce_soql':
                    source_icon = "⚙️"
                else:
                    source_icon = "📋"
                
                st.caption(f"{source_icon} {source_type} | {metadata['row_count']} rows | {metadata['column_count']} cols")
            
            with col3:
                if st.button("✓ Set Active", key=f"active_{dataset_id}", use_container_width=True):
                    data_hub.set_active_dataset(dataset_id)
                    st.rerun()
            
            with col4:
                if st.button("📊 Preview", key=f"preview_{dataset_id}", use_container_width=True):
                    st.session_state[f'show_preview_{dataset_id}'] = not st.session_state.get(f'show_preview_{dataset_id}', False)
                    st.rerun()
            
            with col5:
                if st.button("❌ Delete", key=f"delete_{dataset_id}", use_container_width=True):
                    if st.session_state.get(f'confirm_delete_{dataset_id}', False):
                        data_hub.delete_dataset(dataset_id)
                        st.success(f"✅ Dataset '{name}' deleted")
                        st.rerun()
                    else:
                        st.session_state[f'confirm_delete_{dataset_id}'] = True
                        st.warning("⚠️ Click again to confirm deletion")
                        st.rerun()
            
            # Show preview if requested
            if st.session_state.get(f'show_preview_{dataset_id}', False):
                with st.expander(f"📊 Preview: {name}", expanded=True):
                    df = data_hub.get_dataset(dataset_id)
                    st.dataframe(df.head(10), use_container_width=True)
                    
                    # Show metadata
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Rows", metadata['row_count'])
                    with col2:
                        st.metric("Columns", metadata['column_count'])
                    with col3:
                        st.metric("Size (KB)", f"{metadata['memory_usage_kb']:.2f}")
                    with col4:
                        timestamp = datetime.fromisoformat(metadata['timestamp'])
                        st.metric("Loaded", timestamp.strftime("%H:%M:%S"))
            
            st.divider()


def _show_active_dataset_preview(data_hub: DataHub):
    """Show active dataset preview and details"""
    if not data_hub.has_active_dataset():
        st.info("📭 No active dataset. Select a dataset from 'Manage Datasets' tab or load new data.")
        return
    
    dataset_info = data_hub.get_active_dataset_with_metadata()
    metadata = dataset_info['metadata']
    df = dataset_info['df']
    
    # Header with dataset info
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader(f"🎯 {dataset_info['name']}")
    with col2:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📊 Rows", metadata['row_count'])
    with col2:
        st.metric("📋 Columns", metadata['column_count'])
    with col3:
        st.metric("💾 Size (KB)", f"{metadata['memory_usage_kb']:.2f}")
    with col4:
        timestamp = datetime.fromisoformat(metadata['timestamp'])
        st.metric("⏰ Loaded", timestamp.strftime("%m/%d %H:%M"))
    
    st.divider()
    
    # Source details
    st.write("**📍 Source Information:**")
    source_col1, source_col2 = st.columns(2)
    
    with source_col1:
        st.write(f"**Source Type:** {metadata['source_type'].replace('_', ' ').title()}")
    with source_col2:
        source_details = metadata['source_details']
        if 'file_name' in source_details:
            st.write(f"**File:** {source_details['file_name']}")
        elif 'object_name' in source_details:
            st.write(f"**Object:** {source_details['object_name']}")
    
    st.divider()
    
    # Columns info
    with st.expander("📋 Column Details", expanded=False):
        col_df = pd.DataFrame({
            'Column Name': metadata['columns'],
            'Data Type': [str(df[col].dtype) for col in metadata['columns']],
            'Non-Null Count': [df[col].notna().sum() for col in metadata['columns']]
        })
        st.dataframe(col_df, use_container_width=True)
    
    st.divider()
    
    # Data preview
    st.write("**📊 Data Preview (first 10 rows):**")
    st.dataframe(df.head(10), use_container_width=True)
    
    st.divider()
    
    # Download options
    st.write("**📥 Download Active Dataset:**")
    col1, col2 = st.columns(2)
    
    with col1:
        csv_data = df.to_csv(index=False)
        st.download_button(
            label="📄 Download as CSV",
            data=csv_data,
            file_name=f"{dataset_info['name']}_exported.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with col2:
        try:
            import io
            buffer = io.BytesIO()
            df.to_excel(buffer, index=False, engine='openpyxl')
            excel_data = buffer.getvalue()
            
            st.download_button(
                label="📊 Download as Excel",
                data=excel_data,
                file_name=f"{dataset_info['name']}_exported.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        except:
            st.info("💡 Excel export requires openpyxl. Install: pip install openpyxl")


def get_active_dataset() -> Optional[pd.DataFrame]:
    """
    Get active dataset from Data Hub
    
    Utility function for other modules to use active dataset
    
    Returns:
        DataFrame or None if no active dataset
    """
    if 'data_hub' in st.session_state:
        return st.session_state.data_hub.get_active_dataset()
    return None


def get_active_dataset_info() -> Optional[Dict[str, Any]]:
    """
    Get active dataset info including metadata
    
    Returns:
        Dict with 'name' and 'metadata' keys, or None
    """
    if 'data_hub' in st.session_state:
        return st.session_state.data_hub.get_active_dataset_info()
    return None


def has_active_dataset() -> bool:
    """Check if active dataset exists"""
    if 'data_hub' in st.session_state:
        return st.session_state.data_hub.has_active_dataset()
    return False


def _get_available_salesforce_orgs() -> list:
    """
    Get list of available Salesforce organizations from credentials file
    
    Returns:
        List of org names (e.g., ['HeraQA', 'TestDev', 'deployement'])
    """
    try:
        import json
        import os
        
        creds_file = r"C:\DM_toolkit\Services\linkedservices.json"
        if not os.path.exists(creds_file):
            return []
        
        with open(creds_file, 'r') as f:
            credentials = json.load(f)
        
        # Filter for Salesforce orgs (those with Salesforce credentials)
        sf_orgs = []
        for org_name, org_creds in credentials.items():
            if 'username' in org_creds and 'password' in org_creds:
                sf_orgs.append(org_name)
        
        return sorted(sf_orgs)
    except Exception as e:
        st.error(f"Error loading organizations: {str(e)}")
        return []


@st.cache_data(ttl=3600)
def _get_objects_for_org(org_name: str) -> list:
    """
    Get list of Salesforce objects for a specific organization
    
    Args:
        org_name: Name of the Salesforce organization
    
    Returns:
        Sorted list of object names (e.g., ['Account', 'Contact', 'Opportunity'])
    """
    try:
        import json
        import os
        from simple_salesforce import Salesforce
        
        creds_file = r"C:\DM_toolkit\Services\linkedservices.json"
        if not os.path.exists(creds_file):
            return []
        
        with open(creds_file, 'r') as f:
            credentials = json.load(f)
        
        if org_name not in credentials:
            st.warning(f"Organization '{org_name}' not found in credentials")
            return []
        
        org_creds = credentials[org_name]
        
        # Connect to Salesforce
        sf = Salesforce(
            username=org_creds.get('username'),
            password=org_creds.get('password'),
            security_token=org_creds.get('security_token', ''),
            domain=org_creds.get('domain', 'login')
        )
        
        # Get all objects
        all_objects = sf.describe()['sobjects']
        object_names = [obj['name'] for obj in all_objects if obj.get('queryable', False)]
        
        return sorted(object_names)
    except Exception as e:
        st.warning(f"Could not retrieve objects for {org_name}: {str(e)}")
        return []
