import streamlit as st
import json
import os
import pandas as pd
from typing import Dict
from .utils import establish_sf_connection, show_processing_status

def show_configuration(credentials: Dict):
    """Display configuration management interface"""
    
    st.title("⚙️ Configuration Management")
    st.markdown("Manage your Salesforce organizations, database connections, and system settings")
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "🏢 Organizations", 
        "🗄️ Database Settings", 
        "📁 Directory Structure",
        "🔧 System Settings"
    ])
    
    with tab1:
        show_org_management(credentials)
    
    with tab2:
        show_database_settings(credentials)
    
    with tab3:
        show_directory_structure()
    
    with tab4:
        show_system_settings()

def show_org_management(credentials: Dict):
    """Manage Salesforce organizations"""
    st.subheader("🏢 Salesforce Organizations")
    
    if not credentials:
        st.warning("No credentials found. Please add organization credentials.")
        return
    
    # Display existing organizations
    st.write("### Configured Organizations")
    
    org_data = []
    for org_name, creds in credentials.items():
        if 'username' in creds and 'sql' not in org_name.lower():
            org_data.append({
                "Organization": org_name,
                "Username": creds.get('username', 'N/A'),
                "Domain": creds.get('domain', 'login'),
                "Has Security Token": "Yes" if creds.get('security_token') else "No"
            })
    
    if org_data:
        df_orgs = pd.DataFrame(org_data)
        st.dataframe(df_orgs, use_container_width=True)
    
    st.divider()
    
    # Test connection section
    st.write("### Test Connections")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        test_org = st.selectbox(
            "Select organization to test",
            options=[""] + [org for org in credentials.keys() if 'sql' not in org.lower()],
            key="test_org_selector"
        )
    
    with col2:
        test_button = st.button("🔍 Test Connection", disabled=not test_org)
    
    if test_button and test_org:
        with st.spinner(f"Testing connection to {test_org}..."):
            sf_conn = establish_sf_connection(credentials, test_org)
            
            if sf_conn:
                try:
                    # Get basic org info
                    org_info = sf_conn.query("SELECT Id, Name FROM Organization LIMIT 1")
                    if org_info['records']:
                        org_record = org_info['records'][0]
                        st.success(f"✅ Connection successful!")
                        st.info(f"**Organization ID:** {org_record['Id']}")
                        st.info(f"**Organization Name:** {org_record['Name']}")
                        show_processing_status("connection_test", f"Successfully connected to {test_org}", "success")
                    else:
                        st.warning("Connected but unable to retrieve organization details")
                except Exception as e:
                    st.error(f"Connected but error retrieving org details: {str(e)}")
    
    st.divider()
    
    # Add new organization
    st.write("### Add New Organization")
    
    with st.expander("➕ Add New Salesforce Organization", expanded=False):
        with st.form("add_org_form"):
            new_org_name = st.text_input("Organization Name", help="Unique identifier for this org")
            new_username = st.text_input("Username", help="Salesforce username")
            new_password = st.text_input("Password", type="password", help="Salesforce password")
            new_security_token = st.text_input("Security Token", help="Optional security token")
            new_domain = st.selectbox("Domain", ["login", "test"], help="login for production, test for sandbox")
            
            submit_button = st.form_submit_button("Add Organization")
            
            if submit_button:
                if new_org_name and new_username and new_password:
                    # Add to credentials
                    new_creds = {
                        "username": new_username,
                        "password": new_password,
                        "security_token": new_security_token,
                        "domain": new_domain
                    }
                    
                    # Check if org name already exists
                    if new_org_name in credentials:
                        st.error(f"❌ Organization '{new_org_name}' already exists! Please choose a different name.")
                    else:
                        # Save to file and update session state
                        if save_credentials(credentials, new_org_name, new_creds):
                            # Show prominent success message with balloons effect
                            st.balloons()
                            st.success(f"🎉 **Organization '{new_org_name}' created successfully!**")
                            
                            # Show detailed success information
                            st.markdown("""
                            **✅ What happened:**
                            - New organization credentials saved securely
                            - Organization added to your available orgs list
                            - You can now select it from the sidebar dropdown
                            
                            **🚀 Next steps:**
                            1. Select the new organization from the sidebar dropdown
                            2. Go to any module (Data Operations, Validation, etc.)
                            3. Test the connection to ensure everything works
                            """)
                            
                            # Auto-refresh after showing success
                            import time
                            time.sleep(2)  # Give user time to read the success message
                            st.rerun()
                        else:
                            st.error("❌ Failed to save organization credentials")
                else:
                    st.error("Please fill in all required fields (Name, Username, Password)")

