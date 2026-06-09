import io
import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm, mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image as RLImage, PageBreak, KeepTogether
)
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.pdfgen import canvas as pdfcanvas

REPORTLAB_OK = True  # reportlab is a required dependency

# ── Palette ───────────────────────────────────────────────────────────────────
BRAND_DARK   = colors.HexColor("#06090f")
BRAND_BLUE   = colors.HexColor("#00d4ff")
BRAND_GREEN  = colors.HexColor("#00ff88")
BRAND_RED    = colors.HexColor("#ff4b4b")
BRAND_PURPLE = colors.HexColor("#8e44ad")
ACCENT_LIGHT = colors.HexColor("#0d1b2a")
PANEL_BG     = colors.HexColor("#0a1e30")
MUTED        = colors.HexColor("#778899")
WHITE        = colors.white

STRESS_COLORS = {
    "Safe":         "#2ecc71",
    "Low Stress":   "#f1c40f",
    "Medium Stress":"#e67e22",
    "High Stress":  "#e74c3c",
    "Very High":    "#8e44ad",
}

W, H = A4   # 595.27 x 841.89 pts


# ─────────────────────────────────────────────────────────────────────────────
#  Watermark canvas callback
# ─────────────────────────────────────────────────────────────────────────────
def _watermark_callback(canvas_obj, doc):
    canvas_obj.saveState()
    canvas_obj.setFont("Helvetica-Bold", 52)
    canvas_obj.setFillColorRGB(0, 0.83, 1, alpha=0.06)
    canvas_obj.translate(W / 2, H / 2)
    canvas_obj.rotate(42)
    canvas_obj.drawCentredString(0, 0, "STRESS DETECTOR")
    canvas_obj.restoreState()

    # Footer
    canvas_obj.saveState()
    canvas_obj.setFont("Helvetica", 7)
    canvas_obj.setFillColorRGB(0.47, 0.47, 0.53)
    canvas_obj.drawString(
        1.5 * cm, 0.7 * cm,
        f"Stress Level Detector — Confidential Patient Report — "
        f"Generated {datetime.datetime.now().strftime('%d %b %Y %H:%M')}")
    canvas_obj.drawRightString(
        W - 1.5 * cm, 0.7 * cm,
        f"Page {doc.page}")
    canvas_obj.restoreState()


