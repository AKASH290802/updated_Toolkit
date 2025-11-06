import streamlit as st
import pandas as pd
import os
import sys
from typing import Dict, Optional
import json

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.append(project_root)

from .utils import (
    establish_sf_connection, 
    get_salesforce_objects, 
    display_dataframe_with_download,
    show_processing_status,
    validate_file_upload,
    save_uploaded_file,
    create_progress_tracker
)

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
            selected_object = st.selectbox(
                "Choose an object:",
                options=["Select an object..."] + sorted(objects),
                key="sf_extraction_object",
                help="Choose the Salesforce object to extract data from"
            )
        
        with col2:
            if selected_object != "Select an object...":
                if st.button("🔍 Object Info", use_container_width=True):
                    show_object_info(sf_conn, selected_object)
        
        if selected_object == "Select an object...":
            st.info("👆 Please select an object to continue")
            return
        
        # Update session state
        st.session_state.current_object = selected_object
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
        type=['csv', 'xlsx', 'xls'],
        help="Upload a CSV or Excel file to extract data"
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
                if file_ext.lower() == '.csv':
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)
                
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
        if st.session_state.current_object:
            st.info(st.session_state.current_object)
        else:
            st.warning("No object selected")
    
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
            type=['csv', 'xlsx', 'xls'],
            key="sql_load_upload"
        )
        
        if uploaded_file and validate_file_upload(uploaded_file):
            try:
                file_ext = os.path.splitext(uploaded_file.name)[1].lower()
                
                if file_ext == '.csv':
                    df_to_load = pd.read_csv(uploaded_file)
                else:
                    df_to_load = pd.read_excel(uploaded_file)
                
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
    
    # Object selection for loading
    objects = get_salesforce_objects(sf_conn, filter_custom=True)
    
    if objects:
        target_object = st.selectbox(
            "Select Target Object",
            options=[""] + objects,
            key="sf_load_object"
        )
    else:
        st.error("❌ No Salesforce objects found")
        return
    
    if target_object:
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
                type=['csv', 'xlsx', 'xls'],
                key="sf_load_file"
            )
            
            if uploaded_file and validate_file_upload(uploaded_file):
                try:
                    file_ext = os.path.splitext(uploaded_file.name)[1]
                    if file_ext.lower() == '.csv':
                        df_to_load = pd.read_csv(uploaded_file)
                    else:
                        df_to_load = pd.read_excel(uploaded_file)
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
                        field_mappings = create_custom_mapping_interface(df_to_load.columns.tolist(), sf_fields, sf_field_info, field_mappings)
                
                elif mapping_strategy == "📋 Standard Mapping":
                    # Standard mapping with common field recognition
                    field_mappings = create_standard_mapping_interface(df_to_load.columns.tolist(), sf_fields, sf_field_info)
                
                else:  # Custom Mapping
                    # Full custom mapping interface
                    field_mappings = create_custom_mapping_interface(df_to_load.columns.tolist(), sf_fields, sf_field_info)
                
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
            col_batch1, col_batch2, col_batch3 = st.columns(3)
            
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
            
            # Load button
            if st.button("🚀 Start Loading", type="primary", use_container_width=True):
                load_data_to_salesforce(sf_conn, df_to_load, target_object, 
                                      operation_type, batch_size, parallel_batches)

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
                if filename.endswith(('.csv', '.xlsx', '.xls')):
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

def load_data_to_salesforce(sf_conn, df: pd.DataFrame, target_object: str, operation: str, batch_size: int, parallel_batches: int):
    """Load data to Salesforce with batch processing"""
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
        
        # Clean data before conversion - FIX FOR NaN ERROR
        df_cleaned = clean_dataframe_for_salesforce(df)
        
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
                    result = getattr(sf_conn.bulk, target_object).insert(batch)
                elif operation.lower() == "update":
                    result = getattr(sf_conn.bulk, target_object).update(batch)
                else:  # upsert
                    result = getattr(sf_conn.bulk, target_object).upsert(batch, 'Id')
                
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

def create_custom_mapping_interface(csv_columns: list, sf_fields: list, sf_field_info: dict, existing_mappings: dict = None) -> dict:
    """Create custom mapping interface with full control"""
    st.write("**✏️ Custom Field Mapping:**")
    st.info("Manually configure each field mapping with full control")
    
    if existing_mappings is None:
        existing_mappings = {}
    
    field_mappings = {}
    sf_field_options = ["-- Skip Field --"] + sf_fields
    
    # Create detailed mapping interface
    for csv_col in csv_columns:
        with st.container():
            st.divider()
            col1, col2 = st.columns([1, 1])
            
            with col1:
                st.write(f"**CSV Column: {csv_col}**")
                # Show column details
                st.caption(f"Sample data preview available")
            
            with col2:
                # Get existing mapping or suggest new one
                current_mapping = existing_mappings.get(csv_col, "-- Skip Field --")
                
                if current_mapping not in sf_field_options:
                    # Find suggested mapping if current is not valid
                    current_mapping = find_suggested_mapping(csv_col, sf_fields)
                    if current_mapping not in sf_field_options:
                        current_mapping = "-- Skip Field --"
                
                default_index = sf_field_options.index(current_mapping)
                
                mapped_field = st.selectbox(
                    f"Map '{csv_col}' to Salesforce field:",
                    options=sf_field_options,
                    index=default_index,
                    key=f"custom_mapping_{csv_col}",
                    help=f"Select the Salesforce field to map '{csv_col}' to"
                )
                
                field_mappings[csv_col] = mapped_field
                
                # Show field information
                if mapped_field != "-- Skip Field --":
                    sf_info = sf_field_info.get(mapped_field, {})
                    st.success(f"✅ **{sf_info.get('label', mapped_field)}**")
                    st.caption(f"Type: {sf_info.get('type', 'Unknown')} | Max Length: {sf_info.get('length', 'N/A')}")
                else:
                    st.warning("⏭️ Field will be skipped")
    
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
        st.success("✅ Retry file prepared for download! Fix the issues and try again.")
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
        
    except Exception:
        # If any error occurs, assume validation not completed
        return False