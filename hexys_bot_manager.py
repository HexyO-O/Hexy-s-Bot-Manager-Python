"""
╔══════════════════════════════════════════════════╗
║             Hexy's Bot Manager                   ║
║         Open-Source Bot Management Suite         ║
╚══════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  PLUGIN / FEATURE SYSTEM — HOW TO ADD YOUR OWN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Find the FEATURES list below (search "FEATURES =").
  Each entry is a dict with these keys:

    "name"        – Display name shown in the UI
    "description" – Short description shown under the button
    "script"      – Python file to run (relative to this script's folder)
                    Set to None for built-in features.
    "builtin"     – True = handled internally, False = launches your script

  When your feature script is toggled ON or OFF, it is launched like this:

    python your_script.py --token BOT_TOKEN --state on|off

  Your script receives:
    sys.argv[1]  →  "--token"
    sys.argv[2]  →  the bot token string
    sys.argv[3]  →  "--state"
    sys.argv[4]  →  "on" or "off"

  The script's terminal window is automatically minimized on Windows
  so it stays out of the way.

  Example feature entry:
    {
        "name":        "Auto Responder",
        "description": "Replies to keywords automatically.",
        "script":      "auto_responder.py",
        "builtin":     False,
    },
"""

# ══════════════════════════════════════════════════════════════════════════════
# ▶  FEATURES LIST — Edit this to add your own features
# ══════════════════════════════════════════════════════════════════════════════
FEATURES = [
    {
        "name":        "Lockdown Bot",
        "description": "Prevents the bot from sending messages or\n"
                       "responding to any slash commands.",
        "script":      None,     # Built-in — handled by this file
        "builtin":     True,
        "builtin_key": "lockdown",
    },
    # ── Add your own features below this line ─────────────────────────────────
    {
        "name":        "Weather Command",
        "description": "Adds /weather — lets users pick any city worldwide\n"
                       "and get live weather data. Free API, no key needed.",
        "script":      "weather_plugin.py",
        "builtin":     False,
    },
    # {
    #     "name":        "Auto Responder",
    #     "description": "Replies to trigger keywords automatically.",
    #     "script":      "auto_responder.py",
    #     "builtin":     False,
    # },
]
# ══════════════════════════════════════════════════════════════════════════════


# ─── Dependency bootstrapper (runs before anything else) ──────────────────────
import sys
import subprocess
import importlib

REQUIRED = {
    "discord":    "discord.py",
    "requests":   "requests",
    "PIL":        "Pillow",
    "pypresence": "pypresence",
    "aiohttp":    "aiohttp",
}

def check_and_install_deps():
    missing = []
    for module, package in REQUIRED.items():
        try:
            importlib.import_module(module)
        except ImportError:
            missing.append(package)

    if not missing:
        return

    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("Hexy's Bot Manager – First-Time Setup")
    root.geometry("480x210")
    root.configure(bg="#1a1a2e")
    root.resizable(False, False)

    tk.Label(root, text="Installing missing dependencies…",
             bg="#1a1a2e", fg="#e0e0ff",
             font=("Segoe UI", 12, "bold")).pack(pady=(28, 8))
    bar = ttk.Progressbar(root, length=400, mode="determinate",
                          maximum=len(missing))
    bar.pack(pady=6)
    status = tk.Label(root, text="", bg="#1a1a2e", fg="#9090c0",
                      font=("Segoe UI", 9))
    status.pack(pady=2)
    root.update()

    for i, pkg in enumerate(missing):
        status.config(text=f"pip install {pkg} …")
        bar["value"] = i
        root.update()
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", pkg, "--quiet"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        bar["value"] = i + 1
        root.update()

    status.config(text="✓ All done!  Launching Hexy's Bot Manager…")
    root.update()
    root.after(1600, root.destroy)
    root.mainloop()


check_and_install_deps()

# ─── Full imports ─────────────────────────────────────────────────────────────
import os
import json
import time
import asyncio
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from io import BytesIO

import requests
from PIL import Image, ImageTk, ImageDraw
import discord
from discord.ext import commands
from pypresence import Presence

# ─── Config ───────────────────────────────────────────────────────────────────
APP_NAME    = "Hexy's Bot Manager"
APP_ID      = "1477145298085351575"
PROJECT_DIR = Path(__file__).parent
ICON_NAME   = "Moon"
CONFIG_FILE = PROJECT_DIR / "hexy_config.json"
LOG_MAX     = 300

