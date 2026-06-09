

import streamlit as st
import datetime as _dt
import html

from database import (
    get_doctors_for_patient, get_all_doctors,
    get_doctor_portfolio, get_doctor_availability,
    get_available_slots_for_date,
    book_appointment, get_appointments_for_patient,
    patient_confirm_proposed, patient_decline_proposed,
    patient_request_reschedule, cancel_appointment,
    get_appointment_audit_log, get_pending_confirm_count_for_patient,
    create_ticket, get_tickets_by_user,
    get_user_by_id, check_booking_limit,
    MONTHLY_BOOKING_LIMIT, CONSEC_CANCEL_LIMIT, CANCEL_RESTRICT_DAYS,
    APPT_STATUS_PENDING, APPT_STATUS_CONFIRMED, APPT_STATUS_REJECTED,
    APPT_STATUS_DOCTOR_PROPOSED, APPT_STATUS_COMPLETED,
    APPT_STATUS_CANCELLED, APPT_STATUS_RESCHEDULED,
    DAYS_OF_WEEK,
)

from report_generator import generate_appointment_slip_pdf
from time_utils import format_appt_slot, format_db_timestamp, sanitize_timezone

ACCENT = "#00ff88"

# ── Status display config ─────────────────────────────────────────────────────
STATUS_CFG = {
    APPT_STATUS_PENDING:          ("⏳", "#f1c40f", "#1a1500"),
    APPT_STATUS_CONFIRMED:        ("✅", "#2ecc71", "#0a1a0a"),
    APPT_STATUS_REJECTED:         ("❌", "#ff4b4b", "#1a0505"),
    APPT_STATUS_DOCTOR_PROPOSED:  ("📝", "#aa88ff", "#1a0a2a"),
    APPT_STATUS_COMPLETED:        ("✔️", "#00d4ff", "#0a1628"),
    APPT_STATUS_CANCELLED:        ("🚫", "#778899", "#0d1520"),
    APPT_STATUS_RESCHEDULED:      ("🔄", "#ffaa44", "#1a1200"),
}


def _status_badge(status):
    icon, ac, _ = STATUS_CFG.get(status, ("❓","#aaa","#111"))
    return (f"<span style='background:{ac};color:#000;border-radius:6px;"
            f"padding:1px 8px;font-size:0.72rem;margin-left:6px;'>"
            f"{icon} {status}</span>")

def _slip_download_button(appt: dict, patient: dict, key_prefix: str):
    if appt.get("status") in [APPT_STATUS_CANCELLED, APPT_STATUS_REJECTED]:
        return
    doctor_id = appt.get("doctor_id")
    doctor = get_user_by_id(doctor_id) if doctor_id else None
    if not doctor:
        return
    timezone_name = sanitize_timezone((patient or {}).get("timezone"))
    try:
        slip_pdf = generate_appointment_slip_pdf(appt, patient, doctor, timezone_name=timezone_name)
        st.download_button(
            f"⬇️ Latest Slip (APT-{appt['id']:05d})",
            data=slip_pdf,
            file_name=f"appointment_slip_APT{appt['id']:05d}.pdf",
            mime="application/pdf",
            key=key_prefix,
            use_container_width=True,
        )
    except Exception as err:
        st.caption(f"Slip unavailable right now: {err}")




# ── Appointment activity banner ───────────────────────────────────────────────
def _appointment_activity_banner(patient_id: int, appts: list):
    """Show a collapsible recent-activity strip for appointment status changes."""
    # Pull unread appointment notifications from DB
    try:
        from database import get_appointment_notifications, mark_appointment_notifications_read
        notifs = get_appointment_notifications(patient_id, limit=5, unread_only=True)
    except Exception:
        # Fallback: derive from appointments list directly
        notifs = []

    # Derive recent events from appointments if no DB function
    if not notifs:
        _EVENT_ICONS = {
            APPT_STATUS_CONFIRMED:       ("✅", "#2ecc71", "Confirmed"),
            APPT_STATUS_COMPLETED:       ("✔️", "#00d4ff", "Completed"),
            APPT_STATUS_CANCELLED:       ("🚫", "#ff4b4b", "Cancelled"),
            APPT_STATUS_DOCTOR_PROPOSED: ("📝", "#aa88ff", "Reschedule Proposed"),
            APPT_STATUS_REJECTED:        ("❌", "#ff4b4b", "Rejected"),
        }
        recent_events = [
            a for a in appts
            if a.get("status") in _EVENT_ICONS
            and not st.session_state.get(f"_appt_seen_{a['id']}_{a.get('status')}")
        ][:4]

        if not recent_events:
            return

        with st.expander(
            f"🔔 {len(recent_events)} recent appointment update(s) — click to view",
            expanded=True):
            for a in recent_events:
                aid    = a["id"]
                status = a.get("status", "")
                icon, ac, label = _EVENT_ICONS.get(status, ("❓", "#aaa", status))
                extra = ""
                if status == APPT_STATUS_DOCTOR_PROPOSED:
                    extra = (f"<div style='color:#aa88ff;font-size:0.82rem;margin-top:3px;'>"
                             f"New proposed: 📅 {a.get('proposed_date','—')} "
                             f"🕐 {a.get('proposed_time','—')}</div>")
                st.markdown(
                    f"<div style='background:#0a1628;border-left:4px solid {ac};"
                    f"border-radius:8px;padding:10px 14px;margin-bottom:6px;'>"
                    f"<div style='color:white;font-weight:700;'>"
                    f"{icon} APT-{aid:05d} — <span style='color:{ac};'>{label}</span></div>"
                    f"<div style='color:#aaa;font-size:0.82rem;margin-top:3px;'>"
                    f"🩺 Dr. {a.get('doctor_name','—')} &nbsp;|&nbsp; "
                    f"📅 {a.get('appt_date','—')} 🕐 {a.get('appt_time','—')}</div>"
                    f"{extra}</div>",
                    unsafe_allow_html=True)
            if st.button("✅ Mark all as seen", key="appt_mark_seen_btn"):
                for a in recent_events:
                    st.session_state[f"_appt_seen_{a['id']}_{a.get('status')}"] = True
                st.rerun()
        return

    # If DB notifications returned — display them
    with st.expander(
        f"🔔 {len(notifs)} new appointment notification(s)", expanded=True):
        for n in notifs:
            st.markdown(
                f"<div style='background:#0a1628;border-left:4px solid #aa88ff;"
                f"border-radius:8px;padding:10px 14px;margin-bottom:6px;'>"
                f"<div style='color:white;font-weight:700;'>{n.get('title','')}</div>"
                f"<div style='color:#aaa;font-size:0.82rem;margin-top:2px;'>"
                f"{n.get('message','')}</div></div>",
                unsafe_allow_html=True)
        if st.button("✅ Mark all as read", key="appt_notif_read_btn"):
            try:
                mark_appointment_notifications_read(patient_id)
            except Exception:
                pass
            st.rerun()