def show_database_settings(credentials: Dict):
    """Manage database connections"""
    st.subheader("🗄️ SQL Server Database Settings")
    st.markdown("Manage your SQL Server database connections for data operations")
    
    # Display existing SQL connections
    sql_connections = {k: v for k, v in credentials.items() if 'sql' in k.lower()}
    
    if sql_connections:
        st.write("### Configured Database Connections")
        
        # Create a more detailed table view
        db_data = []
        for db_name, db_config in sql_connections.items():
            db_data.append({
                "Connection Name": db_name.replace('sql_', '').upper(),
                "Server": db_config.get('server', 'N/A'),
                "Database": db_config.get('database', 'N/A'),
                "Username": db_config.get('username', 'Windows Auth' if db_config.get('Trusted_Connection') == 'yes' else 'N/A'),
                "Driver": db_config.get('driver', 'N/A'),
                "Auth Type": "Windows Authentication" if db_config.get('Trusted_Connection') == 'yes' else "SQL Authentication"
            })
        
        if db_data:
            df_dbs = pd.DataFrame(db_data)
            st.dataframe(df_dbs, use_container_width=True)
        
        # Detailed view with test connections
        st.write("### Connection Details & Testing")
        for db_name, db_config in sql_connections.items():
            with st.expander(f"📊 {db_name.replace('sql_', '').upper()} - Connection Details", expanded=False):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Server:**", db_config.get('server', 'N/A'))
                    st.write("**Database:**", db_config.get('database', 'N/A'))
                    st.write("**Port:**", db_config.get('port', '1433 (default)'))
                    st.write("**Driver:**", db_config.get('driver', 'N/A'))
                
                with col2:
                    auth_type = "Windows Authentication" if db_config.get('Trusted_Connection') == 'yes' else "SQL Authentication"
                    st.write("**Authentication:**", auth_type)
                    if auth_type == "SQL Authentication":
                        st.write("**Username:**", db_config.get('username', 'N/A'))
                        st.write("**Password:**", "***" if db_config.get('password') else 'Not set')
                    st.write("**Encryption:**", db_config.get('encrypt', 'No'))
                
                # Test connection with detailed feedback
                col_test1, col_test2 = st.columns([1, 1])
                
                with col_test1:
                    if st.button(f"🔍 Test {db_name.replace('sql_', '')} Connection", key=f"test_db_{db_name}"):
                        test_database_connection(db_config, db_name)
                
                with col_test2:
                    if st.button(f"🗑️ Remove {db_name.replace('sql_', '')}", key=f"remove_db_{db_name}"):
                        if remove_database_connection(credentials, db_name):
                            st.success(f"✅ Database connection '{db_name.replace('sql_', '')}' removed successfully!")
                            st.rerun()
                        else:
                            st.error("❌ Failed to remove database connection")
    else:
        st.info("🔍 No database connections configured. Add your first SQL Server connection below.")
    
    st.divider()
    
    # Add new database connection with enhanced UI
    st.write("### Add New SQL Server Connection")
    
    with st.expander("➕ Add New SQL Server Database Connection", expanded=False):
        st.markdown("**Configure a new SQL Server database connection for data operations**")
        
        with st.form("add_db_form"):
            # Basic connection details
            st.markdown("#### 🔧 **Connection Details**")
            
            col1, col2 = st.columns(2)
            
            with col1:
                db_name = st.text_input(
                    "Connection Name*", 
                    help="Unique identifier for this database connection (e.g., 'Production', 'Staging', 'Dev')"
                )
                server = st.text_input(
                    "Server Address*", 
                    help="SQL Server instance name or IP address (e.g., 'localhost', '192.168.1.100\\SQLEXPRESS')"
                )
                database = st.text_input(
                    "Database Name*", 
                    help="Name of the database to connect to"
                )
                port = st.text_input(
                    "Port", 
                    value="1433",
                    help="SQL Server port (default: 1433)"
                )
            
            with col2:
                # Auto-detect installed SQL Server drivers
                try:
                    import pyodbc as _pyodbc
                    installed_sql_drivers = [
                        d for d in _pyodbc.drivers()
                        if 'sql server' in d.lower() or 'sql native' in d.lower()
                    ]
                except Exception:
                    installed_sql_drivers = []

                driver_options = ["Auto-detect (recommended)"] + installed_sql_drivers + [
                    "{ODBC Driver 18 for SQL Server}",
                    "{ODBC Driver 17 for SQL Server}",
                    "{ODBC Driver 13 for SQL Server}",
                    "{SQL Server}",
                    "{SQL Server Native Client 11.0}"
                ]
                # Remove duplicates while preserving order
                seen = set()
                driver_options = [x for x in driver_options if not (x in seen or seen.add(x))]

                driver = st.selectbox(
                    "ODBC Driver (optional)",
                    driver_options,
                    index=0,
                    help="Auto-detect will pick the best available driver on this machine. You can also choose manually."
                )
                
                encrypt = st.selectbox(
                    "Encryption",
                    ["no", "yes", "strict"],
                    index=0,
                    help="Connection encryption level"
                )
                
                trust_server_cert = st.checkbox(
                    "Trust Server Certificate",
                    value=False,
                    help="Trust the server certificate (use with caution in production)"
                )
                
                connection_timeout = st.number_input(
                    "Connection Timeout (seconds)",
                    min_value=5,
                    max_value=300,
                    value=30,
                    help="Maximum time to wait for connection"
                )
            
            st.divider()
            
            # Authentication section
            st.markdown("#### 🔐 **Authentication Settings**")
            
            auth_type = st.radio(
                "Authentication Type",
                ["Windows Authentication", "SQL Server Authentication"],
                help="Choose authentication method"
            )
            
            if auth_type == "SQL Server Authentication":
                col_auth1, col_auth2 = st.columns(2)
                
                with col_auth1:
                    username = st.text_input(
                        "Username*", 
                        help="SQL Server username"
                    )
                
                with col_auth2:
                    password = st.text_input(
                        "Password*", 
                        type="password", 
                        help="SQL Server password"
                    )
            else:
                username = ""
                password = ""
                st.info("ℹ️ Windows Authentication will use your current Windows credentials")
            
            st.divider()
            
            # Advanced settings
            with st.expander("⚙️ Advanced Settings", expanded=False):
                col_adv1, col_adv2 = st.columns(2)
                
                with col_adv1:
                    application_name = st.text_input(
                        "Application Name",
                        value="DM_Toolkit",
                        help="Application name for connection tracking"
                    )
                    
                    mars_connection = st.checkbox(
                        "Enable MARS",
                        value=False,
                        help="Multiple Active Result Sets"
                    )
                
                with col_adv2:
                    command_timeout = st.number_input(
                        "Command Timeout (seconds)",
                        min_value=30,
                        max_value=3600,
                        value=300,
                        help="Maximum time to wait for command execution"
                    )
                    
                    auto_commit = st.checkbox(
                        "Auto Commit",
                        value=True,
                        help="Automatically commit transactions"
                    )
            
            # Test connection before saving
            col_submit1, col_submit2 = st.columns([1, 2])
            
            with col_submit1:
                test_before_save = st.form_submit_button("🔍 Test Connection")
            
            with col_submit2:
                submit_db = st.form_submit_button("✅ Save Database Connection", type="primary")
            
            # Handle test connection
            if test_before_save:
                if db_name and server and database:
                    # Create temporary config for testing
                    test_config = create_db_config(
                        server, database, username, password, driver, port,
                        auth_type == "Windows Authentication", encrypt, trust_server_cert,
                        connection_timeout, application_name, mars_connection, 
                        command_timeout, auto_commit
                    )
                    
                    st.write("#### 🧪 Testing Connection...")
                    test_database_connection(test_config, f"Test_{db_name}")
                else:
                    st.error("❌ Please fill in required fields (Connection Name, Server, Database)")
            
            # Handle save connection
            if submit_db:
                if db_name and server and database:
                    if auth_type == "SQL Server Authentication" and (not username or not password):
                        st.error("❌ Username and password are required for SQL Server Authentication")
                    else:
                        # Create database config
                        new_db_config = create_db_config(
                            server, database, username, password, driver, port,
                            auth_type == "Windows Authentication", encrypt, trust_server_cert,
                            connection_timeout, application_name, mars_connection, 
                            command_timeout, auto_commit
                        )
                        
                        # Check if connection name already exists
                        if f"sql_{db_name}" in credentials:
                            st.error(f"❌ Database connection '{db_name}' already exists! Please choose a different name.")
                        else:
                            # Save to credentials
                            if save_credentials(credentials, f"sql_{db_name}", new_db_config):
                                # Show success with balloons effect
                                st.balloons()
                                st.success(f"🎉 **Database connection '{db_name}' created successfully!**")
                                
                                # Show detailed success information
                                st.markdown(f"""
                                **✅ What happened:**
                                - New SQL Server connection saved securely
                                - Connection added to your available databases list
                                - You can now use it in Data Operations for extraction and loading
                                
                                **🚀 Next steps:**
                                1. Go to Data Operations → SQL Server tab
                                2. Select '{db_name}' from the database dropdown
                                3. Test queries and data operations
                                4. Use for data extraction or loading operations
                                """)
                                
                                # Auto-refresh after showing success
                                import time
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error("❌ Failed to save database connection")
                else:
                    st.error("❌ Please fill in all required fields (Connection Name, Server, Database)")

