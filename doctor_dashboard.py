
import io
from datetime import datetime, date
import streamlit as st
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from database import (
    get_patients_by_doctor, get_predictions_by_patient,
    add_doctor_note, get_notes_for_patient,
    get_doctor_self_notes, add_doctor_self_note, delete_doctor_self_note,
    get_patient_notes,
    NOTE_COLOR_MAP, NOTE_ACCENT_MAP,
    send_message, get_chat_messages, mark_messages_read, get_unread_count,
    update_profile_photo, delete_profile_photo, update_bio, get_user_by_id,
    unsend_message, edit_message,
    add_checklist_item, get_checklist, toggle_checklist_item,
    delete_checklist_item, CHECKLIST_CATEGORIES,
    update_user_profile, change_password, encode_photo, authenticate_user,
    get_stress_alerts_for_doctor, get_unread_alert_count, mark_alerts_read,
    upsert_doctor_portfolio, get_doctor_portfolio,
    get_checklist_pending_count,
    get_appointments_for_doctor, update_appointment_status,
    get_all_medical_reports_for_doctor, get_medical_report_data,
    update_medical_report_analysis,
    get_doctor_portfolio_pdf, calculate_age_from_dob,
    get_appointment_notifications, mark_appointment_notifications_read,
    add_notification,
)
from utils import avatar_html, to_ist_str, to_ist_full
from report_generator import generate_patient_report_pdf, generate_doctor_appointments_pdf

ACCENT     = "#00d4ff"
COLOR_NAMES = list(NOTE_COLOR_MAP.keys())


# ══════════════════════════════════════════════════════════════════════════════
#  CHAT
# ══════════════════════════════════════════════════════════════════════════════
def _chat_ui(my_id: int, other_user: dict, prefix: str):
    other_id    = other_user["id"]
    other_name  = other_user["full_name"]
    other_photo = other_user.get("profile_photo")

    # ── Clear-flag pattern (MUST run before any widget is drawn) ─────────────
    send_key   = f"{prefix}_inp"
    clear_flag = f"{prefix}_clear"
    if st.session_state.pop(clear_flag, False):
        st.session_state.pop(send_key, None)

    mark_messages_read(other_id, my_id)
    unread   = get_unread_count(my_id, other_id)
    messages = get_chat_messages(my_id, other_id)

    # Header
    st.markdown(f"""
    <div style='display:flex;align-items:center;gap:12px;background:#0a1e30;
                border-radius:12px;padding:12px 16px;margin-bottom:8px;
                border-bottom:1px solid #1e3a5a;'>
        {avatar_html(other_photo, other_name, 42, ACCENT)}
        <div style='flex:1;'>
            <div style='color:white;font-weight:800;'>{other_name}</div>
            <div style='color:#00ff88;font-size:0.75rem;'>● Patient</div>
        </div>
        {"<span style='background:#ff4b4b;color:white;border-radius:20px;"
         "padding:2px 10px;font-size:0.75rem;font-weight:800;'>"
         f"{unread} new</span>" if unread > 0 else ""}
    </div>
    """, unsafe_allow_html=True)

    # Message bubbles
    html = (f"<div style='height:300px;overflow-y:auto;padding:8px 4px;"
            f"display:flex;flex-direction:column;gap:5px;' id='cb_{prefix}'>")
    for m in messages:
        mine   = m["sender_id"] == my_id
        bg     = "#0a4d6e" if mine else "#0d1b2a"
        align  = "flex-end" if mine else "flex-start"
        radius = "14px 14px 4px 14px" if mine else "14px 14px 14px 4px"
        ts     = to_ist_str(m["sent_at"])
        ed     = " ✏️" if m.get("edited") else ""
        tick   = " ✓✓" if mine else ""
        html += (f"<div style='display:flex;justify-content:{align};'>"
                 f"<div style='max-width:72%;background:{bg};"
                 f"border-radius:{radius};padding:8px 12px;"
                 f"border:1px solid #1e3a5a;'>"
                 f"<div style='color:white;font-size:0.9rem;'>{m['message']}</div>"
                 f"<div style='color:#556;font-size:0.68rem;"
                 f"text-align:right;margin-top:2px;'>{ts} IST{ed}{tick}</div>"
                 f"</div></div>")
    html += (f"</div><script>"
             f"var c=document.getElementById('cb_{prefix}');"
             f"if(c)c.scrollTop=c.scrollHeight;</script>")
    st.components.v1.html(html, height=330, scrolling=False)

    # Send row
    ci, cb = st.columns([5, 1])
    with ci:
        st.text_input("msg", key=send_key,
                      placeholder="Type a message…",
                      label_visibility="collapsed")
    with cb:
        if st.button("➤", key=f"{prefix}_sendbtn",
                     use_container_width=True, type="primary"):
            txt = st.session_state.get(send_key, "").strip()
            if txt:
                send_message(my_id, other_id, txt)
                # Set clear_flag — popped BEFORE widget drawn on next run
                st.session_state[clear_flag] = True
                st.rerun()

    # Manage panel
    my_msgs = [m for m in messages if m["sender_id"] == my_id]
    if my_msgs:
        with st.expander("⚙️ Unsend / Edit my messages (5-min window)"):
            for m in list(reversed(my_msgs))[:5]:
                mid = m["id"]
                c1, c2, c3 = st.columns([3, 1, 1])
                with c1:
                    prev = m["message"][:55] + (
                        "…" if len(m["message"]) > 55 else "")
                    st.markdown(
                        f"<span style='color:#aaa;font-size:0.82rem;'>"
                        f"[{to_ist_str(m['sent_at'])}] {prev}</span>",
                        unsafe_allow_html=True)
                with c2:
                    if st.button("✏️", key=f"{prefix}_edt_{mid}", help="Edit"):
                        st.session_state[f"{prefix}_editing_{mid}"] = True
                with c3:
                    if st.button("🗑️", key=f"{prefix}_uns_{mid}", help="Unsend"):
                        ok, info = unsend_message(mid, my_id)
                        (st.success if ok else st.error)(info)
                        if ok:
                            st.rerun()

                if st.session_state.get(f"{prefix}_editing_{mid}"):
                    et_key = f"{prefix}_etxt_{mid}"
                    if et_key not in st.session_state:
                        st.session_state[et_key] = m["message"]
                    st.text_input("Edit:", key=et_key,
                                  label_visibility="collapsed")
                    s1, s2 = st.columns(2)
                    with s1:
                        if st.button("💾 Save", key=f"{prefix}_esave_{mid}"):
                            ok, info = edit_message(
                                mid, my_id,
                                st.session_state.get(et_key, ""))
                            (st.success if ok else st.error)(info)
                            st.session_state.pop(f"{prefix}_editing_{mid}", None)
                            if ok:
                                st.rerun()
                    with s2:
                        if st.button("✖", key=f"{prefix}_ecancel_{mid}"):
                            st.session_state.pop(f"{prefix}_editing_{mid}", None)
                            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