def appointments_tab_patient(patient_id, user):
    """Main patient appointments tab — replaces old _appointments_tab_patient."""
    st.subheader("📅 Appointment Center")

    appts            = get_appointments_for_patient(patient_id)
    pending_confirms = get_pending_confirm_count_for_patient(patient_id)

    # ── Quota summary at top of page ──────────────────────────────────────────
    _, _, quota = check_booking_limit(patient_id)
    used      = quota.get("used", 0)
    limit     = quota.get("limit", MONTHLY_BOOKING_LIMIT)
    remaining = quota.get("remaining", limit - used)
    bar_color = "#2ecc71" if remaining > 4 else ("#f1c40f" if remaining > 1 else "#ff4b4b")
    ru        = quota.get("restricted_until")
    q1, q2, q3 = st.columns(3)
    q1.metric("📅 Used This Month",  f"{used} / {limit}")
    q2.metric("✅ Remaining",        remaining)
    q3.metric("🚫 Restriction",
              f"Until {str(ru)[:10]}" if ru else "None active",
              delta=None)

    # ── Recent activity notifications panel ───────────────────────────────────
    _appointment_activity_banner(patient_id, appts)

    # Alert banner for pending confirmations
    if pending_confirms > 0:
        st.markdown(
            f"<div style='background:#1a0a2a;border:1px solid #aa88ff44;"
            f"border-radius:10px;padding:10px 14px;margin-bottom:12px;'>"
            f"<span style='color:#aa88ff;font-weight:800;font-size:1rem;'>"
            f"📝 {pending_confirms} appointment(s) need your confirmation!</span>"
            f"<div style='color:#aaa;font-size:0.82rem;margin-top:2px;'>"
            f"Doctor proposed a schedule change — review the Confirm tab.</div></div>",
            unsafe_allow_html=True)

    confirm_lbl = f"📝 Confirm 🔴{pending_confirms}" if pending_confirms > 0 else "📝 Confirm"

    t_book, t_confirm, t_all, t_calendar, t_ticket = st.tabs([
        "📝 Book New", confirm_lbl, "📋 My Appointments",
        "📅 Calendar View", "🎫 Support Tickets"])

    with t_book:
        _book_tab(patient_id, user)

    with t_confirm:
        _confirm_tab(patient_id, appts, user)

    with t_all:
        _all_appointments_tab(patient_id, appts, user)

    with t_calendar:
        _calendar_tab(patient_id, appts)

    with t_ticket:
        _ticket_tab(patient_id, appts)


# ══════════════════════════════════════════════════════════════════════════════
#  BOOK NEW APPOINTMENT
# ══════════════════════════════════════════════════════════════════════════════


