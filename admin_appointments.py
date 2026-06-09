"""
admin_appointments.py  –  Admin Appointment & Ticketing System v5
Emergency reassignment, multi-doctor management, ticketing, audit logs
"""

import streamlit as st
import pandas as pd
from time_utils import format_db_timestamp

from database import (
    get_all_appointments, get_appointment_by_id,
    emergency_reassign_appointment, cancel_appointment,
    get_all_audit_logs, get_appointment_audit_log,
    get_all_tickets, update_ticket, get_open_ticket_count,
    get_all_doctors, get_all_patients,
    add_doctor_to_patient, remove_doctor_from_patient,
    get_doctors_for_patient, set_primary_doctor,
    add_notification,
    get_patient_booking_status, lift_patient_restriction,
    MONTHLY_BOOKING_LIMIT, CONSEC_CANCEL_LIMIT, CANCEL_RESTRICT_DAYS,
    APPT_STATUS_PENDING, APPT_STATUS_CONFIRMED, APPT_STATUS_REJECTED,
    APPT_STATUS_DOCTOR_PROPOSED, APPT_STATUS_COMPLETED,
    APPT_STATUS_CANCELLED, APPT_STATUS_RESCHEDULED,
    TICKET_STATUS_OPEN, TICKET_STATUS_REVIEWED, TICKET_STATUS_CLOSED,
)

ACCENT = "#ff4b4b"

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


def admin_appointments_tab(admin_user):
    """Admin appointment management — tabs for all features."""

    open_tickets = get_open_ticket_count()
    ticket_lbl   = f"🎫 Tickets {'🔴' if open_tickets > 0 else ''}"

    # Count currently restricted patients for badge
    try:
        all_pats      = get_all_patients()
        restricted_n  = sum(
            1 for p in all_pats
            if get_patient_booking_status(p["id"]).get("restricted_until")
        )
    except Exception:
        restricted_n = 0
    restrict_lbl = f"🚫 Booking Limits {'🔴' + str(restricted_n) if restricted_n > 0 else ''}"

    t_all, t_emergency, t_tickets, t_multidoc, t_restrict, t_audit = st.tabs([
        "📋 All Appointments", "🚨 Emergency Reassign",
        ticket_lbl, "👥 Multi-Doctor Assign", restrict_lbl, "📜 Audit Logs"])

    with t_all:
        _all_appointments_admin(admin_user)

    with t_emergency:
        _emergency_reassign(admin_user)

    with t_tickets:
        _tickets_admin(admin_user)

    with t_multidoc:
        _multi_doctor_admin()

    with t_restrict:
        _booking_limits_admin(admin_user)

    with t_audit:
        _audit_logs_admin()


# ══════════════════════════════════════════════════════════════════════════════
#  ALL APPOINTMENTS
# ══════════════════════════════════════════════════════════════════════════════

