"""
doctor_appointments.py  –  Stress Level Detector
Standalone appointments tab for the Doctor Dashboard.

Features:
  • All / Pending / Proposed / Completed / Cancelled sub-tabs
  • Complete + Cancel buttons (duplicate-key-safe prefixes)
  • Reschedule — doctor proposes new date/time, patient gets notified to confirm
  • DoctorProposed status shown with proposed date/time
  • Summary metrics bar with Proposed count
  • PDF + CSV export
"""

import streamlit as st
from datetime import date, datetime, timedelta

from time_utils import format_appt_slot, format_db_timestamp, sanitize_timezone

from database import (
    get_appointments_for_doctor,
    doctor_accept_appointment,
    doctor_reject_appointment,
    doctor_complete_appointment,
    cancel_appointment,
    doctor_propose_change,
    create_ticket,
    get_tickets_by_user,
    APPT_STATUS_PENDING,
    APPT_STATUS_ACCEPTED,
    APPT_STATUS_DOCTOR_PROPOSED,
    APPT_STATUS_PATIENT_CONFIRM,
    APPT_STATUS_CONFIRMED,
    APPT_STATUS_COMPLETED,
    APPT_STATUS_CANCELLED,
    APPT_STATUS_RESCHEDULED,
    APPT_STATUS_REJECTED,
)

ACCENT = "#00d4ff"

# ── Status config — covers every possible DB value ────────────────────────────
STATUS_CFG = {
    APPT_STATUS_PENDING:         {"color": "#f1c40f", "bg": "#1a1500",  "icon": "⏳", "label": "Pending"},
    APPT_STATUS_ACCEPTED:        {"color": "#f1c40f", "bg": "#1a1500",  "icon": "⏳", "label": "Accepted"},
    APPT_STATUS_PATIENT_CONFIRM: {"color": "#aa88ff", "bg": "#1a0a2a",  "icon": "📝", "label": "Awaiting Confirm"},
    APPT_STATUS_DOCTOR_PROPOSED: {"color": "#aa88ff", "bg": "#1a0a2a",  "icon": "📝", "label": "Proposed"},
    APPT_STATUS_CONFIRMED:       {"color": "#2ecc71", "bg": "#0a1a0a",  "icon": "✅", "label": "Confirmed"},
    APPT_STATUS_COMPLETED:       {"color": "#00d4ff", "bg": "#0a1628",  "icon": "✔️", "label": "Completed"},
    APPT_STATUS_CANCELLED:       {"color": "#ff4b4b", "bg": "#1a0505",  "icon": "❌", "label": "Cancelled"},
    APPT_STATUS_REJECTED:        {"color": "#ff4b4b", "bg": "#1a0505",  "icon": "🚫", "label": "Rejected"},
    APPT_STATUS_RESCHEDULED:     {"color": "#ffaa44", "bg": "#1a1200",  "icon": "🔄", "label": "Rescheduled"},
}

# Statuses that need Accept/Reject/Propose buttons (Pending workflow)
NEEDS_ACCEPT   = {APPT_STATUS_PENDING, APPT_STATUS_ACCEPTED}
# Statuses that need Complete/Cancel/Reschedule buttons (Confirmed workflow)
NEEDS_COMPLETE = {APPT_STATUS_CONFIRMED, APPT_STATUS_PATIENT_CONFIRM}
# Statuses that show "waiting for patient" UI
NEEDS_WITHDRAW = {APPT_STATUS_DOCTOR_PROPOSED}


# ── 30-min time slots 08:00 – 20:00 ──────────────────────────────────────────
def _time_slots():
    slots, t = [], datetime.strptime("08:00", "%H:%M")
    end = datetime.strptime("20:00", "%H:%M")
    while t <= end:
        slots.append(t.strftime("%H:%M"))
        t += timedelta(minutes=30)
    return slots


