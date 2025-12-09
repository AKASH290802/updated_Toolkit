import streamlit as st
import simple_salesforce as sf
import pandas as pd
import json
import os
import sys
from typing import Dict, List, Optional, Tuple

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

def establish_sf_connection(credentials: Dict, org_name: str) -> Optional[sf.Salesforce]:
    """Establish Salesforce connection for the selected org"""
    try:
        if org_name not in credentials:
            st.error(f"Organization '{org_name}' not found in credentials")
            return None
            
        creds = credentials[org_name]
        
        # Check if connection already exists in session state for the SAME org
        if (st.session_state.get('sf_connection') and 
            st.session_state.get('connected_org') == org_name):
            # Test if connection is still valid
            try:
                st.session_state.sf_connection.query("SELECT Id FROM Organization LIMIT 1")
                return st.session_state.sf_connection
            except:
                # Connection is stale, will create new one
                pass
        
        with st.spinner(f"Connecting to {org_name}..."):
            sf_conn = sf.Salesforce(
                username=creds['username'],
                password=creds['password'],
                security_token=creds.get('security_token', ''),
                domain=creds.get('domain', 'login')
            )
            
        # Store connection and the org it's connected to
        st.session_state.sf_connection = sf_conn
        st.session_state.connected_org = org_name
        st.success(f"✅ Connected to {org_name}")
        return sf_conn
        
    except Exception as e:
        st.error(f"❌ Failed to connect to {org_name}: {str(e)}")
        # Clear invalid connection from session state
        if 'sf_connection' in st.session_state:
            del st.session_state.sf_connection
        if 'connected_org' in st.session_state:
            del st.session_state.connected_org
        return None

def get_salesforce_objects(sf_conn: sf.Salesforce, filter_custom: bool = False) -> List[str]:
    """Get list of Salesforce objects"""
    if sf_conn is None:
        st.error("❌ No Salesforce connection available")
        return []
    
    try:
        with st.spinner("Fetching Salesforce objects..."):
            # Get all objects from the org
            describe_result = sf_conn.describe()
            
            if not describe_result or 'sobjects' not in describe_result:
                st.error("❌ Failed to retrieve object list from Salesforce")
                return []
            
            objects_data = describe_result['sobjects']
            object_names = [obj['name'] for obj in objects_data if obj.get('name')]
            
            if filter_custom:
                # Filter for Account and custom objects (ending with __c) and some common objects
                filtered_objects = []
                for name in object_names:
                    if (name.lower() == 'account' or 
                        name.endswith('__c') or 
                        'wod' in name.lower() or
                        name in ['Contact', 'Lead', 'Opportunity', 'Case']):
                        filtered_objects.append(name)
                
                st.info(f"Found {len(filtered_objects)} eligible objects (Account, custom objects, and common standard objects)")
                return sorted(filtered_objects)
            
            st.info(f"Found {len(object_names)} total objects in the organization")
            return sorted(object_names)
        
    except Exception as e:
        st.error(f"❌ Error fetching Salesforce objects: {str(e)}")
        st.error("Please check your connection and try again.")
        return []

def get_object_description(sf_conn: sf.Salesforce, object_name: str) -> Optional[Dict]:
    """Get detailed description of a Salesforce object"""
    try:
        return getattr(sf_conn, object_name).describe()
    except Exception as e:
        st.error(f"Error getting object description for {object_name}: {str(e)}")
        return None

def display_dataframe_with_download(df: pd.DataFrame, filename: str, title: str = "Data Preview"):
    """Display dataframe with download option"""
    if df is not None and not df.empty:
        st.subheader(title)
        
        # Display basic info
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Rows", len(df))
        with col2:
            st.metric("Total Columns", len(df.columns))
        with col3:
            st.metric("Memory Usage", f"{df.memory_usage(deep=True).sum() / 1024:.1f} KB")
        
        # Display dataframe
        st.dataframe(df, use_container_width=True, height=400)
        
        # Download button
        csv_data = df.to_csv(index=False)
        st.download_button(
            label=f"📥 Download {filename}",
            data=csv_data,
            file_name=filename,
            mime="text/csv",
            use_container_width=True
        )
    else:
        st.warning("No data to display")