def show_directory_structure():
    """Show and manage directory structure"""
    st.subheader("📁 Directory Structure")
    
    project_root = os.path.dirname(os.path.dirname(__file__))
    
    # Display current directory structure
    st.write("### Current Project Structure")
    
    required_directories = [
        "DataFiles",
        "DataLoader_Logs", 
        "mapping_logs",
        "Validation",
        "Unit Testing Generates",
        "Services"
    ]
    
    dir_status = []
    for dir_name in required_directories:
        dir_path = os.path.join(project_root, dir_name)
        if os.path.exists(dir_path):
            # Count files in directory
            file_count = sum([len(files) for _, _, files in os.walk(dir_path)])
            dir_status.append({
                "Directory": dir_name,
                "Status": "✅ Exists",
                "Files": file_count,
                "Path": dir_path
            })
        else:
            dir_status.append({
                "Directory": dir_name,
                "Status": "❌ Missing",
                "Files": 0,
                "Path": dir_path
            })
    
    df_dirs = pd.DataFrame(dir_status)
    st.dataframe(df_dirs, use_container_width=True)
    
    st.divider()
    
    # Create missing directories
    st.write("### Directory Management")
    
    missing_dirs = [d for d in dir_status if "Missing" in d["Status"]]
    
    if missing_dirs:
        st.warning(f"Found {len(missing_dirs)} missing directories")
        
        if st.button("🔨 Create Missing Directories"):
            created_count = 0
            for dir_info in missing_dirs:
                try:
                    os.makedirs(dir_info["Path"], exist_ok=True)
                    created_count += 1
                    st.success(f"✅ Created: {dir_info['Directory']}")
                except Exception as e:
                    st.error(f"❌ Failed to create {dir_info['Directory']}: {str(e)}")
            
            if created_count > 0:
                st.success(f"Successfully created {created_count} directories!")
                st.rerun()
    else:
        st.success("✅ All required directories exist")
    
    # Cleanup options
    st.write("### Cleanup Options")
    
    with st.expander("🧹 Cleanup Tools", expanded=False):
        st.warning("⚠️ These operations will permanently delete files. Use with caution!")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🗑️ Clear Log Files", key="clear_logs"):
                if clear_log_files():
                    st.success("Log files cleared successfully")
                else:
                    st.error("Error clearing log files")
        
        with col2:
            if st.button("🗑️ Clear Temp Files", key="clear_temp"):
                if clear_temp_files():
                    st.success("Temporary files cleared successfully")
                else:
                    st.error("Error clearing temporary files")

