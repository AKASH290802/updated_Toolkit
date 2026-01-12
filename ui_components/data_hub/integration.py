"""
Data Hub Integration Helpers
=============================
Utility functions for other modules to use Data Hub
"""

import streamlit as st
import pandas as pd
from typing import Optional, Dict, Any


def get_data_from_hub() -> Optional[pd.DataFrame]:
    """
    Get active dataset from Data Hub
    
    Use in any module that needs data:
    
    Usage:
        from ui_components.data_hub.integration import get_data_from_hub
        
        df = get_data_from_hub()
        if df is not None:
            # Use data
            st.dataframe(df)
        else:
            st.warning("Please load data from Data Hub first")
    
    Returns:
        DataFrame or None if no active dataset
    """
    if 'data_hub' in st.session_state:
        return st.session_state.data_hub.get_active_dataset()
    return None


def get_data_info() -> Optional[Dict[str, Any]]:
    """
    Get info about active dataset
    
    Returns:
        Dict with 'name' and 'metadata' keys, or None
    """
    if 'data_hub' in st.session_state:
        return st.session_state.data_hub.get_active_dataset_info()
    return None


def has_data() -> bool:
    """
    Check if active dataset exists
    
    Usage:
        from ui_components.data_hub.integration import has_data
        
        if has_data():
            # User has loaded data
            df = get_data_from_hub()
        else:
            st.info("Please load data from Data Hub first")
    
    Returns:
        True if active dataset exists, False otherwise
    """
    if 'data_hub' in st.session_state:
        return st.session_state.data_hub.has_active_dataset()
    return False


def show_data_source_info():
    """
    Display active dataset source information
    
    Call this in your module's UI to show user what data they're working with
    
    Usage:
        from ui_components.data_hub.integration import show_data_source_info
        
        st.subheader("Data Configuration")
        show_data_source_info()
    """
    data_info = get_data_info()
    
    if data_info is None:
        st.warning("⚠️ No active dataset selected. Please load data from Data Hub first.")
        st.info("💡 Go to **📊 Data Hub** tab to upload a file or query Salesforce.")
        return False
    
    # Display data source info
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("📊 Dataset", data_info['name'])
    with col2:
        st.metric("📦 Rows", data_info['metadata']['row_count'])
    with col3:
        st.metric("📋 Columns", data_info['metadata']['column_count'])
    
    # Show source details
    st.caption(f"Source: {data_info['metadata']['source_type'].replace('_', ' ').title()}")
    
    return True


def validate_data_available(module_name: str) -> bool:
    """
    Validate that data is available and show helpful message if not
    
    Usage:
        from ui_components.data_hub.integration import validate_data_available
        
        if not validate_data_available("Enhanced Validation"):
            st.stop()
        
        # Now proceed with processing
        df = get_data_from_hub()
    
    Args:
        module_name: Name of the module using this check (e.g., "Enhanced Validation")
    
    Returns:
        True if data is available, False otherwise
    """
    if not has_data():
        st.error(f"❌ {module_name} requires data to be loaded")
        st.info("""
        **Steps to use this module:**
        1. Go to the **📊 Data Hub** tab
        2. Load data from either:
           - **Upload File** (CSV or Excel)
           - **Query Salesforce** (SOQL query)
        3. Return to this module and start working with your data
        """)
        return False
    
    return True


def get_data_summary() -> str:
    """
    Get a summary string of the active dataset
    
    Usage:
        summary = get_data_summary()
        st.write(f"Working with: {summary}")
    
    Returns:
        Summary string like "Dataset_Name (251 rows, 36 columns, loaded at 10:30)"
    """
    data_info = get_data_info()
    
    if data_info is None:
        return "No active dataset"
    
    from datetime import datetime
    name = data_info['name']
    rows = data_info['metadata']['row_count']
    cols = data_info['metadata']['column_count']
    timestamp = datetime.fromisoformat(data_info['metadata']['timestamp'])
    time_str = timestamp.strftime("%H:%M:%S")
    
    return f"{name} ({rows} rows, {cols} columns, loaded at {time_str})"
