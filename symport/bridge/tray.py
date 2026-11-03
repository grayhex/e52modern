"""Small native Windows tray/settings UI. Phone management remains in SymPort Web."""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

from . import VERSION
from .settings import load_config, save_config

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def autostart(enabled=None):
    if os.name != "nt":
        return False
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled is None:
            try:
                value, _ = winreg.QueryValueEx(key, "SymPortBridge")
                return bool(value)
            except FileNotFoundError:
                return False
        if enabled:
            if not getattr(sys, "frozen", False):
                raise ValueError("Autostart is available in the portable exe")
            winreg.SetValueEx(key, "SymPortBridge", 0, winreg.REG_SZ, '"' + sys.executable + '"')
        else:
            try:
                winreg.DeleteValue(key, "SymPortBridge")
            except FileNotFoundError:
                pass
    return bool(enabled)


def run_tray(agent, key):
    from tkinter import BooleanVar, StringVar, Tk, filedialog, messagebox, ttk

    import pystray
    from PIL import Image

    settings_open = threading.Lock()

    def settings():
        if not settings_open.acquire(blocking=False):
            return

        def window():
            root = Tk()
            root.title("SymPort Bridge · " + VERSION)
            root.resizable(False, False)
            config = load_config(agent.root)
            frame = ttk.Frame(root, padding=18)
            frame.grid()
            ttk.Label(frame, text="Nokia Symbian S60 · Local Bridge").grid(
                row=0, column=0, columnspan=3, sticky="w", pady=(0, 12)
            )
            auto = BooleanVar(value=config.get("auto_usb", True))
            startup = BooleanVar(value=autostart())
            ttk.Checkbutton(
                frame, text="Discover Nokia USB devices automatically", variable=auto
            ).grid(row=1, column=0, columnspan=3, sticky="w")
            ttk.Checkbutton(frame, text="Start at Windows sign-in", variable=startup).grid(
                row=2, column=0, columnspan=3, sticky="w"
            )
            gammu = StringVar(value=config.get("gammu_config", ""))
            profiles = StringVar(value=config.get("connections_file", ""))
            for row, label, value in [
                (3, "Gammu config (optional)", gammu),
                (4, "Connection profiles (optional)", profiles),
            ]:
                ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=7)
                ttk.Entry(frame, textvariable=value, width=43).grid(row=row, column=1)
                ttk.Button(
                    frame,
                    text="Browse",
                    command=lambda v=value: v.set(filedialog.askopenfilename() or v.get()),
                ).grid(row=row, column=2, padx=(8, 0))
            ttk.Label(
                frame,
                text="API: http://127.0.0.1:"
                + str(agent.server.server_port)
                + " · pair in SymPort → Connection",
            ).grid(row=5, column=0, columnspan=3, sticky="w", pady=10)

            def copy():
                root.clipboard_clear()
                root.clipboard_append(key)
                root.update()
                messagebox.showinfo(
                    "Bridge key",
                    "Key copied. Keep it private; configure the same key in your SymPort backend.",
                )

            ttk.Button(frame, text="Copy Bridge key", command=copy).grid(
                row=6, column=0, sticky="w"
            )

            def save():
                try:
                    for value in (gammu.get(), profiles.get()):
                        if value and (not Path(value).is_absolute() or not Path(value).is_file()):
                            raise ValueError("Choose existing absolute configuration paths")
                    config.update(
                        auto_usb=auto.get(),
                        gammu_config=gammu.get(),
                        connections_file=profiles.get(),
                    )
                    save_config(agent.root, config)
                    autostart(startup.get())
                    agent.refresh_config()
                    root.destroy()
                except (ValueError, OSError):
                    messagebox.showerror(
                        "Settings",
                        "Settings could not be applied. Check the selected files and connection profile schema.",
                    )

            ttk.Button(frame, text="Save", command=save).grid(row=6, column=2, sticky="e")
            ttk.Label(
                frame, text="No firmware flashing. Pair Bluetooth devices in Windows first."
            ).grid(row=7, column=0, columnspan=3, sticky="w", pady=(12, 0))
            try:
                root.mainloop()
            finally:
                settings_open.release()

        threading.Thread(target=window, daemon=True, name="bridge-settings").start()

    def diagnostics():
        import ctypes

        status = agent.status
        text = (
            "Version "
            + VERSION
            + "\nState: "
            + str(status["state"])
            + "\nConnected: "
            + str(status["connected"])
            + "\nNokia candidates: "
            + str(status["candidates"])
            + "\n\n"
            + "\n".join(status.get("diagnostics", []))
            + "\n\nOperation logs contain action/status only. Settings and private backups: "
            + str(agent.root)
        )
        ctypes.windll.user32.MessageBoxW(None, text, "SymPort Bridge diagnostics", 0x40)

    def logs():
        path = agent.manager.journal
        if path.exists():
            os.startfile(path)
        else:
            diagnostics()

    def quit_app(icon, item):
        icon.stop()

    asset = Path(__file__).resolve().parents[1] / "web_assets/brand/appmark-192.png"
    icon = pystray.Icon(
        "SymPortBridge",
        Image.open(asset),
        "SymPort Bridge",
        pystray.Menu(
            pystray.MenuItem(
                lambda item: (
                    "Status: " + str(agent.status["state"]) + " · " + str(agent.status["connected"])
                ),
                diagnostics,
                default=True,
            ),
            pystray.MenuItem("Settings", lambda icon, item: settings()),
            pystray.MenuItem("Diagnostics", lambda icon, item: diagnostics()),
            pystray.MenuItem("Revoke web access", lambda icon, item: agent.revoke()),
            pystray.MenuItem("Operation logs", lambda icon, item: logs()),
            pystray.MenuItem("Exit", quit_app),
        ),
    )
    icon.run()