# ── Quota / restriction banner ────────────────────────────────────────────────
def _quota_banner(allowed: bool, limit_msg: str, quota: dict):
    """Render a colour-coded quota status bar at the top of the booking tab."""
    used      = quota.get("used", 0)
    limit     = quota.get("limit", MONTHLY_BOOKING_LIMIT)
    remaining = quota.get("remaining", limit - used)
    consec    = quota.get("consec_cancels", 0)
    ru        = quota.get("restricted_until")

    # ── Restriction block ─────────────────────────────────────────────────────
    if not allowed and ru:
        st.markdown(
            f"<div style='background:#2a0505;border:1px solid #ff4b4b;"
            f"border-left:5px solid #ff4b4b;border-radius:12px;"
            f"padding:16px 20px;margin-bottom:14px;'>"
            f"<div style='color:#ff4b4b;font-weight:900;font-size:1.05rem;'>"
            f"🚫 Booking Temporarily Restricted</div>"
            f"<div style='color:#ffaaaa;font-size:0.9rem;margin-top:6px;'>"
            f"You cancelled <strong>{CONSEC_CANCEL_LIMIT}</strong> appointments "
            f"in a row. New requests are blocked for <strong>{CANCEL_RESTRICT_DAYS} days</strong>.</div>"
            f"<div style='color:#ff6666;font-weight:700;margin-top:8px;font-size:0.95rem;'>"
            f"⏰ Restriction lifts: {str(ru)[:16]}</div>"
            f"</div>", unsafe_allow_html=True)
        return

    # ── Monthly quota exhausted ───────────────────────────────────────────────
    if not allowed and not ru:
        st.markdown(
            f"<div style='background:#1a1500;border:1px solid #f1c40f;"
            f"border-left:5px solid #f1c40f;border-radius:12px;"
            f"padding:16px 20px;margin-bottom:14px;'>"
            f"<div style='color:#f1c40f;font-weight:900;font-size:1.05rem;'>"
            f"📅 Monthly Limit Reached</div>"
            f"<div style='color:#ffe08a;font-size:0.9rem;margin-top:6px;'>"
            f"You have used all <strong>{limit}</strong> appointment requests "
            f"for this month. Resets on the 1st of next month.</div>"
            f"</div>", unsafe_allow_html=True)
        return

    # ── Normal quota indicator ────────────────────────────────────────────────
    pct        = int((used / limit) * 100) if limit else 0
    bar_color  = "#2ecc71" if remaining > 4 else ("#f1c40f" if remaining > 1 else "#ff4b4b")
    warn_html  = ""
    if consec >= 2:
        warn_html = (
            f"<div style='color:#ff9944;font-size:0.8rem;margin-top:6px;'>"
            f"⚠️ {consec}/{CONSEC_CANCEL_LIMIT} consecutive cancellations — "
            f"one more will block booking for {CANCEL_RESTRICT_DAYS} days.</div>")
    elif consec == 1:
        warn_html = (
            f"<div style='color:#aaa;font-size:0.8rem;margin-top:6px;'>"
            f"ℹ️ {consec}/{CONSEC_CANCEL_LIMIT} cancellation streak recorded.</div>")

    st.markdown(
        f"<div style='background:#0a1628;border:1px solid {bar_color}44;"
        f"border-radius:10px;padding:12px 16px;margin-bottom:14px;'>"
        f"<div style='display:flex;justify-content:space-between;"
        f"align-items:center;margin-bottom:6px;'>"
        f"<span style='color:white;font-weight:700;'>📅 Monthly Appointment Quota</span>"
        f"<span style='color:{bar_color};font-weight:800;'>"
        f"{used} / {limit} used &nbsp;|&nbsp; {remaining} remaining</span></div>"
        f"<div style='background:#1a2a3a;border-radius:6px;height:8px;overflow:hidden;'>"
        f"<div style='background:{bar_color};width:{pct}%;height:100%;border-radius:6px;'>"
        f"</div></div>"
        f"{warn_html}"
        f"</div>", unsafe_allow_html=True)


