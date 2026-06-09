import streamlit as st

from web_functions import (
    CLASS_LABELS,
    compute_model_performance,
    dataset_profile,
    performance_metric_cards,
    plot_classwise_metrics,
    plot_confusion_matrix,
    plot_learning_curves,
    plot_precision_recall_curve,
    plot_roc_curve,
    plot_support_distribution,
)


ACCENT = "#6ee7f9"
GREEN = "#34d399"
RED = "#fb7185"
BG = "#050816"
CARD = "rgba(13, 20, 36, 0.78)"
BORDER = "rgba(148, 163, 184, 0.16)"


def _inject_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Sora:wght@600;700;800&display=swap');

        html, body, [class*="css"] {font-family:'Inter', sans-serif;}
        .stApp {
            background:
                radial-gradient(circle at 15% 15%, rgba(56,189,248,0.18), transparent 26%),
                radial-gradient(circle at 85% 18%, rgba(52,211,153,0.12), transparent 24%),
                radial-gradient(circle at 50% 70%, rgba(129,140,248,0.10), transparent 25%),
                linear-gradient(180deg, #040814 0%, #071120 48%, #050913 100%);
            color: #edf2f7;
        }

        header[data-testid="stHeader"] {display:none;}
        section[data-testid="stSidebar"] {display:none !important;}
        button[data-testid="collapsedControl"], [data-testid="collapsedControl"] {
            display: none !important;
        }

        .block-container {
            max-width: 1180px;
            padding-top: 1.2rem;
            padding-bottom: 4rem;
        }

        .premium-shell {
            position: relative;
            border: 1px solid rgba(148,163,184,0.12);
            border-radius: 28px;
            background:
                linear-gradient(180deg, rgba(10,15,29,0.80), rgba(6,11,22,0.88)),
                rgba(7, 13, 24, 0.88);
            box-shadow:
                0 24px 60px rgba(2,6,23,0.55),
                inset 0 1px 0 rgba(255,255,255,0.05);
            overflow: hidden;
        }

        .premium-shell::before {
            content: "";
            position: absolute;
            inset: 0;
            background-image:
                linear-gradient(rgba(255,255,255,0.015) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255,255,255,0.015) 1px, transparent 1px);
            background-size: 38px 38px;
            opacity: 0.42;
            pointer-events: none;
        }

        .grain-layer::after {
            content: "";
            position: absolute;
            inset: 0;
            background-image: radial-gradient(rgba(255,255,255,0.05) 0.5px, transparent 0.5px);
            background-size: 7px 7px;
            opacity: 0.06;
            pointer-events: none;
        }

        .section-label {
            display:inline-flex;
            align-items:center;
            gap:0.45rem;
            padding:0.38rem 0.78rem;
            border-radius:999px;
            font-size:0.78rem;
            letter-spacing:0.04em;
            font-weight:700;
            color:#bfe9ff;
            background:rgba(56,189,248,0.12);
            border:1px solid rgba(56,189,248,0.22);
            backdrop-filter: blur(10px);
        }

        .hero-headline {
            font-family:'Sora', sans-serif;
            font-size: clamp(2.6rem, 5vw, 4.7rem);
            line-height: 1.02;
            letter-spacing: -0.04em;
            font-weight: 800;
            color: #f8fafc;
            margin: 0.9rem 0 1rem 0;
        }

        .hero-headline .accent {
            background: linear-gradient(135deg, #e2f3ff 0%, #73d9ff 42%, #60f1bc 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .hero-copy {
            color:#94a3b8;
            font-size:1.03rem;
            line-height:1.8;
            max-width: 640px;
        }

        .subtle-note {
            color:#7c8ba1;
            font-size:0.86rem;
            line-height:1.65;
        }

        .info-card, .panel-card, .metric-card, .mini-card {
            position: relative;
            border-radius: 22px;
            border: 1px solid rgba(148,163,184,0.12);
            background:
                linear-gradient(180deg, rgba(15,23,42,0.86), rgba(9,14,27,0.92));
            box-shadow: 0 20px 50px rgba(2, 8, 23, 0.42), inset 0 1px 0 rgba(255,255,255,0.05);
        }

        .info-card { padding: 1.25rem 1.2rem; }
        .panel-card { padding: 1.45rem 1.35rem; }
        .metric-card { padding: 1rem 1.05rem; min-height: 126px; }
        .mini-card { padding: 0.95rem 1rem; }

        .panel-title {
            font-family:'Sora', sans-serif;
            font-size:1.12rem;
            font-weight:700;
            color:#f8fafc;
            margin-bottom:0.35rem;
        }

        .card-kicker {
            color:#7dd3fc;
            font-size:0.74rem;
            font-weight:700;
            letter-spacing:0.08em;
            text-transform:uppercase;
            margin-bottom:0.3rem;
        }

        .kpi-value {
            font-family:'Sora', sans-serif;
            font-size:1.55rem;
            color:#f8fafc;
            font-weight:800;
            line-height:1.08;
            margin-top:0.35rem;
            margin-bottom:0.2rem;
        }

        .kpi-label {
            color:#cbd5e1;
            font-size:0.92rem;
            font-weight:600;
        }

        .kpi-sub {
            color:#7c8ba1;
            font-size:0.78rem;
            line-height:1.55;
        }

        .hero-visual {
            position: relative;
            min-height: 470px;
            padding: 1.1rem;
            perspective: 1200px;
        }

        .float-card {
            position: absolute;
            backdrop-filter: blur(18px);
            border: 1px solid rgba(255,255,255,0.08);
            background: linear-gradient(180deg, rgba(15,23,42,0.82), rgba(7,11,22,0.92));
            box-shadow: 0 24px 45px rgba(2,8,23,0.45);
            border-radius: 24px;
            animation: floatY 7s ease-in-out infinite;
        }

        .float-card.delay { animation-delay: 1.2s; }
        .float-card.delay2 { animation-delay: 2.4s; }

        .hero-main-board {
            position:absolute;
            top: 18px;
            right: 10px;
            left: 30px;
            min-height: 330px;
            transform: rotateY(-10deg) rotateX(6deg);
            padding: 1.35rem;
        }

        .hero-small-a {
            width: 210px;
            left: 0;
            bottom: 18px;
            padding: 1rem 1.05rem;
            transform: rotateY(14deg) rotateX(5deg);
        }

        .hero-small-b {
            width: 220px;
            right: 0;
            bottom: 24px;
            padding: 1rem 1.05rem;
            transform: rotateY(-14deg) rotateX(5deg);
        }

        .soft-divider {
            height: 1px;
            background: linear-gradient(90deg, transparent, rgba(148,163,184,0.26), transparent);
            margin: 0.9rem 0 1rem;
        }

        .benefit-list {
            margin:0;
            padding-left:1.05rem;
            color:#cbd5e1;
            line-height:1.8;
            font-size:0.92rem;
        }

        .process-step {
            height:100%;
            padding:1.2rem 1.1rem;
            border-radius:20px;
            border:1px solid rgba(148,163,184,0.12);
            background:linear-gradient(180deg, rgba(15,23,42,0.74), rgba(8,13,24,0.92));
            box-shadow:0 18px 44px rgba(2,8,23,0.34);
        }

        .step-index {
            width:2rem;
            height:2rem;
            border-radius:50%;
            display:inline-flex;
            align-items:center;
            justify-content:center;
            background:linear-gradient(135deg,#38bdf8,#34d399);
            color:#05101d;
            font-weight:800;
            margin-bottom:0.9rem;
        }

        .section-title {
            font-family:'Sora', sans-serif;
            color:#f8fafc;
            font-size: clamp(1.6rem, 3vw, 2.35rem);
            font-weight: 760;
            letter-spacing: -0.025em;
            margin-bottom: 0.4rem;
        }

        .section-copy {
            color:#94a3b8;
            font-size:0.98rem;
            line-height:1.75;
            max-width: 760px;
        }

        .action-chip {
            display:inline-flex;
            align-items:center;
            gap:0.45rem;
            padding:0.42rem 0.72rem;
            border-radius:999px;
            background:rgba(15,23,42,0.72);
            border:1px solid rgba(148,163,184,0.14);
            color:#cbd5e1;
            font-size:0.78rem;
            margin:0.2rem 0.3rem 0.2rem 0;
        }

        .hero-stat-strip {
            display:grid;
            grid-template-columns:repeat(3, minmax(0, 1fr));
            gap:0.8rem;
            margin-top:1.2rem;
        }

        .role-card h4, .process-step h4, .info-card h4, .mini-card h4 {
            color:#f8fafc;
            margin:0.05rem 0 0.35rem;
            font-size:1.02rem;
            font-weight:700;
        }

        .role-card p, .process-step p, .info-card p, .mini-card p {
            color:#94a3b8;
            margin:0;
            font-size:0.9rem;
            line-height:1.7;
        }

        .stButton > button {
            width: 100%;
            min-height: 3rem;
            border-radius: 15px;
            border: 1px solid rgba(148,163,184,0.16);
            background: linear-gradient(135deg, #0f172a, #0a1223);
            color: #edf2f7;
            font-weight: 700;
            box-shadow: 0 16px 34px rgba(2,8,23,0.28);
            transition: all 0.18s ease;
        }

        .stButton > button:hover {
            transform: translateY(-1px);
            border-color: rgba(96, 165, 250, 0.38);
            box-shadow: 0 18px 36px rgba(8,15,35,0.42);
        }

        .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #38bdf8, #34d399) !important;
            color: #071220 !important;
            border: none !important;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 0.55rem;
            padding: 0.4rem;
            background: rgba(15,23,42,0.78);
            border: 1px solid rgba(148,163,184,0.12);
            border-radius: 16px;
        }

        .stTabs [data-baseweb="tab"] {
            min-height: 44px;
            color: #94a3b8;
            border-radius: 12px;
            font-weight: 650;
        }

        .stTabs [aria-selected="true"] {
            background: linear-gradient(135deg, rgba(56,189,248,0.18), rgba(52,211,153,0.18));
            color: #f8fafc !important;
        }

        .stSelectbox label, .stMarkdown, .stCaption, .stText {
            color: #e2e8f0;
        }

        .stSelectbox > div > div {
            background: rgba(10,16,28,0.92) !important;
            color: #f8fafc !important;
            border-color: rgba(148,163,184,0.18) !important;
            border-radius: 14px !important;
        }

        [data-testid="stMetric"] {
            background: transparent;
        }

        .footer-band {
            border-radius: 24px;
            padding: 1.35rem 1.3rem;
            border: 1px solid rgba(148,163,184,0.12);
            background: linear-gradient(135deg, rgba(9,14,27,0.94), rgba(10,18,33,0.84));
            box-shadow: 0 20px 50px rgba(2,8,23,0.34);
        }

        @keyframes floatY {
            0%, 100% { transform: translateY(0px); }
            50% { transform: translateY(-8px); }
        }

        @media (max-width: 980px) {
            .hero-visual { min-height: 420px; }
            .hero-main-board {
                left: 10px;
                right: 10px;
                transform: none;
            }
            .hero-small-a, .hero-small-b {
                position: relative;
                width: 100%;
                left: auto;
                right: auto;
                bottom: auto;
                margin-top: 0.9rem;
                transform: none;
            }
            .hero-stat-strip { grid-template-columns: 1fr; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )



def _metric_text(value, as_percent=True):
    if value is None:
        return "—"
    if as_percent:
        return f"{value * 100:.1f}%"
    if float(value).is_integer():
        return f"{int(value):,}"
    return f"{value:.3f}"



def _nav_to_login(role=None):
    st.session_state.show_login = True
    if role:
        st.session_state.selected_role = role
    st.rerun()



def _hero_section(perf):
    holdout = perf["evaluations"]["Hold-out Test"]
    cards = performance_metric_cards(holdout)
    profile = dataset_profile()

    left, right = st.columns([1.24, 1.0], gap="large")
    with left:
        st.markdown("<div class='section-label'>● Premium mental wellness workflow</div>", unsafe_allow_html=True)
        st.markdown(
            """
            <div class="hero-headline">
                Understand <span class="accent">stress risk</span>, coordinate care,
                and guide every next step with confidence.
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <div class="hero-copy">
                StressGuard is a role-based clinical web app for <b>patients</b>, <b>doctors</b>, and <b>admins</b>.
                It combines AI-assisted stress screening, appointment coordination, secure communication, and operational visibility
                so users understand the workflow within seconds and know exactly what to do next.
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <div style="margin-top:1rem;">
                <span class="action-chip">AI stress classification</span>
                <span class="action-chip">admin + doctor + patient workflows</span>
                <span class="action-chip">appointments and ticketing</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Continue to Secure Login", type="primary", key="hero_login"):
            _nav_to_login()

        st.markdown("<div class='soft-divider'></div>", unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="subtle-note">
                First view, simplified: <b>what it does</b> — AI stress prediction and care coordination.<br>
                <b>who it is for</b> — clinical teams, operations staff, and patients.<br>
                <b>what to do next</b> — choose a portal and sign in securely.
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("<div class='hero-stat-strip'>", unsafe_allow_html=True)
        stat_cols = st.columns(3)
        hero_stats = [
            ("Dataset Rows", f"{profile['row_count']:,}", "Reference records used for evaluation"),
            ("Stress Classes", str(profile["class_count"]), "Safe to very high stress"),
            ("Hold-out Accuracy", _metric_text(holdout['summary']['accuracy']), "Current premium analytics preview"),
        ]
        for col, (label, value, sub) in zip(stat_cols, hero_stats):
            with col:
                st.markdown(
                    f"""
                    <div class="metric-card">
                        <div class="card-kicker">{label}</div>
                        <div class="kpi-value">{value}</div>
                        <div class="kpi-sub">{sub}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown("<div class='hero-visual'>", unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="float-card hero-main-board grain-layer">
                <div class="card-kicker">Live product overview</div>
                <div class="panel-title">Opening screen that explains the product fast</div>
                <p class="subtle-note" style="margin-bottom:0.9rem;">
                    Premium onboarding combines value proposition, operational workflow, role guidance, and model confidence in one structured surface.
                </p>
                <div class="soft-divider"></div>
                <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0.8rem;">
                    <div class="mini-card">
                        <div class="card-kicker">Primary audience</div>
                        <h4>Patients, doctors, admins</h4>
                        <p>Different entry points, shared system visibility, and clearer next actions.</p>
                    </div>
                    <div class="mini-card">
                        <div class="card-kicker">Workflow</div>
                        <h4>Predict → review → coordinate</h4>
                        <p>Move from screening to communication, scheduling, and follow-through.</p>
                    </div>
                    <div class="mini-card">
                        <div class="card-kicker">Analytics</div>
                        <h4>{_metric_text(holdout['summary']['auc_macro_ovr'])} AUC</h4>
                        <p>Integrated performance dashboard with multiple evaluation views.</p>
                    </div>
                    <div class="mini-card">
                        <div class="card-kicker">Security</div>
                        <h4>Verified recovery workflow</h4>
                        <p>Identity checks, reset OTP, email delivery, and contact-admin support path.</p>
                    </div>
                </div>
            </div>
            <div class="float-card hero-small-a delay">
                <div class="card-kicker">Model snapshot</div>
                <h4 style="margin:0.2rem 0 0.35rem;color:#f8fafc;">{_metric_text(cards[0][1])} accuracy</h4>
                <p>Balanced evaluation with macro precision, recall, F1, AUC, and class-wise views.</p>
            </div>
            <div class="float-card hero-small-b delay2">
                <div class="card-kicker">User action</div>
                <h4 style="margin:0.2rem 0 0.35rem;color:#f8fafc;">Choose a portal</h4>
                <p>Open Patient or Doctor login, or continue to the role selector for all pathways.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)



def _value_section():
    st.markdown("<div class='section-label'>● Value proposition</div>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'>From data to insight. From insight to care.</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='section-copy'>Extracts meaningful insights from behavioral trends to enable early detection and responsive care.Bridges data and wellbeing by transforming user patterns into actionable mental health guidance.</div>",
        unsafe_allow_html=True,
    )

    cols = st.columns(3, gap="large")
    cards = [
        (
            "🧠",
            "What the app does",
            "Predicts stress from sleep and behavioral indicators, then turns those predictions into actionable care coordination for clinical users and patients.",
        ),
        (
            "👥",
            "Who it is for",
            "Patients track wellness, doctors review trends and appointments, and admins manage user operations and system-level workflows.",
        ),
        (
            "➡️",
            "What users should do next",
            "Choose the correct portal, sign in securely, and move directly into prediction, review, communication, or administrative tasks accordingly.",
        ),
    ]
    for col, (icon, title, desc) in zip(cols, cards):
        with col:
            st.markdown(
                f"""
                <div class="info-card role-card">
                    <div style="font-size:1.4rem;">{icon}</div>
                    <h4>{title}</h4>
                    <p>{desc}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )



def _role_pathways():
    st.markdown("<div class='section-label'>● Clear pathways</div>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'>Role-Based Access.</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='section-copy'>Designed to guide each role into the right workflow with clarity and efficiency.</div>",
        unsafe_allow_html=True,
    )

    role_cols = st.columns(3, gap="large")
    role_data = [
        (
            "admin",
            "🔴 Admin",
            "System operations, user management, assignment control, ticket review, and global oversight.",
            ["Manage users", "Review tickets", "Audit workflow integrity"],
        ),
        (
            "doctor",
            "🩺 Doctor",
            "Review patient cases, confirm appointments, add notes, monitor stress history, and communicate securely.",
            ["Open doctor login", "Check appointments", "Review patient trends"],
        ),
        (
            "patient",
            "👤 Patient",
            "Run predictions, track stress history, manage appointments, view notes, and contact your care team.",
            ["Open patient login", "Start prediction workflow", "Get reports and more"],
        ),
    ]
    for col, (role, title, desc, bullets) in zip(role_cols, role_data):
        with col:
            st.markdown(
                f"""
                <div class="panel-card role-card">
                    <div class="card-kicker">Portal</div>
                    <h4>{title}</h4>
                    <p>{desc}</p>
                    <div class="soft-divider"></div>
                    <ul class="benefit-list">
                        {''.join(f'<li>{item}</li>' for item in bullets)}
                    </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button(f"Enter {role.title()} Portal", key=f"landing_portal_{role}", use_container_width=True):
                _nav_to_login(role)



def _how_it_works():
    st.markdown("<div class='section-label'>● How the system works</div>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'>From data capture to coordinated follow-through.</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='section-copy'>The workflow is intentionally staged so both clinical and non-technical users can understand the product quickly. Data is transformed into predictions, predictions into review, and review into coordinated action.</div>",
        unsafe_allow_html=True,
    )

    steps = [
        ("1", "Capture relevant inputs", "Sleep, respiratory, and behavioral indicators are prepared for the model using a clean preprocessing pipeline."),
        ("2", "Generate stress classification", "The model predicts one of five stress levels & supports review through probabilities, summary metrics, & historical context."),
        ("3", "Coordinate care actions", "Doctors and patients use appointments, notes, messages, and admin workflows to follow through securely."),
        ("4", "Monitor quality continuously", "The performance dashboard shows confusion matrix, ROC, precision–recall, learning curves, and class breakdowns."),
    ]
    cols = st.columns(4, gap="large")
    for col, (idx, title, desc) in zip(cols, steps):
        with col:
            st.markdown(
                f"""
                <div class="process-step">
                    <div class="step-index">{idx}</div>
                    <h4>{title}</h4>
                    <p>{desc}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )



def _performance_section(perf):
    st.markdown("<div class='section-label'>● Model performance dashboard</div>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'>Integrated analytics area for fast model review.</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='section-copy'>{perf['meta']['evaluation_note']} Users can switch the evaluation dataset, focus on individual classes, and move from top-line metrics to detailed charts without leaving the landing experience.</div>",
        unsafe_allow_html=True,
    )

    toolbar_left, toolbar_right = st.columns([1.2, 1.0], gap="large")
    with toolbar_left:
        eval_name = st.selectbox(
            "Evaluation dataset",
            options=list(perf["evaluations"].keys()),
            key="perf_eval_name",
            help="Switch between hold-out test results and cross-validated out-of-fold predictions.",
        )
    with toolbar_right:
        class_choice = st.selectbox(
            "Focus class",
            options=["All classes"] + [CLASS_LABELS[c] for c in perf["meta"]["classes"]],
            key="perf_class_focus",
            help="Filter ROC and precision–recall curves for a selected stress level.",
        )

    eval_bundle = perf["evaluations"][eval_name]
    focus_classes = None
    if class_choice != "All classes":
        focus_classes = [k for k, v in CLASS_LABELS.items() if v == class_choice]

    metric_cols = st.columns(4, gap="large")
    top_metrics = performance_metric_cards(eval_bundle)[:8]
    for col, (label, value, subtitle) in zip(metric_cols * 2, top_metrics):
        with col:
            is_support = label == "Support"
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="card-kicker">{label}</div>
                    <div class="kpi-value">{_metric_text(value, as_percent=not is_support)}</div>
                    <div class="kpi-sub">{subtitle}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    tabs = st.tabs(["Overview", "Curves", "Learning", "Class Breakdown"])

    with tabs[0]:
        left, right = st.columns([1.05, 0.95], gap="large")
        with left:
            st.caption("Confusion matrix: how true classes map to predicted classes.")
            st.pyplot(plot_confusion_matrix(eval_bundle), clear_figure=True, use_container_width=True)
        with right:
            st.caption("Support distribution: how many evaluated samples belong to each stress class.")
            st.pyplot(plot_support_distribution(eval_bundle), clear_figure=True, use_container_width=True)
            st.markdown(
                f"""
                <div class="panel-card" style="margin-top:0.8rem;">
                    <div class="card-kicker">Evaluation notes</div>
                    <div class="panel-title">{eval_bundle['summary']['title']}</div>
                    <p class="subtle-note">This view helps users interpret more than raw accuracy by combining multiple summary metrics, class support, and error distribution.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with tabs[1]:
        left, right = st.columns(2, gap="large")
        with left:
            st.caption("ROC curve: trade-off between sensitivity and false positives.")
            st.pyplot(plot_roc_curve(eval_bundle, focus_classes=focus_classes), clear_figure=True, use_container_width=True)
        with right:
            st.caption("Precision–recall curve: quality of positive class retrieval under imbalance-sensitive evaluation.")
            st.pyplot(plot_precision_recall_curve(eval_bundle, focus_classes=focus_classes), clear_figure=True, use_container_width=True)

    with tabs[2]:
        st.caption("Training vs validation curves show whether the model is learning consistently as sample size grows.")
        st.pyplot(plot_learning_curves(perf), clear_figure=True, use_container_width=True)

    with tabs[3]:
        metric_map = {
            "Precision": "precision",
            "Recall": "recall",
            "F1-score": "f1_score",
            "Specificity": "specificity",
            "Class-wise Accuracy": "class_accuracy",
        }
        metric_choice = st.selectbox("Class metric", options=list(metric_map.keys()), key="perf_metric_choice")
        left, right = st.columns([1.05, 0.95], gap="large")
        with left:
            st.caption("Class-wise metric comparison for the selected evaluation dataset.")
            st.pyplot(
                plot_classwise_metrics(eval_bundle, metric_key=metric_map[metric_choice]),
                clear_figure=True,
                use_container_width=True,
            )
        with right:
            rows = []
            for row in eval_bundle["per_class"]:
                rows.append(
                    {
                        "Class": row["class_name"],
                        "Precision": f"{row['precision'] * 100:.1f}%",
                        "Recall": f"{row['recall'] * 100:.1f}%",
                        "F1": f"{row['f1_score'] * 100:.1f}%",
                        "Specificity": f"{row['specificity'] * 100:.1f}%",
                        "Support": row["support"],
                    }
                )
            st.caption("Per-class metrics table for quick comparison.")
            st.dataframe(rows, use_container_width=True, hide_index=True)

def show_landing():
    _inject_css()
    perf = compute_model_performance()

    st.markdown("<div class='premium-shell grain-layer' style='padding:1.35rem 1.2rem 1.5rem;'>", unsafe_allow_html=True)
    _hero_section(perf)
    st.markdown("<div style='height:1.1rem;'></div>", unsafe_allow_html=True)
    _value_section()
    st.markdown("<div style='height:1.35rem;'></div>", unsafe_allow_html=True)
    _role_pathways()
    st.markdown("<div style='height:1.35rem;'></div>", unsafe_allow_html=True)
    _how_it_works()
    st.markdown("<div style='height:1.55rem;'></div>", unsafe_allow_html=True)
    _performance_section(perf)
    st.markdown("<div style='height:1.55rem;'></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
