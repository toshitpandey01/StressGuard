import io
import random
from datetime import datetime, date
import streamlit as st
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os

from web_functions import predict, load_data
from database import (
    save_prediction, get_predictions_by_patient,
    get_notes_for_patient, get_doctor_of_patient, get_doctors_for_patient,
    send_message, get_chat_messages, mark_messages_read, get_unread_count,
    add_patient_note, get_patient_notes, delete_patient_note, update_patient_note,
    update_profile_photo, delete_profile_photo, update_bio, get_user_by_id,
    unsend_message, edit_message, update_user_profile, change_password,
    encode_photo, authenticate_user, NOTE_COLOR_MAP, NOTE_ACCENT_MAP,
    get_checklist_for_patient, toggle_checklist_item, CHECKLIST_CATEGORIES,
    get_checklist_pending_count, get_doctor_portfolio,
    create_stress_alert,
    book_appointment, get_appointments_for_patient,
    save_medical_report, get_medical_reports_for_patient,
    get_medical_report_data, delete_medical_report,
    get_doctor_portfolio_pdf, calculate_age_from_dob,
    get_unread_notification_count,
)
from report_generator import generate_patient_report_pdf, generate_appointment_slip_pdf
from utils import avatar_html, to_ist_str, to_ist_full
from patient_appointments import appointments_tab_patient as render_patient_appointments
from time_utils import COMMON_TIMEZONES, format_db_timestamp, sanitize_timezone, tz_label

ACCENT = "#00ff88"

STRESS_INFO = {
    0: {"label": "Safe 😄",          "color": "#2ecc71",
        "advice": "Excellent! Keep this sleep routine going."},
    1: {"label": "Low Stress 🙂",    "color": "#f1c40f",
        "advice": "Mild stress. Try light relaxation exercises."},
    2: {"label": "Medium Stress 😐",  "color": "#e67e22",
        "advice": "Moderate stress. Try meditation, limit screens before bed."},
    3: {"label": "High Stress 😞",   "color": "#e74c3c",
        "advice": "High stress! Contact your doctor. Practice deep breathing."},
    4: {"label": "Very High 😫",     "color": "#8e44ad",
        "advice": "Critical! Seek professional help immediately."},
}

STRESS_IMGS = {
    0: "./images/calm.png",
    1: "./images/low_stress.png",
    2: "./images/medium_stress.png",
    3: "./images/high_stress.png",
    4: "./images/very_high_stress.png",
}


# ══════════════════════════════════════════════════════════════════════════════
#  CHATBOT  — Rule-based positive support
# ══════════════════════════════════════════════════════════════════════════════

_BOT_RULES = [
    # greetings
    (["hello","hi","hey","good morning","good afternoon","good evening","hii"],
     ["Hello! 😊 I'm your wellness companion. How are you feeling today?",
      "Hey there! 🌟 I'm here for you. What's on your mind?",
      "Hi! 💚 Great to see you. How can I support you today?"]),

    # stress keywords
    (["stress","stressed","overwhelm","pressure","tense","tension","burnout",
      "exhausted","drain","overload"],
     ["It's completely normal to feel stressed sometimes. 💙 Remember, you're stronger than you think! Try taking 5 deep breaths — breathe in for 4 counts, hold for 4, and out for 4.",
      "Stress can feel heavy, but it always passes. 🌈 One step at a time! Try a short walk or listen to your favourite calming music.",
      "You're doing amazing by recognizing this. 🌟 Stress is your mind's signal to slow down. How about a 5-minute stretch break right now?"]),

    # anxiety
    (["anxious","anxiety","panic","worry","worr","nervous","fear","scared",
      "dread","uneasy"],
     ["Anxiety can feel overwhelming, but you are safe right now. 💚 Try the 5-4-3-2-1 technique: name 5 things you see, 4 you can touch, 3 you hear, 2 you smell, 1 you taste.",
      "You are not alone in this! 🤗 Anxiety is just your brain trying to protect you. Slow your breathing — it sends a calm signal to your nervous system.",
      "It's okay to feel anxious. 🌸 Take it one moment at a time. You've overcome hard moments before — you'll get through this too!"]),

    # sleep
    (["sleep","insomnia","tired","fatigue","rest","sleepless","can't sleep",
      "cannot sleep","no sleep","bad sleep"],
     ["Good sleep is the foundation of wellness. 🌙 Try keeping a consistent bedtime, avoiding screens 1 hour before bed, and making your room cool and dark.",
      "Trouble sleeping? 💤 Try progressive muscle relaxation: tense and release each muscle group from toes to head. Many people fall asleep within 10 minutes!",
      "Your body needs quality rest to recover. 🌟 A warm bath, light reading, or soft music can signal your brain it's time to wind down."]),

    # sad / low mood
    (["sad","unhappy","depress","low mood","down","cry","hopeless","lonely",
      "empty","worthless","not okay","not fine"],
     ["I hear you, and your feelings are completely valid. 💙 Remember, dark clouds always pass. You matter more than you know.",
      "It's okay to not be okay sometimes. 🌸 Be gentle with yourself today. Even doing one small kind thing for yourself counts as progress.",
      "You showed up today — that takes courage. 💪 Please know that brighter days are ahead. Consider talking to someone you trust or your doctor."]),

    # positive / happy
    (["happy","great","good","well","awesome","fantastic","wonderful","excited",
      "positive","better","improve"],
     ["That's wonderful to hear! 🎉 Keep nurturing those positive feelings — they're great for your well-being!",
      "You're glowing with good energy! ✨ Celebrate your wins, big and small — you deserve it!",
      "Brilliant! 🌟 Keep this momentum going. Positivity is contagious — share your good vibes with those around you!"]),

    # breathing / meditation
    (["breath","breathe","meditate","calm","relax","peaceful","mindful",
      "mindfulness","yoga"],
     ["Brilliant choice! 🧘 Deep breathing activates your parasympathetic nervous system and reduces cortisol. Just 5 minutes can make a real difference.",
      "Mindfulness is a superpower! 🌸 Even a few conscious breaths can anchor you in the present and dissolve stress. You're on the right track!",
      "Love that you're focusing on relaxation. 💚 Consistency is key — a short daily practice builds resilience over time."]),

    # exercise / physical
    (["exercise","walk","run","workout","gym","physical","sport","active",
      "move","movement"],
     ["Exercise is one of the best natural stress relievers! 🏃 Even a 10-minute brisk walk can boost your mood significantly.",
      "Great instinct! 💪 Physical activity releases endorphins — your brain's natural happiness chemicals. Keep it up!",
      "Movement is medicine! 🌟 Regular exercise not only reduces stress but also improves sleep quality. You're making excellent choices."]),

    # eating / nutrition
    (["eat","food","diet","nutrition","hungry","meal","drink","water",
      "hydrat"],
     ["Nourishing your body is self-care! 🥗 Omega-3 rich foods, leafy greens, and staying hydrated can genuinely improve your mood and reduce anxiety.",
      "Remember to eat well and stay hydrated! 💧 Your brain is 75% water — even mild dehydration can affect your mood and focus.",
      "Food is fuel for your mind too. 🌿 Try to avoid excessive caffeine and sugar, especially when you're feeling stressed."]),

    # asking for help / doctor
    (["doctor","help","support","professional","counsel","therapist","talk to",
      "need help","consult"],
     ["Seeking help is a sign of strength, not weakness. 💙 Your doctor is there to support you. Don't hesitate to share everything you're feeling with them.",
      "Reaching out is the bravest thing you can do! 🌟 Mental health professionals have the tools to help you thrive — you deserve that support.",
      "You're making the right move! 💪 Your wellness team is here for you. Use the Chat section to message your doctor directly."]),

    # gratitude / thankful
    (["grateful","gratitude","thankful","thank","appreciate","blessed"],
     ["Gratitude is a powerful practice! 🌸 Research shows that expressing thanks can rewire the brain for positivity over time. Keep it up!",
      "What a beautiful mindset! ✨ Gratitude shifts your focus from what's wrong to what's right. You're on an amazing path.",
      "Love that energy! 💚 Try keeping a gratitude journal — writing down 3 things you're thankful for each day can transform your outlook."]),

    # default fallback
    (None,
     ["I'm here to support you on your wellness journey! 💙 Remember, every day is a new opportunity to care for yourself.",
      "You're doing great by taking care of your mental health! 🌟 Keep going — I believe in you!",
      "Whatever you're facing, you have the strength to overcome it. 💚 I'm always here if you want to talk.",
      "Your well-being matters. 🌸 Take it one day at a time, and be kind to yourself along the way.",
      "You are not alone on this journey. 💪 Small steps every day lead to big transformations!"])
]


def _bot_respond(user_msg: str) -> str:
    """Return a positive, supportive bot response for the given message."""
    msg_lower = user_msg.lower()
    for keywords, responses in _BOT_RULES:
        if keywords is None:
            # default — return random
            return random.choice(responses)
        if any(kw in msg_lower for kw in keywords):
            return random.choice(responses)
    # fallback
    return random.choice(_BOT_RULES[-1][1])