BG_DARK   = "#0d0d1a";  BG_PANEL  = "#111128";  BG_CARD   = "#18183a"
ACCENT    = "#7b5ea7";  ACCENT_LT = "#a07dd0";  TXT_PRI   = "#e8e8ff"
TXT_SEC   = "#8888aa";  TXT_MUT   = "#454565";  BORDER    = "#252548"
LOG_BG    = "#09091e";  SUCCESS   = "#4caf8a";  WARNING   = "#f0a050"
ERR       = "#e05070";  LOCK_RED  = "#c0304a";  LOCK_BG   = "#200010"

# ─── Project structure ────────────────────────────────────────────────────────
def ensure_project_structure():
    for folder in ("logs", "plugins", "assets"):
        (PROJECT_DIR / folder).mkdir(exist_ok=True)
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(json.dumps({"token": "", "last_launch": ""}, indent=2))

ensure_project_structure()

# ─── Icon helpers ─────────────────────────────────────────────────────────────
def find_icon():
    for ext in (".ico", ".png", ".jpg", ".jpeg", ".webp", ".bmp"):
        p = PROJECT_DIR / (ICON_NAME + ext)
        if p.exists():
            return p
    return None

def to_ico(src):
    try:
        out = PROJECT_DIR / "Moon.ico"
        img = Image.open(src).convert("RGBA").resize((256, 256), Image.LANCZOS)
        img.save(out, format="ICO",
                 sizes=[(256,256),(128,128),(64,64),(32,32),(16,16)])
        return out
    except Exception:
        return None

def set_taskbar_icon(root, ico):
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "Hexy.BotManager.1")
        root.iconbitmap(str(ico))
        root.wm_iconbitmap(str(ico))
    except Exception:
        pass

def circle_photo(src, size):
    try:
        img  = Image.open(src).convert("RGBA").resize(size, Image.LANCZOS)
        mask = Image.new("L", size, 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size[0]-1, size[1]-1), fill=255)
        img.putalpha(mask)
        return ImageTk.PhotoImage(img)
    except Exception:
        return None

# ─── Rich Presence ────────────────────────────────────────────────────────────
class RPCThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.rpc = None
        self.active = False

    def run(self):
        try:
            self.rpc = Presence(APP_ID)
            self.rpc.connect()
            self.rpc.update(
                details="Using Hexy's Bot Manager",
                state="Managing a Discord Bot",
                large_image="moon",
                large_text="Hexy's Bot Manager",
                start=int(time.time()),
            )
            self.active = True
            while self.active:
                time.sleep(15)
        except Exception:
            pass

    def stop(self):
        self.active = False
        try:
            if self.rpc:
                self.rpc.clear()
                time.sleep(0.3)
                self.rpc.close()
        except Exception:
            pass

# ─── Plugin launcher ──────────────────────────────────────────────────────────
def launch_feature_script(script_name: str, token: str, state: str):
    """
    Launch a feature script in a minimized terminal window.
    Passes --token and --state arguments to the script.
    """
    script_path = PROJECT_DIR / script_name
    if not script_path.exists():
        return False, f"Script not found: {script_path}"

    try:
        kwargs = {
            "args": [sys.executable, str(script_path),
                     "--token", token,
                     "--state", state],
        }

        if sys.platform == "win32":
            # Minimize the console window so it doesn't get in the way
            si = subprocess.STARTUPINFO()
            si.dwFlags    |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 6   # SW_MINIMIZE
            kwargs["startupinfo"] = si
            kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
        else:
            kwargs["start_new_session"] = True

        subprocess.Popen(**kwargs)
        return True, "OK"
    except Exception as e:
        return False, str(e)

