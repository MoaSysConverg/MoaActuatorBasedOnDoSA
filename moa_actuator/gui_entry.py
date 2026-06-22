"""GUI-first entry point for desktop/exe launches."""

from __future__ import annotations

import sys


def main() -> int:
    """Launch GUI directly for double-click/exe usage."""
    import os
    import sys
    import ctypes
    import ctypes.wintypes

    log_lines = []
    log_lines.append(f"Python version: {sys.version}")
    log_lines.append(f"sys.executable: {sys.executable}")
    log_lines.append(f"sys._MEIPASS: {getattr(sys, '_MEIPASS', 'Not defined')}")
    log_lines.append(f"Initial PATH: {os.environ.get('PATH', '')}")

    # 1. Clean up PATH
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    cleaned_dirs = []
    for d in path_dirs:
        if not d:
            continue
        qtcore = os.path.join(d, "Qt6Core.dll")
        if os.path.isfile(qtcore):
            if hasattr(sys, "_MEIPASS"):
                abs_d = os.path.abspath(d)
                abs_meipass = os.path.abspath(sys._MEIPASS)
                if abs_meipass not in abs_d and os.path.abspath(os.path.dirname(sys.executable)) not in abs_d:
                    continue
            else:
                continue
        cleaned_dirs.append(d)
    os.environ["PATH"] = os.pathsep.join(cleaned_dirs)
    log_lines.append(f"Cleaned PATH: {os.environ.get('PATH', '')}")

    # 2. Add PyQt6 DLL directory to DLL search path for PyInstaller
    if hasattr(sys, "_MEIPASS"):
        qt_bin = os.path.abspath(os.path.join(sys._MEIPASS, "PyQt6", "Qt6", "bin"))
        if os.path.isdir(qt_bin):
            os.environ["PATH"] = qt_bin + os.pathsep + os.environ.get("PATH", "")
            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(qt_bin)
                except Exception:
                    pass

    try:
        # Use absolute import so this works both as __main__ (PyInstaller exe)
        # and as a package module. Relative imports fail when run as __main__.
        from moa_actuator.gui.app import launch
        launch()
        return 0
    except Exception as exc:
        import traceback
        import tkinter as tk
        import tkinter.messagebox as mb
        tb_str = traceback.format_exc()
        try:
            with open("moa_actuator_gui_error.log", "w", encoding="utf-8") as f:
                f.write(tb_str)
        except Exception:
            pass
        root = tk.Tk()
        root.withdraw()
        mb.showerror("Startup Error", f"An error occurred during startup:\n\n{tb_str}")
        root.destroy()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

