

from fpdf import FPDF
from datetime import datetime
from time_utils import format_now


# ── Stress level colors (RGB) ─────────────────────────────────────────────────
STRESS_COLORS = {
    0: (46,  204, 113),   # green
    1: (241, 196,  15),   # yellow
    2: (230, 126,  34),   # orange
    3: (231,  76,  60),   # red
    4: (142,  68, 173),   # purple
}
STRESS_LABELS = {
    0: "Safe",
    1: "Low Stress",
    2: "Medium Stress",
    3: "High Stress",
    4: "Very High Stress",
}

APP_NAME   = "Stress Level Detector"
APP_TAG    = "AI-Powered Mental Wellness Monitoring Platform"
WATERMARK  = "CONFIDENTIAL — STRESS LEVEL DETECTOR"


class _StressReportPDF(FPDF):
    def __init__(self, patient_name, generated_by, role):
        super().__init__()
        self.patient_name  = patient_name
        self.generated_by  = generated_by
        self.role          = role
        self.gen_dt        = format_now(fmt="%d %b %Y, %I:%M %p")
        self.set_auto_page_break(auto=True, margin=18)

    # ── Header ────────────────────────────────────────────────────────────────
    def header(self):
        # Dark top bar
        self.set_fill_color(10, 22, 40)
        self.rect(0, 0, 210, 22, "F")
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(0, 212, 255)
        self.set_xy(8, 5)
        self.cell(120, 12, f"  {APP_NAME}", ln=0)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(170, 180, 200)
        self.set_xy(135, 8)
        self.cell(70, 8, self.gen_dt, align="R", ln=0)
        self.ln(24)

    # ── Footer ────────────────────────────────────────────────────────────────
    def footer(self):
        self.set_y(-14)
        self.set_fill_color(10, 22, 40)
        self.rect(0, self.get_y(), 210, 20, "F")
        self.set_font("Helvetica", "I", 7.5)
        self.set_text_color(85, 102, 120)
        self.cell(0, 8,
                  f"Page {self.page_no()} | {APP_TAG} | Confidential",
                  align="C")

    # ── Watermark ─────────────────────────────────────────────────────────────
    def watermark(self):
        self.set_font("Helvetica", "B", 36)
        self.set_text_color(220, 230, 245)
        # Save state
        with self.local_context(fill_opacity=0.07):
            self.set_xy(15, 110)
            self.rotate(40, x=105, y=148)
            self.cell(180, 18, WATERMARK, align="C")
            self.rotate(0)

    # ── Section heading ───────────────────────────────────────────────────────
    def section(self, title, accent=(0, 212, 255)):
        self.set_fill_color(*accent)
        self.rect(10, self.get_y(), 3, 7, "F")
        self.set_xy(15, self.get_y())
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(255, 255, 255)
        self.cell(0, 7, title, ln=1)
        self.ln(2)

    # ── Labelled row ──────────────────────────────────────────────────────────
    def row(self, label, value, accent=(0, 212, 255)):
        self.set_font("Helvetica", "", 9)
        self.set_text_color(170, 180, 200)
        self.set_x(14)
        self.cell(50, 6, label + ":", ln=0)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 9)
        self.cell(0, 6, str(value), ln=1)