# ─────────────────────────────────────────────────────────────────────────────
#  Build stress trend chart → bytes
# ─────────────────────────────────────────────────────────────────────────────
def _build_trend_chart(preds) -> bytes:
    levels = [int(p["stress_level"]) for p in reversed(preds[-20:]) if p.get("stress_level") is not None]
    labels = [p["stress_label"].split()[0] for p in reversed(preds[-20:])]

    fig, ax = plt.subplots(figsize=(7, 2.6), facecolor="#06090f")
    ax.set_facecolor("#0d1b2a")

    color_pts = []
    for lv in levels:
        if lv == 0:   color_pts.append("#2ecc71")
        elif lv == 1: color_pts.append("#f1c40f")
        elif lv == 2: color_pts.append("#e67e22")
        elif lv == 3: color_pts.append("#e74c3c")
        else:         color_pts.append("#8e44ad")

    xs = list(range(len(levels)))
    ax.plot(xs, levels, color="#00d4ff", linewidth=1.8, zorder=2)
    ax.fill_between(xs, levels, alpha=0.15, color="#00d4ff")
    for x, y, c in zip(xs, levels, color_pts):
        ax.scatter(x, y, color=c, s=55, zorder=3)

    ax.set_yticks([0, 1, 2, 3, 4])
    ax.set_yticklabels(["Safe", "Low", "Med", "High", "V.High"],
                       color="white", fontsize=7)
    ax.tick_params(axis="x", colors="white", labelsize=7)
    ax.set_xticks(xs[::max(1, len(xs)//8)])
    for sp in ax.spines.values():
        sp.set_edgecolor("#2a3a5a")
    ax.set_title("Stress Level Trend", color="white", fontsize=9, pad=5)
    ax.grid(axis="y", color="#1e2a3a", linewidth=0.5)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ─────────────────────────────────────────────────────────────────────────────
#  Build distribution pie chart → bytes
# ─────────────────────────────────────────────────────────────────────────────
def _build_dist_chart(preds) -> bytes:
    from collections import Counter
    dist = Counter(p["stress_label"] for p in preds)
    labels = list(dist.keys())
    vals   = list(dist.values())
    clrs   = [STRESS_COLORS.get(k, "#778") for k in labels]

    fig, ax = plt.subplots(figsize=(4, 3), facecolor="#06090f")
    ax.set_facecolor("#06090f")
    wedges, texts, autotexts = ax.pie(
        vals, labels=labels, colors=clrs,
        autopct="%1.0f%%", startangle=140,
        textprops={"color": "white", "fontsize": 7})
    for at in autotexts:
        at.set_fontsize(7)
    ax.set_title("Stress Distribution", color="white", fontsize=9)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight",
                facecolor="#06090f")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ─────────────────────────────────────────────────────────────────────────────
#  Styles
# ─────────────────────────────────────────────────────────────────────────────
def _get_styles():
    base = getSampleStyleSheet()
    styles = {}

    styles["cover_title"] = ParagraphStyle(
        "cover_title", parent=base["Title"],
        fontSize=26, fontName="Helvetica-Bold",
        textColor=BRAND_BLUE, alignment=TA_CENTER,
        spaceAfter=6)

    styles["cover_sub"] = ParagraphStyle(
        "cover_sub", parent=base["Normal"],
        fontSize=11, fontName="Helvetica",
        textColor=BRAND_GREEN, alignment=TA_CENTER,
        spaceAfter=4)

    styles["section_head"] = ParagraphStyle(
        "section_head", parent=base["Heading2"],
        fontSize=13, fontName="Helvetica-Bold",
        textColor=BRAND_BLUE, spaceBefore=14, spaceAfter=6,
        borderPad=2)

    styles["label"] = ParagraphStyle(
        "label", parent=base["Normal"],
        fontSize=8, fontName="Helvetica-Bold",
        textColor=MUTED)

    styles["value"] = ParagraphStyle(
        "value", parent=base["Normal"],
        fontSize=9, fontName="Helvetica",
        textColor=WHITE, spaceAfter=3)

    styles["note_text"] = ParagraphStyle(
        "note_text", parent=base["Normal"],
        fontSize=8.5, fontName="Helvetica",
        textColor=WHITE, leading=13, spaceAfter=4)

    styles["small_muted"] = ParagraphStyle(
        "small_muted", parent=base["Normal"],
        fontSize=7.5, fontName="Helvetica",
        textColor=MUTED, spaceAfter=2)

    styles["body"] = ParagraphStyle(
        "body", parent=base["Normal"],
        fontSize=9, fontName="Helvetica",
        textColor=WHITE, leading=14, spaceAfter=6)

    return styles


# ─────────────────────────────────────────────────────────────────────────────
#  Main generator
# ─────────────────────────────────────────────────────────────────────────────
def generate_patient_report_pdf(
    patient: dict,
    doctor: dict,
    preds: list,
    doc_notes: list,
    checklist: list,
    for_patient: bool = False,
    timezone_name: str | None = None,
) -> bytes:
    """
    Returns PDF bytes.

    patient     : dict with id, full_name, email, phone, username, bio
    doctor      : dict or None
    preds       : list of prediction rows
    doc_notes   : list of doctor note rows
    checklist   : list of checklist rows
    for_patient : if True, omit doctor-only sections
    """
    # reportlab is a hard dependency — if missing, pip install reportlab

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.8 * cm, rightMargin=1.8 * cm,
        topMargin=2.2 * cm, bottomMargin=2.0 * cm,
        title=f"Stress Report — {patient.get('full_name', 'Patient')}",
        author="Stress Level Detector",
        subject="Patient Stress Analysis Report",
    )

    S = _get_styles()
    story = []

    # ── COVER ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 1.2 * cm))
    story.append(Paragraph("🧠 Stress Level Detector", S["cover_title"]))
    story.append(Paragraph("Patient Stress Analysis Report", S["cover_sub"]))
    story.append(HRFlowable(width="100%", thickness=1.5,
                            color=BRAND_BLUE, spaceAfter=10))

    # Patient info card
    gen_dt = datetime.datetime.now().strftime("%d %B %Y, %H:%M")
    cover_data = [
        ["Patient Name", patient.get("full_name", "—")],
        ["Username",     f"@{patient.get('username','—')}"],
        ["Email",        patient.get("email","—")],
        ["Phone",        patient.get("phone","—") or "—"],
        ["Assigned Doctor",
         f"Dr. {doctor['full_name']}" if doctor else "Not assigned"],
        ["Report Date",  gen_dt],
        ["Total Predictions", str(len(preds))],
    ]
    cover_tbl = Table(
        [[Paragraph(f"<b><font color='#778899' size='8'>{r[0]}</font></b>",
                    S["body"]),
          Paragraph(f"<font color='white' size='9'>{r[1]}</font>",
                    S["body"])]
         for r in cover_data],
        colWidths=[5.5 * cm, 10 * cm])
    cover_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ACCENT_LIGHT),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1),
         [PANEL_BG, ACCENT_LIGHT]),
        ("TEXTCOLOR", (0, 0), (-1, -1), WHITE),
        ("FONTNAME",  (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE",  (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("ROUNDEDCORNERS", [6, 6, 6, 6]),
        ("BOX",  (0, 0), (-1, -1), 1, BRAND_BLUE),
        ("LINEAFTER", (0, 0), (0, -1), 0.5, BRAND_BLUE),
    ]))
    story.append(cover_tbl)
    story.append(Spacer(1, 0.6 * cm))

    # ── SUMMARY METRICS ───────────────────────────────────────────────────────
    if preds:
        from collections import Counter
        dist = Counter(p["stress_label"] for p in preds)
        most_common = dist.most_common(1)[0][0] if dist else "—"
        latest = preds[-1]["stress_label"] if preds else "—"
        avg_score = round(
            sum(int(p["stress_level"]) for p in preds if p.get("stress_level") is not None) / max(1, sum(1 for p in preds if p.get("stress_level") is not None)), 2)

        story.append(Paragraph("📊 Summary", S["section_head"]))
        metrics_data = [
            ["Most Frequent Stress", "Latest Result", "Average Score"],
            [most_common,           latest,           str(avg_score)],
        ]
        mt = Table(metrics_data,
                   colWidths=[(W - 4.6 * cm) / 3] * 3)
        mt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), PANEL_BG),
            ("BACKGROUND", (0, 1), (-1, 1), ACCENT_LIGHT),
            ("TEXTCOLOR",  (0, 0), (-1, 0), MUTED),
            ("TEXTCOLOR",  (0, 1), (-1, 1), WHITE),
            ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME",   (0, 1), (-1, 1), "Helvetica-Bold"),
            ("FONTSIZE",   (0, 0), (-1, 0), 8),
            ("FONTSIZE",   (0, 1), (-1, 1), 11),
            ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("BOX",        (0, 0), (-1, -1), 1, BRAND_BLUE),
            ("INNERGRID",  (0, 0), (-1, -1), 0.5, PANEL_BG),
        ]))
        story.append(mt)
        story.append(Spacer(1, 0.4 * cm))

    # ── TREND CHART ───────────────────────────────────────────────────────────
    if len(preds) > 1:
        story.append(Paragraph("📈 Stress Trend", S["section_head"]))
        trend_bytes = _build_trend_chart(preds)
        img = RLImage(io.BytesIO(trend_bytes),
                      width=15 * cm, height=5.5 * cm)
        story.append(img)
        story.append(Spacer(1, 0.3 * cm))

    # ── DISTRIBUTION CHART ────────────────────────────────────────────────────
    if len(preds) >= 3:
        story.append(Paragraph("🥧 Stress Distribution", S["section_head"]))
        dist_bytes = _build_dist_chart(preds)
        img2 = RLImage(io.BytesIO(dist_bytes),
                       width=8 * cm, height=6 * cm)
        story.append(img2)
        story.append(Spacer(1, 0.3 * cm))

    # ── PREDICTIONS TABLE ─────────────────────────────────────────────────────
    if preds:
        story.append(Paragraph("📋 Prediction History",
                                S["section_head"]))

        def _sf(val, dec=1):
            try: return str(round(float(val), dec)) if val is not None else "—"
            except: return "—"

        col_widths = [3.5*cm, 1.8*cm, 1.6*cm, 1.8*cm,
                      1.8*cm, 1.8*cm, 1.8*cm, 3.0*cm]
        headers = ["Stress Level", "Score", "Age",
                   "ScrnTm", "Resp.", "Body Tmp", "Heart Rate", "Timestamp"]
        tbl_data = [headers]
        for p in preds[-30:]:   # cap at 30 rows
            age_v = p.get("age") or p.get("Age") or p.get("sr")
            scr_v = p.get("screen_time") or p.get("ScreenTimeHours")
            tbl_data.append([
                p.get("stress_label",  "—"),
                str(p.get("stress_level", "—")),
                _sf(age_v, 0),
                _sf(scr_v, 1),
                _sf(p.get("rr"),  1),
                _sf(p.get("bt"),  1),
                _sf(p.get("hr"),  1),
                str(p.get("predicted_at", "—"))[:16],
            ])

        pred_tbl = Table(tbl_data, colWidths=col_widths, repeatRows=1)
        row_colors = []
        for i, row in enumerate(tbl_data[1:], 1):
            lbl = row[0]
            hex_c = STRESS_COLORS.get(lbl, "#1a2a3a") + "40"
            row_colors.append(("BACKGROUND", (0, i), (-1, i),
                                colors.HexColor(hex_c)))

        pred_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), PANEL_BG),
            ("TEXTCOLOR",     (0, 0), (-1, 0), BRAND_BLUE),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, 0), 8),
            ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE",      (0, 1), (-1, -1), 7.5),
            ("TEXTCOLOR",     (0, 1), (-1, -1), WHITE),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1),
             [ACCENT_LIGHT, PANEL_BG]),
            ("BOX",           (0, 0), (-1, -1), 1, BRAND_BLUE),
            ("LINEBELOW",     (0, 0), (-1, 0),  1, BRAND_BLUE),
            ("INNERGRID",     (0, 0), (-1, -1), 0.3, MUTED),
        ] + row_colors))
        story.append(pred_tbl)
        story.append(Spacer(1, 0.5 * cm))

    # ── DOCTOR NOTES ──────────────────────────────────────────────────────────
    if doc_notes and not for_patient:
        story.append(PageBreak())
        story.append(Paragraph("📝 Clinical Notes", S["section_head"]))
        for n in doc_notes:
            ts = str(n.get("created_at", ""))[:16]
            note_tbl = Table(
                [[Paragraph(
                    f"<font color='#00d4ff' size='7'><b>🩺 "
                    f"{n.get('doctor_name','Doctor')} • {ts}</b></font><br/>"
                    f"<font color='white' size='8.5'>{n.get('note','')}</font>",
                    S["note_text"])]],
                colWidths=[W - 4.6 * cm])
            note_tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), PANEL_BG),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING",  (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LINEBEFOREBEFORE", (0, 0), (0, -1), 3, BRAND_BLUE),
                ("LINEBEFORE", (0, 0), (0, -1), 3, BRAND_BLUE),
                ("BOX",       (0, 0), (-1, -1), 0.5, MUTED),
                ("ROUNDEDCORNERS", [5, 5, 5, 5]),
            ]))
            story.append(note_tbl)
            story.append(Spacer(1, 0.25 * cm))

    # ── CHECKLIST ─────────────────────────────────────────────────────────────
    if checklist:
        story.append(Paragraph("✅ Checklist Summary", S["section_head"]))
        done_count = sum(1 for c in checklist if c.get("is_done"))
        story.append(Paragraph(
            f"<font color='#00ff88'>{done_count}</font> / {len(checklist)}"
            f" tasks completed",
            S["body"]))

        cats = {"Daily": "☀️", "Weekly": "📅", "Monthly": "🗓️"}
        for cat, icon in cats.items():
            cat_items = [c for c in checklist if c.get("category") == cat]
            if not cat_items:
                continue
            story.append(Paragraph(
                f"<b><font color='#00d4ff'>{icon} {cat} Tasks</font></b>",
                S["body"]))
            chk_data = []
            for ci in cat_items:
                done = bool(ci.get("is_done"))
                mark = "✓" if done else "○"
                col  = "#00ff88" if done else "#778899"
                chk_data.append([
                    Paragraph(
                        f"<font color='{col}'>{mark}</font>",
                        S["body"]),
                    Paragraph(
                        f"<font color='{'#556' if done else 'white'}'>"
                        f"{'<strike>' if done else ''}"
                        f"{ci.get('item_text','')}"
                        f"{'</strike>' if done else ''}"
                        f"</font>",
                        S["body"]),
                ])
            ck_tbl = Table(chk_data,
                           colWidths=[1.2 * cm, W - 5.8 * cm])
            ck_tbl.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), PANEL_BG),
                ("TOPPADDING",    (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING",   (0, 0), (-1, -1), 8),
                ("LINEBELOW",     (0, 0), (-1, -2), 0.3, ACCENT_LIGHT),
            ]))
            story.append(ck_tbl)
            story.append(Spacer(1, 0.2 * cm))

    # ── DISCLAIMER ────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.8 * cm))
    story.append(HRFlowable(width="100%", thickness=0.5,
                             color=MUTED, spaceAfter=6))
    story.append(Paragraph(
        "<font color='#778899' size='7'>"
        "⚠️ This report is generated by an AI-based system for informational "
        "purposes only. It does not constitute medical advice. Please consult "
        "a qualified healthcare professional for diagnosis and treatment."
        "</font>",
        S["body"]))

    # Build PDF
    doc.build(
        story,
        onFirstPage=_watermark_callback,
        onLaterPages=_watermark_callback)
    pdf_bytes = buf.getvalue()
    return pdf_bytes