# ── Notification + Email helper ───────────────────────────────────────────────
_NOTIF_CFG = {
    # event → (icon, short_title, in_app_msg_template, email_subject)
    "accepted": (
        "✅", "Appointment Confirmed",
        "Dr. {doctor} confirmed your appointment on {date} at {time}.",
        "Your Appointment Has Been Confirmed",
    ),
    "rejected": (
        "❌", "Appointment Rejected",
        "Dr. {doctor} rejected your appointment request (APT-{appt_id}).",
        "Appointment Request Rejected",
    ),
    "cancelled": (
        "🚫", "Appointment Cancelled",
        "Your appointment (APT-{appt_id}) on {date} at {time} was cancelled by Dr. {doctor}.",
        "Appointment Cancelled",
    ),
    "completed": (
        "✔️", "Appointment Completed",
        "Your appointment (APT-{appt_id}) with Dr. {doctor} has been marked complete.",
        "Appointment Completed",
    ),
    "rescheduled": (
        "📝", "Doctor Proposed New Schedule",
        "Dr. {doctor} proposed a new time for APT-{appt_id}: {new_date} at {new_time}. Please confirm.",
        "Action Required: Doctor Proposed a New Appointment Time",
    ),
    "reschedule_cancelled": (
        "🔄", "Reschedule Proposal Withdrawn",
        "Dr. {doctor} withdrew the reschedule proposal for APT-{appt_id}. Original slot restored.",
        "Reschedule Proposal Withdrawn",
    ),
}


def _notify(a: dict, event: str, new_date: str = "", new_time: str = "", note: str = ""):
    """Send in-app notification AND email to patient for appointment events."""
    appt_id    = a.get("id", "?")
    patient_id = a.get("patient_id")
    doctor_nm  = a.get("doctor_name", "Doctor")
    orig_date  = a.get("appt_date", "—")
    orig_time  = a.get("appt_time", "—")
    pat_email  = a.get("patient_email", "")
    pat_name   = a.get("patient_name", "Patient")

    cfg = _NOTIF_CFG.get(event)
    if not cfg:
        return
    icon, title, msg_tmpl, email_subj = cfg

    msg = msg_tmpl.format(
        appt_id=f"{appt_id:05d}" if isinstance(appt_id, int) else appt_id,
        doctor=doctor_nm,
        date=orig_date, time=orig_time,
        new_date=new_date or orig_date,
        new_time=new_time or orig_time,
    )
    if note:
        msg += f" Note: {note}"

    # ── In-app notification ───────────────────────────────────────────────────
    if patient_id:
        try:
            from database import add_notification
            add_notification(patient_id, f"{icon} {title}", msg, "appointment")
        except Exception:
            pass

    # ── Email notification ─────────────────────────────────────────────────────
    if pat_email:
        try:
            from email_service import send_appointment_email
            send_appointment_email(
                pat_email, pat_name, event, {
                    "patient_name":   pat_name,
                    "doctor_name":    doctor_nm,
                    "appt_id":        f"{appt_id:05d}" if isinstance(appt_id, int) else str(appt_id),
                    "appt_date":      orig_date,
                    "appt_time":      orig_time,
                    "proposed_date":  new_date,
                    "proposed_time":  new_time,
                    "reason":         a.get("reason", ""),
                    "payment_mode":   a.get("payment_mode", "—"),
                    "payment_status": a.get("payment_status", "—"),
                    "doctor_note":    note,
                    "subject_override": email_subj,
                }
            )
        except Exception:
            pass


