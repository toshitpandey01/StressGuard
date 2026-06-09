
from datetime import datetime, date
import streamlit as st
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from time_utils import COMMON_TIMEZONES, format_db_timestamp, sanitize_timezone, tz_label

from admin_appointments import admin_appointments_tab
from database import (
    get_all_users, get_all_doctors, get_all_patients,
    get_all_predictions, get_stats, delete_user,
    register_user, assign_doctor_to_patient,
    update_profile_photo, delete_profile_photo,
    update_bio, get_user_by_id, admin_reset_password,
    update_user_profile, change_password, encode_photo, authenticate_user, calculate_age_from_dob,
    upsert_doctor_portfolio, get_all_doctor_portfolios, get_doctor_portfolio,
    get_patients_with_doctors,
    get_all_login_logs,
    save_doctor_portfolio_pdf, get_doctor_portfolio_pdf, delete_doctor_portfolio_pdf,
)
from utils import avatar_html
from report_generator import generate_admin_roster_pdf, generate_login_log_pdf

ACCENT = "#ff4b4b"


def app():
    user = st.session_state.user

    # ── Header ─────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div style='background:linear-gradient(90deg,#1a0505,#2a0d0d);
                padding:1.2rem 1.6rem;border-radius:14px;margin-bottom:1.2rem;
                border-left:5px solid {ACCENT};
                display:flex;align-items:center;gap:14px;'>
        <div>{avatar_html(user.get('profile_photo'),
                          user.get('full_name','A'), 56, ACCENT)}</div>
        <div>
            <div style='font-size:1.5rem;font-weight:900;color:{ACCENT};'>
                🔴 Admin Dashboard</div>
            <div style='color:#aaa;font-size:0.9rem;'>
                Logged in as <b style='color:white;'>{user['full_name']}</b>
                &nbsp;|&nbsp;
                <span style='color:{ACCENT};'>System Administrator</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    stats = get_stats()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🩺 Doctors",     stats['doctors'])
    c2.metric("👤 Patients",    stats['patients'])
    c3.metric("📊 Predictions", stats['predictions'])
    c4.metric("👥 Total Users", stats['doctors'] + stats['patients'])

    st.markdown("---")
    (tab_users, tab_add, tab_assign,
     tab_preds, tab_analytics, tab_portfolio,
     tab_appts,
     tab_download, tab_login_logs, tab_profile) = st.tabs(
        ["👥 Users", "➕ Add User", "🔗 Assign",
         "📋 Predictions", "📈 Analytics",
         "🩺 Doctor Portfolios",
         "📅 Appointments & Tickets",
         "⬇️ Download Roster",
         "🔑 Login Logs",
         "⚙️ My Profile"])

    # ── TAB: Users ─────────────────────────────────────────────────────────
    with tab_users:
        st.subheader("All Registered Users")
        srch = st.text_input("🔍 Search users…", key="adm_search",
                             placeholder="Name / username / email / role…")
        users = get_all_users()
        if srch:
            q = srch.lower()
            users = [u for u in users if
                     q in (u.get('full_name') or '').lower() or
                     q in (u.get('username')  or '').lower() or
                     q in (u.get('email')     or '').lower() or
                     q in (u.get('role')      or '').lower()]

        if not users:
            st.info("No users found.")
        else:
            for u in users:
                rc = "#00d4ff" if u['role'] == "doctor" else "#00ff88"
                role_lbl = ("🩺 Doctor" if u['role'] == "doctor"
                            else "👤 Patient")
                with st.expander(
                    f"**{u.get('full_name','?')}**  "
                    f"(@{u.get('username','?')})  —  {role_lbl}"):

                    ci1, ci2, ci3 = st.columns([2, 2, 1])
                    uid = u['id']

                    with ci1:
                        st.write(f"📧 {u.get('email','—')}")
                        st.write(f"📱 {u.get('phone','—')}")
                        dob_text = str(u.get('dob',''))[:10] if u.get('dob') else "—"
                        st.write(f"🎂 DOB: {dob_text}")
                        st.write(f"📅 Joined: "
                                 f"{str(u.get('created_at',''))[:10]}")

                    with ci2:
                        vis_key = f"adm_pw_vis_{uid}"
                        if st.button(
                            "🙈 Hide" if st.session_state.get(vis_key)
                            else "👁️ Show Password",
                            key=f"adm_pw_toggle_{uid}"):
                            st.session_state[vis_key] = \
                                not st.session_state.get(vis_key, False)
                            st.session_state.pop("_nav_redirect", None)
                            st.rerun()

                        if st.session_state.get(vis_key):
                            plain = u.get('plain_password') or '(not stored)'
                            st.code(plain, language=None)

                        rp_key = f"adm_rp_{uid}"
                        if rp_key not in st.session_state:
                            st.session_state[rp_key] = ""
                        st.text_input("New password to set",
                                      type="password", key=rp_key,
                                      label_visibility="collapsed",
                                      placeholder="Enter new password…")
                        if st.button("🔄 Reset Password",
                                     key=f"adm_rp_btn_{uid}"):
                            new_pw = st.session_state.get(rp_key, "")
                            if len(new_pw) >= 6:
                                admin_reset_password(uid, new_pw)
                                st.success("✅ Password reset!")
                                st.session_state[rp_key] = ""
                                st.session_state.pop("_nav_redirect", None)
                                st.rerun()
                            else:
                                st.warning("Password must be ≥ 6 chars.")

                    with ci3:
                        if st.button("🗑️ Delete",
                                     key=f"adm_del_{uid}"):
                            delete_user(uid)
                            st.success("Deleted.")
                            st.session_state.pop("_nav_redirect", None)
                            st.rerun()

    # ── TAB: Add User ───────────────────────────────────────────────────────
    with tab_add:
        st.subheader("Add New User")

        # ── Clear flags for text fields after successful creation ──────────
        for fk in ["adm_add_name","adm_add_email","adm_add_phone",
                   "adm_add_uname","adm_add_pass", "adm_add_dob"]:
            if st.session_state.pop(f"{fk}_clr", False):
                st.session_state.pop(fk, None)

        add_role = st.selectbox(
            "Role", ["doctor", "patient"],
            format_func=lambda x: (
                "🩺 Doctor" if x == "doctor" else "👤 Patient"),
            key="adm_add_role")

        a1, a2 = st.columns(2)
        with a1:
            st.text_input("Full Name *",  key="adm_add_name")
            st.text_input("Email *",      key="adm_add_email")
            st.text_input("Phone",        key="adm_add_phone")
            st.date_input("Date of Birth *", value=date(2000, 1, 1), min_value=date(1900, 1, 1), max_value=date.today(), key="adm_add_dob")
        with a2:
            st.text_input("Username *",   key="adm_add_uname")
            st.text_input("Password *",   type="password",
                          key="adm_add_pass")

        a_photo = st.file_uploader(
            "Profile Photo (optional)",
            type=["jpg","jpeg","png","webp"],
            key="adm_add_photo")

        doc_id = None
        if add_role == "patient":
            doctors = get_all_doctors()
            if doctors:
                d_opts = {f"🩺 Dr. {d['full_name']}": d['id']
                          for d in doctors}
                d_opts["— Assign later —"] = None
                sel = st.selectbox("Assign Doctor:",
                                   list(d_opts.keys()),
                                   key="adm_add_doc")
                doc_id = d_opts[sel]

        if st.button("➕ Create Account", key="adm_create_btn",
                     type="primary"):
            name  = st.session_state.get("adm_add_name","").strip()
            email = st.session_state.get("adm_add_email","").strip()
            uname = st.session_state.get("adm_add_uname","").strip()
            pw    = st.session_state.get("adm_add_pass","")
            phone = st.session_state.get("adm_add_phone","")
            dob = st.session_state.get("adm_add_dob")

            if not all([name, email, uname, pw, dob]):
                st.warning("⚠️ Fill in all required (*) fields.")
            elif len(pw) < 6:
                st.warning("Password must be ≥ 6 chars.")
            elif calculate_age_from_dob(dob) is None:
                st.warning("Please enter a valid DOB.")
            else:
                photo_uri = None
                if a_photo:
                    photo_uri = encode_photo(
                        a_photo.read(),
                        a_photo.type or "image/png")
                ok, msg = register_user(
                    uname, pw, add_role, name, email,
                    phone, doc_id, photo_uri, dob=dob)
                if ok:
                    # ── popup / balloon on success ─────────────────────────
                    st.balloons()
                    st.success(f"✅ {add_role.title()} account created for "
                               f"**{name}** (@{uname})!")
                    # Clear all text fields
                    for fk in ["adm_add_name","adm_add_email","adm_add_phone",
                               "adm_add_uname","adm_add_pass", "adm_add_dob"]:
                        st.session_state[f"{fk}_clr"] = True
                    st.session_state.pop("_nav_redirect", None)
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")

    # ── TAB: Assign ─────────────────────────────────────────────────────────
    with tab_assign:
        st.subheader("Assign Doctor to Patient")
        doctors  = get_all_doctors()
        patients = get_all_patients()
        if doctors and patients:
            d_opts = {f"🩺 Dr. {d['full_name']}": d['id']
                      for d in doctors}
            p_opts = {f"👤 {p['full_name']} (@{p['username']})": p['id']
                      for p in patients}
            sel_doc = st.selectbox("Doctor:",  list(d_opts.keys()),
                                   key="adm_asgn_doc")
            sel_pat = st.selectbox("Patient:", list(p_opts.keys()),
                                   key="adm_asgn_pat")
            if st.button("🔗 Assign", key="adm_asgn_btn",
                         type="primary"):
                assign_doctor_to_patient(p_opts[sel_pat],
                                         d_opts[sel_doc])
                st.success("✅ Doctor–Patient relationship assigned!")
                st.session_state.pop("_nav_redirect", None)
                st.rerun()
        else:
            st.info("Need at least one doctor AND one patient.")

    # ── TAB: Predictions ────────────────────────────────────────────────────
    with tab_preds:
        st.subheader("All Predictions")
        preds = get_all_predictions()
        if preds:
            df_p = pd.DataFrame(preds)[
                ['full_name','username','stress_label',
                 'stress_level','predicted_at']
            ].rename(columns={
                'full_name':  'Patient',
                'username':   '@username',
                'stress_label': 'Stress',
                'stress_level': 'Level',
                'predicted_at': 'When'})
            srch2 = st.text_input("🔍 Filter…", key="adm_pred_srch")
            if srch2:
                mask = df_p.apply(
                    lambda r: srch2.lower() in str(r).lower(), axis=1)
                df_p = df_p[mask]
            st.dataframe(df_p, use_container_width=True)
        else:
            st.info("No predictions yet.")

    # ── TAB: Analytics ──────────────────────────────────────────────────────
    with tab_analytics:
        st.subheader("System Analytics")
        dist = stats.get('stress_dist', {})
        if dist:
            fig, (ax1, ax2) = plt.subplots(
                1, 2, figsize=(10, 4), facecolor='#0d1b2a')
            colors_list = ['#2ecc71','#f1c40f','#e67e22','#e74c3c','#8e44ad']
            labels = list(dist.keys())
            values = list(dist.values())

            ax1.pie(values, labels=labels,
                    colors=colors_list[:len(values)],
                    autopct='%1.1f%%', startangle=90,
                    textprops={'color':'white','fontsize':9})
            ax1.set_title("Stress Distribution",
                          color='white', fontweight='bold')
            ax1.set_facecolor('#0d1b2a')

            ax2.bar(labels, values,
                    color=colors_list[:len(values)],
                    edgecolor='#1e3a5a')
            ax2.set_facecolor('#0d1b2a')
            ax2.tick_params(colors='white')
            for sp in ax2.spines.values():
                sp.set_edgecolor('#2a3a5a')
            ax2.set_title("Stress Counts",
                          color='white', fontweight='bold')

            fig.tight_layout()
            st.pyplot(fig)
            plt.close()
        else:
            st.info("No prediction data yet.")

    # ── TAB: Doctor Portfolios ───────────────────────────────────────────────
    with tab_portfolio:
        _portfolio_tab()

    # ── TAB: Appointments & Tickets ─────────────────────────────────────
    with tab_appts:
        admin_appointments_tab(user)

    # ── TAB: Download Roster ────────────────────────────────────────────────
    with tab_download:
        _download_roster_tab()

    # ── TAB: Login Logs ─────────────────────────────────────────────────────
    with tab_login_logs:
        _login_logs_tab()

    # ── TAB: Profile ────────────────────────────────────────────────────────
    with tab_profile:
        _profile_section(user)


