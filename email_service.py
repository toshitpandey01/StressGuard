import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import streamlit as st

# ── Shared constants ──────────────────────────────────────────────────────────
APP_NAME   = "Stress Level Detector"
BRAND_CLR  = "#00ff88"
DARK_BG    = "#06090f"
CARD_BG    = "#0d1b2a"
ACCENT_BG  = "#081a12"
BORDER_CLR = "#00ff8844"


# ── Internal: send any HTML email ─────────────────────────────────────────────
def _send(to: str, subject: str, html_body: str) -> tuple:
    """
    Low-level send. Reads smtp_email / smtp_password from st.secrets.
    Returns (True, "Sent!") or (False, "error message").
    """
    try:
        sender   = st.secrets.get("smtp_email", "")
        app_pw   = st.secrets.get("smtp_password", "")

        if not sender or not app_pw:
            return False, "SMTP not configured. Add smtp_email and smtp_password to .streamlit/secrets.toml"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[{APP_NAME}] {subject}"
        msg["From"]    = f"{APP_NAME} <{sender}>"
        msg["To"]      = to
        msg.attach(MIMEText(html_body, "html"))

        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as srv:
            srv.login(sender, app_pw)
            srv.sendmail(sender, to, msg.as_string())

        return True, "Email sent successfully!"

    except smtplib.SMTPAuthenticationError:
        return False, (
            "Gmail authentication failed. "
            "Make sure you are using an App Password, not your regular Gmail password. "
            "Enable 2-Step Verification → myaccount.google.com → Security → App Passwords."
        )
    except smtplib.SMTPException as e:
        return False, f"SMTP error: {e}"
    except Exception as e:
        return False, f"Unexpected error: {e}"


# ── Shared HTML wrapper ───────────────────────────────────────────────────────
def _wrap(content_html: str, footer_note: str = "") -> str:
    """Wraps content in a branded dark email card."""
    return f"""
    <html>
    <body style="margin:0;padding:0;background:{DARK_BG};
                 font-family:'Segoe UI',Arial,sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0"
             style="background:{DARK_BG};padding:32px 0;">
        <tr><td align="center">
          <table width="520" cellpadding="0" cellspacing="0"
                 style="background:{CARD_BG};border-radius:18px;
                        border:1px solid {BORDER_CLR};overflow:hidden;">

            <!-- Header -->
            <tr><td style="background:linear-gradient(90deg,#081a12,#0d2035);
                           padding:22px 32px;border-bottom:1px solid {BORDER_CLR};">
              <span style="font-size:1.5rem;font-weight:900;
                           color:{BRAND_CLR};">🧠 {APP_NAME}</span>
            </td></tr>

            <!-- Body -->
            <tr><td style="padding:32px;">
              {content_html}
            </td></tr>

            <!-- Footer -->
            <tr><td style="background:#060c14;padding:14px 32px;
                           border-top:1px solid #1e3a5a;text-align:center;">
              <span style="color:#445;font-size:0.72rem;">
                {footer_note or f'This is an automated message from {APP_NAME}. Do not reply.'}
              </span>
            </td></tr>

          </table>
        </td></tr>
      </table>
    </body>
    </html>
    """


# ─────────────────────────────────────────────────────────────────────────────
# 1.  OTP / VERIFICATION EMAIL
# ─────────────────────────────────────────────────────────────────────────────
def send_otp_email(email: str, otp: str,
                   name: str = "User",
                   purpose: str = "registration") -> tuple:
    """
    Send a 6-digit OTP email.
    purpose: "registration" | "password_reset" | "login_verification"
    """
    purpose_labels = {
        "registration":       "Account Registration",
        "password_reset":     "Password Reset",
        "login_verification": "Login Verification",
    }
    label = purpose_labels.get(purpose, purpose.replace("_", " ").title())

    content = f"""
    <p style="color:#ccc;font-size:1rem;margin:0 0 6px;">Hi <b style="color:white;">{name}</b>,</p>
    <p style="color:#aaa;font-size:0.9rem;margin:0 0 24px;">
        Your One-Time Password for <b style="color:{BRAND_CLR};">{label}</b>:
    </p>

    <!-- OTP Box -->
    <div style="text-align:center;margin:0 0 28px;">
      <div style="display:inline-block;background:{ACCENT_BG};
                  border:2px solid {BRAND_CLR};border-radius:14px;
                  padding:20px 40px;">
        <span style="font-size:2.8rem;font-weight:900;
                     letter-spacing:14px;color:{BRAND_CLR};">
          {otp}
        </span>
      </div>
    </div>

    <table width="100%" cellpadding="0" cellspacing="0"
           style="background:#0a1e30;border-radius:10px;
                  border:1px solid #1e3a5a;padding:14px 18px;margin-bottom:20px;">
      <tr>
        <td style="color:#aaa;font-size:0.82rem;padding:4px 0;">
          ⏱️ &nbsp;Expires in <b style="color:white;">10 minutes</b>
        </td>
      </tr>
      <tr>
        <td style="color:#aaa;font-size:0.82rem;padding:4px 0;">
          🔒 &nbsp;Do <b style="color:white;">not share</b> this OTP with anyone.
        </td>
      </tr>
      <tr>
        <td style="color:#aaa;font-size:0.82rem;padding:4px 0;">
          ❓ &nbsp;Didn't request this? Ignore this email safely.
        </td>
      </tr>
    </table>
    """
    html = _wrap(content)
    return _send(email, f"Your OTP — {label}", html)


