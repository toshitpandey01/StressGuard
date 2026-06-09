import streamlit as st
import streamlit.components.v1 as components
from time_utils import DEFAULT_TIMEZONE, tz_label


ROLE_CFG = {
    "admin": {
        "accent": "#ff4b4b",
        "icon": "🔴",
        "grad": "linear-gradient(135deg,#1a0505,#2a1010)",
        "title": "Admin Command Center",
        "subtitle": "Manage users, assignments, analytics, appointments, and system-level oversight from one place.",
        "section": "✨ Admin Features",
        "steps_title": "🚀 Admin Workflow",
        "features": [
            ("👥", "User Directory", "Browse all registered users, inspect profiles, and manage doctor/patient accounts."),
            ("➕", "Add New User", "Create doctor or patient accounts directly from the admin panel."),
            ("🔗", "Doctor Assignment", "Link patients to their assigned doctors from the Assign tab."),
            ("📋", "Prediction Oversight", "Review all submitted stress predictions across the platform."),
            ("📈", "System Analytics", "Track doctors, patients, predictions, and overall system activity."),
            ("🩺", "Doctor Portfolios", "View and edit doctor portfolio details available to patients."),
            ("📅", "Appointments & Tickets", "Monitor appointment-related activity across the platform."),
            ("🔑", "Login Logs", "Audit recent user access history from the login logs tab."),
        ],
        "steps": [
            "Open the Admin Panel to review the latest system activity.",
            "Add new doctor and patient accounts from the Add User tab.",
            "Assign each patient to a doctor in the Assign tab.",
            "Review Predictions and Analytics for platform-wide monitoring.",
            "Check Portfolios, Appointments, and Login Logs for operational follow-up.",
        ],
    },
    "doctor": {
        "accent": "#00d4ff",
        "icon": "🩺",
        "grad": "linear-gradient(135deg,#0a1628,#0d2035)",
        "title": "Doctor Workspace",
        "subtitle": "Track patients, monitor alerts, write notes, and manage appointments from your clinical dashboard.",
        "section": "✨ Doctor Features",
        "steps_title": "🚀 Doctor Workflow",
        "features": [
            ("👤", "Assigned Patients", "Open each patient card to review history, notes, and checklist progress."),
            ("📝", "Clinical & Private Notes", "Write patient-specific notes and maintain your own private self-notes."),
            ("💬", "Realtime Chat", "Chat directly with patients and track unread message counts."),
            ("🚨", "Priority Stress Alerts", "Review medium/high stress alerts and respond to patients faster."),
            ("📅", "Appointment Management", "View, update, and download appointment information."),
            ("🔬", "Medical Reports", "Review uploaded patient medical reports and their extracted content."),
            ("👤", "Profile & Portfolio", "Maintain your doctor profile and patient-facing portfolio information."),
            ("⬇️", "Patient PDF Reports", "Generate downloadable PDF summaries for individual patients."),
        ],
        "steps": [
            "Start with the Doctor Panel tab to review assigned patients and pending checklist work.",
            "Open Alerts to see which patients may need attention first.",
            "Use Notes to document clinical observations and maintain private reminders.",
            "Respond in Chat and keep up with Appointments and Medical Reports.",
            "Update your Profile and Portfolio so patients can view current doctor information.",
        ],
    },
    "patient": {
        "accent": "#00ff88",
        "icon": "👤",
        "grad": "linear-gradient(135deg,#081a12,#0d2018)",
        "title": "Patient Wellness Hub",
        "subtitle": "Run stress checks, follow doctor instructions, chat securely, and manage your wellness records.",
        "section": "✨ Patient Features",
        "steps_title": "🚀 Patient Workflow",
        "features": [
            ("🔮", "Stress Prediction", "Use the Predict tab to assess stress from physiological inputs."),
            ("📊", "Prediction History", "Review previous results, trend charts, and downloadable reports."),
            ("📋", "Doctor Checklist", "Track daily, weekly, or monthly tasks assigned by your doctor."),
            ("💬", "Doctor Chat", "Message your assigned doctor and check unread conversation updates."),
            ("🤖", "Wellness Bot", "Get supportive wellness-focused responses whenever you need them."),
            ("📓", "Personal & Doctor Notes", "Keep personal notes and read notes shared by your doctor."),
            ("👨‍⚕️", "My Doctor", "View your assigned doctor and available doctor portfolio information."),
            ("📅", "Appointments & Reports", "Book appointments and upload/view your medical reports."),
        ],
        "steps": [
            "Go to Predict to run your latest stress assessment.",
            "Review History to understand recent trends and download reports when needed.",
            "Complete tasks in Checklist and read updates from Doctor Notes.",
            "Use Chat to stay in touch with your doctor and Appointments to manage visits.",
            "Visit Wellness Bot or Personal Notes whenever you need support or reflection.",
        ],
    },
}