# ─────────────────────────────────────────────────────────────────────────────
#  Admin Roster PDF  (doctors list + patients list + assignments)
# ─────────────────────────────────────────────────────────────────────────────
def generate_admin_roster_pdf(doctors: list, patients_with_doctors: list) -> bytes:
    """
    doctors               : list of user dicts (role='doctor')
    patients_with_doctors : from get_patients_with_doctors()
    Returns PDF bytes.
    """
    # Filter out any None or non-dict entries defensively
    doctors = [d for d in (doctors or []) if d and isinstance(d, dict)]
    patients_with_doctors = [p for p in (patients_with_doctors or []) if p and isinstance(p, dict)]
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.8*cm, rightMargin=1.8*cm,
        topMargin=2.2*cm, bottomMargin=2.0*cm,
        title="Admin Roster — Stress Level Detector",
        author="Stress Level Detector",
    )
    S = _get_styles()
    story = []

    # ── Cover ─────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.6*cm))
    story.append(Paragraph("🧠 Stress Level Detector", S["cover_title"]))
    story.append(Paragraph("Admin Roster — Doctors, Patients & Assignments",
                            S["cover_sub"]))
    story.append(HRFlowable(width="100%", thickness=1.5,
                             color=BRAND_BLUE, spaceAfter=10))
    gen_dt = datetime.datetime.now().strftime("%d %B %Y, %H:%M")
    story.append(Paragraph(
        f"<font color='#778899'>Generated: {gen_dt} &nbsp;|&nbsp; "
        f"Doctors: {len(doctors)} &nbsp;|&nbsp; "
        f"Patients: {len(patients_with_doctors)}</font>",
        S["body"]))
    story.append(Spacer(1, 0.5*cm))

    # ── Section 1: Doctors ────────────────────────────────────────────────────
    story.append(Paragraph("🩺 Registered Doctors", S["section_head"]))
    if doctors:
        doc_headers = ["#", "Full Name", "Username", "Email", "Phone",
                       "Joined"]
        doc_data = [doc_headers]
        for i, d in enumerate(doctors, 1):
            if not d or not isinstance(d, dict): continue  # guard against None
            doc_data.append([
                str(i),
                d.get("full_name", "—") or "—",
                f"@{d.get('username','—')}",
                d.get("email","—") or "—",
                d.get("phone","—") or "—",
                str(d.get("created_at","") or "")[:10],
            ])
        col_w = [1*cm, 3.8*cm, 3.2*cm, 4.5*cm, 2.8*cm, 2.2*cm]
        tbl = Table(doc_data, colWidths=col_w, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,0), PANEL_BG),
            ("TEXTCOLOR",     (0,0), (-1,0), BRAND_BLUE),
            ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",      (0,0), (-1,0), 8),
            ("FONTNAME",      (0,1), (-1,-1), "Helvetica"),
            ("FONTSIZE",      (0,1), (-1,-1), 7.5),
            ("TEXTCOLOR",     (0,1), (-1,-1), WHITE),
            ("ALIGN",         (0,0), (-1,-1), "LEFT"),
            ("ALIGN",         (0,0), (0,-1), "CENTER"),
            ("ROWBACKGROUNDS",(0,1), (-1,-1), [ACCENT_LIGHT, PANEL_BG]),
            ("BOX",           (0,0), (-1,-1), 1, BRAND_BLUE),
            ("LINEBELOW",     (0,0), (-1,0), 1, BRAND_BLUE),
            ("INNERGRID",     (0,0), (-1,-1), 0.3, MUTED),
            ("TOPPADDING",    (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ]))
        story.append(tbl)
    else:
        story.append(Paragraph("<font color='#778899'>No doctors registered.</font>",
                                S["body"]))

    story.append(Spacer(1, 0.6*cm))

    # ── Section 2: Patients ───────────────────────────────────────────────────
    story.append(Paragraph("👤 Registered Patients", S["section_head"]))
    if patients_with_doctors:
        pat_headers = ["#", "Full Name", "Username", "Email",
                       "Assigned Doctor", "Joined"]
        pat_data = [pat_headers]
        for i, p in enumerate(patients_with_doctors, 1):
            if not p or not isinstance(p, dict): continue  # guard against None
            dr_name = p.get("doctor_name") or "— Unassigned —"
            pat_data.append([
                str(i),
                p.get("full_name","—") or "—",
                f"@{p.get('username','—')}",
                p.get("email","—") or "—",
                f"Dr. {dr_name}" if p.get("doctor_name") else "— Unassigned —",
                str(p.get("created_at","") or "")[:10],
            ])
        col_w2 = [1*cm, 3.5*cm, 3.0*cm, 3.8*cm, 3.8*cm, 2.4*cm]
        tbl2 = Table(pat_data, colWidths=col_w2, repeatRows=1)
        tbl2.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,0), PANEL_BG),
            ("TEXTCOLOR",     (0,0), (-1,0), BRAND_GREEN),
            ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",      (0,0), (-1,0), 8),
            ("FONTNAME",      (0,1), (-1,-1), "Helvetica"),
            ("FONTSIZE",      (0,1), (-1,-1), 7.5),
            ("TEXTCOLOR",     (0,1), (-1,-1), WHITE),
            ("ALIGN",         (0,0), (-1,-1), "LEFT"),
            ("ALIGN",         (0,0), (0,-1), "CENTER"),
            ("ROWBACKGROUNDS",(0,1), (-1,-1), [ACCENT_LIGHT, PANEL_BG]),
            ("BOX",           (0,0), (-1,-1), 1, BRAND_GREEN),
            ("LINEBELOW",     (0,0), (-1,0), 1, BRAND_GREEN),
            ("INNERGRID",     (0,0), (-1,-1), 0.3, MUTED),
            ("TOPPADDING",    (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ]))
        story.append(tbl2)
    else:
        story.append(Paragraph("<font color='#778899'>No patients registered.</font>",
                                S["body"]))

    story.append(PageBreak())

    # ── Section 3: Doctor–Patient Assignment Map ─────────────────────────────
    story.append(Paragraph("🔗 Doctor–Patient Assignment Map", S["section_head"]))
    story.append(Paragraph(
        "<font color='#778899'>Each doctor listed with their assigned patients.</font>",
        S["body"]))
    story.append(Spacer(1, 0.3*cm))

    # Group patients by doctor
    from collections import defaultdict
    groups = defaultdict(list)
    unassigned = []
    for p in patients_with_doctors:
        if not p or not isinstance(p, dict): continue  # guard against None
        dn = p.get("doctor_name")
        if dn:
            groups[dn].append(p)
        else:
            unassigned.append(p)

    for doc_obj in doctors:
        dname = doc_obj.get("full_name","?")
        assigned = groups.get(dname, [])
        story.append(Paragraph(
            f"<b><font color='#00d4ff'>🩺 Dr. {dname}</font></b> "
            f"<font color='#778899'>— {len(assigned)} patient(s)</font>",
            S["body"]))
        if assigned:
            for idx, p in enumerate(assigned, 1):
                story.append(Paragraph(
                    f"<font color='#556'>&nbsp;&nbsp;&nbsp;{idx}.</font> "
                    f"<font color='white'>{p.get('full_name','?')}</font> "
                    f"<font color='#556'>(@{p.get('username','?')}) "
                    f"• {p.get('email','—')}</font>",
                    S["body"]))
        else:
            story.append(Paragraph(
                "&nbsp;&nbsp;&nbsp;<font color='#556'>No patients assigned yet.</font>",
                S["body"]))
        story.append(Spacer(1, 0.15*cm))

    if unassigned:
        story.append(Paragraph(
            "<b><font color='#ff8800'>⚠️ Unassigned Patients</font></b>",
            S["body"]))
        for idx, p in enumerate(unassigned, 1):
            story.append(Paragraph(
                f"<font color='#556'>&nbsp;&nbsp;&nbsp;{idx}.</font> "
                f"<font color='#ccc'>{p.get('full_name','?')}</font> "
                f"<font color='#556'>(@{p.get('username','?')})</font>",
                S["body"]))

    # Disclaimer
    story.append(Spacer(1, 0.8*cm))
    story.append(HRFlowable(width="100%", thickness=0.5,
                             color=MUTED, spaceAfter=6))
    story.append(Paragraph(
        "<font color='#778899' size='7'>"
        "⚠️ This roster is generated by the Stress Level Detector admin system. "
        "Handle all patient data in accordance with applicable privacy regulations."
        "</font>", S["body"]))

    doc.build(story,
              onFirstPage=_watermark_callback,
              onLaterPages=_watermark_callback)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