def _all_appointments_admin(admin_user):
    st.subheader("📋 All System Appointments")

    appts = get_all_appointments()
    if not appts:
        st.info("No appointments in the system.")
        return

    # Summary metrics
    total = len(appts)
    by_status = {}
    for a in appts:
        s = a.get("status", "?")
        by_status[s] = by_status.get(s, 0) + 1

    cols = st.columns(4)
    cols[0].metric("📊 Total", total)
    cols[1].metric("⏳ Pending", by_status.get(APPT_STATUS_PENDING, 0))
    cols[2].metric("✅ Confirmed", by_status.get(APPT_STATUS_CONFIRMED, 0))
    cols[3].metric("✔️ Completed", by_status.get(APPT_STATUS_COMPLETED, 0))

    # Filter
    status_filter = st.selectbox("Filter by status",
        ["All", APPT_STATUS_PENDING, APPT_STATUS_CONFIRMED,
         APPT_STATUS_DOCTOR_PROPOSED, APPT_STATUS_COMPLETED,
         APPT_STATUS_REJECTED, APPT_STATUS_CANCELLED, APPT_STATUS_RESCHEDULED],
        key="adm_appt_filter")

    filtered = appts if status_filter == "All" else [
        a for a in appts if a.get("status") == status_filter]

    srch = st.text_input("🔍 Search…", key="adm_appt_search",
                          placeholder="Patient name, doctor name, APT ID…")
    if srch:
        q = srch.lower()
        filtered = [a for a in filtered if
            q in (a.get("patient_name","") or "").lower() or
            q in (a.get("doctor_name","") or "").lower() or
            q in f"apt-{a.get('id',0):05d}" or
            q in str(a.get("id",""))]

    if not filtered:
        st.info("No appointments match your criteria.")
        return

    # Table view
    df_appts = pd.DataFrame([{
        "ID":       f"APT-{a['id']:05d}",
        "Patient":  a.get("patient_name","—"),
        "Doctor":   a.get("doctor_name","—"),
        "Date":     a.get("appt_date","—"),
        "Time":     a.get("appt_time","—"),
        "Type":     a.get("appointment_type","—"),
        "Status":   a.get("status","—"),
        "Emergency": "🚨" if a.get("is_emergency") else "",
        "Reason":   (a.get("reason","") or "")[:50],
    } for a in filtered])
    st.dataframe(df_appts, use_container_width=True, height=400)

    # Detail expanders
    for a in filtered[:20]:  # Limit to 20 for performance
        aid = a["id"]
        status = a.get("status", "")
        with st.expander(
            f"APT-{aid:05d} | {a.get('patient_name','?')} → "
            f"Dr. {a.get('doctor_name','?')} | {status}"):

            c1, c2 = st.columns(2)
            with c1:
                st.write(f"📅 Date: **{a.get('appt_date','')}**")
                st.write(f"🕐 Time: **{a.get('appt_time','')}**")
                st.write(f"🏥 Type: {a.get('appointment_type','')}")
                st.write(f"📝 Reason: {a.get('reason','—') or '—'}")
            with c2:
                st.write(f"💳 Payment: {a.get('payment_mode','—')} ({a.get('payment_status','')})")
                st.write(f"📧 Patient: {a.get('patient_email','—')}")
                st.write(f"📧 Doctor: {a.get('doctor_email','—')}")
                if a.get("doctor_note"):
                    st.write(f"🩺 Doctor Note: {a['doctor_note']}")

            # Admin actions
            if status not in [APPT_STATUS_CANCELLED, APPT_STATUS_COMPLETED]:
                if st.button("❌ Force Cancel", key=f"adm_force_cancel_{aid}"):
                    ok, msg = cancel_appointment(aid, admin_user["id"], "admin",
                                                  "Cancelled by admin")
                    if ok: st.success("Cancelled."); st.rerun()
                    else: st.error(msg)

            # Show audit log
            if st.button("📜 View Audit Log", key=f"adm_audit_{aid}"):
                st.session_state[f"adm_audit_show_{aid}"] = \
                    not st.session_state.get(f"adm_audit_show_{aid}", False)
            if st.session_state.get(f"adm_audit_show_{aid}"):
                logs = get_appointment_audit_log(aid)
                if logs:
                    for log in logs:
                        role_icon = {"patient":"👤","doctor":"🩺","admin":"🔴"}.get(
                            log.get("actor_role",""), "❓")
                        st.markdown(
                            f"{role_icon} **{log.get('actor_name','—')}** — "
                            f"`{log.get('action','')}` "
                            f"({log.get('old_status','?')} → {log.get('new_status','?')}) "
                            f"*{log.get('details','')[:60]}* "
                            f"<span style='color:#556;font-size:0.75rem;'>"
                            f"{format_db_timestamp(log.get('created_at',''))}</span>",
                            unsafe_allow_html=True)
                else:
                    st.info("No audit entries.")


# ══════════════════════════════════════════════════════════════════════════════
#  EMERGENCY REASSIGNMENT
# ══════════════════════════════════════════════════════════════════════════════