# ════════════════════════════════════════════════════════════════════════════════
#  Download Roster Tab
# ════════════════════════════════════════════════════════════════════════════════
def _download_roster_tab():
    st.subheader("⬇️ Download Admin Roster PDF")
    st.markdown(
        "<div style='background:#0a1e30;border:1px solid #ff4b4b44;"
        "border-radius:10px;padding:12px 16px;margin-bottom:12px;'>"
        "<b style='color:#ff4b4b;'>📄 Roster PDF</b>"
        "<span style='color:#aaa;font-size:0.85rem;'> — Contains a full list of "
        "registered doctors, patients, and which patient is assigned to which doctor. "
        "Includes a professional watermark.</span></div>",
        unsafe_allow_html=True)

    col_info, col_btn = st.columns([2, 1])
    with col_info:
        docs = get_all_doctors()
        pwds = get_patients_with_doctors()
        st.markdown(
            f"<div style='background:#0d1b2a;border-radius:8px;padding:12px 16px;'>"
            f"<div style='color:#ff4b4b;font-weight:700;font-size:1rem;'>Roster Preview</div>"
            f"<div style='color:#aaa;margin-top:6px;font-size:0.9rem;'>"
            f"🩺 Doctors: <b style='color:white;'>{len(docs)}</b> &nbsp;&nbsp;"
            f"👤 Patients: <b style='color:white;'>{len(pwds)}</b> &nbsp;&nbsp;"
            f"🔗 Assigned: <b style='color:white;'>{sum(1 for p in pwds if p.get('doctor_name'))}</b> &nbsp;&nbsp;"
            f"⚠️ Unassigned: <b style='color:#ff8800;'>{sum(1 for p in pwds if not p.get('doctor_name'))}</b>"
            f"</div></div>",
            unsafe_allow_html=True)

    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("📊 Generate & Download PDF Roster",
                     key="adm_dl_roster", type="primary",
                     use_container_width=True):
            try:
                pdf_bytes = generate_admin_roster_pdf(
                    doctors=get_all_doctors(),
                    patients_with_doctors=get_patients_with_doctors())
                st.download_button(
                    label="⬇️ Click here to Download Roster PDF",
                    data=pdf_bytes,
                    file_name="admin_roster.pdf",
                    mime="application/pdf",
                    key="adm_dl_roster_dl",
                    use_container_width=True)
            except Exception as exc:
                st.error(f"❌ PDF generation error: {exc}")
                # CSV fallback
                import io as _io
                docs2  = get_all_doctors()
                pwds2  = get_patients_with_doctors()
                rows   = []
                for d in docs2:
                    rows.append({"Role":"Doctor","Name":d.get("full_name",""),
                                 "Username":d.get("username",""),
                                 "Email":d.get("email",""),
                                 "Assigned Doctor":""})
                for p in pwds2:
                    rows.append({"Role":"Patient","Name":p.get("full_name",""),
                                 "Username":p.get("username",""),
                                 "Email":p.get("email",""),
                                 "Assigned Doctor":p.get("doctor_name","") or "Unassigned"})
                import pandas as _pd
                buf = _io.StringIO()
                _pd.DataFrame(rows).to_csv(buf, index=False)
                st.download_button(
                    label="⬇️ Download Roster (CSV fallback)",
                    data=buf.getvalue(),
                    file_name="admin_roster.csv",
                    mime="text/csv",
                    key="adm_dl_roster_csv")