#  APPOINTMENT SLIP PDF
# ══════════════════════════════════════════════════════════════════════════════
def generate_appointment_slip_pdf(appt: dict, patient: dict, doctor: dict, timezone_name: str | None = None) -> bytes:
    """Generate a downloadable appointment slip for a patient."""
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    import io

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            topMargin=2*cm, bottomMargin=2*cm,
                            leftMargin=2.5*cm, rightMargin=2.5*cm)
    styles = getSampleStyleSheet()
    TEAL  = colors.HexColor("#00d4ff")
    GREEN = colors.HexColor("#00ff88")
    DARK  = colors.HexColor("#06090f")
    MID   = colors.HexColor("#0d1b2a")
    LGREY = colors.HexColor("#778899")

    title_style = ParagraphStyle("Title", parent=styles["Title"],
                                  textColor=TEAL, fontSize=22,
                                  spaceAfter=6, alignment=TA_CENTER)
    sub_style   = ParagraphStyle("Sub", parent=styles["Normal"],
                                  textColor=GREEN, fontSize=12,
                                  alignment=TA_CENTER, spaceAfter=4)
    body_style  = ParagraphStyle("Body", parent=styles["Normal"],
                                  textColor=colors.white, fontSize=10,
                                  leading=16)
    label_style = ParagraphStyle("Label", parent=styles["Normal"],
                                  textColor=LGREY, fontSize=9)

    story = []
    story.append(Paragraph("🏥 Appointment Slip", title_style))
    story.append(Paragraph("Stress Level Detector – Healthcare Portal", sub_style))

    # Show UPDATED banner if rescheduled or proposed
    _slip_status = appt.get("status", "")
    if _slip_status in ("DoctorProposed", "Rescheduled", "Confirmed") and \
            (appt.get("proposed_date") or appt.get("new_date")):
        _banner_style = ParagraphStyle("Banner", parent=styles["Normal"],
                                        textColor=colors.HexColor("#f1c40f"),
                                        fontSize=10, alignment=TA_CENTER,
                                        spaceAfter=4, backColor=colors.HexColor("#1a1500"))
        story.append(Paragraph("⚠️  UPDATED SLIP — Time has been rescheduled by Doctor", _banner_style))

    story.append(HRFlowable(width="100%", thickness=1, color=TEAL, spaceAfter=12))

    # Appointment details table
    appt_id   = appt.get("id", "—")
    appt_date = appt.get("appt_date", "—")
    # Times shown in IST, no timezone label (clean for PDF)
    _raw_time = appt.get("appt_time", "—")
    appt_time = _raw_time  # already HH:MM string — display as-is
    reason    = appt.get("reason", "—") or "—"
    pay_mode  = appt.get("payment_mode", "—") or "—"
    pay_ref   = appt.get("payment_ref", "—") or "—"
    pay_st    = appt.get("payment_status", "—") or "—"
    status    = appt.get("status", "—") or "—"
    p_name    = patient.get("full_name", "—")
    p_email   = patient.get("email", "—") or "—"
    p_phone   = patient.get("phone", "—") or "—"
    d_name    = doctor.get("full_name", "—")
    d_email   = doctor.get("email", "—") or "—"

    # Detect rescheduled / proposed times
    proposed_date = appt.get("proposed_date") or appt.get("new_date")
    proposed_time = appt.get("proposed_time") or appt.get("new_time")
    is_rescheduled = status in ("DoctorProposed", "Rescheduled", "Confirmed") and proposed_date
    orig_date = appt.get("original_date") or appt_date
    orig_time = appt.get("original_time") or appt_time
    # Use effective (latest confirmed) date/time
    eff_date = proposed_date if is_rescheduled else appt_date
    eff_time = proposed_time if is_rescheduled else appt_time

    data = [
        ["Field", "Details"],
        ["Appointment ID",  f"APT-{appt_id:05d}" if isinstance(appt_id, int) else str(appt_id)],
        ["Status",          status],
        ["", ""],
        ["Scheduled Date",  eff_date],
        ["Scheduled Time",  eff_time],
    ]
    if is_rescheduled:
        data += [
            ["Original Date",   orig_date],
            ["Original Time",   orig_time],
            ["Rescheduled By",  appt.get("proposed_by", "Doctor").title()],
            ["Doctor Note",     appt.get("doctor_note", "—") or "—"],
        ]
    data += [
        ["Reason / Notes",  reason],
        ["", ""],
        ["Patient Name",    p_name],
        ["Patient Email",   p_email],
        ["Patient Phone",   p_phone],
        ["", ""],
        ["Doctor",          f"Dr. {d_name}"],
        ["Doctor Email",    d_email],
        ["", ""],
        ["Payment Mode",    pay_mode],
        ["Payment Status",  pay_st],
        ["Transaction Ref", pay_ref],
    ]

    tbl = Table(data, colWidths=[5*cm, 10*cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1e3a5a")),
        ("TEXTCOLOR",  (0,0), (-1,0), TEAL),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,0), 11),
        ("BACKGROUND", (0,1), (-1,-1), MID),
        ("TEXTCOLOR",  (0,1), (0,-1), LGREY),
        ("TEXTCOLOR",  (1,1), (1,-1), colors.white),
        ("FONTSIZE",   (0,1), (-1,-1), 10),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [MID, colors.HexColor("#0a1620")]),
        ("GRID",       (0,0), (-1,-1), 0.5, colors.HexColor("#1e3a5a")),
        ("LEFTPADDING",(0,0), (-1,-1), 10),
        ("RIGHTPADDING",(0,0),(-1,-1), 10),
        ("TOPPADDING", (0,0), (-1,-1), 7),
        ("BOTTOMPADDING",(0,0),(-1,-1), 7),
        ("ROUNDEDCORNERS", [6]),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 0.8*cm))
    story.append(HRFlowable(width="100%", thickness=0.5,
                             color=colors.HexColor("#2a3a5a")))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        "<i>This is an auto-generated appointment slip. "
        "Please carry this document on your appointment day.</i>",
        ParagraphStyle("Footer", parent=styles["Normal"],
                        textColor=LGREY, fontSize=8,
                        alignment=TA_CENTER)))

    doc.build(story)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
