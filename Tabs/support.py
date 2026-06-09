"""
support.py  –  Quick Help (Patient Panel) / Support Resources
"""
import streamlit as st

def app():
    st.markdown("""
    <div style='background:linear-gradient(90deg,#0a1e30,#0d2040);
                padding:1.2rem 1.6rem;border-radius:14px;margin-bottom:1.2rem;
                border-left:5px solid #00ff88;'>
        <div style='font-size:1.5rem;font-weight:900;color:#00ff88;'>
            🆘 Quick Help</div>
        <div style='color:#aaa;font-size:0.9rem;'>
            Mental health resources, helplines & stress-relief tips</div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div style='background:#0d1b2a;border:1px solid #00ff8844;border-radius:12px;
                    padding:16px;margin-bottom:12px;'>
            <div style='color:#00ff88;font-weight:800;font-size:1rem;margin-bottom:10px;'>
                📞 Mental Health Helplines (India)
            </div>
        """, unsafe_allow_html=True)

        helplines = [
            ("🟢", "Vandrevala Foundation", "9999 666 555", "24/7 free counseling"),
            ("🔵", "Tele-MANAS (Govt.)",    "14416",        "Free, 20+ languages"),
            ("🟡", "iCall by TISS",          "9152 987 821", "Mon–Sat 8am–10pm"),
            ("🔴", "AASRA",                  "9820 466 626", "Suicide prevention, 24/7"),
            ("🟠", "Roshni Trust",           "8142 020 033", "Mon–Sat 9am–8pm"),
            ("🟣", "Sumaitri",               "9315 767 849", "Mon–Fri 12:30–5pm"),
            ("⚪", "iMind",                  "9048059555",   "Mental health support"),
        ]
        for dot, name, number, hours in helplines:
            st.markdown(f"""
            <div style='background:#0a1a2a;border-radius:8px;padding:10px 12px;
                        margin-bottom:6px;border-left:3px solid #00ff88;'>
                <div style='display:flex;justify-content:space-between;align-items:center;'>
                    <div>
                        <span style='color:white;font-weight:700;font-size:0.9rem;'>{dot} {name}</span>
                        <div style='color:#778;font-size:0.75rem;margin-top:2px;'>{hours}</div>
                    </div>
                    <div style='color:#00ff88;font-weight:800;font-size:0.9rem;'>{number}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div style='background:#0d1b2a;border:1px solid #00d4ff44;border-radius:12px;
                    padding:16px;margin-bottom:12px;'>
            <div style='color:#00d4ff;font-weight:800;font-size:1rem;margin-bottom:10px;'>
                💡 Quick Stress-Relief Techniques
            </div>
        """, unsafe_allow_html=True)

        tips = [
            ("🫁", "Box Breathing",        "Inhale 4s → Hold 4s → Exhale 4s → Hold 4s. Repeat 4 times."),
            ("🧘", "5-4-3-2-1 Grounding", "Name 5 things you see, 4 touch, 3 hear, 2 smell, 1 taste."),
            ("🚶", "Walk It Out",           "A 10-minute walk releases endorphins and clears the mind."),
            ("📝", "Journaling",            "Write 3 things you're grateful for each morning."),
            ("💤", "Sleep Hygiene",         "Keep consistent bedtimes, no screens 1hr before sleep."),
            ("🎵", "Music Therapy",         "Listen to calm music — it lowers cortisol by up to 66%."),
            ("🍵", "Hydrate & Nourish",     "Drink water, eat balanced meals. Stress depletes nutrients."),
        ]
        for icon, title, desc in tips:
            st.markdown(f"""
            <div style='background:#0a1a2a;border-radius:8px;padding:10px 12px;
                        margin-bottom:6px;border-left:3px solid #00d4ff;'>
                <div style='color:white;font-weight:700;font-size:0.88rem;'>{icon} {title}</div>
                <div style='color:#aaa;font-size:0.78rem;margin-top:3px;'>{desc}</div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # Emergency banner
    st.markdown("""
    <div style='background:#1a0505;border:1px solid #ff4b4b55;border-radius:12px;
                padding:14px 18px;margin-top:8px;text-align:center;'>
        <div style='color:#ff4b4b;font-weight:800;font-size:1rem;'>
            🚨 In Crisis? You are not alone.</div>
        <div style='color:#aaa;font-size:0.85rem;margin-top:4px;'>
            Please call <b style='color:white;'>iCall: 9152987821</b> or
            <b style='color:white;'>Vandrevala: 9999666555</b> immediately.
            Professional help is available 24/7, free and confidential.
        </div>
    </div>
    """, unsafe_allow_html=True)