def _book_tab(patient_id, user):
    """Patient books a new appointment — can choose from multiple doctors."""

    # ── Booking limit / restriction check ─────────────────────────────────────
    allowed, limit_msg, quota = check_booking_limit(patient_id)
    _quota_banner(allowed, limit_msg, quota)
    if not allowed:
        return          # hard block — don't render the form at all

    my_doctors  = get_doctors_for_patient(patient_id)
    all_doctors = get_all_doctors()

    if not my_doctors and not all_doctors:
        st.warning("⚠️ No doctors registered in the system. Contact admin.")
        return

    # Doctor selection
    st.markdown(f"""
    <div style='background:#0a1e30;border:1px solid {ACCENT}44;
                border-radius:12px;padding:14px 18px;margin-bottom:12px;'>
        <div style='color:{ACCENT};font-weight:800;font-size:1.05rem;'>
            📝 Request New Appointment</div>
        <div style='color:#aaa;font-size:0.82rem;margin-top:3px;'>
            Choose a doctor, pick a date & time, and submit your request.
            The doctor will accept, reject, or propose an alternative.</div>
    </div>""", unsafe_allow_html=True)

    # Build doctor list: assigned doctors first, then all doctors
    doc_opts = {}
    for d in my_doctors:
        primary = " ⭐" if d.get("is_primary") else ""
        port = get_doctor_portfolio(d["id"])
        spec = port.get("specialization", "") if port else ""
        label = f"🩺 Dr. {d['full_name']}{primary}"
        if spec: label += f" — {spec}"
        doc_opts[label] = d

    # Add other doctors not already assigned
    assigned_ids = {d["id"] for d in my_doctors}
    for d in all_doctors:
        if d["id"] not in assigned_ids:
            port = get_doctor_portfolio(d["id"])
            spec = port.get("specialization", "") if port else ""
            label = f"🩺 Dr. {d['full_name']}"
            if spec: label += f" — {spec}"
            label += " (other)"
            doc_opts[label] = d

    sel_doc_label = st.selectbox("Choose Doctor", list(doc_opts.keys()),
                                  key="pat_bk_doc_sel")
    sel_doctor = doc_opts[sel_doc_label]
    doc_id = sel_doctor["id"]

    # Show doctor's availability
    avail = get_doctor_availability(doc_id)
    if avail:
        avail_text = " | ".join(
            f"**{a['day_of_week']}** {a['start_time']}–{a['end_time']}"
            for a in avail)
        st.markdown(
            f"<div style='background:#081a12;border-left:3px solid {ACCENT};"
            f"border-radius:6px;padding:8px 12px;margin-bottom:10px;'>"
            f"<span style='color:{ACCENT};font-weight:700;font-size:0.85rem;'>"
            f"🗓️ Doctor's Availability:</span>"
            f"<div style='color:#ccc;font-size:0.82rem;margin-top:4px;'>"
            f"{avail_text}</div></div>",
            unsafe_allow_html=True)
    else:
        st.info("ℹ️ Doctor has not set specific availability hours. You can still request.")

    # Date & time selection
    today = _dt.date.today()
    min_date = today + _dt.timedelta(days=1)

    b1, b2 = st.columns(2)
    with b1:
        appt_date = st.date_input("📅 Appointment Date",
                                    value=min_date, min_value=min_date,
                                    key="pat_bk_date")
    with b2:
        # Try to show available slots
        date_str = str(appt_date)
        available = get_available_slots_for_date(doc_id, date_str)
        if available:
            appt_time_str = st.selectbox("🕐 Available Slots", available,
                                          key="pat_bk_time_sel")
        else:
            appt_time = st.time_input("🕐 Appointment Time",
                                        value=_dt.time(10, 0), step=1800,
                                        key="pat_bk_time")
            appt_time_str = appt_time.strftime("%H:%M")

    # Appointment type
    appt_type = st.radio("Appointment Type",
                          ["Physical (In-person)", "Online (Teleconsult)"],
                          key="pat_bk_type", horizontal=True)
    appt_type_val = "Physical" if "Physical" in appt_type else "Online"

    reason = st.text_area("📝 Reason / Symptoms (optional)",
                            key="pat_bk_reason", height=70,
                            placeholder="Describe your symptoms or reason for visit…")

    # Emergency flag
    is_emergency = st.checkbox("🚨 Mark as Emergency", key="pat_bk_emergency")
    if is_emergency:
        st.warning("⚠️ Emergency appointments are prioritized but must still be approved by the doctor.")

    # Payment
    st.markdown("### 💳 Payment Details")
    pay_mode = st.selectbox("Payment Mode",
                              ["Online — UPI", "Online — Credit/Debit Card",
                               "Online — Net Banking", "Cash (On Visit)"],
                              key="pat_bk_paymode")
    pay_ref = ""
    if "Online" in pay_mode:
        pay_ref = st.text_input("Transaction Reference / UTR No.",
                                  key="pat_bk_ref",
                                  placeholder="Enter transaction ID…")

    # Fee info
    port = get_doctor_portfolio(doc_id)
    if port and port.get("consultation_fee"):
        st.markdown(
            f"<div style='background:#0d1b2a;border-left:3px solid #00d4ff;"
            f"border-radius:6px;padding:8px 12px;margin:6px 0;'>"
            f"<span style='color:#778;'>💰 Consultation Fee: </span>"
            f"<span style='color:#00d4ff;font-weight:700;'>"
            f"{port['consultation_fee']}</span></div>",
            unsafe_allow_html=True)

    if st.button("📅 Submit Appointment Request", key="pat_bk_submit",
                  type="primary", use_container_width=True):
        if "Online" in pay_mode and not pay_ref.strip():
            st.error("❌ Please provide a transaction reference for online payment.")
        else:
            pay_status = "Paid" if "Online" in pay_mode else "Cash"
            ok, result = book_appointment(
                patient_id, doc_id, date_str, appt_time_str,
                reason=reason, appointment_type=appt_type_val,
                payment_mode=pay_mode, payment_ref=pay_ref.strip(),
                payment_status=pay_status, is_emergency=int(is_emergency))
            if ok:
                st.balloons()
                st.success(f"✅ Appointment request submitted! (APT-{result:05d})")
                st.info("⏳ Waiting for doctor to accept, reject, or propose changes.")
                st.rerun()
            else:
                st.error(f"❌ {result}")


# ══════════════════════════════════════════════════════════════════════════════
#  CONFIRM / RESPOND TO DOCTOR PROPOSALS
# ══════════════════════════════════════════════════════════════════════════════


# ── Notify doctor of patient action (in-app) ──────────────────────────────────
def _notify_doctor_of_patient_action(a: dict, action: str, message: str):
    """Send an in-app notification to the doctor when a patient acts on an appointment."""
    doctor_id = a.get("doctor_id")
    if not doctor_id:
        return
    try:
        from database import add_notification
        titles = {
            "confirmed": "✅ Patient Confirmed Reschedule",
            "declined":  "❌ Patient Declined Reschedule",
            "cancelled": "🚫 Patient Cancelled Appointment",
            "rescheduled": "🔄 Patient Requested Reschedule",
        }
        title = titles.get(action, "📅 Appointment Update")
        add_notification(doctor_id, title, message, "appointment")
    except Exception:
        pass