def show_system_settings():
    """Show system-wide settings"""
    st.subheader("🔧 System Settings")
    
    # Batch processing settings
    st.write("### Default Batch Processing Settings")
    
    col1, col2 = st.columns(2)
    
    with col1:
        default_batch_size = st.number_input(
            "Default Batch Size",
            min_value=1,
            max_value=10000,
            value=2000,
            help="Default number of records per batch"
        )
        
        max_parallel_batches = st.number_input(
            "Max Parallel Batches",
            min_value=1,
            max_value=10,
            value=3,
            help="Maximum number of batches to process in parallel"
        )
    
    with col2:
        log_level = st.selectbox(
            "Log Level",
            ["DEBUG", "INFO", "WARNING", "ERROR"],
            index=1,
            help="Minimum log level to record"
        )
        
        auto_cleanup = st.checkbox(
            "Auto Cleanup",
            value=False,
            help="Automatically clean up old log files"
        )
    
    # File handling settings
    st.write("### File Handling Settings")
    
    col3, col4 = st.columns(2)
    
    with col3:
        max_file_size_mb = st.number_input(
            "Max File Size (MB)",
            min_value=1,
            max_value=1000,
            value=100,
            help="Maximum file size for uploads"
        )
    
    with col4:
        backup_enabled = st.checkbox(
            "Enable Backups",
            value=True,
            help="Create backups before processing"
        )
    
    # Save settings
    if st.button("💾 Save Settings", use_container_width=True):
        settings = {
            "batch_size": default_batch_size,
            "max_parallel_batches": max_parallel_batches,
            "log_level": log_level,
            "auto_cleanup": auto_cleanup,
            "max_file_size_mb": max_file_size_mb,
            "backup_enabled": backup_enabled
        }
        
        if save_system_settings(settings):
            st.success("✅ Settings saved successfully!")
            show_processing_status("settings_save", "System settings updated", "success")
        else:
            st.error("❌ Failed to save settings")