# ── Public API ────────────────────────────────────────────────────────────────
def generate_stress_report(patient_info: dict, predictions: list,
                            doctor_info: dict = None,
                            generated_by: str = "Patient",
                            role: str = "patient") -> bytes:
    """
    Build a professional PDF stress report.
    Returns raw PDF bytes.
    """
    pat_name = patient_info.get("full_name", "Patient")
    pdf = _StressReportPDF(pat_name, generated_by, role)
    pdf.add_page()
    pdf.watermark()

    # ── Cover block ───────────────────────────────────────────────────────────
    pdf.set_fill_color(13, 27, 42)
    pdf.rect(10, 26, 190, 38, "F")
    pdf.set_xy(14, 29)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(0, 255, 136)
    pdf.cell(0, 9, "Stress Level Analysis Report", ln=1)
    pdf.set_x(14)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(170, 180, 200)
    pdf.cell(0, 6, APP_TAG, ln=1)
    pdf.set_x(14)
    pdf.set_text_color(100, 120, 140)
    pdf.set_font("Helvetica", "I", 8)
    pdf.cell(0, 5, f"Generated: {pdf.gen_dt}  |  Role: {role.title()}",ln=1)
    pdf.ln(6)

    # ── Patient info ──────────────────────────────────────────────────────────
    pdf.section("Patient Information", accent=(0, 255, 136))
    pdf.row("Full Name",  patient_info.get("full_name", "—"))
    pdf.row("Username",   "@" + patient_info.get("username", "—"))
    pdf.row("Email",      patient_info.get("email", "—"))
    pdf.row("Phone",      patient_info.get("phone", "—"))
    pdf.row("Joined",     str(patient_info.get("created_at", "—"))[:10])
    pdf.ln(4)

    # ── Doctor info (if available) ────────────────────────────────────────────
    if doctor_info:
        pdf.section("Assigned Doctor", accent=(0, 212, 255))
        pdf.row("Doctor",      "Dr. " + doctor_info.get("full_name", "—"))
        pdf.row("Email",       doctor_info.get("email", "—"))
        pdf.row("Phone",       doctor_info.get("phone", "—"))
        pdf.ln(4)

    # ── Summary statistics ────────────────────────────────────────────────────
    if predictions:
        levels = [int(p["stress_level"]) for p in predictions if p.get("stress_level") is not None]
        avg    = sum(levels) / len(levels)
        latest = predictions[0]["stress_level"]
        hi_cnt = sum(1 for l in levels if l >= 3)

        pdf.section("Summary Statistics", accent=(255, 170, 68))
        pdf.row("Total Predictions", str(len(predictions)))
        pdf.row("Average Stress",    f"{avg:.2f} / 4")
        pdf.row("Latest Reading",
                STRESS_LABELS.get(latest, "—") + f" (Level {latest})")
        pdf.row("High/Critical Count", str(hi_cnt))
        pdf.ln(4)

        # ── Colour-coded stress badge for latest ──────────────────────────────
        clr = STRESS_COLORS.get(latest, (255, 255, 255))
        pdf.set_fill_color(*clr)
        pdf.set_text_color(10, 10, 10)
        pdf.set_font("Helvetica", "B", 11)
        x_badge = 14
        pdf.set_xy(x_badge, pdf.get_y())
        pdf.cell(80, 10,
                 f"  Latest: {STRESS_LABELS.get(latest,'')} (L{latest})  ",
                 fill=True, border=0, align="C", ln=1)
        pdf.ln(5)

    # ── Prediction history table ───────────────────────────────────────────────
    if predictions:
        pdf.section("Prediction History (Latest 20)", accent=(170, 136, 255))
        # Table header
        pdf.set_fill_color(13, 27, 42)
        pdf.set_text_color(0, 212, 255)
        pdf.set_font("Helvetica", "B", 7.5)
        col_w = [26, 20, 12, 14, 12, 14, 12, 14, 12, 22]
        headers = ["Timestamp","Stress","Age","ScrnTm","RR","BT","LM","BO","REM","Score"]
        pdf.set_x(10)
        for h, w in zip(headers, col_w):
            pdf.cell(w, 6, h, border=1, align="C", fill=True)
        pdf.ln()

        def _fv(val, dec=0):
            try: return f"{float(val):.{dec}f}" if val is not None else "—"
            except: return "—"

        pdf.set_font("Helvetica", "", 7)
        for i, p in enumerate(predictions[:20]):
            ts    = str(p.get("predicted_at", ""))[:16]
            lv    = p.get("stress_level", 0) or 0
            clr   = STRESS_COLORS.get(lv, (255, 255, 255))
            pdf.set_fill_color(*(c // 4 for c in clr))
            pdf.set_text_color(255, 255, 255)
            age_v = p.get("age") or p.get("Age") or p.get("sr")
            scr_v = p.get("screen_time") or p.get("ScreenTimeHours")
            row_vals = [
                ts,
                STRESS_LABELS.get(lv, "?")[:12],
                _fv(age_v, 0),
                _fv(scr_v, 1),
                _fv(p.get("rr"), 0),
                _fv(p.get("bt"), 1),
                _fv(p.get("lm"), 0),
                _fv(p.get("bo"), 1),
                _fv(p.get("rem"), 0),
                f"L{lv}",
            ]
            pdf.set_x(10)
            for v, w in zip(row_vals, col_w):
                pdf.cell(w, 5.5, str(v), border=1, align="C",
                         fill=(i % 2 == 1))
            pdf.ln()
        pdf.ln(5)

    # ── Disclaimer ────────────────────────────────────────────────────────────
    pdf.section("Disclaimer", accent=(85, 102, 120))
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(140, 150, 170)
    pdf.set_x(14)
    pdf.multi_cell(182, 5,
        "This report is generated by an AI-based Stress Level Detector "
        "for informational purposes only. It does not constitute medical "
        "advice. Please consult a qualified healthcare professional for "
        "any health concerns. All data is confidential.")

    return bytes(pdf.output())