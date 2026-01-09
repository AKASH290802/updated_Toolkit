import streamlit as st
import sys
import os
import json
import pandas as pd
from pathlib import Path

# Add project root to sys.path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)

# Import UI modules
from ui_components import (
    data_operations, 
    mapping_operations, 
    validation_operations, 
    unit_testing_operations,
    config_management,
    dashboard_overview,
    logs_reports,
    org_migration,
    object_comparison
)
from ui_components.data_hub import show_data_hub_interface, initialize_data_hub

# Page configuration
st.set_page_config(
    page_title="DM Toolkit - Data Migration & Validation",
    page_icon="🔄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        text-align: center;
        color: #1f77b4;
        font-size: 2.2rem;
        font-weight: 600;
        margin-bottom: 1.5rem;
        background: linear-gradient(90deg, #1f77b4, #2ca02c);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 8px 16px;
        border: 1px solid #e9ecef;
    }
    .stTabs [aria-selected="true"] {
        background-color: #1f77b4;
        color: white;
    }
    .status-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        margin: 0.5rem 0;
    }
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid #1f77b4;
    }
</style>
""", unsafe_allow_html=True)

def initialize_session_state():
    """Initialize session state variables"""
    if 'current_org' not in st.session_state:
        st.session_state.current_org = None
    if 'current_sql_connection' not in st.session_state:
        st.session_state.current_sql_connection = None
    if 'current_object' not in st.session_state:
        st.session_state.current_object = None
    if 'sf_connection' not in st.session_state:
        st.session_state.sf_connection = None
    if 'sql_connection' not in st.session_state:
        st.session_state.sql_connection = None
    if 'connected_org' not in st.session_state:
        st.session_state.connected_org = None
    if 'connected_sql' not in st.session_state:
        st.session_state.connected_sql = None
    if 'available_orgs' not in st.session_state:
        st.session_state.available_orgs = []
    if 'available_sql_connections' not in st.session_state:
        st.session_state.available_sql_connections = []
    if 'processing_status' not in st.session_state:
        st.session_state.processing_status = {}
    if 'active_page' not in st.session_state:
        st.session_state.active_page = "🏠 Dashboard"

def load_credentials():
    """Load credentials from linkedservices.json"""
    try:
        creds_path = os.path.join(project_root, 'Services', 'linkedservices.json')
        if os.path.exists(creds_path):
            with open(creds_path, 'r') as f:
                creds = json.load(f)
            
            # Separate Salesforce orgs and SQL connections
            sf_orgs = {k: v for k, v in creds.items() if 'username' in v and 'sql' not in k.lower()}
            sql_connections = {k: v for k, v in creds.items() if 'sql' in k.lower()}
            
            # Update session state
            st.session_state.available_orgs = list(sf_orgs.keys())
            st.session_state.available_sql_connections = list(sql_connections.keys())
            
            return creds
        else:
            st.error("Credentials file not found. Please ensure linkedservices.json exists in the Services folder.")
            return {}
    except Exception as e:
        st.error(f"Error loading credentials: {str(e)}")
        return {}

def main():
    """Main application function"""
    
    # Initialize session state
    initialize_session_state()
    
    # Load credentials and store in session state for dynamic updates
    credentials = load_credentials()
    st.session_state.credentials = credentials  # Store for config management updates
    
    # Main header
    st.markdown('<h1 class="main-header">🔄 DM Toolkit</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; color: #666; margin-bottom: 2rem;">Data Migration & Validation Platform</p>', unsafe_allow_html=True)
    
    # Sidebar navigation
    with st.sidebar:
        st.markdown("### 🧭 Navigation")
        
        # Global organization selection
        if st.session_state.available_orgs:
            st.markdown("#### 🏢 Select Organization")
            
            col1, col2 = st.columns([3, 1])
            with col1:
                selected_org = st.selectbox(
                    "Choose your Salesforce org:",
                    options=["Select an organization..."] + st.session_state.available_orgs,
                    key="global_org_selector",
                    help="Select a Salesforce organization to work with"
                )
            
            with col2:
                if st.button("🔄", help="Refresh org list", key="refresh_orgs"):
                    # Reload credentials and refresh org list
                    fresh_credentials = load_credentials()
                    st.session_state.credentials = fresh_credentials
                    
                    # Count orgs before and after
                    old_count = len(st.session_state.available_orgs) if st.session_state.available_orgs else 0
                    new_count = len(st.session_state.available_orgs)
                    
                    if new_count > old_count:
                        st.success(f"🎉 Found {new_count - old_count} new organization(s)!")
                    else:
                        st.success("✅ Organization list refreshed!")
                    
                    st.rerun()
            
            if selected_org != "Select an organization..." and selected_org != st.session_state.current_org:
                # Check if this is a newly created org (not in previous session)
                was_new_org = st.session_state.current_org is None
                
                st.session_state.current_org = selected_org
                # Clear connection and object when org changes
                st.session_state.sf_connection = None
                st.session_state.connected_org = None
                st.session_state.current_object = None
                
                if was_new_org:
                    st.success(f"🎉 Welcome! Selected your new organization: **{selected_org}**")
                    st.info("💡 You can now use this organization across all modules")
                else:
                    st.success(f"✅ Switched to: **{selected_org}**")
                
                st.rerun()
        else:
            st.error("❌ No organizations found in credentials")
        
        st.divider()
        
        # Global SQL Server connection selection
        if st.session_state.available_sql_connections:
            st.markdown("#### 🗄️ Select SQL Server Connection")
            
            col1, col2 = st.columns([3, 1])
            with col1:
                # Create display names for SQL connections
                sql_connection_options = ["Select a SQL connection..."] + [
                    f"{k.replace('sql_', '').upper()}" 
                    for k in st.session_state.available_sql_connections
                ]
                sql_connection_keys = [""] + st.session_state.available_sql_connections
                
                selected_sql_display = st.selectbox(
                    "Choose your SQL Server:",
                    options=sql_connection_options,
                    key="global_sql_selector",
                    help="Select a SQL Server connection to work with"
                )
                
                # Get the actual key
                selected_sql = ""
                if selected_sql_display != "Select a SQL connection...":
                    selected_index = sql_connection_options.index(selected_sql_display)
                    selected_sql = sql_connection_keys[selected_index]
            
            with col2:
                if st.button("🔄", help="Refresh SQL connections", key="refresh_sql"):
                    # Reload credentials and refresh SQL connections
                    fresh_credentials = load_credentials()
                    st.session_state.credentials = fresh_credentials
                    
                    # Count connections before and after
                    old_count = len(st.session_state.available_sql_connections) if st.session_state.available_sql_connections else 0
                    new_count = len(st.session_state.available_sql_connections)
                    
                    if new_count > old_count:
                        st.success(f"🎉 Found {new_count - old_count} new SQL connection(s)!")
                    else:
                        st.success("✅ SQL connections refreshed!")
                    
                    st.rerun()
            
            if selected_sql and selected_sql != st.session_state.current_sql_connection:
                # Check if this is a newly created connection
                was_new_sql = st.session_state.current_sql_connection is None
                
                st.session_state.current_sql_connection = selected_sql
                
                # Clear any existing SQL connection when connection changes
                if 'sql_connection' in st.session_state:
                    del st.session_state.sql_connection
                if 'connected_sql' in st.session_state:
                    del st.session_state.connected_sql
                
                # Show selection confirmation
                display_name = selected_sql.replace('sql_', '').upper()
                if was_new_sql:
                    st.success(f"🎉 Welcome! Selected your SQL Server: **{display_name}**")
                    st.info("💡 You can now use this connection across all modules")
                else:
                    st.success(f"✅ Switched to SQL Server: **{display_name}**")
                    
                st.rerun()
        else:
            st.info("💡 No SQL Server connections configured. Go to Configuration → Database Settings to add them.")
        
        st.divider()
        
        # Navigation menu
        st.markdown("#### 📋 Modules")
        
        # Page list for consistent referencing
        page_list = [
            "🏠 Dashboard",
            "⚙️ Configuration",
            "📊 Data Hub",
            "1️⃣ Validation",
            "2️⃣ Data Operations",
            "3️⃣ Unit Testing",
            "🗺️ Mapping",
            "🔄 Org Migration",
            "🔍 Object Comparison",
            "📋 Logs & Reports"
        ]
        
        # Initialize active_page if not exists
        if 'active_page' not in st.session_state:
            st.session_state.active_page = "🏠 Dashboard"
        
        # Ensure active_page is valid
        if st.session_state.active_page not in page_list:
            st.session_state.active_page = "🏠 Dashboard"
        
        # Get current index for radio button
        current_index = page_list.index(st.session_state.active_page)
        
        # Use a unique key that changes when session state changes to force radio refresh
        nav_key = f"nav_{st.session_state.active_page.replace(' ', '_').replace('️⃣', '')}"
        
        page = st.radio(
            "Choose a module:",
            page_list,
            index=current_index,
            key=nav_key
        )
        
        # Update active page when navigation changes
        st.session_state.active_page = page
        
        # Debug info (uncomment for troubleshooting navigation issues)
        # st.sidebar.caption(f"Debug: Current page = {st.session_state.active_page}")
        
        st.divider()
        
        # Status display
        st.markdown("#### 📊 Current Status")
        if st.session_state.current_org:
            st.markdown(f'<div class="status-card">🏢 <strong>{st.session_state.current_org}</strong></div>', unsafe_allow_html=True)
        else:
            st.warning("⚠️ No organization selected")
            
        if st.session_state.current_object:
            st.success(f"🎯 **Current Object:** {st.session_state.current_object}")
        else:
            st.info("📋 **Current Object:** None selected")
        
        # Connection status
        if st.session_state.sf_connection and st.session_state.connected_org:
            st.success(f"🔗 Connected to {st.session_state.connected_org}")
        elif st.session_state.current_org:
            st.info("🔌 Ready to connect")
    
    # Main content area - use session state as the source of truth
    current_page = st.session_state.active_page
    
    # Use session state credentials (may be updated by config management)
    current_credentials = st.session_state.get('credentials', credentials)
    
    # Initialize Data Hub
    data_hub = initialize_data_hub()
    
    if current_page == "🏠 Dashboard":
        dashboard_overview.show_dashboard(current_credentials)
    elif current_page == "⚙️ Configuration":
        config_management.show_configuration(current_credentials)
    elif current_page == "📊 Data Hub":
        show_data_hub_interface(st.session_state.get('sf_connection', None))
    elif current_page == "1️⃣ Validation":
        validation_operations.show_validation_operations(current_credentials)
    elif current_page == "2️⃣ Data Operations":
        data_operations.show_data_operations(current_credentials)
    elif current_page == "3️⃣ Unit Testing":
        unit_testing_operations.show_unit_testing(current_credentials)
    elif current_page == "🗺️ Mapping":
        mapping_operations.show_mapping_operations(current_credentials)
    elif current_page == "🔄 Org Migration":
        org_migration.show_org_migration(current_credentials)
    elif current_page == "🔍 Object Comparison":
        object_comparison.show_object_comparison()
    elif current_page == "📋 Logs & Reports":
        logs_reports.show_logs_reports()

if __name__ == "__main__":
    main()