def _resolve_driver(driver_setting: str) -> str:
    """
    Resolve driver string. If 'Auto-detect', pick the best installed SQL Server driver.
    Priority: ODBC 18 > 17 > 13 > Native Client > SQL Server
    """
    if driver_setting and driver_setting != 'Auto-detect (recommended)':
        return driver_setting
    try:
        import pyodbc
        installed = [d for d in pyodbc.drivers() if 'sql server' in d.lower() or 'sql native' in d.lower()]
        priority = [
            'ODBC Driver 18 for SQL Server',
            'ODBC Driver 17 for SQL Server',
            'ODBC Driver 13 for SQL Server',
            'SQL Server Native Client 11.0',
            'SQL Server',
        ]
        for preferred in priority:
            for d in installed:
                if preferred.lower() in d.lower():
                    return '{' + d + '}' if not d.startswith('{') else d
        if installed:
            d = installed[0]
            return '{' + d + '}' if not d.startswith('{') else d
    except Exception:
        pass
    return '{ODBC Driver 17 for SQL Server}'


def test_database_connection(db_config: Dict, db_name: str):
    """Test database connection with enhanced feedback"""
    try:
        import pyodbc
        
        with st.spinner(f"Testing connection to {db_name.replace('sql_', '')}..."):
            # Resolve driver (handles Auto-detect)
            resolved_driver = _resolve_driver(db_config.get('driver', 'Auto-detect (recommended)'))

            # Build connection string
            connection_string = f"DRIVER={resolved_driver};SERVER={db_config['server']};DATABASE={db_config['database']}"

            # Add port if specified
            if db_config.get('port') and db_config.get('port') != '1433':
                if '\\' not in db_config['server']:  # Only add port if not using named instance
                    connection_string = f"DRIVER={resolved_driver};SERVER={db_config['server']},{db_config['port']};DATABASE={db_config['database']}"
            
            # Add authentication
            if db_config.get('Trusted_Connection') == 'yes':
                connection_string += ";Trusted_Connection=yes"
            else:
                connection_string += f";UID={db_config['username']};PWD={db_config['password']}"
            
            # Add encryption settings
            encrypt_val = db_config.get('encrypt', 'no')
            if encrypt_val and str(encrypt_val).lower() not in ('no', 'false', ''):
                connection_string += f";Encrypt={encrypt_val}"

            # TrustServerCertificate: respect explicit setting OR auto-enable for Azure SQL with older drivers
            trust_cert = db_config.get('trust_server_cert', False)
            is_azure = '.database.windows.net' in db_config.get('server', '')
            older_driver = any(d in db_config.get('driver', '') for d in ['13', '11', 'Native', 'SQL Server}'])
            if trust_cert or (is_azure and older_driver):
                connection_string += ";TrustServerCertificate=yes"

            # Add timeout
            if db_config.get('connection_timeout'):
                connection_string += f";Connection Timeout={db_config['connection_timeout']}"

            # Add application name
            if db_config.get('application_name'):
                connection_string += f";APP={db_config['application_name']}"
            
            # Test connection
            with pyodbc.connect(connection_string) as conn:
                cursor = conn.cursor()
                
                # Test basic query
                cursor.execute("SELECT @@VERSION as sql_version, DB_NAME() as current_db, SYSTEM_USER as connected_user")
                result = cursor.fetchone()
                
                if result:
                    st.success("✅ **Database connection successful!**")
                    
                    # Show detailed connection info
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.info(f"**Database:** {result.current_db}")
                        st.info(f"**Connected User:** {result.connected_user}")
                    
                    with col2:
                        # Get table count
                        cursor.execute("SELECT COUNT(*) as table_count FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'")
                        table_result = cursor.fetchone()
                        st.info(f"**Tables Available:** {table_result.table_count}")
                        
                        # Test permissions
                        try:
                            cursor.execute("SELECT 1")
                            st.info("**Permissions:** ✅ Read Access")
                        except:
                            st.warning("**Permissions:** ⚠️ Limited Access")
                    
                    # Show SQL Server version info
                    with st.expander("📊 SQL Server Details", expanded=False):
                        st.text(result.sql_version)
                    
                    show_processing_status("db_connection_test", f"Successfully connected to {db_name.replace('sql_', '')}", "success")
                else:
                    st.error("❌ Database connection failed - no response from server")
                    
    except ImportError:
        st.error("❌ **pyodbc module not installed**")
        st.markdown("""
        **To fix this issue:**
        ```bash
        pip install pyodbc
        ```
        """)
    except pyodbc.Error as e:
        st.error(f"❌ **Database connection failed**")

        # Parse error for better user guidance
        # NOTE: checks must come BEFORE the driver check because pyodbc always
        # embeds the driver name in the error text, e.g. "[ODBC Driver 18 for SQL Server]"
        # which would make "driver" in error_msg match every single error.
        error_msg = str(e)
        st.code(error_msg, language="text")  # Always show full error for diagnosis

        if "40615" in error_msg or "IP address" in error_msg:
            st.warning("🔥 **Firewall Issue:** Your IP is not whitelisted on the Azure SQL Server. Add it in Azure Portal → SQL Server → Networking → Firewall rules.")
        elif "SSL" in error_msg or "certificate" in error_msg.lower() or "TLS" in error_msg:
            st.warning("🔒 **SSL Issue:** Enable 'Trust Server Certificate' in Advanced Settings and retry.")
        elif "Login failed" in error_msg:
            st.warning("🔐 **Authentication Issue:** Check username and password")
        elif "server was not found" in error_msg or "network-related" in error_msg:
            st.warning("🌐 **Server Issue:** Check server address and network connectivity")
        elif "database" in error_msg.lower() and "does not exist" in error_msg.lower():
            st.warning("🗄️ **Database Issue:** Check database name")
        elif "IM002" in error_msg or "data source name not found" in error_msg.lower():
            st.warning("🔧 **Driver Issue:** The selected ODBC driver is not installed on this machine.")
        else:
            st.warning(f"**Error Details:** {error_msg}")
            
        # Show troubleshooting tips
        with st.expander("🔧 Troubleshooting Tips", expanded=False):
            st.markdown("""
            **Common Solutions:**
            
            1. **Authentication Issues:**
               - Verify username and password
               - Try Windows Authentication if available
               - Check if account is locked or expired
            
            2. **Connection Issues:**
               - Verify server name and port
               - Check if SQL Server is running
               - Verify network connectivity
               - Check firewall settings
            
            3. **Driver Issues:**
               - Install Microsoft ODBC Driver for SQL Server
               - Try different driver version
               - Restart application after driver installation
            
            4. **Database Issues:**
               - Verify database exists
               - Check database permissions
               - Ensure database is online
            """)
            
    except Exception as e:
        st.error(f"❌ **Unexpected error:** {str(e)}")