#  LOGIN LOG PDF
# ══════════════════════════════════════════════════════════════════════════════
def generate_login_log_pdf(logs: list) -> bytes:
    """Generate a PDF listing all login events."""
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    import io
    from datetime import datetime

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                            topMargin=1.5*cm, bottomMargin=1.5*cm,
                            leftMargin=2*cm, rightMargin=2*cm)
    styles = getSampleStyleSheet()
    RED   = colors.HexColor("#ff4b4b")
    MID   = colors.HexColor("#0d1b2a")
    LGREY = colors.HexColor("#778899")

    title_s = ParagraphStyle("T", parent=styles["Title"],
                              textColor=RED, fontSize=20,
                              spaceAfter=4, alignment=TA_CENTER)
    sub_s   = ParagraphStyle("S", parent=styles["Normal"],
                              textColor=LGREY, fontSize=10,
                              alignment=TA_CENTER, spaceAfter=2)

    story = []
    story.append(Paragraph("🔑 User Login History", title_s))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%d %b %Y, %H:%M:%S')}  |  "
        f"Total Entries: {len(logs)}", sub_s))
    story.append(HRFlowable(width="100%", thickness=1, color=RED, spaceAfter=10))

    header = ["#", "Username", "Full Name", "Role", "Email", "Login Time"]
    rows   = [header]
    for i, lg in enumerate(logs, 1):
        rows.append([
            str(i),
            lg.get("username", "—"),
            lg.get("full_name", "—") or "—",
            (lg.get("role","—") or "—").title(),
            lg.get("email", "—") or "—",
            str(lg.get("logged_in_at","—"))[:16],
        ])

    col_w = [1.2*cm, 4*cm, 5*cm, 3*cm, 6*cm, 5*cm]
    tbl   = Table(rows, colWidths=col_w, repeatRows=1)
    row_colors = [MID, colors.HexColor("#0a1620")]
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1a0505")),
        ("TEXTCOLOR",  (0,0), (-1,0), RED),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,0), 9),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), row_colors),
        ("TEXTCOLOR",  (0,1), (-1,-1), colors.white),
        ("FONTSIZE",   (0,1), (-1,-1), 8),
        ("GRID",       (0,0), (-1,-1), 0.4, colors.HexColor("#1e3a5a")),
        ("LEFTPADDING",(0,0), (-1,-1), 6),
        ("RIGHTPADDING",(0,0),(-1,-1), 6),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1), 5),
        ("ALIGN",      (0,0), (-1,-1), "LEFT"),
    ]))
    story.append(tbl)
    doc.build(story)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
