"""
utils.py – Shared helpers: datetime bar, avatars, profile cards, themes,
and region-default timestamp rendering.

This version contains a SIGNIFICANTLY hardened `inject_tab_persistence()`
implementation that prevents Streamlit's `st.tabs` from snapping back to
the first tab whenever a button / form / chat send triggers a rerun.

Key design points of the new implementation:
  • A single global handler is registered on the parent window (the actual
    Streamlit page DOM), guarded by `window.__gsTabPersistInit` so we
    never bind more than once even if the helper is called from many
    places.
  • Tab state is keyed by a *stable signature* of the cleaned tab labels
    (numeric badges like "🔴3" / "(5)" stripped) so the saved index
    survives badge re-renders.
  • Two complementary mechanisms keep the active tab in place:
      1. A click listener saves the chosen tab index to `sessionStorage`.
      2. A permanent `MutationObserver` plus a long-running interval
         restores the saved index every time Streamlit rebuilds the
         tab list (which happens on every rerun).
  • A small CSS block briefly hides freshly-rendered tab panels until
    the correct one has been activated, eliminating the visible flicker
    where the user sees tab 0 for a split second before being snapped
    back to the saved tab.
"""

from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from time_utils import (
    DEFAULT_TIMEZONE,
    format_db_time,
    format_db_timestamp,
    sanitize_timezone,
    tz_label,
)


APP_TIMEZONE = sanitize_timezone(DEFAULT_TIMEZONE)
APP_TZ_LABEL = tz_label(APP_TIMEZONE)


# ── GLOBAL TAB PERSISTENCE ───────────────────────────────────────────────────
def inject_tab_persistence():
    """Persist Streamlit tab selection across reruns in the current browser tab.

    Streamlit's native ``st.tabs`` widget is *stateless*: every rerun rebuilds
    the tab list and forces the first tab to become active.  This helper
    patches that behaviour purely on the client side, so:

      • Clicking any button inside a tab no longer kicks you back to tab 0.
      • Sending a chat message, adding a note, rescheduling/cancelling an
        appointment, downloading a PDF, etc. all keep you on the tab you
        were already viewing.
      • Badge counts (e.g. "💬 Chat 🔴3") can change without losing the
        saved selection — labels are normalised before being hashed.

    Call this helper exactly once per script run (e.g. from ``main.py``
    right after the user is authenticated).
    """
    components.html(
        """
        <script>
        (function () {
          // We operate on the parent (top-level Streamlit) document because
          // this `components.html` block lives inside a sandboxed iframe.
          let parentWin;
          try { parentWin = window.parent; } catch (e) { return; }
          if (!parentWin) return;
          const doc = parentWin.document;
          if (!doc || !doc.body) return;

          // Re-register on every script run so that hot-reloads pick up the
          // newest logic, but skip the heavy DOM-wide setup if it has
          // already been done in this browser tab.
          const ALREADY = '__gsTabPersistInit_v3';
          if (parentWin[ALREADY]) return;
          parentWin[ALREADY] = true;

          const storage = parentWin.sessionStorage;
          const pageKey = (parentWin.location.pathname || '/') +
                          (parentWin.location.search   || '');
          const keyPrefix = 'gs_tab_state_v3:' + pageKey + ':';

          // Strip dynamic markers so the signature stays stable when badge
          // counts update — e.g. "💬 Chat 🔴3" and "💬 Chat" must produce
          // the same signature so the saved index survives.
          function cleanLabel(txt) {
            return String(txt || '')
              .replace(/🔴\\s*\\d*/g, '')
              .replace(/🟣\\s*\\d*/g, '')
              .replace(/🟡\\s*\\d*/g, '')
              .replace(/🟢\\s*\\d*/g, '')
              .replace(/\\s*\\(\\d+\\)\\s*/g, ' ')
              .replace(/[\\u200B-\\u200D\\uFEFF]/g, '')
              .replace(/\\s+/g, ' ')
              .trim();
          }

          function signature(tabs) {
            return tabs.map(t => cleanLabel(t.innerText)).join('||');
          }

          // Briefly hide tab panels for the very first paint so the user
          // never sees tab[0] flash before we restore the correct tab.
          // Each tab-list gets its own short window; after that we stop
          // hiding so subsequent renders are instant.
          function hidePanels(list) {
            try {
              // Find the panel container that follows the tab-list.
              const wrapper = list.closest('.stTabs') || list.parentElement;
              if (!wrapper) return null;
              const panels = wrapper.querySelectorAll('[data-baseweb="tab-panel"]');
              panels.forEach(p => { p.style.visibility = 'hidden'; });
              return panels;
            } catch (e) { return null; }
          }
          function showPanels(panels) {
            if (!panels) return;
            panels.forEach(p => { p.style.visibility = ''; });
          }

          function processTabList(list) {
            const tabs = Array.from(list.querySelectorAll('[data-baseweb="tab"]'));
            if (!tabs.length) return;

            const sig = signature(tabs);
            if (!sig) return;
            const storageKey = keyPrefix + sig;

            // (Re)bind a click handler on every tab. The handler is
            // idempotent: each tab remembers the last storageKey it was
            // bound for, so we never attach duplicates.
            tabs.forEach((tab, idx) => {
              if (tab.dataset.gsBound === storageKey) return;
              tab.dataset.gsBound = storageKey;
              tab.addEventListener('click', () => {
                // Ignore clicks that we ourselves dispatch while restoring.
                if (tab.dataset.gsRestoring === '1') return;
                try { storage.setItem(storageKey, String(idx)); } catch (e) {}
              }, true);
            });

            // Restore the saved tab (if any) when the live DOM disagrees
            // with what we have on record.
            const saved = storage.getItem(storageKey);
            if (saved === null) return;
            const idx = parseInt(saved, 10);
            if (!(idx >= 0 && idx < tabs.length)) return;

            const activeIdx = tabs.findIndex(
              t => t.getAttribute('aria-selected') === 'true');
            if (idx === activeIdx) return;

            // Hide panels for a moment to avoid the wrong-tab flash.
            const panels = hidePanels(list);
            tabs[idx].dataset.gsRestoring = '1';
            try { tabs[idx].click(); } catch (e) {}
            // Give Streamlit a tick to swap the panel, then unhide.
            setTimeout(() => {
              tabs[idx].dataset.gsRestoring = '0';
              showPanels(panels);
            }, 60);
          }

          function scan() {
            const lists = doc.querySelectorAll('[data-baseweb="tab-list"]');
            lists.forEach(processTabList);
          }

          // Run once immediately, then watch the DOM forever.  The
          // observer is the workhorse — every Streamlit rerun replaces
          // the tab nodes and the observer reacts within a few ms.
          scan();
          try {
            const obs = new parentWin.MutationObserver(() => scan());
            obs.observe(doc.body, { childList: true, subtree: true });
          } catch (e) {}

          // Safety net: a low-frequency interval that keeps scanning for
          // ~20 seconds after page load to cover edge cases where the
          // MutationObserver missed an update.
          let n = 0;
          const intv = parentWin.setInterval(() => {
            scan();
            if (++n > 200) parentWin.clearInterval(intv);
          }, 100);
        })();
        </script>
        """,
        height=0,
        scrolling=False,
    )


