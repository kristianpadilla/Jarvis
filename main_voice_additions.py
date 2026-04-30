# ════════════════════════════════════════════════════════════════
# MAIN.PY — VOICE COMMAND ADDITIONS FOR CYPHER 5
# Drop these into your handle_command() function
# alongside your existing timer/calendar/mode handlers
# ════════════════════════════════════════════════════════════════

import re
import dateparser
import requests

BASE_URL = "http://localhost:5000"

def log_session(text):
    """Post an entry to the session log."""
    try:
        requests.post(f"{BASE_URL}/session-log/add",
                      json={"text": text}, timeout=2)
    except:
        pass

# ─────────────────────────────────────────────────────
# ADD THIS BLOCK inside your handle_command() function,
# after your existing elif blocks for timer/calendar/etc.
# ─────────────────────────────────────────────────────

def handle_command_additions(command: str) -> str | None:
    """
    Returns a response string if command was handled, else None.
    Call this inside your handle_command() before falling through to Claude.
    
    Usage inside handle_command():
        result = handle_command_additions(command)
        if result:
            return result
    """
    cmd = command.lower().strip()

    # ── GOALS ──────────────────────────────────────────────────

    # "add a goal: finish the slides"
    # "add goal: work out"
    if re.search(r'add (a )?goal[s]?\s*[:\-]\s*', cmd):
        match = re.search(r'add (a )?goal[s]?\s*[:\-]\s*(.+)', cmd, re.IGNORECASE)
        if match:
            goal_text = match.group(2).strip()
            try:
                r = requests.post(f"{BASE_URL}/goals/add",
                                  json={"text": goal_text}, timeout=3)
                data = r.json()
                if data.get("status") == "ok":
                    log_session(f"Goal added: {goal_text}")
                    return f"Got it. I've added your goal: {goal_text}. You've got this, Nine."
                else:
                    return "You already have three goals set for today. Clear them first if you want to add more."
            except Exception as e:
                return f"Couldn't reach the goal system. Error: {e}"

    # "mark goal 1 done" / "check off goal 2" / "complete goal 3"
    if re.search(r'(mark|check off|complete|finish|done)\s+goal\s+(\d)', cmd):
        match = re.search(r'(\d)', cmd)
        if match:
            idx = int(match.group(1)) - 1  # convert to 0-indexed
            try:
                r = requests.post(f"{BASE_URL}/goals/toggle",
                                  json={"index": idx}, timeout=3)
                if r.json().get("status") == "ok":
                    log_session(f"Goal {idx+1} toggled")
                    return f"Goal {idx+1} toggled. Nice work."
                else:
                    return f"Couldn't find goal {idx+1}. Check your goal list."
            except Exception as e:
                return f"Goal toggle failed: {e}"

    # "clear my goals" / "reset goals" / "wipe goals"
    if re.search(r'(clear|reset|wipe|delete)\s+(my\s+)?goals', cmd):
        try:
            requests.post(f"{BASE_URL}/goals/clear", timeout=3)
            log_session("Daily goals cleared")
            return "Goals cleared. Fresh slate for the rest of the day."
        except Exception as e:
            return f"Couldn't clear goals: {e}"

    # "what are my goals" / "show me my goals"
    if re.search(r'(what|show|list).*(my\s+)?goals', cmd):
        try:
            r = requests.get(f"{BASE_URL}/goals", timeout=3)
            data = r.json()
            goals = data.get("goals", [])
            if not goals:
                return "No goals set for today. You can add up to three — just say 'add a goal' followed by what you want to get done."
            lines = []
            for i, g in enumerate(goals):
                status = "✓" if g["done"] else "○"
                lines.append(f"{status} {i+1}. {g['text']}")
            return "Here are your goals for today:\n" + "\n".join(lines)
        except Exception as e:
            return f"Couldn't fetch goals: {e}"

    # ── COUNTDOWN ──────────────────────────────────────────────

    # "count down to graduation on June 15th"
    # "add a countdown to my birthday on December 3rd"
    # "count down to vacation May 20 2025"
    countdown_match = re.search(
        r'(count down to|countdown to|add a? countdown to)\s+(.+?)\s+on\s+(.+)',
        cmd, re.IGNORECASE
    )
    if not countdown_match:
        # Try alternative: "count down to [label] [date]" without "on"
        countdown_match = re.search(
            r'(count down to|countdown to)\s+(.+?)\s+(january|february|march|april|may|june|july|august|september|october|november|december|\d{1,2}/\d{1,2})',
            cmd, re.IGNORECASE
        )
        if countdown_match:
            label = countdown_match.group(2).strip().title()
            date_str = cmd[countdown_match.start(3):]
        else:
            label = None
            date_str = None
    else:
        label = countdown_match.group(2).strip().title()
        date_str = countdown_match.group(3).strip()

    if label and date_str:
        parsed_date = dateparser.parse(date_str, settings={"PREFER_DATES_FROM": "future"})
        if parsed_date:
            iso_date = parsed_date.strftime("%Y-%m-%d")
            friendly = parsed_date.strftime("%B %d, %Y")
            try:
                r = requests.post(f"{BASE_URL}/countdown/add",
                                  json={"label": label, "date": iso_date}, timeout=3)
                if r.json().get("status") == "ok":
                    log_session(f"Countdown added: {label} → {friendly}")
                    days_left = (parsed_date.date() - __import__('datetime').date.today()).days
                    return f"Countdown added. {label} is on {friendly} — {days_left} days from now."
                else:
                    return "Couldn't add that countdown."
            except Exception as e:
                return f"Countdown add failed: {e}"
        else:
            return f"I couldn't parse that date. Try something like 'count down to graduation on June 15th'."

    # "delete countdown 1" / "remove countdown 2"
    del_match = re.search(r'(delete|remove|cancel)\s+countdown\s+(\d+)', cmd)
    if del_match:
        idx = int(del_match.group(2)) - 1
        try:
            r = requests.post(f"{BASE_URL}/countdown/delete",
                              json={"index": idx}, timeout=3)
            if r.json().get("status") == "ok":
                log_session(f"Countdown {idx+1} deleted")
                return f"Countdown {idx+1} removed."
            else:
                return f"No countdown at position {idx+1}."
        except Exception as e:
            return f"Countdown delete failed: {e}"

    # ── Nothing matched ────────────────────────────────────────
    return None


# ════════════════════════════════════════════════════════════════
# HOW TO WIRE THIS INTO YOUR EXISTING handle_command():
#
# At the TOP of your handle_command() function, before your
# existing if/elif chain, add:
#
#     result = handle_command_additions(command)
#     if result:
#         return result
#
# That's it — it slots in cleanly without touching existing logic.
# ════════════════════════════════════════════════════════════════


# ════════════════════════════════════════════════════════════════
# SESSION LOG CALLS — Add these to your existing handlers:
# ════════════════════════════════════════════════════════════════
#
# In your timer SET handler, add:
#     log_session(f"Timer set — {minutes}m {seconds}s")
#
# In your timer CANCEL/RESET handler, add:
#     log_session("Timer cancelled")
#
# In your mode switch handler, add:
#     log_session(f"Mode → {mode_name.upper()}")
#
# In your calendar ADD handler, add:
#     log_session(f"Event added: {title} on {date}")
#
# In your app OPEN handler, add:
#     log_session(f"Opened {app_name}")
#
# ════════════════════════════════════════════════════════════════
