"""Tkinter control panel for Zaber linear and rotary motion stages.

Each axis gets Home, Jog, Go-to, and a live position readout, plus a shared
STOP ALL button. This build runs against a software simulator, so it works with
no hardware attached.

Run:
    python stage_console.py
"""

import sys
import tkinter as tk
from tkinter import font as tkfont, messagebox, ttk

from simulator import StageController   # simulated hardware layer

POLL_MS = 120        # position-readout refresh interval, ms
DEFAULT_PORT = "SIM1"
UI_SCALE = 1.25      # font/widget scale factor (1.0 = default)

WINDOW_BG = "#0d0f13"    # near-black page
CARD_BG = "#161a20"      # elevated dark card
CARD_BORDER = "#2a2f38"
ENTRY_BG = "#0f1216"

TEXT = "#e8eaed"         # primary text (near-white)
TEXT_MUTED = "#9aa1ab"   # secondary/gray text
TITLE_TEXT = "#7f8792"   # subtle stage-name (card title)
MAXSPEED = "#c0392b"     # max-speed value (dark red)

# Status pill backgrounds (per axis state).
PILL_IDLE = "#2ecc71"
PILL_MOVING = "#f0a12e"
PILL_ERROR = "#e74c3c"
PILL_OFFLINE = "#333842"

# Button bevel: subtle at rest, lighter on hover/press (a lift, not a sink).
BEVEL = "#2a2f38"
BEVEL_LIGHT = "#7d8794"

ACCENT = "#3b82f6"          # blue
ACCENT_HOVER = "#5b9bff"
ACCENT_PRESSED = "#7db0ff"

STOP_AXIS = "#d83a45"       # per-axis stop (red)
STOP_AXIS_HOVER = "#ef5561"
STOP_AXIS_PRESSED = "#ff6f7a"

STOP_ALL = "#e63946"        # bright red
STOP_ALL_HOVER = "#ff5a66"
STOP_ALL_PRESSED = "#ff8088"
STOP_ALL_DISABLED = "#4a2327"  # dark muted red while disconnected

END = "#8f2d37"                # End Program (dark red)
END_HOVER = "#a5343f"
END_PRESSED = "#b5424e"

BTN_TEXT = "#ffffff"
BTN_DISABLED_BG = "#23262d"
BTN_DISABLED_TEXT = "#5f666f"

CONNECTED_COLOR = "#2ecc71"     # status dot
DISCONNECTED_COLOR = "#e74c3c"