# ── REGION / DEFAULT DateTime Bar ─────────────────────────────────────────────
def show_datetime_bar(timezone_name: str | None = None):
    """Live region-default date/time bar shown at the top of the app."""
    tz_name = sanitize_timezone(timezone_name or APP_TIMEZONE)
    tz_short = tz_label(tz_name)
    components.html(
        f"""
        <div id="datetime-bar" style="
            background: linear-gradient(90deg,#0d1b2a 0%,#1b2838 100%);
            border-bottom: 1px solid #2a3a5a;
            padding: 6px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-family: 'Nunito', sans-serif;
            font-size: 0.82rem;
            color: #aab4c8;
        ">
            <span style="color:#ff4b4b;font-weight:700;font-size:0.85rem;">🧠 Stress Level Detector</span>
            <span style="display:flex;gap:18px;align-items:center;">
                <span>📅 <span id="date-display"></span></span>
                <span style="color:#2a3a5a;">|</span>
                <span>🕐 {tz_short} <span id="time-display" style="color:#00d4ff;font-weight:700;font-size:0.88rem;"></span></span>
                <span style="color:#2a3a5a;">|</span>
                <span style="color:#00ff88;font-size:0.75rem;" id="day-display"></span>
            </span>
        </div>
        <script>
        (function() {{
            const timeZone = {tz_name!r};
            function parts(opts) {{
                return new Intl.DateTimeFormat('en-IN', Object.assign({{ timeZone }}, opts))
                    .formatToParts(new Date())
                    .reduce((acc, part) => {{ acc[part.type] = part.value; return acc; }}, {{}});
            }}
            function updateDT() {{
                const d = parts({{ weekday:'long', day:'2-digit', month:'long', year:'numeric', hour:'2-digit', minute:'2-digit', second:'2-digit', hour12:false }});
                const dateEl = document.getElementById('date-display');
                const timeEl = document.getElementById('time-display');
                const dayEl  = document.getElementById('day-display');
                if (dateEl) dateEl.innerText = `${{d.day}} ${{d.month}} ${{d.year}}`;
                if (timeEl) timeEl.innerText = `${{d.hour}}:${{d.minute}}:${{d.second}}`;
                if (dayEl) dayEl.innerText = d.weekday || '';
            }}
            updateDT();
            setInterval(updateDT, 1000);
        }})();
        </script>
        """,
        height=40,
        scrolling=False,
    )


def get_user_timezone(user: dict | None = None) -> str:
    return sanitize_timezone((user or {}).get("timezone") or APP_TIMEZONE)


