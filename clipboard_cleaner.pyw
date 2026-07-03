# clipboard_cleaner.py
import os
import sys
import json
import time
import glob
import ctypes
import argparse
import textwrap
import threading
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, List

APP_VERSION = "2.0.2"


def show_missing_dependency_error(error_msg):
    """Shows a native OS error popup using only built-in libraries."""
    if sys.platform == 'win32':
        ctypes.windll.user32.MessageBoxW(0,
                                         f"Missing dependency: {error_msg}\n\nPlease run:\npip install -r requirements.txt",
                                         "Clipboard Cleaner - Error", 0x10)
    sys.exit(1)


try:
    import eel
    import pystray
    import pyperclip
    import darkdetect
    from PIL import Image, ImageDraw
except ImportError as e:
    show_missing_dependency_error(e.name)


def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and PyInstaller --onefile."""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


try:
    import keyboard
except ImportError:
    keyboard = None

# Redirect stdout to nowhere, but redirect stderr to a log file to catch crashes
if sys.stdout is None:
    log_dir = os.path.dirname(os.path.abspath(__file__))
    error_log_path = os.path.join(log_dir, 'cleaner_error.log')

    sys.stdout = open(os.devnull, 'w', encoding='utf-8')
    sys.stderr = open(error_log_path, 'a', encoding='utf-8')


# --- Prevent Multiple Instances ---
class AppInstanceLock:
    """Ensures only a single instance of the application runs simultaneously."""

    def __init__(self, identifier: str = "98765"):
        self.identifier = identifier
        self._lock_ref = None

    def enforce(self) -> None:
        if sys.platform == 'win32':
            mutex_name = f"Global\\ClipboardCleaner_Unique_Mutex_{self.identifier}"
            kernel32 = ctypes.windll.kernel32
            mutex = kernel32.CreateMutexW(None, False, mutex_name)
            if kernel32.GetLastError() == 183:
                sys.exit(0)
            self._lock_ref = mutex
        else:
            import fcntl
            self._lock_ref = open(f'/tmp/clipboard_cleaner_{self.identifier}.lock', 'w')
            try:
                fcntl.flock(self._lock_ref, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (BlockingIOError, IOError):
                sys.exit(0)


# --- Platform-Specific Import ---
IS_WINDOWS = sys.platform == 'win32'
if IS_WINDOWS:
    try:
        import win32gui
        import win32con
    except ImportError:
        print("Windows detected, but 'pywin32' is not installed.")
        print("Please run: pip install pywin32")
        IS_WINDOWS = False

# --- Configuration ---
TARGET_WINDOWS = []
CHECK_WINDOW_TITLES_ON_LINUX = False

# Global reference for Eel
app_instance = None


@eel.expose
def ignore_next_copy(text):
    app_instance.ignore_text = text.replace('\r\n', '\n') if isinstance(text, str) else text


@eel.expose
def get_history():
    return app_instance.history_db.load_all_history()


@eel.expose
def clear_history_data():
    import shutil
    history_dir = app_instance.history_db.base_dir
    try:
        for item in history_dir.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
    except Exception:
        pass
    return True


@eel.expose
def toggle_setting(setting_name, state):
    if setting_name == 'pause':
        app_instance.toggle_pause = state
    elif setting_name == 'diff':
        app_instance.toggle_diff = state
    elif setting_name == 'dedent':
        app_instance.toggle_dedent = state


@eel.expose
def set_gui_ready():
    app_instance.gui_ready = True


@eel.expose
def toggle_topmost(is_pinned):
    if IS_WINDOWS:
        try:
            hwnd = win32gui.GetForegroundWindow()
            if is_pinned:
                win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                                      win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
            else:
                win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                                      win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
        except Exception:
            pass


class WindowTracker:
    def __init__(self, is_windows: bool, check_linux: bool):
        self.is_windows = is_windows
        self.check_linux = check_linux

    def get_active_title(self) -> Optional[str]:
        try:
            if self.is_windows:
                hwnd = win32gui.GetForegroundWindow()
                return win32gui.GetWindowText(hwnd)
            elif not self.is_windows and self.check_linux:
                result = subprocess.check_output(
                    ['xdotool', 'getactivewindow', 'getwindowname'],
                    text=True, stderr=subprocess.DEVNULL
                )
                return result.strip()
        except Exception:
            pass
        return None


class HistoryManager:
    def __init__(self):
        self.base_dir = Path.home() / "Documents" / "smart-clipboard"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_entry(self, original: str, cleaned: str, labels: List[str]):
        now = datetime.now()
        month_dir = self.base_dir / now.strftime("%Y-%m")
        month_dir.mkdir(exist_ok=True)
        file_path = month_dir / f"{now.strftime('%Y-%m-%d')}.json"

        entry = {
            "timestamp": now.isoformat(),
            "original": original,
            "cleaned": cleaned,
            "labels": labels
        }

        history = []
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            except json.JSONDecodeError:
                pass

        history.append(entry)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=4, ensure_ascii=False)

    def load_all_history(self) -> dict:
        history_by_date = {}
        for file_path in sorted(glob.glob(str(self.base_dir / "*" / "*.json"))):
            date_str = Path(file_path).stem
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                    if history:
                        history_by_date[date_str] = history
            except json.JSONDecodeError:
                pass
        return history_by_date


class SystemTrayMenu:
    def __init__(self, app_instance):
        self.app = app_instance
        self.icon = None

    def _create_image(self, is_paused: bool = False) -> Image:
        is_dark = darkdetect.isDark()
        bg_color = (0, 0, 0, 0)
        board_color = (100, 100, 100) if is_paused else ((220, 220, 220) if is_dark else (40, 40, 40))
        paper_color = (150, 150, 150) if is_paused else ((255, 255, 255) if is_dark else (240, 240, 240))
        clip_color = (120, 120, 120) if is_paused else (97, 175, 239)

        image = Image.new('RGBA', (64, 64), color=bg_color)
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((12, 16, 52, 60), radius=4, fill=board_color)
        draw.rectangle((18, 26, 46, 56), fill=paper_color)
        draw.rounded_rectangle((24, 8, 40, 20), radius=2, fill=clip_color)

        if is_paused:
            draw.rectangle((26, 34, 32, 48), fill=(220, 60, 60))
            draw.rectangle((38, 34, 44, 48), fill=(220, 60, 60))
        return image

    def _quit_app(self, icon, item):
        icon.stop()
        try:
            if self.app.gui_ready:
                eel.close_window()
                time.sleep(0.2)
        except Exception:
            pass
        os._exit(0)

    def _toggle_pause(self, icon, item):
        self.app.toggle_pause = not self.app.toggle_pause
        if self.icon:
            self.icon.icon = self._create_image(is_paused=self.app.toggle_pause)

    def _show_gui(self, icon, item):
        try:
            eel.show('index.html')
            self.app.gui_ready = True
        except Exception:
            pass

    def start(self):
        menu = pystray.Menu(
            pystray.MenuItem('Show History (GUI)', self._show_gui, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Pause All Cleaning', self._toggle_pause, checked=lambda item: self.app.toggle_pause),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Clean Diffs (+/-)', lambda: setattr(self.app, 'toggle_diff', not self.app.toggle_diff),
                             checked=lambda item: self.app.toggle_diff),
            pystray.MenuItem('Smart Dedent Code',
                             lambda: setattr(self.app, 'toggle_dedent', not self.app.toggle_dedent),
                             checked=lambda item: self.app.toggle_dedent),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Exit', self._quit_app),
        )
        self.icon = pystray.Icon("ClipboardCleaner", self._create_image(is_paused=self.app.toggle_pause),
                                 "Clipboard Cleaner", menu)
        self.icon.run()


class ClipboardFormatter:
    @staticmethod
    def clean(text: str, pause: bool, do_diff: bool, do_dedent: bool) -> Tuple[str, bool, List[str]]:
        if pause or not isinstance(text, str):
            return text, False, []

        original_text = text
        applied_labels = []
        text = text.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")

        if text.strip().startswith('```') and text.strip().endswith('```'):
            lines = text.strip().splitlines()
            if len(lines) >= 2:
                text = "\n".join(lines[1:-1])
                applied_labels.append("Markdown Stripped")

        if text.strip().startswith(('{', '[')) and text.strip().endswith(('}', ']')):
            try:
                parsed = json.loads(text)
                text = json.dumps(parsed, indent=4)
                applied_labels.append("JSON Formatted")
            except ValueError:
                pass

        for char in ['\u200b', '\u200c', '\u200d', '\ufeff']:
            if char in text:
                text = text.replace(char, '')
                applied_labels.append("Zero-Width Cleaned")

        lines = text.splitlines()
        cleaned_lines = []
        diff_cleaned = False

        for line in lines:
            if line.startswith(('--- a/', '+++ b/', '@@ ', 'diff --git', 'index ')):
                diff_cleaned = True
                continue
            if line.startswith(('$ ', '# ', '> ')):
                cleaned_lines.append(line[2:])
                continue
            if line.lstrip().startswith('%') and not line.lstrip().startswith('%%'):
                continue

            if do_diff and line.startswith(('+', '-')):
                content = line[1:]
                if content.startswith(' ') and not content.startswith('  '):
                    content = content[1:]
                cleaned_lines.append(content)
                diff_cleaned = True
            else:
                cleaned_lines.append(line.rstrip())

        if diff_cleaned:
            applied_labels.append("Diff/Comments Cleaned")

        joined_text = "\n".join(cleaned_lines)

        if do_dedent:
            dedented = textwrap.dedent(joined_text)
            if dedented != joined_text:
                joined_text = dedented
                applied_labels.append("Smart Dedent")

        is_changed = joined_text != original_text
        return joined_text, is_changed, applied_labels


class ClipboardApp:
    def __init__(self, target_windows: list, silent: bool):
        self.target_windows = target_windows
        self.silent = silent

        self.toggle_pause = False
        self.toggle_diff = True
        self.toggle_dedent = False
        self.gui_ready = False

        self.ignore_text = None

        self.original_text = ""
        self.cleaned_text = ""
        self.last_processed = pyperclip.paste()

        self.tracker = WindowTracker(IS_WINDOWS, CHECK_WINDOW_TITLES_ON_LINUX)
        self.formatter = ClipboardFormatter()
        self.history_db = HistoryManager()

    def paste_original(self):
        if self.original_text and keyboard:
            pyperclip.copy(self.original_text)
            time.sleep(0.05)
            keyboard.send('ctrl+v')
            time.sleep(0.05)
            pyperclip.copy(self.cleaned_text)

    def _poll_clipboard(self):
        while True:
            try:
                current_text = pyperclip.paste()
                current_normalized = current_text.replace('\r\n', '\n') if isinstance(current_text,
                                                                                      str) else current_text

                if self.ignore_text and current_normalized == self.ignore_text:
                    self.last_processed = current_text
                    self.ignore_text = None
                    time.sleep(0.5)
                    continue

                if current_text != self.last_processed and current_text != self.original_text:
                    self.original_text = current_text
                    window_title = self.tracker.get_active_title()

                    should_process = (
                            not self.target_windows or
                            (not IS_WINDOWS and not CHECK_WINDOW_TITLES_ON_LINUX) or
                            (window_title and any(t.lower() in window_title.lower() for t in self.target_windows))
                    )

                    if should_process:
                        cleaned, was_changed, labels = self.formatter.clean(
                            current_text, self.toggle_pause, self.toggle_diff, self.toggle_dedent
                        )
                        self.history_db.save_entry(current_text, cleaned, labels)

                        if self.gui_ready:
                            try:
                                eel.add_new_entry(current_text, cleaned, labels)()
                            except Exception:
                                pass

                        if was_changed:
                            if not self.silent:
                                print(f"Change detected from: {window_title or 'Unknown'}")
                            pyperclip.copy(cleaned)
                            self.last_processed = cleaned
                            self.cleaned_text = cleaned
                        else:
                            self.last_processed = current_text
                            self.cleaned_text = current_text
                    else:
                        self.last_processed = current_text
                        self.cleaned_text = current_text

                time.sleep(0.5)

            except pyperclip.PyperclipException:
                self.last_processed = ""
                time.sleep(1)

    def run(self):
        global app_instance
        app_instance = self

        if keyboard:
            keyboard.add_hotkey('ctrl+shift+v', self.paste_original)

        threading.Thread(target=self._poll_clipboard, daemon=True).start()
        tray = SystemTrayMenu(self)
        threading.Thread(target=tray.start, daemon=True).start()

        if not self.silent:
            print("Clipboard Cleaner is running...")

        web_dir = get_resource_path('web')
        os.makedirs(web_dir, exist_ok=True)

        icon_path = os.path.join(web_dir, 'icon.ico')
        tray._create_image().save(icon_path, format='ICO')

        eel.init(web_dir)

        def handle_close(page, sockets):
            self.gui_ready = False

        try:
            eel.start('index.html', size=(1200, 800), mode='chrome', block=False, close_callback=handle_close)
            while True:
                eel.sleep(1.0)
        except (SystemExit, KeyboardInterrupt):
            pass


if __name__ == "__main__":
    AppInstanceLock().enforce()
    parser = argparse.ArgumentParser(description="Monitors and cleans clipboard text.")
    parser.add_argument("--silent", action="store_true", help="Run without console output.")
    args = parser.parse_args()
    ClipboardApp(TARGET_WINDOWS, args.silent).run()