def setup_style(root, scale=UI_SCALE):
    """Set the theme, scale fonts/padding, and define the card look.

    Call once before building the UI.
    """
    style = ttk.Style(root)
    # 'clam' honours custom backgrounds/borders; fall back if unavailable.
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    for name in ("TkDefaultFont", "TkTextFont"):
        f = tkfont.nametofont(name)
        base = abs(f.cget("size")) or 9        # abs handles pixel sizes; 9 if unset
        f.configure(size=int(round(base * scale)))

    family = tkfont.nametofont("TkDefaultFont").cget("family")

    style.configure(".", background=WINDOW_BG, foreground=TEXT)
    style.configure("TFrame", background=WINDOW_BG)
    style.configure("TLabel", background=WINDOW_BG, foreground=TEXT)

    # Buttons: raised bevel that lifts (lightens) on hover/press.
    def button_style(name, base, hover, pressed):
        style.configure(name, padding=(8, 6), relief="raised", borderwidth=2,
                        background=base, foreground=BTN_TEXT,
                        bordercolor=BEVEL, lightcolor=BEVEL, darkcolor=BEVEL,
                        focuscolor=base,
                        font=(family, int(round(10 * scale)), "bold"))
        style.map(
            name,
            background=[("disabled", BTN_DISABLED_BG),
                        ("pressed", pressed), ("active", hover)],
            foreground=[("disabled", BTN_DISABLED_TEXT)],
            bordercolor=[("active", BEVEL_LIGHT), ("pressed", BEVEL_LIGHT)],
            lightcolor=[("active", BEVEL_LIGHT), ("pressed", BEVEL_LIGHT)],
            darkcolor=[("active", BEVEL_LIGHT), ("pressed", BEVEL_LIGHT)])

    button_style("TButton", ACCENT, ACCENT_HOVER, ACCENT_PRESSED)
    button_style("Stop.TButton", STOP_AXIS, STOP_AXIS_HOVER, STOP_AXIS_PRESSED)
    button_style("End.TButton", END, END_HOVER, END_PRESSED)

    # Entries: dark field, white text, accent-blue border on focus.
    style.configure("TEntry", padding=4, relief="solid", borderwidth=1,
                    fieldbackground=ENTRY_BG, foreground=TEXT,
                    insertcolor=TEXT, bordercolor=CARD_BORDER)
    style.map("TEntry", bordercolor=[("focus", ACCENT)],
              lightcolor=[("focus", ACCENT)], darkcolor=[("focus", ACCENT)])

    # Card = one axis panel.
    style.configure("Card.TLabelframe", background=CARD_BG,
                    borderwidth=1, relief="solid", bordercolor=CARD_BORDER)
    style.configure("Card.TLabelframe.Label", background=CARD_BG,
                    foreground=TITLE_TEXT,
                    font=(family, int(round(10 * scale)), "bold"))
    style.configure("Card.TLabel", background=CARD_BG, foreground=TEXT)
    style.configure("MaxSpeed.TLabel", background=CARD_BG, foreground=MAXSPEED,
                    font=(family, int(round(10 * scale)), "bold"))

    # Caption above the hero value; hero = the large live position readout.
    style.configure("Caption.TLabel", background=CARD_BG, foreground=TEXT_MUTED,
                    font=(family, int(round(8 * scale))))
    style.configure("Hero.TLabel", background=CARD_BG, foreground=ACCENT,
                    font=("Consolas", int(round(20 * scale)), "bold"))

    # Status pill: a small filled badge; one style per state.
    pill_font = (family, int(round(8 * scale)), "bold")
    for pname, bg, fg in (("PillIdle", PILL_IDLE, WINDOW_BG),
                          ("PillMoving", PILL_MOVING, WINDOW_BG),
                          ("PillError", PILL_ERROR, "#ffffff"),
                          ("PillOffline", PILL_OFFLINE, TEXT_MUTED)):
        style.configure(pname + ".TLabel", background=bg, foreground=fg,
                        font=pill_font, padding=(8, 2), anchor="center")

    # Hairline separators inside the cards.
    style.configure("Card.TSeparator", background=CARD_BORDER)

    root.configure(bg=WINDOW_BG)


