import os
import sqlite3
import hashlib
import base64
from datetime import datetime, timedelta, date

from time_utils import sanitize_timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "users.db")

# ── Status constants ──────────────────────────────────────────────────────────
APPT_STATUS_PENDING          = "Pending"
APPT_STATUS_ACCEPTED         = "Accepted"
APPT_STATUS_REJECTED         = "Rejected"
APPT_STATUS_DOCTOR_PROPOSED  = "DoctorProposed"
APPT_STATUS_PATIENT_CONFIRM  = "PatientConfirm"
APPT_STATUS_CONFIRMED        = "Confirmed"
APPT_STATUS_CANCELLED        = "Cancelled"
APPT_STATUS_COMPLETED        = "Completed"
APPT_STATUS_RESCHEDULED      = "Rescheduled"

APPT_ACTIVE_STATUSES = [
    APPT_STATUS_PENDING, APPT_STATUS_ACCEPTED,
    APPT_STATUS_DOCTOR_PROPOSED, APPT_STATUS_PATIENT_CONFIRM,
    APPT_STATUS_CONFIRMED,
]

TICKET_STATUS_OPEN     = "Open"
TICKET_STATUS_REVIEWED = "Reviewed"
TICKET_STATUS_CLOSED   = "Closed"


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def hash_password(p: str) -> str:
    return hashlib.sha256(p.encode()).hexdigest()


def normalize_dob(dob_value):
    """Normalize DOB to YYYY-MM-DD text."""
    if dob_value in (None, "", 0):
        return None
    if isinstance(dob_value, date):
        return dob_value.strftime("%Y-%m-%d")
    raw = str(dob_value).strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw[:10], fmt).strftime("%Y-%m-%d")
        except Exception:
            pass
    return raw[:10]


def calculate_age_from_dob(dob_value, on_date=None):
    dob_norm = normalize_dob(dob_value)
    if not dob_norm:
        return None
    try:
        dob_dt = datetime.strptime(dob_norm, "%Y-%m-%d").date()
    except Exception:
        return None
    ref = on_date or date.today()
    age = ref.year - dob_dt.year - ((ref.month, ref.day) < (dob_dt.month, dob_dt.day))
    return age if 0 <= age <= 120 else None


def update_user_dob(user_id, dob):
    dob_norm = normalize_dob(dob)
    conn = get_connection(); c = conn.cursor()
    c.execute("UPDATE users SET dob=? WHERE id=?", (dob_norm, user_id))
    conn.commit(); conn.close()


def get_user_age(user_id):
    user = get_user_by_id(user_id)
    if not user:
        return None
    return calculate_age_from_dob(user.get("dob"))