# ── AVATAR ────────────────────────────────────────────────────────────────────
def avatar_html(photo_data_uri, name, size=52, border_color="#00d4ff"):
    """Returns HTML for a circular avatar with photo or initials fallback."""
    if photo_data_uri:
        return (
            f"<img src='{photo_data_uri}' "
            f"style='width:{size}px;height:{size}px;object-fit:cover;"
            f"border-radius:50%;border:2px solid {border_color};'>"
        )
    initials = "".join([w[0].upper() for w in str(name).split()[:2]])
    return (
        f"<div style='width:{size}px;height:{size}px;border-radius:50%;"
        f"background:linear-gradient(135deg,{border_color}44,{border_color}88);"
        f"border:2px solid {border_color};display:inline-flex;"
        f"align-items:center;justify-content:center;"
        f"font-size:{size//2.5:.0f}px;font-weight:800;color:{border_color};'>"
        f"{initials}</div>"
    )


# ── SIDEBAR PROFILE CARD ──────────────────────────────────────────────────────
def sidebar_profile_card(user, accent_color):
    photo = user.get('profile_photo') or ''
    name  = user.get('full_name', 'User')
    role  = user.get('role', '')
    bio   = user.get('bio') or ''
    tz_display = tz_label(get_user_timezone(user))

    if photo:
        img_html = (
            f"<img src='{photo}' style='width:72px;height:72px;"
            f"object-fit:cover;border-radius:50%;border:3px solid {accent_color};'>"
        )
    else:
        initials = "".join([w[0].upper() for w in name.split()[:2]])
        img_html = (
            f"<div style='width:72px;height:72px;border-radius:50%;"
            f"background:linear-gradient(135deg,{accent_color}44,{accent_color}99);"
            f"border:3px solid {accent_color};display:inline-flex;align-items:center;"
            f"justify-content:center;font-size:24px;font-weight:900;color:{accent_color};'>"
            f"{initials}</div>"
        )

    role_icons  = {'admin': '🔴', 'doctor': '🩺', 'patient': '👤'}
    role_colors = {'admin': '#ff4b4b', 'doctor': '#00d4ff', 'patient': '#00ff88'}
    rc = role_colors.get(role, accent_color)
    bio_html = (
        f"<div style='font-size:0.75rem;color:#888;margin-top:4px;'>{bio[:60]}{'...' if len(bio) > 60 else ''}</div>"
    ) if bio else ''

    st.markdown(
        f"""
        <div style='text-align:center;padding:14px 0 10px;border-bottom:1px solid #2a3a5a;margin-bottom:12px;'>
            {img_html}
            <div style='font-size:1rem;font-weight:800;color:white;margin-top:8px;'>{name}</div>
            <div style='font-size:0.72rem;color:{rc};letter-spacing:1.5px;text-transform:uppercase;font-weight:700;'>
                {role_icons.get(role, '')} {role.upper()}
            </div>
            <div style='font-size:0.72rem;color:#8fb3c9;margin-top:4px;'>🌍 {tz_display}</div>
            {bio_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── ROLE THEME ────────────────────────────────────────────────────────────────
def role_theme(role):
    """Returns (accent_color, bg_gradient, border_color)."""
    themes = {
        'admin':   ('#ff4b4b', 'linear-gradient(135deg,#1a0a0a,#2a1010)', '#ff4b4b'),
        'doctor':  ('#00d4ff', 'linear-gradient(135deg,#0a1628,#0d2035)', '#00d4ff'),
        'patient': ('#00ff88', 'linear-gradient(135deg,#081a12,#0d2018)', '#00ff88'),
    }
    return themes.get(role, ('#ffffff', '#0e1117', '#ffffff'))


# ── TIMESTAMP FORMATTERS ──────────────────────────────────────────────────────
def to_local_str(utc_str: str, timezone_name: str | None = None) -> str:
    return format_db_time(utc_str, timezone_name or APP_TIMEZONE)


def to_local_full(utc_str: str, timezone_name: str | None = None) -> str:
    return format_db_timestamp(utc_str, timezone_name or APP_TIMEZONE)


# Backward-compatible aliases used across the project

def to_ist_str(utc_str: str, timezone_name: str | None = None) -> str:
    return to_local_str(utc_str, timezone_name)


def to_ist_full(utc_str: str, timezone_name: str | None = None) -> str:
    return to_local_full(utc_str, timezone_name)


# ── UNREAD DOT HTML ───────────────────────────────────────────────────────────
def unread_dot(count: int, color: str = "#ff4b4b") -> str:
    if count > 0:
        return (
            f"<span style='background:{color};color:white;border-radius:50%;"
            f"width:18px;height:18px;display:inline-flex;align-items:center;"
            f"justify-content:center;font-size:0.65rem;font-weight:900;'>"
            f"{count if count < 99 else '99+'}</span>"
        )
    return ""
