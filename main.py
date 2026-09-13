import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
import minecraft_launcher_lib as mll
import subprocess
import os
import sys
import shutil
import tempfile
import time
import json
import urllib.request
import zipfile
import platform
import requests
import threading
import webbrowser
from pathlib import Path
import ssl
import certifi
from datetime import datetime
import pickle
import random
from PIL import Image, ImageTk
from io import BytesIO
import socket
import base64
import re
import traceback
import hashlib
import websocket as ws_client
from urllib.parse import unquote
import multiprocessing

RELAY_URL = "wss://screen-relay-production.up.railway.app"


def check_dependencies():
    required = ['customtkinter', 'minecraft_launcher_lib', 'requests', 'PIL', 'certifi']
    pip_names = {}
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pip_names.get(pkg, pkg))

    required_pip_only = {'websocket': 'websocket-client', 'webview': 'pywebview'}
    for import_name, pip_name in required_pip_only.items():
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pip_name)

    if missing:
        print(f"❌ Отсутствуют пакеты: {', '.join(missing)}")
        print("Установите их командой:")
        print(f"pip install {' '.join(missing)}")
        input("Нажмите Enter для выхода...")
        sys.exit(1)


check_dependencies()


def _ms_login_webview_process(login_url, redirect_uri, result_queue):
    """
    Запускается в ОТДЕЛЬНОМ процессе, потому что pywebview требует,
    чтобы webview.start() вызывался в главном потоке процесса - а
    главный поток основного лаунчера занят циклом Tkinter.
    """
    try:
        import re as _re
        import webview
        from urllib.parse import unquote as _unquote
    except Exception as e:
        result_queue.put({"code": None, "error": f"import_error: {e}"})
        return

    captured = {"code": None, "error": None, "done": False}

    def check_url():
        if captured["done"]:
            return
        try:
            current_url = window.get_current_url()
        except Exception:
            return
        if not current_url or not current_url.startswith(redirect_uri):
            return

        captured["done"] = True
        match = _re.search(r'[?&]code=([^&]+)', current_url)
        if match:
            captured["code"] = _unquote(match.group(1))
        else:
            err_match = _re.search(r'[?&]error=([^&]+)', current_url)
            captured["error"] = _unquote(err_match.group(1)) if err_match else "Вход отменён"
        try:
            window.destroy()
        except Exception:
            pass

    window = webview.create_window(
        "Вход в Microsoft — залогинься своим аккаунтом",
        login_url,
        width=480,
        height=640,
        confirm_close=False,
    )
    window.events.loaded += check_url

    try:
        webview.start(gui="edgechromium", debug=False)
    except Exception:
        try:
            webview.start(debug=False)
        except Exception as e:
            result_queue.put({"code": None, "error": f"webview_start_error: {e}"})
            return

    result_queue.put({"code": captured["code"], "error": captured["error"]})


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def add_firewall_rule():
    if sys.platform != "win32":
        return True

    try:
        import subprocess
        check_cmd = 'netsh advfirewall firewall show rule name="67Launcher Chat"'
        result = subprocess.run(check_cmd, capture_output=True, text=True, shell=True, encoding='cp866')

        if "No rules match" in result.stdout or "Не найдено" in result.stdout:
            add_cmd = 'netsh advfirewall firewall add rule name="67Launcher Chat" dir=in action=allow protocol=TCP localport=25565'
            subprocess.run(add_cmd, capture_output=True, text=True, shell=True, encoding='cp866')
            add_cmd2 = 'netsh advfirewall firewall add rule name="67Launcher Chat All" dir=in action=allow protocol=TCP localport=25560-25570'
            subprocess.run(add_cmd2, capture_output=True, text=True, shell=True, encoding='cp866')
            print("✅ Правило брандмауэра добавлено")
            return True
        else:
            print("✅ Правило брандмауэра уже существует")
            return True
    except Exception as e:
        print(f"⚠️ Не удалось добавить правило брандмауэра: {e}")
        return False


def get_sound_path(sound_name):
    paths_to_try = []
    exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    paths_to_try.append(os.path.join(exe_dir, "resources", sound_name))
    paths_to_try.append(os.path.join(exe_dir, sound_name))
    paths_to_try.append(os.path.join(os.getcwd(), "resources", sound_name))
    paths_to_try.append(os.path.join(os.getcwd(), sound_name))
    paths_to_try.append(os.path.join("resources", sound_name))
    paths_to_try.append(sound_name)
    try:
        if hasattr(sys, '_MEIPASS'):
            paths_to_try.insert(0, os.path.join(sys._MEIPASS, "resources", sound_name))
            paths_to_try.insert(0, os.path.join(sys._MEIPASS, sound_name))
    except:
        pass
    for path in paths_to_try:
        if os.path.exists(path):
            return path
    return None


def play_mp3_winmm(sound_path):
    try:
        import ctypes
        winmm = ctypes.WinDLL('winmm.dll')

        def mci_send_string(command):
            buffer = ctypes.create_unicode_buffer(1024)
            result = winmm.mciSendStringW(command, buffer, 1024, None)
            return result, buffer.value

        mci_send_string("close all")
        cmd = f'open "{sound_path}" type mpegvideo alias mp3'
        result, _ = mci_send_string(cmd)
        if result != 0:
            return False
        result, _ = mci_send_string("play mp3")
        if result != 0:
            mci_send_string("close mp3")
            return False

        def close_mp3():
            time.sleep(3)
            try:
                mci_send_string("close mp3")
            except:
                pass

        threading.Thread(target=close_mp3, daemon=True).start()
        return True
    except:
        return False


def play_sound(sound_type="click"):
    try:
        sound_name = "PING.mp3" if sound_type == "click" else "FAHH.mp3"
        sound_path = get_sound_path(sound_name)
        if sound_path and os.path.exists(sound_path):
            if play_mp3_winmm(sound_path):
                return True
        if sys.platform == "win32":
            import winsound
            if sound_type == "error":
                winsound.Beep(500, 500)
                time.sleep(0.1)
                winsound.Beep(300, 500)
            else:
                winsound.Beep(1000, 100)
            return True
    except:
        pass
    return False


def play_click():
    threading.Thread(target=lambda: play_sound("click"), daemon=True).start()


def play_error():
    threading.Thread(target=lambda: play_sound("error"), daemon=True).start()


GOLDEN_THEME_ACTIVE = {"value": False}
_GOLDEN_BUTTON_REGISTRY = []

GOLDEN_FG_COLOR = "#FFD700"
GOLDEN_HOVER_COLOR = "#C9A400"
GOLDEN_TEXT_COLOR = "#16141f"


def _register_golden_button(button):
    try:
        original = {
            "fg_color": button.cget("fg_color"),
            "hover_color": button.cget("hover_color"),
            "text_color": button.cget("text_color"),
        }
    except Exception:
        original = None
    _GOLDEN_BUTTON_REGISTRY.append((button, original))
    if GOLDEN_THEME_ACTIVE["value"] and original is not None:
        _apply_golden_to_button(button)


def _apply_golden_to_button(button):
    try:
        button.configure(fg_color=GOLDEN_FG_COLOR, hover_color=GOLDEN_HOVER_COLOR,
                          text_color=GOLDEN_TEXT_COLOR)
    except Exception:
        pass


def _restore_button_color(button, original):
    if original is None:
        return
    try:
        button.configure(**original)
    except Exception:
        pass


def set_golden_button_theme(active):
    """Включает/выключает золотую тему для ВСЕХ кнопок приложения разом."""
    GOLDEN_THEME_ACTIVE["value"] = active
    alive_registry = []
    for button, original in _GOLDEN_BUTTON_REGISTRY:
        try:
            if not button.winfo_exists():
                continue
        except Exception:
            continue
        alive_registry.append((button, original))
        if active:
            _apply_golden_to_button(button)
        else:
            _restore_button_color(button, original)
    _GOLDEN_BUTTON_REGISTRY[:] = alive_registry


def make_sound_button(master, text, command, **kwargs):
    def wrapped_command():
        play_click()
        if command:
            command()

    btn = ctk.CTkButton(master, text=text, command=wrapped_command, **kwargs)
    _register_golden_button(btn)
    return btn


def generate_room_code(length=6):
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(random.choice(alphabet) for _ in range(length))


def safe_window_geometry(size_str, default="800x850", min_w=400, min_h=400, max_w=1400, max_h=1000):
    try:
        width_str, height_str = size_str.lower().split("x")
        width, height = int(width_str), int(height_str)
        if width < min_w or height < min_h or width > max_w or height > max_h:
            return default
        return f"{width}x{height}"
    except:
        return default


def get_settings_path():
    game_appdata = os.path.join(os.environ.get('APPDATA', os.path.expanduser("~")), ".minecraft")
    try:
        os.makedirs(game_appdata, exist_ok=True)
    except:
        pass
    settings_path = os.path.join(game_appdata, "launcher_settings.json")

    if not os.path.exists(settings_path):
        old_docs_dir = os.path.join(os.path.expanduser("~"), "Documents", "67Launcher")
        old_settings_path = os.path.join(old_docs_dir, "launcher_settings.json")
        if os.path.exists(old_settings_path):
            try:
                shutil.copy2(old_settings_path, settings_path)
                old_stats_path = os.path.join(old_docs_dir, "launcher_stats.json")
                new_stats_path = os.path.join(game_appdata, "launcher_stats.json")
                if os.path.exists(old_stats_path) and not os.path.exists(new_stats_path):
                    shutil.copy2(old_stats_path, new_stats_path)
            except:
                pass

    return settings_path


def get_cert_path():
    exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    cert_path = os.path.join(exe_dir, "cacert.pem")
    if os.path.exists(cert_path):
        return cert_path
    cert_path = os.path.join(os.path.dirname(exe_dir), "cacert.pem")
    if os.path.exists(cert_path):
        return cert_path
    cert_path = os.path.join(os.getcwd(), "cacert.pem")
    if os.path.exists(cert_path):
        return cert_path
    try:
        cert_path = resource_path("cacert.pem")
        if os.path.exists(cert_path):
            return cert_path
    except:
        pass
    try:
        import certifi
        return certifi.where()
    except:
        return None


def fix_ssl_for_windows():
    try:
        cert_path = get_cert_path()
        if cert_path and os.path.exists(cert_path):
            os.environ['SSL_CERT_FILE'] = cert_path
            os.environ['REQUESTS_CA_BUNDLE'] = cert_path
            ssl_context = ssl.create_default_context(cafile=cert_path)
            try:
                import urllib.request
                https_handler = urllib.request.HTTPSHandler(context=ssl_context)
                opener = urllib.request.build_opener(https_handler)
                urllib.request.install_opener(opener)
            except:
                pass
            try:
                import requests
                requests.packages.urllib3.disable_warnings()
                session = requests.Session()
                session.verify = cert_path
                requests.sessions.session = lambda: session
            except:
                pass
            print("✅ SSL fix applied")
            return True
    except Exception as e:
        print(f"⚠️ SSL fix error: {e}")
        return False


if sys.platform == "win32":
    try:
        fix_ssl_for_windows()
    except:
        pass

_THEME_67LAUNCHER = {
    "CTk": {"fg_color": ["#f3f2f9", "#16141f"]},
    "CTkToplevel": {"fg_color": ["#f3f2f9", "#16141f"]},
    "CTkFrame": {
        "corner_radius": 6, "border_width": 0,
        "fg_color": ["#ffffff", "#1a1826"],
        "top_fg_color": ["#f6f5fb", "#1c1a29"],
        "border_color": ["#ddd9ec", "#26243a"]
    },
    "CTkButton": {
        "corner_radius": 5, "border_width": 0,
        "fg_color": ["#3d6bf0", "#3d6bf0"],
        "hover_color": ["#3157c4", "#3157c4"],
        "border_color": ["#c7c2df", "#302c46"],
        "text_color": ["#ffffff", "#ffffff"],
        "text_color_disabled": ["#a29cc0", "#7a7791"]
    },
    "CTkLabel": {
        "corner_radius": 0, "fg_color": "transparent",
        "text_color": ["#221f30", "#e5e2f0"]
    },
    "CTkEntry": {
        "corner_radius": 5, "border_width": 1,
        "fg_color": ["#ffffff", "#201d30"],
        "border_color": ["#c9c4de", "#302c46"],
        "text_color": ["#221f30", "#e5e2f0"],
        "placeholder_text_color": ["#8f89a8", "#7a7791"]
    },
    "CTkCheckBox": {
        "corner_radius": 4, "border_width": 2,
        "fg_color": ["#3d6bf0", "#3d6bf0"],
        "border_color": ["#b6b0cf", "#4a4664"],
        "hover_color": ["#3157c4", "#3157c4"],
        "checkmark_color": ["#ffffff", "#ffffff"],
        "text_color": ["#221f30", "#e5e2f0"],
        "text_color_disabled": ["#a29cc0", "#7a7791"]
    },
    "CTkSwitch": {
        "corner_radius": 1000, "border_width": 3, "button_length": 0,
        "fg_color": ["#dedaee", "#302c46"],
        "progress_color": ["#3d6bf0", "#3d6bf0"],
        "button_color": ["#ffffff", "#e5e2f0"],
        "button_hover_color": ["#f3f2f9", "#ffffff"],
        "text_color": ["#221f30", "#e5e2f0"],
        "text_color_disabled": ["#a29cc0", "#7a7791"]
    },
    "CTkRadioButton": {
        "corner_radius": 1000, "border_width_checked": 4, "border_width_unchecked": 2,
        "fg_color": ["#3d6bf0", "#6d92ff"],
        "border_color": ["#b6b0cf", "#4a4664"],
        "hover_color": ["#3157c4", "#5a7dd8"],
        "text_color": ["#3c3852", "#cfcbe0"],
        "text_color_disabled": ["#a29cc0", "#7a7791"]
    },
    "CTkProgressBar": {
        "corner_radius": 3, "border_width": 0,
        "fg_color": ["#e4e1f2", "#2b2840"],
        "progress_color": ["#3d6bf0", "#6d92ff"],
        "border_color": ["#ddd9ec", "#26243a"]
    },
    "CTkSlider": {
        "corner_radius": 1000, "button_corner_radius": 1000, "border_width": 6,
        "fg_color": ["#e4e1f2", "#2b2840"],
        "progress_color": ["#cfc9e8", "#302c46"],
        "button_color": ["#3d6bf0", "#3d6bf0"],
        "button_hover_color": ["#3157c4", "#3157c4"]
    },
    "CTkOptionMenu": {
        "corner_radius": 5,
        "fg_color": ["#ffffff", "#201d30"],
        "button_color": ["#e4e1f2", "#302c46"],
        "button_hover_color": ["#3d6bf0", "#3d6bf0"],
        "text_color": ["#221f30", "#e5e2f0"],
        "text_color_disabled": ["#a29cc0", "#7a7791"]
    },
    "CTkComboBox": {
        "corner_radius": 5, "border_width": 1,
        "fg_color": ["#ffffff", "#201d30"],
        "border_color": ["#c9c4de", "#302c46"],
        "button_color": ["#e4e1f2", "#302c46"],
        "button_hover_color": ["#3d6bf0", "#3d6bf0"],
        "text_color": ["#221f30", "#e5e2f0"],
        "text_color_disabled": ["#a29cc0", "#7a7791"]
    },
    "CTkScrollbar": {
        "corner_radius": 1000, "border_spacing": 4, "fg_color": "transparent",
        "button_color": ["#d3cee6", "#302c46"],
        "button_hover_color": ["#3d6bf0", "#3d6bf0"]
    },
    "CTkSegmentedButton": {
        "corner_radius": 5, "border_width": 2,
        "fg_color": ["#ffffff", "#201d30"],
        "selected_color": ["#3d6bf0", "#3d6bf0"],
        "selected_hover_color": ["#3157c4", "#3157c4"],
        "unselected_color": ["#ffffff", "#201d30"],
        "unselected_hover_color": ["#eeecf8", "#2b2840"],
        "text_color": ["#221f30", "#e5e2f0"],
        "text_color_disabled": ["#a29cc0", "#7a7791"]
    },
    "CTkTextbox": {
        "corner_radius": 5, "border_width": 0,
        "fg_color": ["#ffffff", "#100e1a"],
        "border_color": ["#ddd9ec", "#26243a"],
        "text_color": ["#4b4763", "#8f8ba6"],
        "scrollbar_button_color": ["#d3cee6", "#302c46"],
        "scrollbar_button_hover_color": ["#3d6bf0", "#3d6bf0"]
    },
    "CTkScrollableFrame": {"label_fg_color": ["#ffffff", "#1a1826"]},
    "CTkTabview": {
        "corner_radius": 6, "border_width": 0,
        "fg_color": ["#ffffff", "#1a1826"],
        "segmented_button_fg_color": ["#eeecf8", "#1a1826"],
        "segmented_button_selected_color": ["#ffffff", "#1c1a29"],
        "segmented_button_selected_hover_color": ["#ffffff", "#1c1a29"],
        "segmented_button_unselected_color": ["#eeecf8", "#1a1826"],
        "segmented_button_unselected_hover_color": ["#e2dff2", "#201d30"],
        "text_color": ["#4b4763", "#a8a4bd"],
        "text_color_disabled": ["#c2bdd6", "#4a4664"]
    },
    "DropdownMenu": {
        "fg_color": ["#ffffff", "#201d30"],
        "hover_color": ["#eeecf8", "#2b2840"],
        "text_color": ["#221f30", "#e5e2f0"]
    },
    "CTkFont": {
        "macOS": {"family": "SF Display", "size": -13, "weight": "normal"},
        "Windows": {"family": "Segoe UI", "size": -13, "weight": "normal"},
        "Linux": {"family": "Roboto", "size": -13, "weight": "normal"}
    }
}


def _load_67launcher_theme():
    merged = {}
    try:
        base_theme_path = os.path.join(
            os.path.dirname(ctk.__file__), "assets", "themes", "blue.json"
        )
        with open(base_theme_path, "r", encoding="utf-8") as f:
            merged = json.load(f)
    except Exception:
        merged = {}

    def deep_merge(base, override):
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                deep_merge(base[key], value)
            else:
                base[key] = value

    deep_merge(merged, _THEME_67LAUNCHER)

    try:
        theme_path = os.path.join(tempfile.gettempdir(), "67launcher_theme.json")
        with open(theme_path, "w", encoding="utf-8") as f:
            json.dump(merged, f)
        return theme_path
    except Exception:
        return "blue"


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme(_load_67launcher_theme())

DEFAULT_GAME_DIR = os.path.join(os.environ['APPDATA'], ".minecraft")
GAME_DIR = DEFAULT_GAME_DIR
MINECRAFT_DIR = GAME_DIR

SETTINGS_FILE = get_settings_path()
STATS_FILE = os.path.join(os.path.dirname(SETTINGS_FILE), "launcher_stats.json")

ACCOUNTS_FILE = os.path.join(MINECRAFT_DIR, "accounts.json")
PROFILES_FILE = os.path.join(MINECRAFT_DIR, "profile.json")
LAUNCHER_PROFILES_FILE = os.path.join(MINECRAFT_DIR, "launcher_profiles.json")

REQUIRED_FOLDERS = [
    "assets", "config", "libraries", "logs", "mods",
    "resourcepacks", "resources", "runtime", "saves",
    "skins", "stats", "texturepacks", "versions"
]


def fix_game_path():
    settings_path = SETTINGS_FILE
    if os.path.exists(settings_path):
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            old_path = settings.get("game_dir", "")
            if ".ionux" in old_path or old_path != DEFAULT_GAME_DIR:
                settings["game_dir"] = DEFAULT_GAME_DIR
                with open(settings_path, 'w', encoding='utf-8') as f:
                    json.dump(settings, f, indent=2, ensure_ascii=False)
        except:
            pass

fix_game_path()

log_callback = None


def set_log_callback(callback):
    global log_callback
    log_callback = callback


def log_message(message):
    global log_callback
    if log_callback:
        log_callback(message)

DEFAULT_MS_CLIENT_ID = "6ca935f1-4e54-484c-bbe2-482a8dcf9b33"