def _fallback_stats():
    try:
        from database import get_stats
        stats = get_stats()
        total_users = stats.get("doctors", 0) + stats.get("patients", 0)
        return [
            ("🩺 Doctors", stats.get("doctors", 0)),
            ("👤 Patients", stats.get("patients", 0)),
            ("📊 Predictions", stats.get("predictions", 0)),
            ("👥 Total Users", total_users),
        ]
    except Exception:
        return [
            ("👤 Role", "Portal"),
            ("📊 Status", "Active"),
            ("🧠 App", "Stress Care"),
            ("✅ Session", "Ready"),
        ]



def _role_metrics(role: str, user: dict):
    user_id = user.get("id")

    if role == "admin":
        return _fallback_stats()

    if role == "doctor":
        try:
            from database import (
                get_patients_by_doctor,
                get_predictions_by_patient,
                get_unread_count,
                get_unread_alert_count,
            )
            patients = get_patients_by_doctor(user_id) or []
            total_preds = sum(len(get_predictions_by_patient(p["id"]) or []) for p in patients)
            unread = get_unread_count(user_id)
            alerts = get_unread_alert_count(user_id)
            return [
                ("👤 My Patients", len(patients)),
                ("📊 Patient Predictions", total_preds),
                ("💬 Unread Chats", unread),
                ("🚨 Alerts", alerts),
            ]
        except Exception:
            return _fallback_stats()

    if role == "patient":
        try:
            from database import (
                get_predictions_by_patient,
                get_unread_count,
                get_checklist_pending_count,
                get_doctor_of_patient,
            )
            preds = get_predictions_by_patient(user_id) or []
            unread = get_unread_count(user_id)
            pending = get_checklist_pending_count(user_id)
            doctor = get_doctor_of_patient(user_id)
            doctor_name = doctor.get("full_name", "Not assigned") if doctor else "Not assigned"
            return [
                ("📊 My Predictions", len(preds)),
                ("📋 Pending Tasks", pending),
                ("💬 Unread Chats", unread),
                ("👨‍⚕️ My Doctor", doctor_name),
            ]
        except Exception:
            return _fallback_stats()

    return _fallback_stats()