def create_db_config(server: str, database: str, username: str, password: str, driver: str, 
                    port: str, use_windows_auth: bool, encrypt: str, trust_server_cert: bool,
                    connection_timeout: int, application_name: str, mars_connection: bool,
                    command_timeout: int, auto_commit: bool) -> Dict:
    """Create database configuration dictionary"""
    config = {
        "server": server,
        "database": database,
        "driver": driver,
        "port": port if port != "1433" else "",
        "encrypt": encrypt,
        "trust_server_cert": trust_server_cert,
        "connection_timeout": connection_timeout,
        "application_name": application_name,
        "mars_connection": mars_connection,
        "command_timeout": command_timeout,
        "auto_commit": auto_commit
    }
    
    if use_windows_auth:
        config["Trusted_Connection"] = "yes"
        config["username"] = ""
        config["password"] = ""
    else:
        config["username"] = username
        config["password"] = password
        config["Trusted_Connection"] = "no"
    
    return config

def remove_database_connection(credentials: Dict, db_name: str) -> bool:
    """Remove database connection from credentials"""
    try:
        if db_name in credentials:
            del credentials[db_name]
            
            # Save updated credentials to file
            creds_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), 
                'Services', 
                'linkedservices.json'
            )
            
            with open(creds_path, 'w') as f:
                json.dump(credentials, f, indent=2)
            
            # Update session state
            if 'credentials' in st.session_state:
                st.session_state.credentials = credentials
            
            return True
        else:
            return False
            
    except Exception as e:
        st.error(f"Error removing database connection: {str(e)}")
        return False