def _confirm_tab(patient_id, appts, user):
    """Show appointments that need patient action (DoctorProposed)."""
    proposals = [a for a in appts if a.get("status") == APPT_STATUS_DOCTOR_PROPOSED]

    # ── Slip download after recent confirmation ───────────────────────────────
    recently_confirmed = [
        a for a in appts
        if a.get("status") == APPT_STATUS_CONFIRMED
        and st.session_state.get(f"_pat_just_confirmed_{a['id']}")
    ]
    if recently_confirmed:
        for a in recently_confirmed:
            aid = a["id"]
            st.markdown(
                f"<div style='background:#081a12;border:1px solid {ACCENT}55;"
                f"border-left:5px solid {ACCENT};border-radius:12px;"
                f"padding:16px 20px;margin-bottom:14px;'>"
                f"<div style='color:{ACCENT};font-weight:900;font-size:1.05rem;'>"
                f"✅ APT-{aid:05d} Confirmed!</div>"
                f"<div style='color:#aaa;font-size:0.85rem;margin-top:4px;'>"
                f"🩺 Dr. {a.get('doctor_name','—')} &nbsp;|&nbsp; "
                f"📅 {a.get('proposed_date') or a.get('appt_date','—')} "
                f"🕐 {a.get('proposed_time') or a.get('appt_time','—')}"
                f"</div></div>",
                unsafe_allow_html=True)
            _slip_download_button(a, user, key_prefix=f"pat_slip_just_{aid}")
        st.markdown("---")

    if not proposals:
        st.markdown(
            "<div style='background:#0d1b2a;border-radius:12px;"
            "padding:24px;text-align:center;'>"
            "<div style='font-size:2rem;'>✅</div>"
            "<div style='color:#00ff88;font-weight:700;margin-top:8px;'>"
            "No pending confirmations — all clear!</div></div>",
            unsafe_allow_html=True)
        return

    st.markdown(
        f"<div style='color:#aa88ff;font-weight:800;font-size:0.95rem;"
        f"margin-bottom:12px;'>📝 {len(proposals)} appointment(s) need your response:</div>",
        unsafe_allow_html=True)

    for a in proposals:
        aid       = a["id"]
        doc_note  = a.get("doctor_note", "")
        safe_doc_note = html.escape(str(doc_note)).replace("\n", "<br>")
        note_html = (
            f"<div style='background:#0d0820;border-left:3px solid #aa88ff;"
            f"border-radius:6px;padding:8px 12px;margin-top:8px;'>"
            f"<span style='color:#aa88ff;font-weight:700;font-size:0.82rem;'>📝 Doctor's note: </span>"
            f"<span style='color:#ccc;font-size:0.82rem;'>{safe_doc_note}</span></div>"
        ) if doc_note else ""

        st.markdown(
            f"<div style='background:#1a0a2a;border:1px solid #aa88ff44;"
            f"border-left:4px solid #aa88ff;border-radius:12px;"
            f"padding:16px 20px;margin-bottom:6px;'>"
            f"<div style='color:white;font-weight:800;font-size:1rem;'>"
            f"APT-{aid:05d} {_status_badge(a['status'])}</div>"
            f"<div style='color:#aaa;font-size:0.85rem;margin-top:6px;'>"
            f"🩺 Dr. {a.get('doctor_name','—')} &nbsp;|&nbsp; "
            f"🏥 {a.get('appointment_type','Physical')}</div>"
            f"<div style='display:flex;gap:24px;flex-wrap:wrap;margin-top:12px;'>"
            f"<div><div style='color:#778;font-size:0.78rem;'>Your original request</div>"
            f"<div style='color:#ff6688;font-weight:700;margin-top:2px;'>"
            f"📅 {a.get('appt_date','—')} &nbsp; 🕐 {a.get('appt_time','—')}</div></div>"
            f"<div style='color:#aa88ff;font-size:1.6rem;align-self:center;'>→</div>"
            f"<div><div style='color:#778;font-size:0.78rem;'>Doctor's proposed time</div>"
            f"<div style='color:#aa88ff;font-weight:800;font-size:1.05rem;margin-top:2px;'>"
            f"📅 {a.get('proposed_date','—')} &nbsp; 🕐 {a.get('proposed_time','—')}</div>"
            f"</div></div>"
            f"{note_html}</div>",
            unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ Accept Proposed Schedule",
                         key=f"pat_cnf_accept_{aid}",
                         type="primary", use_container_width=True):
                ok, msg = patient_confirm_proposed(aid, patient_id)
                if ok:
                    # Notify doctor in-app
                    _notify_doctor_of_patient_action(
                        a, "confirmed",
                        f"{a.get('patient_name','Patient')} confirmed the rescheduled "
                        f"appointment APT-{aid:05d}: "
                        f"{a.get('proposed_date','—')} at {a.get('proposed_time','—')}.")
                    st.session_state[f"_pat_just_confirmed_{aid}"] = True
                    st.success("✅ Appointment confirmed! Download your slip below.")
                    st.rerun()
                else:
                    st.error(msg)
        with c2:
            if st.button("❌ Decline & Cancel",
                         key=f"pat_cnf_decline_{aid}",
                         use_container_width=True):
                ok, msg = patient_decline_proposed(
                    aid, patient_id, "Patient declined proposed schedule")
                if ok:
                    _notify_doctor_of_patient_action(
                        a, "declined",
                        f"{a.get('patient_name','Patient')} declined the proposed "
                        f"schedule for APT-{aid:05d}. Appointment cancelled.")
                    st.warning("Appointment cancelled.")
                    st.rerun()
                else:
                    st.error(msg)