# ════════════════════════════════════════════════════════════════════════════════
#  Doctor Portfolio Tab
# ════════════════════════════════════════════════════════════════════════════════
def _portfolio_tab():
    st.subheader("🩺 Doctor Portfolios")

    doctors = get_all_doctors()
    if not doctors:
        st.info("No doctors registered yet.")
        return

    # Sub-tabs: View All | Edit
    pv_view, pv_edit = st.tabs(["👀 View All", "✏️ Edit Portfolio"])

    with pv_view:
        portfolios = get_all_doctor_portfolios()
        port_map = {p["doctor_id"]: p for p in portfolios}

        for doc in doctors:
            did  = doc["id"]
            port = port_map.get(did, {})

            spec  = port.get("specialization",  "—") or "—"
            qual  = port.get("qualification",   "—") or "—"
            exp   = port.get("experience_yrs",   0)
            hosp  = port.get("hospital",         "—") or "—"
            about = port.get("about",            "") or ""
            langs = port.get("languages",        "—") or "—"
            fee   = port.get("consultation_fee", "—") or "—"
            avail = port.get("availability",     "—") or "—"

            with st.expander(
                f"🩺 **Dr. {doc.get('full_name','?')}**  "
                f"— {spec}"):

                pc1, pc2 = st.columns([1, 3])
                with pc1:
                    photo = doc.get("profile_photo")
                    if photo:
                        st.markdown(
                            f"<img src='{photo}' style='width:90px;"
                            f"height:90px;object-fit:cover;border-radius:50%;"
                            f"border:3px solid #00d4ff;'>",
                            unsafe_allow_html=True)
                    else:
                        st.markdown(
                            "<div style='width:90px;height:90px;"
                            "border-radius:50%;background:#0a2a3a;"
                            "border:3px solid #00d4ff;"
                            "display:flex;align-items:center;"
                            "justify-content:center;"
                            "font-size:2.5rem;'>🩺</div>",
                            unsafe_allow_html=True)

                with pc2:
                    info_rows = [
                        ("📧 Email",        doc.get("email","—")),
                        ("📱 Phone",        doc.get("phone","—") or "—"),
                        ("🎓 Qualification",qual),
                        ("⏳ Experience",   f"{exp} year(s)"),
                        ("🏥 Hospital",     hosp),
                        ("🌐 Languages",    langs),
                        ("💰 Fee",          fee),
                        ("🗓️ Availability", avail),
                    ]
                    for lbl, val in info_rows:
                        st.markdown(
                            f"<div style='display:flex;gap:8px;"
                            f"margin-bottom:2px;'>"
                            f"<span style='color:#778;font-size:0.8rem;"
                            f"min-width:130px;'>{lbl}</span>"
                            f"<span style='color:white;font-size:0.85rem;'>"
                            f"{val}</span></div>",
                            unsafe_allow_html=True)

                if about:
                    st.markdown(
                        f"<div style='background:#0d1b2a;border-left:3px "
                        f"solid #00d4ff;border-radius:6px;padding:8px 12px;"
                        f"margin-top:6px;color:#ccc;font-size:0.85rem;'>"
                        f"ℹ️ {about}</div>",
                        unsafe_allow_html=True)
                if doc.get("bio"):
                    st.markdown(
                        f"<div style='color:#aaa;font-size:0.82rem;"
                        f"margin-top:4px;'>📝 {doc['bio']}</div>",
                        unsafe_allow_html=True)

    with pv_edit:
        if not doctors:
            st.info("No doctors available.")
            return

        d_opts = {f"🩺 Dr. {d['full_name']}": d for d in doctors}
        sel_label = st.selectbox("Select Doctor to Edit:",
                                 list(d_opts.keys()),
                                 key="adm_port_sel")
        sel_doc  = d_opts[sel_label]
        did      = sel_doc["id"]
        existing = get_doctor_portfolio(did)

        pe1, pe2 = st.columns(2)
        with pe1:
            st.text_input("Specialization",
                          value=existing.get("specialization",""),
                          key="adm_port_spec")
            st.text_input("Qualification",
                          value=existing.get("qualification",""),
                          key="adm_port_qual")
            st.number_input("Years of Experience",
                            value=int(existing.get("experience_yrs",0)),
                            min_value=0, max_value=60,
                            key="adm_port_exp")
            st.text_input("Hospital / Clinic",
                          value=existing.get("hospital",""),
                          key="adm_port_hosp")
        with pe2:
            st.text_input("Languages (comma-separated)",
                          value=existing.get("languages",""),
                          key="adm_port_langs")
            st.text_input("Consultation Fee",
                          value=existing.get("consultation_fee",""),
                          key="adm_port_fee")
            st.text_input("Availability (e.g. Mon-Fri 9am-5pm)",
                          value=existing.get("availability",""),
                          key="adm_port_avail")

        st.text_area("About / Bio",
                     value=existing.get("about",""),
                     key="adm_port_about", height=80)
        st.text_area("Achievements",
                     value=existing.get("achievements",""),
                     key="adm_port_achiev", height=70)

        if st.button("💾 Save Portfolio", key="adm_port_save",
                     type="primary"):
            upsert_doctor_portfolio(
                did,
                specialization   = st.session_state.get("adm_port_spec",""),
                qualification    = st.session_state.get("adm_port_qual",""),
                experience_yrs   = st.session_state.get("adm_port_exp", 0),
                hospital         = st.session_state.get("adm_port_hosp",""),
                about            = st.session_state.get("adm_port_about",""),
                achievements     = st.session_state.get("adm_port_achiev",""),
                languages        = st.session_state.get("adm_port_langs",""),
                consultation_fee = st.session_state.get("adm_port_fee",""),
                availability     = st.session_state.get("adm_port_avail",""),
            )
            st.success(f"✅ Portfolio saved for Dr. {sel_doc['full_name']}!")
            st.session_state.pop("_nav_redirect", None)
            st.rerun()

        # ── PDF Portfolio Upload ──────────────────────────────────────────────
        st.markdown("---")
        st.markdown("**📄 Upload PDF Portfolio** *(patients can view/download this)*")
        existing_pdf = get_doctor_portfolio_pdf(did)
        if existing_pdf:
            st.markdown(
                f"<div style='background:#0a1e30;border:1px solid #00d4ff44;"
                f"border-radius:8px;padding:8px 12px;margin-bottom:8px;'>"
                f"<span style='color:#00d4ff;font-weight:700;'>📄 Current PDF: </span>"
                f"<span style='color:white;font-size:0.88rem;'>"
                f"{existing_pdf.get('filename','portfolio.pdf')}</span>"
                f"<span style='color:#556;font-size:0.75rem;margin-left:8px;'>"
                f"(uploaded {format_db_timestamp(existing_pdf.get('uploaded_at',''), sanitize_timezone(user.get('timezone')) )})</span>"
                f"</div>", unsafe_allow_html=True)
            import base64 as _b64
            pdf_raw = _b64.b64decode(existing_pdf["pdf_data"])
            st.download_button(
                "⬇️ Download Current PDF", data=pdf_raw,
                file_name=existing_pdf.get("filename","portfolio.pdf"),
                mime="application/pdf",
                key=f"adm_port_dl_{did}")
            if st.button("🗑️ Remove PDF", key=f"adm_port_del_pdf_{did}"):
                delete_doctor_portfolio_pdf(did)
                st.success("PDF removed.")
                st.session_state.pop("_nav_redirect", None)
                st.rerun()
        pdf_up = st.file_uploader(
            "Upload new PDF portfolio", type=["pdf"],
            key=f"adm_port_pdf_up_{did}")
        if pdf_up and st.button("📤 Upload PDF Portfolio",
                                 key=f"adm_port_pdf_save_{did}",
                                 type="primary"):
            save_doctor_portfolio_pdf(did, pdf_up.read(), pdf_up.name)
            st.success(f"✅ PDF portfolio uploaded for Dr. {sel_doc['full_name']}!")
            st.session_state.pop("_nav_redirect", None)
            st.rerun()