def app():
    user = st.session_state.get("user", {})
    role = st.session_state.get("role", "patient")
    name = user.get("full_name", "User")

    cfg = ROLE_CFG.get(role, ROLE_CFG["patient"])
    accent = cfg["accent"]

    # ── Greeting ─────────────────────────────────────────────────────────────
    components.html(f"""
    <div id="greeting-block" style="
        background:{cfg['grad']};
        border:1px solid {accent}33;
        border-radius:20px;
        padding:28px 32px;
        margin-bottom:18px;
        display:flex;
        align-items:center;
        gap:20px;
        font-family:'Nunito',sans-serif;
    ">
        <div style="font-size:3.5rem;" id="greet-icon">🌞</div>
        <div>
            <div id="greet-text" style="
                font-size:1.9rem;
                font-weight:900;
                background:linear-gradient(90deg,{accent},white);
                -webkit-background-clip:text;
                -webkit-text-fill-color:transparent;
                background-clip:text;
            ">Good Morning, {name}!</div>
            <div style="color:#aab4c8;font-size:0.92rem;margin-top:5px;">
                {cfg['icon']} {role.title()} Portal &nbsp;•&nbsp;
                <span id="greet-time" style="color:{accent};font-weight:700;"></span>
            </div>
            <div style="color:#d8e0ef;font-size:0.95rem;margin-top:8px;max-width:820px;">
                {cfg['subtitle']}
            </div>
        </div>
    </div>
    <script>
    (function(){{
        function updateGreeting(){{
            const timeZone = '{DEFAULT_TIMEZONE}';
            const parts = new Intl.DateTimeFormat('en-IN', {{
                timeZone,
                weekday:'short',
                day:'2-digit',
                month:'short',
                year:'numeric',
                hour:'2-digit',
                minute:'2-digit',
                hour12:false
            }}).formatToParts(new Date()).reduce((acc, part) => {{
                acc[part.type] = part.value;
                return acc;
            }}, {{}});
            var h = parseInt(parts.hour || '0', 10);
            var greeting, icon;
            if (h >= 5 && h < 12) {{ greeting = 'Good Morning'; icon = '🌅'; }}
            else if (h >= 12 && h < 17) {{ greeting = 'Good Afternoon'; icon = '🌤️'; }}
            else if (h >= 17 && h < 21) {{ greeting = 'Good Evening'; icon = '🌆'; }}
            else {{ greeting = 'Good Night'; icon = '🌙'; }}
            var gt = document.getElementById('greet-text');
            var gi = document.getElementById('greet-icon');
            var gtm = document.getElementById('greet-time');
            if (gt) gt.innerText = greeting + ', {name}!';
            if (gi) gi.innerText = icon;
            if (gtm) gtm.innerText = (parts.weekday || '') + ', ' + (parts.day || '') + ' ' + (parts.month || '') + ' ' + (parts.year || '') + ' — ' + (parts.hour || '00') + ':' + (parts.minute || '00') + ' {tz_label(DEFAULT_TIMEZONE)}';
        }}
        updateGreeting();
        setInterval(updateGreeting, 30000);
    }})();
    </script>
    """, height=150)

    # ── Role-based stats ─────────────────────────────────────────────────────
    stats = _role_metrics(role, user)
    cols = st.columns(4)
    for col, (label, value) in zip(cols, stats):
        col.metric(label, value)

    st.markdown("---")

    # ── Role-specific feature cards ──────────────────────────────────────────
    st.markdown(
        f"<h3 style='color:{accent};margin-bottom:12px;'>{cfg['section']}</h3>",
        unsafe_allow_html=True,
    )

    cols = st.columns(2)
    for i, (icon, title, desc) in enumerate(cfg["features"]):
        with cols[i % 2]:
            st.markdown(f"""
            <div style='background:linear-gradient(135deg,{accent}08,{accent}04);
                        border:1px solid {accent}33;border-radius:14px;
                        padding:14px 18px;margin-bottom:10px;'>
                <div style='font-size:1.6rem;margin-bottom:6px;'>{icon}</div>
                <div style='color:{accent};font-weight:800;font-size:0.95rem;
                            margin-bottom:4px;'>{title}</div>
                <div style='color:#aaa;font-size:0.82rem;line-height:1.5;'>{desc}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("---")

    # ── Role-specific quick guide ────────────────────────────────────────────
    st.markdown(
        f"<h3 style='color:{accent};margin-bottom:10px;'>{cfg['steps_title']}</h3>",
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        for idx, step in enumerate(cfg["steps"], 1):
            st.markdown(
                f"<div style='display:flex;gap:10px;align-items:flex-start;margin-bottom:8px;'>"
                f"<span style='background:{accent};color:#081018;border-radius:50%;"
                f"width:24px;height:24px;display:inline-flex;align-items:center;"
                f"justify-content:center;font-size:0.78rem;font-weight:900;'>{idx}</span>"
                f"<span style='color:#d7dce5;font-size:0.92rem;'>{step}</span></div>",
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # ── Footer ───────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div style='background:#0a0e1a;border:1px solid #1e2a3a;border-radius:12px;
                padding:16px 20px;margin-top:20px;text-align:center;'>
        <div style='color:{accent};font-weight:800;font-size:1rem;'>
            {cfg['icon']} {cfg['title']}</div>
        <div style='color:#556;font-size:0.78rem;margin-top:6px;'>
            Home screen powered by Streamlit
        </div>
    </div>""", unsafe_allow_html=True)
