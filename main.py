import streamlit as st
from web_functions import load_data
from auth import show_auth_page, logout
from landing import show_landing
from database import init_db, get_user_by_id
from utils import show_datetime_bar, sidebar_profile_card, role_theme, inject_tab_persistence
from Tabs import home, data, predict, visualise, support
from Tabs import admin_dashboard, doctor_dashboard, patient_dashboard

# ── PAGE CONFIG ────────────────────────────────────────
st.set_page_config(
    page_title='StressGuard',
    page_icon='🧠',
    layout='wide',
    initial_sidebar_state='expanded'
)
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Sora:wght@600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background:
        radial-gradient(circle at 15% 15%, rgba(56,189,248,0.10), transparent 24%),
        radial-gradient(circle at 85% 15%, rgba(52,211,153,0.08), transparent 22%),
        linear-gradient(180deg, #050816 0%, #071120 48%, #050913 100%);
}

.block-container { padding-top: 3.5rem !important; }

div[data-testid="metric-container"] {
    background: linear-gradient(180deg, rgba(13,27,42,0.96), rgba(10,18,31,0.96));
    border: 1px solid rgba(148,163,184,0.14);
    border-radius: 16px;
    padding: 16px;
    box-shadow: 0 18px 34px rgba(2,8,23,0.25);
}
div[data-testid="metric-container"] label { color: #94a3b8 !important; }
div[data-testid="metric-container"] [data-testid="stMetricValue"] { color: white !important; }

.stDataFrame, [data-testid="stDataFrame"] {
    background: rgba(13,27,42,0.85);
    border-radius: 14px;
}

.stTabs [data-baseweb="tab-list"] {
    background: rgba(13,27,42,0.92);
    border-radius: 14px;
    border: 1px solid rgba(148,163,184,0.12);
    gap: 6px;
    padding: 4px;
}
.stTabs [data-baseweb="tab"] { color: #94a3b8 !important; border-radius: 10px; }
.stTabs [aria-selected="true"] {
    color: white !important;
    background: linear-gradient(135deg, rgba(56,189,248,0.18), rgba(52,211,153,0.18));
}

.stTextInput > div > input,
.stTextArea textarea,
.stSelectbox > div > div,
.stNumberInput > div > input,
.stDateInput input,
.stTimeInput input {
    background: rgba(13,27,42,0.92) !important;
    color: white !important;
    border-color: rgba(148,163,184,0.16) !important;
    border-radius: 12px !important;
}

.stExpander, .stFileUploader > div, [data-testid="stForm"] {
    background: rgba(13,27,42,0.86) !important;
    border-color: rgba(148,163,184,0.14) !important;
    border-radius: 14px !important;
}

.stButton > button {
    border-radius: 12px;
    font-weight: 700;
    box-shadow: 0 14px 28px rgba(2,8,23,0.18);
}

.element-container { margin-bottom: 0.4rem !important; }

.stSidebar { background: linear-gradient(180deg, #09111e, #0b1525) !important; }
section[data-testid="stSidebar"] { color: white !important; }

div[data-testid="stRadio"] > div { gap: 6px; }
div[data-testid="stRadio"] label {
    display: flex !important;
    align-items: center;
    padding: 7px 10px;
    border-radius: 8px;
    transition: 0.2s;
}
div[data-testid="stRadio"] label:hover { background: #1e2a3a; }
div[data-testid="stRadio"] label[data-checked="true"] {
    background: linear-gradient(135deg, rgba(56,189,248,0.25), rgba(52,211,153,0.20));
    font-weight: 600;
    color: white !important;
}
</style>
""", unsafe_allow_html=True)

# ── INIT DB ────────────────────────────────────────────
init_db()

@st.cache_data(ttl=300, show_spinner=False)
def _load():
    return load_data()

# ── SESSION STATE ──────────────────────────────────────
if 'show_login' not in st.session_state:
    st.session_state.show_login = False

# ── AUTH ───────────────────────────────────────────────
if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    if st.query_params.get("code"):
        show_auth_page()
    elif not st.session_state.show_login:
        show_landing()
    else:
        show_auth_page()
    st.stop()

# ── USER REFRESH ───────────────────────────────────────
@st.cache_data(ttl=8, show_spinner=False)
def _fresh_user(uid):
    return get_user_by_id(uid)

fresh = _fresh_user(st.session_state.user['id'])
if fresh:
    st.session_state.user = fresh

user   = st.session_state.user
role   = st.session_state.role
accent, bg_grad, _ = role_theme(role)

show_datetime_bar()

# Persist tab selection across reruns on EVERY page (fixes screen-switching
# whenever a button/form/chat-send triggers a Streamlit rerun).
inject_tab_persistence()

# ── COUNTERS ───────────────────────────────────────────
@st.cache_data(ttl=5)
def _unread(uid):
    from database import get_unread_count
    return get_unread_count(uid)

@st.cache_data(ttl=10)
def _checklist_pending(uid):
    from database import get_checklist_pending_count
    return get_checklist_pending_count(uid)

@st.cache_data(ttl=8)
def _alert_count(uid):
    from database import get_unread_alert_count
    return get_unread_alert_count(uid)

unread = _unread(user['id'])

# ── NAV OVERRIDE (programmatic redirect — must happen BEFORE radio renders) ──
# Dashboards set st.session_state["nav_override"] = "👤 My Dashboard" etc.
# We resolve it here, write main_nav, then clear the override, then rerun so
# the radio renders fresh with the correct default — avoiding the
# "cannot modify after widget instantiated" error.
_nav_override = st.session_state.pop("nav_override", None)

# ── SIDEBAR ────────────────────────────────────────────
with st.sidebar:
    sidebar_profile_card(user, accent)

    st.markdown(
        f"<div style='font-weight:800;font-size:1rem;color:{accent};margin-bottom:8px;'>"
        f"🧠 Navigation</div>", unsafe_allow_html=True)

    dot = " 🔴" if unread > 0 else ""

    if role == 'admin':
        NAV = ["🏠 Home", "🔴 Admin Panel", "📊 Data Info"]
    elif role == 'doctor':
        alert_cnt  = _alert_count(user['id'])
        # Also count unread appointment notifications for the doctor
        try:
            from database import get_appointment_notifications
            _appt_notifs = get_appointment_notifications(user['id'], unread_only=True)
            _appt_dot_n  = len(_appt_notifs)
        except Exception:
            _appt_dot_n = 0
        _total_dot = alert_cnt + _appt_dot_n
        alert_dot = f" 🔴{_total_dot}" if _total_dot > 0 else ""
        NAV = ["🏠 Home", f"🩺 Doctor Panel{alert_dot}", f"💬 Chat{dot}", "📊 Data Info"]
    else:
        chk_pending = _checklist_pending(user['id'])
        chk_dot = f" 🔴{chk_pending}" if chk_pending > 0 else ""
        NAV = ["🏠 Home", f"👤 My Dashboard{chk_dot}", f"💬 Chat{dot}", "📊 Data Info", "🆘 Quick Help"]

    # ── Restore nav when badge text changes (strip the 🔴 suffix for matching) ──
    def _base(s): return s[:s.find(" 🔴")].strip() if " 🔴" in s else s.strip()

    _cur = st.session_state.get("main_nav", "")
    if _cur and _cur not in NAV:
        _cur_base = _base(_cur)
        for _n in NAV:
            if _base(_n) == _cur_base:
                st.session_state["main_nav"] = _n
                break

    # ── Apply nav_override BEFORE the radio renders ───────────────────────────
    if _nav_override:
        _ov_base = _base(_nav_override)
        for _n in NAV:
            if _base(_n) == _ov_base or _nav_override in _n:
                st.session_state["main_nav"] = _n
                break

    page = st.radio("Navigation", NAV, key="main_nav")

    if unread > 0:
        st.markdown(
            f"<div style='text-align:center;margin-top:-6px;'>"
            f"<span style='background:#ff4b4b;color:white;border-radius:20px;"
            f"padding:2px 10px;font-size:0.72rem;font-weight:800;'>"
            f"💬 {unread} unread</span></div>", unsafe_allow_html=True)

    st.markdown("---")
    if st.button("🚪 Logout", use_container_width=True):
        logout()

# ── LOAD DATA ──────────────────────────────────────────
try:
    df, X, y = _load()
except Exception as e:
    st.error(f"Unable to load model dataset: {e}")
    st.stop()

def _clean(p):
    idx = p.find(" 🔴")
    return p[:idx].strip() if idx != -1 else p.strip()

pc = _clean(page)

# ── ROUTING ────────────────────────────────────────────


if pc == "🏠 Home":
    home.app()
elif pc == "🔴 Admin Panel":
    admin_dashboard.app()
elif pc == "🩺 Doctor Panel":
    doctor_dashboard.app()
elif pc == "💬 Chat" and role == "doctor":
    # Open Doctor Panel with Chat tab auto-selected via JS
    st.session_state["doc_open_chat_tab"] = True
    doctor_dashboard.app()
elif pc == "💬 Chat" and role == "patient":
    # Open My Dashboard with Chat tab auto-selected via JS
    st.session_state["pat_open_chat_tab"] = True
    patient_dashboard.app()
elif pc == "👤 My Dashboard":
    patient_dashboard.app()
elif pc == "📊 Data Info":
    data.app(df)
elif pc == "📈 Visualisation":
    visualise.app(df, X, y)
elif pc in ("🆘 Quick Help", "🆘 Support"):
    support.app()
else:
    home.app()