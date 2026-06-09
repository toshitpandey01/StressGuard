import re
import streamlit as st
from database import (
    authenticate_user, register_user, init_db, encode_photo,
    get_user_by_id, get_user_by_email,
    create_otp, verify_otp, send_otp_email, username_exists,
    log_login, find_user_for_recovery, change_password,
)
from email_service import send_account_recovery_email
from utils import inject_tab_persistence

# ── CSS ───────────────────────────────────────────────────────────────────────
_BASE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Sora:wght@600;700;800&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif;}
.stApp{
    background:
        radial-gradient(circle at 15% 15%, rgba(56,189,248,0.10), transparent 24%),
        radial-gradient(circle at 85% 18%, rgba(52,211,153,0.08), transparent 22%),
        linear-gradient(180deg,#050816 0%,#071120 50%,#050913 100%);
}

.stButton>button{width:100%;border-radius:14px;font-weight:700;padding:0.72rem;box-shadow:0 16px 30px rgba(2,8,23,0.22);}
.stTextInput>div>input,.stSelectbox>div>div,.stNumberInput>div>input{
    background:rgba(13,27,42,0.92)!important;color:white!important;
    border-color:rgba(148,163,184,0.18)!important;border-radius:12px!important;}
.stTabs [data-baseweb="tab-list"]{background:rgba(13,27,42,0.92);border-radius:16px;border:1px solid rgba(148,163,184,0.12);padding:4px;}
.stTabs [data-baseweb="tab"]{color:#94a3b8!important;border-radius:12px;}
.stTabs [aria-selected="true"]{color:white!important;background:linear-gradient(135deg,rgba(56,189,248,0.18),rgba(52,211,153,0.18));}
.stFileUploader>div,[data-testid="stForm"]{background:rgba(13,27,42,0.88)!important;border-color:rgba(148,163,184,0.16)!important;border-radius:14px!important;}
</style>
"""

# ── Role configuration ────────────────────────────────────────────────────────
ROLE_CFG = {
    "admin": {
        "icon": "🔴", "label": "Admin Portal",
        "color": "#ff4b4b",
        "bg":    "linear-gradient(135deg,#1a0505,#2a1010)",
        "border":"#ff4b4b44",
        "grad":  "linear-gradient(90deg,#ff4b4b,#ff8040)",
        "features": [
            ("👥", "Manage All Users", "Add, view, delete doctors and patients"),
            ("🔗", "Assign Doctors",   "Link patients to specific doctors"),
            ("📊", "All Predictions",  "View every prediction across the system"),
            ("📈", "System Analytics", "Pie charts, bar graphs, stress distribution"),
            ("🩺", "Doctor Portfolios","View and manage doctor profiles & credentials"),
            ("🔒", "Password Control", "Reset passwords for any user"),
        ],
        "permissions": [
            "✅ Full system access",
            "✅ Create / delete any user",
            "✅ View all patient data",
            "✅ Assign doctor–patient relationships",
            "✅ View all predictions & analytics",
            "❌ Cannot run stress predictions",
            "❌ Cannot access patient chat",
        ],
    },
    "doctor": {
        "icon": "🩺", "label": "Doctor Portal",
        "color": "#00d4ff",
        "bg":    "linear-gradient(135deg,#0a1628,#0d2035)",
        "border":"#00d4ff44",
        "grad":  "linear-gradient(90deg,#00d4ff,#0072ff)",
        "features": [
            ("👤", "My Patients",      "View all assigned patients and their history"),
            ("📝", "Clinical Notes",   "Add notes per patient + private self-notes"),
            ("📋", "Checklists",       "Post Daily/Weekly/Monthly tasks for patients"),
            ("💬", "Live Chat",        "Real-time WhatsApp-style messaging"),
            ("🚨", "Stress Alerts",    "Priority notifications for high-stress patients"),
            ("⬇️", "Download Reports", "Export PDF reports per patient"),
        ],
        "permissions": [
            "✅ View own assigned patients only",
            "✅ Add / view clinical notes",
            "✅ Manage patient checklists",
            "✅ Chat with assigned patients",
            "✅ Download patient reports",
            "✅ View stress alerts",
            "❌ Cannot add/delete users",
            "❌ Cannot view other doctors' patients",
        ],
    },
    "patient": {
        "icon": "👤", "label": "Patient Portal",
        "color": "#00ff88",
        "bg":    "linear-gradient(135deg,#081a12,#0d2018)",
        "border":"#00ff8844",
        "grad":  "linear-gradient(90deg,#00ff88,#00cc66)",
        "features": [
            ("🔮", "Stress Prediction", "AI-powered stress analysis from sleep data"),
            ("📊", "My History",        "View trend charts of past predictions"),
            ("📋", "My Checklist",      "Doctor-assigned tasks with progress tracking"),
            ("🤖", "Wellness Bot",      "24/7 positive support chatbot"),
            ("💬", "Chat Doctor",       "Direct messaging with assigned doctor"),
            ("📓", "Personal Notes",    "Private color-coded diary & notes"),
        ],
        "permissions": [
            "✅ Run stress predictions",
            "✅ View own history only",
            "✅ Chat with assigned doctor",
            "✅ View doctor notes & checklists",
            "✅ Download own report",
            "❌ Cannot see other patients' data",
            "❌ Cannot assign doctors",
            "❌ Cannot access admin features",
        ],
    },
}


# ── Validation helpers ────────────────────────────────────────────────────────
def _valid_email(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.strip()))

def _valid_phone(phone: str) -> bool:
    if not phone:
        return False
    digits = re.sub(r'[\s\-\+\(\)]', '', phone)
    return digits.isdigit() and len(digits) == 10


# ── Google OAuth helpers ──────────────────────────────────────────────────────
def _google_oauth_available():
    try:
        val = st.secrets.get("google_client_id", "")
        return bool(val and val != "YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com")
    except:
        return False

def _handle_google_callback():
    try:
        import requests

        params = st.query_params
        code  = params.get("code")
        state = params.get("state", "")

        if not code:
            return

        role = "patient"
        if state.startswith("role:"):
            role = state.split(":", 1)[1]
        if role not in ROLE_CFG:
            role = "patient"

        st.session_state.selected_role = role
        st.session_state.show_login = True

        client_id = st.secrets["google_client_id"]
        client_secret = st.secrets["google_client_secret"]
        redirect_uri = st.secrets.get("google_redirect_uri", "http://localhost:8501")

        token_resp = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        token_data = token_resp.json()

        if "error" in token_data:
            st.error(f"Token error: {token_data['error']} — {token_data.get('error_description','')}")
            st.query_params.clear()
            return

        access_token = token_data["access_token"]

        user_resp = requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        user_info = user_resp.json()

        email = user_info.get("email", "")
        name = user_info.get("name", "Google User")
        g_sub = user_info.get("sub", "")
        username = f"g_{g_sub}"

        from database import get_connection
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=?", (username,))
        existing = c.fetchone()
        conn.close()

        if existing:
            user_dict = dict(existing)
        else:
            import hashlib
            rand_pw = hashlib.sha256(g_sub.encode()).hexdigest()[:16]
            ok, msg = register_user(
                username, rand_pw, role, name, email, "",
                doctor_id=None, is_verified=1,
            )
            if not ok:
                st.error(f"Registration error: {msg}")
                st.query_params.clear()
                return
            conn = get_connection()
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE username=?", (username,))
            user_dict = dict(c.fetchone())
            conn.close()

        st.session_state.logged_in = True
        st.session_state.user = user_dict
        try:
            log_login(user_dict["id"], user_dict["username"],
                      user_dict.get("full_name",""), user_dict.get("role",""))
        except Exception:
            pass
        st.session_state.role = user_dict["role"]
        st.query_params.clear()
        st.success(f"✅ Signed in with Google as {name}!")
        st.rerun()

    except Exception as e:
        st.error(f"Google sign-in error: {e}")
        try:
            st.query_params.clear()
        except:
            pass


def _google_login_button(role: str, cfg: dict):
    if not _google_oauth_available():
        try:
            raw = st.secrets.get("google_client_id", "NOT SET")
            st.markdown(
                f"<div style='background:#0d1b2a;border:1px solid #2a3a5a;"
                f"border-radius:8px;padding:8px 12px;text-align:center;"
                f"color:#556;font-size:0.78rem;margin-top:6px;'>"
                f"ℹ️ Google Sign-In not configured (key={raw[:30]}...)</div>",
                unsafe_allow_html=True)
        except Exception as ex:
            st.error(f"Secrets error: {ex}")
        return

    try:
        if st.query_params.get("code"):
            return
    except:
        pass

    try:
        from urllib.parse import urlencode

        client_id = st.secrets["google_client_id"]
        redirect_uri = st.secrets.get("google_redirect_uri", "http://localhost:8501")
        state = f"role:{role}"

        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
            "prompt": "select_account",
        }
        auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)

        st.markdown(
            f"<div style='text-align:center;margin-top:6px;'>"
            f"<a href='{auth_url}' target='_self' style='"
            f"background:white;color:#333;border-radius:8px;"
            f"padding:9px 18px;text-decoration:none;font-weight:700;"
            f"display:inline-flex;align-items:center;gap:8px;'>"
            f"<img src='https://www.google.com/favicon.ico' width='16'>"
            f"&nbsp;Sign in with Google</a></div>",
            unsafe_allow_html=True)

    except Exception as e:
        st.error(f"OAuth URL error: {e}")


# ── Role header ───────────────────────────────────────────────────────────────
def _role_header(role: str):
    cfg = ROLE_CFG[role]
    st.markdown(f"""
    <div style='background:{cfg["bg"]};border:1px solid {cfg["border"]};
                border-radius:16px;padding:1.2rem;text-align:center;
                margin-bottom:1rem;'>
        <div style='font-size:2.8rem;'>{cfg["icon"]}</div>
        <div style='font-size:1.6rem;font-weight:900;
                    background:{cfg["grad"]};
                    -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                    background-clip:text;'>{cfg["label"]}</div>
        <div style='color:{cfg["color"]}88;font-size:0.82rem;margin-top:3px;'>
            Stress Level Detector — Secure Login
        </div>
    </div>""", unsafe_allow_html=True)


# ── Login form ────────────────────────────────────────────────────────────────
def _login_form(role: str, cfg: dict):
    st.markdown(f"### {cfg['icon']} {cfg['label']} Login")

    if role == "admin":
        st.markdown(
            f"<div style='background:#0d1b2a;border:1px solid #1e3a5a;"
            f"border-radius:8px;padding:7px 10px;margin-bottom:8px;"
            f"font-size:0.78rem;color:#778;'>"
            f"</div>", unsafe_allow_html=True)

    uname = st.text_input("Username", placeholder="Enter username", key=f"li_u_{role}")
    passw = st.text_input("Password", type="password", placeholder="Enter password", key=f"li_p_{role}")

    if st.button(f"🔐 Login as {role.title()} →", key=f"li_btn_{role}", type="primary"):
        if uname and passw:
            user = authenticate_user(uname.strip(), passw, role_filter=role)
            if user:
                st.session_state.logged_in = True
                st.session_state.user = user
                st.session_state.role = user["role"]
                try:
                    log_login(user["id"], user["username"], user.get("full_name",""), user["role"])
                except Exception:
                    pass
                st.success(f"✅ Welcome back, **{user['full_name']}**!")
                st.rerun()
            else:
                st.error(f"❌ Invalid credentials or wrong portal. Make sure you're on the **{role.title()} portal**.")
        else:
            st.warning("⚠️ Please fill in both fields.")

    st.markdown(
        "<div style='display:flex;align-items:center;gap:8px;margin:10px 0;'>"
        "<div style='flex:1;height:1px;background:#2a3a5a;'></div>"
        "<span style='color:#556;font-size:0.78rem;'>or</span>"
        "<div style='flex:1;height:1px;background:#2a3a5a;'></div>"
        "</div>", unsafe_allow_html=True)
    _google_login_button(role, cfg)

    if role in ("doctor", "patient"):
        _recovery_form(role, cfg)


def _support_email():
    return st.secrets.get("support_email", st.secrets.get("smtp_email", "admin@stressapp.com"))


def _mask_email(email: str) -> str:
    email = str(email or "").strip()
    if not email or "@" not in email:
        return "your registered email"
    name, domain = email.split("@", 1)
    if len(name) <= 2:
        name_masked = name[0] + "*"
    else:
        name_masked = name[:2] + "*" * max(len(name) - 2, 1)
    return f"{name_masked}@{domain}"


def _clear_recovery_state(role: str):
    for k in [
        f"rc_step_{role}", f"rc_email_{role}", f"rc_phone_{role}",
        f"rc_name_{role}", f"rc_user_{role}", f"rc_verified_email_{role}",
        f"rc_verified_uid_{role}", f"rc_verified_username_{role}", f"rc_otp_{role}",
        f"rc_new_pass_{role}", f"rc_new_pass2_{role}"
    ]:
        st.session_state.pop(k, None)


def _recovery_form(role: str, cfg: dict):
    support_email = _support_email()
    step_key = f"rc_step_{role}"
    if step_key not in st.session_state:
        st.session_state[step_key] = 1

    with st.expander("🔐 Forgot ID or Password?", expanded=False):
        st.markdown(
            f"<div style='background:{cfg['bg']};border:1px solid {cfg['color']}33;border-radius:14px;padding:12px 14px;margin-bottom:10px;'>"
            f"<div style='color:{cfg['color']};font-weight:800;font-size:0.92rem;'>Secure account recovery</div>"
            f"<div style='color:#aab4c8;font-size:0.82rem;margin-top:4px;'>"
            f"Verify your identity with registered details, then reset your password using a time-limited OTP sent to email."
            f"</div></div>",
            unsafe_allow_html=True,
        )

        step = st.session_state.get(step_key, 1)
        if step == 1:
            c1, c2 = st.columns(2)
            with c1:
                email = st.text_input("Registered Email *", key=f"rc_email_{role}", placeholder="you@example.com")
                phone = st.text_input("Registered Phone *", key=f"rc_phone_{role}", placeholder="Digits only")
            with c2:
                full_name = st.text_input("Full Name *", key=f"rc_name_{role}")
                username = st.text_input("Username / ID (optional)", key=f"rc_user_{role}")

            st.caption(f"If you still cannot access your account, contact admin/support at {support_email}.")
            if st.button("Verify identity & send recovery email", key=f"rc_send_{role}"):
                errors = []
                if not email or not _valid_email(email):
                    errors.append("Enter a valid registered email.")
                if not phone or not _valid_phone(phone):
                    errors.append("Enter the registered phone number using digits only.")
                if not full_name.strip():
                    errors.append("Full name is required for identity verification.")
                if errors:
                    for err in errors:
                        st.error(f"❌ {err}")
                else:
                    user = find_user_for_recovery(
                        email=email,
                        phone=phone,
                        role=role,
                        username=username,
                        full_name=full_name,
                    )
                    if not user:
                        st.error("❌ We could not verify those details. Review the information or contact admin support.")
                    else:
                        otp = create_otp(user.get("email", email), purpose="password_reset")
                        ok, msg = send_account_recovery_email(
                            user.get("email", email),
                            user.get("full_name") or role.title(),
                            user.get("username", ""),
                            otp,
                            role,
                        )
                        if ok:
                            st.session_state[f"rc_verified_email_{role}"] = user.get("email", email)
                            st.session_state[f"rc_verified_uid_{role}"] = user.get("id")
                            st.session_state[f"rc_verified_username_{role}"] = user.get("username", "")
                            st.session_state[step_key] = 2
                            st.success("✅ Recovery email sent. Check your inbox for the secure OTP.")
                            st.rerun()
                        else:
                            st.error("❌ Recovery email could not be sent right now. Please contact admin support.")
                            st.caption(msg)

        elif step == 2:
            masked = _mask_email(st.session_state.get(f"rc_verified_email_{role}", ""))
            st.markdown(
                f"<div style='background:#0a1e30;border:1px solid {cfg['color']}44;border-radius:12px;padding:12px 14px;margin-bottom:10px;'>"
                f"<div style='color:{cfg['color']};font-weight:800;'>Email verification in progress</div>"
                f"<div style='color:#aab4c8;font-size:0.82rem;margin-top:4px;'>"
                f"Enter the OTP sent to <b>{masked}</b> and choose a new password. The message also includes your verified username if you forgot it."
                f"</div></div>",
                unsafe_allow_html=True,
            )
            st.text_input("Recovery OTP *", key=f"rc_otp_{role}", max_chars=6, placeholder="6-digit OTP")
            st.text_input("New Password *", type="password", key=f"rc_new_pass_{role}")
            st.text_input("Confirm New Password *", type="password", key=f"rc_new_pass2_{role}")
            a, b = st.columns(2)
            with a:
                if st.button("Reset password securely", key=f"rc_reset_{role}", type="primary"):
                    otp_in = st.session_state.get(f"rc_otp_{role}", "").strip()
                    pw = st.session_state.get(f"rc_new_pass_{role}", "")
                    pw2 = st.session_state.get(f"rc_new_pass2_{role}", "")
                    email = st.session_state.get(f"rc_verified_email_{role}", "")
                    user_id = st.session_state.get(f"rc_verified_uid_{role}")
                    if len(otp_in) != 6 or not otp_in.isdigit():
                        st.error("❌ Recovery OTP must be exactly 6 digits.")
                    elif len(pw) < 6:
                        st.error("❌ New password must be at least 6 characters.")
                    elif pw != pw2:
                        st.error("❌ Passwords do not match.")
                    elif not verify_otp(email, otp_in, "password_reset"):
                        st.error("❌ Invalid or expired OTP. Request a new recovery email.")
                    elif not user_id:
                        st.error("❌ Recovery session expired. Start the recovery process again.")
                    else:
                        change_password(user_id, pw)
                        st.session_state[step_key] = 3
                        st.success("✅ Password reset complete. You can now log in with your updated password.")
                        st.rerun()
            with b:
                if st.button("Resend recovery email", key=f"rc_resend_{role}"):
                    email = st.session_state.get(f"rc_verified_email_{role}", "")
                    username = st.session_state.get(f"rc_verified_username_{role}", "")
                    if not email:
                        st.error("Recovery session expired. Start again.")
                    else:
                        otp = create_otp(email, purpose="password_reset")
                        ok, msg = send_account_recovery_email(
                            email,
                            st.session_state.get(f"rc_name_{role}", role.title()),
                            username,
                            otp,
                            role,
                        )
                        if ok:
                            st.success("✅ A new recovery email has been sent.")
                        else:
                            st.error("❌ Unable to resend email right now. Please contact admin support.")
                            st.caption(msg)
            if st.button("← Start over", key=f"rc_restart_{role}"):
                _clear_recovery_state(role)
                st.session_state[step_key] = 1
                st.rerun()

        else:
            st.success("Password recovery complete. Return to login using your verified account credentials.")
            st.caption(f"Support contact: {support_email}")
            if st.button("Back to login", key=f"rc_back_login_{role}"):
                _clear_recovery_state(role)
                st.session_state[step_key] = 1
                st.rerun()


# ── OTP send sub-form ─────────────────────────────────────────────────────────
def _otp_send_section(role: str, cfg: dict, email: str, name: str):
    otp_sent_key = f"otp_sent_{role}"
    otp_email_key = f"otp_email_{role}"

    st.markdown(
        f"<div style='background:#0a1e30;border:1px solid {cfg['color']}44;"
        f"border-radius:10px;padding:10px 14px;margin:8px 0;'>"
        f"<span style='color:{cfg['color']};font-weight:700;font-size:0.85rem;'>"
        f"📧 Email OTP Verification Required</span><br>"
        f"<span style='color:#aaa;font-size:0.78rem;'>"
        f"An OTP will be sent to your email to verify your account.</span>"
        f"</div>", unsafe_allow_html=True)

    smtp_ok = True
    try:
        import streamlit as _st
        _ = _st.secrets.get("smtp_email", "")
        if not _:
            smtp_ok = False
    except:
        smtp_ok = False

    if not smtp_ok:
        st.warning("⚠️ SMTP not configured — OTP email disabled. Add `smtp_email` and `smtp_password` to .streamlit/secrets.toml. For now, a **demo OTP** will be shown on screen.")

    send_col, status_col = st.columns([2, 3])
    with send_col:
        if st.button("📤 Send OTP to Email", key=f"send_otp_{role}"):
            if not email:
                st.error("Enter email first.")
            elif not _valid_email(email):
                st.error("Invalid email format.")
            elif not name:
                st.error("Enter full name first.")
            else:
                otp = create_otp(email, purpose="register")
                ok, msg = send_otp_email(email, otp, name, "registration")
                if ok:
                    st.session_state[otp_sent_key] = True
                    st.session_state[otp_email_key] = email
                    st.success("✅ OTP sent! Check your inbox.")
                else:
                    st.session_state[otp_sent_key] = True
                    st.session_state[otp_email_key] = email
                    st.warning(f"Email not delivered ({msg}). **Demo OTP: `{otp}`** (use this to proceed)")
    with status_col:
        if st.session_state.get(otp_sent_key):
            st.markdown(
                f"<span style='color:{cfg['color']};font-size:0.82rem;'>"
                f"✅ OTP sent to {st.session_state.get(otp_email_key,'')}</span>",
                unsafe_allow_html=True)


# ── Register form ─────────────────────────────────────────────────────────────
def _register_form(role: str, cfg: dict):
    if role == "admin":
        st.info("🔒 Admin accounts are created by the system only.")
        return

    st.markdown(f"### {cfg['icon']} Create {role.title()} Account")

    step_key = f"reg_step_{role}"
    if step_key not in st.session_state:
        st.session_state[step_key] = 1

    step = st.session_state[step_key]

    st.markdown(f"""
    <div style='display:flex;gap:6px;margin-bottom:12px;align-items:center;'>
        {"".join([
            f"<div style='background:{'#00ff88' if i<=step else '#1e2a3a'};"
            f"color:{'#06090f' if i<=step else '#556'};"
            f"border-radius:20px;padding:3px 12px;font-size:0.75rem;font-weight:700;'>"
            f"{'✓ ' if i<step else ''}{s}</div>"
            for i, s in [(1,"Details"),(2,"Verify OTP"),(3,"Done")]
        ])}
    </div>""", unsafe_allow_html=True)

    if step == 1:
        st.markdown(
            f"<div style='color:{cfg['color']};font-weight:700;margin-bottom:3px;'>"
            f"📷 Profile Photo (optional)</div>", unsafe_allow_html=True)
        photo_file = st.file_uploader(
            "photo", type=["jpg","jpeg","png","webp"],
            key=f"rg_photo_{role}", label_visibility="collapsed")

        c1, c2 = st.columns(2)
        with c1:
            st.text_input("Full Name *", key=f"rg_name_{role}")
            st.text_input("Email *", key=f"rg_email_{role}", placeholder="you@example.com")
            st.text_input("Contact Number *", key=f"rg_phone_{role}", placeholder="e.g. 9876543210")
        with c2:
            st.text_input("Username *", key=f"rg_user_{role}")
            _uval = st.session_state.get(f"rg_user_{role}", "").strip()
            if _uval:
                if username_exists(_uval):
                    st.markdown(
                        "<div style='background:#1a0505;border:1px solid "
                        "#ff4b4b55;border-radius:6px;padding:4px 10px;"
                        "font-size:0.78rem;color:#ff4b4b;'>❌ Username already taken</div>",
                        unsafe_allow_html=True)
                else:
                    st.markdown(
                        "<div style='background:#051a0a;border:1px solid "
                        "#00ff8855;border-radius:6px;padding:4px 10px;"
                        "font-size:0.78rem;color:#00ff88;'>✅ Username available</div>",
                        unsafe_allow_html=True)
            st.text_input("Password *", type="password", key=f"rg_pass_{role}")
            st.text_input("Confirm Password *", type="password", key=f"rg_pass2_{role}")

        if role == "patient":
            st.markdown(
                "<div style='background:#0a1e10;border:1px solid #00ff8844;"
                "border-radius:8px;padding:8px 12px;margin:6px 0;"
                "font-size:0.82rem;color:#00ff88;'>"
                "ℹ️ Doctor assignment is handled by Admin after registration."
                "</div>", unsafe_allow_html=True)

        email_val = st.session_state.get(f"rg_email_{role}", "").strip()
        phone_val = st.session_state.get(f"rg_phone_{role}", "").strip()
        pw_val = st.session_state.get(f"rg_pass_{role}", "")
        pw2_val = st.session_state.get(f"rg_pass2_{role}", "")

        hints = []
        if email_val and not _valid_email(email_val):
            hints.append("⚠️ Email format invalid (e.g. user@domain.com)")
        if not phone_val:
            hints.append("⚠️ Contact number is required")
        elif not _valid_phone(phone_val):
            hints.append("⚠️ Contact number must be exactly 10 digits")
        if pw_val and len(pw_val) < 6:
            hints.append("⚠️ Password must be at least 6 characters")
        if pw_val and pw2_val and pw_val != pw2_val:
            hints.append("⚠️ Passwords do not match")
        for h in hints:
            st.markdown(
                f"<div style='color:#ff8844;font-size:0.78rem;'>{h}</div>",
                unsafe_allow_html=True)

        if st.button("📤 Continue to OTP Verification →", key=f"rg_step1_btn_{role}", type="primary"):
            name = st.session_state.get(f"rg_name_{role}", "").strip()
            email = email_val
            uname = st.session_state.get(f"rg_user_{role}", "").strip()
            pw = pw_val
            pw2 = pw2_val
            phone = phone_val

            errors = []
            if not all([name, email, uname, pw, pw2, phone]):
                errors.append("Fill in all required (*) fields, including contact number.")
            if email and not _valid_email(email):
                errors.append("Email format is invalid.")
            if not phone:
                errors.append("Contact number is required.")
            elif not _valid_phone(phone):
                errors.append("Contact number must contain digits only.")
            if len(pw) < 6:
                errors.append("Password must be ≥ 6 characters.")
            if pw != pw2:
                errors.append("Passwords do not match.")
            if uname and username_exists(uname):
                errors.append("Username is already taken — choose a different one.")

            if errors:
                for e in errors:
                    st.error(f"❌ {e}")
            else:
                st.session_state[f"rg_tmp_{role}"] = {
                    "name": name,
                    "email": email,
                    "uname": uname,
                    "pw": pw,
                    "phone": phone,
                    "photo_file": photo_file,
                }
                otp = create_otp(email, purpose="register")
                ok, msg = send_otp_email(email, otp, name, "registration")
                if ok:
                    st.success("✅ OTP sent to your email!")
                else:
                    st.warning(f"SMTP not ready — **Demo OTP: `{otp}`** (copy this and paste below)")
                st.session_state[step_key] = 2
                st.rerun()

    elif step == 2:
        tmp = st.session_state.get(f"rg_tmp_{role}", {})
        email = tmp.get("email", "")
        st.markdown(
            f"<div style='background:#0a1e30;border:1px solid {cfg['color']}44;"
            f"border-radius:10px;padding:12px 16px;margin-bottom:10px;'>"
            f"<b style='color:{cfg['color']};'>📧 OTP Verification</b><br>"
            f"<span style='color:#aaa;font-size:0.85rem;'>"
            f"Enter the 6-digit OTP sent to <b>{email}</b><br>"
            f"OTP expires in 10 minutes.</span></div>",
            unsafe_allow_html=True)

        st.text_input("Enter 6-digit OTP *", key=f"rg_otp_{role}", placeholder="e.g. 123456", max_chars=6)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Verify & Register", key=f"rg_verify_btn_{role}", type="primary"):
                otp_in = st.session_state.get(f"rg_otp_{role}", "").strip()
                if not otp_in or len(otp_in) != 6 or not otp_in.isdigit():
                    st.error("❌ OTP must be exactly 6 digits.")
                elif not verify_otp(email, otp_in, "register"):
                    st.error("❌ Invalid or expired OTP. Try sending again.")
                else:
                    photo_uri = None
                    pf = tmp.get("photo_file")
                    if pf:
                        pf.seek(0)
                        photo_uri = encode_photo(pf.read(), pf.type or "image/png")
                    ok, msg = register_user(
                        tmp["uname"], tmp["pw"], role,
                        tmp["name"], tmp["email"], tmp["phone"],
                        doctor_id=None, profile_photo=photo_uri,
                        is_verified=1)
                    if ok:
                        st.success("✅ Account created! Please login.")
                        st.balloons()
                        for k in [f"rg_name_{role}", f"rg_email_{role}",
                                  f"rg_phone_{role}", f"rg_user_{role}",
                                  f"rg_pass_{role}", f"rg_pass2_{role}",
                                  f"rg_otp_{role}", f"rg_tmp_{role}",
                                  f"rg_photo_{role}", step_key]:
                            st.session_state.pop(k, None)
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")

        with col2:
            if st.button("🔄 Resend OTP", key=f"rg_resend_{role}"):
                otp2 = create_otp(email, purpose="register")
                ok2, msg2 = send_otp_email(email, otp2, tmp.get("name",""), "registration")
                if ok2:
                    st.success("✅ New OTP sent!")
                else:
                    st.warning(f"SMTP not ready — **Demo OTP: `{otp2}`**")

        if st.button("← Back to Details", key=f"rg_back_{role}"):
            st.session_state[step_key] = 1
            st.rerun()


# ── Walkthrough / feature tour ────────────────────────────────────────────────
def _walkthrough(role: str, cfg: dict):
    rc = ROLE_CFG[role]
    st.markdown(
        f"<div style='color:{cfg['color']};font-weight:800;font-size:1rem;"
        f"margin-bottom:8px;'>✨ What you can do as a {role.title()}</div>",
        unsafe_allow_html=True)

    cols = st.columns(2)
    for i, (icon, title, desc) in enumerate(rc["features"]):
        with cols[i % 2]:
            st.markdown(f"""
            <div style='background:{cfg["bg"]};border:1px solid {cfg["color"]}33;
                        border-radius:10px;padding:10px 12px;margin-bottom:6px;'>
                <span style='font-size:1.3rem;'>{icon}</span>
                <span style='color:{cfg["color"]};font-weight:700;font-size:0.88rem;
                             margin-left:6px;'>{title}</span>
                <div style='color:#aaa;font-size:0.78rem;margin-top:3px;'>{desc}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown(
        f"<div style='color:{cfg['color']};font-weight:800;font-size:0.9rem;"
        f"margin:12px 0 6px;'>🔐 Role Permissions</div>", unsafe_allow_html=True)
    for p in rc["permissions"]:
        color = "#00ff88" if p.startswith("✅") else "#ff6688"
        st.markdown(
            f"<div style='color:{color};font-size:0.82rem;'>{p}</div>",
            unsafe_allow_html=True)


# ── Role Selector ─────────────────────────────────────────────────────────────
def show_role_selector():
    st.markdown(_BASE_CSS, unsafe_allow_html=True)
    inject_tab_persistence()
    col_back, _ = st.columns([1, 5])
    with col_back:
        if st.button("← Back", key="back_to_landing"):
            st.session_state.show_login = False
            st.session_state.pop("selected_role", None)
            st.rerun()

    _, col_c, _ = st.columns([1, 3, 1])
    with col_c:
        st.markdown("""
        <div style='text-align:center;padding:1.5rem 0 1rem;'>
            <div style='font-size:3rem;'>🧠</div>
            <div style='font-size:2rem;font-weight:900;
                background:linear-gradient(135deg,#fff,#00d4ff,#00ff88);
                -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                background-clip:text;'>Choose Your Portal</div>
            <div style='color:#668;font-size:0.87rem;margin-top:5px;
                        margin-bottom:1.5rem;'>
                Select your role to access the correct login & features
            </div>
        </div>""", unsafe_allow_html=True)

        r1, r2, r3 = st.columns(3)
        for col, role, clr, icon, desc in [
            (r1,"admin",  "#ff4b4b","🔴","System Management"),
            (r2,"doctor", "#00d4ff","🩺","Patient Care"),
            (r3,"patient","#00ff88","👤","Health Monitoring"),
        ]:
            with col:
                rc = ROLE_CFG[role]
                perms_preview = rc["permissions"][:3]
                perm_html = "".join(
                    f"<div style='color:#{'00ff88' if p.startswith('✅') else 'ff6688'};"
                    f"font-size:0.72rem;'>{p}</div>"
                    for p in perms_preview)
                st.markdown(f"""
                <div style='background:linear-gradient(135deg,{clr}10,{clr}05);
                            border:2px solid {clr}44;border-radius:14px;
                            padding:16px;text-align:center;'>
                    <div style='font-size:2.2rem;'>{icon}</div>
                    <div style='color:{clr};font-weight:900;font-size:1rem;
                                margin:6px 0;'>{role.title()}</div>
                    <div style='color:#778;font-size:0.78rem;
                                margin-bottom:8px;'>{desc}</div>
                    {perm_html}
                </div>""", unsafe_allow_html=True)
                if st.button(f"Enter {role.title()} Portal", key=f"sel_{role}", use_container_width=True):
                    st.session_state.selected_role = role
                    st.rerun()


# ── Individual Role Auth Page ─────────────────────────────────────────────────
def show_role_auth_page(role: str):
    init_db()
    st.markdown(_BASE_CSS, unsafe_allow_html=True)
    cfg = ROLE_CFG[role]

    col_back, _ = st.columns([1, 5])
    with col_back:
        if st.button("← Back", key=f"back_{role}"):
            st.session_state.pop("selected_role", None)
            st.rerun()

    if role == "admin":
        _, col_c, _ = st.columns([1, 2, 1])
        with col_c:
            _role_header(role)
            _login_form(role, cfg)
        return

    left_col, mid_col, right_col = st.columns([1, 1.6, 1.2])

    with left_col:
        _role_header(role)
        _walkthrough(role, cfg)

    with mid_col:
        t_login, t_reg = st.tabs(["🔐 Login", "📝 Register"])
        with t_login:
            st.markdown("<br>", unsafe_allow_html=True)
            _login_form(role, cfg)
        with t_reg:
            st.markdown("<br>", unsafe_allow_html=True)
            _register_form(role, cfg)

    with right_col:
        tips = {
            "doctor": [
                "💡 Use strong passwords (mix letters + numbers)",
                "🔒 Don't share your login credentials",
                "📊 Review patient stress trends weekly",
                "🚨 Respond to high-stress alerts promptly",
                "📝 Keep clinical notes up-to-date",
            ],
            "patient": [
                "💡 Run predictions regularly for best tracking",
                "📋 Check your daily checklist every morning",
                "🤖 Use the Wellness Bot anytime you feel stressed",
                "💬 Chat your doctor if you have concerns",
                "🔒 Keep your account credentials private",
            ],
        }
        role_tips = tips.get(role, [])
        if role_tips:
            st.markdown(
                f"<div style='background:{cfg['bg']};border:1px solid "
                f"{cfg['color']}33;border-radius:12px;padding:14px 16px;'>"
                f"<div style='color:{cfg['color']};font-weight:800;font-size:0.9rem;"
                f"margin-bottom:8px;'>💡 Quick Tips</div>"
                + "".join(
                    f"<div style='color:#aaa;font-size:0.8rem;"
                    f"margin-bottom:5px;'>{t}</div>" for t in role_tips)
                + "</div>", unsafe_allow_html=True)


# ── Entry point ───────────────────────────────────────────────────────────────
def show_auth_page():
    init_db()

    if st.query_params.get("code"):
        _handle_google_callback()
        return

    role = st.session_state.get("selected_role")
    if role:
        show_role_auth_page(role)
    else:
        show_role_selector()


def logout():
    for k in ["logged_in", "user", "role", "show_login", "selected_role",
              "oauth_state", "_oauth_state_backup"]:
        st.session_state.pop(k, None)
    st.rerun()