def _emergency_reassign(admin_user):
    st.subheader("🚨 Emergency Doctor Reassignment")
    st.markdown(
        f"<div style='background:#1a0505;border:1px solid {ACCENT}44;"
        f"border-radius:10px;padding:12px 16px;margin-bottom:12px;'>"
        f"<b style='color:{ACCENT};'>⚠️ Emergency Reassignment</b>"
        f"<div style='color:#aaa;font-size:0.82rem;margin-top:3px;'>"
        f"Use this to reassign an active appointment to a different doctor "
        f"when the original doctor is unavailable (sick leave, emergency, etc.)."
        f"</div></div>",
        unsafe_allow_html=True)

    appts = get_all_appointments()
    active = [a for a in appts if a.get("status") in [
        APPT_STATUS_PENDING, APPT_STATUS_CONFIRMED, APPT_STATUS_DOCTOR_PROPOSED]]

    if not active:
        st.info("No active appointments available for reassignment.")
        return

    # Select appointment
    appt_labels = {
        f"APT-{a['id']:05d} | {a.get('patient_name','')} → Dr. {a.get('doctor_name','')} "
        f"| {a.get('appt_date','')} {a.get('appt_time','')} [{a.get('status','')}]": a
        for a in active
    }
    sel_label = st.selectbox("Select Appointment to Reassign",
                              list(appt_labels.keys()),
                              key="adm_emg_appt_sel")
    sel_appt = appt_labels[sel_label]

    # Show appointment details
    st.markdown(f"""
    <div style='background:#0d1b2a;border-radius:8px;padding:12px;margin:8px 0;'>
        <div style='color:white;font-weight:700;'>Current Assignment</div>
        <div style='color:#aaa;margin-top:4px;'>
            👤 Patient: <b style='color:white;'>{sel_appt.get('patient_name','')}</b><br>
            🩺 Doctor: <b style='color:#ff6688;'>{sel_appt.get('doctor_name','')}</b><br>
            📅 {sel_appt.get('appt_date','')} at {sel_appt.get('appt_time','')}<br>
            Status: {sel_appt.get('status','')}
        </div>
    </div>""", unsafe_allow_html=True)

    # Select new doctor
    doctors = get_all_doctors()
    other_docs = [d for d in doctors if d["id"] != sel_appt.get("doctor_id")]
    if not other_docs:
        st.warning("No other doctors available for reassignment.")
        return

    doc_opts = {f"🩺 Dr. {d['full_name']} (ID: {d['id']})": d["id"]
                for d in other_docs}
    sel_doc_label = st.selectbox("Assign to New Doctor",
                                  list(doc_opts.keys()),
                                  key="adm_emg_doc_sel")
    new_doc_id = doc_opts[sel_doc_label]

    reason = st.text_area("Reason for Reassignment *",
                            key="adm_emg_reason",
                            placeholder="e.g., Original doctor on emergency leave…")

    if st.button("🚨 Execute Emergency Reassignment",
                  key="adm_emg_submit", type="primary",
                  use_container_width=True):
        if not reason.strip():
            st.error("Please provide a reason for the reassignment.")
        else:
            ok, msg = emergency_reassign_appointment(
                sel_appt["id"], new_doc_id,
                admin_user["id"], reason.strip())
            if ok:
                st.balloons()
                st.success(f"✅ {msg}")
                st.rerun()
            else:
                st.error(f"❌ {msg}")


# ══════════════════════════════════════════════════════════════════════════════
#  TICKETS MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

def _tickets_admin(admin_user):
    st.subheader("🎫 Support Tickets")

    status_filter = st.selectbox("Filter",
        ["All", TICKET_STATUS_OPEN, TICKET_STATUS_REVIEWED, TICKET_STATUS_CLOSED],
        key="adm_tkt_filter")

    if status_filter == "All":
        tickets = get_all_tickets()
    else:
        tickets = get_all_tickets(status_filter=status_filter)

    if not tickets:
        st.info("No tickets found.")
        return

    open_cnt = sum(1 for t in tickets if t.get("status") == TICKET_STATUS_OPEN)
    st.markdown(
        f"<div style='color:#aaa;margin-bottom:8px;'>"
        f"Showing {len(tickets)} ticket(s) | "
        f"<b style='color:#f1c40f;'>{open_cnt} open</b></div>",
        unsafe_allow_html=True)

    for t in tickets:
        tid = t["id"]
        ts  = t.get("status", "Open")
        ts_colors = {
            TICKET_STATUS_OPEN:     ("#f1c40f", "#1a1500"),
            TICKET_STATUS_REVIEWED: ("#00d4ff", "#0a1628"),
            TICKET_STATUS_CLOSED:   ("#2ecc71", "#0a1a0a"),
        }
        ac, bg = ts_colors.get(ts, ("#aaa", "#111"))

        st.markdown(f"""
        <div style='background:{bg};border:1px solid {ac}44;
                    border-left:4px solid {ac};border-radius:10px;
                    padding:12px 16px;margin-bottom:8px;'>
            <div style='color:white;font-weight:800;'>
                🎫 #{tid} — {t.get('subject','—')}
                <span style='background:{ac};color:#000;border-radius:4px;
                padding:1px 6px;font-size:0.72rem;margin-left:6px;'>{ts}</span>
            </div>
            <div style='color:#aaa;font-size:0.82rem;margin-top:4px;'>
                Filed by: <b style='color:white;'>{t.get('filed_by_name','—')}</b>
                ({t.get('filed_role','')}) &nbsp;|&nbsp;
                Type: {t.get('ticket_type','—')} &nbsp;|&nbsp;
                {f"APT-{t['appt_id']:05d}" if t.get('appt_id') else "No linked appointment"}
            </div>
            <div style='color:#ccc;font-size:0.85rem;margin-top:6px;'>
                {t.get('description','') or '(no description)'}
            </div>
            {f"<div style='color:#00d4ff;font-size:0.82rem;margin-top:6px;'>"
             f"📝 Admin Note: {t.get('admin_note','')}</div>"
             if t.get('admin_note') else ""}
        </div>""", unsafe_allow_html=True)

        if ts != TICKET_STATUS_CLOSED:
            with st.expander(f"Manage Ticket #{tid}"):
                admin_note = st.text_area("Admin Note / Response",
                    key=f"adm_tkt_note_{tid}",
                    value=t.get("admin_note", "") or "",
                    placeholder="Add your response or resolution note…")
                tc1, tc2, tc3 = st.columns(3)
                with tc1:
                    if st.button("📝 Mark Reviewed",
                                  key=f"adm_tkt_review_{tid}"):
                        update_ticket(tid, TICKET_STATUS_REVIEWED, admin_note)
                        st.success("Marked as reviewed.")
                        st.rerun()
                with tc2:
                    if st.button("✅ Close Ticket",
                                  key=f"adm_tkt_close_{tid}", type="primary"):
                        update_ticket(tid, TICKET_STATUS_CLOSED, admin_note)
                        st.success("Ticket closed.")
                        # Notify filer
                        add_notification(t["filed_by"],
                            f"🎫 Ticket #{tid} Resolved",
                            f"Your ticket '{t.get('subject','')}' has been resolved. "
                            f"Admin note: {admin_note}",
                            "ticket")
                        st.rerun()
                with tc3:
                    if st.button("🔄 Reopen", key=f"adm_tkt_reopen_{tid}"):
                        update_ticket(tid, TICKET_STATUS_OPEN, admin_note)
                        st.warning("Ticket reopened.")
                        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