class AxisPanel(ttk.LabelFrame):
    """The controls for one axis."""

    def __init__(self, parent, handle, app):
        super().__init__(parent, text=handle.label, padding=10,
                         style="Card.TLabelframe")
        self.handle = handle             # the axis this panel controls
        self.app = app                   # back-reference to the main App
        u = handle.unit_label            # "mm" (linear) or "deg" (rotary)
        v = handle.vel_label             # "mm/s" (linear) or "deg/s" (rotary)
        PAD = (6, 0)                     # uniform vertical rhythm between rows
        self.columnconfigure(1, weight=1)   # entry column takes slack

        # ===== Readout zone: caption, hero position value, status pill =====
        ttk.Label(self, text="POSITION", style="Caption.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w")
        self.status_pill = ttk.Label(self, style="PillOffline.TLabel", text="OFFLINE")
        self.status_pill.grid(row=0, column=2, columnspan=2, sticky="e")

        self.pos_var = tk.StringVar(value=f"--  {u}")
        ttk.Label(self, textvariable=self.pos_var, style="Hero.TLabel").grid(
            row=1, column=0, columnspan=4, sticky="w")

        self._separator(row=2)

        # ===== Controls zone: Home, Jog, Go to, Speed =====
        ttk.Button(self, text="Home", command=self._home).grid(
            row=3, column=0, columnspan=4, sticky="ew", pady=PAD)

        ttk.Label(self, text=f"Jog ({u}):", style="Card.TLabel").grid(
            row=4, column=0, sticky="e", pady=PAD, padx=(0, 6))
        self.jog_var = tk.StringVar(value="5.0")
        ttk.Entry(self, textvariable=self.jog_var, width=7).grid(
            row=4, column=1, sticky="ew", pady=PAD)
        ttk.Button(self, text="Jog -", command=lambda: self._jog(-1)).grid(
            row=4, column=2, sticky="ew", pady=PAD, padx=(6, 0))
        ttk.Button(self, text="Jog +", command=lambda: self._jog(+1)).grid(
            row=4, column=3, sticky="ew", pady=PAD, padx=(6, 0))

        ttk.Label(self, text=f"Go to ({u}):", style="Card.TLabel").grid(
            row=5, column=0, sticky="e", pady=PAD, padx=(0, 6))
        self.abs_var = tk.StringVar(value="0.0")
        ttk.Entry(self, textvariable=self.abs_var, width=7).grid(
            row=5, column=1, sticky="ew", pady=PAD)
        ttk.Button(self, text="Move", command=self._move_abs).grid(
            row=5, column=2, columnspan=2, sticky="ew", pady=PAD, padx=(6, 0))

        ttk.Label(self, text=f"Speed ({v}):", style="Card.TLabel").grid(
            row=6, column=0, sticky="e", pady=PAD, padx=(0, 6))
        self.vel_var = tk.StringVar(value="")
        ttk.Entry(self, textvariable=self.vel_var, width=7).grid(
            row=6, column=1, sticky="ew", pady=PAD)
        ttk.Label(self, style="Card.TLabel", foreground=TEXT_MUTED,
                  text="blank = default").grid(
            row=6, column=2, columnspan=2, sticky="w", pady=PAD, padx=(6, 0))

        self._separator(row=7)

        # ===== Device-info zone: max speed, travel range =====
        ttk.Label(self, text="Max speed:", style="MaxSpeed.TLabel").grid(
            row=8, column=0, sticky="e", pady=PAD, padx=(0, 6))
        max_text = f"{handle.max_velocity:.1f} {v}" if handle.max_velocity is not None else ""
        ttk.Label(self, style="MaxSpeed.TLabel", text=max_text).grid(
            row=8, column=1, columnspan=3, sticky="w", pady=PAD)

        if handle.travel_min is not None:
            ttk.Label(self, text="Range:", style="Card.TLabel",
                      foreground=TEXT_MUTED).grid(
                row=9, column=0, sticky="e", pady=PAD, padx=(0, 6))
            ttk.Label(self, style="Card.TLabel", foreground=TEXT_MUTED,
                      text=f"{handle.travel_min:.1f} to {handle.travel_max:.1f} {u}").grid(
                row=9, column=1, columnspan=3, sticky="w", pady=PAD)

        # ===== Per-axis stop =====
        ttk.Button(self, text="Stop this axis", command=self._stop,
                   style="Stop.TButton").grid(
            row=10, column=0, columnspan=4, sticky="ew", pady=(12, 0))

    def _separator(self, row):
        ttk.Separator(self, orient="horizontal", style="Card.TSeparator").grid(
            row=row, column=0, columnspan=4, sticky="ew", pady=(10, 4))

    # -- button handlers; errors surface as dialogs via App.guard --
    def _home(self):
        self.app.guard(self.handle.home)

    def _jog(self, direction):
        amount = self._read_float(self.jog_var, "jog amount")
        speed = self._read_speed()
        if amount is not None and speed is not None:
            self.app.guard(lambda: self.handle.jog(direction * abs(amount), speed))

    def _move_abs(self):
        target = self._read_float(self.abs_var, "target position")
        speed = self._read_speed()
        if target is not None and speed is not None:
            self.app.guard(lambda: self.handle.move_absolute(target, speed))

    def _stop(self):
        self.app.guard(self.handle.stop)

    def set_enabled(self, enabled):
        """Enable/disable the buttons and entries (labels untouched)."""
        flag = "!disabled" if enabled else "disabled"
        for child in self.winfo_children():
            if isinstance(child, (ttk.Button, ttk.Entry)):
                child.state([flag])

    _PILL = {"offline": ("PillOffline.TLabel", "OFFLINE"),
             "idle": ("PillIdle.TLabel", "IDLE"),
             "moving": ("PillMoving.TLabel", "MOVING"),
             "error": ("PillError.TLabel", "ERROR")}

    def _set_pill(self, state):
        style, text = self._PILL[state]
        self.status_pill.configure(style=style, text=text)

    def _read_float(self, var, what):
        try:
            return float(var.get())
        except ValueError:
            messagebox.showerror("Invalid value", f"Please enter a number for the {what}.")
            return None

    def _read_speed(self):
        """Return the speed field as a float, 0 for blank (default).

        Returns None if the entry is non-numeric or negative (dialog shown).
        """
        text = self.vel_var.get().strip()
        if not text:
            return 0
        try:
            speed = float(text)
        except ValueError:
            messagebox.showerror("Invalid value", "Please enter a number for the speed.")
            return None
        if speed < 0:
            messagebox.showerror("Invalid value", "Speed must be positive.")
            return None
        return speed

    def refresh(self):
        """Update the position readout and status pill; called by the poll timer."""
        u = self.handle.unit_label
        if not self.app.controller.is_connected:
            self.pos_var.set(f"--  {u}")
            self._set_pill("offline")
            return
        try:
            pos = self.handle.position()
            busy = self.handle.is_busy()
        except Exception:
            self.pos_var.set(f"--  {u}")
            self._set_pill("error")
            return
        self.pos_var.set(f"{pos:.3f} {u}")
        self._set_pill("moving" if busy else "idle")


