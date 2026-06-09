"""Shared updates center for patient and doctor portals."""

from __future__ import annotations

import streamlit as st

from database import (
    create_ticket,
    get_appointments_for_doctor,
    get_appointments_for_patient,
    get_notifications,
    get_tickets_by_user,
    get_user_by_id,
    mark_notifications_read,
)
from report_generator import generate_appointment_slip_pdf
from time_utils import format_appt_slot, format_db_timestamp, sanitize_timezone

STATUS_COLORS = {
    "Open": "#f1c40f",
    "Reviewed": "#00d4ff",
    "Closed": "#2ecc71",
}

UPDATE_TYPES = ["appointment_update", "appointment", "ticket"]


def _notif_icon(notif_type: str) -> str:
    if notif_type == "ticket":
        return "🎫"
    if notif_type == "appointment_update":
        return "🔔"
    if notif_type == "appointment":
        return "📅"
    return "ℹ️"


def _appointment_options(appointments: list[dict]) -> dict:
    labels = {"— None —": None}
    for appt in appointments:
        labels[
            f"APT-{appt['id']:05d} | {appt.get('status', '—')} | {appt.get('appt_date', '—')} {appt.get('appt_time', '—')}"
        ] = appt["id"]
    return labels


def _render_ticket_form(user: dict, role: str, appointments: list[dict], accent: str):
    st.markdown(
        f"<div style='background:#0d1b2a;border:1px solid {accent}33;border-radius:12px;padding:14px 16px;margin-bottom:12px;'>"
        f"<div style='color:{accent};font-weight:800;'>🎫 Raise Ticket to Admin</div>"
        f"<div style='color:#9aa4b2;font-size:0.82rem;margin-top:4px;'>"
        f"Use this for reschedule issues, reassignment concerns, billing questions, workflow glitches, or general admin help.</div></div>",
        unsafe_allow_html=True,
    )

    appointment_options = _appointment_options(appointments)
    with st.form(f"{role}_ticket_form", clear_on_submit=True):
        linked = st.selectbox("Linked appointment", list(appointment_options.keys()))
        ticket_type = st.selectbox(
            "Ticket type",
            [
                "General",
                "Reschedule Issue",
                "Reassignment",
                "Billing",
                "Workflow Glitch",
                "Complaint",
                "Other",
            ],
        )
        subject = st.text_input("Subject")
        description = st.text_area("Description", height=120)
        submitted = st.form_submit_button("📤 Submit ticket", type="primary", use_container_width=True)
        if submitted:
            if not subject.strip():
                st.warning("Please enter a subject before submitting the ticket.")
            else:
                ticket_id = create_ticket(
                    appointment_options[linked],
                    user["id"],
                    role,
                    subject.strip(),
                    description.strip(),
                    ticket_type,
                )
                st.success(f"✅ Ticket #{ticket_id} submitted to admin.")
                st.rerun()


def _render_my_tickets(user_id: int, timezone_name: str):
    tickets = get_tickets_by_user(user_id)
    st.markdown("### 🎫 My Tickets")
    if not tickets:
        st.info("No tickets filed yet.")
        return

    for ticket in tickets:
        status = ticket.get("status", "Open")
        accent = STATUS_COLORS.get(status, "#94a3b8")
        linked_appt = f"APT-{ticket['appt_id']:05d}" if ticket.get("appt_id") else "No linked appointment"
        desc_html = (
            f"<div style='color:#d6dbe2;font-size:0.88rem;margin-top:6px;'>{ticket.get('description')}</div>"
            if ticket.get("description")
            else ""
        )
        admin_html = (
            f"<div style='color:#7dd3fc;font-size:0.84rem;margin-top:6px;'>Admin note: {ticket.get('admin_note')}</div>"
            if ticket.get("admin_note")
            else ""
        )
        st.markdown(
            f"<div style='background:#0d1b2a;border-left:4px solid {accent};border-radius:10px;padding:12px 16px;margin-bottom:10px;'>"
            f"<div style='color:white;font-weight:800;'>🎫 #{ticket['id']} — {ticket.get('subject','—')}"
            f"<span style='background:{accent};color:#000;border-radius:999px;padding:2px 8px;font-size:0.72rem;margin-left:8px;'>{status}</span></div>"
            f"<div style='color:#9aa4b2;font-size:0.82rem;margin-top:4px;'>"
            f"{ticket.get('ticket_type','General')}"
            f" &nbsp;|&nbsp; Filed {format_db_timestamp(ticket.get('created_at'), timezone_name)}"
            f" &nbsp;|&nbsp; {linked_appt}</div>"
            f"{desc_html}{admin_html}</div>",
            unsafe_allow_html=True,
        )