def show_processing_status(status_key: str, message: str, status_type: str = "info"):
    """Show processing status with color coding"""
    if status_type == "success":
        st.success(f"✅ {message}")
    elif status_type == "error":
        st.error(f"❌ {message}")
    elif status_type == "warning":
        st.warning(f"⚠️ {message}")
    else:
        st.info(f"ℹ️ {message}")
    
    # Store in session state
    st.session_state.processing_status[status_key] = {
        'message': message,
        'type': status_type,
        'timestamp': pd.Timestamp.now()
    }

def create_progress_tracker(steps: List[str], current_step: int = 0):
    """Create a visual progress tracker"""
    st.subheader("📊 Process Progress")
    
    progress_percentage = (current_step / len(steps)) * 100 if steps else 0
    st.progress(progress_percentage / 100)
    
    for i, step in enumerate(steps):
        if i < current_step:
            st.success(f"✅ {step}")
        elif i == current_step:
            st.info(f"🔄 {step} (Current)")
        else:
            st.write(f"⏳ {step}")

def validate_file_upload(uploaded_file, allowed_extensions: List[str] = ['.csv', '.xlsx', '.xls']) -> bool:
    """Validate uploaded file"""
    if uploaded_file is None:
        return False
    
    file_extension = os.path.splitext(uploaded_file.name)[1].lower()
    if file_extension not in allowed_extensions:
        st.error(f"Invalid file type. Allowed: {', '.join(allowed_extensions)}")
        return False
    
    return True

def save_uploaded_file(uploaded_file, directory: str) -> str:
    """Save uploaded file to specified directory"""
    try:
        os.makedirs(directory, exist_ok=True)
        file_path = os.path.join(directory, uploaded_file.name)
        
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        return file_path
    except Exception as e:
        st.error(f"Error saving file: {str(e)}")
        return ""

def load_mapping_file(org_name: str, object_name: str) -> Optional[Dict]:
    """Load mapping file for specific org and object"""
    try:
        mapping_path = os.path.join(
            project_root, 'mapping_logs', org_name, object_name, 'mapping.json'
        )
        
        if os.path.exists(mapping_path):
            with open(mapping_path, 'r') as f:
                return json.load(f)
        else:
            return None
    except Exception as e:
        st.error(f"Error loading mapping file: {str(e)}")
        return None

def save_mapping_file(mapping_data: Dict, org_name: str, object_name: str) -> bool:
    """Save mapping file for specific org and object"""
    try:
        mapping_dir = os.path.join(project_root, 'mapping_logs', org_name, object_name)
        os.makedirs(mapping_dir, exist_ok=True)
        
        mapping_path = os.path.join(mapping_dir, 'mapping.json')
        with open(mapping_path, 'w') as f:
            json.dump(mapping_data, f, indent=2)
        
        return True
    except Exception as e:
        st.error(f"Error saving mapping file: {str(e)}")
        return False

def get_recent_logs(log_type: str = "all", limit: int = 100) -> List[Dict]:
    """Get recent log entries"""
    logs = []
    try:
        logs_base_path = os.path.join(project_root, 'DataLoader_Logs')
        
        if os.path.exists(logs_base_path):
            for root, dirs, files in os.walk(logs_base_path):
                for file in files:
                    if file.endswith('.csv') and 'log' in file.lower():
                        file_path = os.path.join(root, file)
                        try:
                            df = pd.read_csv(file_path)
                            if not df.empty:
                                logs.extend(df.to_dict('records')[-limit:])
                        except:
                            continue
    except Exception as e:
        st.error(f"Error loading logs: {str(e)}")
    
    return logs[-limit:] if logs else []

def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"

def show_error_summary(errors: List[str]):
    """Display error summary in an expandable section"""
    if errors:
        with st.expander(f"❌ Errors ({len(errors)})", expanded=False):
            for i, error in enumerate(errors, 1):
                st.error(f"{i}. {error}")

def create_download_zip(files: Dict[str, pd.DataFrame], zip_name: str):
    """Create downloadable zip file with multiple CSV files"""
    import zipfile
    import io
    
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for filename, df in files.items():
            csv_data = df.to_csv(index=False)
            zip_file.writestr(filename, csv_data)
    
    zip_buffer.seek(0)
    
    st.download_button(
        label=f"📦 Download {zip_name}",
        data=zip_buffer.getvalue(),
        file_name=zip_name,
        mime="application/zip",
        use_container_width=True
    )