#  DOCTOR APPOINTMENT RECORDS PDF
# ══════════════════════════════════════════════════════════════════════════════
def generate_doctor_appointments_pdf(doctor_name: str, appointments: list, timezone_name: str | None = None) -> bytes:
    """Generate a PDF of all appointments for a doctor."""
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    import io
    from datetime import datetime

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                            topMargin=1.5*cm, bottomMargin=1.5*cm,
                            leftMargin=2*cm, rightMargin=2*cm)
    styles = getSampleStyleSheet()
    TEAL  = colors.HexColor("#00d4ff")
    MID   = colors.HexColor("#0d1b2a")
    LGREY = colors.HexColor("#778899")

    story = []
    story.append(Paragraph(f"📅 Appointment Records — Dr. {doctor_name}",
        ParagraphStyle("T", parent=styles["Title"], textColor=TEAL,
                        fontSize=18, spaceAfter=4, alignment=TA_CENTER)))
    story.append(Paragraph(
        "Generated: " + __import__('datetime').datetime.now(__import__('zoneinfo').ZoneInfo('Asia/Kolkata')).strftime('%d %b %Y, %I:%M %p') + f"  |  Total: {len(appointments)}",
        ParagraphStyle("S", parent=styles["Normal"],
                        textColor=LGREY, fontSize=9,
                        alignment=TA_CENTER, spaceAfter=2)))
    story.append(HRFlowable(width="100%", thickness=1, color=TEAL, spaceAfter=10))

    header = ["#","Patient","Date","Time","Reason","Status","Payment","Ref"]
    rows   = [header]
    for i, a in enumerate(appointments, 1):
        rows.append([
            str(i),
            a.get("patient_name","—"),
            a.get("appt_date","—"),
            a.get("appt_time","—"),
            (a.get("reason","—") or "—")[:30],
            a.get("status","—"),
            a.get("payment_mode","—"),
            (a.get("payment_ref","—") or "—")[:15],
        ])

    col_w = [1*cm,5*cm,3*cm,2.5*cm,5.5*cm,3*cm,3*cm,4*cm]
    tbl   = Table(rows, colWidths=col_w, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#0a1e30")),
        ("TEXTCOLOR",  (0,0), (-1,0), TEAL),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,0), 9),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[MID,colors.HexColor("#0a1620")]),
        ("TEXTCOLOR",  (0,1),(-1,-1), colors.white),
        ("FONTSIZE",   (0,1),(-1,-1), 8),
        ("GRID",       (0,0),(-1,-1), 0.4, colors.HexColor("#1e3a5a")),
        ("LEFTPADDING",(0,0),(-1,-1), 6),
        ("RIGHTPADDING",(0,0),(-1,-1),6),
        ("TOPPADDING", (0,0),(-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1),5),
    ]))
    story.append(tbl)
    doc.build(story)
    return buf.getvalue()