def _render_notifications(user_id: int, timezone_name: str):
    notifications = get_notifications(user_id, limit=40, notif_types=UPDATE_TYPES)
    c1, c2 = st.columns([1, 1])
    with c1:
        st.markdown("### 🔔 Recent Updates")
    with c2:
        if notifications and st.button(
            "Mark all updates as read",
            key=f"mark_updates_{user_id}",
            use_container_width=True,
        ):
            mark_notifications_read(user_id, notif_types=UPDATE_TYPES)
            st.success("Updates marked as read.")
            st.rerun()

    if not notifications:
        st.info("No appointment or ticket updates yet.")
        return

    for notif in notifications:
        icon = _notif_icon(notif.get("notif_type", "info"))
        border = "#334155" if notif.get("is_read") else "#38bdf8"
        st.markdown(
            f"<div style='background:#0d1b2a;border:1px solid {border};border-radius:12px;padding:12px 16px;margin-bottom:10px;'>"
            f"<div style='display:flex;justify-content:space-between;gap:12px;align-items:flex-start;'>"
            f"<div><div style='color:white;font-weight:800;'>{icon} {notif.get('title','Update')}</div>"
            f"<div style='color:#d6dbe2;font-size:0.9rem;margin-top:4px;'>{notif.get('message','')}</div></div>"
            f"<div style='color:#94a3b8;font-size:0.75rem;white-space:nowrap;'>{format_db_timestamp(notif.get('created_at'), timezone_name)}</div>"
            f"</div></div>",
            unsafe_allow_html=True,
        )


def _render_patient_latest_slips(user: dict, timezone_name: str):
    appointments = get_appointments_for_patient(user["id"])
    active = [
        a for a in appointments
        if a.get("status") == "Confirmed"
    ]
    st.markdown("### 📄 Latest Appointment Slips")
    if not active:
        st.info("No active appointments available for slip download.")
        return

    for appt in active[:10]:
        doctor = get_user_by_id(appt.get("doctor_id")) if appt.get("doctor_id") else None
        label = format_appt_slot(appt.get("appt_date"), appt.get("appt_time"), timezone_name)
        st.markdown(
            f"<div style='background:#0d1b2a;border-left:4px solid #00ff88;border-radius:10px;padding:10px 14px;margin-bottom:8px;'>"
            f"<div style='color:white;font-weight:800;'>APT-{appt['id']:05d} — Dr. {appt.get('doctor_name','—')}</div>"
            f"<div style='color:#9aa4b2;font-size:0.84rem;margin-top:4px;'>Status: {appt.get('status','—')} &nbsp;|&nbsp; Schedule: {label}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        if doctor:
            slip_pdf = generate_appointment_slip_pdf(appt, user, doctor, timezone_name=timezone_name)
            st.download_button(
                "⬇️ Download latest slip",
                data=slip_pdf,
                file_name=f"appointment_slip_APT{appt['id']:05d}.pdf",
                mime="application/pdf",
                key=f"latest_slip_{appt['id']}",
                use_container_width=True,
            )


def render_updates_page(user: dict, role: str, accent: str):
    timezone_name = sanitize_timezone(user.get("timezone"))
    st.markdown(
        f"<div style='background:linear-gradient(90deg,#0d1b2a,#111827);border-left:5px solid {accent};border-radius:14px;padding:18px 20px;margin-bottom:14px;'>"
        f"<div style='font-size:1.45rem;font-weight:900;color:{accent};'>🔔 Updates Center</div>"
        f"<div style='color:#9aa4b2;font-size:0.9rem;margin-top:6px;'>Appointment changes, reassignment notices, fresh slips, and admin ticket responses are grouped here.</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    appointments = (
        get_appointments_for_patient(user["id"])
        if role == "patient"
        else get_appointments_for_doctor(user["id"])
    )
    _render_notifications(user["id"], timezone_name)
    st.markdown("---")
    _render_ticket_form(user, role, appointments, accent)
    _render_my_tickets(user["id"], timezone_name)
    if role == "patient":
        st.markdown("---")
        _render_patient_latest_slips(user, timezone_name)