# ══════════════════════════════════════════════════════════════════════════════
#  ALL APPOINTMENTS
# ══════════════════════════════════════════════════════════════════════════════

def _all_appointments_tab(patient_id, appts, user):
    """Show all appointments with filtering and actions."""
    if not appts:
        st.info("No appointments yet. Book one in the 'Book New' tab!")
        return

    # Filter
    status_filter = st.selectbox("Filter by status",
        ["All", APPT_STATUS_PENDING, APPT_STATUS_CONFIRMED,
         APPT_STATUS_DOCTOR_PROPOSED, APPT_STATUS_COMPLETED,
         APPT_STATUS_REJECTED, APPT_STATUS_CANCELLED, APPT_STATUS_RESCHEDULED],
        key="pat_appt_filter")

    filtered = appts if status_filter == "All" else [
        a for a in appts if a.get("status") == status_filter]

    st.markdown(
        f"<div style='color:#aaa;font-size:0.82rem;margin-bottom:8px;'>"
        f"Showing {len(filtered)} appointment(s)</div>",
        unsafe_allow_html=True)

    for a in filtered:
        aid = a["id"]
        status = a.get("status", APPT_STATUS_PENDING)
        icon, ac, bg = STATUS_CFG.get(status, ("❓","#aaa","#111"))
        emergency_badge = (" <span style='background:#ff4b4b;color:white;"
                           "border-radius:4px;padding:1px 6px;font-size:0.7rem;'>"
                           "🚨 EMERGENCY</span>" if a.get("is_emergency") else "")
        reschedule_badge = ""
        if a.get("reschedule_of"):
            reschedule_badge = (f" <span style='background:#ffaa44;color:#000;"
                                f"border-radius:4px;padding:1px 6px;font-size:0.7rem;'>"
                                f"🔄 Reschedule of APT-{a['reschedule_of']:05d}</span>")

        proposed_html = (
            f"<div style='color:#aa88ff;font-size:0.82rem;margin-top:4px;'>"
            f"📝 Doctor proposed: {a.get('proposed_date','—')} {a.get('proposed_time','—')}"
            f"</div>" if a.get('proposed_date') else ""
        )
        safe_doctor_note = html.escape(str(a.get('doctor_note', ''))).replace("\n", "<br>")
        doctor_note_html = (
            f"<div style='color:#aaa;font-size:0.78rem;margin-top:2px;'>"
            f"🩺 Doctor note: {safe_doctor_note}</div>"
            if a.get('doctor_note') else ""
        )

        st.markdown(f"""
        <div style='background:{bg};border:1px solid {ac}44;
                    border-left:4px solid {ac};border-radius:10px;
                    padding:12px 16px;margin-bottom:8px;'>
            <div style='color:white;font-weight:800;font-size:0.95rem;'>
                APT-{aid:05d} {_status_badge(status)}{emergency_badge}{reschedule_badge}
            </div>
            <div style='color:#aaa;font-size:0.85rem;margin-top:4px;'>
                🩺 Dr. {a.get('doctor_name','—')} &nbsp;|&nbsp;
                🗓️ {format_appt_slot(a.get('appt_date','—'), a.get('appt_time','—'), sanitize_timezone(user.get('timezone')))} &nbsp;|&nbsp;
                🏥 {a.get('appointment_type','Physical')}
            </div>
            <div style='color:#778;font-size:0.78rem;margin-top:2px;'>
                📝 {a.get('reason','—') or '—'} &nbsp;|&nbsp;
                💳 {a.get('payment_mode','—')} ({a.get('payment_status','—')})
            </div>
            {proposed_html}
            {doctor_note_html}
        </div>""", unsafe_allow_html=True)

        _slip_download_button(a, user, key_prefix=f"pat_slip_{aid}")

        if status == APPT_STATUS_CONFIRMED:
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("🔄 Reschedule", key=f"pat_resched_{aid}"):
                    st.session_state[f"pat_resched_show_{aid}"] = True
            with c2:
                if st.button("❌ Cancel", key=f"pat_cancel_{aid}"):
                    ok, msg = cancel_appointment(aid, patient_id, "patient")
                    if ok:
                        _notify_doctor_of_patient_action(
                            a, "cancelled",
                            f"{a.get('patient_name', 'Patient')} cancelled "
                            f"APT-{aid:05d} scheduled on {a.get('appt_date','—')} "
                            f"at {a.get('appt_time','—')}.")
                        # Check if a restriction was just applied
                        _, restr_msg, new_quota = check_booking_limit(patient_id)
                        if new_quota.get("restricted_until"):
                            st.warning(
                                f"⚠️ Appointment cancelled. You have now cancelled "
                                f"{CONSEC_CANCEL_LIMIT} in a row — "
                                f"booking is blocked for {CANCEL_RESTRICT_DAYS} days.")
                        else:
                            consec = new_quota.get("consec_cancels", 0)
                            if consec > 0:
                                st.warning(
                                    f"Appointment cancelled. "
                                    f"⚠️ Warning: {consec}/{CONSEC_CANCEL_LIMIT} "
                                    f"consecutive cancellation(s) recorded.")
                            else:
                                st.warning("Appointment cancelled.")
                        st.rerun()
                    else:
                        st.error(msg)
            with c3:
                if st.button("📜 Audit Log", key=f"pat_audit_{aid}"):
                    st.session_state[f"pat_audit_show_{aid}"] = \
                        not st.session_state.get(f"pat_audit_show_{aid}", False)

        elif status == APPT_STATUS_PENDING:
            if st.button("❌ Cancel Request", key=f"pat_cancel_pend_{aid}"):
                ok, msg = cancel_appointment(aid, patient_id, "patient")
                if ok:
                    _notify_doctor_of_patient_action(
                        a, "cancelled",
                        f"{a.get('patient_name', 'Patient')} withdrew "
                        f"appointment request APT-{aid:05d}.")
                    _, _, new_quota = check_booking_limit(patient_id)
                    if new_quota.get("restricted_until"):
                        st.warning(
                            f"⚠️ Request cancelled. Booking blocked for "
                            f"{CANCEL_RESTRICT_DAYS} days due to repeated cancellations.")
                    else:
                        consec = new_quota.get("consec_cancels", 0)
                        if consec > 0:
                            st.warning(
                                f"Request cancelled. "
                                f"⚠️ {consec}/{CONSEC_CANCEL_LIMIT} "
                                f"consecutive cancellation(s) recorded.")
                        else:
                            st.warning("Request cancelled.")
                    st.rerun()
                else:
                    st.error(msg)

        # Reschedule form
        if st.session_state.get(f"pat_resched_show_{aid}"):
            with st.expander("🔄 Reschedule Appointment", expanded=True):
                rc1, rc2 = st.columns(2)
                with rc1:
                    new_date = st.date_input("New Date",
                        value=_dt.date.today() + _dt.timedelta(days=1),
                        min_value=_dt.date.today() + _dt.timedelta(days=1),
                        key=f"pat_resched_date_{aid}")
                with rc2:
                    new_time = st.time_input("New Time",
                        value=_dt.time(10, 0), step=1800,
                        key=f"pat_resched_time_{aid}")
                resched_reason = st.text_input("Reason for reschedule",
                    key=f"pat_resched_reason_{aid}",
                    placeholder="Why do you need to reschedule?")
                sc1, sc2 = st.columns(2)
                with sc1:
                    if st.button("✅ Submit Reschedule",
                                  key=f"pat_resched_submit_{aid}", type="primary"):
                        ok, result = patient_request_reschedule(
                            aid, patient_id,
                            str(new_date), new_time.strftime("%H:%M"),
                            resched_reason)
                        if ok:
                            _notify_doctor_of_patient_action(
                                a, "rescheduled",
                                f"{a.get('patient_name','Patient')} requested a "
                                f"reschedule for APT-{aid:05d} to "
                                f"{new_date} at {new_time.strftime('%H:%M')}. "
                                f"New APT-{result:05d} created.")
                            st.success(f"✅ Reschedule submitted! New APT-{result:05d}")
                            st.session_state.pop(f"pat_resched_show_{aid}", None)
                            st.rerun()
                        else:
                            st.error(result)
                with sc2:
                    if st.button("✖ Cancel", key=f"pat_resched_cancel_{aid}"):
                        st.session_state.pop(f"pat_resched_show_{aid}", None)
                        st.rerun()

        # Audit log display
        if st.session_state.get(f"pat_audit_show_{aid}"):
            _show_audit_log(aid)