def init_db():
    conn = get_connection()
    c = conn.cursor()

    # ── USERS ──────────────────────────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        username       TEXT UNIQUE NOT NULL,
        password       TEXT NOT NULL,
        plain_password TEXT,
        role           TEXT NOT NULL,
        full_name      TEXT,
        email          TEXT,
        phone          TEXT,
        doctor_id      INTEGER,
        profile_photo  TEXT,
        bio            TEXT,
        dob            TEXT,
        timezone       TEXT DEFAULT 'Asia/Kolkata',
        is_verified    INTEGER DEFAULT 0,
        created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    for col, typ in [("profile_photo","TEXT"), ("bio","TEXT"),
                     ("plain_password","TEXT"), ("dob","TEXT"),
                     ("timezone","TEXT DEFAULT 'Asia/Kolkata'"), ("is_verified","INTEGER DEFAULT 0")]:
        try: c.execute(f"ALTER TABLE users ADD COLUMN {col} {typ}")
        except: pass

    # ── PREDICTIONS ────────────────────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS predictions (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id   INTEGER NOT NULL,
        sr REAL, rr REAL, bt REAL, lm REAL,
        bo REAL, rem REAL, sh REAL, hr REAL,
        age REAL, screen_time REAL,
        stress_level INTEGER,
        stress_label TEXT,
        predicted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (patient_id) REFERENCES users(id)
    )''')
    # Migrate new feature columns
    for _col in ['age', 'screen_time']:
        try: c.execute(f'ALTER TABLE predictions ADD COLUMN {_col} REAL')
        except: pass

    # ── DOCTOR NOTES ──────────────────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS doctor_notes (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        doctor_id  INTEGER NOT NULL,
        patient_id INTEGER NOT NULL,
        note       TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ── DOCTOR SELF NOTES ─────────────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS doctor_self_notes (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        doctor_id  INTEGER NOT NULL,
        title      TEXT,
        content    TEXT,
        color      TEXT DEFAULT 'Ocean Blue',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ── PATIENT PERSONAL NOTES ────────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS patient_notes (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        title      TEXT,
        content    TEXT,
        color      TEXT DEFAULT 'Ocean Blue',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ── CHAT MESSAGES ─────────────────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS chat_messages (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id   INTEGER NOT NULL,
        receiver_id INTEGER NOT NULL,
        message     TEXT NOT NULL,
        is_read     INTEGER DEFAULT 0,
        is_deleted  INTEGER DEFAULT 0,
        edited      INTEGER DEFAULT 0,
        sent_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    for col, typ in [("is_deleted","INTEGER DEFAULT 0"),("edited","INTEGER DEFAULT 0")]:
        try: c.execute(f"ALTER TABLE chat_messages ADD COLUMN {col} {typ}")
        except: pass

    # ── PATIENT CHECKLIST ─────────────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS patient_checklist (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        doctor_id  INTEGER NOT NULL,
        patient_id INTEGER NOT NULL,
        item_text  TEXT NOT NULL,
        category   TEXT DEFAULT 'Daily',
        is_done    INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    try: c.execute("ALTER TABLE patient_checklist ADD COLUMN category TEXT DEFAULT 'Daily'")
    except: pass

    # ── DOCTOR PORTFOLIO ──────────────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS doctor_portfolio (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        doctor_id       INTEGER UNIQUE NOT NULL,
        specialization  TEXT,
        qualification   TEXT,
        experience_yrs  INTEGER DEFAULT 0,
        hospital        TEXT,
        about           TEXT,
        achievements    TEXT,
        languages       TEXT,
        consultation_fee TEXT,
        availability    TEXT,
        updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (doctor_id) REFERENCES users(id)
    )''')

    # ── NOTIFICATIONS ─────────────────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS notifications (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER NOT NULL,
        title       TEXT NOT NULL,
        message     TEXT NOT NULL,
        notif_type  TEXT DEFAULT 'info',
        category    TEXT DEFAULT 'general',
        is_read     INTEGER DEFAULT 0,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    # Migrate: add category column to existing DBs
    try:
        c.execute("ALTER TABLE notifications ADD COLUMN category TEXT DEFAULT 'general'")
    except Exception:
        pass
    # Fast unread lookup index
    c.execute("""CREATE INDEX IF NOT EXISTS idx_notif_user_cat
                 ON notifications(user_id, category, is_read)""")

    # ── OTP TOKENS ────────────────────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS otp_tokens (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        email      TEXT NOT NULL,
        otp        TEXT NOT NULL,
        purpose    TEXT DEFAULT 'register',
        expires_at TIMESTAMP NOT NULL,
        used       INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ── STRESS ALERTS ────────────────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS stress_alerts (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id   INTEGER NOT NULL,
        doctor_id    INTEGER,
        stress_level INTEGER NOT NULL,
        stress_label TEXT NOT NULL,
        is_read      INTEGER DEFAULT 0,
        created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    conn.commit()

    # Default admin
    c.execute("SELECT id FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute('''INSERT INTO users (username,password,plain_password,role,
                     full_name,email,is_verified) VALUES (?,?,?,?,?,?,1)''',
                  ('admin', hash_password('admin123'), 'admin123',
                   'admin', 'System Administrator', 'admin@stressapp.com'))
        conn.commit()
    conn.close()


# ── AUTH ──────────────────────────────────────────────────────────────────────
def authenticate_user(username, password, role_filter=None):
    conn = get_connection(); c = conn.cursor()
    if role_filter:
        c.execute("SELECT * FROM users WHERE username=? AND password=? AND role=?",
                  (username, hash_password(password), role_filter))
    else:
        c.execute("SELECT * FROM users WHERE username=? AND password=?",
                  (username, hash_password(password)))
    row = c.fetchone(); conn.close()
    return dict(row) if row else None


def register_user(username, password, role, full_name, email, phone,
                  doctor_id=None, profile_photo=None, dob=None,
                  timezone="Asia/Kolkata", is_verified=0):
    conn = get_connection(); c = conn.cursor()
    dob_norm = normalize_dob(dob)
    try:
        c.execute("""INSERT INTO users
            (username,password,plain_password,role,full_name,email,
             phone,doctor_id,profile_photo,dob,timezone,is_verified)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (username, hash_password(password), password,
                   role, full_name, email, phone, doctor_id,
                   profile_photo, dob_norm, sanitize_timezone(timezone), is_verified))
        conn.commit(); conn.close()
        return True, "Registration successful!"
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Username already exists."

# ── OTP ───────────────────────────────────────────────────────────────────────
def create_otp(email: str, purpose: str = "register") -> str:
    import random
    otp = str(random.randint(100000, 999999))
    expires = datetime.utcnow() + timedelta(minutes=10)
    conn = get_connection(); c = conn.cursor()
    c.execute("UPDATE otp_tokens SET used=1 WHERE email=? AND purpose=? AND used=0",
              (email, purpose))
    c.execute("INSERT INTO otp_tokens (email,otp,purpose,expires_at) VALUES (?,?,?,?)",
              (email, otp, purpose, expires.strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit(); conn.close()
    return otp


def verify_otp(email: str, otp: str, purpose: str = "register") -> bool:
    conn = get_connection(); c = conn.cursor()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("""SELECT id FROM otp_tokens
                 WHERE email=? AND otp=? AND purpose=?
                   AND used=0 AND expires_at > ?""",
              (email, otp, purpose, now))
    row = c.fetchone()
    if row:
        c.execute("UPDATE otp_tokens SET used=1 WHERE id=?", (row["id"],))
        conn.commit()
    conn.close()
    return bool(row)


def send_otp_email(email: str, otp: str, name: str = "User",
                   purpose: str = "register") -> tuple:
    try:
        import smtplib, ssl
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        import streamlit as st
        sender  = st.secrets.get("smtp_email", "")
        app_pw  = st.secrets.get("smtp_password", "")
        if not sender or not app_pw:
            return False, "SMTP not configured in secrets.toml"
        subject = "Your OTP — Stress Level Detector"
        body = f"""
        <html><body style="font-family:Arial,sans-serif;background:#06090f;color:white;">
        <div style="max-width:480px;margin:auto;background:#0d1b2a;border-radius:16px;
                    padding:32px;border:1px solid #00ff8844;">
          <h2 style="color:#00ff88;text-align:center;">🧠 Stress Level Detector</h2>
          <p>Hi <b>{name}</b>,</p>
          <p>Your OTP for <b>{purpose}</b> is:</p>
          <div style="text-align:center;margin:24px 0;">
            <span style="font-size:2.5rem;font-weight:900;letter-spacing:12px;
                         color:#00ff88;background:#081a12;padding:16px 32px;
                         border-radius:12px;border:2px solid #00ff88;">{otp}</span>
          </div>
          <p style="color:#aaa;font-size:0.85rem;">
            ⏱️ This OTP expires in <b>10 minutes</b>.<br>Do not share it with anyone.
          </p>
        </div></body></html>"""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject; msg["From"] = sender; msg["To"] = email
        msg.attach(MIMEText(body, "html"))
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as srv:
            srv.login(sender, app_pw)
            srv.sendmail(sender, email, msg.as_string())
        return True, "OTP sent successfully!"
    except Exception as e:
        return False, f"Email error: {e}"


# ── PROFILE ───────────────────────────────────────────────────────────────────
def encode_photo(photo_bytes, mime_type="image/png"):
    b64 = base64.b64encode(photo_bytes).decode()
    return f"data:{mime_type};base64,{b64}"

def update_profile_photo(user_id, photo_bytes, mime_type="image/png"):
    uri = encode_photo(photo_bytes, mime_type)
    conn = get_connection(); c = conn.cursor()
    c.execute("UPDATE users SET profile_photo=? WHERE id=?", (uri, user_id))
    conn.commit(); conn.close(); return uri

def delete_profile_photo(user_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("UPDATE users SET profile_photo=NULL WHERE id=?", (user_id,))
    conn.commit(); conn.close()

def update_bio(user_id, bio):
    conn = get_connection(); c = conn.cursor()
    c.execute("UPDATE users SET bio=? WHERE id=?", (bio, user_id))
    conn.commit(); conn.close()

def update_user_profile(user_id, full_name=None, email=None, phone=None, dob=None, timezone=None):
    conn = get_connection(); c = conn.cursor()
    updates = []
    params = []
    if full_name is not None:
        updates.append("full_name=?")
        params.append(full_name)
    if email is not None:
        updates.append("email=?")
        params.append(email)
    if phone is not None:
        updates.append("phone=?")
        params.append(phone)
    if dob is not None:
        updates.append("dob=?")
        params.append(normalize_dob(dob))
    if timezone is not None:
        updates.append("timezone=?")
        params.append(sanitize_timezone(timezone))
    if updates:
        params.append(user_id)
        c.execute(f"UPDATE users SET {', '.join(updates)} WHERE id=?", tuple(params))
    conn.commit(); conn.close()

def change_password(user_id, new_password):
    conn = get_connection(); c = conn.cursor()
    c.execute("UPDATE users SET password=?, plain_password=? WHERE id=?",
              (hash_password(new_password), new_password, user_id))
    conn.commit(); conn.close()

def get_user_by_id(user_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id=?", (user_id,))
    row = c.fetchone(); conn.close()
    return dict(row) if row else None

def get_user_by_email(email):
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT * FROM users WHERE email=?", (email,))
    row = c.fetchone(); conn.close()
    return dict(row) if row else None


def _normalize_phone(phone: str) -> str:
    return "".join(ch for ch in str(phone or "") if ch.isdigit())


def find_user_for_recovery(email, phone, role, username="", full_name=""):
    """Verify identity for password recovery without exposing sensitive data."""
    email = str(email or "").strip().lower()
    phone_norm = _normalize_phone(phone)
    username = str(username or "").strip()
    full_name = str(full_name or "").strip().lower()

    if not email or not role:
        return None

    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT * FROM users WHERE LOWER(email)=? AND role=?", (email, role))
    candidates = [dict(r) for r in c.fetchall()]
    conn.close()

    for user in candidates:
        stored_phone = _normalize_phone(user.get("phone"))
        stored_name = str(user.get("full_name") or "").strip().lower()
        stored_username = str(user.get("username") or "").strip()

        if phone_norm and stored_phone != phone_norm:
            continue
        if username and stored_username.lower() != username.lower():
            continue
        if full_name and stored_name != full_name:
            continue
        return user
    return None


# ── USER QUERIES ──────────────────────────────────────────────────────────────
def username_exists(username: str) -> bool:
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT 1 FROM users WHERE username=?", (username.strip(),))
    found = c.fetchone() is not None
    conn.close(); return found

def get_all_doctors():
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT * FROM users WHERE role='doctor' ORDER BY full_name")
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return rows

def get_all_patients():
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT * FROM users WHERE role='patient' ORDER BY full_name")
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return rows

def get_all_users():
    conn = get_connection(); c = conn.cursor()
    c.execute("""SELECT id,username,plain_password,role,full_name,
                        email,phone,dob,created_at
                 FROM users WHERE role!='admin' ORDER BY role,full_name""")
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return rows

def delete_user(user_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit(); conn.close()

def get_patients_by_doctor(doctor_id):
    """Get patients assigned via legacy doctor_id OR via patient_doctors table."""
    conn = get_connection(); c = conn.cursor()
    c.execute("""SELECT DISTINCT u.* FROM users u
                 LEFT JOIN patient_doctors pd ON pd.patient_id=u.id AND pd.doctor_id=?
                 WHERE u.role='patient' AND (u.doctor_id=? OR pd.doctor_id=?)
                 ORDER BY u.full_name""",
              (doctor_id, doctor_id, doctor_id))
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return rows

def assign_doctor_to_patient(patient_id, doctor_id):
    """Legacy single-doctor assignment + add to patient_doctors table."""
    conn = get_connection(); c = conn.cursor()
    c.execute("UPDATE users SET doctor_id=? WHERE id=?", (doctor_id, patient_id))
    # Also insert into patient_doctors if not exists
    c.execute("""INSERT OR IGNORE INTO patient_doctors (patient_id, doctor_id)
                 VALUES (?,?)""", (patient_id, doctor_id))
    conn.commit(); conn.close()

def get_doctor_of_patient(patient_id):
    """Get primary (legacy) doctor."""
    conn = get_connection(); c = conn.cursor()
    c.execute("""SELECT u.* FROM users u
                 JOIN users p ON p.doctor_id=u.id
                 WHERE p.id=?""", (patient_id,))
    row = c.fetchone(); conn.close()
    return dict(row) if row else None

def admin_reset_password(user_id, new_password):
    conn = get_connection(); c = conn.cursor()
    c.execute("UPDATE users SET password=?, plain_password=? WHERE id=?",
              (hash_password(new_password), new_password, user_id))
    conn.commit(); conn.close()


# ── PREDICTIONS ───────────────────────────────────────────────────────────────
def save_prediction(patient_id, features, stress_level, stress_label):
    """Save a prediction. Supports both old 8-feature and new 9-feature schemas."""
    conn = get_connection(); c = conn.cursor()
    if len(features) == 9:
        # New schema: Age, ScreenTimeHours, rr, bt, lm, bo, rem, sh, hr
        age, screen_time, rr, bt, lm, bo, rem, sh, hr = features
        c.execute('''INSERT INTO predictions
                     (patient_id,age,screen_time,rr,bt,lm,bo,rem,sh,hr,stress_level,stress_label)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                  (patient_id, age, screen_time, rr, bt, lm, bo, rem, sh, hr,
                   stress_level, stress_label))
    else:
        # Legacy 8-feature schema: sr, rr, bt, lm, bo, rem, sh, hr
        c.execute('''INSERT INTO predictions
                     (patient_id,sr,rr,bt,lm,bo,rem,sh,hr,stress_level,stress_label)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                  (patient_id, *features, stress_level, stress_label))
    conn.commit(); conn.close()

def get_predictions_by_patient(patient_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("""SELECT p.*, p.age AS Age, p.screen_time AS ScreenTimeHours
                 FROM predictions p
                 WHERE p.patient_id=?
                 ORDER BY p.predicted_at DESC""",
              (patient_id,))
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return rows

def get_all_predictions():
    conn = get_connection(); c = conn.cursor()
    c.execute("""SELECT p.*, p.age AS Age, p.screen_time AS ScreenTimeHours,
                        u.full_name,u.username
                 FROM predictions p
                 JOIN users u ON p.patient_id=u.id
                 ORDER BY p.predicted_at DESC""")
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return rows

def get_predictions_by_doctor_patients(doctor_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("""SELECT p.*, p.age AS Age, p.screen_time AS ScreenTimeHours,
                        u.full_name,u.username
                 FROM predictions p
                 JOIN users u ON p.patient_id=u.id
                 WHERE u.doctor_id=? ORDER BY p.predicted_at DESC""",
              (doctor_id,))
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return rows


# ── DOCTOR NOTES ──────────────────────────────────────────────────────────────
def add_doctor_note(doctor_id, patient_id, note):
    conn = get_connection(); c = conn.cursor()
    c.execute("INSERT INTO doctor_notes (doctor_id,patient_id,note) VALUES (?,?,?)",
              (doctor_id, patient_id, note))
    conn.commit(); conn.close()

def get_notes_for_patient(patient_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("""SELECT dn.*,u.full_name as doctor_name FROM doctor_notes dn
                 JOIN users u ON dn.doctor_id=u.id WHERE dn.patient_id=?
                 ORDER BY dn.created_at DESC""", (patient_id,))
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return rows

def delete_doctor_note(note_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("DELETE FROM doctor_notes WHERE id=?", (note_id,))
    conn.commit(); conn.close()


# ── DOCTOR SELF NOTES ─────────────────────────────────────────────────────────
NOTE_COLOR_MAP = {
    "Forest Green":  "#1a3a2a",
    "Ocean Blue":    "#1a2a3a",
    "Royal Purple":  "#2a1a3a",
    "Sunset Orange": "#3a2a1a",
    "Crimson Red":   "#3a1a1a",
}
NOTE_ACCENT_MAP = {
    "Forest Green":  "#00ff88",
    "Ocean Blue":    "#00d4ff",
    "Royal Purple":  "#aa88ff",
    "Sunset Orange": "#ffaa44",
    "Crimson Red":   "#ff6688",
}

def add_doctor_self_note(doctor_id, title, content, color="Ocean Blue"):
    conn = get_connection(); c = conn.cursor()
    c.execute("INSERT INTO doctor_self_notes (doctor_id,title,content,color) VALUES (?,?,?,?)",
              (doctor_id, title, content, color))
    conn.commit(); conn.close()

def get_doctor_self_notes(doctor_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT * FROM doctor_self_notes WHERE doctor_id=? ORDER BY created_at DESC",
              (doctor_id,))
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return rows

def delete_doctor_self_note(note_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("DELETE FROM doctor_self_notes WHERE id=?", (note_id,))
    conn.commit(); conn.close()


# ── PATIENT PERSONAL NOTES ────────────────────────────────────────────────────
def add_patient_note(patient_id, title, content, color="Ocean Blue"):
    conn = get_connection(); c = conn.cursor()
    c.execute("INSERT INTO patient_notes (patient_id,title,content,color) VALUES (?,?,?,?)",
              (patient_id, title, content, color))
    conn.commit(); conn.close()

def get_patient_notes(patient_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT * FROM patient_notes WHERE patient_id=? ORDER BY created_at DESC",
              (patient_id,))
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return rows

def update_patient_note(note_id, title, content, color):
    conn = get_connection(); c = conn.cursor()
    c.execute("""UPDATE patient_notes SET title=?,content=?,color=?,
                 updated_at=CURRENT_TIMESTAMP WHERE id=?""",
              (title, content, color, note_id))
    conn.commit(); conn.close()

def delete_patient_note(note_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("DELETE FROM patient_notes WHERE id=?", (note_id,))
    conn.commit(); conn.close()


# ── CHAT ──────────────────────────────────────────────────────────────────────
def send_message(sender_id, receiver_id, message):
    conn = get_connection(); c = conn.cursor()
    c.execute("INSERT INTO chat_messages (sender_id,receiver_id,message) VALUES (?,?,?)",
              (sender_id, receiver_id, message))
    conn.commit(); conn.close()

def get_chat_messages(user1_id, user2_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("""SELECT cm.*,
                        s.full_name     as sender_name,
                        s.role          as sender_role,
                        s.profile_photo as sender_photo
                 FROM chat_messages cm
                 JOIN users s ON cm.sender_id=s.id
                 WHERE ((cm.sender_id=? AND cm.receiver_id=?)
                     OR (cm.sender_id=? AND cm.receiver_id=?))
                   AND cm.is_deleted=0
                 ORDER BY cm.sent_at ASC""",
              (user1_id, user2_id, user2_id, user1_id))
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return rows

def mark_messages_read(sender_id, receiver_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("UPDATE chat_messages SET is_read=1 WHERE sender_id=? AND receiver_id=?",
              (sender_id, receiver_id))
    conn.commit(); conn.close()

def get_unread_count(receiver_id, sender_id=None):
    conn = get_connection(); c = conn.cursor()
    if sender_id:
        c.execute("""SELECT COUNT(*) FROM chat_messages
                     WHERE receiver_id=? AND sender_id=?
                       AND is_read=0 AND is_deleted=0""",
                  (receiver_id, sender_id))
    else:
        c.execute("""SELECT COUNT(*) FROM chat_messages
                     WHERE receiver_id=? AND is_read=0 AND is_deleted=0""",
                  (receiver_id,))
    cnt = c.fetchone()[0]; conn.close(); return cnt

def unsend_message(message_id, sender_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT sender_id,sent_at FROM chat_messages WHERE id=?", (message_id,))
    row = c.fetchone()
    if not row: conn.close(); return False, "Message not found."
    if row["sender_id"] != sender_id: conn.close(); return False, "Not your message."
    try:
        dt   = datetime.strptime(str(row["sent_at"])[:19], "%Y-%m-%d %H:%M:%S")
        diff = (datetime.utcnow() - dt).total_seconds()
        if diff > 300: conn.close(); return False, "Cannot unsend after 5 minutes."
    except: pass
    c.execute("UPDATE chat_messages SET is_deleted=1 WHERE id=?", (message_id,))
    conn.commit(); conn.close(); return True, "Message unsent."

def edit_message(message_id, sender_id, new_text):
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT sender_id,sent_at FROM chat_messages WHERE id=?", (message_id,))
    row = c.fetchone()
    if not row: conn.close(); return False, "Message not found."
    if row["sender_id"] != sender_id: conn.close(); return False, "Not your message."
    try:
        dt   = datetime.strptime(str(row["sent_at"])[:19], "%Y-%m-%d %H:%M:%S")
        diff = (datetime.utcnow() - dt).total_seconds()
        if diff > 300: conn.close(); return False, "Cannot edit after 5 minutes."
    except: pass
    c.execute("UPDATE chat_messages SET message=?,edited=1 WHERE id=?",
              (new_text, message_id))
    conn.commit(); conn.close(); return True, "Message edited."


# ── PATIENT CHECKLIST ─────────────────────────────────────────────────────────
CHECKLIST_CATEGORIES = ["Daily", "Weekly", "Monthly"]

def add_checklist_item(doctor_id, patient_id, item_text, category="Daily"):
    conn = get_connection(); c = conn.cursor()
    c.execute("""INSERT INTO patient_checklist
                 (doctor_id,patient_id,item_text,category)
                 VALUES (?,?,?,?)""",
              (doctor_id, patient_id, item_text, category))
    conn.commit(); conn.close()

def get_checklist(doctor_id, patient_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("""SELECT * FROM patient_checklist
                 WHERE doctor_id=? AND patient_id=?
                 ORDER BY category,created_at""",
              (doctor_id, patient_id))
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return rows

def get_checklist_for_patient(patient_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("""SELECT pc.*,u.full_name as doctor_name
                 FROM patient_checklist pc
                 JOIN users u ON pc.doctor_id=u.id
                 WHERE pc.patient_id=?
                 ORDER BY pc.category,pc.created_at""", (patient_id,))
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return rows

def toggle_checklist_item(item_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("UPDATE patient_checklist SET is_done=1-is_done WHERE id=?", (item_id,))
    conn.commit(); conn.close()

def delete_checklist_item(item_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("DELETE FROM patient_checklist WHERE id=?", (item_id,))
    conn.commit(); conn.close()

def get_checklist_pending_count(patient_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("""SELECT COUNT(*) FROM patient_checklist
                 WHERE patient_id=? AND is_done=0""", (patient_id,))
    cnt = c.fetchone()[0]; conn.close(); return cnt


# ── DOCTOR PORTFOLIO ──────────────────────────────────────────────────────────
def upsert_doctor_portfolio(doctor_id, specialization="", qualification="",
                             experience_yrs=0, hospital="", about="",
                             achievements="", languages="",
                             consultation_fee="", availability=""):
    conn = get_connection(); c = conn.cursor()
    c.execute("""INSERT INTO doctor_portfolio
                 (doctor_id,specialization,qualification,experience_yrs,
                  hospital,about,achievements,languages,consultation_fee,availability)
                 VALUES (?,?,?,?,?,?,?,?,?,?)
                 ON CONFLICT(doctor_id) DO UPDATE SET
                   specialization=excluded.specialization,
                   qualification=excluded.qualification,
                   experience_yrs=excluded.experience_yrs,
                   hospital=excluded.hospital,
                   about=excluded.about,
                   achievements=excluded.achievements,
                   languages=excluded.languages,
                   consultation_fee=excluded.consultation_fee,
                   availability=excluded.availability,
                   updated_at=CURRENT_TIMESTAMP""",
              (doctor_id, specialization, qualification, experience_yrs,
               hospital, about, achievements, languages,
               consultation_fee, availability))
    conn.commit(); conn.close()

def get_doctor_portfolio(doctor_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT * FROM doctor_portfolio WHERE doctor_id=?", (doctor_id,))
    row = c.fetchone(); conn.close()
    return dict(row) if row else {}

def get_all_doctor_portfolios():
    conn = get_connection(); c = conn.cursor()
    c.execute("""SELECT dp.*,u.full_name,u.email,u.phone,u.profile_photo,u.bio
                 FROM doctor_portfolio dp
                 JOIN users u ON dp.doctor_id=u.id
                 ORDER BY u.full_name""")
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return rows


# ── NOTIFICATIONS ─────────────────────────────────────────────────────────────
def add_notification(user_id, title, message, notif_type="info", category=None):
    """Insert an in-app notification.

    notif_type : legacy field kept for backward-compat (info/ticket/appointment_update…)
    category   : 'general' | 'appointment' | 'ticket' | 'alert'
                 If omitted, inferred from notif_type for backward-compat.
    """
    if category is None:
        # Infer category from notif_type for backward-compat callers
        if notif_type in ("appointment_update", "appointment"):
            category = "appointment"
        elif notif_type == "ticket":
            category = "ticket"
        elif notif_type == "alert":
            category = "alert"
        else:
            category = "general"
    conn = get_connection(); c = conn.cursor()
    c.execute("""INSERT INTO notifications (user_id, title, message, notif_type, category)
                 VALUES (?,?,?,?,?)""",
              (user_id, title, message, notif_type, category))
    conn.commit(); conn.close()

def get_notifications(user_id, limit=20, notif_types=None):
    conn = get_connection(); c = conn.cursor()
    q = "SELECT * FROM notifications WHERE user_id=?"
    params = [user_id]
    if notif_types:
        placeholders = ",".join("?" for _ in notif_types)
        q += f" AND notif_type IN ({placeholders})"
        params.extend(notif_types)
    q += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    c.execute(q, tuple(params))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def get_appointment_notifications(user_id: int, limit: int = 10,
                                  unread_only: bool = False) -> list:
    """Return recent appointment-category notifications for a user."""
    try:
        conn = get_connection(); c = conn.cursor()
        cond = "AND is_read = 0" if unread_only else ""
        rows = c.execute(f"""
            SELECT id, title, message, is_read, created_at
            FROM notifications
            WHERE user_id = ? AND category = 'appointment'
            {cond}
            ORDER BY created_at DESC LIMIT ?
        """, (user_id, limit)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []

def mark_appointment_notifications_read(user_id: int) -> None:
    """Mark all appointment-category notifications as read for a user."""
    try:
        conn = get_connection(); c = conn.cursor()
        c.execute("""UPDATE notifications SET is_read = 1
                     WHERE user_id = ? AND category = 'appointment' AND is_read = 0""",
                  (user_id,))
        conn.commit(); conn.close()
    except Exception:
        pass

def get_unread_notification_count(user_id, notif_types=None):
    conn = get_connection(); c = conn.cursor()
    q = "SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0"
    params = [user_id]
    if notif_types:
        placeholders = ",".join("?" for _ in notif_types)
        q += f" AND notif_type IN ({placeholders})"
        params.extend(notif_types)
    c.execute(q, tuple(params))
    cnt = c.fetchone()[0]
    conn.close()
    return cnt

def mark_notifications_read(user_id, notif_types=None):
    conn = get_connection(); c = conn.cursor()
    q = "UPDATE notifications SET is_read=1 WHERE user_id=?"
    params = [user_id]
    if notif_types:
        placeholders = ",".join("?" for _ in notif_types)
        q += f" AND notif_type IN ({placeholders})"
        params.extend(notif_types)
    c.execute(q, tuple(params))
    conn.commit(); conn.close()


# ── STRESS ALERTS ─────────────────────────────────────────────────────────────
def create_stress_alert(patient_id, doctor_id, stress_level, stress_label):
    conn = get_connection(); c = conn.cursor()
    c.execute("""INSERT INTO stress_alerts
                 (patient_id,doctor_id,stress_level,stress_label)
                 VALUES (?,?,?,?)""",
              (patient_id, doctor_id, stress_level, stress_label))
    conn.commit(); conn.close()

def get_stress_alerts_for_doctor(doctor_id, unread_only=False):
    conn = get_connection(); c = conn.cursor()
    q = """SELECT sa.*,u.full_name as patient_name,u.profile_photo
           FROM stress_alerts sa
           JOIN users u ON sa.patient_id=u.id
           WHERE sa.doctor_id=?"""
    if unread_only:
        q += " AND sa.is_read=0"
    q += " ORDER BY sa.created_at DESC LIMIT 50"
    c.execute(q, (doctor_id,))
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return rows

def get_unread_alert_count(doctor_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM stress_alerts WHERE doctor_id=? AND is_read=0",
              (doctor_id,))
    cnt = c.fetchone()[0]; conn.close(); return cnt

def mark_alerts_read(doctor_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("UPDATE stress_alerts SET is_read=1 WHERE doctor_id=?", (doctor_id,))
    conn.commit(); conn.close()


# ── STATS ─────────────────────────────────────────────────────────────────────
def get_patients_with_doctors():
    conn = get_connection(); c = conn.cursor()
    c.execute("""
        SELECT p.id, p.full_name, p.username, p.email, p.phone, p.created_at,
               d.full_name AS doctor_name, d.username AS doctor_username
        FROM users p
        LEFT JOIN users d ON p.doctor_id = d.id
        WHERE p.role = 'patient'
        ORDER BY d.full_name, p.full_name
    """)
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return rows

def get_stats():
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE role='doctor'");  doctors  = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE role='patient'"); patients = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM predictions");                preds    = c.fetchone()[0]
    c.execute("SELECT stress_label,COUNT(*) FROM predictions GROUP BY stress_label")
    dist = dict(c.fetchall()); conn.close()
    return {"doctors": doctors, "patients": patients,
            "predictions": preds, "stress_dist": dist}


# ══════════════════════════════════════════════════════════════════════════════
#  V5 MIGRATION — APPOINTMENT SYSTEM UPGRADE
# ══════════════════════════════════════════════════════════════════════════════

def _ensure_appt_columns():
    """Force-add missing appointments columns on every import.
    Fixes databases created before _migrate_v5 was introduced."""
    COLS = [
        ("updated_at",       "TIMESTAMP"),
        ("proposed_date",    "TEXT"),
        ("proposed_time",    "TEXT"),
        ("proposed_by",      "TEXT"),
        ("doctor_note",      "TEXT"),
        ("is_emergency",     "INTEGER DEFAULT 0"),
        ("reschedule_of",    "INTEGER"),
        ("original_appt_id","INTEGER"),
        ("appointment_type","TEXT DEFAULT 'Physical'"),
        ("payment_mode",    "TEXT DEFAULT 'Online'"),
        ("payment_status",  "TEXT DEFAULT 'Pending'"),
        ("payment_ref",     "TEXT"),
        ("reason",          "TEXT"),
        ("status",          "TEXT DEFAULT 'Pending'"),
    ]
    try:
        conn = get_connection(); c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='appointments'")
        if c.fetchone():
            for col, typ in COLS:
                try:
                    c.execute(f"ALTER TABLE appointments ADD COLUMN {col} {typ}")
                    conn.commit()
                except Exception:
                    pass
        conn.close()
    except Exception:
        pass


def _migrate_v5():
    """Full appointment system upgrade: new tables + columns."""
    conn = get_connection(); c = conn.cursor()

    # ── UPGRADED APPOINTMENTS TABLE ──────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS appointments (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id       INTEGER NOT NULL,
        doctor_id        INTEGER NOT NULL,
        appt_date        TEXT NOT NULL,
        appt_time        TEXT NOT NULL,
        reason           TEXT,
        appointment_type TEXT DEFAULT 'Physical',
        payment_mode     TEXT DEFAULT 'Online',
        payment_status   TEXT DEFAULT 'Pending',
        payment_ref      TEXT,
        status           TEXT DEFAULT 'Pending',
        proposed_date    TEXT,
        proposed_time    TEXT,
        proposed_by      TEXT,
        doctor_note      TEXT,
        is_emergency     INTEGER DEFAULT 0,
        reschedule_of    INTEGER,
        original_appt_id INTEGER,
        created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (patient_id) REFERENCES users(id),
        FOREIGN KEY (doctor_id)  REFERENCES users(id)
    )''')
    # Migrate existing appointments table with new columns
    for col, typ in [
        ("appointment_type", "TEXT DEFAULT 'Physical'"),
        ("proposed_date",    "TEXT"),
        ("proposed_time",    "TEXT"),
        ("proposed_by",      "TEXT"),
        ("doctor_note",      "TEXT"),
        ("is_emergency",     "INTEGER DEFAULT 0"),
        ("reschedule_of",    "INTEGER"),
        ("original_appt_id", "INTEGER"),
        ("updated_at",       "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ("payment_mode",     "TEXT DEFAULT 'Online'"),
        ("payment_status",   "TEXT DEFAULT 'Pending'"),
        ("payment_ref",      "TEXT"),
        ("reason",           "TEXT"),
        ("status",           "TEXT DEFAULT 'Pending'"),
    ]:
        try: c.execute(f"ALTER TABLE appointments ADD COLUMN {col} {typ}")
        except: pass

    # ── DOCTOR AVAILABILITY ──────────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS doctor_availability (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        doctor_id   INTEGER NOT NULL,
        day_of_week TEXT NOT NULL,
        start_time  TEXT NOT NULL,
        end_time    TEXT NOT NULL,
        slot_mins   INTEGER DEFAULT 30,
        is_active   INTEGER DEFAULT 1,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (doctor_id) REFERENCES users(id)
    )''')

    # ── PATIENT BOOKING RESTRICTIONS ─────────────────────────────────────────
    # Tracks monthly booking count and consecutive-cancel behaviour per patient
    c.execute('''CREATE TABLE IF NOT EXISTS patient_booking_restrictions (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id           INTEGER NOT NULL UNIQUE,
        monthly_count        INTEGER DEFAULT 0,
        month_key            TEXT DEFAULT '',
        consec_cancels       INTEGER DEFAULT 0,
        restricted_until     TIMESTAMP,
        last_cancel_at       TIMESTAMP,
        updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (patient_id) REFERENCES users(id)
    )''')

    # ── APPOINTMENT AUDIT LOG ────────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS appointment_audit_log (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        appt_id     INTEGER NOT NULL,
        actor_id    INTEGER NOT NULL,
        actor_role  TEXT NOT NULL,
        action      TEXT NOT NULL,
        old_status  TEXT,
        new_status  TEXT,
        details     TEXT,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (appt_id) REFERENCES appointments(id),
        FOREIGN KEY (actor_id) REFERENCES users(id)
    )''')

    # ── APPOINTMENT TICKETS (admin review) ───────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS appointment_tickets (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        appt_id      INTEGER,
        filed_by     INTEGER NOT NULL,
        filed_role   TEXT NOT NULL,
        subject      TEXT NOT NULL,
        description  TEXT,
        ticket_type  TEXT DEFAULT 'General',
        status       TEXT DEFAULT 'Open',
        admin_note   TEXT,
        resolved_at  TIMESTAMP,
        created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (appt_id) REFERENCES appointments(id),
        FOREIGN KEY (filed_by) REFERENCES users(id)
    )''')

    # ── PATIENT-DOCTORS (many-to-many) ───────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS patient_doctors (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        doctor_id  INTEGER NOT NULL,
        is_primary INTEGER DEFAULT 0,
        assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (patient_id) REFERENCES users(id),
        FOREIGN KEY (doctor_id) REFERENCES users(id),
        UNIQUE(patient_id, doctor_id)
    )''')

    # ── LOGIN LOGS ────────────────────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS login_logs (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER NOT NULL,
        username   TEXT NOT NULL,
        full_name  TEXT,
        role       TEXT,
        logged_in_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    # ── DOCTOR PORTFOLIO PDF ──────────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS doctor_portfolio_pdf (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        doctor_id  INTEGER UNIQUE NOT NULL,
        pdf_data   TEXT NOT NULL,
        filename   TEXT,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (doctor_id) REFERENCES users(id)
    )''')

    # ── MEDICAL REPORTS ───────────────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS medical_reports (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id  INTEGER NOT NULL,
        filename    TEXT NOT NULL,
        file_data   TEXT NOT NULL,
        file_type   TEXT,
        analysis    TEXT,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (patient_id) REFERENCES users(id)
    )''')

    # Backfill patient_doctors from existing doctor_id assignments
    c.execute("""INSERT OR IGNORE INTO patient_doctors (patient_id, doctor_id, is_primary)
                 SELECT id, doctor_id, 1 FROM users
                 WHERE role='patient' AND doctor_id IS NOT NULL""")

    conn.commit(); conn.close()