#  CHECKLIST  (doctor posts, patient marks)
# ══════════════════════════════════════════════════════════════════════════════
def _checklist_ui(doctor_id, patient_id, patient_name, prefix):
    st.markdown(f"**📋 Checklist Tasks for {patient_name}**")

    items = get_checklist(doctor_id, patient_id)

    if items:
        cats = CHECKLIST_CATEGORIES
        for cat in cats:
            cat_items = [i for i in items if i["category"] == cat]
            if not cat_items:
                continue
            cat_icons = {"Daily": "☀️", "Weekly": "📅", "Monthly": "🗓️"}
            st.markdown(
                f"<div style='color:{ACCENT};font-weight:700;font-size:0.9rem;"
                f"margin:10px 0 4px;border-bottom:1px solid #1e3a5a;'>"
                f"{cat_icons.get(cat,'📌')} {cat} Tasks</div>",
                unsafe_allow_html=True)
            for item in cat_items:
                iid  = item["id"]
                done = bool(item["is_done"])
                c2, c3 = st.columns([5, 0.6])
                # Doctor can view but NOT toggle — only patient can mark items
                with c2:
                    done_icon = "✅" if done else "⬜"
                    style = ("text-decoration:line-through;color:#556;"
                             if done else "color:white;")
                    st.markdown(
                        f"<span style='margin-right:6px;'>{done_icon}</span>"
                        f"<span style='{style}'>{item['item_text']}</span>",
                        unsafe_allow_html=True)
                with c3:
                    if st.button("🗑️", key=f"{prefix}_delchk_{iid}"):
                        delete_checklist_item(iid)
                        st.rerun()
    else:
        st.info("No checklist items yet. Add some below!")

    st.markdown("---")
    st.markdown("**➕ Add New Checklist Item**")

    cat_key  = f"{prefix}_newcat"
    ni_key   = f"{prefix}_newchk"
    ni_clear = f"{prefix}_newchk_clear"
    if st.session_state.pop(ni_clear, False):
        st.session_state.pop(ni_key, None)

    cat_col, item_col, btn_col = st.columns([2, 3, 1])
    with cat_col:
        st.selectbox("Category", CHECKLIST_CATEGORIES,
                     key=cat_key, label_visibility="collapsed")
    with item_col:
        st.text_input("Add item", key=ni_key,
                      placeholder="Add checklist item…",
                      label_visibility="collapsed")
    with btn_col:
        if st.button("➕", key=f"{prefix}_addchk",
                     use_container_width=True):
            txt = st.session_state.get(ni_key, "").strip()
            cat = st.session_state.get(cat_key, "Daily")
            if txt:
                add_checklist_item(doctor_id, patient_id, txt, cat)
                st.session_state[ni_clear] = True
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
#  NOTES  (patient-specific notes + self notes)
# ══════════════════════════════════════════════════════════════════════════════
def _notes_tab(my_id, patients):
    nt1, nt2 = st.tabs(["📝 Patient Notes", "🗒️ My Private Notes"])

    # ── Patient Notes ─────────────────────────────────────────────────────────
    with nt1:
        if not patients:
            st.info("No patients assigned yet.")
            return

        opts = {f"👤 {p['full_name']} (@{p['username']})": p for p in patients}
        sel_label = st.selectbox("Select patient:", list(opts.keys()),
                                 key="doc_notes_pat_sel")
        pat = opts[sel_label]
        pid = pat["id"]

        # ── Add doctor note ──────────────────────────────────────────────────
        st.markdown(
            f"<div style='color:{ACCENT};font-weight:700;margin:10px 0 4px;'>"
            f"✍️ Add Note for {pat['full_name']}</div>",
            unsafe_allow_html=True)

        nk     = f"doc_note_pg_{pid}"
        nk_clr = f"doc_note_pg_clr_{pid}"
        if st.session_state.pop(nk_clr, False):
            st.session_state.pop(nk, None)

        st.text_area("Note content", key=nk, height=90,
                     label_visibility="collapsed",
                     placeholder="Write a clinical note for this patient…")
        if st.button("💾 Save Note for Patient", key=f"doc_savepgnote_{pid}",
                     type="primary"):
            txt = st.session_state.get(nk, "").strip()
            if txt:
                add_doctor_note(my_id, pid, txt)
                st.session_state[nk_clr] = True
                st.success("✅ Note saved!")
                st.rerun()
            else:
                st.warning("Write something first.")

        # ── Doctor's notes for this patient ───────────────────────────────────
        st.markdown(
            f"<div style='color:{ACCENT};font-weight:700;margin:14px 0 6px;'>"
            f"📋 Your Notes for {pat['full_name']}</div>",
            unsafe_allow_html=True)
        doc_notes = get_notes_for_patient(pid)
        if doc_notes:
            for n in doc_notes:
                _n_time = to_ist_full(n["created_at"])
                _n_note = n["note"]
                st.markdown(
                    "<div style='background:#0a1e30;border-left:3px solid " + ACCENT + ";"
                    "border-radius:8px;padding:10px 14px;margin-bottom:6px;'>"
                    "<div style='color:" + ACCENT + ";font-size:0.72rem;font-weight:700;'>"
                    "&#129514; " + _n_time + "</div>"
                    "<div style='color:white;margin-top:4px;'>" + _n_note + "</div>"
                    "</div>",
                    unsafe_allow_html=True)
        else:
            st.info("No notes added yet for this patient.")

        # ── Patient's own personal notes (read-only for doctor) ──────────────
        st.markdown(
            "<div style='color:#aa88ff;font-weight:700;margin:14px 0 6px;'>"
            "📓 Patient's Personal Notes (read-only)</div>",
            unsafe_allow_html=True)
        pat_notes = get_patient_notes(pid)
        if pat_notes:
            for n in pat_notes:
                cn = n.get("color", "Ocean Blue")
                if cn.startswith("#"):
                    cn = "Ocean Blue"
                bg = NOTE_COLOR_MAP.get(cn, "#1a2a3a")
                ac = NOTE_ACCENT_MAP.get(cn, "#00d4ff")
                _pn_title   = n["title"]
                _pn_time    = to_ist_full(n["created_at"])
                _pn_content = n["content"]
                st.markdown(
                    "<div style='background:" + bg + ";border-left:4px solid " + ac + ";"
                    "border-radius:8px;padding:10px 14px;margin-bottom:6px;'>"
                    "<div style='color:" + ac + ";font-size:0.72rem;font-weight:700;'>"
                    "&#128204; " + _pn_title + " &nbsp;&bull;&nbsp; " + _pn_time + "</div>"
                    "<div style='color:white;font-size:0.88rem;white-space:pre-wrap;"
                    "margin-top:4px;'>" + _pn_content + "</div>"
                    "</div>",
                    unsafe_allow_html=True)
        else:
            st.info("This patient has no personal notes yet.")

    # ── Doctor Self Notes ─────────────────────────────────────────────────────
    with nt2:
        st.markdown("**🗒️ Private Notes (only you can see these)**")

        with st.expander("➕ Add New Self Note", expanded=False):
            sn_title_key = "doc_selfnote_title"
            sn_body_key  = "doc_selfnote_body"
            sn_col_key   = "doc_selfnote_col"
            sn_clr_flag  = "doc_selfnote_clear"
            # Clear fields after save
            if st.session_state.pop(sn_clr_flag, False):
                st.session_state.pop(sn_title_key, None)
                st.session_state.pop(sn_body_key, None)
            st.text_input("Title *", key=sn_title_key,
                          placeholder="Note title…")
            st.text_area("Content *", key=sn_body_key, height=100,
                         placeholder="Write your private note…")
            sn_color = st.selectbox("Color Theme", COLOR_NAMES,
                                    key=sn_col_key)
            bg_hex = NOTE_COLOR_MAP[sn_color]
            ac_hex = NOTE_ACCENT_MAP[sn_color]
            st.markdown(
                f"<div style='width:100%;height:10px;border-radius:4px;"
                f"background:{bg_hex};border-left:4px solid {ac_hex};'></div>",
                unsafe_allow_html=True)
            if st.button("💾 Save Private Note", key="doc_save_selfnote",
                         type="primary"):
                t = st.session_state.get(sn_title_key, "").strip()
                b = st.session_state.get(sn_body_key, "").strip()
                if t and b:
                    add_doctor_self_note(my_id, t, b, sn_color)
                    st.session_state[sn_clr_flag] = True
                    st.success("✅ Private note saved!")
                    st.rerun()
                else:
                    st.warning("Fill in both title and content.")

        self_notes = get_doctor_self_notes(my_id)
        if not self_notes:
            st.info("No private notes yet.")
        else:
            cols = st.columns(2)
            for i, note in enumerate(self_notes):
                cn = note.get("color", "Ocean Blue")
                if cn.startswith("#"):
                    cn = "Ocean Blue"
                bg = NOTE_COLOR_MAP.get(cn, "#1a2a3a")
                ac = NOTE_ACCENT_MAP.get(cn, "#00d4ff")
                nid = note["id"]
                with cols[i % 2]:
                    _sn_title   = note["title"]
                    _sn_time    = to_ist_full(note["created_at"])
                    _sn_content = note["content"]
                    st.markdown(
                        "<div style='background:" + bg + ";border-left:4px solid " + ac + ";"
                        "border-radius:8px;padding:12px 14px;margin-bottom:8px;'>"
                        "<div style='color:" + ac + ";font-size:0.7rem;font-weight:700;'>"
                        "&#128204; " + _sn_title + " &nbsp;&bull;&nbsp; " + _sn_time + "</div>"
                        "<div style='color:white;font-size:0.88rem;"
                        "white-space:pre-wrap;margin-top:4px;'>" + _sn_content + "</div>"
                        "</div>",
                        unsafe_allow_html=True)
                    if st.button("🗑️ Delete", key=f"doc_del_sn_{nid}"):
                        delete_doctor_self_note(nid)
                        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