# ════════════════════════════════════════════════════════════════════════════════
#  Profile Section (unique keys prefixed with adm_)
# ════════════════════════════════════════════════════════════════════════════════
def _profile_section(user: dict):
    uid = user["id"]

    def _dob_for_input(raw_value):
        if not raw_value:
            return date(1990, 1, 1)
        try:
            return datetime.strptime(str(raw_value)[:10], "%Y-%m-%d").date()
        except Exception:
            return date(1990, 1, 1)

    col_photo, col_form = st.columns([1, 2])

    with col_photo:
        st.markdown("**Profile Photo**")
        photo = user.get('profile_photo')
        if photo:
            st.markdown(
                f"<img src='{photo}' style='width:120px;height:120px;object-fit:cover;border-radius:50%;border:3px solid {ACCENT};'>",
                unsafe_allow_html=True)
            if st.button("🗑️ Delete Photo", key="adm_del_photo"):
                delete_profile_photo(uid)
                st.session_state.user = get_user_by_id(uid)
                st.success("Photo deleted.")
                st.session_state.pop("_nav_redirect", None)
                st.rerun()
        else:
            st.markdown(
                f"<div style='width:120px;height:120px;border-radius:50%;background:{ACCENT}22;border:3px solid {ACCENT};display:flex;align-items:center;justify-content:center;font-size:3rem;'>🔴</div>",
                unsafe_allow_html=True)

        new_photo = st.file_uploader("Upload photo", type=["jpg","jpeg","png","webp"], key="adm_upload_photo")
        if new_photo:
            if st.button("📤 Upload", key="adm_do_upload"):
                update_profile_photo(uid, new_photo.read(), new_photo.type or "image/png")
                st.session_state.user = get_user_by_id(uid)
                st.success("✅ Photo updated!")
                st.session_state.pop("_nav_redirect", None)
                st.rerun()

    with col_form:
        st.text_input("Full Name", value=user.get('full_name',''), key="adm_pf_name")
        st.text_input("Email", value=user.get('email',''), key="adm_pf_email")
        st.text_input("Phone", value=user.get('phone',''), key="adm_pf_phone")
        st.date_input(
            "Date of Birth",
            value=_dob_for_input(user.get("dob")),
            min_value=date(1900, 1, 1),
            max_value=date.today(),
            key="adm_pf_dob",
        )
        detected_age = calculate_age_from_dob(st.session_state.get("adm_pf_dob"))
        if detected_age is not None:
            st.caption(f"Current age from DOB: {detected_age} years")
        current_tz = sanitize_timezone(user.get("timezone"))
        tz_options = COMMON_TIMEZONES if current_tz in COMMON_TIMEZONES else [current_tz] + COMMON_TIMEZONES
        st.selectbox(
            "Preferred Timezone",
            tz_options,
            index=tz_options.index(current_tz),
            format_func=lambda x: f"{tz_label(x)} ({x})",
            key="adm_pf_timezone",
        )
        st.text_area("Bio", value=user.get('bio',''), key="adm_pf_bio", height=80)

        if st.button("💾 Save Profile", key="adm_save_profile", type="primary"):
            update_user_profile(
                uid,
                st.session_state.get("adm_pf_name"),
                st.session_state.get("adm_pf_email"),
                st.session_state.get("adm_pf_phone"),
                st.session_state.get("adm_pf_dob"),
                timezone=st.session_state.get("adm_pf_timezone"),
            )
            update_bio(uid, st.session_state.get("adm_pf_bio",""))
            st.session_state.user = get_user_by_id(uid)
            st.success("✅ Profile saved!")
            st.session_state.pop("_nav_redirect", None)
            st.rerun()

        st.markdown("---")
        st.markdown("**Change Password**")
        st.text_input("Current Password", type="password", key="adm_old_pw")
        st.text_input("New Password", type="password", key="adm_new_pw1")
        st.text_input("Confirm New", type="password", key="adm_new_pw2")

        if st.button("🔒 Change Password", key="adm_chg_pw"):
            old = st.session_state.get("adm_old_pw","")
            n1 = st.session_state.get("adm_new_pw1","")
            n2 = st.session_state.get("adm_new_pw2","")
            if authenticate_user(user['username'], old, role_filter="admin"):
                if n1 == n2 and len(n1) >= 6:
                    change_password(uid, n1)
                    st.success("✅ Password changed!")
                else:
                    st.error("Passwords don't match or too short.")
            else:
                st.error("Current password incorrect.")