class _PlaceholderAxis:
    """Stand-in used to render the cards while nothing is connected.

    It exposes the same attributes and methods AxisPanel reads/calls so the full
    layout is always visible. The cards are shown disabled while disconnected, so
    the move commands are never actually reached.
    """
    def __init__(self, label, is_rotary=False):
        self.label = label
        self.is_rotary = is_rotary
        self.unit_label = "deg" if is_rotary else "mm"
        self.vel_label = "deg/s" if is_rotary else "mm/s"
        self.max_velocity = None
        self.travel_min = None
        self.travel_max = None

    def position(self):
        return 0.0

    def is_busy(self):
        return False

    def home(self):
        pass

    def jog(self, distance, velocity=0):
        pass

    def move_absolute(self, position, velocity=0):
        pass

    def stop(self):
        pass


class App(ttk.Frame):
    def __init__(self, root, port):
        super().__init__(root, padding=8)
        self.grid(sticky="nsew")
        root.title("Zaber Stage Control Panel")
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        # Let the axis-panel row stretch so the cards fill the window's width.
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self.controller = StageController(port)
        self.panels = []

        # --- Top bar: port + connect ---
        bar = ttk.Frame(self)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(bar, text="Port:").pack(side="left")
        self.port_var = tk.StringVar(value=port)
        ttk.Entry(bar, textvariable=self.port_var, width=10).pack(side="left", padx=(4, 8))
        self.connect_btn = ttk.Button(bar, text="Connect", command=self.toggle_connection)
        self.connect_btn.pack(side="left")
        # Connection indicator: a colored dot + text (green/connected, red/not).
        self.status_dot = ttk.Label(bar, text="●")
        self.status_dot.pack(side="left", padx=(12, 3))
        self.conn_status = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.conn_status).pack(side="left")

        # --- Where the axis panels go ---
        self.axis_container = ttk.Frame(self)
        self.axis_container.grid(row=1, column=0, sticky="nsew")

        # --- STOP ALL ---
        self.stop_btn = tk.Button(
            self, text="STOP ALL", command=self.stop_all,
            bg=STOP_ALL_DISABLED, fg="white",
            activebackground=STOP_ALL_PRESSED, activeforeground="white",
            disabledforeground=TEXT_MUTED, highlightthickness=0,
            relief="raised", bd=3, cursor="hand2",
            font=("Segoe UI", 16, "bold"), height=2, state="disabled")
        self.stop_btn.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        self.stop_btn.bind("<Enter>", self._stop_btn_hover)
        self.stop_btn.bind("<Leave>", self._stop_btn_leave)

        # --- End program (stop, disconnect, close) ---
        ttk.Button(self, text="End Program", command=self.end_program,
                   style="End.TButton").grid(
            row=3, column=0, sticky="ew", pady=(6, 0))

        # Esc = STOP ALL.
        root.bind("<Escape>", lambda _e: self.stop_all())

        self._poll_job = None

        # Show the full GUI in its disconnected state at startup.
        self._show_disconnected()

    # ---------- connection ----------
    def toggle_connection(self):
        if self.controller.is_connected:
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        self.controller.port = self.port_var.get().strip()
        try:
            axes = self.controller.connect()
        except Exception as exc:
            messagebox.showerror("Connection failed", str(exc))
            return
        if not axes:
            messagebox.showwarning("No axes", "Connected, but no devices/axes were detected.")
            self.controller.disconnect()
            return

        self._clear_panels()             # drop the disconnected placeholder cards
        self._populate_axes(axes, enabled=True)
        self.conn_status.set(f"Connected - {len(axes)} axis/axes on {self.controller.port}")
        self.status_dot.configure(foreground=CONNECTED_COLOR)
        self.connect_btn.config(text="Disconnect")
        self.stop_btn.config(state="normal", bg=STOP_ALL)
        self._schedule_poll()

    def disconnect(self):
        if self._poll_job is not None:
            self.after_cancel(self._poll_job)
            self._poll_job = None
        self.controller.disconnect()
        self._show_disconnected()
        self.connect_btn.config(text="Connect")
        self.stop_btn.config(state="disabled", bg=STOP_ALL_DISABLED)

    def _stop_btn_hover(self, _e):
        if str(self.stop_btn["state"]) == "normal":
            self.stop_btn.configure(bg=STOP_ALL_HOVER)

    def _stop_btn_leave(self, _e):
        if str(self.stop_btn["state"]) == "normal":
            self.stop_btn.configure(bg=STOP_ALL)

    # ---------- axis panels ----------
    def _clear_panels(self):
        """Destroy all current axis panels (real or placeholder)."""
        for panel in self.panels:
            panel.destroy()
        self.panels = []

    def _populate_axes(self, handles, enabled=True):
        """Build one card per handle, side by side. enabled=False greys them."""
        for col, handle in enumerate(handles):
            panel = AxisPanel(self.axis_container, handle, self)
            panel.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 8, 0))
            self.axis_container.columnconfigure(col, weight=1, uniform="axis")
            panel.refresh()              # show initial position/status right away
            panel.set_enabled(enabled)
            self.panels.append(panel)

    def _show_disconnected(self):
        """Show disabled placeholder cards and the red 'Not connected' dot."""
        self._clear_panels()
        placeholders = [
            _PlaceholderAxis("Linear stage 1"),
            _PlaceholderAxis("Linear stage 2"),
            _PlaceholderAxis("Rotary stage", is_rotary=True),
        ]
        self._populate_axes(placeholders, enabled=False)
        self.conn_status.set("Not connected - enter a port and click Connect")
        self.status_dot.configure(foreground=DISCONNECTED_COLOR)

    # ---------- actions ----------
    def stop_all(self):
        if not self.controller.is_connected:
            return
        errors = self.controller.stop_all()
        if errors:
            detail = "\n".join(f"{label}: {exc}" for label, exc in errors)
            messagebox.showerror("Stop All - some axes did not stop", detail)

    def end_program(self):
        """Stop every axis, disconnect, then close the window."""
        if self.controller.is_connected:
            self.controller.stop_all()   # halt motion before releasing the port
        self.disconnect()                # cancel polling and close the connection
        self.master.destroy()            # close the window and end mainloop

    def guard(self, action):
        """Run an action, showing a dialog on error."""
        try:
            action()
        except Exception as exc:
            messagebox.showerror("Command failed", str(exc))

    # ---------- polling ----------
    def _schedule_poll(self):
        for panel in self.panels:
            panel.refresh()
        self._poll_job = self.after(POLL_MS, self._schedule_poll)