#  STRESS ALERTS TAB
# ══════════════════════════════════════════════════════════════════════════════
def _alerts_tab(my_id):
    unread_count = get_unread_alert_count(my_id)

    col_h, col_btn = st.columns([3, 1])
    with col_h:
        st.subheader("🚨 Priority Stress Alerts")
    with col_btn:
        if unread_count > 0:
            if st.button("✅ Mark all read", key="doc_mark_alerts"):
                mark_alerts_read(my_id)
                st.rerun()

    alerts = get_stress_alerts_for_doctor(my_id, unread_only=False)

    if not alerts:
        st.markdown(
            "<div style='background:#0d1b2a;border-radius:12px;"
            "padding:24px;text-align:center;'>"
            "<div style='font-size:2rem;'>✅</div>"
            "<div style='color:#00ff88;font-weight:700;margin-top:8px;'>"
            "No stress alerts — all patients are in good condition!</div>"
            "</div>", unsafe_allow_html=True)
        return

    # Info banner
    if unread_count > 0:
        st.markdown(
            f"<div style='background:#1a0a0a;border:1px solid #ff4b4b44;"
            f"border-radius:10px;padding:10px 14px;margin-bottom:10px;"
            f"display:flex;align-items:center;gap:10px;'>"
            f"<span style='font-size:1.4rem;'>🔔</span>"
            f"<span style='color:#ff4b4b;font-weight:700;'>"
            f"{unread_count} new unread alert(s)</span></div>",
            unsafe_allow_html=True)

    ALERT_COLORS = {
        "Medium Stress": ("#e67e22", "#1a1200"),
        "High Stress":   ("#e74c3c", "#1a0505"),
        "Very High":     ("#8e44ad", "#120a1a"),
    }

    def _alert_color(lbl: str):
        """Match even if label has trailing emoji."""
        for key, val in ALERT_COLORS.items():
            if key.lower() in lbl.lower():
                return val
        return ("#ff8800", "#1a1000")

    for a in alerts:
        label = a.get("stress_label", "—")
        ac, bg = _alert_color(label)
        is_new = not bool(a.get("is_read", False))
        new_badge = (" <span style='background:#ff4b4b;color:white;"
                     "border-radius:10px;padding:1px 7px;"
                     "font-size:0.7rem;'>NEW</span>" if is_new else "")

        st.markdown(f"""
        <div style='background:{bg};border:1px solid {ac}44;
                    border-left:4px solid {ac};border-radius:10px;
                    padding:12px 16px;margin-bottom:8px;'>
            <div style='display:flex;align-items:center;gap:10px;'>
                {avatar_html(a.get("profile_photo"),
                             a.get("patient_name","P"), 38, ac)}
                <div style='flex:1;'>
                    <div style='color:white;font-weight:800;font-size:0.95rem;'>
                        {a.get("patient_name","Patient")} {new_badge}
                    </div>
                    <div style='color:{ac};font-weight:700;font-size:0.85rem;'>
                        ⚠️ {label} (Score: {a.get("stress_level","—")})
                    </div>
                    <div style='color:#778;font-size:0.75rem;'>
                        🕐 {str(a.get("created_at",""))[:16]}
                    </div>
                </div>
            </div>
        </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  PROFILE
# ══════════════════════════════════════════════════════════════════════════════
def _profile_section(user):
    uid = user["id"]
    prof_tab, portfolio_tab = st.tabs(["👤 My Profile", "🩺 My Portfolio"])

    def _dob_for_input(raw_value):
        if not raw_value:
            return date(1990, 1, 1)
        try:
            return datetime.strptime(str(raw_value)[:10], "%Y-%m-%d").date()
        except Exception:
            return date(1990, 1, 1)

    with prof_tab:
        col_p, col_f = st.columns([1, 2])

        with col_p:
            st.markdown("**Profile Photo**")
            photo = user.get("profile_photo")
            if photo:
                st.markdown(
                    f"<img src='{photo}' style='width:120px;height:120px;object-fit:cover;border-radius:50%;border:3px solid {ACCENT};'>",
                    unsafe_allow_html=True)
                if st.button("🗑️ Delete Photo", key="doc_del_photo"):
                    delete_profile_photo(uid)
                    st.session_state.user = get_user_by_id(uid)
                    st.rerun()
            else:
                st.markdown(
                    f"<div style='width:120px;height:120px;border-radius:50%;background:{ACCENT}22;border:3px solid {ACCENT};display:flex;align-items:center;justify-content:center;font-size:3rem;'>🩺</div>",
                    unsafe_allow_html=True)
            upf = st.file_uploader("Upload", type=["jpg","jpeg","png","webp"], key="doc_upf")
            if upf and st.button("📤 Upload Photo", key="doc_do_up"):
                update_profile_photo(uid, upf.read(), upf.type or "image/png")
                st.session_state.user = get_user_by_id(uid)
                st.success("✅ Photo updated!")
                st.rerun()

        with col_f:
            st.text_input("Full Name", value=user.get("full_name", ""), key="doc_pf_name")
            st.text_input("Email", value=user.get("email", ""), key="doc_pf_email")
            st.text_input("Phone", value=user.get("phone", ""), key="doc_pf_phone")
            st.date_input(
                "Date of Birth",
                value=_dob_for_input(user.get("dob")),
                min_value=date(1900, 1, 1),
                max_value=date.today(),
                key="doc_pf_dob",
            )
            detected_age = calculate_age_from_dob(st.session_state.get("doc_pf_dob"))
            if detected_age is not None:
                st.caption(f"Current age from DOB: {detected_age} years")
            st.text_area("Bio", value=user.get("bio", ""), key="doc_pf_bio", height=80)

            if st.button("💾 Save Profile", key="doc_save_pf", type="primary"):
                update_user_profile(
                    uid,
                    st.session_state.get("doc_pf_name"),
                    st.session_state.get("doc_pf_email"),
                    st.session_state.get("doc_pf_phone"),
                    st.session_state.get("doc_pf_dob"),
                )
                update_bio(uid, st.session_state.get("doc_pf_bio", ""))
                st.session_state.user = get_user_by_id(uid)
                st.success("✅ Saved!")
                st.rerun()

            st.markdown("---")
            st.markdown("**Change Password**")
            st.text_input("Current Password", type="password", key="doc_old_pw")
            st.text_input("New Password", type="password", key="doc_np1")
            st.text_input("Confirm New", type="password", key="doc_np2")
            if st.button("🔒 Change Password", key="doc_chg_pw"):
                old = st.session_state.get("doc_old_pw", "")
                n1 = st.session_state.get("doc_np1", "")
                n2 = st.session_state.get("doc_np2", "")
                if authenticate_user(user["username"], old, role_filter="doctor"):
                    if n1 == n2 and len(n1) >= 6:
                        change_password(uid, n1)
                        st.success("✅ Password changed!")
                    else:
                        st.error("Passwords don't match or too short (min 6).")
                else:
                    st.error("Current password incorrect.")

    with portfolio_tab:
        st.markdown("**🩺 My Professional Portfolio**")
        st.markdown(
            "<div style='background:#0a1e30;border:1px solid #00d4ff44;"
            "border-radius:8px;padding:8px 12px;margin-bottom:10px;"
            "font-size:0.82rem;color:#aaa;'>"
            "ℹ️ This information is visible to your assigned patients "
            "when they view 'My Doctor' section.</div>",
            unsafe_allow_html=True)

        existing = get_doctor_portfolio(uid)
        pe1, pe2 = st.columns(2)
        with pe1:
            st.text_input("Specialization",
                          value=existing.get("specialization",""),
                          key="doc_port_spec")
            st.text_input("Qualification",
                          value=existing.get("qualification",""),
                          key="doc_port_qual")
            st.number_input("Years of Experience",
                            value=int(existing.get("experience_yrs",0)),
                            min_value=0, max_value=60,
                            key="doc_port_exp")
            st.text_input("Hospital / Clinic",
                          value=existing.get("hospital",""),
                          key="doc_port_hosp")
        with pe2:
            st.text_input("Languages",
                          value=existing.get("languages",""),
                          key="doc_port_langs")
            st.text_input("Consultation Fee",
                          value=existing.get("consultation_fee",""),
                          key="doc_port_fee")
            st.text_input("Availability",
                          value=existing.get("availability",""),
                          key="doc_port_avail")

        st.text_area("About / Bio",
                     value=existing.get("about",""),
                     key="doc_port_about", height=80)
        st.text_area("Achievements",
                     value=existing.get("achievements",""),
                     key="doc_port_achiev", height=70)

        if st.button("💾 Save Portfolio", key="doc_port_save",
                     type="primary"):
            upsert_doctor_portfolio(
                uid,
                specialization   = st.session_state.get("doc_port_spec",""),
                qualification    = st.session_state.get("doc_port_qual",""),
                experience_yrs   = st.session_state.get("doc_port_exp", 0),
                hospital         = st.session_state.get("doc_port_hosp",""),
                about            = st.session_state.get("doc_port_about",""),
                achievements     = st.session_state.get("doc_port_achiev",""),
                languages        = st.session_state.get("doc_port_langs",""),
                consultation_fee = st.session_state.get("doc_port_fee",""),
                availability     = st.session_state.get("doc_port_avail",""),
            )
            st.success("✅ Portfolio saved!")
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
#  DOWNLOAD  (PDF)
# ══════════════════════════════════════════════════════════════════════════════
def _download_patient_report_pdf(patient, doctor_user, key_suffix=""):
    pid   = patient["id"]
    pname = patient.get("full_name", "patient")
    preds = get_predictions_by_patient(pid)
    notes = get_notes_for_patient(pid)

    from database import get_checklist_for_patient
    checklist = get_checklist_for_patient(pid)

    # Generate PDF bytes once — show a spinner, cache in session state per pid
    cache_key = f"_pdf_bytes_{pid}"
    pdf_key   = f"dl_pdf_{pid}_{key_suffix}"
    csv_key   = f"dl_csv_{pid}_{key_suffix}"

    if st.button(f"📄 Generate PDF for {pname}", key=f"gen_pdf_btn_{pid}_{key_suffix}",
                 use_container_width=True):
        with st.spinner("Generating PDF…"):
            try:
                pdf_bytes = generate_patient_report_pdf(
                    patient=patient,
                    doctor=doctor_user,
                    preds=preds,
                    doc_notes=notes,
                    checklist=checklist,
                    for_patient=False,
                )
                st.session_state[cache_key] = pdf_bytes
                st.success("✅ PDF ready! Click below to download.")
            except Exception as e:
                st.error(f"PDF generation error: {e}")
                st.session_state[cache_key] = None

    cached = st.session_state.get(cache_key)
    if cached is not None:
        fname = f"{pname.replace(' ','_')}_stress_report.pdf"
        st.download_button(
            label=f"⬇️ Download {pname}'s PDF Report",
            data=cached,
            file_name=fname,
            mime="application/pdf",
            key=pdf_key,
            use_container_width=True)
    elif cached is None and preds and st.session_state.get(f"_pdf_err_{pid}_{key_suffix}"):
        import io as _io
        safe_cols = [c for c in ["stress_label","stress_level","rr","bt","lm",
                                  "bo","rem","sh","hr","predicted_at"]
                     if c in pd.DataFrame(preds).columns]
        df = pd.DataFrame(preds)[safe_cols]
        buf = _io.StringIO()
        df.to_csv(buf, index=False)
        st.download_button(
            label=f"⬇️ Download {pname}'s Report (CSV fallback)",
            data=buf.getvalue(),
            file_name=f"{pname.replace(' ','_')}_stress_report.csv",
            mime="text/csv",
            key=csv_key)


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN app()
# ══════════════════════════════════════════════════════════════════════════════
def app():
    user     = st.session_state.user
    my_id    = user["id"]
    patients = get_patients_by_doctor(my_id)

    # ── Inner-tab auto-switch ─────────────────────────────────────────────────
    _open_alerts = st.session_state.pop("doc_open_alerts_tab", False)
    _open_chat   = st.session_state.pop("doc_open_chat_tab",   False)

    # Unread alert count for tab badge
    alert_cnt = get_unread_alert_count(my_id)

    _doc_name    = user.get("full_name", "Doctor")
    _doc_photo   = user.get("profile_photo")
    _avatar_html = avatar_html(_doc_photo, _doc_name, 56, ACCENT)
    _pat_count   = len(patients)
    _alert_html  = (
        "&nbsp;|&nbsp;<span style='color:#ff4b4b;'>&#128276; "
        + str(alert_cnt) + " alert(s)</span>"
    ) if alert_cnt > 0 else ""

    _header = (
        "<div style='background:linear-gradient(90deg,#0a1628,#0d2035);"
        "padding:1.2rem 1.6rem;border-radius:14px;margin-bottom:1.2rem;"
        "border-left:5px solid " + ACCENT + ";display:flex;"
        "align-items:center;gap:14px;'>"
        "<div>" + _avatar_html + "</div>"
        "<div>"
        "<div style='font-size:1.5rem;font-weight:900;color:" + ACCENT + ";'>"
        "&#129514; Doctor Dashboard</div>"
        "<div style='color:#aaa;font-size:0.9rem;'>"
        "Dr. <b style='color:white;'>" + _doc_name + "</b>"
        " &nbsp;|&nbsp; "
        "<span style='color:" + ACCENT + ";'>" + str(_pat_count) + " patient(s)</span>"
        + _alert_html +
        "</div>"
        "</div>"
        "</div>"
    )
    st.markdown(_header, unsafe_allow_html=True)

    total_p = sum(len(get_predictions_by_patient(p["id"])) for p in patients)
    unread  = get_unread_count(my_id)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👤 Patients",    len(patients))
    c2.metric("📊 Predictions", total_p)
    c3.metric("💬 Unread",      unread)
    c4.metric("🚨 Alerts",      alert_cnt)

    st.markdown("---")

    alert_tab_lbl  = (f"🚨 Alerts 🔴{alert_cnt}" if alert_cnt > 0 else "🚨 Alerts")
    unread_msg_lbl = (f"💬 Chat 🔴{unread}" if unread > 0 else "💬 Chat")
    t_pts, t_notes, t_chat, t_alerts, t_appts, t_med, t_prof = st.tabs(
        ["👤 Patients", "📝 Notes", unread_msg_lbl,
         alert_tab_lbl, "📅 Appointments", "🔬 Medical Reports", "⚙️ Profile"])

    # Auto-click a tab if redirected via session state flag
    _tab_keyword = (
        "Alerts" if _open_alerts else
        "Chat"   if _open_chat   else None
    )
    if _tab_keyword:
        st.components.v1.html(f"""
        <script>
        (function() {{
            function cleanLabel(txt) {{
                return String(txt || '')
                    .split('🔴')[0]
                    .replace(/\\s*\\(\\d+\\)\\s*/g, ' ')
                    .replace(/\\s+/g, ' ')
                    .trim();
            }}

            function tryClick(attempts) {{
                const tabs = Array.from(window.parent.document.querySelectorAll('[data-baseweb="tab"]'));
                for (const tab of tabs) {{
                    if (tab.innerText && tab.innerText.includes('{_tab_keyword}')) {{
                        tab.click();
                        try {{
                            const list = tab.closest('[data-baseweb="tab-list"]');
                            const sibs = Array.from(list.querySelectorAll('[data-baseweb="tab"]'));
                            const idx = sibs.indexOf(tab);
                            const labels = sibs.map(t => cleanLabel(t.innerText)).join('||');
                            const pageKey = (window.parent.location.pathname || '') + (window.parent.location.search || '');
                            window.parent.sessionStorage.setItem('gs_tab_state:' + pageKey + ':' + labels, String(idx));
                        }} catch (e) {{}}
                        return;
                    }}
                }}
                if (attempts > 0) setTimeout(() => tryClick(attempts - 1), 150);
            }}

            setTimeout(() => tryClick(12), 150);
        }})();
        </script>
        """, height=0, scrolling=False)

    # ── Patients ──────────────────────────────────────────────────────────────
    with t_pts:
        srch = st.text_input("🔍 Search patients…", key="doc_srch",
                             placeholder="Name / username / email…")
        fl   = patients
        if srch:
            q  = srch.lower()
            fl = [p for p in patients if
                  q in (p.get("full_name") or "").lower() or
                  q in (p.get("username")  or "").lower() or
                  q in (p.get("email")     or "").lower()]

        if not fl:
            st.info("No patients found.")
        else:
            for pat in fl:
                unr   = get_unread_count(my_id, pat["id"])
                badge = f" 🔴{unr}" if unr else ""

                # Checklist pending badge
                pending = get_checklist_pending_count(pat["id"])
                chk_badge = f" 📋{pending}" if pending else ""

                with st.expander(
                    f"👤 **{pat.get('full_name','?')}**"
                    f" (@{pat.get('username','?')}){badge}{chk_badge}"):

                    pt1, pt2 = st.tabs(["📊 History & Notes", "📋 Checklist"])

                    with pt1:
                        preds = get_predictions_by_patient(pat["id"])
                        if preds:
                            df_p = pd.DataFrame(preds)[[
                                "stress_label","stress_level","predicted_at"
                            ]].rename(columns={
                                "stress_label": "Level",
                                "stress_level": "Score",
                                "predicted_at": "When"})
                            st.dataframe(df_p.head(10),
                                         use_container_width=True)
                        else:
                            st.info("No predictions yet.")

                        # ── PDF Download ─────────────────────────────────────
                        _download_patient_report_pdf(pat, user, key_suffix="pts")

                        # Note input with clear-flag pattern
                        nk     = f"doc_note_{pat['id']}"
                        nk_clr = f"doc_note_clr_{pat['id']}"
                        if st.session_state.pop(nk_clr, False):
                            st.session_state.pop(nk, None)

                        st.markdown(
                            f"<div style='color:{ACCENT};font-weight:700;"
                            f"margin:10px 0 4px;'>✍️ Add Clinical Note</div>",
                            unsafe_allow_html=True)
                        st.text_area("Add note", key=nk, height=70,
                                     label_visibility="collapsed",
                                     placeholder="Write a clinical note…")
                        if st.button("➕ Save Note",
                                     key=f"doc_addnote_{pat['id']}"):
                            txt = st.session_state.get(nk, "").strip()
                            if txt:
                                add_doctor_note(my_id, pat["id"], txt)
                                st.session_state[nk_clr] = True
                                st.success("✅ Note added!")
                                st.rerun()

                        # Show doctor's notes for patient
                        st.markdown(
                            "<div style='color:#aaa;font-weight:700;"
                            "margin:12px 0 4px;'>📋 Your Notes</div>",
                            unsafe_allow_html=True)
                        for n in get_notes_for_patient(pat["id"])[:5]:
                            st.markdown(
                                f"<div style='background:#0d1b2a;"
                                f"border-left:3px solid {ACCENT};"
                                f"border-radius:6px;padding:8px 12px;"
                                f"margin-top:6px;'>"
                                f"<div style='color:{ACCENT};font-size:0.7rem;'>"
                                f"{to_ist_full(n['created_at'])}</div>"
                                f"<div style='color:white;font-size:0.88rem;'>"
                                f"{n['note']}</div></div>",
                                unsafe_allow_html=True)

                        # Show patient's personal notes (read-only)
                        pat_notes = get_patient_notes(pat["id"])
                        if pat_notes:
                            st.markdown(
                                "<div style='color:#aa88ff;font-weight:700;"
                                "margin:12px 0 4px;'>📓 Patient's Own Notes</div>",
                                unsafe_allow_html=True)
                            for n in pat_notes[:5]:
                                cn = n.get("color", "Ocean Blue")
                                if cn.startswith("#"):
                                    cn = "Ocean Blue"
                                ac = NOTE_ACCENT_MAP.get(cn, "#00d4ff")
                                st.markdown(
                                    f"<div style='background:#1a1a2a;"
                                    f"border-left:3px solid {ac};"
                                    f"border-radius:6px;padding:8px 12px;"
                                    f"margin-top:4px;'>"
                                    f"<div style='color:{ac};font-size:0.7rem;'>"
                                    f"📌 {n['title']} • {to_ist_full(n['created_at'])}</div>"
                                    f"<div style='color:#ccc;font-size:0.85rem;"
                                    f"margin-top:3px;'>{n['content'][:200]}"
                                    f"{'…' if len(n['content'])>200 else ''}</div>"
                                    f"</div>",
                                    unsafe_allow_html=True)

                    with pt2:
                        _checklist_ui(my_id, pat["id"],
                                      pat.get("full_name", "Patient"),
                                      prefix=f"chk_{pat['id']}")

    # ── Notes ─────────────────────────────────────────────────────────────────
    with t_notes:
        _notes_tab(my_id, patients)

    # ── Chat ──────────────────────────────────────────────────────────────────
    with t_chat:
        _chat_selector(my_id, patients, ctx="tab")

    # ── Alerts ────────────────────────────────────────────────────────────────
    with t_alerts:
        _updates_tab_doctor(my_id, patients)

    # ── Profile ───────────────────────────────────────────────────────────────
    with t_appts:
        _appointments_tab_doctor(my_id, user)

    with t_med:
        _medical_reports_tab_doctor(my_id)

    with t_prof:
        _profile_section(user)


# ══════════════════════════════════════════════════════════════════════════════
#  UPDATES TAB  — combined alerts + unread messages + recent appointments
# ══════════════════════════════════════════════════════════════════════════════
def _updates_tab_doctor(my_id, patients):
    """Unified updates panel: stress alerts + appointment activity + unread chat."""
    alert_cnt   = get_unread_alert_count(my_id)
    unread_msg  = get_unread_count(my_id)
    appt_notifs = get_appointment_notifications(my_id, limit=20, unread_only=False)
    appt_unread = sum(1 for n in appt_notifs if not n.get("is_read"))

    st.markdown(
        "<div style='background:linear-gradient(90deg,#0a1628,#0d2035);"
        "border-radius:12px;padding:14px 18px;margin-bottom:16px;"
        "border-left:5px solid #ff4b4b;'>"
        "<div style='font-size:1.2rem;font-weight:900;color:#ff4b4b;'>"
        "🔔 Updates & Notifications</div>"
        "<div style='color:#aaa;font-size:0.82rem;margin-top:3px;'>"
        "Stress alerts, appointment activity and unread messages.</div>"
        "</div>", unsafe_allow_html=True)

    # ── Summary badges ────────────────────────────────────────────────────────
    ub1, ub2, ub3, ub4 = st.columns(4)
    try:
        all_appts     = get_appointments_for_doctor(my_id)
        pending_appts = sum(1 for a in all_appts if a.get("status") == "Pending")
    except Exception:
        pending_appts = 0

    for col, count, label in [
        (ub1, alert_cnt,   "Stress Alerts"),
        (ub2, appt_unread, "Appt Updates"),
        (ub3, unread_msg,  "Unread Messages"),
        (ub4, pending_appts, "Pending Appts"),
    ]:
        c = ("#ff4b4b" if count > 0 else "#2ecc71") if label != "Pending Appts" \
            else ("#f1c40f" if count > 0 else "#2ecc71")
        col.markdown(
            f"<div style='background:#0d1b2a;border:1px solid {c}44;"
            f"border-radius:10px;padding:12px 14px;text-align:center;'>"
            f"<div style='font-size:1.5rem;font-weight:900;color:{c};'>{count}</div>"
            f"<div style='color:#aaa;font-size:0.8rem;'>{label}</div></div>",
            unsafe_allow_html=True)

    st.markdown("---")

    upd_t1, upd_t2, upd_t3 = st.tabs([
        f"🚨 Stress Alerts {'🔴' + str(alert_cnt) if alert_cnt > 0 else '✅'}",
        f"📅 Appointment Activity {'🔴' + str(appt_unread) if appt_unread > 0 else '✅'}",
        f"💬 Messages {'🔴' + str(unread_msg) if unread_msg > 0 else '✅'}",
    ])

    # ── Stress alerts ─────────────────────────────────────────────────────────
    with upd_t1:
        _alerts_tab(my_id)

    # ── Appointment notifications (patient confirmed / declined / cancelled) ───
    with upd_t2:
        if not appt_notifs:
            st.markdown(
                "<div style='background:#0d1b2a;border-radius:12px;"
                "padding:24px;text-align:center;'>"
                "<div style='font-size:2rem;'>✅</div>"
                "<div style='color:#00ff88;font-weight:700;margin-top:8px;'>"
                "No appointment activity yet.</div></div>",
                unsafe_allow_html=True)
        else:
            if appt_unread > 0:
                if st.button("✅ Mark all as read",
                             key="doc_mark_appt_read", type="primary"):
                    mark_appointment_notifications_read(my_id)
                    st.rerun()
                st.markdown("")
            for n in appt_notifs:
                is_new = not n.get("is_read")
                border = "#aa88ff" if is_new else "#2a3a4a"
                bg     = "#1a0a2a" if is_new else "#0d1b2a"
                new_badge = (" <span style='background:#ff4b4b;color:white;"
                             "border-radius:10px;padding:1px 7px;"
                             "font-size:0.72rem;font-weight:800;'>NEW</span>"
                             if is_new else "")
                ts = str(n.get("created_at", ""))[:16]
                st.markdown(
                    f"<div style='background:{bg};border-left:4px solid {border};"
                    f"border-radius:8px;padding:12px 16px;margin-bottom:8px;'>"
                    f"<div style='color:white;font-weight:700;'>"
                    f"{n.get('title','')} {new_badge}</div>"
                    f"<div style='color:#aaa;font-size:0.85rem;margin-top:4px;'>"
                    f"{n.get('message','')}</div>"
                    f"<div style='color:#556;font-size:0.75rem;margin-top:4px;'>"
                    f"🕐 {ts}</div></div>",
                    unsafe_allow_html=True)

    # ── Unread messages per patient ───────────────────────────────────────────
    with upd_t3:
        if not patients:
            st.info("No patients assigned yet.")
        else:
            has_any = False
            for pat in patients:
                cnt = get_unread_count(my_id, pat["id"])
                if cnt > 0:
                    has_any = True
                    st.markdown(
                        f"<div style='background:#0a1628;border-left:4px solid #ff4b4b;"
                        f"border-radius:10px;padding:12px 16px;margin-bottom:8px;"
                        f"display:flex;align-items:center;justify-content:space-between;'>"
                        f"<div><div style='color:white;font-weight:800;'>"
                        f"👤 {pat['full_name']}</div>"
                        f"<div style='color:#aaa;font-size:0.8rem;'>"
                        f"@{pat.get('username','')}</div></div>"
                        f"<span style='background:#ff4b4b;color:white;border-radius:20px;"
                        f"padding:3px 12px;font-size:0.85rem;font-weight:800;'>"
                        f"💬 {cnt} new</span></div>",
                        unsafe_allow_html=True)
            if not has_any:
                st.markdown(
                    "<div style='background:#0d1b2a;border-radius:12px;"
                    "padding:24px;text-align:center;'>"
                    "<div style='font-size:2rem;'>✅</div>"
                    "<div style='color:#00ff88;font-weight:700;margin-top:8px;'>"
                    "No unread messages — all caught up!</div></div>",
                    unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  Reusable chat-selector
# ══════════════════════════════════════════════════════════════════════════════
def _chat_selector(my_id, patients, ctx):
    if not patients:
        st.info("No patients assigned yet.")
        return

    labels = []
    for p in patients:
        cnt = get_unread_count(my_id, p["id"])
        lbl = f"👤 {p['full_name']}"
        if cnt:
            lbl += f" 🔴{cnt}"
        labels.append(lbl)

    sel_lbl = st.selectbox("Select patient:", labels,
                           key=f"doc_chatsel_{ctx}")
    base    = sel_lbl.split(" 🔴")[0].strip()
    sel_pat = next(
        (p for p in patients if f"👤 {p['full_name']}" == base),
        patients[0])

    _chat_ui(my_id, sel_pat, prefix=f"{ctx}_{sel_pat['id']}")


# ══════════════════════════════════════════════════════════════════════════════
#  Sidebar Chat page
# ══════════════════════════════════════════════════════════════════════════════
def app_chat():
    user     = st.session_state.user
    my_id    = user["id"]
    patients = get_patients_by_doctor(my_id)

    st.markdown(f"""
    <div style='background:linear-gradient(90deg,#0a1628,#0d2035);
                padding:1rem 1.4rem;border-radius:14px;margin-bottom:1rem;
                border-left:5px solid {ACCENT};'>
        <div style='font-size:1.3rem;font-weight:900;color:{ACCENT};'>
            💬 Live Chat</div>
        <div style='color:#aaa;font-size:0.85rem;'>
            Real-time messaging with your patients</div>
    </div>""", unsafe_allow_html=True)

    _chat_selector(my_id, patients, ctx="side")


# ══════════════════════════════════════════════════════════════════════════════
#  APPOINTMENTS TAB (Doctor side)
# ══════════════════════════════════════════════════════════════════════════════
def _appointments_tab_doctor(doctor_id, user):
    from doctor_appointments import appointments_tab_doctor
    appointments_tab_doctor(doctor_id, user)


# ══════════════════════════════════════════════════════════════════════════════
#  MEDICAL REPORTS TAB (Doctor side — view + PDF scan)
# ══════════════════════════════════════════════════════════════════════════════
def _medical_reports_tab_doctor(doctor_id):
    st.subheader("🔬 Patient Medical Reports")
    st.markdown(
        "<div style='background:#0a1e30;border:1px solid #00d4ff44;"
        "border-radius:10px;padding:10px 14px;margin-bottom:12px;'>"
        "<b style='color:#00d4ff;'>📋 Medical Report Analysis</b>"
        "<span style='color:#aaa;font-size:0.85rem;'> — View and add notes on "
        "medical reports uploaded by your patients.</span></div>",
        unsafe_allow_html=True)

    reports = get_all_medical_reports_for_doctor(doctor_id)

    if not reports:
        st.info("No medical reports uploaded by your patients yet.")
        return

    for r in reports:
        rid       = r["id"]
        patient   = r.get("patient_name", "Unknown")
        fname     = r.get("filename", "report")
        ftype     = r.get("file_type", "")
        analysis  = r.get("analysis", "") or ""
        upl_at    = str(r.get("uploaded_at", ""))[:16]

        with st.expander(f"📄 {patient}  —  {fname}  ({upl_at})"):
            # Download the file
            full = get_medical_report_data(rid)
            if full and full.get("file_data"):
                import base64 as _b64
                raw = _b64.b64decode(full["file_data"])
                col_dl, col_sz = st.columns([2, 3])
                with col_dl:
                    mime = ftype or "application/octet-stream"
                    st.download_button(
                        f"⬇️ Download {fname}",
                        data=raw,
                        file_name=fname,
                        mime=mime,
                        key=f"doc_mr_dl_{rid}")
                with col_sz:
                    st.caption(f"Size: {len(raw)/1024:.1f} KB  |  Type: {ftype or 'unknown'}")

            # Analysis notes
            an_key = f"doc_mr_an_{rid}"
            if an_key not in st.session_state:
                st.session_state[an_key] = analysis

            st.text_area(
                "📝 Doctor's Analysis / Notes on this report",
                key=an_key,
                height=100,
                placeholder="Enter your clinical observations, stress indicators, etc…")

            if st.button("💾 Save Analysis", key=f"doc_mr_save_{rid}",
                         type="primary"):
                update_medical_report_analysis(
                    rid, st.session_state.get(an_key, ""))
                st.success("✅ Analysis saved!")
                st.rerun()

            # PDF stress scan hint
            if fname.lower().endswith(".pdf") or "pdf" in (ftype or "").lower():
                with st.expander("🔍 PDF Content Preview (text extraction)"):
                    try:
                        import io as _io
                        import importlib.util
                        # Try PyPDF2 or pdfplumber
                        full2 = get_medical_report_data(rid)
                        if full2:
                            raw2  = _b64.b64decode(full2["file_data"])
                            pdf_text = ""
                            # Try pdfplumber first
                            try:
                                import pdfplumber
                                with pdfplumber.open(_io.BytesIO(raw2)) as pdf:
                                    for pg in pdf.pages[:5]:
                                        pdf_text += (pg.extract_text() or "") + "\n"
                            except ImportError:
                                try:
                                    import PyPDF2
                                    reader = PyPDF2.PdfReader(_io.BytesIO(raw2))
                                    for pg in reader.pages[:5]:
                                        pdf_text += (pg.extract_text() or "") + "\n"
                                except ImportError:
                                    pdf_text = "(Install pdfplumber or PyPDF2 for text extraction)"
                            if pdf_text.strip():
                                st.text_area("Extracted Text (first 5 pages)",
                                             value=pdf_text[:3000],
                                             height=200,
                                             key=f"doc_mr_text_{rid}",
                                             disabled=True)
                                # Keyword stress scan
                                stress_kw = ["stress","anxiety","high blood pressure",
                                             "cortisol","depression","insomnia",
                                             "fatigue","burnout","hypertension"]
                                found_kw = [k for k in stress_kw
                                            if k in pdf_text.lower()]
                                if found_kw:
                                    st.markdown(
                                        f"<div style='background:#1a0505;border-left:4px solid #ff4b4b;"
                                        f"border-radius:8px;padding:8px 12px;margin-top:6px;'>"
                                        f"<b style='color:#ff4b4b;'>⚠️ Stress indicators found:</b>"
                                        f"<span style='color:white;'> "
                                        f"{', '.join(found_kw)}</span></div>",
                                        unsafe_allow_html=True)
                                else:
                                    st.success("✅ No common stress keywords detected in report.")
                            else:
                                st.info("Could not extract text from this PDF.")
                    except Exception as ex:
                        st.warning(f"Preview error: {ex}")