# ════════════════════════════════════════════════════════════════════════════════
#  Login Logs Tab
# ════════════════════════════════════════════════════════════════════════════════
def _login_logs_tab():
    st.subheader("🔑 User Login History")
    st.markdown(
        "<div style='background:#0a1e30;border:1px solid #ff4b4b44;"
        "border-radius:10px;padding:10px 16px;margin-bottom:12px;'>"
        "<b style='color:#ff4b4b;'>📊 Login Audit Log</b>"
        "<span style='color:#aaa;font-size:0.85rem;'> — Shows all user login "
        "events, most recent first.</span></div>",
        unsafe_allow_html=True)

    logs = get_all_login_logs(limit=500)

    if not logs:
        st.info("No login records yet.")
        return

    ll1, ll2 = st.columns([2, 1])
    with ll1:
        srch = st.text_input("🔍 Filter by name / username / role…",
                             key="adm_log_srch",
                             placeholder="Type to filter…")
    with ll2:
        role_f = st.selectbox("Role filter", ["All","admin","doctor","patient"],
                              key="adm_log_role")

    filtered = logs
    if srch:
        q = srch.lower()
        filtered = [l for l in filtered if
                    q in (l.get("username") or "").lower() or
                    q in (l.get("full_name") or "").lower() or
                    q in (l.get("role") or "").lower()]
    if role_f != "All":
        filtered = [l for l in filtered if l.get("role") == role_f]

    st.markdown(
        f"<div style='color:#aaa;font-size:0.82rem;margin-bottom:8px;'>"
        f"Showing <b style='color:white;'>{len(filtered)}</b> of "
        f"<b style='color:white;'>{len(logs)}</b> entries</div>",
        unsafe_allow_html=True)

    import pandas as pd
    df_logs = pd.DataFrame([{
        "Username":   l.get("username","—"),
        "Full Name":  l.get("full_name","—") or "—",
        "Role":       (l.get("role","—") or "—").title(),
        "Email":      l.get("email","—") or "—",
        "Login Time": format_db_timestamp(l.get("logged_in_at","—")),
    } for l in filtered])
    st.dataframe(df_logs, use_container_width=True, height=420)

    # Download as PDF
    col_pdf, col_csv = st.columns(2)
    with col_pdf:
        if st.button("📊 Generate Login Log PDF", key="adm_log_pdf_btn",
                     type="primary", use_container_width=True):
            try:
                pdf_bytes = generate_login_log_pdf(filtered, timezone_name=sanitize_timezone(st.session_state.user.get("timezone")))
                st.download_button(
                    "⬇️ Download Login Log PDF",
                    data=pdf_bytes,
                    file_name="login_history.pdf",
                    mime="application/pdf",
                    key="adm_log_pdf_dl",
                    use_container_width=True)
            except Exception as e:
                st.error(f"PDF error: {e}")
    with col_csv:
        import io as _io
        buf = _io.StringIO()
        df_logs.to_csv(buf, index=False)
        st.download_button(
            "⬇️ Download CSV",
            data=buf.getvalue(),
            file_name="login_history.csv",
            mime="text/csv",
            key="adm_log_csv",
            use_container_width=True)