def _build(port=DEFAULT_PORT):
    root = tk.Tk()
    setup_style(root)       # theme, fonts, and card look before building the UI
    app = App(root, port)
    root.protocol("WM_DELETE_WINDOW", app.end_program)
    return root, app


def main():
    if "--selftest" in sys.argv:
        root, app = _build(DEFAULT_PORT)
        app.connect()
        app.panels[0].handle.move_absolute(120, 0)
        app.panels[2].handle.jog(90, 0)
        for _ in range(30):
            for p in app.panels:
                p.refresh()
            root.update()
        print("selftest OK: axes=%d pos0=%.1f" % (
            len(app.panels), app.panels[0].handle.position()))
        app.end_program()
        return 0

    if "--screenshot" in sys.argv:
        import time
        from PIL import ImageGrab
        path = sys.argv[sys.argv.index("--screenshot") + 1]
        root, app = _build(DEFAULT_PORT)
        root.geometry("+80+80")
        root.update()
        app.connect()
        app.panels[0].handle.move_absolute(96.4, 0)
        app.panels[1].handle.move_absolute(30.0, 0)
        app.panels[2].handle.move_absolute(215.0, 0)
        # Bring the window to the very front so the grab only sees it.
        root.attributes("-topmost", True)
        root.lift()
        root.focus_force()
        for _ in range(12):
            for p in app.panels:
                p.refresh()
            root.update()
            time.sleep(0.03)
        root.update_idletasks()
        x, y = root.winfo_rootx(), root.winfo_rooty()
        w, h = root.winfo_width(), root.winfo_height()
        ImageGrab.grab(bbox=(x, y, x + w, y + h)).save(path)
        print(f"saved screenshot to {path}")
        app.end_program()
        return 0

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    port = args[0] if args else DEFAULT_PORT
    root, app = _build(port)
    root.mainloop()


if __name__ == "__main__":
    main()