# ── Reschedule form ───────────────────────────────────────────────────────────
def _reschedule_form(a: dict, key_prefix: str, doctor_id: int):
    appt_id = a.get("id")

    st.markdown("""
    <div style='background:#1a0a2a;border:1px solid #aa88ff44;border-radius:10px;
                padding:14px 18px;margin:4px 0 10px;'>
        <div style='color:#aa88ff;font-weight:800;font-size:0.9rem;margin-bottom:6px;'>
            🗓️ Propose New Date / Time</div>
        <div style='color:#aaa;font-size:0.78rem;'>
            The patient will receive a notification to confirm or decline.
            The appointment remains active until they respond.
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_d, col_t = st.columns(2)
    with col_d:
        new_date = st.date_input(
            "📅 New Date",
            min_value=date.today(),
            value=date.today() + timedelta(days=1),
            key=f"rs_date_{key_prefix}_{appt_id}")
    with col_t:
        slots = _time_slots()
        current_time = a.get("appt_time", "09:00")
        default_idx = slots.index(current_time) if current_time in slots else 2
        new_time = st.selectbox(
            "🕐 New Time",
            options=slots,
            index=default_idx,
            key=f"rs_time_{key_prefix}_{appt_id}")

    note = st.text_area(
        "📝 Note to Patient (optional)",
        placeholder="e.g., Rescheduling due to an emergency. Apologies for the inconvenience.",
        key=f"rs_note_{key_prefix}_{appt_id}",
        max_chars=300)

    # Preview the change
    st.markdown(
        f"<div style='background:#0d0818;border:1px solid #aa88ff33;"
        f"border-radius:8px;padding:8px 14px;margin:8px 0;"
        f"font-size:0.82rem;'>"
        f"<span style='color:#778;'>Current: </span>"
        f"<b style='color:white;'>{a.get('appt_date','—')} "
        f"at {a.get('appt_time','—')}</b>"
        f"<span style='color:#aa88ff;font-size:1rem;'> → </span>"
        f"<span style='color:#778;'>Proposed: </span>"
        f"<b style='color:#aa88ff;'>{new_date} at {new_time}</b>"
        f"</div>",
        unsafe_allow_html=True)

    cb1, cb2 = st.columns([2, 1])
    with cb1:
        if st.button("📤 Send Reschedule Request",
                     key=f"rs_submit_{key_prefix}_{appt_id}",
                     type="primary", use_container_width=True):
            ok, msg = doctor_propose_change(
                appt_id, doctor_id, str(new_date), new_time, note.strip())
            if ok:
                _notify(a, "rescheduled",
                        new_date=str(new_date), new_time=new_time,
                        note=note.strip())
                st.success(f"✅ {msg}")
                st.session_state[f"show_rs_{key_prefix}_{appt_id}"] = False
                st.rerun()
            else:
                st.error(f"❌ {msg}")
    with cb2:
        if st.button("✖ Close", key=f"rs_close_{key_prefix}_{appt_id}",
                     use_container_width=True):
            st.session_state[f"show_rs_{key_prefix}_{appt_id}"] = False
            st.rerun()


# ── Single appointment card ───────────────────────────────────────────────────
def _appt_card(a: dict, key_prefix: str, doctor_id: int, show_controls: bool = True):
    status   = a.get("status", APPT_STATUS_PENDING)
    cfg      = STATUS_CFG.get(status, {"color": "#778899", "bg": "#0d1b2a", "icon": "❓"})
    ac       = cfg["color"]
    bg       = cfg["bg"]
    icon     = cfg["icon"]
    appt_id  = a.get("id", "?")
    pat_name = a.get("patient_name", "—")
    timezone_name = sanitize_timezone((st.session_state.get('user') or {}).get('timezone'))
    appt_dt  = a.get("appt_date", "—")
    appt_tm  = a.get("appt_time", "—")
    appt_slot = format_appt_slot(appt_dt, appt_tm, timezone_name, include_zone=False)
    pat_email= a.get("patient_email", "—") or "—"
    pat_phone= a.get("patient_phone", "—") or "—"
    reason   = a.get("reason", "—") or "No reason provided"
    pay_mode = a.get("payment_mode", "—")
    pay_stat = a.get("payment_status", "—")

    # Proposed time banner — built before the markdown call
    proposed_html = ""
    if status == APPT_STATUS_DOCTOR_PROPOSED:
        pd_ = a.get("proposed_date", "—")
        pt_ = a.get("proposed_time", "—")
        proposed_slot = format_appt_slot(pd_, pt_, timezone_name, include_zone=False)
        proposed_html = (
            "<div style='color:#aa88ff;font-size:0.78rem;margin-top:6px;"
            "background:#2a1040;border-radius:6px;padding:3px 10px;"
            "display:inline-block;'>"
            + "&#128221; Proposed: <b>" + proposed_slot + "</b> &mdash; awaiting patient confirmation"
            + "</div>")
    # Escape braces so .format() template does not misinterpret HTML
    proposed_html = proposed_html.replace("{", "&#123;").replace("}", "&#125;")

    # Use a template string with .format() — safest approach, no f-string issues
    CARD_TMPL = (
        "<div style='background:{BG};border:1px solid {AC}33;"
        "border-left:4px solid {AC};border-radius:12px;"
        "padding:14px 18px;margin-bottom:6px;'>"
        "<div style='display:flex;align-items:flex-start;"
        "justify-content:space-between;gap:10px;'>"
        "<div style='flex:1;'>"
        "<div style='color:white;font-weight:800;font-size:0.97rem;margin-bottom:4px;'>"
        "&#128100; {PAT_NAME}"
        "<span style='background:{AC};color:#000;border-radius:6px;"
        "padding:1px 9px;font-size:0.7rem;margin-left:8px;font-weight:700;'>"
        "{STATUS}</span>"
        "</div>"
        "<div style='color:#aaa;font-size:0.83rem;margin-bottom:3px;'>"
        "&#128197; <b style='color:white;'>{SLOT}</b>"
        " &nbsp;&nbsp;&#128231; {EMAIL}"
        " &nbsp;&nbsp;&#128241; {PHONE}"
        "</div>"
        "<div style='color:#778;font-size:0.78rem;'>"
        "&#128221; {REASON}"
        " &nbsp;|&nbsp; &#128179; {PAY_MODE} &mdash; {PAY_STAT}"
        "</div>"
        "{PROPOSED}"
        "</div>"
        "</div>"
        "</div>"
    )
    card_html = CARD_TMPL.format(
        BG=bg, AC=ac,
        PAT_NAME=pat_name,
        STATUS=cfg.get("label", status),
        SLOT=appt_slot,
        EMAIL=pat_email, PHONE=pat_phone,
        REASON=reason,
        PAY_MODE=pay_mode, PAY_STAT=pay_stat,
        PROPOSED=proposed_html,
    )
    st.markdown(card_html, unsafe_allow_html=True)

    # ── Action buttons — driven by status sets, not individual string comparisons ──
    if show_controls and status in NEEDS_ACCEPT:
        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            if st.button("✅ Accept", key=f"appt_accept_{key_prefix}_{appt_id}",
                         use_container_width=True, type="primary"):
                ok, msg = doctor_accept_appointment(appt_id, doctor_id)
                if ok:
                    _notify(a, "accepted")
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        with c2:
            if st.button("❌ Reject", key=f"appt_reject_{key_prefix}_{appt_id}",
                         use_container_width=True):
                ok, msg = doctor_reject_appointment(appt_id, doctor_id, "Rejected by doctor")
                if ok:
                    _notify(a, "rejected")
                    st.warning(msg)
                    st.rerun()
                else:
                    st.error(msg)
        with c3:
            toggle_key = f"show_rs_{key_prefix}_{appt_id}"
            if toggle_key not in st.session_state:
                st.session_state[toggle_key] = False
            btn_lbl = "🔒 Close" if st.session_state[toggle_key] else "🗓️ Propose Time"
            if st.button(btn_lbl, key=f"appt_rs_toggle_{key_prefix}_{appt_id}",
                         use_container_width=True):
                st.session_state[toggle_key] = not st.session_state[toggle_key]
                st.rerun()
        if st.session_state.get(f"show_rs_{key_prefix}_{appt_id}"):
            _reschedule_form(a, key_prefix, doctor_id)

    elif show_controls and status in NEEDS_COMPLETE:
        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            if st.button("✅ Complete", key=f"appt_done_{key_prefix}_{appt_id}",
                         use_container_width=True, type="primary"):
                ok, msg = doctor_complete_appointment(appt_id, doctor_id)
                if ok:
                    _notify(a, "completed")
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        with c2:
            if st.button("❌ Cancel", key=f"appt_cancel_{key_prefix}_{appt_id}",
                         use_container_width=True):
                ok, msg = cancel_appointment(appt_id, doctor_id, "doctor",
                                             "Cancelled by doctor")
                if ok:
                    _notify(a, "cancelled")
                    st.warning(msg)
                    st.rerun()
                else:
                    st.error(msg)
        with c3:
            toggle_key = f"show_rs_{key_prefix}_{appt_id}"
            if toggle_key not in st.session_state:
                st.session_state[toggle_key] = False
            btn_lbl = "🔒 Close" if st.session_state[toggle_key] else "🗓️ Reschedule"
            if st.button(btn_lbl, key=f"appt_rs_toggle_{key_prefix}_{appt_id}",
                         use_container_width=True):
                st.session_state[toggle_key] = not st.session_state[toggle_key]
                st.rerun()
        if st.session_state.get(f"show_rs_{key_prefix}_{appt_id}"):
            _reschedule_form(a, key_prefix, doctor_id)

    elif show_controls and status in NEEDS_WITHDRAW:
        st.markdown(
            "<div style='color:#aa88ff;font-size:0.78rem;margin:-2px 0 6px;'>"
            "⏳ Waiting for patient to confirm or decline.</div>",
            unsafe_allow_html=True)
        if st.button("❌ Withdraw Proposal",
                     key=f"appt_cancel_prop_{key_prefix}_{appt_id}"):
            ok, msg = cancel_appointment(appt_id, doctor_id, "doctor",
                                         "Doctor withdrew proposal")
            if ok:
                _notify(a, "reschedule_cancelled")
                st.warning("Proposal withdrawn.")
                st.rerun()
            else:
                st.error(msg)


# ── Summary metrics bar ───────────────────────────────────────────────────────
def _summary_bar(appts: list):
    total     = len(appts)
    pending   = sum(1 for a in appts if a.get("status") in NEEDS_ACCEPT)
    proposed  = sum(1 for a in appts if a.get("status") in NEEDS_WITHDRAW)
    confirmed = sum(1 for a in appts if a.get("status") in NEEDS_COMPLETE)
    completed = sum(1 for a in appts if a.get("status") == APPT_STATUS_COMPLETED)
    cancelled = sum(1 for a in appts if a.get("status") in
                    {APPT_STATUS_CANCELLED, APPT_STATUS_REJECTED})

    st.markdown(f"""
    <div style='display:flex;gap:10px;margin-bottom:16px;flex-wrap:wrap;'>
        <div style='background:#0d1b2a;border:1px solid #1e3a5a;border-radius:10px;
                    padding:10px 14px;flex:1;text-align:center;min-width:70px;'>
            <div style='color:#778;font-size:0.72rem;'>Total</div>
            <div style='color:white;font-size:1.3rem;font-weight:900;'>{total}</div>
        </div>
        <div style='background:#1a1500;border:1px solid #f1c40f44;border-radius:10px;
                    padding:10px 14px;flex:1;text-align:center;min-width:70px;'>
            <div style='color:#778;font-size:0.72rem;'>⏳ Pending</div>
            <div style='color:#f1c40f;font-size:1.3rem;font-weight:900;'>{pending}</div>
        </div>
        <div style='background:#1a0a2a;border:1px solid #aa88ff44;border-radius:10px;
                    padding:10px 14px;flex:1;text-align:center;min-width:70px;'>
            <div style='color:#778;font-size:0.72rem;'>📝 Proposed</div>
            <div style='color:#aa88ff;font-size:1.3rem;font-weight:900;'>{proposed}</div>
        </div>
        <div style='background:#0a1a0a;border:1px solid #2ecc7144;border-radius:10px;
                    padding:10px 14px;flex:1;text-align:center;min-width:70px;'>
            <div style='color:#778;font-size:0.72rem;'>✅ Done</div>
            <div style='color:#2ecc71;font-size:1.3rem;font-weight:900;'>{completed}</div>
        </div>
        <div style='background:#1a0505;border:1px solid #ff4b4b44;border-radius:10px;
                    padding:10px 14px;flex:1;text-align:center;min-width:70px;'>
            <div style='color:#778;font-size:0.72rem;'>❌ Cancelled</div>
            <div style='color:#ff4b4b;font-size:1.3rem;font-weight:900;'>{cancelled}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ── Export tab ────────────────────────────────────────────────────────────────
def _download_tab(appts: list, doctor_name: str, timezone_name: str | None = None):
    st.markdown(f"<div style='color:{ACCENT};font-weight:800;margin-bottom:10px;'>"
                f"⬇️ Export Appointment Records</div>", unsafe_allow_html=True)
    if not appts:
        st.info("No appointments to export yet.")
        return

    col_pdf, col_csv = st.columns(2)
    with col_pdf:
        _pdf_cache_key = "da_pdf_bytes_cache"
        if st.button("📄 Generate PDF Report", key="da_pdf_btn",
                     type="primary", use_container_width=True):
            with st.spinner("Generating PDF…"):
                try:
                    from report_generator import generate_doctor_appointments_pdf
                    pdf_bytes = generate_doctor_appointments_pdf(
                        doctor_name, appts, timezone_name=timezone_name)
                    st.session_state[_pdf_cache_key] = pdf_bytes
                    st.success("✅ PDF ready!")
                except Exception as e:
                    st.session_state.pop(_pdf_cache_key, None)
                    st.error(f"PDF error: {e}")
        cached_pdf = st.session_state.get(_pdf_cache_key)
        if cached_pdf:
            st.download_button("⬇️ Download PDF", data=cached_pdf,
                               file_name="appointment_records.pdf",
                               mime="application/pdf", key="da_pdf_dl",
                               use_container_width=True)
    with col_csv:
        import pandas as pd, io
        buf = io.StringIO()
        pd.DataFrame(appts).to_csv(buf, index=False)
        st.download_button("📊 Download CSV", data=buf.getvalue(),
                           file_name="appointments.csv", mime="text/csv",
                           key="da_csv_dl", use_container_width=True)


# ── Main entry point ──────────────────────────────────────────────────────────
def appointments_tab_doctor(doctor_id: int, user: dict):
    """Full appointments tab — called from doctor_dashboard._appointments_tab_doctor()."""

    st.markdown(f"""
    <div style='background:linear-gradient(90deg,#0a1628,#0d2035);
                padding:1rem 1.4rem;border-radius:12px;margin-bottom:14px;
                border-left:4px solid {ACCENT};'>
        <div style='color:{ACCENT};font-weight:900;font-size:1.1rem;'>
            📅 Patient Appointments</div>
        <div style='color:#aaa;font-size:0.82rem;margin-top:3px;'>
            Accept, reject, complete or propose a new time for patient appointments
        </div>
    </div>
    """, unsafe_allow_html=True)

    appts = get_appointments_for_doctor(doctor_id)
    _summary_bar(appts)

    # Tab badge counts — group by logical workflow stage
    pending_list   = [a for a in appts if a.get("status") in NEEDS_ACCEPT]
    confirmed_list = [a for a in appts if a.get("status") in NEEDS_COMPLETE]
    proposed_list  = [a for a in appts if a.get("status") in NEEDS_WITHDRAW]
    completed_list = [a for a in appts if a.get("status") == APPT_STATUS_COMPLETED]
    cancelled_list = [a for a in appts if a.get("status") in
                      {APPT_STATUS_CANCELLED, APPT_STATUS_REJECTED}]

    pending_lbl  = f"⏳ Pending 🔴{len(pending_list)}"   if pending_list  else "⏳ Pending"
    proposed_lbl = f"📝 Proposed 🟣{len(proposed_list)}" if proposed_list else "📝 Proposed"
    confirm_lbl  = f"✅ Confirmed {len(confirmed_list)}"  if confirmed_list else "✅ Confirmed"

    # Open-ticket badge for the doctor's own tickets
    try:
        _my_tickets = get_tickets_by_user(doctor_id)
        _open_n     = sum(1 for t in _my_tickets if t.get("status") == "Open")
    except Exception:
        _open_n = 0
    ticket_lbl = f"🎫 Support Tickets 🔴{_open_n}" if _open_n > 0 else "🎫 Support Tickets"

    (t_pending, t_confirmed, t_proposed,
     t_all, t_completed, t_cancelled,
     t_tickets, t_download) = st.tabs([
        pending_lbl, confirm_lbl, proposed_lbl,
        "📋 All", "🏁 Completed", "❌ Cancelled",
        ticket_lbl, "⬇️ Export"])

    # ── Pending — Accept / Reject / Propose Time ──────────────────────────────
    with t_pending:
        if not pending_list:
            st.success("No pending appointments — all caught up! ✅")
        else:
            st.markdown(
                f"<div style='color:#f1c40f;font-size:0.85rem;font-weight:700;"
                f"margin-bottom:8px;'>⏳ {len(pending_list)} appointment(s) need action</div>",
                unsafe_allow_html=True)
            for a in pending_list:
                _appt_card(a, key_prefix="pend", doctor_id=doctor_id)

    # ── Confirmed — Complete / Cancel / Reschedule ────────────────────────────
    with t_confirmed:
        if not confirmed_list:
            st.info("No confirmed appointments right now.")
        else:
            st.markdown(
                f"<div style='color:#2ecc71;font-size:0.85rem;font-weight:700;"
                f"margin-bottom:8px;'>✅ {len(confirmed_list)} confirmed appointment(s)</div>",
                unsafe_allow_html=True)
            for a in confirmed_list:
                _appt_card(a, key_prefix="conf", doctor_id=doctor_id)

    # ── Doctor Proposed — withdraw only ───────────────────────────────────────
    with t_proposed:
        if not proposed_list:
            st.info("No pending reschedule proposals.")
        else:
            st.markdown(
                f"<div style='color:#aa88ff;font-size:0.85rem;font-weight:700;"
                f"margin-bottom:8px;'>📝 {len(proposed_list)} awaiting patient confirmation</div>",
                unsafe_allow_html=True)
            for a in proposed_list:
                _appt_card(a, key_prefix="prop", doctor_id=doctor_id)

    # ── All — read-only overview (no controls to avoid key collisions) ─────────
    with t_all:
        if not appts:
            st.info("No appointments yet.")
        else:
            # Search / filter
            q = st.text_input("🔍 Search by patient name or date…",
                              key="da_all_search", placeholder="e.g. Ashlyn or 2026-05")
            filtered = appts
            if q:
                ql = q.lower()
                filtered = [a for a in appts if
                            ql in (a.get("patient_name") or "").lower() or
                            ql in (a.get("appt_date") or "")]
            st.markdown(
                f"<div style='color:#aaa;font-size:0.8rem;margin-bottom:8px;'>"
                f"Showing {len(filtered)} of {len(appts)} appointments "
                f"(action buttons on Pending / Confirmed tabs)</div>",
                unsafe_allow_html=True)
            for a in filtered:
                # show_controls=False — avoids widget key collisions with action tabs
                _appt_card(a, key_prefix="view", doctor_id=doctor_id,
                           show_controls=False)

    # ── Completed ─────────────────────────────────────────────────────────────
    with t_completed:
        if not completed_list:
            st.info("No completed appointments yet.")
        else:
            for a in completed_list:
                _appt_card(a, key_prefix="done",
                           doctor_id=doctor_id, show_controls=False)

    # ── Cancelled ─────────────────────────────────────────────────────────────
    with t_cancelled:
        if not cancelled_list:
            st.info("No cancelled appointments.")
        else:
            for a in cancelled_list:
                _appt_card(a, key_prefix="cncl",
                           doctor_id=doctor_id, show_controls=False)

    # ── Support Tickets ───────────────────────────────────────────────────────
    with t_tickets:
        _ticket_tab_doctor(doctor_id, appts)

    # ── Export ────────────────────────────────────────────────────────────────
    with t_download:
        _download_tab(appts, user.get("full_name", "Doctor"))


# ══════════════════════════════════════════════════════════════════════════════
#  SUPPORT TICKETS (Doctor side)
# ══════════════════════════════════════════════════════════════════════════════
def _ticket_tab_doctor(doctor_id: int, appts: list):
    """Doctor-side support ticket UI — raise issues for admin review."""
    st.markdown(f"""
    <div style='background:#0a1628;border:1px solid {ACCENT}55;
                border-radius:10px;padding:12px 16px;margin-bottom:12px;'>
        <div style='color:{ACCENT};font-weight:800;font-size:1rem;'>🎫 Support Tickets</div>
        <div style='color:#aaa;font-size:0.82rem;margin-top:3px;'>
            File a ticket if you need admin help with a problem patient,
            scheduling conflicts, system issues, or anything else that needs
            administrative attention.</div>
    </div>""", unsafe_allow_html=True)

    # ── New ticket form ──────────────────────────────────────────────────────
    with st.expander("📝 File New Ticket", expanded=False):
        appt_labels = {"— None —": None}
        for a in appts:
            tag = (a.get('patient_name') or 'Patient')
            appt_labels[f"APT-{a['id']:05d} · {tag} ({a.get('status','')})"] = a["id"]

        sel_appt = st.selectbox(
            "Link to Appointment (optional)",
            list(appt_labels.keys()),
            key="doc_tkt_appt",
        )

        ticket_type = st.selectbox(
            "Ticket Type",
            ["General", "Scheduling Conflict", "Patient Concern",
             "System Issue", "Emergency", "Other"],
            key="doc_tkt_type",
        )
        subject = st.text_input(
            "Subject *", key="doc_tkt_subj",
            placeholder="Short summary of the issue…",
        )
        desc = st.text_area(
            "Description", key="doc_tkt_desc", height=120,
            placeholder="Describe the issue in detail so the admin can help…",
        )

        if st.button("📤 Submit Ticket", key="doc_tkt_submit", type="primary"):
            if not subject.strip():
                st.warning("Please enter a subject.")
            else:
                tid = create_ticket(
                    appt_labels[sel_appt],
                    doctor_id, "doctor",
                    subject.strip(),
                    desc.strip(),
                    ticket_type,
                )
                st.success(
                    f"✅ Ticket #{tid} submitted! Admin will review it shortly."
                )
                st.rerun()

    # ── Existing tickets ─────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("**📋 My Tickets**")
    tickets = get_tickets_by_user(doctor_id)
    if not tickets:
        st.info("You haven't filed any tickets yet.")
        return

    tz_name = sanitize_timezone(
        st.session_state.get('user', {}).get('timezone'))
    for t in tickets:
        tid = t["id"]
        ts = t.get("status", "Open")
        ts_color = {
            "Open":     "#f1c40f",
            "Reviewed": "#00d4ff",
            "Closed":   "#2ecc71",
        }.get(ts, "#aaa")
        appt_tag = (f" | APT-{t['appt_id']:05d}"
                    if t.get("appt_id") else "")
        desc_html = (
            f"<div style='color:#aaa;font-size:0.82rem;margin-top:4px;'>"
            f"{t.get('description','')}</div>"
            if t.get('description') else ""
        )
        note_html = (
            f"<div style='color:#00d4ff;font-size:0.82rem;margin-top:4px;'>"
            f"👤 Admin: {t.get('admin_note','')}</div>"
            if t.get('admin_note') else ""
        )
        st.markdown(
            f"""
            <div style='background:#0d1b2a;border-left:3px solid {ts_color};
                        border-radius:8px;padding:10px 14px;margin-bottom:8px;'>
                <div style='color:white;font-weight:700;'>
                    🎫 #{tid} — {t.get('subject','—')}
                    <span style='background:{ts_color};color:#000;border-radius:4px;
                    padding:1px 6px;font-size:0.72rem;margin-left:6px;'>{ts}</span>
                </div>
                <div style='color:#778;font-size:0.78rem;margin-top:2px;'>
                    Type: {t.get('ticket_type','—')} |
                    Filed: {format_db_timestamp(t.get('created_at',''), tz_name)}{appt_tag}
                </div>
                {desc_html}
                {note_html}
            </div>
            """,
            unsafe_allow_html=True,
        )