#  MULTI-DOCTOR ASSIGNMENT
# ══════════════════════════════════════════════════════════════════════════════

def _multi_doctor_admin():
    st.subheader("👥 Multi-Doctor Patient Assignment")
    st.markdown(
        "<div style='background:#0a1e30;border:1px solid #ff4b4b44;"
        "border-radius:10px;padding:12px 16px;margin-bottom:12px;'>"
        "<b style='color:#ff4b4b;'>🩺 Multiple Doctors per Patient</b>"
        "<div style='color:#aaa;font-size:0.82rem;margin-top:3px;'>"
        "Patients can be assigned to multiple doctors (e.g., specialist + GP). "
        "Set one as primary. Patients can book with any assigned doctor.</div></div>",
        unsafe_allow_html=True)

    patients = get_all_patients()
    doctors  = get_all_doctors()

    if not patients:
        st.info("No patients registered.")
        return
    if not doctors:
        st.info("No doctors registered.")
        return

    # Select patient
    pat_opts = {f"👤 {p['full_name']} (@{p['username']})": p for p in patients}
    sel_pat_label = st.selectbox("Select Patient", list(pat_opts.keys()),
                                  key="adm_md_pat")
    sel_patient = pat_opts[sel_pat_label]
    pid = sel_patient["id"]

    # Show currently assigned doctors
    current_docs = get_doctors_for_patient(pid)
    st.markdown("**Currently Assigned Doctors:**")
    if current_docs:
        for d in current_docs:
            primary = " ⭐ PRIMARY" if d.get("is_primary") else ""
            st.markdown(
                f"<div style='display:flex;align-items:center;gap:10px;"
                f"padding:6px 12px;background:#0d1b2a;border-radius:6px;"
                f"margin-bottom:4px;border-left:3px solid #00d4ff;'>"
                f"<span style='color:white;font-weight:700;'>"
                f"🩺 Dr. {d['full_name']}</span>"
                f"<span style='color:#f1c40f;font-size:0.8rem;'>{primary}</span>"
                f"</div>", unsafe_allow_html=True)

        # Remove / set primary
        doc_labels_current = {f"Dr. {d['full_name']}": d["id"] for d in current_docs}
        rc1, rc2 = st.columns(2)
        with rc1:
            sel_remove = st.selectbox("Remove Doctor",
                list(doc_labels_current.keys()), key="adm_md_remove_sel")
            if st.button("🗑️ Remove", key="adm_md_remove_btn"):
                remove_doctor_from_patient(pid, doc_labels_current[sel_remove])
                st.success(f"Removed {sel_remove}.")
                st.rerun()
        with rc2:
            sel_primary = st.selectbox("Set Primary",
                list(doc_labels_current.keys()), key="adm_md_primary_sel")
            if st.button("⭐ Set Primary", key="adm_md_primary_btn"):
                set_primary_doctor(pid, doc_labels_current[sel_primary])
                st.success(f"{sel_primary} is now primary.")
                st.rerun()
    else:
        st.info("No doctors assigned yet.")

    # Add new doctor
    st.markdown("---")
    st.markdown("**➕ Add Doctor to Patient**")
    assigned_ids = {d["id"] for d in current_docs}
    unassigned = [d for d in doctors if d["id"] not in assigned_ids]
    if unassigned:
        add_opts = {f"🩺 Dr. {d['full_name']}": d["id"] for d in unassigned}
        sel_add = st.selectbox("Doctor to Add", list(add_opts.keys()),
                                key="adm_md_add_sel")
        make_primary = st.checkbox("Make Primary", key="adm_md_add_primary")
        if st.button("➕ Add Doctor", key="adm_md_add_btn", type="primary"):
            add_doctor_to_patient(pid, add_opts[sel_add],
                                   is_primary=int(make_primary))
            if make_primary:
                set_primary_doctor(pid, add_opts[sel_add])
            st.success(f"Doctor added to {sel_patient['full_name']}!")
            st.rerun()
    else:
        st.success("All available doctors are already assigned.")