def save_credentials(credentials: Dict, org_name: str, new_creds: Dict) -> bool:
    """Save updated credentials to file and refresh session state"""
    try:
        credentials[org_name] = new_creds
        
        creds_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            'Services', 
            'linkedservices.json'
        )
        
        # Save to file
        with open(creds_path, 'w') as f:
            json.dump(credentials, f, indent=2)
        
        # CRITICAL FIX: Update session state with the new org
        if 'available_orgs' not in st.session_state:
            st.session_state.available_orgs = []
        
        # Add new org to available orgs if it's not already there
        if org_name not in st.session_state.available_orgs:
            st.session_state.available_orgs.append(org_name)
        
        # Also refresh the complete credentials in session state if it exists
        if 'credentials' in st.session_state:
            st.session_state.credentials = credentials
            
        # Success feedback
        st.info(f"📁 Credentials saved to: {creds_path}")
        st.info(f"🔄 Session state updated with {len(st.session_state.available_orgs)} organizations")
        
        return True
    except Exception as e:
        st.error(f"❌ Error saving credentials: {str(e)}")
        return False

def save_system_settings(settings: Dict) -> bool:
    """Save system settings to file"""
    try:
        settings_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            'system_settings.json'
        )
        
        with open(settings_path, 'w') as f:
            json.dump(settings, f, indent=2)
        
        return True
    except Exception as e:
        st.error(f"Error saving settings: {str(e)}")
        return False

def clear_log_files() -> bool:
    """Clear log files"""
    try:
        logs_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'DataLoader_Logs')
        if os.path.exists(logs_path):
            for root, dirs, files in os.walk(logs_path):
                for file in files:
                    if file.endswith('.log') or 'log' in file.lower():
                        os.remove(os.path.join(root, file))
        return True
    except Exception:
        return False

def clear_temp_files() -> bool:
    """Clear temporary files"""
    try:
        temp_extensions = ['.tmp', '.temp', '.bak']
        project_root = os.path.dirname(os.path.dirname(__file__))
        
        for root, dirs, files in os.walk(project_root):
            for file in files:
                if any(file.lower().endswith(ext) for ext in temp_extensions):
                    os.remove(os.path.join(root, file))
        return True
    except Exception:
        return False