# ─── Discord bot wrapper ──────────────────────────────────────────────────────
class BotWrapper:
    def __init__(self, log_cb):
        self.log_cb       = log_cb
        self.bot          = None
        self.loop         = asyncio.new_event_loop()
        self.thread       = None
        self.running      = False
        self.info         = {}
        self.lockdown     = False   # ← lockdown state flag
        self._token       = ""

    # ── Public API ────────────────────────────────────────────────────────────
    def start(self, token: str):
        if self.running:
            return
        self._token = token
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        self.running = True

    def stop(self):
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self._shutdown(), self.loop)
        self.running = False

    def set_lockdown(self, active: bool):
        """Toggle lockdown mode (thread-safe)."""
        self.lockdown = active
        state = "ENABLED 🔒" if active else "DISABLED 🔓"
        self.log_cb(f"Lockdown {state}", "WARNING" if active else "SUCCESS")

    @property
    def token(self):
        return self._token

    # ── Internals ─────────────────────────────────────────────────────────────
    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._start_bot())

    async def _start_bot(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members          = True

        self.bot = commands.Bot(command_prefix="!", intents=intents)

        # ── Global command check: block all commands during lockdown ──────────
        @self.bot.check
        async def global_lockdown_check(ctx):
            if self.lockdown:
                self.log_cb(
                    f"[LOCKDOWN] Blocked command '{ctx.command}' "
                    f"from {ctx.author}", "WARNING")
                return False
            return True

        @self.bot.event
        async def on_ready():
            self.info = {
                "name":        str(self.bot.user),
                "id":          self.bot.user.id,
                "avatar_url":  str(self.bot.user.display_avatar.url),
                "guild_count": len(self.bot.guilds),
                "ping":        round(self.bot.latency * 1000),
            }
            self.log_cb(
                f"✓ Logged in as {self.bot.user}  (ID: {self.bot.user.id})",
                "SUCCESS")
            self.log_cb(f"  Serving {len(self.bot.guilds)} server(s)", "INFO")

        @self.bot.event
        async def on_message(msg):
            # ── Lockdown: silently delete any message the bot sends ───────────
            if self.lockdown and msg.author == self.bot.user:
                try:
                    await msg.delete()
                    self.log_cb(
                        f"[LOCKDOWN] Deleted bot message in #{msg.channel}",
                        "WARNING")
                except discord.Forbidden:
                    self.log_cb(
                        "[LOCKDOWN] No permission to delete message in "
                        f"#{msg.channel}", "ERROR")
                return   # Don't process commands either

            if not msg.author.bot:
                self.log_cb(
                    f"[#{msg.channel}] {msg.author}: {msg.content[:140]}",
                    "MSG")

            await self.bot.process_commands(msg)

        @self.bot.event
        async def on_interaction(interaction: discord.Interaction):
            # Block all slash command interactions during lockdown
            if self.lockdown and interaction.type == discord.InteractionType.application_command:
                self.log_cb(
                    f"[LOCKDOWN] Blocked slash command "
                    f"'/{interaction.data.get('name', '?')}' "
                    f"from {interaction.user}", "WARNING")
                try:
                    await interaction.response.send_message(
                        "🔒 The bot is currently in lockdown.", ephemeral=True)
                except Exception:
                    pass
                return

        @self.bot.event
        async def on_guild_join(g):
            self.log_cb(f"✓ Joined server: {g.name}", "SUCCESS")

        @self.bot.event
        async def on_guild_remove(g):
            self.log_cb(f"⚠  Left server: {g.name}", "WARNING")

        @self.bot.event
        async def on_command_error(ctx, error):
            if isinstance(error, commands.CheckFailure) and self.lockdown:
                return   # Already logged by the global check
            self.log_cb(f"Command error: {error}", "ERROR")

        try:
            await self.bot.start(self._token)
        except discord.LoginFailure:
            self.log_cb("✗ Invalid token — please re-enter your bot token.",
                        "ERROR")
            self.running = False
        except Exception as e:
            self.log_cb(f"✗ Bot error: {e}", "ERROR")
            self.running = False

    async def _shutdown(self):
        self.bot and await self.bot.close()


# ─── Lockdown double-confirm dialog ──────────────────────────────────────────
class LockdownDialog(tk.Toplevel):
    """
    Two-stage confirmation dialog for activating lockdown.
    .result is True if the user confirmed both stages, False otherwise.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.result = False
        self._stage = 1

        self.title("Lockdown Bot — Confirmation")
        self.geometry("480x290")
        self.resizable(False, False)
        self.configure(bg=BG_DARK)
        self.grab_set()
        self.focus_set()

        # Centre over parent
        self.update_idletasks()
        px = parent.winfo_x() + parent.winfo_width()  // 2 - 240
        py = parent.winfo_y() + parent.winfo_height() // 2 - 145
        self.geometry(f"+{px}+{py}")

        self._build()
        self.wait_window()

    def _build(self):
        # Clear any existing widgets
        for w in self.winfo_children():
            w.destroy()

        if self._stage == 1:
            icon_text  = "⚠"
            icon_color = WARNING
            title_text = "Activate Lockdown Mode?"
            body_text  = (
                "Lockdown Mode will immediately:\n\n"
                "  •  Delete every message the bot attempts to send\n"
                "  •  Block all prefix commands (! commands)\n"
                "  •  Block all slash commands with a lockdown notice\n\n"
                "The bot will stay online but will be completely silent\n"
                "and unresponsive until you turn Lockdown off."
            )
            confirm_label = "Yes, activate lockdown"
            confirm_color = WARNING
        else:
            icon_text  = "🔒"
            icon_color = LOCK_RED
            title_text = "Are you absolutely sure?"
            body_text  = (
                "This is your final warning.\n\n"
                "Once activated, your bot will stop responding\n"
                "to everything across ALL servers it is in.\n\n"
                "Click  \"Lock it down\"  to proceed."
            )
            confirm_label = "Lock it down"
            confirm_color = LOCK_RED

        tk.Label(self, text=icon_text, bg=BG_DARK, fg=icon_color,
                 font=("Segoe UI", 32)).pack(pady=(22, 4))

        tk.Label(self, text=title_text, bg=BG_DARK, fg=TXT_PRI,
                 font=("Segoe UI", 14, "bold")).pack()

        tk.Label(self, text=body_text, bg=BG_DARK, fg=TXT_SEC,
                 font=("Segoe UI", 9), justify="left").pack(
            padx=30, pady=(10, 18))

        btn_row = tk.Frame(self, bg=BG_DARK)
        btn_row.pack()

        tk.Button(btn_row, text="Cancel",
                  bg=BG_CARD, fg=TXT_SEC,
                  activebackground=BORDER, activeforeground=TXT_PRI,
                  font=("Segoe UI", 10), relief="flat",
                  cursor="hand2", padx=18, pady=7,
                  command=self.destroy).pack(side="left", padx=6)

        tk.Button(btn_row, text=confirm_label,
                  bg=confirm_color, fg="#ffffff",
                  activebackground="#ff4060",
                  activeforeground="#ffffff",
                  font=("Segoe UI", 10, "bold"), relief="flat",
                  cursor="hand2", padx=18, pady=7,
                  command=self._confirm).pack(side="left", padx=6)

    def _confirm(self):
        if self._stage == 1:
            self._stage = 2
            self._build()
        else:
            self.result = True
            self.destroy()


# ─── Main Application ─────────────────────────────────────────────────────────
class HexysApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1180x720")
        self.minsize(960, 600)
        self.configure(bg=BG_DARK)

        # Icons
        self._ico_path = None
        src = find_icon()
        if src:
            self._ico_path = src if src.suffix == ".ico" else to_ico(src)
        if self._ico_path:
            set_taskbar_icon(self, self._ico_path)

        icon_src = find_icon()
        self._moon_lg = circle_photo(icon_src, (110, 110)) if icon_src else None
        self._moon_sm = circle_photo(icon_src, (42,  42))  if icon_src else None

        # State
        self._bot_avatar_photo = None
        self.bot_wrapper       = None
        self.rpc_thread        = None

        # Feature toggle states  {feature_index: bool}
        self._feature_states: dict[int, bool] = {
            i: False for i in range(len(FEATURES))
        }
        self._feature_btns: dict[int, tk.Button]   = {}
        self._feature_lamps: dict[int, tk.Label]   = {}

        cfg = json.loads(CONFIG_FILE.read_text())
        self._saved_token = cfg.get("token", "")

        self._apply_styles()
        self._build_token_screen()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ═══ Styles ═══════════════════════════════════════════════════════════════
    def _apply_styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TSeparator", background=BORDER)
        s.configure("Vertical.TScrollbar",
                    background=BG_CARD, troughcolor=LOG_BG,
                    borderwidth=0, arrowsize=12)

    # ═══ Token screen ══════════════════════════════════════════════════════════
    def _build_token_screen(self):
        self._token_frame = tk.Frame(self, bg=BG_DARK)
        self._token_frame.place(relx=.5, rely=.5, anchor="center")

        if self._moon_lg:
            tk.Label(self._token_frame, image=self._moon_lg,
                     bg=BG_DARK).pack(pady=(0, 12))

        tk.Label(self._token_frame, text=APP_NAME,
                 bg=BG_DARK, fg=TXT_PRI,
                 font=("Segoe UI", 28, "bold")).pack()
        tk.Label(self._token_frame, text="Discord Bot Management Suite",
                 bg=BG_DARK, fg=TXT_SEC,
                 font=("Segoe UI", 11)).pack(pady=(2, 30))

        card = tk.Frame(self._token_frame, bg=BG_CARD,
                        highlightthickness=1, highlightbackground=BORDER)
        card.pack(ipadx=10)

        inner = tk.Frame(card, bg=BG_CARD, padx=36, pady=30)
        inner.pack()

        tk.Label(inner, text="BOT TOKEN", bg=BG_CARD, fg=TXT_SEC,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")

        ef = tk.Frame(inner, bg=BORDER, padx=1, pady=1)
        ef.pack(fill="x", pady=(4, 0))
        ef2 = tk.Frame(ef, bg=BG_DARK)
        ef2.pack(fill="x")

        self._token_var = tk.StringVar(value=self._saved_token)
        self._token_entry = tk.Entry(
            ef2, textvariable=self._token_var,
            show="•", width=44, bg=BG_DARK, fg=TXT_PRI,
            insertbackground=TXT_PRI, relief="flat",
            font=("Segoe UI", 12), bd=10)
        self._token_entry.pack(side="left", fill="x", expand=True)

        self._show_tok = False
        eye = tk.Label(ef2, text="👁", bg=BG_DARK, fg=TXT_SEC,
                       cursor="hand2", font=("Segoe UI", 13), padx=8)
        eye.pack(side="right")
        eye.bind("<Button-1>", lambda _: self._toggle_token())
        self._eye = eye

        # Security notice
        warn_box = tk.Frame(inner, bg="#1e1000",
                            highlightthickness=1, highlightbackground="#4a3000")
        warn_box.pack(fill="x", pady=(14, 20))
        wi = tk.Frame(warn_box, bg="#1e1000", padx=12, pady=10)
        wi.pack(fill="x")
        tk.Label(wi, text="⚠  Security Notice",
                 bg="#1e1000", fg=WARNING,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        tk.Label(wi,
                 text="Your bot token grants full control over your Discord bot.\n"
                      "Never share it publicly, commit it to version control,\n"
                      "or send it to anyone you do not completely trust.",
                 bg="#1e1000", fg="#c09040",
                 font=("Segoe UI", 8), justify="left").pack(anchor="w", pady=(3, 0))

        tk.Button(inner, text="Connect Bot  →",
                  bg=ACCENT, fg="#ffffff",
                  activebackground=ACCENT_LT, activeforeground="#ffffff",
                  font=("Segoe UI", 12, "bold"), relief="flat",
                  cursor="hand2", padx=28, pady=11,
                  command=self._connect_bot).pack()

        self._token_entry.bind("<Return>", lambda _: self._connect_bot())
        self._token_entry.focus_set()

    def _toggle_token(self):
        self._show_tok = not self._show_tok
        self._token_entry.config(show="" if self._show_tok else "•")
        self._eye.config(fg=ACCENT_LT if self._show_tok else TXT_SEC)

    def _connect_bot(self):
        token = self._token_var.get().strip()
        if not token:
            messagebox.showwarning(APP_NAME, "Please enter your bot token.")
            return

        cfg = json.loads(CONFIG_FILE.read_text())
        cfg["token"] = token
        cfg["last_launch"] = time.strftime("%Y-%m-%d %H:%M:%S")
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2))

        self._token_frame.place_forget()
        self._build_main_ui()

        self.rpc_thread = RPCThread()
        self.rpc_thread.start()

        self.bot_wrapper = BotWrapper(log_cb=self._append_log)
        self.bot_wrapper.start(token)
        self.after(3500, self._poll_bot_info)

    # ═══ Main UI ═══════════════════════════════════════════════════════════════
    def _build_main_ui(self):
        self._build_topbar()

        cols = tk.Frame(self, bg=BG_DARK)
        cols.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        cols.columnconfigure(0, weight=0, minsize=246)
        cols.columnconfigure(1, weight=1)
        cols.columnconfigure(2, weight=0, minsize=320)
        cols.rowconfigure(0, weight=1)

        self._build_left(cols).grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._build_centre(cols).grid(row=0, column=1, sticky="nsew", padx=4)
        self._build_right(cols).grid(row=0, column=2, sticky="nsew", padx=(8, 0))

    def _build_topbar(self):
        bar = tk.Frame(self, bg=BG_PANEL, height=56)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        if self._moon_sm:
            tk.Label(bar, image=self._moon_sm, bg=BG_PANEL).pack(
                side="left", padx=(14, 0), pady=7)

        tk.Label(bar, text=APP_NAME, bg=BG_PANEL, fg=TXT_PRI,
                 font=("Segoe UI", 14, "bold")).pack(side="left", padx=10)

        self._dot = tk.Label(bar, text="●", bg=BG_PANEL,
                              fg=TXT_MUT, font=("Segoe UI", 12))
        self._dot.pack(side="left", padx=(6, 2))
        self._status_lbl = tk.Label(bar, text="Connecting…",
                                     bg=BG_PANEL, fg=TXT_MUT,
                                     font=("Segoe UI", 9))
        self._status_lbl.pack(side="left")

        tk.Button(bar, text="⏻  Disconnect",
                  bg="#200010", fg=ERR,
                  activebackground="#300020", activeforeground=ERR,
                  font=("Segoe UI", 9, "bold"), relief="flat",
                  cursor="hand2", padx=10, pady=4,
                  command=self._disconnect).pack(side="right", padx=14, pady=12)

    # ── Left panel ────────────────────────────────────────────────────────────
    def _build_left(self, parent):
        p = tk.Frame(parent, bg=BG_PANEL,
                     highlightthickness=1, highlightbackground=BORDER)

        tk.Label(p, text="Bot Information", bg=BG_PANEL, fg=ACCENT_LT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=14, pady=(14, 6))
        tk.Frame(p, bg=BORDER, height=1).pack(fill="x", padx=14)

        self._av_lbl = tk.Label(p, bg=BG_PANEL)
        self._av_lbl.pack(pady=(18, 4))

        self._bname = tk.Label(p, text="—", bg=BG_PANEL, fg=TXT_PRI,
                                font=("Segoe UI", 14, "bold"), wraplength=220)
        self._bname.pack()
        self._btag = tk.Label(p, text="", bg=BG_PANEL, fg=TXT_SEC,
                               font=("Segoe UI", 9))
        self._btag.pack(pady=(0, 14))

        tk.Frame(p, bg=BORDER, height=1).pack(fill="x", padx=14)

        info_f = tk.Frame(p, bg=BG_PANEL)
        info_f.pack(fill="x", padx=14, pady=12)
        self._info = {}
        for label, emoji in (("User ID", "🆔"), ("Servers", "🌐"), ("Ping", "📡")):
            row = tk.Frame(info_f, bg=BG_PANEL)
            row.pack(fill="x", pady=5)
            tk.Label(row, text=f"{emoji}  {label}", bg=BG_PANEL, fg=TXT_MUT,
                     font=("Segoe UI", 9), width=14, anchor="w").pack(side="left")
            val = tk.Label(row, text="—", bg=BG_PANEL, fg=TXT_PRI,
                           font=("Segoe UI", 9, "bold"), anchor="w")
            val.pack(side="left", fill="x", expand=True)
            self._info[label] = val

        return p

    # ── Centre panel (features) ───────────────────────────────────────────────
    def _build_centre(self, parent):
        outer = tk.Frame(parent, bg=BG_PANEL,
                         highlightthickness=1, highlightbackground=BORDER)

        tk.Label(outer, text="Features", bg=BG_PANEL, fg=ACCENT_LT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=14, pady=(14, 6))
        tk.Frame(outer, bg=BORDER, height=1).pack(fill="x", padx=14)

        # Scrollable feature cards
        canvas = tk.Canvas(outer, bg=BG_PANEL, bd=0, highlightthickness=0)
        sb     = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True, padx=8, pady=8)

        scroll_f = tk.Frame(canvas, bg=BG_PANEL)
        win_id   = canvas.create_window((0, 0), window=scroll_f, anchor="nw")

        def _on_resize(e):
            canvas.itemconfig(win_id, width=e.width)
        canvas.bind("<Configure>", _on_resize)

        def _on_frame_configure(_):
            canvas.configure(scrollregion=canvas.bbox("all"))
        scroll_f.bind("<Configure>", _on_frame_configure)

        # Mouse-wheel scrolling
        def _on_wheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_wheel)

        if not FEATURES:
            tk.Label(scroll_f, text="No features configured.\nEdit the FEATURES list in the source.",
                     bg=BG_PANEL, fg=TXT_SEC, font=("Segoe UI", 10),
                     justify="center").pack(pady=40)
        else:
            for i, feat in enumerate(FEATURES):
                self._build_feature_card(scroll_f, i, feat)

        return outer

    def _build_feature_card(self, parent, idx: int, feat: dict):
        """Build one feature card with toggle button and status lamp."""
        is_lockdown = feat.get("builtin_key") == "lockdown"

        card = tk.Frame(parent, bg=BG_CARD,
                        highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="x", padx=6, pady=6, ipady=4)

        top_row = tk.Frame(card, bg=BG_CARD)
        top_row.pack(fill="x", padx=12, pady=(10, 4))

        # Status lamp (● indicator)
        lamp = tk.Label(top_row, text="●", bg=BG_CARD, fg=TXT_MUT,
                        font=("Segoe UI", 11))
        lamp.pack(side="left", padx=(0, 6))
        self._feature_lamps[idx] = lamp

        # Feature name
        name_lbl = tk.Label(top_row, text=feat["name"], bg=BG_CARD, fg=TXT_PRI,
                             font=("Segoe UI", 11, "bold"))
        name_lbl.pack(side="left")

        # Script badge
        if not feat.get("builtin") and feat.get("script"):
            tk.Label(top_row, text=f"  📄 {feat['script']}",
                     bg=BG_CARD, fg=TXT_MUT,
                     font=("Segoe UI", 8)).pack(side="left", padx=6)
        elif feat.get("builtin"):
            tk.Label(top_row, text="  ⚡ built-in",
                     bg=BG_CARD, fg=TXT_MUT,
                     font=("Segoe UI", 8)).pack(side="left", padx=6)

        # Description
        if feat.get("description"):
            tk.Label(card, text=feat["description"], bg=BG_CARD, fg=TXT_SEC,
                     font=("Segoe UI", 8), justify="left",
                     wraplength=340).pack(anchor="w", padx=12, pady=(0, 8))

        # Toggle button
        btn_colour = LOCK_RED if is_lockdown else ACCENT
        btn = tk.Button(card,
                        text=f"Enable  {feat['name']}",
                        bg=btn_colour, fg="#ffffff",
                        activebackground=ACCENT_LT, activeforeground="#ffffff",
                        font=("Segoe UI", 9, "bold"), relief="flat",
                        cursor="hand2", padx=14, pady=6,
                        command=lambda i=idx: self._toggle_feature(i))
        btn.pack(anchor="w", padx=12, pady=(0, 10))
        self._feature_btns[idx] = btn

    def _toggle_feature(self, idx: int):
        feat       = FEATURES[idx]
        currently  = self._feature_states[idx]
        turning_on = not currently

        # ── Lockdown: special double-confirm dialog ───────────────────────────
        if feat.get("builtin_key") == "lockdown" and turning_on:
            dlg = LockdownDialog(self)
            if not dlg.result:
                return   # User cancelled

        # ── External script feature ───────────────────────────────────────────
        if not feat.get("builtin") and feat.get("script"):
            if not self.bot_wrapper:
                messagebox.showwarning(APP_NAME, "Bot is not connected yet.")
                return
            ok, msg = launch_feature_script(
                feat["script"],
                self.bot_wrapper.token,
                "on" if turning_on else "off",
            )
            if not ok:
                messagebox.showerror(APP_NAME,
                                     f"Could not launch script:\n{msg}")
                return
            self._append_log(
                f"{'▶ Started' if turning_on else '■ Stopped'} "
                f"plugin: {feat['name']}  ({feat['script']})",
                "SUCCESS" if turning_on else "INFO"
            )

        # ── Built-in: lockdown ────────────────────────────────────────────────
        if feat.get("builtin_key") == "lockdown":
            if self.bot_wrapper:
                self.bot_wrapper.set_lockdown(turning_on)
            else:
                messagebox.showwarning(APP_NAME, "Bot is not connected yet.")
                return

        # ── Update UI state ───────────────────────────────────────────────────
        self._feature_states[idx] = turning_on
        self._refresh_feature_card(idx)

    def _refresh_feature_card(self, idx: int):
        feat    = FEATURES[idx]
        active  = self._feature_states[idx]
        btn     = self._feature_btns[idx]
        lamp    = self._feature_lamps[idx]
        is_lock = feat.get("builtin_key") == "lockdown"

        if active:
            lamp.config(fg=LOCK_RED if is_lock else SUCCESS)
            btn.config(
                text=f"Disable  {feat['name']}",
                bg="#1a1a1a" if is_lock else "#1a2a1a",
                fg=LOCK_RED if is_lock else SUCCESS,
                activebackground=BG_CARD,
            )
        else:
            lamp.config(fg=TXT_MUT)
            btn.config(
                text=f"Enable  {feat['name']}",
                bg=LOCK_RED if is_lock else ACCENT,
                fg="#ffffff",
                activebackground=ACCENT_LT,
            )

    # ── Right panel (log) ─────────────────────────────────────────────────────
    def _build_right(self, parent):
        p = tk.Frame(parent, bg=BG_PANEL,
                     highlightthickness=1, highlightbackground=BORDER)

        hdr = tk.Frame(p, bg=BG_PANEL)
        hdr.pack(fill="x", padx=14, pady=(14, 6))
        tk.Label(hdr, text="Live Activity Log", bg=BG_PANEL, fg=ACCENT_LT,
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        clr = tk.Label(hdr, text="Clear", bg=BG_PANEL, fg=TXT_MUT,
                       font=("Segoe UI", 8), cursor="hand2")
        clr.pack(side="right")
        clr.bind("<Button-1>", lambda _: self._clear_log())

        tk.Frame(p, bg=BORDER, height=1).pack(fill="x", padx=14)

        log_f = tk.Frame(p, bg=LOG_BG)
        log_f.pack(fill="both", expand=True, padx=8, pady=8)

        self._log = tk.Text(
            log_f, bg=LOG_BG, fg=TXT_PRI,
            font=("Cascadia Mono", 8),
            relief="flat", bd=0, state="disabled",
            wrap="word", cursor="arrow",
            selectbackground=ACCENT, selectforeground="#fff",
        )
        sb = ttk.Scrollbar(log_f, orient="vertical", command=self._log.yview)
        self._log.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._log.pack(fill="both", expand=True, padx=(6, 0), pady=4)

        self._log.tag_configure("TIME",    foreground=TXT_MUT)
        self._log.tag_configure("INFO",    foreground=TXT_SEC)
        self._log.tag_configure("SUCCESS", foreground=SUCCESS)
        self._log.tag_configure("WARNING", foreground=WARNING)
        self._log.tag_configure("ERROR",   foreground=ERR)
        self._log.tag_configure("MSG",     foreground=TXT_PRI)

        return p

    # ═══ Runtime helpers ═══════════════════════════════════════════════════════
    def _append_log(self, msg: str, level: str = "INFO"):
        self.after(0, self._write_log, msg, level)

    def _write_log(self, msg: str, level: str):
        t = time.strftime("%H:%M:%S")
        self._log.config(state="normal")
        self._log.insert("end", f"[{t}] ", "TIME")
        self._log.insert("end", f"{msg}\n", level)
        lines = int(self._log.index("end-1c").split(".")[0])
        if lines > LOG_MAX:
            self._log.delete("1.0", f"{lines - LOG_MAX}.0")
        self._log.config(state="disabled")
        self._log.see("end")

    def _clear_log(self):
        self._log.config(state="normal")
        self._log.delete("1.0", "end")
        self._log.config(state="disabled")

    def _poll_bot_info(self):
        if not self.bot_wrapper:
            return
        info = self.bot_wrapper.info
        if info:
            self._dot.config(fg=SUCCESS)
            self._status_lbl.config(text="Connected", fg=SUCCESS)
            parts = str(info.get("name", "Bot")).split("#")
            self._bname.config(text=parts[0])
            self._btag.config(text=f"#{parts[1]}" if len(parts) > 1 else "")
            self._info["User ID"].config(text=str(info.get("id", "—")))
            self._info["Servers"].config(text=str(info.get("guild_count", "—")))
            ping  = info.get("ping", "—")
            pclr  = SUCCESS if isinstance(ping, int) and ping < 100 else \
                    WARNING if isinstance(ping, int) and ping < 250 else ERR
            self._info["Ping"].config(
                text=f"{ping} ms" if isinstance(ping, int) else "—", fg=pclr)
            if not self._bot_avatar_photo and info.get("avatar_url"):
                self.after(0, self._load_avatar, info["avatar_url"])
        else:
            self._dot.config(fg=WARNING)
            self._status_lbl.config(text="Connecting…", fg=WARNING)
        self.after(5000, self._poll_bot_info)

    def _load_avatar(self, url: str):
        try:
            data = requests.get(url, timeout=6).content
            img  = Image.open(BytesIO(data)).convert("RGBA").resize((88, 88))
            mask = Image.new("L", (88, 88), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, 87, 87), fill=255)
            img.putalpha(mask)
            self._bot_avatar_photo = ImageTk.PhotoImage(img)
            self._av_lbl.config(image=self._bot_avatar_photo)
        except Exception:
            pass

    # ═══ Disconnect / close ════════════════════════════════════════════════════
    def _disconnect(self):
        if messagebox.askyesno(APP_NAME,
                               "Disconnect the bot and return to the token screen?"):
            self._teardown()
            for w in self.winfo_children():
                w.destroy()
            self._feature_btns.clear()
            self._feature_lamps.clear()
            self._feature_states = {i: False for i in range(len(FEATURES))}
            self._build_token_screen()

    def _teardown(self):
        if self.bot_wrapper:
            self.bot_wrapper.stop()
            self.bot_wrapper = None
        if self.rpc_thread:
            self.rpc_thread.stop()
            self.rpc_thread.join(timeout=3)
            self.rpc_thread = None
        self._bot_avatar_photo = None

    def _on_close(self):
        self._teardown()
        self.destroy()


# ─── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = HexysApp()
    app.mainloop()