_ensure_appt_columns()
_migrate_v5()


# ══════════════════════════════════════════════════════════════════════════════
#  PATIENT-DOCTORS (multiple doctors per patient)
# ══════════════════════════════════════════════════════════════════════════════

def add_doctor_to_patient(patient_id, doctor_id, is_primary=0):
    """Add a doctor to a patient (many-to-many)."""
    conn = get_connection(); c = conn.cursor()
    try:
        c.execute("""INSERT INTO patient_doctors (patient_id, doctor_id, is_primary)
                     VALUES (?,?,?)""", (patient_id, doctor_id, is_primary))
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # already exists
    conn.close()

def remove_doctor_from_patient(patient_id, doctor_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("DELETE FROM patient_doctors WHERE patient_id=? AND doctor_id=?",
              (patient_id, doctor_id))
    conn.commit(); conn.close()

def get_doctors_for_patient(patient_id):
    """Get ALL doctors assigned to a patient."""
    conn = get_connection(); c = conn.cursor()
    c.execute("""SELECT u.*, pd.is_primary FROM users u
                 JOIN patient_doctors pd ON pd.doctor_id=u.id
                 WHERE pd.patient_id=?
                 ORDER BY pd.is_primary DESC, u.full_name""",
              (patient_id,))
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return rows

def get_primary_doctor_for_patient(patient_id):
    """Get the primary doctor for a patient."""
    conn = get_connection(); c = conn.cursor()
    # Check patient_doctors table first
    c.execute("""SELECT u.* FROM users u
                 JOIN patient_doctors pd ON pd.doctor_id=u.id
                 WHERE pd.patient_id=? AND pd.is_primary=1""",
              (patient_id,))
    row = c.fetchone()
    if not row:
        # Fallback to legacy doctor_id
        c.execute("""SELECT u.* FROM users u
                     JOIN users p ON p.doctor_id=u.id
                     WHERE p.id=?""", (patient_id,))
        row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def set_primary_doctor(patient_id, doctor_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("UPDATE patient_doctors SET is_primary=0 WHERE patient_id=?", (patient_id,))
    c.execute("UPDATE patient_doctors SET is_primary=1 WHERE patient_id=? AND doctor_id=?",
              (patient_id, doctor_id))
    c.execute("UPDATE users SET doctor_id=? WHERE id=?", (doctor_id, patient_id))
    conn.commit(); conn.close()


# ══════════════════════════════════════════════════════════════════════════════
#  DOCTOR AVAILABILITY / CALENDAR
# ══════════════════════════════════════════════════════════════════════════════

DAYS_OF_WEEK = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

def set_doctor_availability(doctor_id, day_of_week, start_time, end_time, slot_mins=30):
    """Set/update availability for a specific day."""
    conn = get_connection(); c = conn.cursor()
    c.execute("""DELETE FROM doctor_availability
                 WHERE doctor_id=? AND day_of_week=?""",
              (doctor_id, day_of_week))
    c.execute("""INSERT INTO doctor_availability
                 (doctor_id, day_of_week, start_time, end_time, slot_mins)
                 VALUES (?,?,?,?,?)""",
              (doctor_id, day_of_week, start_time, end_time, slot_mins))
    conn.commit(); conn.close()

def remove_doctor_availability(doctor_id, day_of_week):
    conn = get_connection(); c = conn.cursor()
    c.execute("DELETE FROM doctor_availability WHERE doctor_id=? AND day_of_week=?",
              (doctor_id, day_of_week))
    conn.commit(); conn.close()

def get_doctor_availability(doctor_id):
    """Returns list of availability slots for a doctor."""
    conn = get_connection(); c = conn.cursor()
    c.execute("""SELECT * FROM doctor_availability
                 WHERE doctor_id=? AND is_active=1
                 ORDER BY CASE day_of_week
                   WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2
                   WHEN 'Wednesday' THEN 3 WHEN 'Thursday' THEN 4
                   WHEN 'Friday' THEN 5 WHEN 'Saturday' THEN 6
                   WHEN 'Sunday' THEN 7 END""",
              (doctor_id,))
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return rows

def get_available_slots_for_date(doctor_id, date_str):
    """Generate time slots for a given date based on doctor's availability.
       Returns list of 'HH:MM' strings that are NOT already booked."""
    from datetime import datetime as _dt
    try:
        dt = _dt.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return []
    day_name = dt.strftime("%A")  # Monday, Tuesday, etc.

    conn = get_connection(); c = conn.cursor()
    c.execute("""SELECT * FROM doctor_availability
                 WHERE doctor_id=? AND day_of_week=? AND is_active=1""",
              (doctor_id, day_name))
    avail = c.fetchone()
    if not avail:
        conn.close(); return []

    avail = dict(avail)
    start = _dt.strptime(avail["start_time"], "%H:%M")
    end   = _dt.strptime(avail["end_time"],   "%H:%M")
    slot_mins = avail.get("slot_mins", 30)

    slots = []
    current = start
    while current < end:
        slots.append(current.strftime("%H:%M"))
        current += timedelta(minutes=slot_mins)

    # Remove already booked slots
    active_statuses_str = ",".join(f"'{s}'" for s in APPT_ACTIVE_STATUSES)
    c.execute(f"""SELECT appt_time FROM appointments
                  WHERE doctor_id=? AND appt_date=?
                  AND status IN ({active_statuses_str})""",
              (doctor_id, date_str))
    booked = {row["appt_time"] for row in c.fetchall()}
    conn.close()

    return [s for s in slots if s not in booked]


# ══════════════════════════════════════════════════════════════════════════════
#  APPOINTMENTS — UPGRADED
# ══════════════════════════════════════════════════════════════════════════════


# ── Booking limit constants ────────────────────────────────────────────────────
MONTHLY_BOOKING_LIMIT   = 10   # max new requests per calendar month
CONSEC_CANCEL_LIMIT     = 3    # consecutive patient-cancels before restriction
CANCEL_RESTRICT_DAYS    = 3    # days blocked after hitting consecutive limit


def _get_or_create_restriction_row(c, patient_id: int) -> dict:
    """Return (and upsert if missing) the restriction row for a patient."""
    row = c.execute(
        "SELECT * FROM patient_booking_restrictions WHERE patient_id=?",
        (patient_id,)).fetchone()
    if not row:
        c.execute(
            "INSERT OR IGNORE INTO patient_booking_restrictions "
            "(patient_id, monthly_count, month_key, consec_cancels) VALUES (?,0,'',0)",
            (patient_id,))
        row = c.execute(
            "SELECT * FROM patient_booking_restrictions WHERE patient_id=?",
            (patient_id,)).fetchone()
    return dict(row)


def check_booking_limit(patient_id: int):
    """Check whether a patient can book a new appointment.

    Returns (allowed: bool, message: str, quota_info: dict).
    quota_info keys: used, limit, remaining, restricted_until, consec_cancels
    """
    conn = get_connection(); c = conn.cursor()
    row  = _get_or_create_restriction_row(c, patient_id)
    conn.commit()
    conn.close()

    now       = datetime.utcnow()
    month_key = now.strftime("%Y-%m")
    used      = row["monthly_count"] if row["month_key"] == month_key else 0
    remaining = max(0, MONTHLY_BOOKING_LIMIT - used)

    # ── Restriction window check ──────────────────────────────────────────────
    restricted_until = row.get("restricted_until")
    if restricted_until:
        try:
            ru = datetime.strptime(str(restricted_until)[:19], "%Y-%m-%d %H:%M:%S")
        except Exception:
            ru = None
        if ru and now < ru:
            delta   = ru - now
            hours   = int(delta.total_seconds() // 3600)
            minutes = int((delta.total_seconds() % 3600) // 60)
            time_str = (f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m")
            return False, (
                f"🚫 You have been temporarily restricted from booking appointments "
                f"due to {CONSEC_CANCEL_LIMIT} consecutive cancellations. "
                f"You can book again in **{time_str}**."
            ), {
                "used": used, "limit": MONTHLY_BOOKING_LIMIT,
                "remaining": 0, "restricted_until": ru,
                "consec_cancels": row.get("consec_cancels", 0),
            }

    # ── Monthly quota check ───────────────────────────────────────────────────
    if used >= MONTHLY_BOOKING_LIMIT:
        return False, (
            f"📅 You have reached your monthly appointment limit of "
            f"**{MONTHLY_BOOKING_LIMIT}** requests for {now.strftime('%B %Y')}. "
            f"You can book again from {(now.replace(day=1) + timedelta(days=32)).replace(day=1).strftime('%d %b %Y')}."
        ), {
            "used": used, "limit": MONTHLY_BOOKING_LIMIT,
            "remaining": 0, "restricted_until": None,
            "consec_cancels": row.get("consec_cancels", 0),
        }

    return True, "", {
        "used": used, "limit": MONTHLY_BOOKING_LIMIT,
        "remaining": remaining, "restricted_until": None,
        "consec_cancels": row.get("consec_cancels", 0),
    }


def _increment_booking_count(c, conn, patient_id: int):
    """Increment monthly booking count. Reset if new month."""
    month_key = datetime.utcnow().strftime("%Y-%m")
    row = _get_or_create_restriction_row(c, patient_id)
    conn.commit()
    if row["month_key"] == month_key:
        new_count = row["monthly_count"] + 1
    else:
        new_count = 1   # new month — reset
    c.execute("""UPDATE patient_booking_restrictions
                 SET monthly_count=?, month_key=?, updated_at=CURRENT_TIMESTAMP
                 WHERE patient_id=?""",
              (new_count, month_key, patient_id))
    conn.commit()


def _record_patient_cancel(c, conn, patient_id: int):
    """Increment consecutive-cancel counter; apply restriction if threshold reached."""
    row = _get_or_create_restriction_row(c, patient_id)
    conn.commit()
    new_consec = row.get("consec_cancels", 0) + 1
    restricted_until = None
    if new_consec >= CONSEC_CANCEL_LIMIT:
        restricted_until = (datetime.utcnow() + timedelta(days=CANCEL_RESTRICT_DAYS)).strftime(
            "%Y-%m-%d %H:%M:%S")
        new_consec = 0  # reset counter after applying restriction
    c.execute("""UPDATE patient_booking_restrictions
                 SET consec_cancels=?, restricted_until=?,
                     last_cancel_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
                 WHERE patient_id=?""",
              (new_consec, restricted_until, patient_id))
    conn.commit()
    return restricted_until  # None or datetime string


def _reset_consec_cancels(c, conn, patient_id: int):
    """Reset consecutive-cancel counter when patient successfully books or completes."""
    c.execute("""UPDATE patient_booking_restrictions
                 SET consec_cancels=0, updated_at=CURRENT_TIMESTAMP
                 WHERE patient_id=?""",
              (patient_id,))
    conn.commit()


def book_appointment(patient_id, doctor_id, appt_date, appt_time,
                     reason="", appointment_type="Physical",
                     payment_mode="Online", payment_ref="",
                     payment_status="Paid", is_emergency=0):
    """Book a new appointment request. Status starts as 'Pending'.
       Returns (True, appt_id) or (False, error_msg)."""

    # ── Booking limit / restriction check ─────────────────────────────────────
    if not is_emergency:
        allowed, limit_msg, _ = check_booking_limit(patient_id)
        if not allowed:
            return False, limit_msg

    conn = get_connection(); c = conn.cursor()

    # Double-booking check: same doctor, same date+time, active status
    active_statuses_str = ",".join(f"'{s}'" for s in APPT_ACTIVE_STATUSES)
    c.execute(f"""SELECT id FROM appointments
                  WHERE doctor_id=? AND appt_date=? AND appt_time=?
                  AND status IN ({active_statuses_str})""",
              (doctor_id, appt_date, appt_time))
    if c.fetchone():
        conn.close()
        return False, "That time slot is already booked. Please choose another."

    # 1-hour gap check for patient on same day
    c.execute(f"""SELECT appt_date, appt_time FROM appointments
                  WHERE patient_id=? AND appt_date=?
                  AND status IN ({active_statuses_str})""",
              (patient_id, appt_date))
    existing = c.fetchall()
    try:
        new_dt = datetime.strptime(f"{appt_date} {appt_time}", "%Y-%m-%d %H:%M")
    except ValueError:
        conn.close()
        return False, "Invalid date/time format."
    for row in existing:
        try:
            ex_dt = datetime.strptime(f"{row['appt_date']} {row['appt_time']}",
                                       "%Y-%m-%d %H:%M")
            if abs((new_dt - ex_dt).total_seconds()) < 3600:
                conn.close()
                return False, "Must maintain at least 1-hour gap between bookings."
        except: pass

    c.execute("""INSERT INTO appointments
                 (patient_id, doctor_id, appt_date, appt_time, reason,
                  appointment_type, payment_mode, payment_ref, payment_status,
                  status, is_emergency)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
              (patient_id, doctor_id, appt_date, appt_time, reason,
               appointment_type, payment_mode, payment_ref, payment_status,
               APPT_STATUS_PENDING, is_emergency))
    appt_id = c.lastrowid
    conn.commit()

    # ── Increment monthly counter + reset consecutive-cancel streak ───────────
    if not is_emergency:
        _increment_booking_count(c, conn, patient_id)
        _reset_consec_cancels(c, conn, patient_id)

    # Audit log
    _log_appt_audit(c, conn, appt_id, patient_id, "patient", "CREATED",
                    None, APPT_STATUS_PENDING,
                    f"Appointment requested: {appt_date} {appt_time}")

    # Notification to doctor
    _safe_add_notification(c, conn, doctor_id, "📅 New Appointment Request",
                          f"Patient requested appointment on {appt_date} at {appt_time}.",
                          "appointment_update")
    conn.close()
    return True, appt_id


def doctor_accept_appointment(appt_id, doctor_id):
    """Doctor accepts the appointment as-is."""
    conn = get_connection(); c = conn.cursor()
    appt = _get_appt(c, appt_id)
    if not appt: conn.close(); return False, "Appointment not found."
    if appt["doctor_id"] != doctor_id: conn.close(); return False, "Not your appointment."
    if appt["status"] != APPT_STATUS_PENDING:
        conn.close(); return False, f"Cannot accept — status is '{appt['status']}'."
    if _doctor_slot_conflict(c, appt["doctor_id"], appt["appt_date"], appt["appt_time"], exclude_appt_id=appt_id):
        conn.close(); return False, "That requested slot is no longer available. Please propose a new time for the patient."

    c.execute("""UPDATE appointments SET status=?, updated_at=CURRENT_TIMESTAMP
                 WHERE id=?""", (APPT_STATUS_CONFIRMED, appt_id))
    conn.commit()
    _log_appt_audit(c, conn, appt_id, doctor_id, "doctor", "ACCEPTED",
                    APPT_STATUS_PENDING, APPT_STATUS_CONFIRMED, "Doctor accepted appointment")
    _safe_add_notification(c, conn, appt["patient_id"], "✅ Appointment Confirmed",
                          f"Dr. accepted your appointment on {appt['appt_date']} at {appt['appt_time']}.",
                          "appointment_update")
    _safe_send_appointment_email(c, appt, "confirmed")
    conn.close()
    return True, "Appointment confirmed!"


def doctor_reject_appointment(appt_id, doctor_id, reason=""):
    """Doctor rejects the appointment."""
    conn = get_connection(); c = conn.cursor()
    appt = _get_appt(c, appt_id)
    if not appt: conn.close(); return False, "Appointment not found."
    if appt["doctor_id"] != doctor_id: conn.close(); return False, "Not your appointment."
    if appt["status"] not in [APPT_STATUS_PENDING, APPT_STATUS_PATIENT_CONFIRM]:
        conn.close(); return False, f"Cannot reject — status is '{appt['status']}'."

    c.execute("""UPDATE appointments SET status=?, doctor_note=?,
                 updated_at=CURRENT_TIMESTAMP WHERE id=?""",
              (APPT_STATUS_REJECTED, reason, appt_id))
    conn.commit()
    _log_appt_audit(c, conn, appt_id, doctor_id, "doctor", "REJECTED",
                    appt["status"], APPT_STATUS_REJECTED, f"Reason: {reason}")
    _safe_add_notification(c, conn, appt["patient_id"], "❌ Appointment Rejected",
                          f"Doctor rejected your appointment. Reason: {reason or 'Not specified'}",
                          "appointment_update")
    _safe_send_appointment_email(c, appt, "cancelled", reason_override=reason or appt.get("reason", ""))
    conn.close()
    return True, "Appointment rejected."


def doctor_propose_change(appt_id, doctor_id, new_date, new_time, note=""):
    """Doctor proposes a schedule change. Patient must confirm."""
    conn = get_connection(); c = conn.cursor()
    appt = _get_appt(c, appt_id)
    if not appt: conn.close(); return False, "Appointment not found."
    if appt["doctor_id"] != doctor_id: conn.close(); return False, "Not your appointment."
    if appt["status"] not in [APPT_STATUS_PENDING, APPT_STATUS_CONFIRMED, APPT_STATUS_ACCEPTED]:
        conn.close(); return False, f"Cannot modify — status is '{appt['status']}'."

    active_statuses_str = ",".join(f"'{s}'" for s in APPT_ACTIVE_STATUSES)
    c.execute(f"""SELECT id FROM appointments
                  WHERE doctor_id=? AND appt_date=? AND appt_time=?
                  AND status IN ({active_statuses_str}) AND id!=?""",
              (doctor_id, new_date, new_time, appt_id))
    if c.fetchone():
        conn.close()
        return False, "That proposed time slot is already booked."

    old_status = appt["status"]
    c.execute("""UPDATE appointments SET status=?, proposed_date=?,
                 proposed_time=?, proposed_by='doctor', doctor_note=?,
                 updated_at=CURRENT_TIMESTAMP WHERE id=?""",
              (APPT_STATUS_DOCTOR_PROPOSED, new_date, new_time, note, appt_id))
    conn.commit()
    _log_appt_audit(c, conn, appt_id, doctor_id, "doctor", "PROPOSED_CHANGE",
                    old_status, APPT_STATUS_DOCTOR_PROPOSED,
                    f"Proposed: {new_date} {new_time}. Note: {note}")
    _safe_add_notification(c, conn, appt["patient_id"], "📅 Schedule Change Proposed",
                          f"Doctor proposed {new_date} at {new_time}. Please confirm or decline.",
                          "appointment_update")
    _safe_send_appointment_email(c, appt, "changed", date_override=new_date, time_override=new_time, reason_override=note or appt.get("reason", ""))
    conn.close()
    return True, "Proposed change sent to patient."


def patient_confirm_proposed(appt_id, patient_id):
    """Patient confirms the doctor's proposed schedule change."""
    conn = get_connection(); c = conn.cursor()
    appt = _get_appt(c, appt_id)
    if not appt: conn.close(); return False, "Appointment not found."
    if appt["patient_id"] != patient_id: conn.close(); return False, "Not your appointment."
    if appt["status"] != APPT_STATUS_DOCTOR_PROPOSED:
        conn.close(); return False, f"Nothing to confirm — status is '{appt['status']}'."

    new_date = appt["proposed_date"]
    new_time = appt["proposed_time"]
    if _doctor_slot_conflict(c, appt["doctor_id"], new_date, new_time, exclude_appt_id=appt_id):
        conn.close(); return False, "That proposed time is no longer available. Please ask the doctor for another slot."
    c.execute("""UPDATE appointments SET status=?, appt_date=?, appt_time=?,
                 proposed_date=NULL, proposed_time=NULL, proposed_by=NULL,
                 updated_at=CURRENT_TIMESTAMP WHERE id=?""",
              (APPT_STATUS_CONFIRMED, new_date, new_time, appt_id))
    conn.commit()
    _log_appt_audit(c, conn, appt_id, patient_id, "patient", "CONFIRMED_PROPOSAL",
                    APPT_STATUS_DOCTOR_PROPOSED, APPT_STATUS_CONFIRMED,
                    f"Patient accepted proposed schedule: {new_date} {new_time}")
    _safe_add_notification(c, conn, appt["doctor_id"], "✅ Patient Confirmed Change",
                          f"Patient confirmed appointment on {new_date} at {new_time}. Latest schedule is now active.",
                          "appointment_update")
    _safe_add_notification(c, conn, appt["patient_id"], "✅ Appointment Change Confirmed",
                          f"Your appointment is now confirmed for {new_date} at {new_time}. You can download the latest slip from the portal.",
                          "appointment_update")
    _safe_send_appointment_email(c, appt, "confirmed", date_override=new_date, time_override=new_time)
    conn.close()
    return True, "Confirmed! Appointment updated."


def patient_decline_proposed(appt_id, patient_id, reason=""):
    """Patient declines the doctor's proposed change."""
    conn = get_connection(); c = conn.cursor()
    appt = _get_appt(c, appt_id)
    if not appt: conn.close(); return False, "Appointment not found."
    if appt["patient_id"] != patient_id: conn.close(); return False, "Not your appointment."
    if appt["status"] != APPT_STATUS_DOCTOR_PROPOSED:
        conn.close(); return False, f"Nothing to decline — status is '{appt['status']}'."

    c.execute("""UPDATE appointments SET status=?,
                 updated_at=CURRENT_TIMESTAMP WHERE id=?""",
              (APPT_STATUS_CANCELLED, appt_id))
    conn.commit()
    _log_appt_audit(c, conn, appt_id, patient_id, "patient", "DECLINED_PROPOSAL",
                    APPT_STATUS_DOCTOR_PROPOSED, APPT_STATUS_CANCELLED,
                    f"Patient declined proposed change. Reason: {reason}")
    _safe_add_notification(c, conn, appt["doctor_id"], "❌ Patient Declined Change",
                          f"Patient declined proposed schedule. Reason: {reason or 'Not specified'}",
                          "appointment_update")
    conn.close()
    return True, "Appointment cancelled."


def patient_request_reschedule(appt_id, patient_id, new_date, new_time, reason=""):
    """Patient requests a reschedule of a confirmed appointment."""
    conn = get_connection(); c = conn.cursor()
    appt = _get_appt(c, appt_id)
    if not appt: conn.close(); return False, "Appointment not found."
    if appt["patient_id"] != patient_id: conn.close(); return False, "Not your appointment."
    if appt["status"] not in [APPT_STATUS_CONFIRMED, APPT_STATUS_ACCEPTED]:
        conn.close(); return False, "Can only reschedule confirmed appointments."

    doctor_id = appt["doctor_id"]
    active_statuses_str = ",".join(f"'{s}'" for s in APPT_ACTIVE_STATUSES)
    c.execute(f"""SELECT id FROM appointments
                  WHERE doctor_id=? AND appt_date=? AND appt_time=?
                  AND status IN ({active_statuses_str})""",
              (doctor_id, new_date, new_time))
    slot_conflict = c.fetchone() is not None

    c.execute("""UPDATE appointments SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
              (APPT_STATUS_RESCHEDULED, appt_id))
    c.execute("""INSERT INTO appointments
                 (patient_id, doctor_id, appt_date, appt_time, reason,
                  appointment_type, payment_mode, payment_ref, payment_status,
                  status, reschedule_of, original_appt_id)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
              (patient_id, doctor_id, new_date, new_time,
               (f"[Reschedule - doctor review needed] {reason}" if slot_conflict else (f"[Reschedule] {reason}" if reason else "[Reschedule request]")),
               appt.get("appointment_type","Physical"),
               appt.get("payment_mode",""),
               appt.get("payment_ref",""),
               appt.get("payment_status",""),
               APPT_STATUS_PENDING, appt_id, appt_id))
    new_id = c.lastrowid
    conn.commit()
    _log_appt_audit(c, conn, appt_id, patient_id, "patient", "RESCHEDULED",
                    appt["status"], APPT_STATUS_RESCHEDULED,
                    f"Rescheduled to new APT-{new_id:05d}: {new_date} {new_time}")
    _log_appt_audit(c, conn, new_id, patient_id, "patient", "CREATED_RESCHEDULE",
                    None, APPT_STATUS_PENDING,
                    f"Reschedule of APT-{appt_id:05d}")
    doctor_msg = (
        f"Patient requested reschedule to {new_date} at {new_time}, but that slot is already occupied. Please propose an alternative time."
        if slot_conflict else
        f"Patient requested reschedule to {new_date} at {new_time}."
    )
    patient_msg = (
        f"Your reschedule request created APT-{new_id:05d}. The requested slot is being reviewed; if unavailable, your doctor will propose a new time for you to confirm."
        if slot_conflict else
        f"Your reschedule request created APT-{new_id:05d}. Once approved, download the latest slip from the Updates Center."
    )
    _safe_add_notification(c, conn, doctor_id, "📅 Reschedule Request",
                          doctor_msg,
                          "appointment_update")
    _safe_add_notification(c, conn, patient_id, "🔄 Reschedule Submitted",
                          patient_msg,
                          "appointment_update")
    conn.close()
    return True, new_id


def doctor_complete_appointment(appt_id, doctor_id):
    """Mark appointment as completed."""
    conn = get_connection(); c = conn.cursor()
    appt = _get_appt(c, appt_id)
    if not appt: conn.close(); return False, "Appointment not found."
    if appt["doctor_id"] != doctor_id: conn.close(); return False, "Not your appointment."
    if appt["status"] not in [APPT_STATUS_CONFIRMED, APPT_STATUS_ACCEPTED, APPT_STATUS_PENDING]:
        conn.close(); return False, f"Cannot complete — status is '{appt['status']}'."

    c.execute("""UPDATE appointments SET status=?,
                 updated_at=CURRENT_TIMESTAMP WHERE id=?""",
              (APPT_STATUS_COMPLETED, appt_id))
    conn.commit()
    _log_appt_audit(c, conn, appt_id, doctor_id, "doctor", "COMPLETED",
                    appt["status"], APPT_STATUS_COMPLETED, "Appointment completed")
    _safe_add_notification(c, conn, appt["patient_id"], "✅ Appointment Completed",
                          f"Your appointment on {appt['appt_date']} has been marked as completed.",
                          "appointment_update")
    conn.close()
    return True, "Appointment completed!"


def cancel_appointment(appt_id, user_id, role, reason=""):
    """Cancel appointment by patient or doctor."""
    conn = get_connection(); c = conn.cursor()
    appt = _get_appt(c, appt_id)
    if not appt: conn.close(); return False, "Appointment not found."
    if appt["status"] in [APPT_STATUS_CANCELLED, APPT_STATUS_COMPLETED]:
        conn.close(); return False, "Appointment already finished."

    c.execute("""UPDATE appointments SET status=?, doctor_note=COALESCE(doctor_note,'') || ? ,
                 updated_at=CURRENT_TIMESTAMP WHERE id=?""",
              (APPT_STATUS_CANCELLED, f"\n[Cancelled by {role}] {reason}", appt_id))
    conn.commit()
    _log_appt_audit(c, conn, appt_id, user_id, role, "CANCELLED",
                    appt["status"], APPT_STATUS_CANCELLED, f"Cancelled by {role}. {reason}")

    # ── Track consecutive patient cancels and apply restriction if needed ─────
    restriction_applied = None
    if role == "patient":
        restriction_applied = _record_patient_cancel(c, conn, user_id)

    recipients = []
    if role == "patient":
        recipients = [appt["doctor_id"]]
    elif role == "doctor":
        recipients = [appt["patient_id"]]
    else:
        recipients = [appt["patient_id"], appt["doctor_id"]]

    for notify_id in recipients:
        _safe_add_notification(c, conn, notify_id, "❌ Appointment Cancelled",
                              f"Appointment APT-{appt_id:05d} was cancelled by {role}. {reason}",
                              "appointment_update")

    # ── If restriction just applied, notify the patient ───────────────────────
    if restriction_applied:
        _safe_add_notification(
            c, conn, user_id,
            "⚠️ Booking Temporarily Restricted",
            f"You have cancelled {CONSEC_CANCEL_LIMIT} appointments in a row. "
            f"New booking requests are blocked for {CANCEL_RESTRICT_DAYS} days "
            f"(until {restriction_applied[:10]}).",
            "appointment")

    if role in {"doctor", "admin"}:
        _safe_send_appointment_email(c, appt, "cancelled", reason_override=reason or appt.get("reason", ""))
    conn.close()
    return True, "Appointment cancelled."


def emergency_reassign_appointment(appt_id, new_doctor_id, admin_id, reason=""):
    """Admin emergency reassignment to another doctor."""
    conn = get_connection(); c = conn.cursor()
    appt = _get_appt(c, appt_id)
    if not appt: conn.close(); return False, "Appointment not found."
    if appt["status"] in [APPT_STATUS_CANCELLED, APPT_STATUS_COMPLETED]:
        conn.close(); return False, "Cannot reassign finished appointment."

    old_doctor_id = appt["doctor_id"]

    # Double-booking check for new doctor
    active_statuses_str = ",".join(f"'{s}'" for s in APPT_ACTIVE_STATUSES)
    c.execute(f"""SELECT id FROM appointments
                  WHERE doctor_id=? AND appt_date=? AND appt_time=?
                  AND status IN ({active_statuses_str})""",
              (new_doctor_id, appt["appt_date"], appt["appt_time"]))
    if c.fetchone():
        conn.close()
        return False, "New doctor already has a booking at that time."

    c.execute("""UPDATE appointments SET doctor_id=?, is_emergency=1,
                 doctor_note=COALESCE(doctor_note,'') || ?,
                 status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
              (new_doctor_id,
               f"\n[Emergency reassigned by admin] {reason}",
               APPT_STATUS_CONFIRMED, appt_id))
    conn.commit()
    _log_appt_audit(c, conn, appt_id, admin_id, "admin", "EMERGENCY_REASSIGN",
                    appt["status"], APPT_STATUS_CONFIRMED,
                    f"Reassigned from doctor #{old_doctor_id} to #{new_doctor_id}. {reason}")
    # Notify old doctor
    _safe_add_notification(c, conn, old_doctor_id, "🚨 Appointment Reassigned",
                          f"APT-{appt_id:05d} was emergency-reassigned to another doctor.",
                          "appointment_update")
    # Notify new doctor
    _safe_add_notification(c, conn, new_doctor_id, "🚨 Emergency Appointment Assigned",
                          f"APT-{appt_id:05d} was emergency-assigned to you on {appt['appt_date']} at {appt['appt_time']}.",
                          "appointment_update")
    # Notify patient
    _safe_add_notification(c, conn, appt["patient_id"], "🔄 Appointment Reassigned",
                          f"Your appointment APT-{appt_id:05d} has been reassigned to doctor #{new_doctor_id} for {appt['appt_date']} at {appt['appt_time']}. Download the latest slip from your portal.",
                          "appointment_update")
    _safe_send_appointment_email(c, appt, "reassigned")
    conn.close()
    return True, "Emergency reassignment done."


def get_appointments_for_patient(patient_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("""SELECT a.*,u.full_name as doctor_name,u.email as doctor_email
                 FROM appointments a JOIN users u ON a.doctor_id=u.id
                 WHERE a.patient_id=?
                 ORDER BY COALESCE(a.updated_at, a.created_at) DESC, a.id DESC""",
              (patient_id,))
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return rows

def get_appointments_for_doctor(doctor_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("""SELECT a.*,u.full_name as patient_name,u.email as patient_email,
                        u.phone as patient_phone
                 FROM appointments a JOIN users u ON a.patient_id=u.id
                 WHERE a.doctor_id=?
                 ORDER BY COALESCE(a.updated_at, a.created_at) DESC, a.id DESC""",
              (doctor_id,))
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return rows

def get_all_appointments():
    """Admin: get all appointments with user details."""
    conn = get_connection(); c = conn.cursor()
    c.execute("""SELECT a.*,
                        p.full_name as patient_name, p.email as patient_email,
                        d.full_name as doctor_name, d.email as doctor_email
                 FROM appointments a
                 JOIN users p ON a.patient_id=p.id
                 JOIN users d ON a.doctor_id=d.id
                 ORDER BY a.created_at DESC""")
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return rows

def get_appointment_by_id(appt_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("""SELECT a.*,
                        p.full_name as patient_name, p.email as patient_email,
                        d.full_name as doctor_name, d.email as doctor_email
                 FROM appointments a
                 JOIN users p ON a.patient_id=p.id
                 JOIN users d ON a.doctor_id=d.id
                 WHERE a.id=?""", (appt_id,))
    row = c.fetchone(); conn.close()
    return dict(row) if row else None

def get_pending_appt_count_for_doctor(doctor_id):
    """Count pending appointment requests for doctor."""
    conn = get_connection(); c = conn.cursor()
    c.execute("""SELECT COUNT(*) FROM appointments
                 WHERE doctor_id=? AND status=?""",
              (doctor_id, APPT_STATUS_PENDING))
    cnt = c.fetchone()[0]; conn.close(); return cnt

def get_patient_booking_status(patient_id: int) -> dict:
    """Return the full booking restriction status for a patient (for admin view)."""
    conn = get_connection(); c = conn.cursor()
    row = _get_or_create_restriction_row(c, patient_id)
    conn.commit(); conn.close()
    month_key = datetime.utcnow().strftime("%Y-%m")
    used = row["monthly_count"] if row["month_key"] == month_key else 0
    return {
        "used":             used,
        "limit":            MONTHLY_BOOKING_LIMIT,
        "remaining":        max(0, MONTHLY_BOOKING_LIMIT - used),
        "month_key":        row["month_key"],
        "consec_cancels":   row.get("consec_cancels", 0),
        "restricted_until": row.get("restricted_until"),
        "last_cancel_at":   row.get("last_cancel_at"),
    }


def lift_patient_restriction(patient_id: int, admin_id: int) -> tuple:
    """Admin lifts a patient's booking restriction immediately."""
    conn = get_connection(); c = conn.cursor()
    row = c.execute(
        "SELECT * FROM patient_booking_restrictions WHERE patient_id=?",
        (patient_id,)).fetchone()
    if not row:
        conn.close()
        return False, "No restriction record found for this patient."
    c.execute("""UPDATE patient_booking_restrictions
                 SET restricted_until=NULL, consec_cancels=0,
                     updated_at=CURRENT_TIMESTAMP
                 WHERE patient_id=?""", (patient_id,))
    conn.commit()
    _safe_add_notification(c, conn, patient_id,
                           "✅ Booking Restriction Lifted",
                           "An administrator has lifted your appointment booking restriction. "
                           "You can now make new requests.",
                           "appointment")
    conn.close()
    return True, "Restriction lifted successfully."


def get_pending_confirm_count_for_patient(patient_id):
    """Count appointments waiting for patient confirmation."""
    conn = get_connection(); c = conn.cursor()
    c.execute("""SELECT COUNT(*) FROM appointments
                 WHERE patient_id=? AND status=?""",
              (patient_id, APPT_STATUS_DOCTOR_PROPOSED))
    cnt = c.fetchone()[0]; conn.close(); return cnt

def update_appointment_status(appt_id, status):
    """Legacy status update — safe against missing updated_at column."""
    conn = get_connection(); c = conn.cursor()
    try:
        c.execute("ALTER TABLE appointments ADD COLUMN updated_at TIMESTAMP")
        conn.commit()
    except Exception:
        pass  # Column already exists
    try:
        c.execute("UPDATE appointments SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                  (status, appt_id))
    except Exception:
        c.execute("UPDATE appointments SET status=? WHERE id=?", (status, appt_id))
    conn.commit(); conn.close()


# ── HELPERS ──────────────────────────────────────────────────────────────────

def _get_appt(cursor, appt_id):
    cursor.execute("SELECT * FROM appointments WHERE id=?", (appt_id,))
    row = cursor.fetchone()
    return dict(row) if row else None

def _log_appt_audit(cursor, conn, appt_id, actor_id, actor_role, action,
                     old_status, new_status, details=""):
    cursor.execute("""INSERT INTO appointment_audit_log
                      (appt_id, actor_id, actor_role, action,
                       old_status, new_status, details)
                      VALUES (?,?,?,?,?,?,?)""",
                   (appt_id, actor_id, actor_role, action,
                    old_status, new_status, details))
    conn.commit()

def _safe_add_notification(cursor, conn, user_id, title, message, notif_type="info"):
    """Internal helper — inserts notification via open cursor (no new connection)."""
    # Infer category from notif_type
    if notif_type in ("appointment_update", "appointment"):
        category = "appointment"
    elif notif_type == "ticket":
        category = "ticket"
    elif notif_type == "alert":
        category = "alert"
    else:
        category = "general"
    cursor.execute("""INSERT INTO notifications (user_id, title, message, notif_type, category)
                      VALUES (?,?,?,?,?)""",
                   (user_id, title, message, notif_type, category))
    conn.commit()


def _get_user_contact(cursor, user_id):
    cursor.execute("SELECT full_name, email FROM users WHERE id=?", (user_id,))
    row = cursor.fetchone()
    return dict(row) if row else {"full_name": "", "email": ""}


def _doctor_slot_conflict(cursor, doctor_id, appt_date, appt_time, exclude_appt_id=None):
    active_statuses_str = ",".join(f"'{s}'" for s in APPT_ACTIVE_STATUSES)
    query = f"""SELECT id FROM appointments
                  WHERE doctor_id=? AND appt_date=? AND appt_time=?
                  AND status IN ({active_statuses_str})"""
    params = [doctor_id, appt_date, appt_time]
    if exclude_appt_id is not None:
        query += " AND id!=?"
        params.append(exclude_appt_id)
    cursor.execute(query, tuple(params))
    return cursor.fetchone() is not None


def _safe_send_appointment_email(cursor, appt_row, event, *, date_override=None, time_override=None, reason_override=None):
    try:
        from email_service import send_appointment_email
    except Exception:
        return

    patient = _get_user_contact(cursor, appt_row.get("patient_id"))
    doctor = _get_user_contact(cursor, appt_row.get("doctor_id"))
    patient_email = (patient.get("email") or "").strip()
    if not patient_email:
        return

    details = {
        "patient_name": patient.get("full_name") or "Patient",
        "doctor_name": doctor.get("full_name") or "Doctor",
        "appt_date": date_override or appt_row.get("appt_date", "—"),
        "appt_time": time_override or appt_row.get("appt_time", "—"),
        "reason": reason_override if reason_override is not None else (appt_row.get("reason", "") or "—"),
        "payment_mode": appt_row.get("payment_mode", "—"),
        "payment_status": appt_row.get("payment_status", "—"),
    }
    try:
        send_appointment_email(patient_email, patient.get("full_name") or "Patient", event, details)
    except Exception:
        pass


# ── APPOINTMENT AUDIT LOG ────────────────────────────────────────────────────

def get_appointment_audit_log(appt_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("""SELECT al.*, u.full_name as actor_name
                 FROM appointment_audit_log al
                 JOIN users u ON al.actor_id=u.id
                 WHERE al.appt_id=?
                 ORDER BY al.created_at ASC""", (appt_id,))
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return rows

def get_all_audit_logs(limit=200):
    conn = get_connection(); c = conn.cursor()
    c.execute("""SELECT al.*, u.full_name as actor_name
                 FROM appointment_audit_log al
                 JOIN users u ON al.actor_id=u.id
                 ORDER BY al.created_at DESC LIMIT ?""", (limit,))
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return rows


# ══════════════════════════════════════════════════════════════════════════════
#  TICKETS
# ══════════════════════════════════════════════════════════════════════════════

def create_ticket(appt_id, filed_by, filed_role, subject, description="",
                  ticket_type="General"):
    conn = get_connection(); c = conn.cursor()
    c.execute("""INSERT INTO appointment_tickets
                 (appt_id, filed_by, filed_role, subject, description,
                  ticket_type, status)
                 VALUES (?,?,?,?,?,?,?)""",
              (appt_id, filed_by, filed_role, subject, description,
               ticket_type, TICKET_STATUS_OPEN))
    tid = c.lastrowid
    conn.commit(); conn.close()
    admins = _get_admins()
    for a in admins:
        add_notification(a["id"], "🎫 New Support Ticket",
                        f"Ticket #{tid}: {subject}", "ticket")
    add_notification(filed_by, f"🎫 Ticket #{tid} Submitted",
                     "Your ticket has been sent to admin and is open for review.",
                     "ticket")
    return tid

def get_all_tickets(status_filter=None):
    conn = get_connection(); c = conn.cursor()
    q = """SELECT t.*, u.full_name as filed_by_name, u.role as filer_actual_role
           FROM appointment_tickets t
           JOIN users u ON t.filed_by=u.id"""
    if status_filter:
        q += f" WHERE t.status='{status_filter}'"
    q += " ORDER BY t.created_at DESC"
    c.execute(q)
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return rows

def get_tickets_by_user(user_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("""SELECT * FROM appointment_tickets
                 WHERE filed_by=? ORDER BY created_at DESC""", (user_id,))
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return rows

def update_ticket(ticket_id, status, admin_note=""):
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT * FROM appointment_tickets WHERE id=?", (ticket_id,))
    ticket = c.fetchone()
    resolved = None
    if status == TICKET_STATUS_CLOSED:
        resolved = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("""UPDATE appointment_tickets SET status=?, admin_note=?,
                 resolved_at=? WHERE id=?""",
              (status, admin_note, resolved, ticket_id))
    conn.commit(); conn.close()
    if ticket:
        ticket = dict(ticket)
        add_notification(
            ticket["filed_by"],
            f"🎫 Ticket #{ticket_id} {status}",
            f"Admin updated your ticket '{ticket.get('subject','')}'. {admin_note or 'Open the updates center to view the latest response.'}",
            "ticket",
        )

def get_open_ticket_count():
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM appointment_tickets WHERE status=?",
              (TICKET_STATUS_OPEN,))
    cnt = c.fetchone()[0]; conn.close(); return cnt


def _get_admins():
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT * FROM users WHERE role='admin'")
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return rows


# ══════════════════════════════════════════════════════════════════════════════
#  LOGIN LOGS
# ══════════════════════════════════════════════════════════════════════════════

def log_login(user_id, username, full_name, role):
    conn = get_connection(); c = conn.cursor()
    c.execute("""INSERT INTO login_logs (user_id,username,full_name,role)
                 VALUES (?,?,?,?)""",
              (user_id, username, full_name or "", role or ""))
    conn.commit(); conn.close()

def get_all_login_logs(limit=500):
    conn = get_connection(); c = conn.cursor()
    c.execute("""SELECT ll.*, u.email FROM login_logs ll
                 LEFT JOIN users u ON ll.user_id=u.id
                 ORDER BY ll.logged_in_at DESC LIMIT ?""", (limit,))
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return rows


# ══════════════════════════════════════════════════════════════════════════════
#  DOCTOR PORTFOLIO PDF
# ══════════════════════════════════════════════════════════════════════════════

def save_doctor_portfolio_pdf(doctor_id, pdf_bytes, filename="portfolio.pdf"):
    encoded = base64.b64encode(pdf_bytes).decode()
    conn = get_connection(); c = conn.cursor()
    c.execute("""INSERT INTO doctor_portfolio_pdf (doctor_id,pdf_data,filename)
                 VALUES (?,?,?)
                 ON CONFLICT(doctor_id) DO UPDATE SET
                   pdf_data=excluded.pdf_data,
                   filename=excluded.filename,
                   uploaded_at=CURRENT_TIMESTAMP""",
              (doctor_id, encoded, filename))
    conn.commit(); conn.close()

def get_doctor_portfolio_pdf(doctor_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT * FROM doctor_portfolio_pdf WHERE doctor_id=?", (doctor_id,))
    row = c.fetchone(); conn.close()
    return dict(row) if row else None

def delete_doctor_portfolio_pdf(doctor_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("DELETE FROM doctor_portfolio_pdf WHERE doctor_id=?", (doctor_id,))
    conn.commit(); conn.close()


# ══════════════════════════════════════════════════════════════════════════════
#  MEDICAL REPORTS
# ══════════════════════════════════════════════════════════════════════════════

def save_medical_report(patient_id, filename, file_bytes, file_type):
    encoded = base64.b64encode(file_bytes).decode()
    conn = get_connection(); c = conn.cursor()
    c.execute("""INSERT INTO medical_reports (patient_id,filename,file_data,file_type)
                 VALUES (?,?,?,?)""",
              (patient_id, filename, encoded, file_type))
    rid = c.lastrowid
    conn.commit(); conn.close()
    return rid

def get_medical_reports_for_patient(patient_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("""SELECT id,patient_id,filename,file_type,analysis,uploaded_at
                 FROM medical_reports WHERE patient_id=?
                 ORDER BY uploaded_at DESC""", (patient_id,))
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return rows

def get_medical_report_data(report_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT * FROM medical_reports WHERE id=?", (report_id,))
    row = c.fetchone(); conn.close()
    return dict(row) if row else None

def update_medical_report_analysis(report_id, analysis):
    conn = get_connection(); c = conn.cursor()
    c.execute("UPDATE medical_reports SET analysis=? WHERE id=?",
              (analysis, report_id))
    conn.commit(); conn.close()

def delete_medical_report(report_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("DELETE FROM medical_reports WHERE id=?", (report_id,))
    conn.commit(); conn.close()

def get_all_medical_reports_for_doctor(doctor_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("""SELECT mr.id, mr.patient_id, mr.filename, mr.file_type,
                        mr.analysis, mr.uploaded_at,
                        u.full_name as patient_name
                 FROM medical_reports mr
                 JOIN users u ON mr.patient_id=u.id
                 WHERE u.doctor_id=?
                 ORDER BY mr.uploaded_at DESC""", (doctor_id,))
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return rows