# ══════════════════════════════════════════════════════════════════════════════
#  CALENDAR VIEW
# ══════════════════════════════════════════════════════════════════════════════

def _calendar_tab(patient_id, appts):
    """Simple calendar-like view of appointments."""
    st.markdown("**📅 My Appointment Calendar**")

    if not appts:
        st.info("No appointments to show.")
        return

    # Group by date
    from collections import defaultdict
    by_date = defaultdict(list)
    for a in appts:
        if a.get("status") not in [APPT_STATUS_CANCELLED, APPT_STATUS_REJECTED]:
            by_date[a.get("appt_date", "")].append(a)

    for date_str in sorted(by_date.keys(), reverse=True):
        day_appts = by_date[date_str]
        try:
            dt = _dt.datetime.strptime(date_str, "%Y-%m-%d")
            day_label = dt.strftime("%A, %B %d, %Y")
        except:
            day_label = date_str

        st.markdown(
            f"<div style='color:{ACCENT};font-weight:800;font-size:0.95rem;"
            f"margin:12px 0 6px;border-bottom:1px solid #1e3a5a;padding-bottom:4px;'>"
            f"📅 {day_label}</div>",
            unsafe_allow_html=True)

        for a in sorted(day_appts, key=lambda x: x.get("appt_time", "")):
            status = a.get("status", "")
            icon, ac, _ = STATUS_CFG.get(status, ("❓","#aaa","#111"))
            st.markdown(
                f"<div style='display:flex;align-items:center;gap:10px;"
                f"padding:6px 12px;margin-bottom:4px;'>"
                f"<span style='color:{ac};font-weight:700;min-width:50px;'>"
                f"{a.get('appt_time','—')}</span>"
                f"<span style='color:white;'>🩺 Dr. {a.get('doctor_name','—')}</span>"
                f"<span style='color:#778;font-size:0.8rem;'>"
                f"({a.get('appointment_type','')}) — {a.get('reason','')[:40]}</span>"
                f"{_status_badge(status)}</div>",
                unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  SUPPORT TICKETS
# ══════════════════════════════════════════════════════════════════════════════

def _ticket_tab(patient_id, appts):
    """Patient can file support tickets for admin review."""
    st.markdown(f"""
    <div style='background:#0a1e30;border:1px solid {ACCENT}44;
                border-radius:10px;padding:12px 16px;margin-bottom:12px;'>
        <div style='color:{ACCENT};font-weight:800;'>🎫 Support Tickets</div>
        <div style='color:#aaa;font-size:0.82rem;margin-top:3px;'>
            File a ticket if you need admin help with appointments, reassignments,
            billing issues, or complaints.</div>
    </div>""", unsafe_allow_html=True)

    # New ticket form
    with st.expander("📝 File New Ticket"):
        # Optional appointment link
        appt_labels = {"— None —": None}
        for a in appts:
            appt_labels[f"APT-{a['id']:05d} ({a.get('status','')})"] = a["id"]
        sel_appt = st.selectbox("Link to Appointment (optional)",
                                 list(appt_labels.keys()),
                                 key="pat_tkt_appt")

        ticket_type = st.selectbox("Ticket Type",
            ["General", "Reschedule Issue", "Billing",
             "Doctor Complaint", "Emergency Reassign", "Other"],
            key="pat_tkt_type")
        subject = st.text_input("Subject *", key="pat_tkt_subj",
                                 placeholder="Brief subject line…")
        desc = st.text_area("Description", key="pat_tkt_desc", height=100,
                             placeholder="Describe your issue in detail…")

        if st.button("📤 Submit Ticket", key="pat_tkt_submit", type="primary"):
            if not subject.strip():
                st.warning("Please enter a subject.")
            else:
                tid = create_ticket(
                    appt_labels[sel_appt], patient_id, "patient",
                    subject.strip(), desc.strip(), ticket_type)
                st.success(f"✅ Ticket #{tid} submitted! Admin will review it.")
                st.rerun()

    # My tickets
    st.markdown("---")
    st.markdown("**📋 My Tickets**")
    tickets = get_tickets_by_user(patient_id)
    if not tickets:
        st.info("No tickets filed yet.")
    else:
        for t in tickets:
            tid = t["id"]
            ts = t.get("status", "Open")
            ts_color = {"Open":"#f1c40f","Reviewed":"#00d4ff","Closed":"#2ecc71"}.get(ts,"#aaa")
            st.markdown(f"""
            <div style='background:#0d1b2a;border-left:3px solid {ts_color};
                        border-radius:8px;padding:10px 14px;margin-bottom:8px;'>
                <div style='color:white;font-weight:700;'>
                    🎫 #{tid} — {t.get('subject','—')}
                    <span style='background:{ts_color};color:#000;border-radius:4px;
                    padding:1px 6px;font-size:0.72rem;margin-left:6px;'>{ts}</span>
                </div>
                <div style='color:#778;font-size:0.78rem;margin-top:2px;'>
                    Type: {t.get('ticket_type','—')} |
                    Filed: {format_db_timestamp(t.get('created_at',''), sanitize_timezone(st.session_state.get('user', {}).get('timezone')))}
                    {f"| APT-{t['appt_id']:05d}" if t.get('appt_id') else ""}
                </div>
                {f"<div style='color:#aaa;font-size:0.82rem;margin-top:4px;'>{t.get('description','')}</div>"
                 if t.get('description') else ""}
                {f"<div style='color:#00d4ff;font-size:0.82rem;margin-top:4px;'>"
                 f"👤 Admin: {t.get('admin_note','')}</div>"
                 if t.get('admin_note') else ""}
            </div>""", unsafe_allow_html=True)


# ── Shared: Audit log display ────────────────────────────────────────────────

def _show_audit_log(appt_id):
    """Show appointment audit trail."""
    logs = get_appointment_audit_log(appt_id)
    if not logs:
        st.info("No audit history yet.")
        return

    st.markdown(f"**📜 Audit Trail — APT-{appt_id:05d}**")
    for log in logs:
        role_icon = {"patient":"👤","doctor":"🩺","admin":"🔴"}.get(
            log.get("actor_role",""), "❓")
        st.markdown(
            f"<div style='display:flex;gap:10px;padding:4px 0;"
            f"border-bottom:1px solid #1e3a5a22;'>"
            f"<span style='color:#556;font-size:0.75rem;min-width:120px;'>"
            f"{format_db_timestamp(log.get('created_at',''), sanitize_timezone(st.session_state.get('user', {}).get('timezone')))}</span>"
            f"<span style='font-size:0.85rem;'>{role_icon}</span>"
            f"<span style='color:white;font-size:0.85rem;font-weight:600;'>"
            f"{log.get('actor_name','—')}</span>"
            f"<span style='color:#00d4ff;font-size:0.82rem;'>"
            f"{log.get('action','—')}</span>"
            f"<span style='color:#aaa;font-size:0.78rem;'>"
            f"{log.get('details','')[:80]}</span></div>",
            unsafe_allow_html=True)