# ══════════════════════════════════════════════════════════════════════════════
#  AUDIT LOGS
# ══════════════════════════════════════════════════════════════════════════════

def _audit_logs_admin():
    st.subheader("📜 Appointment Audit Logs")
    st.markdown(
        "<div style='background:#0a1e30;border:1px solid #ff4b4b44;"
        "border-radius:10px;padding:10px 16px;margin-bottom:12px;'>"
        "<b style='color:#ff4b4b;'>📋 Full Audit Trail</b>"
        "<span style='color:#aaa;font-size:0.85rem;'> — Every appointment action "
        "is logged for compliance and review.</span></div>",
        unsafe_allow_html=True)

    logs = get_all_audit_logs(limit=200)
    if not logs:
        st.info("No audit log entries yet.")
        return

    # Filter
    action_filter = st.text_input("🔍 Filter by action/name…",
                                    key="adm_audit_filter",
                                    placeholder="CREATED, ACCEPTED, REJECTED, etc.")
    if action_filter:
        q = action_filter.lower()
        logs = [l for l in logs if
            q in (l.get("action","") or "").lower() or
            q in (l.get("actor_name","") or "").lower() or
            q in (l.get("details","") or "").lower()]

    st.markdown(f"<div style='color:#aaa;font-size:0.82rem;margin-bottom:8px;'>"
                f"Showing {len(logs)} entries</div>", unsafe_allow_html=True)

    df_logs = pd.DataFrame([{
        "Time":    format_db_timestamp(l.get("created_at","")),
        "APT ID":  f"APT-{l.get('appt_id',0):05d}",
        "Actor":   l.get("actor_name","—"),
        "Role":    l.get("actor_role","—"),
        "Action":  l.get("action","—"),
        "From":    l.get("old_status","—") or "—",
        "To":      l.get("new_status","—") or "—",
        "Details": (l.get("details","") or "")[:60],
    } for l in logs])
    st.dataframe(df_logs, use_container_width=True, height=500)

