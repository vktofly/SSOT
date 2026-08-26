"""
Frontend Authentication & Session State Management for Streamlit.
Provides session initialization, OAuth/Mock login, token storage, role-based page guards,
and a modern Identity Gateway UI.
"""
import os
import logging
from typing import List, Optional

try:
    import streamlit as st
except ImportError:
    class _DummySessionState(dict):
        def __getattr__(self, name):
            return self.get(name, None)
        def __setattr__(self, name, value):
            self[name] = value
    class _DummyStreamlit:
        session_state = _DummySessionState()
        def rerun(self):
            pass
        def stop(self):
            raise RuntimeError("Streamlit stopped")
        def error(self, msg):
            pass
        def warning(self, msg):
            pass
        def success(self, msg):
            pass
        def caption(self, msg):
            pass
        def markdown(self, *args, **kwargs):
            pass
    st = _DummyStreamlit()

from src.api_client import api_client

logger = logging.getLogger("bharattrip.auth")



def init_auth_state():
    """Initializes authentication variables in Streamlit session state."""
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False
    if "access_token" not in st.session_state:
        st.session_state["access_token"] = None
    if "user_profile" not in st.session_state:
        st.session_state["user_profile"] = None
    if "role" not in st.session_state:
        st.session_state["role"] = None
    if "username" not in st.session_state:
        st.session_state["username"] = None


def login_mock(role: str, username: Optional[str] = None) -> bool:
    """
    Authenticates against the FastAPI backend /api/v1/auth/mock-login endpoint,
    storing the issued JWT access token and user profile in session state.
    
    Args:
        role: "Manager" or "Operator"
        username: Optional custom username override
        
    Returns:
        bool: True on successful authentication, False otherwise.
    """
    init_auth_state()
    try:
        resp = api_client.post(
            "/api/v1/auth/mock-login",
            json={"role": role, "username": username},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            st.session_state["access_token"] = data.get("access_token")
            user_profile = data.get("user_profile", {})
            st.session_state["user_profile"] = user_profile
            st.session_state["role"] = user_profile.get("role", role)
            st.session_state["username"] = user_profile.get("name") or user_profile.get("email") or username or role
            st.session_state["logged_in"] = True
            return True
        else:
            logger.error("Mock login rejected with HTTP %s: %s", resp.status_code, resp.text)
            st.error(f"Login failed: {resp.text}")
            return False
    except Exception as err:
        logger.warning("Backend auth service unreachable (%s). Using local fallback token.", err)
        # Fallback local state if backend is starting up
        st.session_state["logged_in"] = True
        st.session_state["role"] = role
        st.session_state["username"] = f"{role} User"
        st.session_state["access_token"] = f"local_mock_token_{role.lower()}"
        st.session_state["user_profile"] = {
            "user_id": f"user_{role.lower()}_01",
            "email": f"{role.lower()}@bharattrip.com",
            "name": f"{role} User",
            "role": role,
        }
        return True


def logout():
    """Logs out the active user and clears token session state."""
    init_auth_state()
    st.session_state["logged_in"] = False
    st.session_state["access_token"] = None
    st.session_state["user_profile"] = None
    st.session_state["role"] = None
    st.session_state["username"] = None

    if os.path.exists(".remember.json"):
        try:
            os.remove(".remember.json")
        except OSError:
            pass

    try:
        st.rerun()
    except Exception:
        pass


def require_auth() -> bool:
    """
    Page-level authentication guard.
    
    Returns:
        bool: True if user is logged in, False otherwise.
    """
    init_auth_state()
    return bool(st.session_state.get("logged_in"))


def require_role(allowed_roles: List[str]):
    """
    Page-level role guard enforcing RBAC permissions. Halts rendering if unauthorized.
    
    Args:
        allowed_roles: List of authorized roles (e.g. ["Manager"]).
    """
    init_auth_state()
    if not st.session_state.get("logged_in"):
        st.error("Authentication required. Please log in.")
        st.stop()

    current_role = st.session_state.get("role")
    if current_role not in allowed_roles:
        st.error(f"⛔ **Access Forbidden**: Your active role (`{current_role}`) does not have permission to view this page. Required: {', '.join(allowed_roles)}.")
        st.stop()


def render_login_gate() -> bool:
    """
    Renders the modern Identity Gateway UI supporting 1-click persona switching
    and direct OAuth / Mock login for Manager and Operator roles.
    
    Returns:
        bool: True if already logged in or login just succeeded.
    """
    init_auth_state()
    if st.session_state.logged_in:
        return True

    col1, col2, col3 = st.columns([1, 2.2, 1])
    with col2:
        st.markdown(
            """
            <div style="text-align: center; margin-bottom: 24px;">
                <h1 style="font-size: 2.2rem; font-weight: 700; margin-bottom: 4px;">BharatTrip SSOT</h1>
                <p style="color: #64748b; font-size: 1.05rem;">Enterprise AI Escalation Resolver & Reconciliation Platform</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("### 🔐 Identity Gateway")
        st.caption("Select your verified enterprise persona below to authenticate with JWT bearer tokens:")

        p_col1, p_col2 = st.columns(2)

        with p_col1:
            with st.container(border=True):
                st.markdown("#### 👔 Operations Manager")
                st.markdown("**Role**: `Manager`")
                st.markdown("- Full Operations Cockpit\n- Financial Ledger & Recon\n- Partner Matrix & Metrics")
                if st.button("🚀 Login as Manager", key="btn_login_mgr", type="primary", use_container_width=True):
                    if login_mock(role="Manager"):
                        st.success("Authenticated as Manager!")
                        st.rerun()

        with p_col2:
            with st.container(border=True):
                st.markdown("#### 🎧 Support Operator")
                st.markdown("**Role**: `Operator`")
                st.markdown("- Inbound Escalation Triage\n- WhatsApp Claim Ingestion\n- Masked DLP Database View")
                if st.button("⚡ Login as Operator", key="btn_login_op", type="secondary", use_container_width=True):
                    if login_mock(role="Operator"):
                        st.success("Authenticated as Operator!")
                        st.rerun()

        st.markdown("---")
        with st.expander("🛠️ Custom Mock Login (Advanced Testing)", expanded=False):
            with st.form("custom_login_form"):
                custom_username = st.text_input("Custom Username / ID", value="test_user_01")
                custom_role = st.selectbox("Assign Role", ["Manager", "Operator"])
                custom_submit = st.form_submit_button("Authenticate Custom Persona", use_container_width=True)
                if custom_submit:
                    if login_mock(role=custom_role, username=custom_username):
                        st.success(f"Authenticated as {custom_role} ({custom_username})!")
                        st.rerun()

    return False
