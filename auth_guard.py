# auth_guard.py
import streamlit as st
from datetime import datetime, timedelta

AUTH_TIMEOUT_MIN = 60  # auto-logout setelah idle N menit

def _init_state():
    if "auth_ok" not in st.session_state:
        st.session_state.auth_ok = False
    if "last_activity" not in st.session_state:
        st.session_state.last_activity = None

def _timeout_if_idle():
    if st.session_state.auth_ok and st.session_state.last_activity:
        if datetime.utcnow() - st.session_state.last_activity > timedelta(minutes=AUTH_TIMEOUT_MIN):
            st.session_state.auth_ok = False
            st.session_state.last_activity = None
            st.rerun()

def check_auth():
    """Panggil di awal setiap page untuk proteksi."""
    _init_state()
    _timeout_if_idle()

    if not st.session_state.auth_ok:
        st.title("Login")
        pwd = st.text_input("Masukkan password", type="password", key="pwd_input")
        if st.button("Masuk", key="login_btn"):
            try:
                expected = st.secrets["auth"]["app_password"]
            except Exception:
                st.error("Konfigurasi secrets tidak ditemukan: [auth].app_password")
                st.stop()
            if pwd == expected:
                st.session_state.auth_ok = True
                st.session_state.last_activity = datetime.utcnow()
                st.rerun()
            else:
                st.error("Password salah.")
        st.stop()

    # sudah login → update aktivitas dan sediakan tombol logout
    st.session_state.last_activity = datetime.utcnow()
    with st.sidebar:
        st.caption(f"Login aktif • auto-logout {AUTH_TIMEOUT_MIN} menit idle")
        if st.button("Logout", key="logout_btn"):
            st.session_state.auth_ok = False
            st.session_state.last_activity = None
            st.rerun()

def require_auth(func):
    """Decorator untuk membungkus page/function."""
    def wrapper(*args, **kwargs):
        check_auth()
        return func(*args, **kwargs)
    return wrapper