# ─────────────────────────────────────────────────────────────────────────────
# 2.  APPOINTMENT NOTIFICATION EMAILS
# ─────────────────────────────────────────────────────────────────────────────
def send_appointment_email(to_email: str,
                           to_name: str,
                           event: str,
                           appt_details: dict) -> tuple:
    """
    Send an appointment notification.

    event values:
        "booked"    → sent to patient after booking
        "confirmed" → sent to patient when doctor accepts
        "cancelled" → sent to patient when appointment is cancelled
        "reminder"  → sent to patient 1 day before
        "new_for_doctor" → sent to doctor when patient books

    appt_details keys:
        patient_name, doctor_name, appt_date, appt_time,
        reason, payment_mode, payment_status
    """
    patient  = appt_details.get("patient_name", "Patient")
    doctor   = appt_details.get("doctor_name", "Doctor")
    date     = appt_details.get("appt_date", "—")
    time     = appt_details.get("appt_time", "—")
    reason   = appt_details.get("reason", "—") or "—"
    pay_mode = appt_details.get("payment_mode", "—")
    pay_stat = appt_details.get("payment_status", "—")

    event_cfg = {
        "booked": {
            "subject":    "Appointment Booked Successfully",
            "headline":   "✅ Appointment Confirmed!",
            "color":      "#00ff88",
            "intro":      f"Your appointment with <b>Dr. {doctor}</b> has been booked.",
        },
        "confirmed": {
            "subject":    "Your Appointment is Confirmed",
            "headline":   "🩺 Appointment Confirmed by Doctor",
            "color":      "#00d4ff",
            "intro":      f"Dr. {doctor} has confirmed your appointment.",
        },
        "cancelled": {
            "subject":    "Appointment Cancelled",
            "headline":   "❌ Appointment Cancelled",
            "color":      "#ff4b4b",
            "intro":      "Your appointment has been cancelled.",
        },
        "changed": {
            "subject":    "Appointment Change Proposed",
            "headline":   "📝 Appointment Change Proposed",
            "color":      "#aa88ff",
            "intro":      f"Dr. {doctor} proposed a new appointment schedule. Please review it in the app and confirm the updated time.",
        },
        "reassigned": {
            "subject":    "Appointment Reassigned",
            "headline":   "🔄 Appointment Reassigned",
            "color":      "#ffaa44",
            "intro":      "Your appointment has been reassigned or updated. Please review the latest appointment details in the app.",
        },
        "reminder": {
            "subject":    "Appointment Reminder — Tomorrow",
            "headline":   "⏰ Reminder: Appointment Tomorrow",
            "color":      "#f1c40f",
            "intro":      f"This is a reminder for your appointment with <b>Dr. {doctor}</b> tomorrow.",
        },
        "new_for_doctor": {
            "subject":    f"New Appointment Request from {patient}",
            "headline":   "📋 New Appointment Booked",
            "color":      "#00d4ff",
            "intro":      f"<b>{patient}</b> has booked an appointment with you.",
        },
    }

    cfg = event_cfg.get(event, event_cfg["booked"])
    clr = cfg["color"]

    content = f"""
    <p style="color:#ccc;font-size:1rem;margin:0 0 6px;">
        Hi <b style="color:white;">{to_name}</b>,
    </p>
    <p style="color:#aaa;font-size:0.9rem;margin:0 0 24px;">
        {cfg['intro']}
    </p>

    <!-- Details Card -->
    <table width="100%" cellpadding="0" cellspacing="0"
           style="background:#0a1e30;border-radius:12px;
                  border-left:4px solid {clr};
                  border:1px solid {clr}33;
                  margin-bottom:24px;">
      <tr><td style="padding:18px 20px;">
        <table width="100%" cellpadding="0" cellspacing="0">
          {"".join(f'''
          <tr>
            <td style="color:#778;font-size:0.82rem;padding:5px 0;width:40%;">{lbl}</td>
            <td style="color:white;font-size:0.88rem;font-weight:700;
                       padding:5px 0;">{val}</td>
          </tr>''' for lbl, val in [
              ("👤 Patient",        patient),
              ("🩺 Doctor",         f"Dr. {doctor}"),
              ("📅 Date",           date),
              ("🕐 Time",           time),
              ("📝 Reason",         reason),
              ("💳 Payment Mode",   pay_mode),
              ("✅ Payment Status", pay_stat),
          ])}
        </table>
      </td></tr>
    </table>

    <p style="color:#778;font-size:0.8rem;margin:0;">
        Log in to the app to view full details or manage your appointment.
    </p>
    """
    html = _wrap(content)
    return _send(to_email, cfg["subject"], html)


