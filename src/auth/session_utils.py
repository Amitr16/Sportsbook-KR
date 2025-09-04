"""
Session utility functions for namespaced session management.
This prevents cross-tab logouts by using targeted session operations instead of session.clear().
"""

from flask import session

# Session key constants
SUPERADMIN_KEY = "sid:_superadmin"
TENANT_KEY_PREFIX = "sid:"

def tenant_key(tenant: str) -> str:
    """Generate a namespaced session key for a tenant"""
    return f"{TENANT_KEY_PREFIX}{tenant}"

def log_in_tenant(tenant: str, payload: dict):
    """Store tenant session data with namespaced key"""
    session[tenant_key(tenant)] = payload

def log_out_tenant(tenant: str):
    """Remove only tenant session data, leaving superadmin intact"""
    session.pop(tenant_key(tenant), None)

def log_in_superadmin(payload: dict):
    """Store superadmin session data with namespaced key"""
    session[SUPERADMIN_KEY] = payload

def log_out_superadmin():
    """Remove only superadmin session data, leaving tenant sessions intact"""
    session.pop(SUPERADMIN_KEY, None)

def clear_operator_session(subdomain: str = None):
    """Clear operator-specific session data (for admin/operator logouts)"""
    if subdomain:
        # Clear specific operator session
        session.pop(tenant_key(subdomain), None)
    # Clear operator-specific keys that might exist
    session.pop('operator_id', None)
    session.pop('operator_login', None)
    session.pop('operator_subdomain', None)
    session.pop('operator_name', None)

def is_superadmin_logged_in() -> bool:
    """Check if superadmin is logged in"""
    return SUPERADMIN_KEY in session

def is_tenant_logged_in(tenant: str) -> bool:
    """Check if a specific tenant is logged in"""
    return tenant_key(tenant) in session

def get_superadmin_session():
    """Get superadmin session data"""
    return session.get(SUPERADMIN_KEY)

def get_tenant_session(tenant: str):
    """Get tenant session data"""
    return session.get(tenant_key(tenant))