# ══════════════════════════════════════════════════════════════════════════════
#  BOOKING LIMITS — Admin view and override
# ══════════════════════════════════════════════════════════════════════════════
def _booking_limits_admin(admin_user):
    """Admin panel: view all patient booking quotas and lift restrictions."""
    from datetime import datetime

    st.markdown(
        "<div style='background:linear-gradient(90deg,#1a0505,#200a0a);"
        "border-radius:12px;padding:14px 18px;margin-bottom:16px;"
        "border-left:5px solid #ff4b4b;'>"
        "<div style='font-size:1.1rem;font-weight:900;color:#ff4b4b;'>"
        "🚫 Patient Booking Limits & Restrictions</div>"
        "<div style='color:#aaa;font-size:0.82rem;margin-top:3px;'>"
        f"Monthly limit: <b>{MONTHLY_BOOKING_LIMIT}</b> requests &nbsp;|&nbsp; "
        f"Consecutive cancel limit: <b>{CONSEC_CANCEL_LIMIT}</b> "
        f"→ blocked for <b>{CANCEL_RESTRICT_DAYS} days</b></div>"
        "</div>", unsafe_allow_html=True)

    patients = get_all_patients()
    if not patients:
        st.info("No patients registered yet.")
        return

    now = datetime.utcnow()

    # Build table rows
    rows = []
    for p in patients:
        s = get_patient_booking_status(p["id"])
        ru = s.get("restricted_until")
        if ru:
            try:
                ru_dt = datetime.strptime(str(ru)[:19], "%Y-%m-%d %H:%M:%S")
                is_restricted = now < ru_dt
                ru_str = str(ru)[:16]
            except Exception:
                is_restricted = False
                ru_str = "—"
        else:
            is_restricted = False
            ru_str = "—"
        rows.append({
            "pid":          p["id"],
            "name":         p.get("full_name", "—"),
            "used":         s["used"],
            "remaining":    s["remaining"],
            "consec":       s.get("consec_cancels", 0),
            "restricted":   is_restricted,
            "ru_str":       ru_str,
            "last_cancel":  str(s.get("last_cancel_at") or "—")[:16],
        })

    # Sort: restricted first
    rows.sort(key=lambda r: (not r["restricted"], -r["consec"]))

    # Show filter
    show_all = st.checkbox("Show all patients (default: restricted + warning only)",
                           key="adm_bl_show_all", value=False)
    if not show_all:
        rows = [r for r in rows if r["restricted"] or r["consec"] >= 1
                or r["used"] >= MONTHLY_BOOKING_LIMIT - 2]

    if not rows:
        st.markdown(
            "<div style='background:#0d1b2a;border-radius:10px;padding:20px;"
            "text-align:center;'>"
            "<div style='font-size:2rem;'>✅</div>"
            "<div style='color:#00ff88;font-weight:700;margin-top:8px;'>"
            "No patients are restricted or near their limit.</div></div>",
            unsafe_allow_html=True)
        return

    for r in rows:
        is_restricted = r["restricted"]
        border  = "#ff4b4b" if is_restricted else ("#f1c40f" if r["consec"] >= 2 else "#2a3a4a")
        bg      = "#2a0505" if is_restricted else ("#1a1000" if r["consec"] >= 2 else "#0d1b2a")
        status_badge = (
            "<span style='background:#ff4b4b;color:white;border-radius:6px;"
            "padding:1px 8px;font-size:0.75rem;font-weight:800;'>RESTRICTED</span>"
            if is_restricted else
            f"<span style='background:#f1c40f;color:#000;border-radius:6px;"
            f"padding:1px 8px;font-size:0.75rem;font-weight:800;'>"
            f"⚠️ {r['consec']} cancel(s)</span>"
            if r["consec"] >= 1 else ""
        )

        st.markdown(
            f"<div style='background:{bg};border:1px solid {border}44;"
            f"border-left:4px solid {border};border-radius:10px;"
            f"padding:12px 16px;margin-bottom:8px;'>"
            f"<div style='display:flex;justify-content:space-between;"
            f"align-items:center;flex-wrap:wrap;gap:8px;'>"
            f"<div><div style='color:white;font-weight:800;'>"
            f"👤 {r['name']} &nbsp; {status_badge}</div>"
            f"<div style='color:#aaa;font-size:0.8rem;margin-top:4px;'>"
            f"📅 Used: {r['used']}/{MONTHLY_BOOKING_LIMIT} &nbsp;|&nbsp; "
            f"Remaining: {r['remaining']} &nbsp;|&nbsp; "
            f"Consec. cancels: {r['consec']}/{CONSEC_CANCEL_LIMIT}"
            f"</div>"
            f"{'<div style=\"color:#ff6666;font-size:0.8rem;margin-top:2px;\">🔒 Restricted until: ' + r['ru_str'] + '</div>' if is_restricted else ''}"
            f"<div style='color:#556;font-size:0.75rem;margin-top:2px;'>"
            f"Last cancel: {r['last_cancel']}</div>"
            f"</div></div></div>",
            unsafe_allow_html=True)

        if is_restricted:
            if st.button(f"✅ Lift Restriction — {r['name']}",
                         key=f"adm_lift_{r['pid']}", type="primary"):
                ok, msg = lift_patient_restriction(r["pid"], admin_user["id"])
                if ok:
                    st.success(f"✅ {msg}")
                    st.rerun()
                else:
                    st.error(msg)
        st.markdown("")