def _chatbot_ui():
    """Render the supportive chatbot panel for patients."""
    st.markdown(f"""
    <div style='background:linear-gradient(135deg,#081a12,#0d2018);
                border:1px solid {ACCENT}44;border-radius:14px;
                padding:16px 20px;margin-bottom:12px;'>
        <div style='font-size:1.2rem;font-weight:900;color:{ACCENT};'>
            🤖 Wellness Companion</div>
        <div style='color:#aaa;font-size:0.85rem;margin-top:4px;'>
            Share your thoughts, feelings, or questions.
            I'm here to provide positive support 💚</div>
    </div>""", unsafe_allow_html=True)

    # Init chat history in session state
    if "bot_history" not in st.session_state:
        st.session_state.bot_history = [
            {"role": "bot",
             "text": "Hi there! 👋 I'm your Wellness Companion. "
                     "Feel free to share how you're feeling — whether it's stress, "
                     "anxiety, sleep issues, or just wanting someone to talk to. "
                     "I'm here to support you! 💚"}
        ]

    # Display chat history
    history_html = (
        "<div style='height:340px;overflow-y:auto;padding:8px 4px;"
        "display:flex;flex-direction:column;gap:8px;' id='bot_chat_box'>")
    for msg in st.session_state.bot_history:
        if msg["role"] == "user":
            history_html += (
                f"<div style='display:flex;justify-content:flex-end;'>"
                f"<div style='max-width:75%;background:#1a4a2a;"
                f"border-radius:14px 14px 4px 14px;padding:10px 14px;"
                f"border:1px solid #2a6a3a;'>"
                f"<div style='color:white;font-size:0.9rem;'>{msg['text']}</div>"
                f"<div style='color:#556;font-size:0.65rem;text-align:right;margin-top:3px;'>You</div>"
                f"</div></div>")
        else:
            history_html += (
                f"<div style='display:flex;justify-content:flex-start;gap:8px;'>"
                f"<div style='font-size:1.5rem;align-self:flex-end;'>🤖</div>"
                f"<div style='max-width:75%;background:#0a1e30;"
                f"border-radius:14px 14px 14px 4px;padding:10px 14px;"
                f"border:1px solid #1e3a5a;'>"
                f"<div style='color:{ACCENT};font-size:0.9rem;'>{msg['text']}</div>"
                f"<div style='color:#556;font-size:0.65rem;margin-top:3px;'>Wellness Bot</div>"
                f"</div></div>")
    history_html += (
        "</div><script>"
        "var b=document.getElementById('bot_chat_box');"
        "if(b)b.scrollTop=b.scrollHeight;</script>")
    st.components.v1.html(history_html, height=360, scrolling=False)

    # Input row
    bot_inp_key   = "bot_msg_input"
    bot_clr_flag  = "bot_msg_clear"
    if st.session_state.pop(bot_clr_flag, False):
        st.session_state.pop(bot_inp_key, None)

    ci, cb = st.columns([5, 1])
    with ci:
        st.text_input("Your message", key=bot_inp_key,
                      placeholder="How are you feeling? Share anything…",
                      label_visibility="collapsed")
    with cb:
        if st.button("➤", key="bot_send_btn",
                     use_container_width=True, type="primary"):
            txt = st.session_state.get(bot_inp_key, "").strip()
            if txt:
                st.session_state.bot_history.append(
                    {"role": "user", "text": txt})
                response = _bot_respond(txt)
                st.session_state.bot_history.append(
                    {"role": "bot", "text": response})
                st.session_state[bot_clr_flag] = True
                st.rerun()

    # Quick-action buttons
    st.markdown("**💡 Quick topics:**")
    qb_cols = st.columns(4)
    quick_prompts = [
        "I'm feeling stressed",
        "I can't sleep well",
        "I feel anxious",
        "Give me a motivation boost",
    ]
    for i, (col, prompt) in enumerate(zip(qb_cols, quick_prompts)):
        with col:
            if st.button(prompt, key=f"bot_quick_{i}",
                         use_container_width=True):
                st.session_state.bot_history.append(
                    {"role": "user", "text": prompt})
                response = _bot_respond(prompt)
                st.session_state.bot_history.append(
                    {"role": "bot", "text": response})
                st.rerun()

    # Clear chat
    if st.button("🗑️ Clear conversation", key="bot_clear_hist"):
        st.session_state.bot_history = [
            {"role": "bot",
             "text": "Fresh start! 🌟 I'm here whenever you need me. "
                     "How can I support you today? 💚"}
        ]
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
#  CHECKLIST  (doctor-assigned, patient marks)
# ══════════════════════════════════════════════════════════════════════════════
def _checklist_ui_patient(patient_id, key_prefix: str = "chk"):

    """Show doctor-assigned checklist with toggle for patient."""
    st.markdown(f"""
    <div style='background:linear-gradient(135deg,#081a12,#0d2018);
                border:1px solid {ACCENT}44;border-radius:14px;
                padding:16px 20px;margin-bottom:12px;'>
        <div style='font-size:1.1rem;font-weight:900;color:{ACCENT};'>
            📋 My Wellness Checklist</div>
        <div style='color:#aaa;font-size:0.82rem;margin-top:4px;'>
            Tasks set by your doctor to track your daily, weekly & monthly progress
        </div>
    </div>""", unsafe_allow_html=True)

    items = get_checklist_for_patient(patient_id)
    if not items:
        st.info("✅ No checklist items assigned yet. Your doctor will add tasks for you.")
        return

    # Group by category
    cat_icons = {"Daily": "☀️", "Weekly": "📅", "Monthly": "🗓️"}
    cats = CHECKLIST_CATEGORIES

    total   = len(items)
    done    = sum(1 for i in items if i["is_done"])
    pct     = int(done / total * 100) if total else 0

    # Progress bar
    bar_color = "#2ecc71" if pct >= 80 else "#f1c40f" if pct >= 50 else ACCENT
    st.markdown(f"""
    <div style='margin-bottom:14px;'>
        <div style='display:flex;justify-content:space-between;
                    color:#aaa;font-size:0.82rem;margin-bottom:4px;'>
            <span>Overall Progress</span>
            <span style='color:{bar_color};font-weight:700;'>
                {done}/{total} completed ({pct}%)</span>
        </div>
        <div style='background:#1e2a3a;border-radius:20px;height:10px;'>
            <div style='background:{bar_color};width:{pct}%;height:10px;
                        border-radius:20px;transition:width 0.4s;'></div>
        </div>
    </div>""", unsafe_allow_html=True)

    for cat in cats:
        cat_items = [i for i in items if i["category"] == cat]
        if not cat_items:
            continue

        cat_done = sum(1 for i in cat_items if i["is_done"])
        st.markdown(
            f"<div style='color:{ACCENT};font-weight:700;font-size:0.95rem;"
            f"margin:12px 0 6px;border-bottom:1px solid #1e3a5a;'>"
            f"{cat_icons.get(cat,'📌')} {cat} Tasks "
            f"<span style='color:#aaa;font-weight:400;font-size:0.8rem;'>"
            f"({cat_done}/{len(cat_items)})</span></div>",
            unsafe_allow_html=True)

        for item in cat_items:
            iid  = item["id"]
            done_flag = bool(item["is_done"])
            c1, c2 = st.columns([0.5, 8])
            with c1:
                checked = st.checkbox(
                    "", value=done_flag,
                    key=f"{key_prefix}_pat_chk_{iid}",
                    label_visibility="collapsed")
                if checked != done_flag:
                    toggle_checklist_item(iid)
                    st.rerun()
            with c2:
                style = ("text-decoration:line-through;color:#556;"
                         if done_flag else "color:white;")
                doc_name = item.get("doctor_name", "Your Doctor")
                st.markdown(
                    f"<div style='{style}'>{item['item_text']}"
                    f"<span style='color:#446;font-size:0.72rem;margin-left:8px;'>"
                    f"— Dr. {doc_name}</span></div>",
                    unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  CHAT
# ══════════════════════════════════════════════════════════════════════════════
def _chat_ui(my_id: int, doctor: dict, prefix: str, all_doctors: list = None):
    # ── Multi-doctor selector with unread badges ──────────────────────────────
    if all_doctors and len(all_doctors) > 1:
        doc_map   = {}
        total_unread = 0
        for d in all_doctors:
            u = get_unread_count(my_id, d["id"])
            total_unread += u
            star  = "⭐ " if d.get("is_primary") else ""
            badge = f" 🔴 {u}" if u > 0 else ""
            label = f"{star}Dr. {d['full_name']}{badge}"
            doc_map[label] = d

        # Top unread alert banner
        if total_unread > 0:
            st.markdown(
                f"<div style='background:#1a0505;border:1px solid #ff4b4b;"
                f"border-radius:10px;padding:10px 16px;margin-bottom:10px;"
                f"display:flex;align-items:center;gap:10px;'>"
                f"<span style='font-size:1.4rem;'>💬</span>"
                f"<div><b style='color:#ff4b4b;'>You have {total_unread} unread message(s)!</b>"
                f"<div style='color:#aaa;font-size:0.8rem;'>Select a doctor below to read them.</div></div>"
                f"</div>",
                unsafe_allow_html=True)

        sel_key = f"{prefix}_doc_sel"
        chosen_label = st.selectbox(
            "💬 Select Doctor to Chat With",
            list(doc_map.keys()),
            key=sel_key,
        )
        active_doc = doc_map[chosen_label]
    else:
        active_doc   = doctor
        total_unread = get_unread_count(my_id, doctor["id"])
        # Top unread alert banner for single doctor
        if total_unread > 0:
            st.markdown(
                f"<div style='background:#1a0505;border:1px solid #ff4b4b;"
                f"border-radius:10px;padding:10px 16px;margin-bottom:10px;"
                f"display:flex;align-items:center;gap:10px;'>"
                f"<span style='font-size:1.4rem;'>💬</span>"
                f"<div><b style='color:#ff4b4b;'>You have {total_unread} unread message(s) from Dr. {doctor['full_name']}!</b>"
                f"<div style='color:#aaa;font-size:0.8rem;'>Scroll down to read them.</div></div>"
                f"</div>",
                unsafe_allow_html=True)

    doc_id    = active_doc["id"]
    doc_name  = active_doc["full_name"]
    doc_photo = active_doc.get("profile_photo")

    send_key   = f"{prefix}_inp"
    clear_flag = f"{prefix}_clr"
    if st.session_state.pop(clear_flag, False):
        st.session_state.pop(send_key, None)

    mark_messages_read(doc_id, my_id)
    unread   = get_unread_count(my_id, doc_id)
    messages = get_chat_messages(my_id, doc_id)

    st.markdown(f"""
    <div style='display:flex;align-items:center;gap:12px;background:#081a10;
                border-radius:12px;padding:12px 16px;margin-bottom:8px;'>
        {avatar_html(doc_photo, doc_name, 42, "#00d4ff")}
        <div style='flex:1;'>
            <div style='color:white;font-weight:800;'>Dr. {doc_name}</div>
            <div style='color:{ACCENT};font-size:0.75rem;'>● Your Doctor</div>
        </div>
        {"<span style='background:#ff4b4b;color:white;border-radius:20px;"
         "padding:2px 10px;font-size:0.75rem;font-weight:800;'>"
         f"{unread} new</span>" if unread > 0 else ""}
    </div>""", unsafe_allow_html=True)

    html = (f"<div style='height:300px;overflow-y:auto;padding:8px 4px;"
            f"display:flex;flex-direction:column;gap:5px;' id='pc_{prefix}'>")
    for m in messages:
        mine   = m["sender_id"] == my_id
        bg     = "#1a4a2a" if mine else "#0d1b2a"
        align  = "flex-end" if mine else "flex-start"
        radius = "14px 14px 4px 14px" if mine else "14px 14px 14px 4px"
        viewer_tz = sanitize_timezone((st.session_state.get('user') or {}).get('timezone'))
        zone_lbl = tz_label(viewer_tz)
        ts     = to_ist_str(m["sent_at"], viewer_tz)
        ed     = " ✏️" if m.get("edited") else ""
        tick   = " ✓✓" if mine else ""
        html += (f"<div style='display:flex;justify-content:{align};'>"
                 f"<div style='max-width:72%;background:{bg};"
                 f"border-radius:{radius};padding:8px 12px;"
                 f"border:1px solid #1e3a5a;'>"
                 f"<div style='color:white;font-size:0.9rem;'>{m['message']}</div>"
                 f"<div style='color:#556;font-size:0.68rem;"
                 f"text-align:right;margin-top:2px;'>{ts} {zone_lbl}{ed}{tick}</div>"
                 f"</div></div>")
    html += (f"</div><script>"
             f"var c=document.getElementById('pc_{prefix}');"
             f"if(c)c.scrollTop=c.scrollHeight;</script>")
    st.components.v1.html(html, height=330, scrolling=False)

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
                send_message(my_id, doc_id, txt)
                # Set clear_flag — popped BEFORE widget drawn on next run
                st.session_state[clear_flag] = True
                st.rerun()

    my_msgs = [m for m in messages if m["sender_id"] == my_id]
    if my_msgs:
        with st.expander("⚙️ Unsend / Edit (5-min window)"):
            for m in list(reversed(my_msgs))[:5]:
                mid = m["id"]
                c1, c2, c3 = st.columns([3, 1, 1])
                with c1:
                    prev = m["message"][:55] + (
                        "…" if len(m["message"]) > 55 else "")
                    st.markdown(
                        f"<span style='color:#aaa;font-size:0.82rem;'>"
                        f"[{to_ist_str(m['sent_at'], viewer_tz)} {zone_lbl}] {prev}</span>",
                        unsafe_allow_html=True)
                with c2:
                    if st.button("✏️", key=f"{prefix}_pe_{mid}", help="Edit"):
                        st.session_state[f"{prefix}_pediting_{mid}"] = True
                with c3:
                    if st.button("🗑️", key=f"{prefix}_pu_{mid}", help="Unsend"):
                        ok, info = unsend_message(mid, my_id)
                        (st.success if ok else st.error)(info)
                        if ok:
                            st.rerun()
                if st.session_state.get(f"{prefix}_pediting_{mid}"):
                    et_key = f"{prefix}_petxt_{mid}"
                    if et_key not in st.session_state:
                        st.session_state[et_key] = m["message"]
                    st.text_input("Edit:", key=et_key,
                                  label_visibility="collapsed")
                    s1, s2 = st.columns(2)
                    with s1:
                        if st.button("💾", key=f"{prefix}_pesave_{mid}"):
                            ok, info = edit_message(
                                mid, my_id,
                                st.session_state.get(et_key, ""))
                            (st.success if ok else st.error)(info)
                            st.session_state.pop(
                                f"{prefix}_pediting_{mid}", None)
                            if ok:
                                st.rerun()
                    with s2:
                        if st.button("✖", key=f"{prefix}_pecancel_{mid}"):
                            st.session_state.pop(
                                f"{prefix}_pediting_{mid}", None)
                            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
#  PREDICT
# ══════════════════════════════════════════════════════════════════════════════
def _predict_ui(user, my_id, df, X, y, doctor=None):
    st.markdown(
        "<h2 style='text-align:center;color:#00ff88;'>🔮 Prediction Page</h2>",
        unsafe_allow_html=True)
    st.markdown(
        "<p style='text-align:center;font-size:1rem;color:#aaa;'>"
        "Stress predictions now adapt to the patient's age group so the same vitals are not interpreted the same way for every age." 
        "</p>",
        unsafe_allow_html=True)

    if st.session_state.get("pat_show_result"):
        res = st.session_state.get("pat_stress_result", {})
        level = res.get("level", 0)
        si = STRESS_INFO.get(level, STRESS_INFO[0])
        metrics = res.get("metrics", {})

        col_r, col_i = st.columns([2, 3])
        with col_r:
            st.info("Stress level detected…")
            st.write("Stress score =", str(level))
            if metrics.get("age_group"):
                st.caption(
                    f"Age used: {int(round(metrics.get('age_used', 0)))} years • "
                    f"Group: {metrics.get('age_group')} • Model: {metrics.get('model_scope', 'Global')}"
                )
            desc = si["label"]
            if level <= 1:
                st.success(desc)
            elif level == 2:
                st.warning(desc)
            else:
                st.error(desc)
            st.markdown(
                f"<div style='background:{si['color']}22;border-left:4px solid {si['color']};border-radius:8px;padding:10px 14px;color:{si['color']};'>"
                f"{si['advice']}</div>",
                unsafe_allow_html=True)
            if st.button("🔄 Go Back / Predict Again", key="pat_go_back", type="primary"):
                st.session_state.pop("pat_show_result", None)
                st.session_state.pop("pat_stress_result", None)
                st.rerun()
        with col_i:
            img_path = STRESS_IMGS.get(level, "./images/calm.png")
            if os.path.exists(img_path):
                st.image(img_path, use_container_width=True)
        return

    stored_age = calculate_age_from_dob(user.get("dob"))
    if stored_age is None:
        st.warning("⚠️ Your DOB is missing. Please update it in Profile for age-aware prediction.")
        age = st.slider(
            "Age",
            int(df["Age"].min()), int(df["Age"].max()),
            int(df["Age"].median()), key="ps_age"
        )
    else:
        st.markdown(
            f"<div style='background:#0a1e10;border:1px solid #00ff8844;border-radius:8px;padding:10px 14px;margin-bottom:10px;'>"
            f"<b style='color:#00ff88;'>Patient age locked from DOB:</b> {stored_age} years"
            f"<br><span style='color:#8bcf9f;font-size:0.82rem;'>Predictions will use your registered DOB to select the appropriate age-aware model.</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        age = int(stored_age)

    sth = st.slider("Screen Time Hours",
                    float(df["ScreenTimeHours"].min()), float(df["ScreenTimeHours"].max()),
                    float(df["ScreenTimeHours"].median()), key="ps_sth")
    rr  = st.slider("Respiration Rate",
                    float(df["rr"].min()), float(df["rr"].max()),
                    float(df["rr"].median()), key="ps_rr")
    bt  = st.slider("Body Temperature (°F)",
                    float(df["bt"].min()), float(df["bt"].max()),
                    float(df["bt"].median()), key="ps_bt")
    lm  = st.slider("Limb Movement",
                    float(df["lm"].min()), float(df["lm"].max()),
                    float(df["lm"].median()), key="ps_lm")
    bo  = st.slider("Blood Oxygen (%)",
                    float(df["bo"].min()), float(df["bo"].max()),
                    float(df["bo"].median()), key="ps_bo")
    rem = st.slider("Rapid Eye Movement",
                    float(df["rem"].min()), float(df["rem"].max()),
                    float(df["rem"].median()), key="ps_rem")
    sh  = st.slider("Sleep Hours",
                    float(df["sh"].min()), float(df["sh"].max()),
                    float(df["sh"].median()), step=0.5, key="ps_sh")
    hr  = st.slider("Heart Rate",
                    float(df["hr"].min()), float(df["hr"].max()),
                    float(df["hr"].median()), key="ps_hr")

    if st.button("🔮 Predict", key="pat_do_predict", type="primary", use_container_width=True):
        try:
            features = [
                age,
                st.session_state.ps_sth,
                st.session_state.ps_rr,
                st.session_state.ps_bt,
                st.session_state.ps_lm,
                st.session_state.ps_bo,
                st.session_state.ps_rem,
                st.session_state.ps_sh,
                st.session_state.ps_hr,
            ]
            prediction, metrics, probabilities = predict(X, y, features)
            level = int(prediction[0])
            label = STRESS_INFO.get(level, STRESS_INFO[0])["label"]
            save_prediction(my_id, features, level, label)
            st.session_state.pat_stress_result = {
                "level": level,
                "label": label,
                "metrics": metrics,
                "probabilities": probabilities.tolist() if hasattr(probabilities, 'tolist') else probabilities,
            }
            st.session_state.pat_show_result = True
            if level >= 2 and doctor:
                try:
                    create_stress_alert(my_id, doctor["id"], level, label)
                except Exception:
                    pass
            st.rerun()
        except Exception as e:
            st.error(f"Prediction error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  NOTES
# ══════════════════════════════════════════════════════════════════════════════
def _notes_ui(my_id):
    st.subheader("📓 My Personal Notes")
    COLOR_NAMES = list(NOTE_COLOR_MAP.keys())

    with st.expander("➕ Add New Note"):
        # Clear-flag pattern: pop fields before rendering if flag was set
        _nt_clr = "pat_note_clear_flag"
        if st.session_state.pop(_nt_clr, False):
            st.session_state.pop("pat_nt", None)
            st.session_state.pop("pat_nc", None)
        st.text_input("Title *", key="pat_nt")
        st.text_area("Content *", key="pat_nc", height=100)
        n_color = st.selectbox("Color Theme:", COLOR_NAMES, key="pat_ncol")
        bg_hex  = NOTE_COLOR_MAP[n_color]
        ac_hex  = NOTE_ACCENT_MAP[n_color]
        st.markdown(
            f"<div style='width:100%;height:12px;border-radius:4px;"
            f"background:{bg_hex};border-left:4px solid {ac_hex};'></div>",
            unsafe_allow_html=True)
        if st.button("💾 Save Note", key="pat_save_note", type="primary"):
            t = st.session_state.get("pat_nt","").strip()
            c = st.session_state.get("pat_nc","").strip()
            if t and c:
                add_patient_note(my_id, t, c, n_color)
                st.session_state[_nt_clr] = True
                st.success("✅ Note saved!")
                st.rerun()
            else:
                st.warning("Fill in both title and content.")

    notes = get_patient_notes(my_id)
    if not notes:
        st.info("No notes yet.")
        return

    cols = st.columns(2)
    for i, note in enumerate(notes):
        cn = note.get("color","Ocean Blue")
        if cn.startswith("#"):
            cn = "Ocean Blue"
        bg = NOTE_COLOR_MAP.get(cn, "#1a2a3a")
        ac = NOTE_ACCENT_MAP.get(cn, "#00d4ff")
        nid = note["id"]
        with cols[i % 2]:
            with st.expander(f"📌 {note['title']}"):
                st.markdown(f"""
                <div style='background:{bg};border-left:4px solid {ac};
                            border-radius:8px;padding:12px;margin-bottom:6px;'>
                  <div style='color:{ac};font-size:0.7rem;font-weight:700;'>
                    🎨 {cn} &nbsp;•&nbsp; {to_ist_full(note['created_at'])}
                  </div>
                  <div style='color:white;font-size:0.9rem;
                              white-space:pre-wrap;'>{note['content']}</div>
                </div>""", unsafe_allow_html=True)

                d1, d2 = st.columns(2)
                with d1:
                    if st.button("🗑️ Delete", key=f"pn_del_{nid}"):
                        delete_patient_note(nid)
                        st.rerun()
                with d2:
                    if st.button("✏️ Edit", key=f"pn_edttoggle_{nid}"):
                        st.session_state[f"pn_edit_{nid}"] = True

                if st.session_state.get(f"pn_edit_{nid}"):
                    st.text_input("Title", value=note["title"],
                                  key=f"pn_et_{nid}")
                    st.text_area("Content", value=note["content"],
                                 key=f"pn_ec_{nid}", height=80)
                    idx = COLOR_NAMES.index(cn) if cn in COLOR_NAMES else 0
                    st.selectbox("Color", COLOR_NAMES,
                                 index=idx, key=f"pn_ecol_{nid}")
                    s1, s2 = st.columns(2)
                    with s1:
                        if st.button("💾 Save", key=f"pn_esave_{nid}"):
                            update_patient_note(
                                nid,
                                st.session_state.get(f"pn_et_{nid}",""),
                                st.session_state.get(f"pn_ec_{nid}",""),
                                st.session_state.get(f"pn_ecol_{nid}", cn))
                            st.session_state.pop(f"pn_edit_{nid}", None)
                            st.rerun()
                    with s2:
                        if st.button("✖ Cancel", key=f"pn_ecancel_{nid}"):
                            st.session_state.pop(f"pn_edit_{nid}", None)
                            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
#  PROFILE
# ══════════════════════════════════════════════════════════════════════════════
def _profile_section(user):
    uid = user["id"]

    def _dob_for_input(raw_value):
        if not raw_value:
            return date(2000, 1, 1)
        try:
            return datetime.strptime(str(raw_value)[:10], "%Y-%m-%d").date()
        except Exception:
            return date(2000, 1, 1)

    col_p, col_f = st.columns([1, 2])
    with col_p:
        st.markdown("**Profile Photo**")
        photo = user.get("profile_photo")
        if photo:
            st.markdown(
                f"<img src='{photo}' style='width:120px;height:120px;object-fit:cover;border-radius:50%;border:3px solid {ACCENT};'>",
                unsafe_allow_html=True)
            if st.button("🗑️ Delete Photo", key="pat_del_photo"):
                delete_profile_photo(uid)
                st.session_state.user = get_user_by_id(uid)
                st.rerun()
        else:
            st.markdown(
                f"<div style='width:120px;height:120px;border-radius:50%;background:{ACCENT}22;border:3px solid {ACCENT};display:flex;align-items:center;justify-content:center;font-size:3rem;'>👤</div>",
                unsafe_allow_html=True)
        upf = st.file_uploader("Upload", type=["jpg","jpeg","png","webp"], key="pat_upf")
        if upf and st.button("📤 Upload Photo", key="pat_do_up"):
            update_profile_photo(uid, upf.read(), upf.type or "image/png")
            st.session_state.user = get_user_by_id(uid)
            st.success("✅ Photo updated!")
            st.rerun()

    with col_f:
        st.text_input("Full Name", value=user.get("full_name", ""), key="pat_pf_name")
        st.text_input("Email", value=user.get("email", ""), key="pat_pf_email")
        st.text_input("Phone", value=user.get("phone", ""), key="pat_pf_phone")
        st.date_input(
            "Date of Birth",
            value=_dob_for_input(user.get("dob")),
            min_value=date(1900, 1, 1),
            max_value=date.today(),
            key="pat_pf_dob",
            help="DOB drives age-aware stress prediction.",
        )
        detected_age = calculate_age_from_dob(st.session_state.get("pat_pf_dob"))
        if detected_age is not None:
            st.caption(f"Current age from DOB: {detected_age} years")
        current_tz = sanitize_timezone(user.get("timezone"))
        tz_options = COMMON_TIMEZONES if current_tz in COMMON_TIMEZONES else [current_tz] + COMMON_TIMEZONES
        st.selectbox(
            "Preferred Timezone",
            tz_options,
            index=tz_options.index(current_tz),
            format_func=lambda x: f"{tz_label(x)} ({x})",
            key="pat_pf_timezone",
        )
        st.text_area("Bio", value=user.get("bio", ""), key="pat_pf_bio", height=80)
        if st.button("💾 Save Profile", key="pat_save_pf", type="primary"):
            update_user_profile(
                uid,
                st.session_state.get("pat_pf_name"),
                st.session_state.get("pat_pf_email"),
                st.session_state.get("pat_pf_phone"),
                st.session_state.get("pat_pf_dob"),
                timezone=st.session_state.get("pat_pf_timezone"),
            )
            update_bio(uid, st.session_state.get("pat_pf_bio", ""))
            st.session_state.user = get_user_by_id(uid)
            st.success("✅ Saved!")
            st.rerun()

        st.markdown("---")
        st.markdown("**Change Password**")
        st.text_input("Current Password", type="password", key="pat_old_pw")
        st.text_input("New Password", type="password", key="pat_np1")
        st.text_input("Confirm New", type="password", key="pat_np2")
        if st.button("🔒 Change Password", key="pat_chg_pw"):
            old = st.session_state.get("pat_old_pw", "")
            n1 = st.session_state.get("pat_np1", "")
            n2 = st.session_state.get("pat_np2", "")
            if authenticate_user(user["username"], old, role_filter="patient"):
                if n1 == n2 and len(n1) >= 6:
                    change_password(uid, n1)
                    st.success("✅ Password changed!")
                else:
                    st.error("Passwords don't match or too short.")
            else:
                st.error("Current password incorrect.")


# ══════════════════════════════════════════════════════════════════════════════
#  DOWNLOAD helper  — PDF
# ══════════════════════════════════════════════════════════════════════════════
def _download_my_report_pdf(my_id, user, doctor):
    """Provide a PDF download button for own stress history."""
    preds = get_predictions_by_patient(my_id)
    if not preds:
        st.info("No predictions yet to download.")
        return
    checklist = get_checklist_for_patient(my_id)
    try:
        pdf_bytes = generate_patient_report_pdf(
            patient=user,
            doctor=doctor,
            preds=preds,
            doc_notes=[],      # patient does not see raw doc notes in their PDF
            checklist=checklist,
            for_patient=True,
            timezone_name=sanitize_timezone(user.get("timezone") or (doctor or {}).get("timezone")),
        )
        fname = f"{user.get('full_name','Patient').replace(' ','_')}_stress_report.pdf"
        st.download_button(
            label="⬇️ Download My Stress Report (PDF)",
            data=pdf_bytes,
            file_name=fname,
            mime="application/pdf",
            key="pat_dl_report_pdf",
            use_container_width=True)
    except Exception as e:
        st.error(f"PDF error: {e}")
        # fallback CSV
        _csv_cols = [c for c in [
            "stress_label","stress_level","Age","ScreenTimeHours",
            "rr","bt","lm","bo","rem","sh","hr","predicted_at"
            ] if c in pd.DataFrame(preds).columns]
        df = pd.DataFrame(preds)[_csv_cols]
        buf = io.StringIO(); df.to_csv(buf, index=False)
        st.download_button(
            label="⬇️ Download My Report (CSV)",
            data=buf.getvalue(),
            file_name=f"{user.get('full_name','').replace(' ','_')}_report.csv",
            mime="text/csv",
            key="pat_dl_report_csv")


# ══════════════════════════════════════════════════════════════════════════════
#  MY DOCTOR VIEW  (patient sees doctor portfolio)
# ══════════════════════════════════════════════════════════════════════════════
def _my_doctor_ui(doctor):
    if not doctor:
        st.markdown(
            "<div style='background:#0d1b2a;border-radius:12px;"
            "padding:24px;text-align:center;'>"
            "<div style='font-size:2rem;'>🩺</div>"
            "<div style='color:#aaa;font-weight:700;margin-top:8px;'>"
            "No doctor has been assigned to you yet.<br/>"
            "<span style='color:#778;font-size:0.85rem;'>Contact admin to get assigned.</span>"
            "</div></div>",
            unsafe_allow_html=True)
        return

    did  = doctor["id"]
    port = get_doctor_portfolio(did)

    # Header card
    spec = port.get("specialization", "") or "General Practitioner"
    st.markdown(f"""
    <div style='background:linear-gradient(135deg,#0a1628,#0d2035);
                border:1px solid #00d4ff44;border-radius:16px;
                padding:20px 24px;margin-bottom:16px;'>
        <div style='display:flex;align-items:center;gap:16px;'>
            <div style='font-size:3.5rem;'>🩺</div>
            <div>
                <div style='font-size:1.4rem;font-weight:900;color:#00d4ff;'>
                    Dr. {doctor.get('full_name','—')}</div>
                <div style='color:#00ff88;font-weight:600;font-size:0.9rem;'>
                    {spec}</div>
                <div style='color:#aaa;font-size:0.82rem;margin-top:3px;'>
                    📧 {doctor.get('email','—')}</div>
            </div>
        </div>
    </div>""", unsafe_allow_html=True)

    if not port:
        st.info("Doctor has not filled in their portfolio yet.")
        return

    # Two-column info grid
    info_items = [
        ("🎓", "Qualification",    port.get("qualification","—") or "—"),
        ("⏳", "Experience",       f"{port.get('experience_yrs',0)} year(s)"),
        ("🏥", "Hospital/Clinic",  port.get("hospital","—") or "—"),
        ("🌐", "Languages",        port.get("languages","—") or "—"),
        ("💰", "Consultation Fee", port.get("consultation_fee","—") or "—"),
        ("🗓️","Availability",     port.get("availability","—") or "—"),
        ("📱", "Phone",            doctor.get("phone","—") or "—"),
    ]
    c1, c2 = st.columns(2)
    for idx, (icon, lbl, val) in enumerate(info_items):
        with (c1 if idx % 2 == 0 else c2):
            st.markdown(
                f"<div style='background:#0a1e30;border-radius:8px;"
                f"padding:10px 14px;margin-bottom:8px;'>"
                f"<div style='color:#778;font-size:0.78rem;'>{icon} {lbl}</div>"
                f"<div style='color:white;font-weight:700;font-size:0.92rem;'>{val}</div>"
                f"</div>",
                unsafe_allow_html=True)

    about = port.get("about", "")
    if about:
        st.markdown("**ℹ️ About**")
        st.markdown(
            f"<div style='background:#0a1e30;border-left:4px solid #00d4ff;"
            f"border-radius:8px;padding:12px 16px;color:#ddd;'>"
            f"{about}</div>",
            unsafe_allow_html=True)

    achiev = port.get("achievements", "")
    if achiev:
        st.markdown("**🏆 Achievements**")
        st.markdown(
            f"<div style='background:#0a1e30;border-left:4px solid #00ff88;"
            f"border-radius:8px;padding:12px 16px;color:#ddd;'>"
            f"{achiev}</div>",
            unsafe_allow_html=True)

    # PDF Portfolio download (if admin uploaded one)
    pdf_port = get_doctor_portfolio_pdf(did)
    if pdf_port and pdf_port.get("pdf_data"):
        import base64 as _b64
        st.markdown("---")
        st.markdown("**📄 Doctor's Portfolio PDF**")
        raw_pdf = _b64.b64decode(pdf_port["pdf_data"])
        st.download_button(
            f"⬇️ Download Dr. {doctor.get('full_name','')} — Portfolio PDF",
            data=raw_pdf,
            file_name=pdf_port.get("filename", "portfolio.pdf"),
            mime="application/pdf",
            key="pat_doc_portfolio_pdf_dl")


def _updates_bell(user_id: int, upd_count: int = 0):
    """Bell icon in header that highlights when there are pending updates."""
    if upd_count > 0:
        label = f"🔔 {upd_count}"
        help_txt = f"{upd_count} update(s) need your attention"
    else:
        label = "🔔"
        help_txt = "No pending updates"
    if st.button(label, key=f"pat_updates_bell_{user_id}",
                 help=help_txt, use_container_width=True):
        st.session_state["nav_override"] = "👤 My Dashboard"
        # Also set a flag to auto-open the Updates tab inside the dashboard
        st.session_state["pat_open_updates_tab"] = True
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN app()
# ══════════════════════════════════════════════════════════════════════════════
def app():
    user   = st.session_state.user
    my_id  = user["id"]
    doctor = get_doctor_of_patient(my_id)

    # ── Inner-tab auto-switch via JS ──────────────────────────────────────────
    _open_tab      = st.session_state.pop("pat_open_updates_tab", False)
    _open_chat_tab = st.session_state.pop("pat_open_chat_tab",    False)

    try:
        df, X, y = load_data()
    except Exception:
        df, X, y = None, None, None

    hdr_left, hdr_right = st.columns([1, 11])
    # Calculate total pending updates for bell
    try:
        from database import get_pending_confirm_count_for_patient as _gcpc
        _bell_appt = _gcpc(my_id)
    except Exception:
        _bell_appt = 0
    _bell_total = get_unread_count(my_id) + _bell_appt
    with hdr_left:
        _updates_bell(my_id, upd_count=_bell_total)
    with hdr_right:
        st.markdown(f"""
        <div style='background:linear-gradient(90deg,#081a12,#0d2018);
                    padding:1.2rem 1.6rem;border-radius:14px;margin-bottom:1.2rem;
                    border-left:5px solid {ACCENT};display:flex;
                    align-items:center;gap:14px;'>
            <div>{avatar_html(user.get("profile_photo"),
                              user.get("full_name","P"), 56, ACCENT)}</div>
            <div>
                <div style='font-size:1.5rem;font-weight:900;color:{ACCENT};'>
                    👤 Patient Dashboard</div>
                <div style='color:#aaa;font-size:0.9rem;'>
                    <b style='color:white;'>{user["full_name"]}</b>
                    &nbsp;|&nbsp;
                    {"🩺 Dr. " + doctor["full_name"] if doctor else
                     "<span style='color:#ff6688;'>No doctor assigned</span>"}
                    &nbsp;|&nbsp; 🌍 {tz_label(sanitize_timezone(user.get("timezone")))}
                </div>
            </div>
        </div>""", unsafe_allow_html=True)

    preds_all = get_predictions_by_patient(my_id)
    notes_all = get_patient_notes(my_id)
    unread    = get_unread_count(my_id)
    c1, c2, c3 = st.columns(3)
    c1.metric("📊 Predictions",  len(preds_all))
    c2.metric("📓 My Notes",     len(notes_all))
    c3.metric("💬 Unread",       unread)

    st.markdown("---")
    # Checklist pending badge
    pending_chk   = get_checklist_pending_count(my_id)
    chk_tab_lbl   = f"📋 Checklist 🔴{pending_chk}" if pending_chk > 0 else "📋 Checklist"
    _chat_unread  = get_unread_count(my_id)
    _chat_tab_lbl = f"💬 Chat 🔴{_chat_unread}" if _chat_unread > 0 else "💬 Chat"

    # Appointment update count (DoctorProposed needing confirmation)
    try:
        from database import get_pending_confirm_count_for_patient
        _appt_pending = get_pending_confirm_count_for_patient(my_id)
    except Exception:
        _appt_pending = 0
    _upd_total    = _chat_unread + _appt_pending
    _upd_tab_lbl  = f"🔔 Updates 🔴{_upd_total}" if _upd_total > 0 else "🔔 Updates"

    (t_pred, t_hist, t_checklist, t_chat,
     t_bot, t_notes, t_dnotes, t_mydr,
     t_appt, t_med, t_updates, t_prof) = st.tabs([
        "🔮 Predict", "📊 History", chk_tab_lbl,
        _chat_tab_lbl, "🤖 Wellness Bot",
        "📓 Notes", "📋 Doctor Notes", "👨‍⚕️ My Doctor",
        "📅 Appointments", "🔬 My Reports", _upd_tab_lbl, "⚙️ Profile"])

    # Auto-click the correct tab when redirected
    _tab_keyword = (
        "Updates" if _open_tab      else
        "Chat"    if _open_chat_tab else
        None
    )
    if _tab_keyword:
        st.markdown(f"""
        <script>
        (function() {{
            const tryClick = (attempts) => {{
                const tabs = window.parent.document.querySelectorAll(
                    '[data-baseweb="tab"]');
                for (const tab of tabs) {{
                    if (tab.innerText && tab.innerText.includes('{_tab_keyword}')) {{
                        tab.click(); return;
                    }}
                }}
                if (attempts > 0) setTimeout(() => tryClick(attempts-1), 150);
            }};
            setTimeout(() => tryClick(8), 200);
        }})();
        </script>""", unsafe_allow_html=True)

    with t_pred:
        if df is not None:
            _predict_ui(user, my_id, df, X, y, doctor=doctor)
        else:
            st.error("Could not load data file. Ensure Stress.csv is present.")

    with t_hist:
        st.subheader("📊 My Prediction History")
        if preds_all:
            df_p = pd.DataFrame(preds_all)[[
                "stress_label","stress_level","predicted_at"
            ]].rename(columns={"stress_label":"Stress",
                               "stress_level":"Score",
                               "predicted_at":"When"})
            st.dataframe(df_p, use_container_width=True)

            # PDF Download button
            _download_my_report_pdf(my_id, user, doctor)

            if len(preds_all) > 1:
                fig, ax = plt.subplots(figsize=(8,3), facecolor="#0d1b2a")
                lvls = [p["stress_level"] for p in reversed(preds_all[-15:])]
                ax.plot(lvls, marker="o", color=ACCENT, linewidth=2,
                        markersize=5)
                ax.fill_between(range(len(lvls)), lvls, alpha=0.12,
                                color=ACCENT)
                ax.set_facecolor("#0d1b2a")
                ax.tick_params(colors="white", labelsize=8)
                for sp in ax.spines.values():
                    sp.set_edgecolor("#2a3a5a")
                ax.set_title("Stress Trend (last 15)",
                             color="white", fontsize=11)
                ax.set_yticks([0,1,2,3,4])
                ax.set_yticklabels(["Safe","Low","Med","High","V.High"],
                                   fontsize=8)
                fig.tight_layout()
                st.pyplot(fig)
                plt.close()
        else:
            st.info("No predictions yet. Go to the Predict tab!")

    with t_checklist:
        _checklist_ui_patient(my_id, key_prefix="chk_main")

    with t_chat:
        all_docs = get_doctors_for_patient(my_id)
        if all_docs:
            _chat_ui(my_id, all_docs[0], prefix="pat_tab", all_doctors=all_docs)
        elif doctor:
            _chat_ui(my_id, doctor, prefix="pat_tab")
        else:
            st.info("💬 No doctor assigned yet. Contact admin.")

    with t_bot:
        _chatbot_ui()

    with t_notes:
        _notes_ui(my_id)

    with t_dnotes:
        st.subheader("📋 Notes from Your Doctor")
        d_notes = get_notes_for_patient(my_id)
        if d_notes:
            for n in d_notes:
                st.markdown(f"""
                <div style='background:#0a1e30;border-left:4px solid #00d4ff;
                            border-radius:8px;padding:12px 14px;
                            margin-bottom:8px;'>
                  <div style='color:#00d4ff;font-size:0.72rem;font-weight:700;'>
                    🩺 Dr. {n["doctor_name"]} &nbsp;•&nbsp;
                    {to_ist_full(n["created_at"])}</div>
                  <div style='color:white;margin-top:6px;'>{n["note"]}</div>
                </div>""", unsafe_allow_html=True)
        else:
            st.info("No notes from your doctor yet.")

    with t_mydr:
        _my_doctor_ui(doctor)

    with t_appt:
        render_patient_appointments(my_id, user)

    with t_med:
        _medical_reports_tab_patient(my_id)

    with t_updates:
        _updates_tab_patient(my_id, doctor)

    with t_prof:
        _profile_section(user)


# ══════════════════════════════════════════════════════════════════════════════
#  UPDATES TAB (Patient)
# ══════════════════════════════════════════════════════════════════════════════
def _updates_tab_patient(my_id: int, doctor):
    """Show all pending actions and notifications for the patient in one place."""
    from database import get_appointments_for_patient

    unread_msgs = get_unread_count(my_id)
    try:
        from database import get_pending_confirm_count_for_patient
        pending_confirms = get_pending_confirm_count_for_patient(my_id)
    except Exception:
        pending_confirms = 0
    pending_chk = get_checklist_pending_count(my_id)

    st.markdown(
        f"<div style='background:linear-gradient(90deg,#081a12,#0d2018);"
        f"border-radius:12px;padding:14px 18px;margin-bottom:16px;"
        f"border-left:5px solid {ACCENT};'>"
        f"<div style='font-size:1.2rem;font-weight:900;color:{ACCENT};'>🔔 Updates & Notifications</div>"
        f"<div style='color:#aaa;font-size:0.82rem;margin-top:3px;'>"
        f"All your pending actions and notifications in one place.</div>"
        f"</div>",
        unsafe_allow_html=True)

    # ── Summary badges ────────────────────────────────────────────────────────
    ub1, ub2, ub3 = st.columns(3)
    with ub1:
        c = "#ff4b4b" if unread_msgs > 0 else "#2ecc71"
        st.markdown(
            f"<div style='background:#0d1b2a;border:1px solid {c}44;"
            f"border-radius:10px;padding:12px 14px;text-align:center;'>"
            f"<div style='font-size:1.5rem;font-weight:900;color:{c};'>{unread_msgs}</div>"
            f"<div style='color:#aaa;font-size:0.8rem;'>Unread Messages</div></div>",
            unsafe_allow_html=True)
    with ub2:
        c = "#aa88ff" if pending_confirms > 0 else "#2ecc71"
        st.markdown(
            f"<div style='background:#0d1b2a;border:1px solid {c}44;"
            f"border-radius:10px;padding:12px 14px;text-align:center;'>"
            f"<div style='font-size:1.5rem;font-weight:900;color:{c};'>{pending_confirms}</div>"
            f"<div style='color:#aaa;font-size:0.8rem;'>Appointments to Confirm</div></div>",
            unsafe_allow_html=True)
    with ub3:
        c = ACCENT if pending_chk > 0 else "#2ecc71"
        st.markdown(
            f"<div style='background:#0d1b2a;border:1px solid {c}44;"
            f"border-radius:10px;padding:12px 14px;text-align:center;'>"
            f"<div style='font-size:1.5rem;font-weight:900;color:{c};'>{pending_chk}</div>"
            f"<div style='color:#aaa;font-size:0.8rem;'>Checklist Pending</div></div>",
            unsafe_allow_html=True)

    st.markdown("---")

    upd_t1, upd_t2, upd_t3 = st.tabs([
        f"💬 Messages {'🔴' + str(unread_msgs) if unread_msgs > 0 else ''}",
        f"📅 Appointment Updates {'🔴' + str(pending_confirms) if pending_confirms > 0 else ''}",
        f"📋 Checklist {'🔴' + str(pending_chk) if pending_chk > 0 else ''}",
    ])

    with upd_t1:
        if unread_msgs == 0:
            st.markdown(
                "<div style='background:#0d1b2a;border-radius:12px;padding:24px;text-align:center;'>"
                "<div style='font-size:2rem;'>✅</div>"
                "<div style='color:#00ff88;font-weight:700;margin-top:8px;'>No unread messages!</div>"
                "</div>", unsafe_allow_html=True)
        else:
            if doctor:
                unread_from_doc = get_unread_count(my_id, doctor["id"])
                if unread_from_doc > 0:
                    st.markdown(
                        f"<div style='background:#0a1628;border-left:4px solid #ff4b4b;"
                        f"border-radius:10px;padding:12px 16px;margin-bottom:8px;"
                        f"display:flex;align-items:center;justify-content:space-between;'>"
                        f"<div>"
                        f"<div style='color:white;font-weight:800;'>🩺 Dr. {doctor['full_name']}</div>"
                        f"<div style='color:#aaa;font-size:0.8rem;'>Your assigned doctor</div>"
                        f"</div>"
                        f"<span style='background:#ff4b4b;color:white;border-radius:20px;"
                        f"padding:3px 12px;font-size:0.85rem;font-weight:800;'>"
                        f"💬 {unread_from_doc} new</span>"
                        f"</div>", unsafe_allow_html=True)
            else:
                st.info(f"You have {unread_msgs} unread message(s). Go to the Chat tab to read them.")

    with upd_t2:
        try:
            appts = get_appointments_for_patient(my_id)
            proposed = [a for a in appts if a.get("status") == "DoctorProposed"]
            if not proposed:
                st.markdown(
                    "<div style='background:#0d1b2a;border-radius:12px;padding:24px;text-align:center;'>"
                    "<div style='font-size:2rem;'>✅</div>"
                    "<div style='color:#00ff88;font-weight:700;margin-top:8px;'>"
                    "No appointment changes need your confirmation!</div></div>",
                    unsafe_allow_html=True)
            else:
                for a in proposed:
                    aid = a["id"]
                    st.markdown(
                        f"<div style='background:#1a0a2a;border:1px solid #aa88ff44;"
                        f"border-left:4px solid #aa88ff;border-radius:10px;"
                        f"padding:14px 18px;margin-bottom:10px;'>"
                        f"<div style='color:white;font-weight:800;font-size:1rem;'>"
                        f"APT-{aid:05d} <span style='background:#aa88ff;color:#000;"
                        f"border-radius:6px;padding:1px 8px;font-size:0.72rem;margin-left:8px;'>"
                        f"📝 Needs Confirmation</span></div>"
                        f"<div style='color:#aaa;font-size:0.85rem;margin-top:6px;'>"
                        f"🩺 Dr. {a.get('doctor_name','—')}</div>"
                        f"<div style='margin-top:6px;color:#778;font-size:0.82rem;'>Original: "
                        f"<span style='color:#ff6688;'>{a.get('appt_date','—')} {a.get('appt_time','—')}</span></div>"
                        f"<div style='color:#aa88ff;font-weight:700;font-size:1rem;'>"
                        f"📅 Proposed: {a.get('proposed_date','—')} 🕐 {a.get('proposed_time','—')}</div>"
                        f"</div>", unsafe_allow_html=True)
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("✅ Confirm", key=f"upd_confirm_{aid}",
                                     type="primary", use_container_width=True):
                            try:
                                from database import patient_confirm_proposed
                                ok, msg = patient_confirm_proposed(aid, my_id)
                                if ok:
                                    st.success("✅ Confirmed!")
                                    st.rerun()
                                else:
                                    st.error(msg)
                            except Exception as e:
                                st.error(str(e))
                    with c2:
                        if st.button("❌ Decline", key=f"upd_decline_{aid}",
                                     use_container_width=True):
                            try:
                                from database import patient_decline_proposed
                                ok, msg = patient_decline_proposed(aid, my_id, "Patient declined")
                                if ok:
                                    st.warning("Declined.")
                                    st.rerun()
                                else:
                                    st.error(msg)
                            except Exception as e:
                                st.error(str(e))
        except Exception as e:
            st.warning(f"Could not load appointment updates: {e}")

    with upd_t3:
        _checklist_ui_patient(my_id, key_prefix="chk_updates")


def app_chat():
    """Sidebar nav → Chat."""
    user   = st.session_state.user
    my_id  = user["id"]
    doctor = get_doctor_of_patient(my_id)

    st.markdown(f"""
    <div style='background:linear-gradient(90deg,#081a12,#0d2018);
                padding:1rem 1.4rem;border-radius:14px;margin-bottom:1rem;
                border-left:5px solid {ACCENT};'>
        <div style='font-size:1.3rem;font-weight:900;color:{ACCENT};'>
            💬 Live Chat</div>
        <div style='color:#aaa;font-size:0.85rem;'>
            Real-time messaging with your doctor</div>
    </div>""", unsafe_allow_html=True)

    all_docs = get_doctors_for_patient(my_id)
    if all_docs:
        _chat_ui(my_id, all_docs[0], prefix="pat_side", all_doctors=all_docs)
    elif doctor:
        _chat_ui(my_id, doctor, prefix="pat_side")
    else:
        st.info("💬 No doctor assigned yet.")

# ══════════════════════════════════════════════════════════════════════════════
#  APPOINTMENTS (Patient side)
# ══════════════════════════════════════════════════════════════════════════════
def _appointments_tab_patient(patient_id, doctor, user):
    st.subheader("📅 Book & Manage Appointments")

    appts = get_appointments_for_patient(patient_id)

    # Sub-tabs
    t_book, t_all, t_pending, t_done = st.tabs(
        ["📝 Book New", "📋 All", "⏳ Pending", "✅ Completed"])

    # ── BOOK ──────────────────────────────────────────────────────────────────
    with t_book:
        if not doctor:
            st.warning("⚠️ No doctor assigned. Contact admin to get a doctor assigned first.")
            return

        st.markdown(f"""
        <div style='background:#0a1e30;border:1px solid #00ff8844;
                    border-radius:12px;padding:14px 18px;margin-bottom:12px;'>
            <div style='color:#00ff88;font-weight:800;'>Book Physical Appointment</div>
            <div style='color:#aaa;font-size:0.85rem;margin-top:3px;'>
                With Dr. <b style='color:white;'>{doctor['full_name']}</b>
            </div>
        </div>""", unsafe_allow_html=True)

        import datetime as _dt
        today = _dt.date.today()
        min_date = today + _dt.timedelta(days=1)

        b1, b2 = st.columns(2)
        with b1:
            appt_date = st.date_input("📅 Appointment Date",
                                       value=min_date,
                                       min_value=min_date,
                                       key="pat_appt_date")
        with b2:
            appt_time = st.time_input("🕐 Appointment Time",
                                       value=_dt.time(10, 0),
                                       step=1800,
                                       key="pat_appt_time")

        reason = st.text_area("📝 Reason / Notes (optional)",
                               key="pat_appt_reason",
                               height=70,
                               placeholder="Describe your symptoms or reason for visit…")

        st.markdown("### 💳 Payment Details")
        pay_mode = st.selectbox("Payment Mode",
                                 ["Online — UPI", "Online — Credit/Debit Card",
                                  "Online — Net Banking", "Cash (On Visit)"],
                                 key="pat_appt_paymode")

        pay_ref = ""
        if "Online" in pay_mode:
            pay_ref = st.text_input("Transaction Reference / UTR No.",
                                     key="pat_appt_ref",
                                     placeholder="Enter transaction ID…")

        pay_fee = ""
        port = get_doctor_portfolio(doctor["id"])
        if port and port.get("consultation_fee"):
            fee_val = port["consultation_fee"]
            st.markdown(
                f"<div style='background:#0d1b2a;border-left:3px solid #00d4ff;"
                f"border-radius:6px;padding:8px 12px;margin:6px 0;'>"
                f"<span style='color:#778;'>💰 Consultation Fee: </span>"
                f"<span style='color:#00d4ff;font-weight:700;'>{fee_val}</span>"
                f"</div>", unsafe_allow_html=True)

        if st.button("📅 Book Appointment", key="pat_appt_book_btn",
                     type="primary", use_container_width=True):
            if "Online" in pay_mode and not pay_ref.strip():
                st.error("❌ Please provide a transaction reference for online payment.")
            else:
                date_str = str(appt_date)
                time_str = appt_time.strftime("%H:%M")
                pay_status = "Paid" if "Online" in pay_mode else "Cash"
                ok, result = book_appointment(
                    patient_id, doctor["id"],
                    date_str, time_str,
                    reason=reason,
                    payment_mode=pay_mode,
                    payment_ref=pay_ref.strip(),
                    payment_status=pay_status)
                if ok:
                    st.balloons()
                    st.success(f"✅ Appointment booked! (ID: APT-{result:05d})")
                    # Generate and show slip download
                    appt_detail = {
                        "id": result,
                        "appt_date": date_str,
                        "appt_time": time_str,
                        "reason": reason,
                        "payment_mode": pay_mode,
                        "payment_ref": pay_ref.strip(),
                        "payment_status": pay_status,
                        "status": "Pending",
                    }
                    try:
                        slip_pdf = generate_appointment_slip_pdf(
                            appt_detail, user, doctor)
                        st.download_button(
                            "⬇️ Download Appointment Slip PDF",
                            data=slip_pdf,
                            file_name=f"appointment_slip_APT{result:05d}.pdf",
                            mime="application/pdf",
                            key="pat_appt_slip_dl")
                    except Exception as slip_err:
                        st.warning(f"Slip generation issue: {slip_err}")
                    st.rerun()
                else:
                    st.error(f"❌ {result}")

    def _appt_row(a):
        status  = a.get("status", "Pending")
        appt_id = a.get("id")
        STATUS_COLORS = {
            "Pending":        ("#f1c40f", "#1a1500"),
            "Confirmed":      ("#2ecc71", "#0a1a0a"),
            "DoctorProposed": ("#aa88ff", "#1a0a2a"),
            "Rescheduled":    ("#ffaa44", "#1a1200"),
            "Completed":      ("#00d4ff", "#0a1628"),
            "Cancelled":      ("#ff4b4b", "#1a0505"),
            "Rejected":       ("#ff4b4b", "#1a0505"),
        }
        ac, bg  = STATUS_COLORS.get(status, ("#778899", "#0d1b2a"))
        # Extract all values before HTML build — no dict access inside HTML
        appt_date  = a.get("appt_date", "—")
        appt_time  = a.get("appt_time", "—")
        doc_name   = a.get("doctor_name", "—")
        reason_txt = a.get("reason", "—") or "—"
        pay_mode   = a.get("payment_mode", "—")
        pay_stat   = a.get("payment_status", "—")
        pay_ref    = a.get("payment_ref", "—") or "—"
        appt_id_str = f"APT-{appt_id:05d}" if isinstance(appt_id, int) else str(appt_id)

        # Proposed slot info
        prop_date = a.get("proposed_date", "")
        prop_time = a.get("proposed_time", "")
        prop_html = ""
        if status == "DoctorProposed" and prop_date:
            prop_html = (
                "<div style='background:#2a1040;border-radius:6px;"
                "padding:3px 10px;margin-top:5px;display:inline-block;"
                "color:#aa88ff;font-size:0.78rem;'>"
                "&#128221; Proposed: <b>" + str(prop_date) + " at " + str(prop_time) + "</b>"
                " &mdash; awaiting your confirmation"
                "</div>")

        card = (
            "<div style='background:" + bg + ";border-left:4px solid " + ac + ";"
            "border-radius:10px;padding:12px 16px;margin-bottom:8px;'>"
            "<div style='color:white;font-weight:700;'>"
            + appt_id_str +
            "<span style='background:" + ac + ";color:#000;border-radius:6px;"
            "padding:1px 7px;font-size:0.72rem;margin-left:8px;'>" + status + "</span>"
            "</div>"
            "<div style='color:#aaa;font-size:0.82rem;margin-top:3px;'>"
            "&#128197; " + str(appt_date) + " &nbsp;&#128336; " + str(appt_time) +
            " &nbsp;&nbsp;&#129514; Dr. " + str(doc_name) +
            "</div>"
            "<div style='color:#778;font-size:0.78rem;'>"
            "&#128221; " + reason_txt +
            " &nbsp;|&nbsp; &#128179; " + pay_mode +
            " (" + pay_stat + ") Ref: " + pay_ref +
            "</div>"
            + prop_html +
            "</div>"
        )
        st.markdown(card, unsafe_allow_html=True)

        # Confirm / Decline for DoctorProposed
        if status == "DoctorProposed" and prop_date:
            cc1, cc2, _cc3 = st.columns([1, 1, 3])
            with cc1:
                if st.button("✅ Confirm", key=f"pat_confirm_{appt_id}",
                             use_container_width=True, type="primary"):
                    try:
                        from database import patient_confirm_proposed
                        ok, msg = patient_confirm_proposed(appt_id, my_id)
                        if ok: st.success("Appointment confirmed!"); st.rerun()
                        else:  st.error(msg)
                    except Exception as e:
                        st.error(str(e))
            with cc2:
                if st.button("❌ Decline", key=f"pat_decline_{appt_id}",
                             use_container_width=True):
                    try:
                        from database import patient_decline_proposed
                        ok, msg = patient_decline_proposed(appt_id, my_id, "Patient declined")
                        if ok: st.warning("Proposal declined."); st.rerun()
                        else:  st.error(msg)
                    except Exception as e:
                        st.error(str(e))

        # Download slip — no timezone_name in PDF (IST shown without label)
        try:
            slip_pdf = generate_appointment_slip_pdf(a, user, doctor or {})
            is_updated = status in ("DoctorProposed", "Rescheduled", "Confirmed") and prop_date
            lbl = f"⬇️ Download {'Updated ' if is_updated else ''}Slip ({appt_id_str})"
            st.download_button(lbl, data=slip_pdf,
                               file_name=f"slip_{appt_id_str}.pdf",
                               mime="application/pdf",
                               key=f"pat_slip_{appt_id}")
        except Exception:
            pass

    with t_all:
        if not appts:
            st.info("No appointments yet.")
        else:
            for a in appts:
                _appt_row(a)

    with t_pending:
        pending = [a for a in appts if a.get("status") == "Pending"]
        if not pending:
            st.info("No pending appointments.")
        else:
            for a in pending:
                _appt_row(a)

    with t_done:
        done = [a for a in appts if a.get("status") == "Completed"]
        if not done:
            st.info("No completed appointments yet.")
        else:
            for a in done:
                _appt_row(a)


# ══════════════════════════════════════════════════════════════════════════════
#  MEDICAL REPORTS (Patient side — upload + view)
# ══════════════════════════════════════════════════════════════════════════════
def _medical_reports_tab_patient(patient_id):
    st.subheader("🔬 My Medical Reports")
    st.markdown(
        "<div style='background:#081a12;border:1px solid #00ff8844;"
        "border-radius:10px;padding:10px 14px;margin-bottom:12px;'>"
        "<b style='color:#00ff88;'>📂 Upload & Share Reports</b>"
        "<span style='color:#aaa;font-size:0.85rem;'> — Upload your medical "
        "reports for your doctor to review and analyze.</span></div>",
        unsafe_allow_html=True)

    # Upload section
    with st.expander("📤 Upload New Medical Report", expanded=True):
        up_file = st.file_uploader(
            "Choose file (PDF, JPG, PNG, DOCX…)",
            type=["pdf", "jpg", "jpeg", "png", "docx", "doc", "txt"],
            key="pat_mr_upload")
        if up_file and st.button("📤 Upload Report",
                                  key="pat_mr_upload_btn",
                                  type="primary"):
            try:
                save_medical_report(
                    patient_id,
                    up_file.name,
                    up_file.read(),
                    up_file.type or "application/octet-stream")
                st.success(f"✅ Report '{up_file.name}' uploaded successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Upload failed: {e}")

    st.markdown("---")
    st.markdown("**📋 My Uploaded Reports**")

    reports = get_medical_reports_for_patient(patient_id)
    if not reports:
        st.info("No reports uploaded yet.")
        return

    for r in reports:
        rid      = r["id"]
        fname    = r.get("filename", "report")
        ftype    = r.get("file_type", "")
        analysis = r.get("analysis", "") or ""
        tz_name = sanitize_timezone((st.session_state.get('user') or {}).get('timezone'))
        upl_at   = format_db_timestamp(r.get("uploaded_at",""), tz_name)

        with st.expander(f"📄 {fname}  ({upl_at})"):
            # Download
            full = get_medical_report_data(rid)
            if full and full.get("file_data"):
                import base64 as _b64
                raw = _b64.b64decode(full["file_data"])
                st.download_button(
                    f"⬇️ Download {fname}",
                    data=raw,
                    file_name=fname,
                    mime=ftype or "application/octet-stream",
                    key=f"pat_mr_dl_{rid}")
                st.caption(f"Size: {len(raw)/1024:.1f} KB")

            if analysis:
                st.markdown(
                    f"<div style='background:#0a1e30;border-left:4px solid #00d4ff;"
                    f"border-radius:8px;padding:10px 14px;margin-top:6px;'>"
                    f"<div style='color:#00d4ff;font-weight:700;font-size:0.82rem;'>"
                    f"🩺 Doctor's Analysis:</div>"
                    f"<div style='color:white;margin-top:4px;'>{analysis}</div>"
                    f"</div>", unsafe_allow_html=True)
            else:
                st.markdown(
                    "<div style='color:#556;font-size:0.82rem;margin-top:6px;'>"
                    "⏳ Awaiting doctor review…</div>",
                    unsafe_allow_html=True)

            # Delete
            if st.button("🗑️ Delete Report", key=f"pat_mr_del_{rid}"):
                delete_medical_report(rid)
                st.success("Report deleted.")
                st.rerun()