# ─────────────────────────────────────────────────────────────────────────────
# 3.  PASSWORD RESET EMAIL
# ─────────────────────────────────────────────────────────────────────────────
def send_password_reset_email(email: str,
                               name: str,
                               otp: str,
                               username: str = "",
                               role: str = "") -> tuple:
    """
    Send a password reset OTP email with optional verified account details.
    """
    support_email = st.secrets.get("support_email", st.secrets.get("smtp_email", "admin@stressapp.com"))
    role_label = role.title() if role else "User"
    username_html = (
        f"<tr><td style='color:#ff6688;font-size:0.82rem;padding:4px 0;'>"
        f"🪪 &nbsp;Verified account username: <b style='color:white;'>{username}</b></td></tr>"
    ) if username else ""

    content = f"""
    <p style="color:#ccc;font-size:1rem;margin:0 0 6px;">
        Hi <b style="color:white;">{name}</b>,
    </p>
    <p style="color:#aaa;font-size:0.9rem;margin:0 0 20px;">
        We received a secure recovery request for your <b style="color:white;">{role_label}</b> account.
        Use the OTP below in the app to reset your password safely.
    </p>

    <div style="text-align:center;margin:0 0 28px;">
      <div style="display:inline-block;background:#1a0505;
                  border:2px solid #ff4b4b;border-radius:14px;
                  padding:20px 40px;">
        <span style="font-size:2.8rem;font-weight:900;
                     letter-spacing:14px;color:#ff4b4b;">
          {otp}
        </span>
      </div>
    </div>

    <table width="100%" cellpadding="0" cellspacing="0"
           style="background:#1a0505;border-radius:10px;
                  border:1px solid #ff4b4b44;padding:14px 18px;margin-bottom:20px;">
      <tr><td style="color:#ff6688;font-size:0.82rem;padding:4px 0;">
        ⏱️ &nbsp;Expires in <b style="color:white;">10 minutes</b>
      </td></tr>
      {username_html}
      <tr><td style="color:#ff6688;font-size:0.82rem;padding:4px 0;">
        🔒 &nbsp;<b style="color:white;">Never share</b> this OTP — our team will never ask for it.
      </td></tr>
      <tr><td style="color:#ff6688;font-size:0.82rem;padding:4px 0;">
        🛟 &nbsp;Need more help? Contact support: <b style="color:white;">{support_email}</b>
      </td></tr>
      <tr><td style="color:#ff6688;font-size:0.82rem;padding:4px 0;">
        ⚠️ &nbsp;If you did NOT request this, you can safely ignore this email.
      </td></tr>
    </table>
    """
    html = _wrap(content, footer_note="This is a security-sensitive email. Do not forward or share it.")
    return _send(email, "Password Recovery OTP", html)


def send_account_recovery_email(email: str, name: str, username: str, otp: str, role: str) -> tuple:
    """Convenience wrapper for secure account recovery emails."""
    return send_password_reset_email(email=email, name=name, otp=otp, username=username, role=role)


# ─────────────────────────────────────────────────────────────────────────────
# 4.  STRESS ALERT EMAIL  (bonus — notify doctor of high-stress patient)
# ─────────────────────────────────────────────────────────────────────────────
def send_stress_alert_email(doctor_email: str,
                             doctor_name: str,
                             patient_name: str,
                             stress_label: str,
                             stress_level: int) -> tuple:
    """
    Notify doctor when a patient records a high/very-high stress reading.
    Call this after saving a prediction with stress_level >= 3.
    """
    level_colors = {3: "#ff8c00", 4: "#ff4b4b"}
    clr = level_colors.get(stress_level, "#ff4b4b")

    content = f"""
    <p style="color:#ccc;font-size:1rem;margin:0 0 6px;">
        Hi <b style="color:white;">Dr. {doctor_name}</b>,
    </p>
    <p style="color:#aaa;font-size:0.9rem;margin:0 0 20px;">
        Your patient <b style="color:white;">{patient_name}</b>
        just recorded a <b style="color:{clr};">high stress reading</b>.
    </p>

    <div style="text-align:center;margin:0 0 28px;">
      <div style="display:inline-block;background:#1a0505;
                  border:2px solid {clr};border-radius:14px;
                  padding:16px 36px;">
        <div style="color:{clr};font-size:1.6rem;font-weight:900;">
          ⚠️ {stress_label}
        </div>
        <div style="color:#aaa;font-size:0.82rem;margin-top:6px;">
          Stress Level {stress_level} / 4
        </div>
      </div>
    </div>

    <p style="color:#aaa;font-size:0.85rem;margin:0;">
      Please log in to the Doctor Portal to review their history
      and reach out via chat if needed.
    </p>
    """
    html = _wrap(content)
    return _send(doctor_email, f"⚠️ High Stress Alert — {patient_name}", html)