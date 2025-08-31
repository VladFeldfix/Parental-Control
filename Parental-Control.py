import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import platform
import subprocess
from datetime import datetime
from typing import Dict, Any

# ===================== CONFIG =====================
DAILY_LIMIT_SECONDS = 60*5.1         # Used only on first run if no state file exists.
WARNING_THRESHOLD_SECONDS = 300     # 5 minutes warning popup
DRY_RUN = True                     # True = no real logout; shows message instead
ENFORCE_LOGOUT_ON_CLOSE = True      # If user closes the window, enforce logout

APP_DIR_NAME = ".logout_timer"      # folder under user's home
STATE_FILENAME = "state.json"
LOG_FILENAME = "activity.log"
# ===================== THEME ======================
BG = "#0f172a"        # slate-900
BG_CARD = "#111827"   # gray-900
FG = "#e5e7eb"        # gray-200
FG_MID = "#a1a1aa"    # gray-400
ACCENT = "#22c55e"    # green-500
ACCENT_DARK = "#16a34a"
WARNING = "#f59e0b"   # amber-500
DANGER = "#ef4444"    # red-500
# ==================================================

def app_dir() -> str:
    home = os.path.expanduser("~")
    path = os.path.join(home, APP_DIR_NAME)
    os.makedirs(path, exist_ok=True)
    return path

def state_path() -> str:
    return os.path.join(app_dir(), STATE_FILENAME)

def log_path() -> str:
    return os.path.join(app_dir(), LOG_FILENAME)

def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")

def hhmmss(total_seconds: int) -> str:
    hrs = max(0, total_seconds) // 3600
    mins = (max(0, total_seconds) % 3600) // 60
    secs = max(0, total_seconds) % 60
    return f"{hrs:02d}:{mins:02d}:{secs:02d}"

def write_activity_log(entry: str) -> None:
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path(), "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {entry}\n")
    except Exception as e:
        print(f"Log write failed: {e}")

def load_state() -> Dict[str, Any]:
    """
    Load state JSON; initialize if missing or corrupted.
    IMPORTANT: We DO NOT overwrite the stored daily limit here.
    The stored value persists across runs. If absent, we use DAILY_LIMIT_SECONDS.
    """
    default_state = {
        "daily_limit_seconds": DAILY_LIMIT_SECONDS,
        "usage": {}  # "YYYY-MM-DD": int seconds used
    }
    p = state_path()
    if not os.path.exists(p):
        save_state(default_state)
        return default_state
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "usage" not in data or not isinstance(data["usage"], dict):
            data["usage"] = {}
        if "daily_limit_seconds" not in data or not isinstance(data["daily_limit_seconds"], int):
            data["daily_limit_seconds"] = DAILY_LIMIT_SECONDS
            save_state(data)
        return data
    except Exception as e:
        write_activity_log(f"State read failed, resetting. Error: {e}")
        save_state(default_state)
        return default_state

def save_state(state: Dict[str, Any]) -> None:
    p = state_path()
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, p)

def get_used_today(state: Dict[str, Any], day: str) -> int:
    return int(state["usage"].get(day, 0))

def set_used_today(state: Dict[str, Any], day: str, value: int) -> None:
    state["usage"][day] = max(0, int(value))
    save_state(state)

def add_used_today(state: Dict[str, Any], day: str, delta: int = 1) -> int:
    new_val = max(0, int(state["usage"].get(day, 0))) + int(delta)
    state["usage"][day] = new_val
    save_state(state)
    return new_val

def log_off_windows() -> None:
    """Log off the current Windows user."""
    if DRY_RUN:
        print("[DRY RUN] Would log off now.")
        messagebox.showinfo("DRY RUN", "Simulated log off (DRY_RUN=True).")
        return

    if platform.system() != "Windows":
        messagebox.showwarning("Not Windows", "This script is designed to log off on Windows only.")
        return

    try:
        # Graceful logoff (no '/f' to avoid forcing app closures)
        subprocess.run(["shutdown", "/l"], check=True)
    except Exception as e:
        try:
            import ctypes
            ctypes.windll.user32.ExitWindowsEx(0, 0)  # 0 = EWX_LOGOFF
        except Exception as e2:
            messagebox.showerror(
                "Logout Failed",
                f"Failed to log off via both methods.\n"
                f"shutdown error: {e}\nAPI error: {e2}"
            )

class DailyLogoutTimerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Daily Usage Limit — Auto Logout")
        self.root.resizable(False, False)

        # --------- Theme / Styles ----------
        style = ttk.Style()
        # 'clam' allows background colors on ttk widgets
        try:
            style.theme_use("clam")
        except Exception:
            pass

        self.style = style
        self.root.configure(bg=BG)

        style.configure("Card.TFrame", background=BG_CARD)
        style.configure("Title.TLabel", background=BG_CARD, foreground=FG_MID, font=("Segoe UI", 11))
        style.configure("Time.TLabel", background=BG_CARD, foreground=FG, font=("Consolas", 48, "bold"))
        style.configure("Info.TLabel", background=BG_CARD, foreground=FG_MID, font=("Segoe UI", 10))
        style.configure("PopupTitle.TLabel", background=BG_CARD, foreground=FG, font=("Segoe UI", 13, "bold"))
        style.configure("PopupBody.TLabel", background=BG_CARD, foreground=FG_MID, font=("Segoe UI", 10))

        style.configure("Accent.TButton", font=("Segoe UI", 11, "bold"))
        # ttk button color mapping (works on 'clam' with layout tweaks)
        style.map("Accent.TButton",
                  foreground=[("disabled", "#7c7c7c"), ("!disabled", "#ffffff")],
                  background=[("pressed", ACCENT_DARK), ("active", ACCENT_DARK), ("!active", ACCENT)]
                  )

        style.configure("Time.Horizontal.TProgressbar", troughcolor=BG, background=ACCENT, bordercolor=BG_CARD, lightcolor=ACCENT, darkcolor=ACCENT)

        # Center window roughly
        self.root.geometry("+320+220")

        # --------- State ----------
        self.state = load_state()
        self.day = today_str()
        self.daily_limit = int(self.state.get("daily_limit_seconds", DAILY_LIMIT_SECONDS))
        self.used_today = get_used_today(self.state, self.day)
        self.remaining = max(0, self.daily_limit - self.used_today)

        self.warning_threshold = WARNING_THRESHOLD_SECONDS
        self.warning_shown = False

        # --------- UI Layout ----------
        outer = tk.Frame(self.root, bg=BG)
        outer.pack(padx=18, pady=18)

        card = ttk.Frame(outer, style="Card.TFrame")
        card.pack(fill="both", expand=True, padx=2, pady=2)

        # Title / info
        self.info_label = ttk.Label(
            card,
            text=f"Daily limit: {hhmmss(self.daily_limit)}   •   Used: {hhmmss(self.used_today)}",
            style="Title.TLabel"
        )
        self.info_label.pack(padx=20, pady=(16, 8))

        # Big time display
        self.time_label = ttk.Label(
            card,
            text=hhmmss(self.remaining),
            style="Time.TLabel",
            anchor="center"
        )
        self.time_label.pack(padx=20, pady=(6, 6))

        # Progress bar
        self.progress = ttk.Progressbar(
            card,
            style="Time.Horizontal.TProgressbar",
            length=420,
            maximum=max(1, self.daily_limit),
            mode="determinate"
        )
        self.progress.pack(padx=20, pady=(6, 2))
        self.progress["value"] = self.used_today

        # Secondary info
        self.subinfo_label = ttk.Label(
            card,
            text="Time remaining today",
            style="Info.TLabel"
        )
        self.subinfo_label.pack(padx=20, pady=(0, 12))

        # Action button
        self.pause_button = ttk.Button(
            card,
            text="Pause & Log Out",
            style="Accent.TButton",
            command=self.pause_and_logout
        )
        self.pause_button.pack(pady=(4, 16))

        # Close behavior
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Start immediately
        if self.remaining <= 0:
            write_activity_log(f"Start: daily time already exhausted for {self.day} -> logging out.")
            self.logoff_and_quit()
        else:
            write_activity_log(
                f"Start: remaining {hhmmss(self.remaining)} "
                f"(used {hhmmss(self.used_today)} of {hhmmss(self.daily_limit)})"
            )
            # Show warning immediately if already under threshold
            if self.daily_limit >= self.warning_threshold and self.remaining <= self.warning_threshold:
                self.show_warning_popup()
            self.tick()

    # ---------- Behavior helpers ----------
    def rollover_if_new_day(self):
        now_day = today_str()
        if now_day != self.day:
            self.day = now_day
            self.used_today = get_used_today(self.state, self.day)
            self.remaining = max(0, self.daily_limit - self.used_today)
            self.warning_shown = False  # allow warning again on new day
            write_activity_log(f"Date rollover to {self.day}. Used: {self.used_today}s. Remaining: {self.remaining}s.")
            # Reset progressbar maximum if daily limit changed externally
            self.progress.configure(maximum=max(1, self.daily_limit))

    def update_visuals(self):
        self.time_label.config(text=hhmmss(self.remaining))
        self.info_label.config(text=f"Daily limit: {hhmmss(self.daily_limit)}   •   Used: {hhmmss(self.used_today)}")
        self.progress["maximum"] = max(1, self.daily_limit)
        self.progress["value"] = min(self.daily_limit, self.used_today)

        # Change progress color when near threshold / danger
        if self.remaining <= 60:
            self.style.configure("Time.Horizontal.TProgressbar", background=DANGER, lightcolor=DANGER, darkcolor=DANGER)
        elif self.remaining <= self.warning_threshold:
            self.style.configure("Time.Horizontal.TProgressbar", background=WARNING, lightcolor=WARNING, darkcolor=WARNING)
        else:
            self.style.configure("Time.Horizontal.TProgressbar", background=ACCENT, lightcolor=ACCENT, darkcolor=ACCENT)

    def maybe_show_warning(self):
        """Show 5-min warning once per app run when crossing threshold."""
        if self.warning_shown:
            return
        if self.daily_limit >= self.warning_threshold and self.remaining <= self.warning_threshold and self.remaining > 0:
            self.show_warning_popup()

    def show_warning_popup(self):
        self.warning_shown = True
        self.root.bell()
        top = tk.Toplevel(self.root)
        top.title("Time Running Out")
        top.configure(bg=BG)
        top.attributes("-topmost", True)
        top.resizable(False, False)
        top.transient(self.root)
        top.grab_set()  # modal until OK pressed

        # Center relative to root
        self.root.update_idletasks()
        rx = self.root.winfo_rootx()
        ry = self.root.winfo_rooty()
        rw = self.root.winfo_width()
        rh = self.root.winfo_height()
        w, h = 420, 180
        x = rx + (rw - w) // 2
        y = ry + (rh - h) // 2
        top.geometry(f"{w}x{h}+{x}+{y}")

        card = ttk.Frame(top, style="Card.TFrame")
        card.pack(fill="both", expand=True, padx=10, pady=10)

        title = ttk.Label(card, text="Less than 05:00 minutes left", style="PopupTitle.TLabel")
        title.pack(padx=16, pady=(14, 8))

        body = ttk.Label(
            card,
            text="Please save your work. You will be logged out automatically when your time runs out.",
            style="PopupBody.TLabel",
            wraplength=360,
            justify="center"
        )
        body.pack(padx=16, pady=(0, 12))

        ok_btn = ttk.Button(card, text="OK", style="Accent.TButton", command=top.destroy)
        ok_btn.pack(pady=(0, 12))

        top.update_idletasks()
        top.lift()
        top.focus_force()

    # ---------- Timer loop ----------
    def tick(self):
        self.rollover_if_new_day()

        if self.remaining <= 0:
            write_activity_log("Countdown reached zero -> logging out.")
            self.logoff_and_quit()
            return

        # Update visuals and possibly show warning
        self.update_visuals()
        self.maybe_show_warning()

        # Consume one second and persist usage
        self.used_today = add_used_today(self.state, self.day, 1)
        self.remaining = max(0, self.daily_limit - self.used_today)

        # Schedule next tick
        self.root.after(1000, self.tick)

    def pause_and_logout(self):
        write_activity_log(f"Pause button pressed with {hhmmss(self.remaining)} remaining. Logging out.")
        self.logoff_and_quit()

    def logoff_and_quit(self):
        # Disable button to avoid double action
        self.pause_button.config(state="disabled")
        self.root.update_idletasks()

        log_off_windows()  # respects DRY_RUN

        try:
            self.root.destroy()
        except Exception:
            pass

    def on_close(self):
        if ENFORCE_LOGOUT_ON_CLOSE:
            write_activity_log("Window closed by user -> enforcing logout.")
            self.logoff_and_quit()
        else:
            write_activity_log("Window closed by user -> exiting without logout (not enforced).")
            self.root.destroy()

def main():
    root = tk.Tk()
    app = DailyLogoutTimerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()