def load_launcher_settings():
    default_settings = {
        "game_dir": DEFAULT_GAME_DIR,
        "last_version": "",
        "last_account": "",
        "last_skin": "",
        "ram": "2G",
        "java_path": "",
        "snapshots": False,
        "launch_count": 0,
        "hygiene_reminders": True,
        "support_shown_5": False,
        "theme": "dark",
        "golden_theme_enabled": True,
        "secret_clicks": 0,
        "show_game_logs": False,
        "chat_window_size": "800x850",
        "ms_client_id": DEFAULT_MS_CLIENT_ID,
        "ms_redirect_uri": "https://login.microsoftonline.com/common/oauth2/nativeclient"
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                if 'support_shown' in settings:
                    del settings['support_shown']
                for key in default_settings:
                    if key not in settings:
                        settings[key] = default_settings[key]
                return settings
        except:
            return default_settings
    else:
        try:
            os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(default_settings, f, indent=2, ensure_ascii=False)
        except:
            pass
        return default_settings


def save_launcher_settings(settings):
    try:
        if 'support_shown' in settings:
            del settings['support_shown']
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        return True
    except:
        return False


def load_stats():
    default_stats = {"launches": 0, "total_play_time": 0, "last_launch": None, "launch_history": []}
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return default_stats
    return default_stats


def save_stats(stats):
    try:
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        return True
    except:
        return False


def update_stats():
    stats = load_stats()
    stats["launches"] += 1
    stats["last_launch"] = datetime.now().isoformat()
    stats["launch_history"].append({
        "time": datetime.now().isoformat(),
        "version": LauncherApp.instance.version_combo.get() if hasattr(LauncherApp.instance,
                                                                       'version_combo') else "unknown"
    })
    if len(stats["launch_history"]) > 100:
        stats["launch_history"] = stats["launch_history"][-100:]
    save_stats(stats)

    if LauncherApp.instance:
        def _update_ui():
            LauncherApp.instance.update_info_display()
            LauncherApp.instance.update_subtitle()

        try:
            LauncherApp.instance.after(0, _update_ui)
        except:
            pass


def update_play_time(seconds):
    stats = load_stats()
    stats["total_play_time"] = stats.get("total_play_time", 0) + seconds
    save_stats(stats)
    if LauncherApp.instance:
        def _update_ui():
            LauncherApp.instance.stats = stats
            LauncherApp.instance.update_info_display()

        try:
            LauncherApp.instance.after(0, _update_ui)
        except:
            pass


def create_launcher_profiles():
    launcher_profiles = {
        "profiles": {},
        "settings": {"enableSnapshots": False, "enableHistorical": False, "keepLauncherOpen": False},
        "selectedProfile": "Latest Release",
        "clientToken": "67-launcher-token",
        "authenticationDatabase": {}
    }
    os.makedirs(os.path.dirname(LAUNCHER_PROFILES_FILE), exist_ok=True)
    with open(LAUNCHER_PROFILES_FILE, 'w', encoding='utf-8') as f:
        json.dump(launcher_profiles, f, indent=2)


def cleanup_forge_temp():
    temp_dir = tempfile.gettempdir()
    for item in os.listdir(temp_dir):
        if item.startswith("minecraft-launcher-lib-forge") or item.startswith("minecraft-launcher-lib-fabric"):
            temp_path = os.path.join(temp_dir, item)
            try:
                shutil.rmtree(temp_path, ignore_errors=True)
            except:
                pass


def ensure_game_folder_structure():
    global MINECRAFT_DIR
    os.makedirs(MINECRAFT_DIR, exist_ok=True)
    for folder in REQUIRED_FOLDERS:
        folder_path = os.path.join(MINECRAFT_DIR, folder)
        os.makedirs(folder_path, exist_ok=True)
    create_launcher_profiles()
    empty_files = ["accounts.json", "options.txt", "profile.json", "profiles.json", "servers.dat", "usercache.json"]
    for filename in empty_files:
        filepath = os.path.join(MINECRAFT_DIR, filename)
        if not os.path.exists(filepath):
            with open(filepath, 'w', encoding='utf-8') as f:
                if filename.endswith('.json'):
                    json.dump({}, f)
                elif filename.endswith('.txt'):
                    f.write("# Minecraft Options\n")
                elif filename.endswith('.dat'):
                    f.write("")


def load_accounts():
    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    accounts = data
                elif isinstance(data, dict):
                    if "accounts" in data:
                        accounts = data["accounts"]
                    else:
                        accounts = list(data.values())
                else:
                    accounts = []
                for acc in accounts:
                    if 'created' not in acc:
                        acc['created'] = "давно"
                return accounts
        except:
            return []
    return []


def save_accounts(accounts):
    os.makedirs(os.path.dirname(ACCOUNTS_FILE), exist_ok=True)
    try:
        with open(ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(accounts, f, indent=2, ensure_ascii=False)
        return True
    except:
        return False


def create_offline_account(username):
    return {"type": "offline", "username": username, "created": time.strftime("%Y-%m-%d %H:%M:%S")}


def create_microsoft_account(login_data):
    return {
        "type": "microsoft",
        "username": login_data["name"],
        "uuid": login_data["id"],
        "access_token": login_data["access_token"],
        "refresh_token": login_data.get("refresh_token", ""),
        "created": time.strftime("%Y-%m-%d %H:%M:%S")
    }


def add_microsoft_account(login_data):
    accounts = load_accounts()
    for i, acc in enumerate(accounts):
        if acc.get("uuid") == login_data["id"] or acc["username"].lower() == login_data["name"].lower():
            accounts[i] = create_microsoft_account(login_data)
            save_accounts(accounts)
            return True, "Аккаунт обновлён"
    accounts.append(create_microsoft_account(login_data))
    if save_accounts(accounts):
        return True, "Лицензионный аккаунт добавлен"
    return False, "Ошибка сохранения"


def refresh_microsoft_account(account):
    client_id = load_launcher_settings().get("ms_client_id", "").strip() or DEFAULT_MS_CLIENT_ID
    redirect_uri = load_launcher_settings().get("ms_redirect_uri",
                                                "https://login.microsoftonline.com/common/oauth2/nativeclient").strip()
    if not client_id or not account.get("refresh_token"):
        return None
    try:
        login_data = mll.microsoft_account.complete_refresh(
            client_id, None, redirect_uri, account["refresh_token"]
        )
        accounts = load_accounts()
        for i, acc in enumerate(accounts):
            if acc.get("uuid") == account.get("uuid"):
                accounts[i] = create_microsoft_account(login_data)
                save_accounts(accounts)
                break
        return login_data
    except Exception:
        return None


def get_or_create_elyby_client_token():
    settings = load_launcher_settings()
    token = settings.get("elyby_client_token", "").strip()
    if not token:
        token = hashlib.sha1(f"{time.time()}{random.random()}".encode()).hexdigest()
        settings["elyby_client_token"] = token
        save_launcher_settings(settings)
    return token


def format_uuid_with_dashes(raw_uuid):
    raw_uuid = raw_uuid.replace("-", "")
    if len(raw_uuid) != 32:
        return raw_uuid
    return f"{raw_uuid[0:8]}-{raw_uuid[8:12]}-{raw_uuid[12:16]}-{raw_uuid[16:20]}-{raw_uuid[20:32]}"


def elyby_authenticate(login, password):
    """
    Настоящая авторизация через официальный (документированный) Yggdrasil-совместимый
    API Ely.by: https://docs.ely.by/ru/minecraft-auth.html
    Возвращает (True, login_data) или (False, "текст ошибки").
    """
    client_token = get_or_create_elyby_client_token()
    try:
        response = requests.post(
            "https://authserver.ely.by/auth/authenticate",
            json={
                "username": login,
                "password": password,
                "clientToken": client_token,
                "requestUser": True,
            },
            timeout=15,
        )
    except Exception as e:
        return False, f"Не удалось связаться с ely.by: {e}"

    data = {}
    try:
        data = response.json()
    except Exception:
        pass

    if response.status_code != 200:
        error_message = data.get("errorMessage") or data.get("error") or f"HTTP {response.status_code}"
        return False, error_message

    profile = data.get("selectedProfile") or {}
    login_data = {
        "name": profile.get("name", login),
        "id": format_uuid_with_dashes(profile.get("id", "")),
        "access_token": data.get("accessToken", ""),
        "client_token": data.get("clientToken", client_token),
    }
    return True, login_data


def create_elyby_account(login_data):
    return {
        "type": "elyby",
        "username": login_data["name"],
        "uuid": login_data["id"],
        "access_token": login_data["access_token"],
        "client_token": login_data.get("client_token", ""),
        "created": time.strftime("%Y-%m-%d %H:%M:%S")
    }


def add_elyby_account(login_data):
    accounts = load_accounts()
    for i, acc in enumerate(accounts):
        if acc.get("uuid") == login_data["id"] or acc["username"].lower() == login_data["name"].lower():
            accounts[i] = create_elyby_account(login_data)
            save_accounts(accounts)
            return True, "Аккаунт обновлён"
    accounts.append(create_elyby_account(login_data))
    if save_accounts(accounts):
        return True, "Ely.by-аккаунт добавлен"
    return False, "Ошибка сохранения"


def refresh_elyby_account(account):
    if not account.get("access_token") or not account.get("client_token"):
        return None
    try:
        response = requests.post(
            "https://authserver.ely.by/auth/refresh",
            json={
                "accessToken": account["access_token"],
                "clientToken": account["client_token"],
                "requestUser": True,
            },
            timeout=15,
        )
        if response.status_code != 200:
            return None
        data = response.json()
        profile = data.get("selectedProfile") or {}
        login_data = {
            "name": profile.get("name", account.get("username", "")),
            "id": format_uuid_with_dashes(profile.get("id", account.get("uuid", ""))),
            "access_token": data.get("accessToken", ""),
            "client_token": data.get("clientToken", account["client_token"]),
        }
        accounts = load_accounts()
        for i, acc in enumerate(accounts):
            if acc.get("uuid") == account.get("uuid"):
                accounts[i] = create_elyby_account(login_data)
                save_accounts(accounts)
                break
        return login_data
    except Exception:
        return None


def ensure_authlib_injector():
    """
    Скачивает (один раз, потом кешируется) authlib-injector.jar - это официально
    рекомендованный Ely.by способ показывать скины в НЕмодифицированной игре,
    без CustomSkinLoader. Подробности: https://docs.ely.by/ru/authlib-injector.html
    Возвращает путь до jar-файла или None при ошибке.
    """
    injector_dir = os.path.join(MINECRAFT_DIR, "authlib-injector")
    injector_path = os.path.join(injector_dir, "authlib-injector.jar")
    if os.path.exists(injector_path) and os.path.getsize(injector_path) > 0:
        return injector_path

    os.makedirs(injector_dir, exist_ok=True)
    try:
        api_response = requests.get(
            "https://api.github.com/repos/yushijinhun/authlib-injector/releases/latest",
            timeout=15,
        )
        api_response.raise_for_status()
        release_data = api_response.json()
        download_url = None
        for asset in release_data.get("assets", []):
            if asset.get("name", "").endswith(".jar"):
                download_url = asset.get("browser_download_url")
                break
        if not download_url:
            return None

        with requests.get(download_url, stream=True, timeout=60) as file_response:
            file_response.raise_for_status()
            with open(injector_path, "wb") as f:
                for chunk in file_response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        return injector_path
    except Exception:
        return None


def add_account(username):
    accounts = load_accounts()
    for acc in accounts:
        if acc['username'].lower() == username.lower():
            return False, "Аккаунт уже существует"
    accounts.append(create_offline_account(username))
    if save_accounts(accounts):
        return True, "Аккаунт создан"
    else:
        return False, "Ошибка сохранения"


def delete_account(username):
    accounts = load_accounts()
    for i, acc in enumerate(accounts):
        if acc['username'] == username:
            accounts.pop(i)
            save_accounts(accounts)
            return True, "Аккаунт удалён"
    return False, "Аккаунт не найден"


def load_profiles():
    if os.path.exists(PROFILES_FILE):
        try:
            with open(PROFILES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    profiles = {}
                    for item in data:
                        if isinstance(item, dict) and "id" in item:
                            profiles[item["id"]] = item
                    return profiles
                elif isinstance(data, dict):
                    return data
                else:
                    return {}
        except:
            return {}
    return {}


def save_profiles(profiles):
    os.makedirs(os.path.dirname(PROFILES_FILE), exist_ok=True)
    try:
        with open(PROFILES_FILE, 'w', encoding='utf-8') as f:
            json.dump(profiles, f, indent=2, ensure_ascii=False)
        return True
    except:
        return False


def create_profile(version_id, version_name=None, java_args="-Xmx2G -Xms512M"):
    profiles = load_profiles()
    if version_name is None:
        version_name = version_id
    if not isinstance(profiles, dict):
        profiles = {}
    profiles[version_id] = {
        "id": version_id,
        "name": version_name,
        "type": "custom",
        "gameDir": MINECRAFT_DIR,
        "lastVersionId": version_id,
        "javaArgs": java_args,
        "created": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    if save_profiles(profiles):
        return True
    return False


def delete_profile(version_id):
    profiles = load_profiles()
    if not isinstance(profiles, dict):
        return False
    if version_id in profiles:
        del profiles[version_id]
        save_profiles(profiles)
        return True
    return False


def get_available_versions(include_snapshots=False):
    try:
        versions = mll.utils.get_available_versions(MINECRAFT_DIR)
        if not include_snapshots:
            versions = [v for v in versions if "snapshot" not in v.get("type", "").lower()]
        return versions
    except:
        return []


def scan_versions():
    versions = []
    versions_dir = os.path.join(MINECRAFT_DIR, "versions")
    if not os.path.exists(versions_dir):
        return versions
    for folder in os.listdir(versions_dir):
        folder_path = os.path.join(versions_dir, folder)
        if os.path.isdir(folder_path):
            jar_file = None
            json_file = None
            for file in os.listdir(folder_path):
                if file.endswith(".jar"):
                    jar_file = file
                if file.endswith(".json"):
                    json_file = file
            if json_file or jar_file:
                version_type = "vanilla"
                folder_lower = folder.lower()
                if "fabric" in folder_lower:
                    version_type = "fabric"
                elif "forge" in folder_lower:
                    version_type = "forge"
                elif "optifine" in folder_lower or "of" in folder_lower:
                    version_type = "optifine"
                elif "snapshot" in folder_lower:
                    version_type = "snapshot"
                versions.append({
                    "id": folder,
                    "type": version_type,
                    "jar": jar_file,
                    "json": json_file,
                    "path": folder_path
                })
    return versions


def get_java_version(java_path="java"):
    try:
        result = subprocess.run([java_path, "-version"], capture_output=True, text=True)
        if result.returncode == 0:
            output = (result.stderr + result.stdout).lower()
            if "1.8" in output or '"8.' in output:
                return 8
            elif "17." in output or '"17' in output:
                return 17
            elif "21." in output or '"21' in output:
                return 21
            elif "11." in output or '"11' in output:
                return 11
    except:
        pass
    return None


def resolve_version_jar_path(version, minecraft_dir, _depth=0):
    """Находит реальный .jar для версии, следуя за 'inheritsFrom' у модифицированных
    версий (Forge/Fabric/Quilt не хранят свой jar, а используют ванильный)."""
    if _depth > 6:
        return None
    version_path = os.path.join(minecraft_dir, "versions", version)
    own_jar = os.path.join(version_path, f"{version}.jar")
    if os.path.exists(own_jar):
        return own_jar

    json_path = os.path.join(version_path, f"{version}.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            parent = data.get("inheritsFrom")
            if parent:
                return resolve_version_jar_path(parent, minecraft_dir, _depth + 1)
        except Exception:
            pass
    return None


def is_legacy_mc_version(version):
    """Версии до 1.13 используют старый формат установщика Forge (без 'inheritsFrom'
    и с патчингом классов в рантайме через FMLDeobfuscatingRemapper) — для них
    официальный .jar-установщик надёжнее, чем встроенная в minecraft_launcher_lib логика."""
    try:
        parts = version.split('.')
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
        return (major, minor) < (1, 13)
    except Exception:
        return False


def get_forge_full_version(mc_version):
    """Возвращает полный ID сборки Forge (например '1.12.2-14.23.5.2860') для версии Minecraft."""
    try:
        if hasattr(mll.forge, 'find_forge_version'):
            found = mll.forge.find_forge_version(mc_version)
            if found:
                return found
    except Exception:
        pass
    try:
        response = requests.get(
            "https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json",
            headers={"User-Agent": "67Launcher/1.5"})
        response.raise_for_status()
        promos = response.json().get("promos", {})
        build = promos.get(f"{mc_version}-recommended") or promos.get(f"{mc_version}-latest")
        if build:
            return f"{mc_version}-{build}"
    except Exception:
        pass
    return None


def get_java_for_version(minecraft_version):
    settings = load_launcher_settings()
    needs_java17 = any(x in minecraft_version for x in ["1.20", "1.21", "1.19", "1.18", "1.17"])
    target_version = 17 if needs_java17 else 8
    manual_java = settings.get("java_path", "")
    if manual_java and os.path.exists(manual_java):
        ver = get_java_version(manual_java)
        if ver == target_version:
            return manual_java
    try:
        result = subprocess.run(["java", "-version"], capture_output=True, text=True)
        if result.returncode == 0:
            output = (result.stderr + result.stdout).lower()
            if target_version == 17 and ("17." in output or '"17' in output):
                return "java"
            elif target_version == 8 and ("1.8" in output or '"8.' in output):
                return "java"
    except:
        pass
    if target_version == 17:
        common_paths = [
            "C:\\Program Files\\Java\\jdk-17.0.13\\bin\\java.exe",
            "C:\\Program Files\\Java\\jdk-17.0.12\\bin\\java.exe",
            "C:\\Program Files\\Java\\jdk-17\\bin\\java.exe",
            "C:\\Program Files\\Eclipse Adoptium\\jdk-17.0.13.11-hotspot\\bin\\java.exe",
            "C:\\Program Files\\Eclipse Adoptium\\jdk-17.0.12.7-hotspot\\bin\\java.exe"
        ]
        for path in common_paths:
            if os.path.exists(path):
                ver = get_java_version(path)
                if ver == 17:
                    return path
    local_java_dir = os.path.join(MINECRAFT_DIR, f"java{target_version}")
    java_exe = os.path.join(local_java_dir, "bin", "java.exe")
    if os.path.exists(java_exe):
        ver = get_java_version(java_exe)
        if ver == target_version:
            return java_exe
    return "java"


def get_mods_folder():
    mods_path = os.path.join(MINECRAFT_DIR, "mods")
    os.makedirs(mods_path, exist_ok=True)
    return mods_path


_icon_cache = {}


def load_image_from_url(url, size=(48, 48)):
    if not url:
        return None
    cache_key = (url, size)
    if cache_key in _icon_cache:
        return _icon_cache[cache_key]
    try:
        response = requests.get(url, timeout=10, headers={"User-Agent": "67Launcher/1.5"})
        response.raise_for_status()
        img = Image.open(BytesIO(response.content)).convert("RGBA")
        ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=size)
        _icon_cache[cache_key] = ctk_img
        return ctk_img
    except Exception as e:
        print(f"⚠️ Ошибка загрузки иконки: {e}")
        return None


def search_mods(query, game_version, mod_loader, limit=20):
    params = {
        "query": query,
        "limit": limit,
        "facets": f'[["versions:{game_version}"],["categories:{mod_loader}"]]'
    }
    try:
        response = requests.get("https://api.modrinth.com/v2/search", params=params,
                                headers={"User-Agent": "67Launcher/1.5"})
        response.raise_for_status()
        return response.json().get("hits", [])
    except:
        return []


def install_mod(project_id, game_version, mod_loader):
    try:
        params = {"game_versions": f'["{game_version}"]', "loaders": f'["{mod_loader}"]'}
        response = requests.get(f"https://api.modrinth.com/v2/project/{project_id}/version",
                                params=params, headers={"User-Agent": "67Launcher/1.5"})
        response.raise_for_status()
        versions = response.json()
        if not versions:
            return False, "Нет совместимых версий"
        mod_file = versions[0].get('files', [])[0]
        download_url = mod_file.get('url')
        filename = mod_file.get('filename')
        if not download_url:
            return False, "Нет ссылки для скачивания"
        filepath = os.path.join(get_mods_folder(), filename)
        response = requests.get(download_url, stream=True)
        response.raise_for_status()
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return True, filename
    except Exception as e:
        return False, str(e)


def list_mods():
    mods_folder = get_mods_folder()
    return [f for f in os.listdir(mods_folder) if f.endswith('.jar')]


def identify_mod_by_hash(filepath):
    try:
        sha1 = hashlib.sha1()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha1.update(chunk)
        file_hash = sha1.hexdigest()

        response = requests.get(f"https://api.modrinth.com/v2/version_file/{file_hash}",
                                params={"algorithm": "sha1"},
                                headers={"User-Agent": "67Launcher/1.5"})
        if response.status_code != 200:
            return None
        version_data = response.json()
        project_id = version_data.get('project_id')
        if not project_id:
            return None

        project_response = requests.get(f"https://api.modrinth.com/v2/project/{project_id}",
                                        headers={"User-Agent": "67Launcher/1.5"})
        project_response.raise_for_status()
        project = project_response.json()
        return {
            "title": project.get('title', 'Без названия'),
            "description": project.get('description', 'Описание отсутствует'),
            "downloads": project.get('downloads', 0),
            "follows": project.get('followers', 0),
            "categories": project.get('categories', []),
            "icon_url": project.get('icon_url'),
            "slug": project.get('slug', project_id),
        }
    except Exception:
        return None


def get_resourcepacks_folder():
    packs_path = os.path.join(MINECRAFT_DIR, "resourcepacks")
    os.makedirs(packs_path, exist_ok=True)
    return packs_path


def search_resourcepacks(query, game_version, limit=20):
    params = {
        "query": query,
        "limit": limit,
        "facets": f'[["project_type:resourcepack"],["versions:{game_version}"]]'
    }
    try:
        response = requests.get("https://api.modrinth.com/v2/search", params=params,
                                headers={"User-Agent": "67Launcher/1.5"})
        response.raise_for_status()
        return response.json().get("hits", [])
    except:
        return []


def install_resourcepack_web(project_id, game_version):
    try:
        params = {"game_versions": f'["{game_version}"]'}
        response = requests.get(f"https://api.modrinth.com/v2/project/{project_id}/version",
                                params=params, headers={"User-Agent": "67Launcher/1.5"})
        response.raise_for_status()
        versions = response.json()
        if not versions:
            return False, "Нет совместимых версий"
        pack_file = versions[0].get('files', [])[0]
        download_url = pack_file.get('url')
        filename = pack_file.get('filename')
        if not download_url:
            return False, "Нет ссылки для скачивания"
        filepath = os.path.join(get_resourcepacks_folder(), filename)
        response = requests.get(download_url, stream=True)
        response.raise_for_status()
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return True, filename
    except Exception as e:
        return False, str(e)


def delete_mod(mod_name):
    filepath = os.path.join(get_mods_folder(), mod_name)
    if os.path.exists(filepath):
        os.remove(filepath)
        return True
    return False


def get_skins_folder():
    skins_path = os.path.join(MINECRAFT_DIR, "skins")
    os.makedirs(skins_path, exist_ok=True)
    return skins_path


_install_progress_callback = None
_install_progress_state = {"current": 0, "max": 1, "download_count": 0}


def set_install_progress_callback(callback):
    global _install_progress_callback
    _install_progress_callback = callback


def _reset_install_progress_state():
    _install_progress_state["current"] = 0
    _install_progress_state["max"] = 1
    _install_progress_state["download_count"] = 0


def _report_install_progress():
    if _install_progress_callback:
        current = _install_progress_state["current"]
        total = _install_progress_state["max"]
        download_count = _install_progress_state["download_count"]
        percent = int((current / total) * 100) if total > 0 else 0
        percent = max(0, min(100, percent))
        try:
            _install_progress_callback(percent, current, total, download_count)
        except:
            pass


def mll_set_status(text):
    log_message(f"📌 {text}")

    if text.lower().startswith("download"):
        _install_progress_state["download_count"] += 1
        _report_install_progress()


def mll_set_progress(value):
    _install_progress_state["current"] = value
    _report_install_progress()


def mll_set_max(value):
    _install_progress_state["max"] = value if value > 0 else 1
    _report_install_progress()


mll_callback = {
    "setStatus": mll_set_status,
    "setProgress": mll_set_progress,
    "setMax": mll_set_max
}


class AnimatedProgressBar(ctk.CTkProgressBar):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.animating = False
        self.current_value = 0
        self.target_value = 0
        self.animation_speed = 50
        self.step = 2
        self.set(0)
        self._after_id = None

    def start_animation(self):
        if self.animating:
            return
        self.animating = True
        self.current_value = 0
        self.target_value = 100
        self._animate()

    def stop_animation(self):
        self.animating = False
        try:
            self.set(1.0)
        except:
            pass
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
                self._after_id = None
            except:
                pass

    def set_progress(self, value):
        self.target_value = min(100, max(0, value))
        if not self.animating:
            self.current_value = self.target_value
            try:
                self.set(self.current_value / 100)
            except:
                pass

    def _animate(self):
        if not self.animating:
            return
        try:
            if not self.winfo_exists():
                self.animating = False
                return
        except:
            self.animating = False
            return
        if self.current_value >= 95:
            self.step = -2
        elif self.current_value <= 5:
            self.step = 2
        self.current_value += self.step
        try:
            self.set(self.current_value / 100)
        except:
            self.animating = False
            return
        try:
            self._after_id = self.after(self.animation_speed, self._animate)
        except:
            self.animating = False
            self._after_id = None


class LoadingSpinner(ctk.CTkLabel):
    def __init__(self, master, **kwargs):
        super().__init__(master, text="", font=ctk.CTkFont(size=30), **kwargs)
        self.running = False
        self.frames = ["⏳", "⌛", "⏳", "⌛"]
        self.idx = 0
        self._after_id = None

    def start(self):
        if self.running:
            return
        self.running = True
        self.idx = 0
        self._animate()

    def _animate(self):
        if not self.running:
            return
        try:
            if not self.winfo_exists():
                self.running = False
                return
        except:
            self.running = False
            return
        self.configure(text=self.frames[self.idx % len(self.frames)])
        self.idx += 1
        try:
            self._after_id = self.after(200, self._animate)
        except:
            self.running = False
            self._after_id = None

    def stop(self):
        self.running = False
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
                self._after_id = None
            except:
                pass
        self.configure(text="✅")


class SecretGeometryDashLauncher(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("🎮 Geometry Dash")
        self.geometry("450x520")
        self.resizable(False, False)
        self.grab_set()

        self.gd_path = os.path.join(os.environ['APPDATA'], "LDASH", "gd")
        self.zip_path = os.path.join(tempfile.gettempdir(), "geometry_dash.zip")
        self.exe_path = os.path.join(self.gd_path, "GeometryDash.exe")
        self.is_installing = False

        self.create_widgets()
        self.check_installation()

        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def create_widgets(self):
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        icon_label = ctk.CTkLabel(main_frame, text="🟦", font=ctk.CTkFont(size=60))
        icon_label.pack(pady=(0, 5))

        header = ctk.CTkLabel(main_frame, text="GEOMETRY DASH",
                              font=ctk.CTkFont(size=24, weight="bold"),
                              text_color="#6d92ff")
        header.pack(pady=(0, 5))

        sub_header = ctk.CTkLabel(main_frame, text="🎮 Секретный лаунчер",
                                  font=ctk.CTkFont(size=14),
                                  text_color="#d9622f")
        sub_header.pack(pady=(0, 15))

        ctk.CTkFrame(main_frame, height=2, fg_color="#6d92ff").pack(fill="x", pady=(0, 15))

        self.status_label = ctk.CTkLabel(main_frame, text="🔍 Проверка установки...",
                                         font=ctk.CTkFont(size=14))
        self.status_label.pack(pady=(0, 5))

        self.percent_label = ctk.CTkLabel(main_frame, text="0%",
                                          font=ctk.CTkFont(size=24, weight="bold"),
                                          text_color="#d9622f")
        self.percent_label.pack(pady=(0, 5))

        self.progressbar = ctk.CTkProgressBar(main_frame, height=15, corner_radius=5,
                                              progress_color="#6d92ff")
        self.progressbar.pack(fill="x", pady=(0, 15))
        self.progressbar.set(0)

        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(pady=(10, 5))

        self.install_btn = make_sound_button(btn_frame, text="📥 Установить GD",
                                             command=self.install_geometry_dash,
                                             width=170, height=45,
                                             fg_color="#6fce7f", hover_color="#5cb56c",
                                             text_color="#16141f",
                                             font=ctk.CTkFont(size=14, weight="bold"))
        self.install_btn.grid(row=0, column=0, padx=5)

        self.launch_btn = make_sound_button(btn_frame, text="🚀 Запустить GD",
                                            command=self.launch_geometry_dash,
                                            width=170, height=45,
                                            fg_color="#6d92ff", hover_color="#5a7dd8",
                                            font=ctk.CTkFont(size=14, weight="bold"),
                                            state="disabled")
        self.launch_btn.grid(row=0, column=1, padx=5)

        update_btn = make_sound_button(main_frame, text="🔄 Обновить статус",
                                   command=self.check_installation,
                                   width=200, height=35,
                                   fg_color="#d9622f", hover_color="#c14f26",
                                   text_color="#16141f",
                                   font=ctk.CTkFont(size=13, weight="bold"))
        update_btn.pack(pady=(10, 5))

        info_label = ctk.CTkLabel(main_frame, text="📁 %APPDATA%/LDASH/gd/",
                                  font=ctk.CTkFont(size=11),
                                  text_color="#6d92ff")
        info_label.pack(pady=(10, 0))

    def check_installation(self):
        try:
            play_click()
            os.makedirs(self.gd_path, exist_ok=True)
            exe_found = False
            if os.path.exists(self.exe_path):
                exe_found = True
            else:
                for root, dirs, files in os.walk(self.gd_path):
                    for file in files:
                        if file.lower() == "geometrydash.exe":
                            self.exe_path = os.path.join(root, file)
                            exe_found = True
                            break
                    if exe_found:
                        break
            if exe_found:
                self.status_label.configure(text="✅ Geometry Dash установлен!", text_color="#6fce7f")
                self.launch_btn.configure(state="normal")
                self.install_btn.configure(text="🔄 Переустановить")
                self.progressbar.set(1.0)
                self.percent_label.configure(text="100%", text_color="#6fce7f")
                try:
                    size = self.get_folder_size(self.gd_path)
                    size_text = self.format_size(size)
                    self.status_label.configure(text=f"✅ Geometry Dash установлен! ({size_text})", text_color="#6fce7f")
                except:
                    pass
            else:
                self.status_label.configure(text="❌ Geometry Dash не установлен", text_color="#d3453f")
                self.launch_btn.configure(state="disabled")
                self.install_btn.configure(text="📥 Установить GD")
                self.progressbar.set(0)
                self.percent_label.configure(text="0%", text_color="#d9622f")
        except Exception as e:
            self.status_label.configure(text=f"❌ Ошибка: {e}", text_color="#d3453f")
            play_error()

    def format_size(self, size):
        for unit in ['Б', 'КБ', 'МБ', 'ГБ']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} ТБ"

    def get_folder_size(self, folder_path):
        total = 0
        try:
            for dirpath, dirnames, filenames in os.walk(folder_path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if os.path.exists(fp):
                        try:
                            total += os.path.getsize(fp)
                        except:
                            pass
        except:
            pass
        return total

    def update_progress(self, percent, stage="Скачивание"):
        try:
            self.progressbar.set(percent / 100)
            self.percent_label.configure(text=f"{percent}%", text_color="#d9622f")
            self.status_label.configure(text=f"⏳ {stage}... ({percent}%)", text_color="#d9622f")
            self.update_idletasks()
        except:
            pass

    def install_geometry_dash(self):
        if self.is_installing:
            return
        if os.path.exists(self.exe_path):
            if not messagebox.askyesno("Переустановка", "Geometry Dash уже установлен.\n\nПереустановить?"):
                return
        self.is_installing = True
        os.makedirs(self.gd_path, exist_ok=True)
        self.install_btn.configure(state="disabled", text="⏳ УСТАНОВКА...")
        self.launch_btn.configure(state="disabled")
        self.status_label.configure(text="⏳ Начинаем скачивание... (0%)", text_color="#d9622f")
        self.percent_label.configure(text="0%", text_color="#d9622f")
        self.progressbar.set(0)
        self.progressbar.configure(progress_color="#d9622f")
        self.update_idletasks()

        def do_install():
            try:
                url = "https://archive.org/download/GD22081/Geometry%20dash.zip"
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                response = requests.get(url, stream=True, timeout=120, headers=headers)
                response.raise_for_status()
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                block_size = 8192
                with open(self.zip_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=block_size):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                percent = int((downloaded / total_size) * 100)
                                self.after(0, lambda p=percent: self.update_progress(p, "Скачивание"))
                self.after(0, lambda: self.status_label.configure(text="📦 Распаковка...", text_color="#d9622f"))
                self.after(0, lambda: self.percent_label.configure(text="0%", text_color="#d9622f"))
                self.after(0, lambda: self.progressbar.set(0))
                with zipfile.ZipFile(self.zip_path, 'r') as zip_ref:
                    zip_ref.extractall(self.gd_path)
                try:
                    os.remove(self.zip_path)
                except:
                    pass
                self.is_installing = False
                self.after(0, self.install_finish)
            except Exception as e:
                self.is_installing = False
                error_msg = str(e)
                self.after(0, lambda: self.install_error(error_msg))

        threading.Thread(target=do_install, daemon=True).start()

    def install_finish(self):
        self.progressbar.set(1.0)
        self.progressbar.configure(progress_color="#6fce7f")
        self.percent_label.configure(text="100%", text_color="#6fce7f")
        self.status_label.configure(text="✅ Geometry Dash установлен!", text_color="#6fce7f")
        self.install_btn.configure(state="normal", text="🔄 Переустановить")
        self.launch_btn.configure(state="normal")
        play_click()
        messagebox.showinfo("Успешно!",
                            "🎮 Geometry Dash успешно установлен!\n\n📁 Папка: " + self.gd_path + "\n🚀 Нажмите 'Запустить GD' для игры!")
    def install_error(self, error):
        self.progressbar.set(0.3)
        self.progressbar.configure(progress_color="#d3453f")
        self.percent_label.configure(text="❌ Ошибка", text_color="#d3453f")
        self.status_label.configure(text="❌ Ошибка", text_color="#d3453f")
        self.install_btn.configure(state="normal", text="📥 Установить GD")
        self.launch_btn.configure(state="disabled")
        play_error()
        messagebox.showerror("Ошибка установки",
                             f"Не удалось установить Geometry Dash.\n\nОшибка: {error}\n\n💡 Попробуйте:\n1. Проверьте интернет\n2. Отключите антивирус\n3. Запустите от имени администратора")

    def launch_geometry_dash(self):
        if not os.path.exists(self.exe_path):
            for root, dirs, files in os.walk(self.gd_path):
                for file in files:
                    if file.lower() == "geometrydash.exe":
                        self.exe_path = os.path.join(root, file)
                        break
                if os.path.exists(self.exe_path):
                    break
            if not os.path.exists(self.exe_path):
                play_error()
                messagebox.showerror("Ошибка", "GeometryDash.exe куда-то потерялся\n\nПосмотри тут:\n" + self.gd_path)
                return
        try:
            self.status_label.configure(text="🚀 Запуск...", text_color="#d9622f")
            self.launch_btn.configure(state="disabled")
            self.update_idletasks()
            exe_dir = os.path.dirname(self.exe_path)
            subprocess.Popen([self.exe_path], cwd=exe_dir)
            self.status_label.configure(text="✅ Запущен!", text_color="#6fce7f")
            self.launch_btn.configure(state="normal")
            play_click()
        except Exception as e:
            self.status_label.configure(text="❌ Ошибка запуска", text_color="#d3453f")
            self.launch_btn.configure(state="normal")
            play_error()
            messagebox.showerror("Ошибка", f"Не запустилось:\n{e}")


class ChatWindow(ctk.CTkToplevel):
    def __init__(self, master, mode="server", room=""):
        super().__init__(master)
        self.master = master
        self.mode = mode
        self.role = "streamer" if mode == "server" else "viewer"
        self.room = room
        self.running = True
        self.connected = False
        self.client_socket = None
        self.username = "Игрок"
        self.message_history = []
        self.is_minimized = False
        self.unread_count = 0

        self.title("💬 Чат 67Launcher")

        saved_size = "800x850"
        try:
            saved_size = safe_window_geometry(master.settings.get("chat_window_size", "800x850"), default="800x850")
        except:
            pass
        self.geometry(saved_size)
        self.minsize(650, 500)
        self.resizable(True, True)
        self.grab_set()

        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

        self.bind("<Unmap>", self.on_minimize)
        self.bind("<Map>", self.on_restore)

        try:
            if hasattr(master, 'account_combo'):
                self.username = master.account_combo.get()
                if self.username == "Нет аккаунтов" or not self.username:
                    self.username = "Игрок"
        except:
            pass

        self.create_widgets()
        self.log(f"🔍 Инициализация чата в режиме: {mode} (комната «{self.room}»)")

        threading.Thread(target=self.run_diagnostics, daemon=True).start()

        threading.Thread(target=self.run_relay, daemon=True).start()

    def run_diagnostics(self):
        self.log("━" * 50)
        self.log("🔧 ДИАГНОСТИКА СЕТИ:")
        try:
            socket.gethostbyname('google.com')
            self.log("✅ Интернет соединение: Есть")
        except:
            self.log("❌ Интернет соединение: Нет")
        self.log(f"🌐 Релей: {RELAY_URL}")
        self.log(f"🚪 Комната: {self.room}")
        self.log("━" * 50)

    def on_minimize(self, event):
        self.is_minimized = True
        self.unread_count = 0

    def on_restore(self, event):
        self.is_minimized = False
        self.unread_count = 0
        self.update_title()

    def update_title(self):
        if self.unread_count > 0:
            self.title(f"💬 Чат 67Launcher ({self.unread_count} новых)")
        else:
            self.title("💬 Чат 67Launcher")
    def show_notification(self, message, sender=""):
        if threading.current_thread() is not threading.main_thread():
            try:
                self.after(0, lambda: self.show_notification(message, sender))
            except:
                pass
            return
        if self.is_minimized:
            self.unread_count += 1
            self.update_title()
        try:
            notif = tk.Toplevel(self)
            notif.title("")
            notif.overrideredirect(True)
            notif.attributes('-topmost', True)

            width, height = 380, 120

            if sys.platform == "win32":
                try:
                    import ctypes
                    ctypes.windll.user32.SetProcessDPIAware()
                    screen_width = ctypes.windll.user32.GetSystemMetrics(0)
                    screen_height = ctypes.windll.user32.GetSystemMetrics(1)
                except:
                    screen_width = notif.winfo_screenwidth()
                    screen_height = notif.winfo_screenheight()
            else:
                screen_width = notif.winfo_screenwidth()
                screen_height = notif.winfo_screenheight()

            x = screen_width - width - 20
            y = screen_height - height - 60

            if x < 0: x = 10
            if y < 0: y = 10

            notif.geometry(f"{width}x{height}+{x}+{y}")
            notif.update_idletasks()

            notif.configure(bg="#100e1a")

            frame = tk.Frame(notif, bg="#100e1a", highlightbackground="#302c46", highlightthickness=1)
            frame.pack(fill="both", expand=True, padx=2, pady=2)
            header_frame = tk.Frame(frame, bg="#100e1a")
            header_frame.pack(fill="x", padx=15, pady=(10, 5))

            title_color = "#6d92ff"
            if sender:
                try:
                    from __main__ import load_accounts
                    accounts = load_accounts()
                    for acc in accounts:
                        if acc["username"] == sender and acc.get("type") == "microsoft":
                            title_color = "#FFD700"
                            break
                except:
                    try:
                        accounts = load_accounts()
                        for acc in accounts:
                            if acc["username"] == sender and acc.get("type") == "microsoft":
                                title_color = "#FFD700"
                                break
                    except:
                        pass

            title_text = f"💬 {sender}" if sender else "💬 Новое сообщение"

            tk.Label(header_frame, text=title_text, font=("Segoe UI", 12, "bold"),
                     bg="#100e1a", fg=title_color).pack(side="left")

            close_btn = tk.Button(header_frame, text="✕", command=notif.destroy,
                                  bg="#100e1a", fg="#e5e2f0", activebackground="#d3453f",
                                  activeforeground="#e5e2f0", relief="flat", bd=0,
                                  font=("Segoe UI", 10), cursor="hand2")
            close_btn.pack(side="right")
            msg_text = message[:80] + "..." if len(message) > 80 else message
            tk.Label(frame, text=msg_text, font=("Segoe UI", 11), bg="#100e1a", fg="#e5e2f0",
                     wraplength=350, justify="left").pack(padx=15, pady=(5, 10), anchor="w")

            notif.after(5000, notif.destroy)
            notif.attributes('-alpha', 0.0)

            def fade_in(alpha=0.0):
                if alpha <= 1.0:
                    try:
                        notif.attributes('-alpha', alpha)
                        notif.after(50, lambda: fade_in(alpha + 0.1))
                    except:
                        pass

            fade_in()
        except Exception as e:
            print(f"Ошибка уведомления: {e}")

    def copy_ip_to_clipboard(self, ip):
        try:
            self.clipboard_clear()
            self.clipboard_append(ip)
            play_click()
            messagebox.showinfo("Скопировано", f"Скопировано в буфер обмена:\n{ip}")
        except:
            play_error()
            messagebox.showerror("Ошибка", "Не скопировалось")

    def open_emoji_picker(self):
        EmojiPicker(self, self.insert_emoji)

    def insert_emoji(self, emoji):
        self.message_entry.insert("insert", emoji)
        self.message_entry.focus()

    def create_widgets(self):
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        header_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 15))

        left_header = ctk.CTkFrame(header_frame, fg_color="transparent")
        left_header.pack(side="left")

        mode_text = "🖥️ Хост комнаты" if self.mode == "server" else "💻 Гость"
        mode_color = "#6fce7f" if self.mode == "server" else "#6d92ff"
        ctk.CTkLabel(left_header, text=f"{mode_text} - {self.username}",
                     font=ctk.CTkFont(size=22, weight="bold"), text_color=mode_color).pack(side="left")

        right_header = ctk.CTkFrame(header_frame, fg_color="transparent")
        right_header.pack(side="right")

        self.status_label = ctk.CTkLabel(right_header, text="🔴 Ожидание",
                                         font=ctk.CTkFont(size=14, weight="bold"),
                                         text_color="#d3453f")
        self.status_label.pack(side="left")

        self.msg_count_label = ctk.CTkLabel(right_header, text="",
                                            font=ctk.CTkFont(size=12),
                                            text_color="#6d92ff")
        self.msg_count_label.pack(side="left", padx=(10, 0))

        ctk.CTkFrame(main_frame, height=2, fg_color="#6d92ff").pack(fill="x", pady=(0, 10))

        self.chat_display = ctk.CTkTextbox(main_frame, font=ctk.CTkFont(family="Consolas", size=14), height=350)
        self.chat_display.pack(fill="both", expand=True, pady=(0, 10))
        self.chat_display.insert("1.0", "💬 Чат готов к работе...\n")
        self.chat_display.insert("end", "━" * 50 + "\n")
        self.chat_display.configure(state="disabled")
        self.chat_display.tag_config("gold_chat_nick", foreground="#FFD700")

        info_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        info_frame.pack(fill="x", pady=(0, 10))

        if self.mode == "server":
            self.connection_info_label = ctk.CTkLabel(info_frame, text=f"🔗 Комната: {self.room}",
                                                      font=ctk.CTkFont(size=13), text_color="#6d92ff")
            self.connection_info_label.pack(side="left")
            self.connection_status_label = ctk.CTkLabel(info_frame, text=f"👤 Ожидание подключения...",
                                                        font=ctk.CTkFont(size=13), text_color="#d9622f")
            self.connection_status_label.pack(side="right")
        else:
            ctk.CTkLabel(info_frame, text=f"🚪 Комната: {self.room}",
                         font=ctk.CTkFont(size=13), text_color="#6d92ff").pack(side="left")
            ctk.CTkLabel(info_frame, text=f"👤 {self.username}",
                         font=ctk.CTkFont(size=13), text_color="#6fce7f").pack(side="right")

        ip_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        ip_frame.pack(fill="x", pady=(5, 10))

        room_text = f"🚪 Код комнаты: {self.room}   |   🌐 Релей: {RELAY_URL}"
        ctk.CTkLabel(ip_frame, text=room_text,
                     font=ctk.CTkFont(size=12), text_color="#d9622f").pack(side="left")
        copy_btn = make_sound_button(ip_frame, text="📋 Копировать код",
                                     command=lambda: self.copy_ip_to_clipboard(self.room),
                                     width=150, height=30,
                                     fg_color="#6d92ff", hover_color="#5a7dd8",
                                     font=ctk.CTkFont(size=11))
        copy_btn.pack(side="right")

        input_container = ctk.CTkFrame(main_frame, fg_color="transparent")
        input_container.pack(fill="x")

        format_frame = ctk.CTkFrame(input_container, fg_color="transparent")
        format_frame.pack(fill="x", pady=(0, 5))

        emoji_btn = make_sound_button(format_frame, text="😊",
                                      command=self.open_emoji_picker,
                                      width=40, height=30,
                                      fg_color="#d9622f", hover_color="#c14f26",
                                      text_color="#16141f",
                                      font=ctk.CTkFont(size=16))
        emoji_btn.pack(side="left", padx=2)

        input_frame = ctk.CTkFrame(input_container, fg_color="transparent")
        input_frame.pack(fill="x")

        self.message_entry = ctk.CTkEntry(input_frame, placeholder_text="Чё пишем...",
                                          height=50, font=ctk.CTkFont(size=15))
        self.message_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.message_entry.bind("<Return>", lambda e: self.send_message())

        self.send_btn = make_sound_button(input_frame, text="📤 Отправить",
                                          command=self.send_message,
                                          width=130, height=50,
                                          fg_color="#6d92ff", hover_color="#5a7dd8",
                                          font=ctk.CTkFont(size=15, weight="bold"))
        self.send_btn.pack(side="right")
        self.send_btn.configure(state="disabled")

        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(10, 0))

        clear_btn = make_sound_button(btn_frame, text="🗑️ Очистить чат",
                                      command=self.clear_chat,
                                      fg_color="#d9622f", hover_color="#c14f26",
                                      text_color="#16141f", height=35,
                                      font=ctk.CTkFont(size=12))
        clear_btn.pack(side="left", padx=(0, 10))

        export_btn = make_sound_button(btn_frame, text="💾 Экспорт",
                                       command=self.export_chat,
                                       fg_color="#6d92ff", hover_color="#5a7dd8",
                                       height=35,
                                       font=ctk.CTkFont(size=12))
        export_btn.pack(side="left", padx=(0, 10))

        if self.mode == "client":
            reconnect_btn = make_sound_button(btn_frame, text="🔄 Переподключиться",
                                              command=self.reconnect,
                                              fg_color="#6fce7f", hover_color="#5cb56c",
                                              text_color="#16141f", height=35,
                                              font=ctk.CTkFont(size=12))
            reconnect_btn.pack(side="left", padx=(0, 10))

        close_btn = make_sound_button(btn_frame, text="❌ Закрыть чат",
                                      command=self.on_close,
                                      fg_color="#d3453f", hover_color="#b83530",
                                      height=35,
                                      font=ctk.CTkFont(size=12))
        close_btn.pack(side="right")

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def clear_chat(self):
        if messagebox.askyesno("Очистка чата", "Очистить все сообщения?"):
            self.chat_display.configure(state="normal")
            self.chat_display.delete("1.0", "end")
            self.chat_display.insert("1.0", "💬 Чат очищен\n")
            self.chat_display.insert("end", "━" * 50 + "\n")
            self.chat_display.configure(state="disabled")
            self.message_history = []
            self.update_msg_count()
            self.log("🗑️ Чат очищен")

    def export_chat(self):
        if not self.message_history:
            play_error()
            messagebox.showinfo("Информация", "Экспортировать нечего, чат пустой")
            return
        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")],
                title="Сохранить чат"
            )
            if not file_path:
                return
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"Чат 67Launcher\n")
                f.write(f"Режим: {'Сервер' if self.mode == 'server' else 'Клиент'}\n")
                f.write(f"Пользователь: {self.username}\n")
                f.write(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("━" * 50 + "\n\n")
                for msg in self.message_history:
                    f.write(msg + "\n")
            play_click()
            messagebox.showinfo("Успешно", f"Сохранил чат сюда:\n{file_path}")
        except Exception as e:
            play_error()
            messagebox.showerror("Ошибка", f"Чат не сохранился:\n{e}")

    def update_msg_count(self):
        count = len(self.message_history)
        if count > 0:
            self.msg_count_label.configure(text=f"📨 {count}")
        else:
            self.msg_count_label.configure(text="")

    def log(self, message):
        if threading.current_thread() is not threading.main_thread():
            try:
                self.after(0, lambda: self.log(message))
            except:
                pass
            return
        try:
            if not self.winfo_exists():
                return
            self.chat_display.configure(state="normal")
            timestamp = datetime.now().strftime("%H:%M:%S")

            start_index = self.chat_display.index("end-1c")

            clean_message = message.lstrip("💬 📤 📨 🔔 ")

            is_licensed_msg = False
            target_nick = ""

            if ": " in clean_message:
                possible_nick = clean_message.split(": ", 1)[0]
                try:
                    from __main__ import load_accounts
                    accounts = load_accounts()
                    for acc in accounts:
                        if acc["username"] == possible_nick and acc.get("type") == "microsoft":
                            is_licensed_msg = True
                            target_nick = possible_nick
                            break
                except:
                    try:
                        accounts = load_accounts()
                        for acc in accounts:
                            if acc["username"] == possible_nick and acc.get("type") == "microsoft":
                                is_licensed_msg = True
                                target_nick = possible_nick
                                break
                    except:
                        pass

            full_text = f"[{timestamp}] {message}\n"
            self.chat_display.insert("end", full_text)

            if is_licensed_msg and target_nick:
                current_line = start_index.split('.')[0]
                line_content = self.chat_display.get(f"{current_line}.0", f"{current_line}.end")
                nick_start_offset = line_content.find(target_nick)

                if nick_start_offset != -1:
                    nick_start_idx = f"{current_line}.{nick_start_offset}"
                    nick_end_idx = f"{current_line}.{nick_start_offset + len(target_nick)}"
                    self.chat_display.tag_add("gold_chat_nick", nick_start_idx, nick_end_idx)

            self.chat_display.see("end")
            self.chat_display.configure(state="disabled")
        except Exception as e:
            print(f"Ошибка логирования в чате: {e}")

    def safe_update_widget(self, widget, **kwargs):

        if threading.current_thread() is not threading.main_thread():
            try:
                self.after(0, lambda: self.safe_update_widget(widget, **kwargs))
            except:
                pass
            return True
        try:
            if widget and widget.winfo_exists():
                widget.configure(**kwargs)
                return True
        except:
            pass
        return False

    def run_relay(self):
        role_text = "хостом (стример)" if self.role == "streamer" else "гостем (зритель)"
        try:
            self.log(f"🌐 Подключаюсь к релею {RELAY_URL}...")
            self.log(f"🚪 Комната: {self.room}, роль: {role_text}")
            self.client_socket = ws_client.create_connection(RELAY_URL, timeout=15)
            self.client_socket.settimeout(0.5)
            hello = json.dumps({"room": self.room, "role": self.role})
            self.client_socket.send(hello)
            self.connected = True
            self.safe_update_widget(self.status_label, text="🟢 Онлайн", text_color="#6fce7f")
            self.safe_update_widget(self.send_btn, state="normal")
            if hasattr(self, 'connection_status_label'):
                self.safe_update_widget(
                    self.connection_status_label,
                    text=f"👤 В комнате «{self.room}», ждём собеседника...",
                    text_color="#6fce7f"
                )
            self.log(f"✅ Подключено к релею! Комната: {self.room}")
            self.after(300, lambda: self.send_message_raw(f"👤 {self.username} присоединился к комнате!"))
            threading.Thread(target=self.receive_messages_thread, daemon=True).start()
        except Exception as e:
            self.log(f"❌ Не удалось подключиться к релею: {e}")
            self.log("💡 ПРОВЕРЬТЕ:")
            self.log("  1. Есть интернет?")
            self.log("  2. Релей-сервер сейчас работает (не уснул на бесплатном хостинге)?")
            self.log("  3. Код комнаты совпадает у обоих игроков?")
            self.connected = False

    def reconnect(self):
        if self.mode != "client":
            return
        if self.connected:
            self.disconnect()
        self.log("🔄 Попытка переподключения...")

        threading.Thread(target=self.run_relay, daemon=True).start()

    def receive_messages_thread(self):
        while self.running and self.connected:
            try:
                if self.client_socket is None:
                    break
                try:
                    message = self.client_socket.recv()
                    if not message:
                        self.log("⚠️ Соединение с релеем закрыто")
                        self.after(0, self.disconnect)
                        break
                    if isinstance(message, bytes):
                        try:
                            message = message.decode('utf-8')
                        except UnicodeDecodeError:
                            continue
                    if message.startswith("SKIN:"):
                        try:
                            _, username, b64_data = message.split(":", 2)
                            self.receive_skin_file(username, b64_data)
                        except Exception as e:
                            self.log(f"❌ Битые данные скина: {e}")
                    else:
                        self.display_message(message)
                except ws_client.WebSocketTimeoutException:
                    continue
                except ws_client.WebSocketConnectionClosedException:
                    if self.running:
                        self.log("⚠️ Соединение с релеем разорвано")
                        self.after(0, self.disconnect)
                    break
            except Exception as e:
                if self.running:
                    self.log(f"❌ Ошибка в потоке: {e}")
                    self.after(0, self.disconnect)
                break
            time.sleep(0.01)

    def display_message(self, message):
        try:
            if not message.startswith("👤"):
                self.message_history.append(message)
                self.update_msg_count()
                self.log(f"💬 {message}")

                if ": " in message:
                    sender, text = message.split(": ", 1)
                else:
                    sender, text = "", message

                self.show_notification(text, sender)
            else:
                self.log(f"🔔 {message}")
        except:
            pass

    def send_message(self):
        if not self.connected or self.client_socket is None:
            self.log("⚠️ Нет подключения к чату")
            return
        message = self.message_entry.get().strip()
        if not message:
            return
        full_message = f"{self.username}: {message}"
        self.send_message_raw(full_message)
        self.message_entry.delete(0, 'end')

    def send_message_raw(self, message):
        try:
            if self.client_socket and self.connected:
                self.client_socket.send(message)
                if not message.startswith("👤"):
                    self.message_history.append(message)
                    self.update_msg_count()
                    self.log(f"📤 {message}")

        except Exception as e:
            self.log(f"❌ Ошибка отправки: {e}")
            self.disconnect()

    def send_skin_file(self, username, file_path):
        if not self.client_socket or not self.connected:
            return False
        try:
            with open(file_path, 'rb') as f:
                raw = f.read()
            if len(raw) > 5 * 1024 * 1024:
                self.log("❌ Скин слишком большой для отправки (>5 МБ)")
                return False
            b64 = base64.b64encode(raw).decode('ascii')
            payload = f"SKIN:{username}:{b64}"
            self.client_socket.send(payload)
            self.log(f"📤 Отправил скин для ника '{username}' собеседнику")
            return True
        except Exception as e:
            self.log(f"❌ Не удалось отправить скин: {e}")
            return False

    def receive_skin_file(self, username, b64_data):
        try:
            raw = base64.b64decode(b64_data)
            skins_local_path = os.path.join(MINECRAFT_DIR, "CustomSkinLoader", "LocalSkin")
            os.makedirs(skins_local_path, exist_ok=True)
            skin_path = os.path.join(skins_local_path, f"{username}.png")
            with open(skin_path, 'wb') as f:
                f.write(raw)
            self.log(f"🎨 Получил скин для ника '{username}' — сохранил локально")
            self.show_notification(f"Прислал(а) скин для ника «{username}»", "🎨 Скин")
        except Exception as e:
            self.log(f"❌ Не удалось сохранить присланный скин: {e}")

    def update_status(self):
        if self.connected and self.client_socket:
            self.safe_update_widget(self.status_label, text="🟢 Онлайн", text_color="#6fce7f")
        else:
            self.safe_update_widget(self.status_label, text="🔴 Офлайн", text_color="#d3453f")

    def disconnect(self):
        if self.connected:
            self.connected = False
            self.safe_update_widget(self.send_btn, state="disabled")
            self.update_status()
            self.log("🔴 Отключено от чата")
            try:
                if self.client_socket:
                    self.client_socket.close()
                    self.client_socket = None
            except:
                pass

    def on_close(self):
        self.running = False
        self.disconnect()
        try:
            if getattr(self.master, 'active_chat_window', None) is self:
                self.master.active_chat_window = None
        except:
            pass

        try:
            raw_size = f"{self.winfo_width()}x{self.winfo_height()}"
            size = safe_window_geometry(raw_size, default=None)
            if size:
                self.master.settings["chat_window_size"] = size
                save_launcher_settings(self.master.settings)
        except:
            pass
        self.destroy()
        play_click()


class EmojiPicker(ctk.CTkToplevel):
    def __init__(self, master, callback):
        super().__init__(master)
        self.callback = callback
        self.title("😊 Выберите эмодзи")
        self.geometry("500x400")
        self.resizable(False, False)
        self.grab_set()

        emojis = [
            "😊", "😂", "😍", "🤔", "😎", "🔥", "💀", "🎉", "💪", "👋",
            "❤️", "🧡", "💛", "💚", "💙", "💜", "🖤", "🤍", "🤎", "💔",
            "✅", "❌", "⚠️", "💯", "✨", "⭐", "🌟", "🌙", "☀️", "⚡",
            "🐱", "🐶", "🐺", "🐉", "🦄", "🐬", "🦋", "🐞", "🌺", "🌸",
            "⚔️", "🛡️", "🏹", "🧙", "🧚", "🧛", "🧝", "🧟", "🐉", "🏰",
            "🎮", "🕹️", "🎯", "🎲", "🎳", "🏆", "🥇", "🥈", "🥉", "🎖️",
            "👍", "👎", "👊", "✊", "🤝", "🙏", "💅", "👀", "👄", "💋"
        ]

        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        scroll_frame = ctk.CTkScrollableFrame(main_frame, fg_color="transparent")
        scroll_frame.pack(fill="both", expand=True)

        row = 0
        col = 0
        for emoji in emojis:
            btn = make_sound_button(scroll_frame, text=emoji, width=50, height=50,
                                font=ctk.CTkFont(size=20),
                                fg_color="transparent", hover_color="#201d30",
                                command=lambda e=emoji: self.select_emoji(e))
            btn.grid(row=row, column=col, padx=5, pady=5)
            col += 1
            if col >= 10:
                col = 0
                row += 1

        close_btn = make_sound_button(main_frame, text="❌ Закрыть",
                                      command=self.destroy,
                                      fg_color="#d3453f", hover_color="#b83530",
                                      height=35)
        close_btn.pack(pady=(10, 0))

    def select_emoji(self, emoji):
        if self.callback:
            self.callback(emoji)
        self.destroy()


class GameConsoleWindow(ctk.CTkToplevel):

    def __init__(self, master, title="🎮 Консоль игры"):
        super().__init__(master)
        self.title(title)
        self.geometry("900x600")
        self.minsize(500, 300)

        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        header = ctk.CTkFrame(main_frame, fg_color="transparent")
        header.pack(fill="x", pady=(0, 5))
        ctk.CTkLabel(header, text="🎮 Логи запущенной игры", font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
        clear_btn = make_sound_button(header, text="🗑️ Очистить", command=self.clear, height=28, width=90,
                                      fg_color="#d3453f", hover_color="#b83530", font=ctk.CTkFont(size=11))
        clear_btn.pack(side="right")

        self.text = ctk.CTkTextbox(main_frame, font=ctk.CTkFont(family="Consolas", size=11))
        self.text.pack(fill="both", expand=True)
        self.text.insert("1.0", "Ожидание вывода от процесса игры...\n")

    def log(self, message):
        if threading.current_thread() is not threading.main_thread():
            try:
                self.after(0, lambda: self.log(message))
            except:
                pass
            return
        try:
            if not self.winfo_exists():
                return
            timestamp = time.strftime("%H:%M:%S")
            self.text.insert("end", f"[{timestamp}] {message}\n")
            self.text.see("end")
        except:
            pass

    def clear(self):
        try:
            self.text.delete("1.0", "end")
        except:
            pass


class LauncherApp(ctk.CTk):
    instance = None

    def __init__(self):
        global MINECRAFT_DIR, GAME_DIR, ACCOUNTS_FILE, PROFILES_FILE, LAUNCHER_PROFILES_FILE

        super().__init__()
        LauncherApp.instance = self

        self.settings = load_launcher_settings()
        self.stats = load_stats()
        self._secret_launcher = None
        self.game_console = None
        self.active_chat_window = None

        theme = self.settings.get("theme", "dark")
        ctk.set_appearance_mode("Dark" if theme == "dark" else "Light")

        launch_count = self.settings.get("launch_count", 0) + 1

        if launch_count >= 5:
            launch_count = 0
            self.settings["support_shown_5"] = False
            save_launcher_settings(self.settings)
            self.after(100, self.show_support_dialog)

        self.settings["launch_count"] = launch_count
        save_launcher_settings(self.settings)

        GAME_DIR = self.settings.get("game_dir", DEFAULT_GAME_DIR)
        MINECRAFT_DIR = GAME_DIR

        ACCOUNTS_FILE = os.path.join(MINECRAFT_DIR, "accounts.json")
        PROFILES_FILE = os.path.join(MINECRAFT_DIR, "profile.json")
        LAUNCHER_PROFILES_FILE = os.path.join(MINECRAFT_DIR, "launcher_profiles.json")

        self.title("67Launcher - МЯУ")

        window_width = 1200
        window_height = 950
        self.minsize(1000, 800)

        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        x = (screen_width // 2) - (window_width // 2)
        y = (screen_height // 2) - (window_height // 2)

        self.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        set_log_callback(self.log)
        set_install_progress_callback(self.update_install_progress_real)

        self.search_results = []
        self.selected_mod_index = -1
        self.mod_cards = []
        self.is_launching = False
        self.installed_versions = []
        self.selected_installer_path = None
        self.install_cancelled = False
        self._closing = False
        self.minecraft_process = None
        self.launch_success = False
        self.timer_running = False
        self.timer_seconds = 0
        self.available_versions = []
        self.available_versions_full = []

        ensure_game_folder_structure()

        self.create_widgets()
        self.refresh_accounts()
        self.refresh_accounts_listbox()
        self.refresh_mods_list()
        self.scan_and_update_versions()

        threading.Thread(target=self.load_available_versions, daemon=True).start()
        self.refresh_resourcepacks()
        self.refresh_skins()

        self.restore_last_selection()

        self.log(f"📁 Папка игры: {MINECRAFT_DIR}")
        self.log(f"📊 Запусков игры: {self.stats.get('launches', 0)}")

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.start_idle_timer()

    def update_combo_text_color(self, selected_username=None):
        if not selected_username:
            selected_username = self.account_combo.get()

        accounts = load_accounts()
        account_type = "offline"
        for acc in accounts:
            if acc["username"] == selected_username:
                account_type = acc.get("type", "offline")
                break

        if account_type == "microsoft":
            self.account_combo.configure(text_color="#FFD700")
        else:
            self.account_combo.configure(text_color=["#221f30", "#e5e2f0"])

        golden_enabled = self.settings.get("golden_theme_enabled", True)
        set_golden_button_theme(account_type == "microsoft" and golden_enabled)

    def apply_theme(self):
        theme = self.settings.get("theme", "dark")
        ctk.set_appearance_mode("Dark" if theme == "dark" else "Light")

    def toggle_theme(self):
        is_dark = self.theme_switch.get() == 1
        theme = "dark" if is_dark else "light"
        self.settings["theme"] = theme
        save_launcher_settings(self.settings)
        ctk.set_appearance_mode("Dark" if theme == "dark" else "Light")
        self.apply_widget_theme()
        self.refresh_accounts()
        play_click()
        self.log(f"🎨 Тема оформления: {'тёмная' if theme == 'dark' else 'светлая'} (сохранено)")

    def toggle_golden_theme_setting(self):
        enabled = self.golden_theme_switch.get() == 1
        self.settings["golden_theme_enabled"] = enabled
        save_launcher_settings(self.settings)
        play_click()
        self.update_combo_text_color()
        self.log(f"🔶 Золотая тема лицензионных аккаунтов: {'включена' if enabled else 'выключена'} (сохранено)")

    def get_theme_colors(self):
        if self.settings.get("theme", "dark") == "light":
            return {
                "listbox_bg": "#ffffff",
                "listbox_fg": "#221f30",
                "listbox_select": "#6d92ff",
                "card_bg": "#f6f5fb",
                "card_bg_selected": "#e2dff2",
            }
        return {
            "listbox_bg": "#100e1a",
            "listbox_fg": "#e5e2f0",
            "listbox_select": "#6d92ff",
            "card_bg": "#201d30",
            "card_bg_selected": "#2b2840",
        }

    def register_themed_widget(self, widget):
        if not hasattr(self, 'themed_widgets'):
            self.themed_widgets = []
        self.themed_widgets.append(widget)

    def apply_widget_theme(self):
        colors = self.get_theme_colors()
        for widget in getattr(self, 'themed_widgets', []):
            try:
                if isinstance(widget, tk.Listbox):
                    widget.configure(bg=colors["listbox_bg"], fg=colors["listbox_fg"],
                                     selectbackground=colors["listbox_select"])
                elif isinstance(widget, tk.Text):
                    widget.configure(bg=colors["listbox_bg"], fg=colors["listbox_fg"])
            except:
                pass
        try:
            if hasattr(self, 'mod_desc_card'):
                self.mod_desc_card.configure(fg_color=colors["card_bg"])
        except:
            pass
        for i, card in enumerate(getattr(self, 'mod_cards', [])):
            try:
                is_selected = (i == self.selected_mod_index)
                card.configure(fg_color=colors["card_bg_selected"] if is_selected else colors["card_bg"])
            except:
                pass
        try:
            if hasattr(self, 'rp_desc_card'):
                self.rp_desc_card.configure(fg_color=colors["card_bg"])
        except:
            pass
        for i, card in enumerate(getattr(self, 'rp_cards', [])):
            try:
                is_selected = (i == getattr(self, 'selected_rp_index', -1))
                card.configure(fg_color=colors["card_bg_selected"] if is_selected else colors["card_bg"])
            except:
                pass

    def format_time(self, seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        if hours > 0:
            return f"{hours}ч {minutes}м {secs}с"
        elif minutes > 0:
            return f"{minutes}м {secs}с"
        else:
            return f"{secs}с"

    def format_date(self, date_str):
        if not date_str:
            return "Никогда"
        try:
            dt = datetime.fromisoformat(date_str)
            return dt.strftime("%d.%m.%Y %H:%M")
        except:
            return date_str

    def format_size(self, size):
        for unit in ['Б', 'КБ', 'МБ', 'ГБ']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} ТБ"

    def get_folder_size(self, folder_path):
        total = 0
        try:
            for dirpath, dirnames, filenames in os.walk(folder_path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if os.path.exists(fp):
                        total += os.path.getsize(fp)
        except:
            pass
        return total

    def start_idle_timer(self):
        self.after(1000, self.update_stats_display)

    def update_stats_display(self):
        stats = load_stats()
        self.stats = stats
        launches = stats.get("launches", 0)
        play_time = stats.get("total_play_time", 0)
        last_launch = stats.get("last_launch", "Никогда")
        if last_launch and last_launch != "Никогда":
            try:
                dt = datetime.fromisoformat(last_launch)
                last_launch = dt.strftime("%d.%m.%Y %H:%M:%S")
            except:
                pass
        history = stats.get("launch_history", [])
        history_text = ""
        if history:
            history_text = "\n".join(
                [f"  • {h.get('time', '')[:16]} - {h.get('version', 'unknown')}" for h in history[-10:]])
        stats_text = f"""
📊 СТАТИСТИКА:

🚀 Всего запусков игры: {launches}
⏱ Общее время игры: {self.format_time(play_time)}
🕐 Последний запуск: {last_launch}

📋 Последние запуски:
{history_text if history_text else "  Нет записей"}

📊 Запусков лаунчера: {self.settings.get('launch_count', 0)}
"""
        self.stats_text.delete("1.0", "end")
        self.stats_text.insert("1.0", stats_text)

    def update_info_display(self):
        stats = load_stats()
        self.stats = stats
        self.update_stats_display()

    def update_subtitle(self):
        launches = self.stats.get("launches", 0)
        play_time = self.stats.get("total_play_time", 0)
        self.title(f"67Launcher - МЯУ | Запусков: {launches} | Время: {self.format_time(play_time)}")

    def restore_last_selection(self):
        last_account = self.settings.get("last_account", "")
        last_version = self.settings.get("last_version", "")
        if last_account:
            try:
                self.account_combo.set(last_account)
            except:
                pass
        if last_version:
            try:
                self.version_combo.set(last_version)
            except:
                pass
        self.update_combo_text_color()

    def save_current_selection(self):
        self.settings["last_account"] = self.account_combo.get()
        self.settings["last_version"] = self.version_combo.get()
        save_launcher_settings(self.settings)

    def load_available_versions(self):
        try:
            self.log("🔄 Загрузка списка версий...")
            versions = mll.utils.get_available_versions(MINECRAFT_DIR)

            self.available_versions_full = [
                {"id": v["id"], "type": v.get("type", "release")} for v in versions
            ]
            self.available_versions = [v["id"] for v in self.available_versions_full if v["type"] != "snapshot"]
            self.log(f"✅ Загружено {len(self.available_versions_full)} версий "
                     f"(релизов: {len(self.available_versions)})")
        except Exception as e:
            self.log(f"❌ Ошибка загрузки версий: {e}")
            self.available_versions_full = []
            self.available_versions = []
        try:
            self.after(0, self.filter_install_versions)
        except:
            pass

    def scan_and_update_versions(self):
        installed = []
        versions_dir = os.path.join(MINECRAFT_DIR, "versions")
        if os.path.exists(versions_dir):
            for folder in os.listdir(versions_dir):
                if os.path.isdir(os.path.join(versions_dir, folder)):
                    installed.append(folder)
        self.installed_versions = installed
        self.update_version_combo()

    def update_version_combo(self):
        versions = self.installed_versions
        if not versions:
            versions = ["Нет версий"]
        self.version_combo.configure(values=versions)
        if versions and versions[0] != "Нет версий":
            last_version = self.settings.get("last_version", "")
            if last_version in versions:
                self.version_combo.set(last_version)
            else:
                self.version_combo.set(versions[0])

    def select_optifine_file(self):
        file_path = filedialog.askopenfilename(
            title="Выберите установщик OptiFine (.jar)",
            filetypes=[("JAR файлы", "*.jar"), ("Все файлы", "*.*")]
        )
        if file_path:
            if file_path.lower().endswith('.exe'):
                play_error()
                messagebox.showwarning("Ошибка", "OptiFine ставится только из .jar — экзешник сюда не годится")
                return
            self.selected_installer_path = file_path
            self.install_file_label.configure(text=f"✅ Файл выбран: {os.path.basename(file_path)}",
                                              text_color="#6fce7f")
            self.log(f"📂 Выбран файл OptiFine: {file_path}")
            play_click()

    def show_download_panel(self, show=True):
        try:
            if hasattr(self, 'download_panel'):
                if show:
                    self.download_panel.grid()
                else:
                    self.download_panel.grid_remove()
        except:
            pass

    def update_install_progress_real(self, percent, current=0, total=0, download_count=0):
        def _update():
            try:
                if hasattr(self, 'install_progressbar'):
                    self.install_progressbar.animating = False
                    self.install_progressbar.set_progress(percent)
                if hasattr(self, 'install_status_label'):
                    if total > 1:

                        text = f"⏳ Обработано: {current} из {total} ({percent}%) · реально скачано: {download_count}"
                    elif download_count > 0:
                        text = f"⏳ Скачивание файлов... (реально скачано: {download_count})"
                    else:
                        text = "⏳ Подготовка..."
                    self.install_status_label.configure(text=text, text_color="#d9622f")
            except:
                pass

        try:
            self.after(0, _update)
        except:
            pass

    def download_with_progress(self, url, filepath, description="Скачивание"):
        try:
            self.after(0, lambda: self.show_download_panel(True))
            self.log(f"📥 {description}...")
            if hasattr(self, 'download_spinner'):
                self.download_spinner.start()
            if hasattr(self, 'download_status_label'):
                self.download_status_label.configure(text=f"⏳ {description}...", text_color="#d9622f")
            if hasattr(self, 'download_progressbar'):
                self.download_progressbar.start_animation()
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            block_size = 8192
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=block_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = int((downloaded / total_size) * 100)
                            if hasattr(self, 'download_progressbar'):
                                self.download_progressbar.set_progress(percent)
                            if percent % 10 == 0:
                                self.log(f"📊 {description}: {percent}%")
            if hasattr(self, 'download_progressbar'):
                self.download_progressbar.stop_animation()
                self.download_progressbar.set(1.0)
                self.download_progressbar.configure(progress_color="#6fce7f")
            if hasattr(self, 'download_spinner'):
                self.download_spinner.stop()
            if hasattr(self, 'download_status_label'):
                self.download_status_label.configure(text=f"✅ {description} завершено!", text_color="#6fce7f")
            self.log(f"✅ {description} завершено!")
            self.after(2000, lambda: self.show_download_panel(False))
            return True
        except Exception as e:
            self.log(f"❌ Ошибка скачивания: {e}")
            if hasattr(self, 'download_spinner'):
                self.download_spinner.stop()
            if hasattr(self, 'download_status_label'):
                self.download_status_label.configure(text=f"❌ Ошибка: {e}", text_color="#d3453f")
            if hasattr(self, 'download_progressbar'):
                self.download_progressbar.stop_animation()
                self.download_progressbar.set(0.3)
                self.download_progressbar.configure(progress_color="#d3453f")
            self.after(3000, lambda: self.show_download_panel(False))
            play_error()
            return False

    def toggle_game_logs(self):
        enabled = bool(self.game_logs_switch.get())
        self.settings["show_game_logs"] = enabled
        save_launcher_settings(self.settings)
        self.log(f"🎮 Логи игры: {'включены' if enabled else 'выключены'}")

    def save_ms_settings(self):
        self.settings["ms_client_id"] = self.ms_client_id_entry.get().strip() or DEFAULT_MS_CLIENT_ID
        self.settings["ms_redirect_uri"] = self.ms_redirect_entry.get().strip()
        save_launcher_settings(self.settings)
        play_click()
        self.log("🔷 Настройки Microsoft-входа сохранены")
        messagebox.showinfo("Готово", "Настройки Microsoft-входа сохранены")

    def show_first_launch_server_dialog(self):
        server_ip = "smpametist.aternos.me"
        dialog = ctk.CTkToplevel(self)
        dialog.title("🎮 С почином!")
        dialog.geometry("480x340")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.transient(self)

        dialog.update_idletasks()
        width = dialog.winfo_width()
        height = dialog.winfo_height()
        x = (dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (dialog.winfo_screenheight() // 2) - (height // 2)
        dialog.geometry(f"{width}x{height}+{x}+{y}")

        main_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=25, pady=25)

        ctk.CTkLabel(main_frame, text="🎉", font=ctk.CTkFont(size=50)).pack(pady=(0, 5))
        ctk.CTkLabel(main_frame, text="ЭТО НЕ МОЙ СЕРВАК!!!", font=ctk.CTkFont(size=20, weight="bold"),
                     text_color="#6d92ff").pack(pady=(0, 5))
        ctk.CTkLabel(main_frame, text="Заходи серв там бесплатный кит старт!!!:", font=ctk.CTkFont(size=13),
                     text_color="#a8a4bd").pack(pady=(0, 10))

        ip_frame = ctk.CTkFrame(main_frame, fg_color="#100e1a", corner_radius=8)
        ip_frame.pack(fill="x", pady=(0, 15))
        ip_label = ctk.CTkLabel(ip_frame, text=server_ip, font=ctk.CTkFont(size=17, weight="bold"),
                                text_color="#6fce7f")
        ip_label.pack(pady=12)

        def copy_server_ip():
            try:
                self.clipboard_clear()
                self.clipboard_append(server_ip)
                play_click()
                copy_btn.configure(text="✅ Скопировано")
                dialog.after(1500, lambda: copy_btn.configure(text="📋 Копировать IP"))
            except Exception as e:
                play_error()
                messagebox.showerror("Ошибка", f"IP не скопировался:\n{e}")

        copy_btn = make_sound_button(main_frame, text="📋 Копировать IP", command=copy_server_ip,
                                     fg_color="#6d92ff", hover_color="#5a7dd8", height=42,
                                     font=ctk.CTkFont(size=14, weight="bold"))
        copy_btn.pack(fill="x", pady=(0, 10))

        close_btn = make_sound_button(main_frame, text="Погнали", command=dialog.destroy,
                                      fg_color="#2b2840", hover_color="#3d3a52", height=36)
        close_btn.pack(fill="x")

    def show_support_dialog(self):
        if self.settings.get("support_shown_5", False):
            return
        self.settings["support_shown_5"] = True
        save_launcher_settings(self.settings)
        dialog = ctk.CTkToplevel(self)
        dialog.title("PLEASE")
        dialog.geometry("500x480")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.transient(self)

        main_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(main_frame, text="🌟", font=ctk.CTkFont(size=70)).pack(pady=(10, 5))
        ctk.CTkLabel(main_frame, text="FOR MEEE", font=ctk.CTkFont(size=22, weight="bold"), text_color="#6d92ff").pack(
            pady=(0, 5))

        msg = """Нравится 67Launcher?
💝 Хоть 50 рублей на пропитание))))

😼 скебоб"""
        ctk.CTkLabel(main_frame, text=msg, font=ctk.CTkFont(size=14), justify="center", wraplength=420).pack(
            pady=(0, 20))

        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(pady=(10, 5))

        donate_btn = make_sound_button(btn_frame, text="💝 Поддержать",
                                       command=lambda: webbrowser.open("https://www.donationalerts.com/r/ionux"),
                                       width=170, height=50, fg_color="#d9622f", hover_color="#c14f26",
                                       font=ctk.CTkFont(size=15, weight="bold"))
        donate_btn.grid(row=0, column=0, padx=10, pady=5)

        close_btn = make_sound_button(btn_frame, text="Не, жалко", command=dialog.destroy,
                                      width=120, height=35, fg_color="#d3453f", hover_color="#b83530",
                                      font=ctk.CTkFont(size=13))
        close_btn.grid(row=0, column=1, padx=10, pady=5)

    def add_elyby_account_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("🟢 Вход через Ely.by")
        dialog.geometry("420x320")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.transient(self)

        main_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(main_frame, text="🟢 Вход через Ely.by", font=ctk.CTkFont(size=18, weight="bold"),
                     text_color="#6fce7f").pack(pady=(0, 10))
        ctk.CTkLabel(main_frame,
                     text="Ник или e-mail, и пароль от ely.by. Если у тебя уже\n"
                          "залит свой скин на сайте ely.by — он появится в игре\n"
                          "БЕЗ модов, authlib-injector сам его подставит.",
                     font=ctk.CTkFont(size=11), text_color="#a8a4bd", justify="left").pack(pady=(0, 10))

        login_entry = ctk.CTkEntry(main_frame, placeholder_text="Ник или e-mail", height=35)
        login_entry.pack(fill="x", pady=(0, 8))
        password_entry = ctk.CTkEntry(main_frame, placeholder_text="Пароль", show="•", height=35)
        password_entry.pack(fill="x", pady=(0, 8))
        totp_entry = ctk.CTkEntry(main_frame, placeholder_text="Код 2FA (если включена)", height=35)
        totp_entry.pack(fill="x", pady=(0, 8))

        status_label = ctk.CTkLabel(main_frame, text="", font=ctk.CTkFont(size=12), wraplength=360, justify="left")
        status_label.pack(pady=(0, 8))

        def do_submit():
            login = login_entry.get().strip()
            password = password_entry.get()
            totp = totp_entry.get().strip()
            if not login or not password:
                play_error()
                status_label.configure(text="Заполни ник/e-mail и пароль", text_color="#d3453f")
                return

            final_password = f"{password}:{totp}" if totp else password
            status_label.configure(text="⏳ Вход...", text_color="#d9622f")
            dialog.update_idletasks()

            def worker():
                success, result = elyby_authenticate(login, final_password)
                self.after(0, lambda: on_result(success, result))

            threading.Thread(target=worker, daemon=True).start()

        def on_result(success, result):
            if not success:
                play_error()
                if "two factor" in str(result).lower():
                    status_label.configure(
                        text="Включена двухфакторная аутентификация — впиши код из приложения "
                             "в поле '2FA' и нажми ещё раз", text_color="#d3453f")
                else:
                    status_label.configure(text=f"Не вошёл: {result}", text_color="#d3453f")
                return

            ok, msg = add_elyby_account(result)
            if ok:
                self.refresh_accounts()
                self.refresh_accounts_listbox()
                play_click()
                dialog.destroy()
                messagebox.showinfo("Готово", f"Залогинен как {result['name']} через Ely.by")
            else:
                play_error()
                status_label.configure(text=msg, text_color="#d3453f")

        make_sound_button(main_frame, text="✅ Войти", command=do_submit,
                          fg_color="#6fce7f", hover_color="#5cb56c", text_color="#16141f", height=40).pack(
            fill="x", pady=(4, 8))

        make_sound_button(main_frame, text="🌐 Открыть ely.by (регистрация / загрузка скина)",
                          command=lambda: webbrowser.open("https://ely.by/skins"),
                          fg_color="#2b2840", hover_color="#3d3a52", height=32).pack(fill="x")

    def open_mods_folder(self):
        mods_path = os.path.join(MINECRAFT_DIR, "mods")
        os.makedirs(mods_path, exist_ok=True)
        os.startfile(mods_path)
        self.log(f"📂 Открыта папка mods")
        play_click()

    def refresh_accounts(self):
        accounts = load_accounts()
        usernames = [acc['username'] for acc in accounts]
        if not usernames:
            usernames = ["Нет аккаунтов"]
        self.account_combo.configure(values=usernames)
        if usernames and usernames[0] != "Нет аккаунтов":
            self.account_combo.set(usernames[0])

        try:
            dropdown_menu = self.account_combo._dropdown_menu
            if dropdown_menu and usernames != ["Нет аккаунтов"]:
                for index, username in enumerate(usernames):
                    is_microsoft = False
                    for acc in accounts:
                        if acc["username"] == username and acc.get("type") == "microsoft":
                            is_microsoft = True
                            break

                    if is_microsoft:
                        dropdown_menu.entryconfigure(index, foreground="#FFD700")
                    else:
                        default_fg = "#221f30" if self.settings.get("theme", "dark") == "light" else "#e5e2f0"
                        dropdown_menu.entryconfigure(index, foreground=default_fg)
        except Exception as e:
            print(f"Не удалось перекрасить пункты выпадающего меню: {e}")

        if hasattr(self, 'update_combo_text_color'):
            self.update_combo_text_color()

    def on_account_listbox_click(self, event):
        try:
            index = self.accounts_listbox.index(f"@{event.x},{event.y}")
            line_num = int(index.split(".")[0])
        except Exception:
            return "break"

        line_idx = line_num - 1
        if line_idx < 0 or line_idx >= len(self._accounts_order):
            return "break"

        self._selected_account_username = self._accounts_order[line_idx]
        self._highlight_account_line(line_num)
        play_click()
        return "break"

    def _highlight_account_line(self, line_num):
        try:
            self.accounts_listbox.tag_remove("selected_account", "1.0", "end")
            self.accounts_listbox.tag_add("selected_account", f"{line_num}.0", f"{line_num}.end+1c")
        except Exception:
            pass

    def refresh_accounts_listbox(self):
        accounts = load_accounts()
        self.accounts_listbox.delete("1.0", "end")
        self._accounts_order = []
        if not accounts:
            self.accounts_listbox.insert("1.0", "Нет аккаунтов")
            self._selected_account_username = None
            return

        for acc in accounts:
            created = acc.get('created', 'неизвестно')
            acc_type = acc.get("type")

            if acc_type == "microsoft":
                icon, label = "🔷", "лицензионный"
                start_pos = self.accounts_listbox.index("end-1c")
                self.accounts_listbox.insert("end", f"{icon} {acc['username']}  ({label}, создан: {created})\n")
                end_pos = self.accounts_listbox.index("end-1c")
                self.accounts_listbox.tag_add("gold_account", start_pos, end_pos)
            else:
                if acc_type == "elyby":
                    icon, label = "🟢", "Ely.by"
                else:
                    icon, label = "👤", "оффлайн"
                self.accounts_listbox.insert("end", f"{icon} {acc['username']}  ({label}, создан: {created})\n")

            self._accounts_order.append(acc['username'])

        if self._selected_account_username in self._accounts_order:
            line_num = self._accounts_order.index(self._selected_account_username) + 1
            self._highlight_account_line(line_num)
        else:
            self._selected_account_username = None

    def add_account_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Добавление аккаунта")
        dialog.geometry("350x180")
        dialog.grab_set()
        ctk.CTkLabel(dialog, text="Как назовём?", font=ctk.CTkFont(size=13)).pack(pady=(20, 5))
        entry = ctk.CTkEntry(dialog, width=280, height=35)
        entry.pack(pady=(5, 10))

        def confirm():
            username = entry.get().strip()
            if not username:
                play_error()
                messagebox.showwarning("Ошибка", "Имя пустым быть не может — придумай хоть что-нибудь")
                return
            success, msg = add_account(username)
            if success:
                self.refresh_accounts()
                self.refresh_accounts_listbox()
                dialog.destroy()
                play_click()
                messagebox.showinfo("Успешно", msg)
            else:
                play_error()
                messagebox.showerror("Ошибка", msg)

        make_sound_button(dialog, text="Добавить", command=confirm,
                          fg_color="#6fce7f", hover_color="#5cb56c", text_color="#16141f").pack(pady=10)

    def add_microsoft_account_dialog(self):
        client_id = self.settings.get("ms_client_id", "").strip() or DEFAULT_MS_CLIENT_ID

        redirect_uri = self.settings.get(
            "ms_redirect_uri", "https://login.microsoftonline.com/common/oauth2/nativeclient"
        ).strip()

        try:
            login_url, state, code_verifier = mll.microsoft_account.get_secure_login_data(client_id, redirect_uri)
        except Exception as e:
            play_error()
            messagebox.showerror("Ошибка", f"Не получилось построить ссылку входа:\n{e}")
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("🔷 Вход через Microsoft")
        dialog.geometry("420x170")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.transient(self)

        main_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(main_frame, text="🔷 Вход через Microsoft", font=ctk.CTkFont(size=18, weight="bold"),
                     text_color="#6d92ff").pack(pady=(0, 10))
        status_label = ctk.CTkLabel(main_frame, text="⏳ Открываю окно входа...",
                                     font=ctk.CTkFont(size=12), text_color="#a8a4bd", wraplength=360, justify="left")
        status_label.pack(pady=(0, 10))

        def set_status(text, color="#a8a4bd"):
            def _apply():
                try:
                    if dialog.winfo_exists():
                        status_label.configure(text=text, text_color=color)
                except Exception:
                    pass
            self.after(0, _apply)

        def do_login(auth_code):
            try:
                login_data = mll.microsoft_account.complete_login(
                    client_id, None, redirect_uri, auth_code, code_verifier
                )
                self.after(0, lambda: login_success(login_data))
            except Exception as e:
                self.after(0, lambda: login_failed(str(e)))

        def login_success(login_data):
            success, msg = add_microsoft_account(login_data)
            if success:
                self.refresh_accounts()
                self.refresh_accounts_listbox()
                play_click()
                try:
                    dialog.destroy()
                except Exception:
                    pass
                messagebox.showinfo("Готово", f"Залогинен как {login_data['name']} — можно играть")
            else:
                play_error()
                set_status(msg, "#d3453f")

        def login_failed(err):
            play_error()
            if "AzureAppNotPermitted" in err:
                set_status(
                    "Твоему Azure-приложению не дали доступ к API Minecraft — "
                    "нужно подать заявку в форме Microsoft", "#d3453f"
                )
            else:
                set_status(f"Не залогинился: {err}", "#d3453f")

        def run_embedded_login():
            try:
                import webview
            except ImportError:
                play_error()
                messagebox.showerror(
                    "Нужен pywebview",
                    "Для встроенного окна входа нужен пакет pywebview.\n"
                    "Установи его командой:\npip install pywebview"
                )
                try:
                    dialog.destroy()
                except Exception:
                    pass
                return

            result_queue = multiprocessing.Queue()
            proc = multiprocessing.Process(
                target=_ms_login_webview_process,
                args=(login_url, redirect_uri, result_queue),
                daemon=True,
            )
            proc.start()

            def poll_result():
                try:
                    if not dialog.winfo_exists():
                        return
                except Exception:
                    return

                if not result_queue.empty():
                    result = result_queue.get()
                    code = result.get("code")
                    error = result.get("error")

                    if code:
                        set_status("⏳ Получение токена...", "#d9622f")
                        threading.Thread(target=do_login, args=(code,), daemon=True).start()
                    elif error and error.startswith("import_error"):
                        play_error()
                        messagebox.showerror(
                            "Нужен pywebview",
                            "Для встроенного окна входа нужен пакет pywebview.\n"
                            "Установи его командой:\npip install pywebview"
                        )
                        try:
                            dialog.destroy()
                        except Exception:
                            pass
                    elif error:
                        play_error()
                        set_status(f"Вход не завершён: {error}", "#d3453f")
                    else:
                        play_error()
                        set_status("Окно входа закрыто без логина", "#d3453f")
                    return

                if proc.is_alive():
                    self.after(200, poll_result)
                else:
                    play_error()
                    set_status("Окно входа закрыто без логина", "#d3453f")

            self.after(200, poll_result)

        run_embedded_login()

    def delete_selected_account(self):
        if not self._accounts_order:
            play_error()
            messagebox.showwarning("Ошибка", "Удалять нечего, аккаунтов нет")
            return
        if not self._selected_account_username:
            play_error()
            messagebox.showwarning("Ошибка", "Сначала кликни по аккаунту в списке, который хочешь удалить")
            return

        username = self._selected_account_username
        if messagebox.askyesno("Подтверждение", f"Удалить аккаунт '{username}'?"):
            success, msg = delete_account(username)
            if success:
                self._selected_account_username = None
                self.refresh_accounts()
                self.refresh_accounts_listbox()
                play_click()
                messagebox.showinfo("Успешно", msg)
            else:
                play_error()
                messagebox.showerror("Ошибка", msg)

    def refresh_mods_list(self):
        self.installed_listbox.delete(0, "end")
        mods = list_mods()
        if not mods:
            self.installed_listbox.insert("end", "📭 Моды не установлены")
            return
        for mod in mods:
            self.installed_listbox.insert("end", f"📦 {mod}")

    def delete_selected_mod(self):
        selection = self.installed_listbox.curselection()
        if not selection:
            play_error()
            messagebox.showwarning("Ошибка", "Сначала ткни в мод, который хочешь удалить")
            return
        mod_name = self.installed_listbox.get(selection[0])
        if "Моды не установлены" in mod_name:
            return
        mod_name = mod_name.replace("📦 ", "").strip()
        if messagebox.askyesno("Подтверждение", f"Удалить мод '{mod_name}'?"):
            if delete_mod(mod_name):
                self.refresh_mods_list()
                play_click()
                messagebox.showinfo("Успешно", "Готово, мода больше нет")
            else:
                play_error()
                messagebox.showerror("Ошибка", "Мод не удалился, что-то пошло не так")

    def read_pack_meta(self, pack_path):
        info = {"description": "Без описания", "pack_format": "неизвестно"}
        try:
            import zipfile
            meta_content = None
            if pack_path.endswith('.zip'):
                with zipfile.ZipFile(pack_path, 'r') as zip_ref:
                    if 'pack.mcmeta' in zip_ref.namelist():
                        meta_content = zip_ref.read('pack.mcmeta').decode('utf-8')
            elif os.path.isdir(pack_path):
                meta_path = os.path.join(pack_path, 'pack.mcmeta')
                if os.path.exists(meta_path):
                    with open(meta_path, 'r', encoding='utf-8') as f:
                        meta_content = f.read()
            if meta_content:
                data = json.loads(meta_content)
                pack_data = data.get('pack', {})
                if 'description' in pack_data:
                    info['description'] = pack_data['description']
                if 'pack_format' in pack_data:
                    info['pack_format'] = str(pack_data['pack_format'])
        except:
            pass
        return info

    def list_resourcepacks(self):
        packs_path = os.path.join(MINECRAFT_DIR, "resourcepacks")
        packs = []
        if os.path.exists(packs_path):
            for item in os.listdir(packs_path):
                item_path = os.path.join(packs_path, item)
                if os.path.isdir(item_path) or item.endswith('.zip'):
                    pack_info = {
                        "name": item,
                        "path": item_path,
                        "size": self.format_size(
                            os.path.getsize(item_path) if os.path.isfile(item_path) else self.get_folder_size(
                                item_path)),
                        "description": "Без описания",
                        "pack_format": "неизвестно"
                    }
                    pack_info.update(self.read_pack_meta(item_path))
                    packs.append(pack_info)
        return sorted(packs, key=lambda x: x['name'].lower())

    def refresh_resourcepacks(self):
        packs = self.list_resourcepacks()
        self.installed_rp_packs = packs
        self.resourcepacks_listbox.delete(0, "end")
        if not packs:
            self.resourcepacks_listbox.insert("end", "📭 Ресурспаки не установлены")
            return
        for pack in packs:
            info = f"📦 {pack['name']}"
            if pack['description'] != "Без описания":
                info += f" - {pack['description']}"
            info += f" ({pack['size']})"
            self.resourcepacks_listbox.insert("end", info)

    def install_resourcepack(self):
        file_path = filedialog.askopenfilename(
            title="Выберите ресурспак (.zip или папка)",
            filetypes=[("ZIP архивы", "*.zip"), ("Все файлы", "*.*")]
        )
        if not file_path:
            return
        packs_path = os.path.join(MINECRAFT_DIR, "resourcepacks")
        os.makedirs(packs_path, exist_ok=True)
        filename = os.path.basename(file_path)
        dest_path = os.path.join(packs_path, filename)
        try:
            if file_path.endswith('.zip'):
                shutil.copy2(file_path, dest_path)
            else:
                shutil.copytree(file_path, dest_path, dirs_exist_ok=True)
            self.log(f"✅ Ресурспак установлен: {filename}")
            play_click()
            messagebox.showinfo("Успешно", f"Ресурспак '{filename}' на месте")
            self.refresh_resourcepacks()
            return True
        except Exception as e:
            self.log(f"❌ Ошибка установки ресурспака: {e}")
            play_error()
            messagebox.showerror("Ошибка", f"Ресурспак не встал:\n{e}")
            return False

    def delete_resourcepack(self, pack_name):
        if not messagebox.askyesno("Подтверждение", f"Удалить ресурспак '{pack_name}'?"):
            return False
        packs_path = os.path.join(MINECRAFT_DIR, "resourcepacks")
        pack_path = os.path.join(packs_path, pack_name)
        try:
            if os.path.isdir(pack_path):
                shutil.rmtree(pack_path)
            elif os.path.isfile(pack_path):
                os.remove(pack_path)
            self.log(f"🗑️ Ресурспак удален: {pack_name}")
            play_click()
            messagebox.showinfo("Успешно", f"Ресурспак '{pack_name}' снесён")
            self.refresh_resourcepacks()
            return True
        except Exception as e:
            self.log(f"❌ Ошибка удаления ресурспака: {e}")
            play_error()
            messagebox.showerror("Ошибка", f"Не вышло удалить ресурспак:\n{e}")
            return False

    def delete_selected_resourcepack(self):
        selection = self.resourcepacks_listbox.curselection()
        if not selection:
            play_error()
            messagebox.showwarning("Ошибка", "Сначала выбери ресурспак")
            return
        selected_text = self.resourcepacks_listbox.get(selection[0])
        if "📭" in selected_text:
            return
        name = selected_text.split("📦 ")[1].split(" -")[0].strip()
        self.delete_resourcepack(name)

    def open_resourcepacks_folder(self):
        packs_path = os.path.join(MINECRAFT_DIR, "resourcepacks")
        if not os.path.exists(packs_path):
            os.makedirs(packs_path, exist_ok=True)
        os.startfile(packs_path)
        play_click()

    def get_skins_list(self):
        skins_path = get_skins_folder()
        skins = []
        if os.path.exists(skins_path):
            for file in os.listdir(skins_path):
                if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                    file_path = os.path.join(skins_path, file)
                    skins.append({
                        "name": file,
                        "path": file_path,
                        "size": self.format_size(os.path.getsize(file_path))
                    })
        return sorted(skins, key=lambda x: x['name'].lower())

    def refresh_skins(self):
        skins = self.get_skins_list()
        self.skins_listbox.delete(0, "end")
        if not skins:
            self.skins_listbox.insert("end", "📭 Скины не установлены")
            return
        for skin in skins:
            info = f"🎨 {skin['name']} ({skin['size']})"
            self.skins_listbox.insert("end", info)

    def import_skin(self):
        file_path = filedialog.askopenfilename(
            title="Выберите скин (PNG или JPG)",
            filetypes=[("PNG изображения", "*.png"), ("JPG изображения", "*.jpg"), ("Все файлы", "*.*")]
        )
        if not file_path:
            return False
        skins_path = get_skins_folder()
        filename = os.path.basename(file_path)
        dest_path = os.path.join(skins_path, filename)
        if os.path.exists(dest_path):
            if not messagebox.askyesno("Файл существует", f"Скин '{filename}' уже существует.\n\nЗаменить?"):
                return False
        try:
            shutil.copy2(file_path, dest_path)
            self.log(f"✅ Скин импортирован: {filename}")
            play_click()
            messagebox.showinfo("Успешно", f"Скин '{filename}' добавлен")
            self.refresh_skins()
            return True
        except Exception as e:
            self.log(f"❌ Ошибка импорта скина: {e}")
            play_error()
            messagebox.showerror("Ошибка", f"Скин не добавился:\n{e}")
            return False

    def delete_skin(self, skin_name):
        if not messagebox.askyesno("Подтверждение", f"Удалить скин '{skin_name}'?"):
            return False
        skins_path = get_skins_folder()
        skin_path = os.path.join(skins_path, skin_name)
        try:
            os.remove(skin_path)
            self.log(f"🗑️ Скин удален: {skin_name}")
            play_click()
            messagebox.showinfo("Успешно", f"Скин '{skin_name}' снесён")
            self.refresh_skins()
            return True
        except Exception as e:
            self.log(f"❌ Ошибка удаления скина: {e}")
            play_error()
            messagebox.showerror("Ошибка", f"Скин не удалился:\n{e}")
            return False

    def delete_selected_skin(self):
        selection = self.skins_listbox.curselection()
        if not selection:
            play_error()
            messagebox.showwarning("Ошибка", "Сначала выбери скин")
            return
        selected_text = self.skins_listbox.get(selection[0])
        if "📭" in selected_text:
            return
        name = selected_text.split("🎨 ")[1].split(" (")[0].strip()
        self.delete_skin(name)

    def preview_skin(self):
        selection = self.skins_listbox.curselection()
        if not selection:
            play_error()
            messagebox.showinfo("Информация", "Сначала выбери скин в списке слева")
            return
        selected_text = self.skins_listbox.get(selection[0])
        if "📭" in selected_text:
            play_error()
            messagebox.showinfo("Информация", "Скин не выбран — глянуть нечего")
            return
        skin_name = selected_text.split("🎨 ")[1].split(" (")[0].strip()
        skins_path = get_skins_folder()
        skin_path = os.path.join(skins_path, skin_name)
        if not os.path.exists(skin_path):
            play_error()
            messagebox.showerror("Ошибка", f"Скин '{skin_name}' куда-то делся")
            return
        try:
            image = Image.open(skin_path)
            preview_window = ctk.CTkToplevel(self)
            preview_window.title(f"Превью скина: {skin_name}")
            preview_window.geometry("400x500")
            preview_window.resizable(False, False)
            preview_window.grab_set()
            max_size = (300, 400)
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
            temp_path = os.path.join(tempfile.gettempdir(), "skin_preview.png")
            image.save(temp_path, "PNG")
            img = Image.open(temp_path)
            photo = ImageTk.PhotoImage(img)
            label = ctk.CTkLabel(preview_window, text="", image=photo)
            label.image = photo
            label.pack(pady=20, padx=20)
            info_text = f"""
📝 Название: {skin_name}
📏 Размер: {self.format_size(os.path.getsize(skin_path))}
            """
            info_label = ctk.CTkLabel(preview_window, text=info_text, font=ctk.CTkFont(size=12), justify="left")
            info_label.pack(pady=10)
            close_btn = make_sound_button(preview_window, text="Закрыть", command=preview_window.destroy, width=100,
                                          height=35)
            close_btn.pack(pady=10)

            def on_close():
                try:
                    os.remove(temp_path)
                except:
                    pass
                preview_window.destroy()

            preview_window.protocol("WM_DELETE_WINDOW", on_close)
        except Exception as e:
            play_error()
            messagebox.showerror("Ошибка", f"Скин не открылся:\n{e}")

    def open_skins_folder(self):
        skins_path = get_skins_folder()
        os.startfile(skins_path)
        self.log(f"📂 Открыта папка скинов")
        play_click()

    def show_skin_info(self, skin_name):
        skins_path = get_skins_folder()
        skin_path = os.path.join(skins_path, skin_name)
        if not os.path.exists(skin_path):
            return
        info_text = f"""
🎨 Скин: {skin_name}

📁 Путь: {skin_path}
📏 Размер: {self.format_size(os.path.getsize(skin_path))}

💡 Это просто файл в папке скинов. Чтобы скин показывался
   в игре — используй вход через Ely.by (вкладка "Аккаунты").
        """
        self.skin_info.configure(state="normal")
        self.skin_info.delete("1.0", "end")
        self.skin_info.insert("1.0", info_text)
        self.skin_info.configure(state="disabled")

    def on_skin_double_click(self, event):
        selection = self.skins_listbox.curselection()
        if not selection:
            return
        selected_text = self.skins_listbox.get(selection[0])
        if "📭" in selected_text:
            return
        name = selected_text.split("🎨 ")[1].split(" (")[0].strip()
        self.show_skin_info(name)

    def on_resourcepack_select(self, event=None):
        selection = self.resourcepacks_listbox.curselection()
        if not selection:
            return
        index = selection[0]
        if not hasattr(self, 'installed_rp_packs') or index >= len(self.installed_rp_packs):
            return
        pack = self.installed_rp_packs[index]

        self.rp_desc_title.configure(text=pack['name'])
        self.rp_desc_meta.configure(text=f"💾 {pack['size']}   🔧 Pack format: {pack['pack_format']}")

        self.rp_desc_text.configure(state="normal")
        self.rp_desc_text.delete("1.0", "end")
        self.rp_desc_text.insert("1.0", pack['description'] if pack['description'] else "Без описания")
        self.rp_desc_text.configure(state="disabled")

        self.rp_desc_icon.configure(text="📦", image=None)
        self.rp_desc_open_btn.configure(state="disabled")

    def on_resourcepack_double_click(self, event):
        selection = self.resourcepacks_listbox.curselection()
        if not selection:
            return
        selected_text = self.resourcepacks_listbox.get(selection[0])
        if "📭" in selected_text:
            return
        self.open_resourcepacks_folder()

    def create_widgets(self):
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(1, weight=1)

        top_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        top_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        top_frame.grid_columnconfigure(0, weight=1)

        title_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(title_frame, text="⚡ 67Launcher", font=ctk.CTkFont(size=28, weight="bold"),
                     text_color="#6d92ff").pack(side="left")
        launch_display = self.settings.get('launch_count', 0)
        launch_text = "обнулен" if launch_display == 0 else str(launch_display)
        self.subtitle_label = ctk.CTkLabel(title_frame, text=f"📁 {MINECRAFT_DIR} | Запуск #{launch_text}",
                                           font=ctk.CTkFont(size=11), text_color="#a8a4bd", cursor="hand2")
        self.subtitle_label.pack(side="left", padx=(10, 0))
        self.subtitle_label.bind("<Button-1>", lambda e: self.copy_game_path())

        chat_btn = make_sound_button(top_frame, text="💬 Чат", command=self.open_chat_window,
                                     width=100, height=35, fg_color="#6d92ff", hover_color="#5a7dd8",
                                     font=ctk.CTkFont(size=13, weight="bold"))
        chat_btn.grid(row=0, column=1, sticky="e", padx=(10, 0))

        self.tab_view = ctk.CTkTabview(self.main_container)
        self.tab_view.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        self.tab_view.add("🎮 Игра")
        self.tab_view.add("📦 Установка")
        self.tab_view.add("👤 Аккаунты")
        self.tab_view.add("📦 Моды")
        self.tab_view.add("🎨 Скины")
        self.tab_view.add("📦 Ресурспаки")
        self.tab_view.add("⚙️ Настройки")
        self.tab_view.add("📊 Статистика")

        self.create_game_tab()
        self.create_install_tab()
        self.create_accounts_tab()
        self.create_mods_tab()
        self.create_skins_tab()
        self.create_resourcepacks_tab()
        self.create_settings_tab()
        self.create_stats_tab()
        self.create_download_panel()
        self.create_console()

    def create_download_panel(self):
        self.download_panel = ctk.CTkFrame(self.main_container, fg_color="transparent", height=40)
        self.download_panel.grid(row=2, column=0, sticky="ew", pady=(5, 0))
        self.download_panel.grid_columnconfigure(1, weight=1)
        self.download_panel.grid_remove()
        self.download_spinner = LoadingSpinner(self.download_panel)
        self.download_spinner.grid(row=0, column=0, padx=(0, 10))
        self.download_spinner.stop()
        self.download_status_label = ctk.CTkLabel(self.download_panel, text="Готов к работе", font=ctk.CTkFont(size=12),
                                                  text_color="#6d92ff")
        self.download_status_label.grid(row=0, column=1, sticky="w")
        self.download_progressbar = AnimatedProgressBar(self.download_panel, height=10, corner_radius=5,
                                                        progress_color="#6d92ff", width=300)
        self.download_progressbar.grid(row=0, column=2, padx=(10, 0))
        self.download_progressbar.set(0)

    def create_console(self):
        console_frame = ctk.CTkFrame(self.main_container)
        console_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        console_frame.grid_columnconfigure(0, weight=1)

        header_frame = ctk.CTkFrame(console_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(5, 0))
        header_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header_frame, text="📋 Консоль", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0,
                                                                                                    sticky="w", padx=5)
        copy_btn = make_sound_button(header_frame, text="📄 Копировать", command=self.copy_console_log,
                                     fg_color="#6d92ff", hover_color="#5a7dd8", height=25, width=100,
                                     font=ctk.CTkFont(size=11))
        copy_btn.grid(row=0, column=1, padx=5)
        clear_btn = make_sound_button(header_frame, text="🗑️ Очистить", command=self.clear_console, fg_color="#d3453f",
                                      hover_color="#b83530", height=25, width=80, font=ctk.CTkFont(size=11))
        clear_btn.grid(row=0, column=2, padx=5)

        self.console_text = ctk.CTkTextbox(console_frame, font=ctk.CTkFont(family="Consolas", size=11), height=200)
        self.console_text.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 5))
        self.console_text.insert("1.0", "[00:00:00] Лаунчер запущен\n")

    def create_game_tab(self):
        tab = self.tab_view.tab("🎮 Игра")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        main_frame = ctk.CTkFrame(tab)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        main_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(main_frame, text="🎮 Запуск игры", font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0,
                                                                                                      pady=(0, 20))
        ctk.CTkLabel(main_frame, text="👤 Аккаунт:", font=ctk.CTkFont(size=14)).grid(row=1, column=0, sticky="w")
        self.account_combo = ctk.CTkComboBox(
            main_frame,
            values=["Нет аккаунтов"],
            width=300,
            height=35,
            command=self.update_combo_text_color
        )
        self.account_combo.grid(row=2, column=0, sticky="w", pady=(0, 15))
        try:
            self.account_combo._entry.bind("<KeyRelease>", lambda e: self.update_combo_text_color())
            self.account_combo._entry.bind("<FocusOut>", lambda e: self.update_combo_text_color())
        except Exception:
            pass

        ctk.CTkLabel(main_frame, text="📦 Версия:", font=ctk.CTkFont(size=14)).grid(row=3, column=0, sticky="w")
        self.version_combo = ctk.CTkComboBox(main_frame, values=["Нет версий"], width=300, height=35)
        self.version_combo.grid(row=4, column=0, sticky="w", pady=(0, 15))

        ctk.CTkLabel(main_frame, text="💾 RAM:", font=ctk.CTkFont(size=14)).grid(row=5, column=0, sticky="w")
        self.ram_var = ctk.StringVar(value="2G")
        ram_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        ram_frame.grid(row=6, column=0, sticky="w", pady=(0, 20))
        for ram in ["1G", "2G", "3G", "4G", "6G", "8G"]:
            ctk.CTkRadioButton(ram_frame, text=ram, variable=self.ram_var, value=ram).pack(side="left", padx=5)

        self.launch_status_label = ctk.CTkLabel(main_frame, text="✅ Погнали", font=ctk.CTkFont(size=13))
        self.launch_status_label.grid(row=7, column=0, sticky="w", pady=(0, 10))

        self.launch_progressbar = AnimatedProgressBar(main_frame, width=300, height=15)
        self.launch_progressbar.grid(row=8, column=0, sticky="ew", pady=(0, 15))

        self.launch_btn = make_sound_button(main_frame, text="🚀 ЗАПУСТИТЬ ИГРУ", command=self.launch_game, height=50,
                                            font=ctk.CTkFont(size=16, weight="bold"), fg_color="#7896f7",
                                            hover_color="#5f7fe0")
        self.launch_btn.grid(row=9, column=0, sticky="ew", pady=(0, 10))

        self.timer_label = ctk.CTkLabel(main_frame, text="⏱ Время игры: 0с", font=ctk.CTkFont(size=13))
        self.timer_label.grid(row=10, column=0, sticky="w")

    def create_install_tab(self):
        tab = self.tab_view.tab("📦 Установка")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        main_frame = ctk.CTkFrame(tab, fg_color="transparent")
        main_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        main_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(main_frame, text="📦 Установка клиентов", font=ctk.CTkFont(size=24, weight="bold")).grid(
            row=0, column=0, pady=(0, 12))
        ctk.CTkLabel(main_frame, text="Тип установки:", font=ctk.CTkFont(size=14)).grid(row=1, column=0, sticky="w")

        self.install_type_var = ctk.StringVar(value="vanilla")
        type_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        type_frame.grid(row=2, column=0, sticky="w", pady=(0, 8))
        types = [("🌐 Vanilla", "vanilla"), ("🧵 Fabric", "fabric"), ("🔥 Forge", "forge"), ("✨ OptiFine", "optifine")]
        for text, value in types:
            ctk.CTkRadioButton(type_frame, text=text, variable=self.install_type_var, value=value).pack(side="left",
                                                                                                        padx=10)
        version_header = ctk.CTkFrame(main_frame, fg_color="transparent")
        version_header.grid(row=3, column=0, sticky="ew", pady=(0, 4))
        version_header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(version_header, text="Версия Minecraft:", font=ctk.CTkFont(size=14)).grid(row=0, column=0,
                                                                                               sticky="w")
        self.show_snapshots_var = ctk.BooleanVar(value=False)
        snapshot_check = ctk.CTkCheckBox(version_header, text="Показывать снапшоты",
                                         variable=self.show_snapshots_var,
                                         command=self.filter_install_versions,
                                         font=ctk.CTkFont(size=12))
        snapshot_check.grid(row=0, column=1, sticky="e")

        search_row = ctk.CTkFrame(main_frame, fg_color="transparent")
        search_row.grid(row=4, column=0, sticky="ew", pady=(0, 8))
        search_row.grid_columnconfigure(0, weight=1)
        self.version_search_entry = ctk.CTkEntry(search_row, placeholder_text="Фильтр версий (например: 1.20)",
                                                 height=35)
        self.version_search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.version_search_entry.bind("<KeyRelease>", lambda e: self.filter_install_versions(e))
        refresh_versions_btn = make_sound_button(search_row, text="🔄", command=self.refresh_available_versions,
                                                 width=40, height=35, fg_color="#6d92ff", hover_color="#5a7dd8")
        refresh_versions_btn.grid(row=0, column=1)

        versions_container = ctk.CTkFrame(main_frame, fg_color="#100e1a", corner_radius=8,
                                          height=165)
        versions_container.grid(row=5, column=0, sticky="ew", pady=(0, 15))
        versions_container.grid_columnconfigure(0, weight=1)
        versions_container.grid_propagate(False)

        self.version_results_frame = ctk.CTkScrollableFrame(
            versions_container,
            fg_color="transparent",
            height=125
        )
        self.version_results_frame.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        self.version_results_frame.grid_columnconfigure(0, weight=1)
        self.version_result_widgets = []

        self.install_file_label = ctk.CTkLabel(main_frame, text="❌ Файл не выбран (только для OptiFine)",
                                               text_color="#d3453f")
        self.install_file_label.grid(row=6, column=0, sticky="w", pady=(0, 5))

        select_file_btn = make_sound_button(main_frame, text="📂 Выбрать файл OptiFine",
                                            command=self.select_optifine_file, fg_color="#d9622f",
                                            hover_color="#c14f26", text_color="#16141f")
        select_file_btn.grid(row=6, column=0, sticky="w", pady=(0, 12))

        self.install_status_label = ctk.CTkLabel(main_frame, text="", font=ctk.CTkFont(size=13))
        self.install_status_label.grid(row=8, column=0, sticky="w", pady=(0, 6))

        self.install_progressbar = AnimatedProgressBar(main_frame, width=300, height=15)
        self.install_progressbar.grid(row=9, column=0, sticky="ew", pady=(0, 12))

        self.install_btn = make_sound_button(main_frame, text="📥 УСТАНОВИТЬ", command=self.install_selected_client,
                                             height=35, font=ctk.CTkFont(size=16, weight="bold"), fg_color="#6fce7f",
                                             hover_color="#5cb56c", text_color="#16141f")
        self.install_btn.grid(row=7, column=0, sticky="ew")

        self.show_install_versions_placeholder()

    def show_install_versions_placeholder(self):
        for widget in self.version_results_frame.winfo_children():
            widget.destroy()
        ctk.CTkLabel(self.version_results_frame, text="⏳ Список версий ещё грузится...",
                     font=ctk.CTkFont(size=12), text_color="#a8a4bd").pack(pady=15)

    def refresh_available_versions(self):
        self.show_install_versions_placeholder()
        threading.Thread(target=self.load_available_versions, daemon=True).start()

    def filter_install_versions(self, event=None):
        query = self.version_search_entry.get().strip().lower()

        if query == "gd2026":
            if event and event.keysym == "Return":
                self.version_search_entry.delete(0, "end")
                self.open_secret_launcher()
                return

        for widget in self.version_results_frame.winfo_children():
            widget.destroy()
        self.version_result_widgets = []

        all_versions = getattr(self, 'available_versions_full', None)
        if not all_versions:
            self.show_install_versions_placeholder()
            return

        show_snapshots = self.show_snapshots_var.get()

        matches = []
        for v in all_versions:
            if not show_snapshots and v["type"] == "snapshot":
                continue
            if query and query not in v["id"].lower():
                continue
            matches.append(v)

        if not matches:
            ctk.CTkLabel(self.version_results_frame, text="Ничего не найдено",
                         font=ctk.CTkFont(size=12), text_color="#a8a4bd").pack(pady=15)
            return

        shown = matches[:100]
        for v in shown:
            self.create_version_result_row(v)
        if len(matches) > len(shown):
            ctk.CTkLabel(self.version_results_frame,
                         text=f"...и ещё {len(matches) - len(shown)}, уточни поиск",
                         font=ctk.CTkFont(size=11), text_color="#a8a4bd").pack(pady=(5, 0))

    def show_mod_results_placeholder(self):
        for widget in self.results_frame.winfo_children():
            widget.destroy()
        placeholder = ctk.CTkFrame(self.results_frame, fg_color="transparent")
        placeholder.pack(fill="both", expand=True, pady=40)
        ctk.CTkLabel(placeholder, text="🔍", font=ctk.CTkFont(size=36)).pack()
        ctk.CTkLabel(placeholder, text="Пиши название мода и жми «Искать»",
                     font=ctk.CTkFont(size=13), text_color="#6d92ff").pack(pady=(5, 0))

    def create_version_result_row(self, version_info):
        version_id = version_info["id"]
        version_type = version_info.get("type", "release")
        type_tag = {"release": "🌐 релиз", "snapshot": "🧪 снапшот",
                    "old_beta": "📼 бета", "old_alpha": "📼 альфа"}.get(version_type, version_type)

        row = ctk.CTkFrame(self.version_results_frame, fg_color="#201d30", corner_radius=6, cursor="hand2")
        row.pack(fill="x", padx=2, pady=2)
        row.grid_columnconfigure(0, weight=1)

        label = ctk.CTkLabel(row, text=f"{version_id}   ·   {type_tag}", font=ctk.CTkFont(size=12),
                             anchor="w", cursor="hand2")
        label.grid(row=0, column=0, sticky="w", padx=10, pady=6)

        def on_click(event=None, vid=version_id):
            self.select_install_version(vid)

        row.bind("<Button-1>", on_click)
        label.bind("<Button-1>", on_click)
        self.version_result_widgets.append((row, version_id))

    def select_install_version(self, version_id):
        self.version_search_entry.delete(0, "end")
        self.version_search_entry.insert(0, version_id)
        play_click()
        for row, vid in self.version_result_widgets:
            try:
                row.configure(fg_color="#2b2840" if vid == version_id else "#201d30")
            except:
                pass

    def create_accounts_tab(self):
        tab = self.tab_view.tab("👤 Аккаунты")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        left_frame = ctk.CTkFrame(tab)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(20, 10), pady=20)
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(left_frame, text="👤 Управление аккаунтами", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0,
                                                                                                                column=0,
                                                                                                                pady=(0,
                                                                                                                      10))

        _c = self.get_theme_colors()
        self.accounts_listbox = tk.Text(left_frame, bg=_c["listbox_bg"], fg=_c["listbox_fg"], font=("Consolas", 11),
                                        height=15,
                                        relief="flat", cursor="hand2")
        self.accounts_listbox.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        self.register_themed_widget(self.accounts_listbox)
        self.accounts_listbox.tag_configure("selected_account", background="#3d3a52", foreground="#ffffff")
        self.accounts_listbox.tag_configure("gold_account", foreground="#FFD700")
        self.accounts_listbox.bind("<Button-1>", self.on_account_listbox_click)
        self._accounts_order = []
        self._selected_account_username = None

        btn_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew")
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)

        add_btn = make_sound_button(btn_frame, text="➕ Добавить", command=self.add_account_dialog, fg_color="#6fce7f",
                                    hover_color="#5cb56c", text_color="#16141f")
        add_btn.grid(row=0, column=0, padx=5)
        delete_btn = make_sound_button(btn_frame, text="🗑️ Удалить", command=self.delete_selected_account,
                                       fg_color="#d3453f", hover_color="#b83530")
        delete_btn.grid(row=0, column=1, padx=5)

        ms_btn = make_sound_button(left_frame, text="🔷 Добавить лицензионный (Microsoft)",
                                   command=self.add_microsoft_account_dialog,
                                   fg_color="#2b2840", hover_color="#3d3a52")
        ms_btn.grid(row=3, column=0, sticky="ew", pady=(8, 0))

        elyby_btn = make_sound_button(left_frame, text="🟢 Добавить Ely.by",
                                      command=self.add_elyby_account_dialog,
                                      fg_color="#2b2840", hover_color="#3d3a52")
        elyby_btn.grid(row=4, column=0, sticky="ew", pady=(8, 0))

        right_frame = ctk.CTkFrame(tab)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 20), pady=20)
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(0, weight=1)

        ctk.CTkLabel(right_frame, text="ℹ️ Информация", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0,
                                                                                                       pady=(0, 10))
        info_text = """📌 Как это работает:

1. "Добавить" — обычный оффлайн-ник
2. "Добавить лицензионный" — вход через
   настоящий аккаунт Microsoft
3. "Добавить Ely.by" — вход через ely.by,
   скин с сайта покажется без модов

💡 Для лицензионного входа нужен свой
   Client ID — впиши его в Настройках
💡 Скин на ely.by заливается на их сайте —
   у них просто нет API для загрузки скина
💡 Аккаунты живут в папке игры"""
        ctk.CTkLabel(right_frame, text=info_text, font=ctk.CTkFont(size=13), justify="left").grid(row=1, column=0,
                                                                                                  sticky="n")

    def create_mods_tab(self):
        tab = self.tab_view.tab("📦 Моды")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        left_frame = ctk.CTkFrame(tab)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(20, 10), pady=20)
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(7, weight=1)

        ctk.CTkLabel(left_frame, text="🔍 Поиск модов", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0,
                                                                                                      pady=(0, 10))

        ctk.CTkLabel(left_frame, text="🎮 Версия Minecraft:", font=ctk.CTkFont(size=13, weight="bold")).grid(row=1,
                                                                                                            column=0,
                                                                                                            sticky="w")
        self.mod_version_entry = ctk.CTkEntry(left_frame, placeholder_text="1.20.4", height=32)
        self.mod_version_entry.insert(0, "1.20.1")
        self.mod_version_entry.grid(row=2, column=0, sticky="w", pady=(0, 5))

        ctk.CTkLabel(left_frame, text="🔧 Загрузчик:", font=ctk.CTkFont(size=13, weight="bold")).grid(row=3, column=0,
                                                                                                     sticky="w")
        self.mod_loader_var = ctk.StringVar(value="fabric")
        loader_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        loader_frame.grid(row=4, column=0, sticky="w", pady=(0, 5))
        for text, value in [("🧵 Fabric", "fabric"), ("🔥 Forge", "forge")]:
            ctk.CTkRadioButton(loader_frame, text=text, variable=self.mod_loader_var, value=value).pack(side="left",
                                                                                                        padx=5)

        self.mod_search_entry = ctk.CTkEntry(left_frame, placeholder_text="Введите название мода...", height=32)
        self.mod_search_entry.grid(row=5, column=0, sticky="ew", pady=(0, 5))
        self.mod_search_entry.bind("<Return>", lambda e: self.search_mods())

        search_btn = make_sound_button(left_frame, text="🔍 Искать", command=self.search_mods, height=32,
                                       fg_color="#6d92ff", hover_color="#5a7dd8")
        search_btn.grid(row=6, column=0, sticky="ew", pady=(0, 5))

        self.results_frame = ctk.CTkScrollableFrame(left_frame, fg_color="transparent", height=250)
        self.results_frame.grid(row=7, column=0, sticky="nsew", pady=(0, 5))
        self.results_frame.grid_columnconfigure(0, weight=1)
        self.mod_cards = []
        self.show_mod_results_placeholder()

        self.install_mod_btn = make_sound_button(left_frame, text="📥 УСТАНОВИТЬ МОД", command=self.install_selected_mod,
                                                 height=40, fg_color="#6fce7f", hover_color="#5cb56c",
                                                 text_color="#16141f", font=ctk.CTkFont(size=14, weight="bold"),
                                                 state="disabled")
        self.install_mod_btn.grid(row=8, column=0, sticky="ew", pady=(0, 5))

        self.mod_status_label = ctk.CTkLabel(left_frame, text="Пиши, что ищем, и жми 'Искать'",
                                             font=ctk.CTkFont(size=11), text_color="#6d92ff")
        self.mod_status_label.grid(row=9, column=0, sticky="w")

        right_frame = ctk.CTkFrame(tab)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 20), pady=20)
        right_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(right_frame, text="📦 Установленные моды", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0,
                                                                                                              column=0,
                                                                                                              pady=(0,
                                                                                                                    10))

        _c = self.get_theme_colors()
        self.installed_listbox = tk.Listbox(right_frame, bg=_c["listbox_bg"], fg=_c["listbox_fg"],
                                            font=("Consolas", 11), height=12,
                                            relief="flat")
        self.installed_listbox.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        self.installed_listbox.bind("<<ListboxSelect>>", self.on_installed_mod_select)
        self.register_themed_widget(self.installed_listbox)

        btn_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew")
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)

        refresh_btn = make_sound_button(btn_frame, text="🔄 Обновить", command=self.refresh_mods_list, height=35,
                                        fg_color="#6d92ff", hover_color="#5a7dd8")
        refresh_btn.grid(row=0, column=0, padx=5)

        delete_mod_btn = make_sound_button(btn_frame, text="🗑️ Удалить", command=self.delete_selected_mod, height=35,
                                           fg_color="#d3453f", hover_color="#b83530")
        delete_mod_btn.grid(row=0, column=1, padx=5)

        ctk.CTkLabel(right_frame, text="ℹ️ О выбранном моде", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=3, column=0, sticky="w", pady=(15, 5))

        self.mod_desc_card = ctk.CTkFrame(right_frame, fg_color=self.get_theme_colors()["card_bg"], corner_radius=10)
        self.mod_desc_card.grid(row=4, column=0, sticky="nsew", pady=(0, 5))
        self.mod_desc_card.grid_columnconfigure(1, weight=1)
        right_frame.grid_rowconfigure(4, weight=1)

        self.mod_desc_icon = ctk.CTkLabel(self.mod_desc_card, text="📦", font=ctk.CTkFont(size=28),
                                          width=64, height=64, fg_color="transparent")
        self.mod_desc_icon.grid(row=0, column=0, rowspan=2, padx=15, pady=15, sticky="n")

        self.mod_desc_title = ctk.CTkLabel(self.mod_desc_card, text="Тыкни в мод слева",
                                           font=ctk.CTkFont(size=16, weight="bold"), anchor="w")
        self.mod_desc_title.grid(row=0, column=1, sticky="w", padx=(0, 15), pady=(15, 0))

        self.mod_desc_meta = ctk.CTkLabel(self.mod_desc_card, text="", font=ctk.CTkFont(size=11),
                                          text_color="#6d92ff", anchor="w")
        self.mod_desc_meta.grid(row=1, column=1, sticky="w", padx=(0, 15), pady=(0, 15))

        self.mod_desc_text = ctk.CTkTextbox(self.mod_desc_card, font=ctk.CTkFont(size=13), wrap="word",
                                            fg_color="transparent", height=180)
        self.mod_desc_text.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=15, pady=(0, 15))
        self.mod_desc_text.configure(state="disabled")

        self.mod_desc_open_btn = make_sound_button(self.mod_desc_card, text="🌐 Открыть на Modrinth",
                                                   command=self.open_selected_mod_page,
                                                   fg_color="#6d92ff", hover_color="#5a7dd8",
                                                   height=32, state="disabled")
        self.mod_desc_open_btn.grid(row=3, column=0, columnspan=2, sticky="ew", padx=15, pady=(0, 15))

    def create_skins_tab(self):
        tab = self.tab_view.tab("🎨 Скины")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        header_frame = ctk.CTkFrame(tab, fg_color="transparent")
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=20, pady=(15, 10))
        ctk.CTkLabel(header_frame, text="🎨 Управление скинами", font=ctk.CTkFont(size=18, weight="bold")).pack(
            side="left")

        left_frame = ctk.CTkFrame(tab)
        left_frame.grid(row=1, column=0, sticky="nsew", padx=(20, 10), pady=(0, 10))
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(left_frame, text="📋 Установленные скины", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0,
                                                                                                              column=0,
                                                                                                              sticky="w",
                                                                                                              padx=10,
                                                                                                              pady=(0,
                                                                                                                    5))

        _c = self.get_theme_colors()
        self.skins_listbox = tk.Listbox(left_frame, bg=_c["listbox_bg"], fg=_c["listbox_fg"],
                                        selectbackground=_c["listbox_select"],
                                        font=("Consolas", 11), height=10, relief="flat")
        self.skins_listbox.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.skins_listbox.bind("<Double-Button-1>", self.on_skin_double_click)
        self.register_themed_widget(self.skins_listbox)

        btn_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)
        btn_frame.grid_columnconfigure(2, weight=1)

        import_btn = make_sound_button(btn_frame, text="📥 Добавить", command=self.import_skin, fg_color="#6fce7f",
                                       hover_color="#5cb56c", text_color="#16141f", height=35)
        import_btn.grid(row=0, column=0, padx=2)

        preview_btn = make_sound_button(btn_frame, text="👁️ Превью", command=self.preview_skin, fg_color="#6d92ff",
                                        hover_color="#5a7dd8", height=35)
        preview_btn.grid(row=0, column=1, padx=2)

        delete_btn = make_sound_button(btn_frame, text="🗑️ Удалить", command=self.delete_selected_skin,
                                       fg_color="#d3453f", hover_color="#b83530", height=35)
        delete_btn.grid(row=0, column=2, padx=2)

        elyby_frame = ctk.CTkFrame(left_frame, fg_color="#201d30", corner_radius=8)
        elyby_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(10, 0))

        ctk.CTkLabel(elyby_frame, text="🟢 Скин через Ely.by — без модов",
                     font=ctk.CTkFont(size=13, weight="bold"), text_color="#6fce7f").pack(anchor="w", padx=12,
                                                                                          pady=(10, 2))
        ctk.CTkLabel(elyby_frame,
                     text="У ely.by нет API для загрузки скина файлом — залить PNG можно\n"
                          "только на их сайте. Зато показ скина в игре не требует модов:\n"
                          "1. Залей скин на сайте (кнопка ниже).\n"
                          "2. Войди через свой Ely.by-аккаунт (вкладка «Аккаунты»).\n"
                          "3. Запусти игру этим аккаунтом — лаунчер сам подключит\n"
                          "   authlib-injector, и твой скин из ely.by появится у всех.",
                     font=ctk.CTkFont(size=11), text_color="#a8a4bd", justify="left").pack(anchor="w", padx=12)

        elyby_btn_row = ctk.CTkFrame(elyby_frame, fg_color="transparent")
        elyby_btn_row.pack(fill="x", padx=12, pady=(8, 12))
        elyby_btn_row.grid_columnconfigure(0, weight=1)
        elyby_btn_row.grid_columnconfigure(1, weight=1)

        elyby_upload_btn = make_sound_button(elyby_btn_row, text="🌐 Открыть ely.by и загрузить скин",
                                             command=lambda: webbrowser.open("https://ely.by/skins"),
                                             fg_color="#2b2840", hover_color="#3d3a52", height=32)
        elyby_upload_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        elyby_login_btn = make_sound_button(elyby_btn_row, text="🟢 Войти через Ely.by",
                                            command=self.add_elyby_account_dialog,
                                            fg_color="#6fce7f", hover_color="#5cb56c",
                                            text_color="#16141f", height=32)
        elyby_login_btn.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        right_frame = ctk.CTkFrame(tab)
        right_frame.grid(row=1, column=1, sticky="nsew", padx=(10, 20), pady=(0, 10))
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(right_frame, text="ℹ️ Информация о скине", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0,
                                                                                                               column=0,
                                                                                                               sticky="w",
                                                                                                               padx=10,
                                                                                                               pady=(0,
                                                                                                                     5))

        self.skin_info = ctk.CTkTextbox(right_frame, font=ctk.CTkFont(family="Consolas", size=11), height=150)
        self.skin_info.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.skin_info.insert("1.0", "Тыкни в скин — покажу инфу")
        self.skin_info.configure(state="disabled")

        open_folder_btn = make_sound_button(right_frame, text="📂 Открыть папку", command=self.open_skins_folder,
                                            fg_color="#d9622f", hover_color="#c14f26", text_color="#16141f", height=35)
        open_folder_btn.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))

    def create_resourcepacks_tab(self):
        tab = self.tab_view.tab("📦 Ресурспаки")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        left_frame = ctk.CTkFrame(tab)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(20, 10), pady=20)
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(5, weight=1)

        ctk.CTkLabel(left_frame, text="🔍 Поиск ресурспаков", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, pady=(0, 10))

        ctk.CTkLabel(left_frame, text="🎮 Версия Minecraft:", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=1, column=0, sticky="w")
        self.rp_version_entry = ctk.CTkEntry(left_frame, placeholder_text="1.20.1", height=32)
        self.rp_version_entry.insert(0, "1.20.1")
        self.rp_version_entry.grid(row=2, column=0, sticky="w", pady=(0, 5))

        self.rp_search_entry = ctk.CTkEntry(left_frame, placeholder_text="Введите название ресурспака...", height=32)
        self.rp_search_entry.grid(row=3, column=0, sticky="ew", pady=(0, 5))
        self.rp_search_entry.bind("<Return>", lambda e: self.search_resourcepacks_web())

        search_btn = make_sound_button(left_frame, text="🔍 Искать", command=self.search_resourcepacks_web,
                                       height=32, fg_color="#6d92ff", hover_color="#5a7dd8")
        search_btn.grid(row=4, column=0, sticky="ew", pady=(0, 5))

        self.rp_results_frame = ctk.CTkScrollableFrame(left_frame, fg_color="transparent", height=250)
        self.rp_results_frame.grid(row=5, column=0, sticky="nsew", pady=(0, 5))
        self.rp_results_frame.grid_columnconfigure(0, weight=1)
        self.rp_cards = []
        self.rp_search_results = []
        self.selected_rp_index = -1
        self.show_rp_results_placeholder()

        self.install_rp_web_btn = make_sound_button(left_frame, text="📥 УСТАНОВИТЬ РЕСУРСПАК",
                                                     command=self.install_selected_resourcepack_web,
                                                     height=40, fg_color="#6fce7f", hover_color="#5cb56c",
                                                     text_color="#16141f", font=ctk.CTkFont(size=14, weight="bold"),
                                                     state="disabled")
        self.install_rp_web_btn.grid(row=6, column=0, sticky="ew", pady=(0, 5))

        self.rp_status_label = ctk.CTkLabel(left_frame, text="Пиши, что ищем, и жми 'Искать'",
                                            font=ctk.CTkFont(size=11), text_color="#6d92ff")
        self.rp_status_label.grid(row=7, column=0, sticky="w")

        right_frame = ctk.CTkFrame(tab)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 20), pady=20)
        right_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(right_frame, text="📦 Установленные ресурспаки", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, pady=(0, 10))

        _c = self.get_theme_colors()
        self.resourcepacks_listbox = tk.Listbox(right_frame, bg=_c["listbox_bg"], fg=_c["listbox_fg"],
                                                selectbackground=_c["listbox_select"],
                                                font=("Consolas", 11), height=10, relief="flat")
        self.resourcepacks_listbox.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        self.resourcepacks_listbox.bind("<Double-Button-1>", self.on_resourcepack_double_click)
        self.resourcepacks_listbox.bind("<<ListboxSelect>>", self.on_resourcepack_select)
        self.register_themed_widget(self.resourcepacks_listbox)

        btn_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew")
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)
        btn_frame.grid_columnconfigure(2, weight=1)

        install_btn = make_sound_button(btn_frame, text="📂 Из файла", command=self.install_resourcepack,
                                        fg_color="#6fce7f", hover_color="#5cb56c", text_color="#16141f")
        install_btn.grid(row=0, column=0, padx=2)

        delete_btn = make_sound_button(btn_frame, text="🗑️ Удалить", command=self.delete_selected_resourcepack,
                                       fg_color="#d3453f", hover_color="#b83530")
        delete_btn.grid(row=0, column=1, padx=2)

        open_folder_btn = make_sound_button(btn_frame, text="📂 Папка", command=self.open_resourcepacks_folder,
                                            fg_color="#6d92ff", hover_color="#5a7dd8")
        open_folder_btn.grid(row=0, column=2, padx=2)

        ctk.CTkLabel(right_frame, text="ℹ️ О выбранном ресурспаке", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=3, column=0, sticky="w", pady=(15, 5))

        self.rp_desc_card = ctk.CTkFrame(right_frame, fg_color=self.get_theme_colors()["card_bg"], corner_radius=10)
        self.rp_desc_card.grid(row=4, column=0, sticky="nsew", pady=(0, 5))
        self.rp_desc_card.grid_columnconfigure(1, weight=1)
        right_frame.grid_rowconfigure(4, weight=1)

        self.rp_desc_icon = ctk.CTkLabel(self.rp_desc_card, text="📦", font=ctk.CTkFont(size=28),
                                         width=64, height=64, fg_color="transparent")
        self.rp_desc_icon.grid(row=0, column=0, rowspan=2, padx=15, pady=15, sticky="n")

        self.rp_desc_title = ctk.CTkLabel(self.rp_desc_card, text="Тыкни в ресурспак",
                                          font=ctk.CTkFont(size=16, weight="bold"), anchor="w")
        self.rp_desc_title.grid(row=0, column=1, sticky="w", padx=(0, 15), pady=(15, 0))

        self.rp_desc_meta = ctk.CTkLabel(self.rp_desc_card, text="", font=ctk.CTkFont(size=11),
                                         text_color="#6d92ff", anchor="w")
        self.rp_desc_meta.grid(row=1, column=1, sticky="w", padx=(0, 15), pady=(0, 15))

        self.rp_desc_text = ctk.CTkTextbox(self.rp_desc_card, font=ctk.CTkFont(size=13), wrap="word",
                                           fg_color="transparent", height=130)
        self.rp_desc_text.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=15, pady=(0, 15))
        self.rp_desc_text.configure(state="disabled")

        self.rp_desc_open_btn = make_sound_button(self.rp_desc_card, text="🌐 Открыть на Modrinth",
                                                   command=self.open_selected_rp_page,
                                                   fg_color="#6d92ff", hover_color="#5a7dd8",
                                                   height=32, state="disabled")
        self.rp_desc_open_btn.grid(row=3, column=0, columnspan=2, sticky="ew", padx=15, pady=(0, 15))

    def show_rp_results_placeholder(self):
        for widget in self.rp_results_frame.winfo_children():
            widget.destroy()
        placeholder = ctk.CTkFrame(self.rp_results_frame, fg_color="transparent")
        placeholder.pack(fill="both", expand=True, pady=40)
        ctk.CTkLabel(placeholder, text="🔍", font=ctk.CTkFont(size=36)).pack()
        ctk.CTkLabel(placeholder, text="Пиши название ресурспака и жми «Искать»",
                     font=ctk.CTkFont(size=13), text_color="#6d92ff").pack(pady=(5, 0))

    def search_resourcepacks_web(self):
        query = self.rp_search_entry.get().strip()
        if not query:
            play_error()
            messagebox.showwarning("Ошибка", "Напиши, что искать")
            return
        version = self.rp_version_entry.get().strip()
        if not version:
            version = "1.20.1"

        for widget in self.rp_results_frame.winfo_children():
            widget.destroy()
        self.rp_cards = []
        self.selected_rp_index = -1
        self.install_rp_web_btn.configure(state="disabled")
        ctk.CTkLabel(self.rp_results_frame, text=f"⏳ Поиск «{query}»...",
                     font=ctk.CTkFont(size=13)).pack(pady=10)
        self.rp_status_label.configure(text="⏳ Поиск...", text_color="#d9622f")
        self.update_idletasks()

        def do_search():
            results = search_resourcepacks(query, version)
            self.after(0, lambda: self.display_rp_search_results(results))

        threading.Thread(target=do_search, daemon=True).start()

    def display_rp_search_results(self, results):
        for widget in self.rp_results_frame.winfo_children():
            widget.destroy()
        self.rp_search_results = results
        self.selected_rp_index = -1
        self.install_rp_web_btn.configure(state="disabled")
        self.rp_cards = []
        self.reset_rp_description()

        if not results:
            ctk.CTkLabel(self.rp_results_frame, text="❌ Ничего не найдено",
                         font=ctk.CTkFont(size=13)).pack(pady=10)
            self.rp_status_label.configure(text="❌ Ресурспаки не найдены", text_color="#d3453f")
            return

        for i, pack in enumerate(results):
            card = self.create_rp_card(self.rp_results_frame, pack, i)
            card.pack(fill="x", padx=5, pady=3)
            self.rp_cards.append(card)

        self.rp_status_label.configure(text=f"✅ Найдено {len(results)} ресурспаков", text_color="#6fce7f")

    def create_rp_card(self, parent, pack, index):
        title = pack.get('title', 'Без названия')
        author = pack.get('author', 'неизвестен')
        downloads = pack.get('downloads', 0)
        icon_url = pack.get('icon_url')

        colors = self.get_theme_colors()
        card = ctk.CTkFrame(parent, fg_color=colors["card_bg"], corner_radius=8, cursor="hand2")
        card.grid_columnconfigure(1, weight=1)

        icon_label = ctk.CTkLabel(card, text="🖼️", font=ctk.CTkFont(size=22),
                                  width=48, height=48, fg_color="transparent")
        icon_label.grid(row=0, column=0, rowspan=2, padx=10, pady=10)

        if icon_url:
            self.load_mod_icon_async(icon_url, icon_label)

        title_label = ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=14, weight="bold"),
                                   anchor="w", cursor="hand2")
        title_label.grid(row=0, column=1, sticky="w", padx=(0, 10), pady=(10, 0))

        downloads_text = f"{downloads:,}".replace(",", " ")
        meta_label = ctk.CTkLabel(card, text=f"👤 {author}   ⬇️ {downloads_text}", font=ctk.CTkFont(size=11),
                                  text_color="#6d92ff", anchor="w", cursor="hand2")
        meta_label.grid(row=1, column=1, sticky="w", padx=(0, 10), pady=(0, 10))

        def on_click(event=None, idx=index):
            self.select_rp_card(idx)

        for widget in (card, icon_label, title_label, meta_label):
            widget.bind("<Button-1>", on_click)

        return card

    def select_rp_card(self, index):
        self.selected_rp_index = index
        self.install_rp_web_btn.configure(state="normal")
        play_click()
        colors = self.get_theme_colors()
        for i, card in enumerate(self.rp_cards):
            try:
                card.configure(fg_color=colors["card_bg_selected"] if i == index else colors["card_bg"])
            except:
                pass
        self.show_rp_description(index)

    def show_rp_description(self, index):
        if index < 0 or index >= len(self.rp_search_results):
            return
        pack = self.rp_search_results[index]
        title = pack.get('title', 'Без названия')
        author = pack.get('author', 'неизвестен')
        description = pack.get('description', 'Описание отсутствует')
        downloads = pack.get('downloads', 0)
        follows = pack.get('follows', 0)
        categories = pack.get('categories', [])
        icon_url = pack.get('icon_url')

        self.rp_desc_title.configure(text=title)
        meta_parts = [f"👤 {author}", f"⬇️ {downloads:,}".replace(",", " "), f"❤️ {follows:,}".replace(",", " ")]
        if categories:
            meta_parts.append("🏷️ " + ", ".join(categories[:4]))
        self.rp_desc_meta.configure(text="   ".join(meta_parts))

        self.rp_desc_text.configure(state="normal")
        self.rp_desc_text.delete("1.0", "end")
        self.rp_desc_text.insert("1.0", description if description else "Описание отсутствует")
        self.rp_desc_text.configure(state="disabled")

        self.rp_desc_icon.configure(text="📦", image=None)
        if icon_url:
            self.load_mod_icon_async(icon_url, self.rp_desc_icon)

        self.rp_desc_open_btn.configure(state="normal")

    def open_selected_rp_page(self):
        if self.selected_rp_index < 0 or self.selected_rp_index >= len(self.rp_search_results):
            return
        pack = self.rp_search_results[self.selected_rp_index]
        slug = pack.get('slug') or pack.get('project_id')
        if slug:
            webbrowser.open(f"https://modrinth.com/resourcepack/{slug}")
            play_click()

    def reset_rp_description(self):
        self.rp_desc_title.configure(text="Тыкни в ресурспак")
        self.rp_desc_meta.configure(text="")
        self.rp_desc_icon.configure(text="📦", image=None)
        self.rp_desc_text.configure(state="normal")
        self.rp_desc_text.delete("1.0", "end")
        self.rp_desc_text.configure(state="disabled")
        self.rp_desc_open_btn.configure(state="disabled")

    def install_selected_resourcepack_web(self):
        if self.selected_rp_index < 0 or self.selected_rp_index >= len(self.rp_search_results):
            play_error()
            messagebox.showwarning("Ошибка", "Сначала выбери ресурспак из списка")
            return
        pack = self.rp_search_results[self.selected_rp_index]
        project_id = pack.get('project_id') or pack.get('slug')
        if not project_id:
            play_error()
            messagebox.showerror("Ошибка", "У ресурспака нет ID, странно как-то")
            return
        version = self.rp_version_entry.get().strip()
        if not version:
            version = "1.20.1"

        self.install_rp_web_btn.configure(state="disabled", text="⏳ УСТАНОВКА...")
        self.rp_status_label.configure(text="⏳ Установка ресурспака...", text_color="#d9622f")
        self.update_idletasks()

        def do_install():
            success, result = install_resourcepack_web(project_id, version)
            self.after(0, lambda: self.install_rp_web_finish(success, result))

        threading.Thread(target=do_install, daemon=True).start()

    def install_rp_web_finish(self, success, result):
        self.install_rp_web_btn.configure(state="normal", text="📥 УСТАНОВИТЬ РЕСУРСПАК")
        if success:
            self.rp_status_label.configure(text=f"✅ Ресурспак установлен: {result}", text_color="#6fce7f")
            self.refresh_resourcepacks()
            play_click()
            messagebox.showinfo("Успешно", f"✅ Ресурспак '{result}' на месте")
        else:
            self.rp_status_label.configure(text=f"❌ Ошибка: {result}", text_color="#d3453f")
            play_error()
            messagebox.showerror("Ошибка", f"❌ Ресурспак не встал:\n{result}")

    def create_settings_tab(self):
        tab = self.tab_view.tab("⚙️ Настройки")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        main_frame = ctk.CTkScrollableFrame(tab)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        main_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(main_frame, text="⚙️ Настройки лаунчера", font=ctk.CTkFont(size=24, weight="bold")).grid(row=0,
                                                                                                              column=0,
                                                                                                              pady=(0,
                                                                                                                    20))

        ctk.CTkLabel(main_frame, text="🎮 Логи игры", font=ctk.CTkFont(size=14, weight="bold")).grid(row=1,
                                                                                                    column=0,
                                                                                                    sticky="w",
                                                                                                    pady=(0, 5))
        logs_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        logs_frame.grid(row=2, column=0, sticky="w", pady=(0, 15))
        self.game_logs_switch = ctk.CTkSwitch(logs_frame,
                                              text="Показывать логи игры (консоль лаунчера + отдельное окно)",
                                              command=self.toggle_game_logs, font=ctk.CTkFont(size=13))
        if self.settings.get("show_game_logs", False):
            self.game_logs_switch.select()
        else:
            self.game_logs_switch.deselect()
        self.game_logs_switch.pack(side="left")

        ctk.CTkLabel(main_frame, text="🎨 Тема оформления", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=3, column=0, sticky="w", pady=(0, 5))
        theme_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        theme_frame.grid(row=4, column=0, sticky="w", pady=(0, 15))
        self.theme_switch = ctk.CTkSwitch(theme_frame,
                                          text="Тёмная тема (выключи для светлой)",
                                          command=self.toggle_theme, font=ctk.CTkFont(size=13))
        if self.settings.get("theme", "dark") == "dark":
            self.theme_switch.select()
        else:
            self.theme_switch.deselect()
        self.theme_switch.pack(side="left")

        ctk.CTkLabel(main_frame, text="🔶 Золотая тема аккаунта", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=5, column=0, sticky="w", pady=(0, 5))
        golden_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        golden_frame.grid(row=6, column=0, sticky="w", pady=(0, 15))
        self.golden_theme_switch = ctk.CTkSwitch(golden_frame,
                                                  text="Красить все кнопки в золотой при выборе лицензионного аккаунта",
                                                  command=self.toggle_golden_theme_setting,
                                                  font=ctk.CTkFont(size=13))
        if self.settings.get("golden_theme_enabled", True):
            self.golden_theme_switch.select()
        else:
            self.golden_theme_switch.deselect()
        self.golden_theme_switch.pack(side="left")

        ctk.CTkLabel(main_frame, text="🔷 Вход через Microsoft", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=7, column=0, sticky="w", pady=(0, 5))
        ms_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        ms_frame.grid(row=8, column=0, sticky="ew", pady=(0, 15))
        ms_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(ms_frame, text="Client ID своего Azure-приложения (portal.azure.com):",
                     font=ctk.CTkFont(size=12), text_color="#a8a4bd").grid(row=0, column=0, sticky="w")
        self.ms_client_id_entry = ctk.CTkEntry(ms_frame, placeholder_text="6ca935f1-4e54-484c-bbe2-482a8dcf9b33",
                                               height=32)
        self.ms_client_id_entry.grid(row=1, column=0, sticky="ew", pady=(2, 6))
        self.ms_client_id_entry.insert(0, self.settings.get("ms_client_id", "").strip() or DEFAULT_MS_CLIENT_ID)

        ctk.CTkLabel(ms_frame, text="Redirect URI (должен совпадать с тем, что указан в Azure):",
                     font=ctk.CTkFont(size=12), text_color="#a8a4bd").grid(row=2, column=0, sticky="w")
        self.ms_redirect_entry = ctk.CTkEntry(ms_frame, height=32)
        self.ms_redirect_entry.grid(row=3, column=0, sticky="ew", pady=(2, 6))
        self.ms_redirect_entry.insert(0, self.settings.get(
            "ms_redirect_uri", "https://login.microsoftonline.com/common/oauth2/nativeclient"))

        save_ms_btn = make_sound_button(ms_frame, text="💾 Сохранить", command=self.save_ms_settings,
                                        fg_color="#6fce7f", hover_color="#5cb56c", text_color="#16141f", height=32)
        save_ms_btn.grid(row=4, column=0, sticky="w")

        ctk.CTkLabel(main_frame, text="🔗 Полезные ссылки", font=ctk.CTkFont(size=14, weight="bold")).grid(row=9,
                                                                                                          column=0,
                                                                                                          sticky="w",
                                                                                                          pady=(15, 10))
        links_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        links_frame.grid(row=10, column=0, sticky="w", pady=(0, 15))

        github_btn = make_sound_button(links_frame, text="⭐ GitHub",
                                       command=lambda: webbrowser.open("https://github.com/KotiPlayYT/67launcher/"),
                                       width=180, height=40, fg_color="#2b2840", hover_color="#3d3a52",
                                       font=ctk.CTkFont(size=13, weight="bold"))
        github_btn.grid(row=0, column=0, padx=(0, 15), pady=5)

        donate_btn = make_sound_button(links_frame, text="💝 Поддержать",
                                       command=lambda: webbrowser.open("https://www.donationalerts.com/r/ionux"),
                                       width=180, height=40, fg_color="#d9622f", hover_color="#c14f26",
                                       font=ctk.CTkFont(size=13, weight="bold"))
        donate_btn.grid(row=0, column=1, pady=5)

    def create_stats_tab(self):
        tab = self.tab_view.tab("📊 Статистика")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        main_frame = ctk.CTkFrame(tab)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(main_frame, text="📊 Статистика", font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0,
                                                                                                     pady=(0, 20))

        self.stats_text = ctk.CTkTextbox(main_frame, font=ctk.CTkFont(family="Consolas", size=13), height=300)
        self.stats_text.grid(row=1, column=0, sticky="nsew", pady=(0, 10))

        refresh_btn = make_sound_button(main_frame, text="🔄 Обновить", command=self.on_stats_refresh_click,
                                        fg_color="#6d92ff", hover_color="#5a7dd8", width=200)
        refresh_btn.grid(row=2, column=0)

        self.update_stats_display()

    def show_install_versions_placeholder(self):
        for widget in self.version_results_frame.winfo_children():
            widget.destroy()
        ctk.CTkLabel(self.version_results_frame, text="⏳ Список версий ещё грузится...",
                     font=ctk.CTkFont(size=12), text_color="#a8a4bd").pack(pady=15)

    def search_mods(self):
        query = self.mod_search_entry.get().strip()
        if not query:
            play_error()
            messagebox.showwarning("Ошибка", "Напиши, что искать")
            return
        version = self.mod_version_entry.get().strip()
        if not version:
            version = "1.20.1"
        loader = self.mod_loader_var.get()

        for widget in self.results_frame.winfo_children():
            widget.destroy()
        self.mod_cards = []
        self.selected_mod_index = -1
        self.install_mod_btn.configure(state="disabled")
        self.reset_mod_description()
        ctk.CTkLabel(self.results_frame, text=f"⏳ Поиск «{query}»...",
                     font=ctk.CTkFont(size=13)).pack(pady=10)
        self.mod_status_label.configure(text="⏳ Поиск...", text_color="#d9622f")
        self.update_idletasks()

        def do_search():
            results = search_mods(query, version, loader)
            self.after(0, lambda: self.display_search_results(results))

        threading.Thread(target=do_search, daemon=True).start()

    def display_search_results(self, results):
        for widget in self.results_frame.winfo_children():
            widget.destroy()
        self.search_results = results
        self.selected_mod_index = -1
        self.install_mod_btn.configure(state="disabled")
        self.mod_cards = []

        if not results:
            ctk.CTkLabel(self.results_frame, text="❌ Ничего не найдено",
                         font=ctk.CTkFont(size=13)).pack(pady=10)
            self.mod_status_label.configure(text="❌ Моды не найдены", text_color="#d3453f")
            return

        for i, mod in enumerate(results):
            card = self.create_mod_card(self.results_frame, mod, i)
            card.pack(fill="x", padx=5, pady=3)
            self.mod_cards.append(card)

        self.mod_status_label.configure(text=f"✅ Найдено {len(results)} модов", text_color="#6fce7f")

    def create_mod_card(self, parent, mod, index):
        title = mod.get('title', 'Без названия')
        author = mod.get('author', 'неизвестен')
        icon_url = mod.get('icon_url')

        colors = self.get_theme_colors()
        card = ctk.CTkFrame(parent, fg_color=colors["card_bg"], corner_radius=8, cursor="hand2")
        card.grid_columnconfigure(1, weight=1)

        icon_label = ctk.CTkLabel(card, text="📦", font=ctk.CTkFont(size=22),
                                  width=48, height=48, fg_color="transparent")
        icon_label.grid(row=0, column=0, rowspan=2, padx=10, pady=10)

        if icon_url:
            self.load_mod_icon_async(icon_url, icon_label)

        title_label = ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=14, weight="bold"),
                                   anchor="w", cursor="hand2")
        title_label.grid(row=0, column=1, sticky="w", padx=(0, 10), pady=(10, 0))

        author_label = ctk.CTkLabel(card, text=f"👤 {author}", font=ctk.CTkFont(size=11),
                                    text_color="#6d92ff", anchor="w", cursor="hand2")
        author_label.grid(row=1, column=1, sticky="w", padx=(0, 10), pady=(0, 10))

        def on_click(event=None, idx=index):
            self.select_mod_card(idx)

        for widget in (card, icon_label, title_label, author_label):
            widget.bind("<Button-1>", on_click)

        return card

    def load_mod_icon_async(self, url, label_widget):
        def worker():
            img = load_image_from_url(url, size=(48, 48))
            if img:
                def apply():
                    try:
                        if label_widget.winfo_exists():
                            label_widget.configure(image=img, text="")
                            label_widget.image = img
                    except:
                        pass

                self.after(0, apply)

        threading.Thread(target=worker, daemon=True).start()

    def select_mod_card(self, index):
        self.selected_mod_index = index
        self.install_mod_btn.configure(state="normal")
        play_click()
        colors = self.get_theme_colors()
        for i, card in enumerate(self.mod_cards):
            try:
                card.configure(fg_color=colors["card_bg_selected"] if i == index else colors["card_bg"])
            except:
                pass
        self.show_mod_description(index)

    def show_mod_description(self, index):
        if index < 0 or index >= len(self.search_results):
            return
        mod = self.search_results[index]
        title = mod.get('title', 'Без названия')
        author = mod.get('author', 'неизвестен')
        description = mod.get('description', 'Описание отсутствует')
        downloads = mod.get('downloads', 0)
        follows = mod.get('follows', 0)
        categories = mod.get('categories', [])
        icon_url = mod.get('icon_url')
        slug = mod.get('slug') or mod.get('project_id')

        self.mod_desc_title.configure(text=title)
        meta_parts = [f"👤 {author}", f"⬇️ {downloads:,}".replace(",", " "), f"❤️ {follows:,}".replace(",", " ")]
        if categories:
            meta_parts.append("🏷️ " + ", ".join(categories[:4]))
        self.mod_desc_meta.configure(text="   ".join(meta_parts))

        self.mod_desc_text.configure(state="normal")
        self.mod_desc_text.delete("1.0", "end")
        self.mod_desc_text.insert("1.0", description if description else "Описание отсутствует")
        self.mod_desc_text.configure(state="disabled")

        self.mod_desc_icon.configure(text="📦", image=None)
        if icon_url:
            self.load_mod_icon_async(icon_url, self.mod_desc_icon)

        self.mod_desc_open_url = f"https://modrinth.com/mod/{slug}" if slug else None
        self.mod_desc_open_btn.configure(state="normal" if self.mod_desc_open_url else "disabled")

    def open_selected_mod_page(self):
        url = getattr(self, 'mod_desc_open_url', None)
        if url:
            webbrowser.open(url)
            play_click()

    def reset_mod_description(self):
        self.mod_desc_title.configure(text="Тыкни в мод слева")
        self.mod_desc_meta.configure(text="")
        self.mod_desc_icon.configure(text="📦", image=None)
        self.mod_desc_text.configure(state="normal")
        self.mod_desc_text.delete("1.0", "end")
        self.mod_desc_text.configure(state="disabled")
        self.mod_desc_open_url = None
        self.mod_desc_open_btn.configure(state="disabled")

    def on_installed_mod_select(self, event=None):
        selection = self.installed_listbox.curselection()
        if not selection:
            return
        entry = self.installed_listbox.get(selection[0])
        if "📭" in entry:
            return
        mod_filename = entry.replace("📦 ", "").strip()

        self.mod_desc_title.configure(text=mod_filename)
        self.mod_desc_meta.configure(text="🔍 Ищу на Modrinth...")
        self.mod_desc_text.configure(state="normal")
        self.mod_desc_text.delete("1.0", "end")
        self.mod_desc_text.configure(state="disabled")
        self.mod_desc_icon.configure(text="📦", image=None)
        self.mod_desc_open_url = None
        self.mod_desc_open_btn.configure(state="disabled")

        mod_path = os.path.join(get_mods_folder(), mod_filename)

        def do_lookup():
            result = identify_mod_by_hash(mod_path)
            self.after(0, lambda: self.display_local_mod_lookup(mod_filename, result))

        threading.Thread(target=do_lookup, daemon=True).start()

    def display_local_mod_lookup(self, mod_filename, result):
        selection = self.installed_listbox.curselection()
        if not selection or self.installed_listbox.get(selection[0]).replace("📦 ", "").strip() != mod_filename:
            return

        if not result:
            self.mod_desc_title.configure(text=mod_filename)
            self.mod_desc_meta.configure(text="")
            self.mod_desc_text.configure(state="normal")
            self.mod_desc_text.delete("1.0", "end")
            self.mod_desc_text.insert("1.0", "Не удалось найти этот мод на Modrinth (возможно, скачан не оттуда).")
            self.mod_desc_text.configure(state="disabled")
            self.mod_desc_open_url = None
            self.mod_desc_open_btn.configure(state="disabled")
            return

        self.mod_desc_title.configure(text=result['title'])
        downloads = result.get('downloads', 0)
        follows = result.get('follows', 0)
        categories = result.get('categories', [])
        meta_parts = [f"⬇️ {downloads:,}".replace(",", " "), f"❤️ {follows:,}".replace(",", " ")]
        if categories:
            meta_parts.append("🏷️ " + ", ".join(categories[:4]))
        self.mod_desc_meta.configure(text="   ".join(meta_parts))

        self.mod_desc_text.configure(state="normal")
        self.mod_desc_text.delete("1.0", "end")
        self.mod_desc_text.insert("1.0", result.get('description', 'Описание отсутствует'))
        self.mod_desc_text.configure(state="disabled")

        icon_url = result.get('icon_url')
        self.mod_desc_icon.configure(text="📦", image=None)
        if icon_url:
            self.load_mod_icon_async(icon_url, self.mod_desc_icon)

        slug = result.get('slug')
        self.mod_desc_open_url = f"https://modrinth.com/mod/{slug}" if slug else None
        self.mod_desc_open_btn.configure(state="normal" if self.mod_desc_open_url else "disabled")

    def install_selected_mod(self):
        if self.selected_mod_index < 0 or self.selected_mod_index >= len(self.search_results):
            play_error()
            messagebox.showwarning("Ошибка", "Сначала выбери мод из списка")
            return
        mod = self.search_results[self.selected_mod_index]
        project_id = mod.get('project_id')
        if not project_id:
            play_error()
            messagebox.showerror("Ошибка", "У мода нет ID, странно как-то")
            return
        version = self.mod_version_entry.get().strip()
        if not version:
            version = "1.20.1"
        loader = self.mod_loader_var.get()

        self.install_mod_btn.configure(state="disabled", text="⏳ УСТАНОВКА...")
        self.mod_status_label.configure(text="⏳ Установка мода...", text_color="#d9622f")
        self.update_idletasks()

        def do_install():
            success, result = install_mod(project_id, version, loader)
            self.after(0, lambda: self.install_mod_finish(success, result))

        threading.Thread(target=do_install, daemon=True).start()

    def install_mod_finish(self, success, result):
        self.install_mod_btn.configure(state="normal", text="📥 УСТАНОВИТЬ МОД")
        if success:
            self.mod_status_label.configure(text=f"✅ Мод установлен: {result}", text_color="#6fce7f")
            self.refresh_mods_list()
            play_click()
            messagebox.showinfo("Успешно", f"✅ Мод '{result}' стоит, можно играть")
        else:
            self.mod_status_label.configure(text=f"❌ Ошибка: {result}", text_color="#d3453f")
            play_error()
            messagebox.showerror("Ошибка", f"❌ Мод не встал:\n{result}")

    def update_timer_display(self):
        if self.timer_running:
            self.timer_label.configure(text=f"⏱ Время игры: {self.format_time(self.timer_seconds)}")
            self.timer_seconds += 1
            self.after(1000, self.update_timer_display)

    def start_game_timer(self):
        if not self.timer_running:
            self.timer_running = True
            self.timer_seconds = 0
            self.log("⏱ Таймер запущен")
            self.update_timer_display()

    def stop_game_timer(self):
        if self.timer_running:
            self.timer_running = False
            if self.timer_seconds > 0:
                update_play_time(self.timer_seconds)
                self.stats = load_stats()
                self.log(f"⏱ Время игры сохранено: {self.format_time(self.timer_seconds)}")
                self.update_info_display()
                self.update_subtitle()
            else:
                self.log("⏱ Таймер остановлен (0 секунд)")
            self.timer_label.configure(text="⏱ Время игры: 0с")

    def set_launch_progress(self, percent, status_text=None):
        def _update():
            try:
                self.launch_progressbar.animating = False
                self.launch_progressbar.set_progress(percent)
                if status_text:
                    self.launch_status_label.configure(text=status_text, text_color="#d9622f")
            except:
                pass

        try:
            self.after(0, _update)
        except:
            pass

    def launch_game(self):
        if self.is_launching:
            return

        username = self.account_combo.get()
        if username == "Нет аккаунтов" or not username:
            play_error()
            messagebox.showwarning("Ошибка", "Аккаунта нет — сначала создай")
            return

        account_data = None
        for acc in load_accounts():
            if acc["username"] == username:
                account_data = acc
                break

        version = self.version_combo.get()
        if version == "Нет версий" or not version:
            play_error()
            messagebox.showwarning("Ошибка", "Версия не стоит — сначала поставь")
            return

        ram = self.ram_var.get()

        self.is_launching = True
        self.launch_btn.configure(state="disabled", text="⏳ ЗАПУСК...")

        self.launch_progressbar.animating = False
        self.launch_progressbar.set(0)
        self.launch_progressbar.configure(progress_color="#7896f7")
        self.launch_status_label.configure(text="⏳ Запуск Minecraft...", text_color="#d9622f")
        self.log(f"🚀 Запуск: {version} от {username} с памятью {ram}")
        self.update_idletasks()

        def do_launch():
            error_message = None
            success = False
            try:
                self.set_launch_progress(10, "⏳ Проверка Java...")
                java_path = get_java_for_version(version)
                self.log(f"☕ Java: {java_path}")
                self.set_launch_progress(25)

                version_path = os.path.join(MINECRAFT_DIR, "versions", version)
                if not os.path.exists(version_path):
                    error_message = f"Версия {version} не найдена"
                    self.after(0, lambda: self.launch_finish(False, error_message))
                    return

                jar_path = resolve_version_jar_path(version, MINECRAFT_DIR)
                if not jar_path:
                    error_message = (f"JAR файл версии {version} не найден "
                                     f"(ни у самой версии, ни у родительской через inheritsFrom)")
                    self.log(f"❌ {error_message}")
                    self.after(0, lambda: self.launch_finish(False, error_message))
                    return
                self.set_launch_progress(45, "⏳ Проверка файлов версии...")

                self.set_launch_progress(55)

                command = mll.command.get_minecraft_command(
                    version=version,
                    minecraft_directory=MINECRAFT_DIR,
                    options=mll.utils.generate_test_options()
                )
                self.set_launch_progress(70, "⏳ Сборка команды запуска...")

                cleaned_command = []
                i = 0
                while i < len(command):
                    arg = command[i]
                    if arg in ["--username", "--uuid", "--accessToken", "--userType"]:
                        i += 2
                        continue
                    cleaned_command.append(arg)
                    i += 1
                command = cleaned_command

                injector_path = None
                if account_data and account_data.get("type") == "microsoft":
                    self.set_launch_progress(75, "⏳ Обновляю токен Microsoft...")
                    refreshed = refresh_microsoft_account(account_data)
                    login_data = refreshed if refreshed else account_data
                    command.extend(["--username", login_data["name"] if refreshed else login_data["username"]])
                    command.extend(["--uuid", login_data["id"] if refreshed else login_data["uuid"]])
                    command.extend(["--accessToken", login_data["access_token"]])
                    command.extend(["--userType", "msa"])
                elif account_data and account_data.get("type") == "elyby":
                    self.set_launch_progress(75, "⏳ Обновляю токен Ely.by...")
                    refreshed = refresh_elyby_account(account_data)
                    login_data = refreshed if refreshed else account_data
                    command.extend(["--username", login_data["name"] if refreshed else login_data["username"]])
                    command.extend(["--uuid", login_data["id"] if refreshed else login_data["uuid"]])
                    command.extend(["--accessToken", login_data["access_token"]])
                    command.extend(["--userType", "mojang"])
                    self.set_launch_progress(78, "⏳ Подключаю authlib-injector (Ely.by)...")
                    injector_path = ensure_authlib_injector()
                    if not injector_path:
                        self.log("⚠️ Не удалось скачать authlib-injector — скин Ely.by в игре не покажется")
                else:
                    command.extend(["--username", username])
                    command.extend(["--uuid", "00000000-0000-0000-0000-000000000000"])
                    command.extend(["--accessToken", "0"])
                    command.extend(["--userType", "mojang"])

                if injector_path:
                    command.insert(0, f"-javaagent:{injector_path}=ely.by")

                if java_path != "java":
                    command.insert(0, java_path)

                self.log(f"📋 Команда запуска: {' '.join(command[:6])}...")
                self.set_launch_progress(85, "⏳ Запуск процесса...")

                self.minecraft_process = subprocess.Popen(
                    command,
                    cwd=MINECRAFT_DIR,

                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    errors='ignore'
                )

                from collections import deque
                self.last_game_output = deque(maxlen=60)

                show_logs = self.settings.get("show_game_logs", False)

                if show_logs:
                    def _open_game_console():
                        try:
                            if self.game_console is not None and self.game_console.winfo_exists():
                                self.game_console.destroy()
                        except:
                            pass
                        self.game_console = GameConsoleWindow(self)

                    self.after(0, _open_game_console)

                def read_output(pipe, name):
                    try:
                        for line in iter(pipe.readline, ''):
                            if line:
                                line = line.strip()
                                if line:
                                    try:
                                        self.last_game_output.append(f"[{name}] {line}")
                                    except:
                                        pass
                                if line and show_logs:
                                    full_line = f"[{name}] {line}"
                                    try:
                                        self.log(full_line)
                                    except:
                                        pass
                                    try:
                                        if self.game_console:
                                            self.game_console.log(full_line)
                                    except:
                                        pass
                    except:
                        pass

                threading.Thread(target=read_output, args=(self.minecraft_process.stdout, "Minecraft"),
                                 daemon=True).start()
                threading.Thread(target=read_output, args=(self.minecraft_process.stderr, "ERROR"), daemon=True).start()

                self.log("✅ Процесс запущен!")
                self.set_launch_progress(95)
                success = True
                was_first_launch = load_stats().get("launches", 0) == 0
                update_stats()
                self.stats = load_stats()
                if was_first_launch:
                    self.after(0, self.show_first_launch_server_dialog)

                self.after(0, self.start_game_timer)

                def monitor_process():
                    if self.minecraft_process:
                        self.minecraft_process.wait()
                        self.after(0, self.stop_game_timer)
                        returncode = self.minecraft_process.returncode
                        if returncode != 0:
                            self.log(f"💥 Игра завершилась с кодом ошибки {returncode}")
                            self.after(0, lambda: self.on_game_crashed(returncode))
                        else:
                            self.log("🔄 Игра закрыта, таймер остановлен")

                threading.Thread(target=monitor_process, daemon=True).start()

            except Exception as e:
                error_message = str(e)
                self.log(f"❌ Ошибка запуска: {error_message}")
                self.stop_game_timer()

            if success:
                self.after(0, lambda: self.launch_finish(True, error_message))
            else:
                self.after(0, lambda: self.launch_finish(False, error_message))

        threading.Thread(target=do_launch, daemon=True).start()

    def launch_finish(self, success, message):
        self.is_launching = False
        self.launch_btn.configure(state="normal", text="🚀 ЗАПУСТИТЬ ИГРУ")
        self.launch_progressbar.animating = False

        if success:
            self.launch_status_label.configure(text="✅ Игра запущена!", text_color="#6fce7f")
            self.launch_progressbar.set(1.0)
            self.launch_progressbar.configure(progress_color="#6fce7f")
            self.log("✅ Игра успешно запущена")
            self.save_current_selection()
            play_click()
        else:
            self.launch_status_label.configure(text="❌ Ошибка запуска", text_color="#d3453f")
            self.launch_progressbar.set(0.3)
            self.launch_progressbar.configure(progress_color="#d3453f")
            self.log(f"❌ Ошибка запуска: {message}")
            self.stop_game_timer()
            play_error()
            messagebox.showerror("Ошибка запуска", f"Игра не запустилась.\n\nПричина: {message}")

    def on_game_crashed(self, returncode):
        play_error()

        crash_report_path = None
        crash_excerpt = None
        try:
            crash_dir = os.path.join(MINECRAFT_DIR, "crash-reports")
            if os.path.isdir(crash_dir):
                reports = [os.path.join(crash_dir, f) for f in os.listdir(crash_dir) if f.endswith(".txt")]
                if reports:
                    crash_report_path = max(reports, key=os.path.getmtime)
                    try:
                        with open(crash_report_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        desc_idx = content.find("Description:")
                        if desc_idx != -1:
                            crash_excerpt = content[desc_idx:desc_idx + 2200].strip()
                        else:
                            crash_excerpt = content[:2200].strip()
                    except Exception:
                        pass
        except Exception:
            pass

        tail_lines = list(self.last_game_output)[-15:] if hasattr(self, 'last_game_output') else []
        tail_text = "\n".join(tail_lines) if tail_lines else "(нет вывода от процесса)"

        self.launch_status_label.configure(text=f"💥 Игра вылетела (код {returncode})", text_color="#d3453f")
        self.launch_progressbar.set(0.3)
        self.launch_progressbar.configure(progress_color="#d3453f")

        message = f"Игра запустилась, но закрылась с кодом ошибки {returncode} — это крэш Java, а не штатное закрытие.\n\n"
        if crash_report_path:
            message += f"Отчёт о крэше:\n{crash_report_path}\n\n"
        if crash_excerpt:
            message += f"Суть ошибки из отчёта:\n{crash_excerpt}\n\n(полный текст — в файле отчёта выше)"
        else:
            message += f"Последние строки вывода:\n{tail_text}"

        messagebox.showerror("Игра вылетела", message)

    def install_vanilla(self, version):
        try:
            self.log(f"📦 Установка Vanilla {version}...")
            mll.install.install_minecraft_version(version, MINECRAFT_DIR, mll_callback)
            self.log(f"✅ Vanilla {version} установлен!")
            create_profile(version, f"Vanilla {version}")
            return True
        except Exception as e:
            self.log(f"❌ Ошибка: {e}")
            return False

    def install_fabric(self, version):
        try:
            self.log(f"📦 Установка Fabric {version}...")
            mll.fabric.install_fabric(version, MINECRAFT_DIR, callback=mll_callback)
            self.log(f"✅ Fabric {version} установлен!")
            installed = mll.utils.get_installed_versions(MINECRAFT_DIR)
            fabric_versions = [v for v in installed if "fabric" in v["id"].lower()]
            if fabric_versions:
                fabric_id = fabric_versions[-1]["id"]
                create_profile(fabric_id, f"Fabric {version}")
            self.scan_and_update_versions()
            return True
        except Exception as e:
            self.log(f"❌ Ошибка установки Fabric: {e}")
            return False

    def install_forge(self, version):
        try:
            self.log(f"📦 Установка Forge {version}...")
            self.log(f"📦 Шаг 1/2: Установка Vanilla {version}...")
            mll.install.install_minecraft_version(version, MINECRAFT_DIR, mll_callback)
            self.log(f"📦 Шаг 2/2: Установка Forge...")

            installed_ok = False

            if is_legacy_mc_version(version):
                full_forge_version = get_forge_full_version(version)
                if full_forge_version:
                    self.log(f"🔧 Версия до 1.13 — использую официальный установщик Forge "
                             f"{full_forge_version} (надёжнее для этого поколения, меньше шанс крашей рантайм-деобфускации)")
                    installed_ok = self.install_forge_manual(full_forge_version)
                else:
                    self.log("⚠️ Не удалось определить точную сборку Forge, пробую через minecraft_launcher_lib...")

            if not installed_ok:
                if hasattr(mll.forge, 'install_forge'):
                    mll.forge.install_forge(version, MINECRAFT_DIR, mll_callback)
                    installed_ok = True
                elif hasattr(mll.forge, 'install_forge_version'):
                    full_forge_version = get_forge_full_version(version) or version
                    mll.forge.install_forge_version(full_forge_version, MINECRAFT_DIR, mll_callback)
                    installed_ok = True
                elif hasattr(mll.install, 'install_forge'):
                    mll.install.install_forge(version, MINECRAFT_DIR, mll_callback)
                    installed_ok = True
                else:
                    full_forge_version = get_forge_full_version(version) or version
                    installed_ok = self.install_forge_manual(full_forge_version)

            if not installed_ok:
                return False

            self.log(f"✅ Forge {version} установлен!")
            installed = mll.utils.get_installed_versions(MINECRAFT_DIR)
            forge_versions = [v for v in installed if "forge" in v["id"].lower()]
            if forge_versions:
                forge_id = forge_versions[-1]["id"]
                create_profile(forge_id, f"Forge {version}")
            self.scan_and_update_versions()
            return True
        except Exception as e:
            self.log(f"❌ Ошибка установки Forge: {e}")
            return False

    def install_forge_manual(self, version):
        try:
            import urllib.request
            self.log("📥 Скачивание установщика Forge...")
            forge_url = f"https://maven.minecraftforge.net/net/minecraftforge/forge/{version}/forge-{version}-installer.jar"
            installer_path = os.path.join(tempfile.gettempdir(), f"forge-{version}-installer.jar")

            def report_progress(count, block_size, total_size):
                if total_size > 0:
                    percent = int(count * block_size * 100 / total_size)
                    if percent % 10 == 0:
                        self.log(f"📊 Скачивание Forge: {percent}%")

            urllib.request.urlretrieve(forge_url, installer_path, report_progress)
            self.log("🔧 Запуск установщика Forge...")
            java_path = get_java_for_version(version)
            cmd = [java_path, "-jar", installer_path, "--installClient", MINECRAFT_DIR]
            process = subprocess.Popen(cmd, cwd=MINECRAFT_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       text=True)
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    self.log(f"📌 {output.strip()}")
            if process.returncode != 0:
                stderr = process.stderr.read()
                self.log(f"❌ Ошибка установки Forge: {stderr}")
                return False
            try:
                os.remove(installer_path)
            except:
                pass
            self.log("✅ Forge установлен через официальный установщик")
            return True
        except Exception as e:
            self.log(f"❌ Ошибка ручной установки Forge: {e}")
            return False

    def install_optifine(self, version):
        try:
            if not hasattr(self, 'selected_installer_path') or not self.selected_installer_path:
                self.log("❌ Файл не выбран")
                return False

            self.log(f"📦 Установка OptiFine {version}...")
            self.log(f"📦 Шаг 1/2: Установка Vanilla {version}...")
            mll.install.install_minecraft_version(version, MINECRAFT_DIR, mll_callback)
            self.log(f"📦 Шаг 2/2: Установка OptiFine...")
            mll.optifine.install_optifine(self.selected_installer_path, MINECRAFT_DIR, mll_callback)

            self.log(f"✅ OptiFine {version} установлен!")
            installed = mll.utils.get_installed_versions(MINECRAFT_DIR)
            optifine_versions = [v for v in installed if "optifine" in v["id"].lower() or "of" in v["id"].lower()]
            if optifine_versions:
                optifine_id = optifine_versions[-1]["id"]
                create_profile(optifine_id, f"OptiFine {version}")
            self.scan_and_update_versions()
            self.selected_installer_path = None
            self.install_file_label.configure(text="❌ Файл не выбран", text_color="#d3453f")
            return True
        except Exception as e:
            self.log(f"❌ Ошибка установки OptiFine: {e}")
            return False

    def install_selected_client(self):
        install_type = self.install_type_var.get()
        version = self.version_search_entry.get().strip()

        if not version:
            play_error()
            messagebox.showwarning("Ошибка", "Укажи версию Minecraft")
            return

        if install_type == "optifine":
            if not hasattr(self, 'selected_installer_path') or not self.selected_installer_path:
                play_error()
                messagebox.showwarning("Ошибка", "Файл OptiFine не выбран")
                return

        self.log(f"📦 Установка {install_type} {version}")
        self.install_btn.configure(state="disabled", text="⏳ УСТАНОВКА...")
        _reset_install_progress_state()
        self.install_progressbar.animating = False
        self.install_progressbar.set(0)
        self.install_progressbar.configure(progress_color="#6d92ff")
        self.install_status_label.configure(text="Подготовка...", text_color="#d9622f")
        self.update_idletasks()

        def do_install():
            success = False
            cleanup_forge_temp()

            if install_type == "vanilla":
                success = self.install_vanilla(version)
            elif install_type == "fabric":
                success = self.install_fabric(version)
            elif install_type == "forge":
                success = self.install_forge(version)
            elif install_type == "optifine":
                success = self.install_optifine(version)

            cleanup_forge_temp()

            def finish_ui():
                self.install_btn.configure(state="normal", text="📥 УСТАНОВИТЬ")
                self.install_progressbar.animating = False
                if success:
                    self.log(f"✅ {install_type.capitalize()} {version} установлен!")
                    self.install_progressbar.set(1.0)
                    self.install_progressbar.configure(progress_color="#6fce7f")
                    self.install_status_label.configure(text=f"✅ {install_type.capitalize()} {version} установлен!",
                                                        text_color="#6fce7f")
                    self.scan_and_update_versions()
                    play_click()
                    messagebox.showinfo("Успешно", f"{install_type.capitalize()} {version} готов к работе")
                else:
                    self.log(f"❌ Ошибка установки {install_type}")
                    self.install_progressbar.set(0.3)
                    self.install_progressbar.configure(progress_color="#d3453f")
                    self.install_status_label.configure(text=f"❌ Ошибка установки {install_type}", text_color="#d3453f")
                    play_error()
                    messagebox.showerror("Ошибка", f"{install_type.capitalize()} {version} не встал")

            self.after(0, finish_ui)

        threading.Thread(target=do_install, daemon=True).start()

    def open_chat_window(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("💬 Настройка чата")

        saved_size = safe_window_geometry(self.settings.get("chat_setup_window_size", "600x620"), default="600x620")
        dialog.geometry(saved_size)
        dialog.minsize(500, 500)
        dialog.resizable(True, True)
        dialog.grab_set()
        dialog.transient(self)

        def _save_setup_size_only():
            try:
                raw_size = f"{dialog.winfo_width()}x{dialog.winfo_height()}"
                size = safe_window_geometry(raw_size, default=None)
                if size:
                    self.settings["chat_setup_window_size"] = size
                    save_launcher_settings(self.settings)
            except:
                pass

        def _save_setup_size_and_close():
            _save_setup_size_only()
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", _save_setup_size_and_close)

        dialog.update_idletasks()
        width = dialog.winfo_width()
        height = dialog.winfo_height()
        x = (dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (dialog.winfo_screenheight() // 2) - (height // 2)
        dialog.geometry(f"{width}x{height}+{x}+{y}")

        main_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(main_frame, text="💬 Настройка чата",
                     font=ctk.CTkFont(size=24, weight="bold"), text_color="#6d92ff").pack(pady=(0, 10))

        relay_frame = ctk.CTkFrame(main_frame, fg_color="#100e1a", corner_radius=10)
        relay_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(relay_frame, text="🌍 ПОДКЛЮЧЕНИЕ ЧЕРЕЗ РЕЛЕЙ (работает через интернет, без проброса портов):",
                     font=ctk.CTkFont(size=12, weight="bold"), text_color="#6fce7f",
                     wraplength=520, justify="center").pack(pady=(8, 4), padx=10)
        ctk.CTkLabel(relay_frame, text=RELAY_URL,
                     font=ctk.CTkFont(size=13, weight="bold"), text_color="#6d92ff").pack(pady=(0, 8))

        instr_frame = ctk.CTkFrame(main_frame, fg_color="#201d30", corner_radius=10)
        instr_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(instr_frame, text="📝 КАК ПОДКЛЮЧИТЬСЯ:",
                     font=ctk.CTkFont(size=13, weight="bold"), text_color="#d9622f").pack(pady=(5, 5))

        instr_text = """1️⃣ Один из вас жмёт "Хост" (создать комнату)
2️⃣ Он копирует код комнаты (вон он ниже) и кидает второму
3️⃣ Второй жмёт "Гость" и вставляет этот же код
4️⃣ Жмёт "Запустить чат" — и погнали

✅ IP и проброс портов больше не нужны — оба просто
   подключаются к общему релею по одному коду комнаты"""

        ctk.CTkLabel(instr_frame, text=instr_text,
                     font=ctk.CTkFont(size=12), text_color="#e5e2f0",
                     justify="left", wraplength=520).pack(pady=5, padx=10)

        mode_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        mode_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(mode_frame, text="Кто ты в этой схеме:",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w")

        mode_var = ctk.StringVar(value="server")

        server_rb = ctk.CTkRadioButton(mode_frame, text="🖥️ Я ХОСТ (создать комнату) - запустите ПЕРВЫМ",
                                       variable=mode_var, value="server",
                                       font=ctk.CTkFont(size=13))
        server_rb.pack(anchor="w", pady=3)

        client_rb = ctk.CTkRadioButton(mode_frame, text="💻 Я ГОСТЬ (подключиться по коду) - запустите ВТОРЫМ",
                                       variable=mode_var, value="client",
                                       font=ctk.CTkFont(size=13))
        client_rb.pack(anchor="w", pady=3)

        settings_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        settings_frame.pack(fill="x", pady=(0, 10))

        room_row = ctk.CTkFrame(settings_frame, fg_color="transparent")
        room_row.pack(fill="x", pady=3)

        ctk.CTkLabel(room_row, text="🚪 Код комнаты:", font=ctk.CTkFont(size=13, weight="bold"),
                     width=140).pack(side="left")
        room_entry = ctk.CTkEntry(room_row, placeholder_text="Код комнаты сюда", width=180, height=35,
                                  font=ctk.CTkFont(size=13))
        room_entry.pack(side="left", padx=(10, 0))
        room_entry.insert(0, generate_room_code())

        def regenerate_room():
            room_entry.delete(0, 'end')
            room_entry.insert(0, generate_room_code())
            play_click()

        new_code_btn = make_sound_button(room_row, text="🎲 Новый",
                                         command=regenerate_room,
                                         width=75, height=30,
                                         fg_color="#2b2840", hover_color="#3d3a52",
                                         font=ctk.CTkFont(size=11))
        new_code_btn.pack(side="left", padx=(5, 0))

        paste_btn = make_sound_button(room_row, text="📋 Вставить",
                                      command=lambda: self.paste_ip_to_entry(room_entry),
                                      width=80, height=30,
                                      fg_color="#d9622f", hover_color="#c14f26",
                                      text_color="#16141f", font=ctk.CTkFont(size=11))
        paste_btn.pack(side="left", padx=(5, 0))

        copy_room_btn = make_sound_button(room_row, text="📋 Копировать",
                                          command=lambda: self.copy_ip_to_clipboard(room_entry.get().strip()),
                                          width=95, height=30,
                                          fg_color="#6d92ff", hover_color="#5a7dd8",
                                          font=ctk.CTkFont(size=11))
        copy_room_btn.pack(side="left", padx=(5, 0))

        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(5, 0))

        def start_chat():
            try:
                mode = mode_var.get()
                room = room_entry.get().strip()

                if not room:
                    play_error()
                    messagebox.showwarning("Ошибка", "Код комнаты пустой")
                    return

                _save_setup_size_only()
                dialog.destroy()
                chat_window = ChatWindow(self, mode, room)
                self.active_chat_window = chat_window
                self.log(f"💬 Чат открыт в режиме: {mode}, комната: {room}")

            except Exception as e:
                play_error()
                messagebox.showerror("Ошибка", f"Чат не открылся:\n{e}")

        start_btn = make_sound_button(btn_frame, text="🚀 ЗАПУСТИТЬ ЧАТ", command=start_chat,
                                      fg_color="#6fce7f", hover_color="#5cb56c", text_color="#16141f",
                                      font=ctk.CTkFont(size=16, weight="bold"), height=50)
        start_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))

        cancel_btn = make_sound_button(btn_frame, text="❌ ОТМЕНА", command=_save_setup_size_and_close,
                                       fg_color="#d3453f", hover_color="#b83530", height=50,
                                       font=ctk.CTkFont(size=16, weight="bold"))
        cancel_btn.pack(side="right", fill="x", expand=True)

    def paste_ip_to_entry(self, entry):
        try:
            clipboard_text = self.clipboard_get()
            if clipboard_text:
                entry.delete(0, 'end')
                entry.insert(0, clipboard_text)
                play_click()
        except:
            play_error()
            messagebox.showinfo("Информация", "В буфере обмена пусто")

    def copy_ip_to_clipboard(self, ip):
        try:
            self.clipboard_clear()
            self.clipboard_append(ip)
            play_click()
            messagebox.showinfo("Скопировано", f"IP-адрес скопирован в буфер обмена:\n{ip}")
        except:
            play_error()
            messagebox.showerror("Ошибка", "IP не скопировался")

    def on_stats_refresh_click(self):
        play_click()
        self.update_stats_display()
        self.log("🔄 Статистика обновлена")

    def open_secret_launcher(self):
        try:
            if self._secret_launcher:
                try:
                    if self._secret_launcher.winfo_exists():
                        self._secret_launcher.focus_force()
                        self.log("ℹ️ Секретный лаунчер уже открыт")
                        return
                except:
                    pass

            self._secret_launcher = SecretGeometryDashLauncher(self)
            self._secret_launcher.focus_force()
            self.log("🎮 Секретный лаунчер открыт!")

            def on_close():
                if self._secret_launcher:
                    self._secret_launcher.destroy()
                    self._secret_launcher = None

            self._secret_launcher.protocol("WM_DELETE_WINDOW", on_close)

        except Exception as e:
            self.log(f"❌ Ошибка открытия секретного лаунчера: {e}")
            play_error()
            messagebox.showerror("Ошибка",
                                 f"Не удалось открыть секретный лаунчер:\n{e}\n\n"
                                 "Попробуйте перезапустить лаунчер.")

    def clear_console(self):
        self.console_text.delete("1.0", "end")
        self.console_text.insert("1.0", "[00:00:00] Консоль очищена\n")

    def copy_game_path(self):
        try:
            self.clipboard_clear()
            self.clipboard_append(MINECRAFT_DIR)
            play_click()
            messagebox.showinfo("Скопировано", f"Путь скопирован:\n{MINECRAFT_DIR}")
        except Exception as e:
            play_error()
            messagebox.showerror("Ошибка", f"Путь не скопировался:\n{e}")

    def copy_console_log(self):
        try:
            text = self.console_text.get("1.0", "end").strip()
            if not text:
                play_error()
                messagebox.showinfo("Информация", "Консоль пустая — копировать нечего")
                return
            self.clipboard_clear()
            self.clipboard_append(text)
            play_click()
            messagebox.showinfo("Скопировано", "Лог скопирован. Кидай в чат поддержки, если что-то сломалось")
        except Exception as e:
            play_error()
            messagebox.showerror("Ошибка", f"Лог не скопировался:\n{e}")

    def log(self, message):

        if threading.current_thread() is not threading.main_thread():
            try:
                self.after(0, lambda: self.log(message))
            except:
                print(f"LOG: {message}")
            return
        try:
            if hasattr(self, 'console_text') and self.console_text:
                timestamp = time.strftime("%H:%M:%S")
                self.console_text.insert("end", f"[{timestamp}] {message}\n")
                self.console_text.see("end")
        except:
            print(f"LOG: {message}")

    def on_closing(self):
        if self.timer_running:
            self.stop_game_timer()
        self._closing = True
        self.save_current_selection()
        try:
            self.destroy()
        except:
            pass


if __name__ == "__main__":
    multiprocessing.freeze_support()
    try:
        app = LauncherApp()
        app.mainloop()
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        import traceback

        traceback.print_exc()
        with open("error_log.txt", "w", encoding="utf-8") as f:
            f.write(f"Ошибка: {e}\n")
            f.write(traceback.format_exc())
        play_error()
        input("\nНажмите Enter для выхода...")
