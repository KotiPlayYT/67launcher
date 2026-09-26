import tkinter as tk


_boot_root = tk.Tk()
_boot_root.title("67Launcher")
_boot_root.configure(bg="#16141f")
try:
    _boot_root.overrideredirect(True)
except Exception:
    pass

tk.Label(_boot_root, text="⚡ 67Launcher", font=("Segoe UI", 20, "bold"),
         bg="#16141f", fg="#6d92ff").pack(pady=(24, 8), padx=40)
_boot_status_label = tk.Label(_boot_root, text="⏳ Загрузка...", font=("Segoe UI", 13),
                               bg="#16141f", fg="#a8a4bd")
_boot_status_label.pack(pady=(0, 24))

_boot_root.update_idletasks()
_bw = _boot_root.winfo_reqwidth() or 320
_bh = _boot_root.winfo_reqheight() or 120
_bsw = _boot_root.winfo_screenwidth()
_bsh = _boot_root.winfo_screenheight()
_boot_root.geometry(f"{_bw}x{_bh}+{(_bsw - _bw) // 2}+{(_bsh - _bh) // 2}")
_boot_root.update()


def _boot_tick(status=None):
    if status:
        try:
            _boot_status_label.configure(text=f"⏳ {status}")
        except Exception:
            pass
    try:
        _boot_root.update()
    except Exception:
        pass


_boot_tick("Запуск...")


import customtkinter as ctk
from tkinter import messagebox, filedialog
import minecraft_launcher_lib as mll
_boot_tick("Загрузка интерфейса...")
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
import random
_boot_tick("Загрузка сетевых модулей...")
import threading
import queue as _queue_module
import webbrowser
from pathlib import Path
import ssl
import certifi
from datetime import datetime
import pickle
_boot_tick("Загрузка изображений...")
from PIL import Image, ImageDraw, ImageFont, ImageTk, ImageSequence
from io import BytesIO
import socket
import base64
import re
import traceback
import hashlib
import uuid
_boot_tick("Загрузка чата и трея...")
import websocket as ws_client
from urllib.parse import unquote
import multiprocessing
import pystray
_boot_tick("Почти готово...")


try:
    import mss
except ImportError:
    mss = None
try:
    import pyautogui
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0
except ImportError:
    pyautogui = None

RELAY_URL_DEFAULT = "wss://screen-relay-production.up.railway.app"
RELAY_URL_API_SOURCE = "https://api.github.com/repos/KotiPlayYT/67launcher/contents/relay.active.txt?ref=main"
RELAY_URL_RAW_SOURCE = "https://raw.githubusercontent.com/KotiPlayYT/67launcher/main/relay.active.txt"
RELAY_URL = RELAY_URL_DEFAULT


def _extract_relay_candidate(text):
    text = (text or "").strip()
    return text.splitlines()[0].strip() if text else ""


def fetch_active_relay_url(timeout=5):
    global RELAY_URL
    candidate = ""
    source_used = None

    try:
        response = requests.get(
            RELAY_URL_API_SOURCE,
            timeout=timeout,
            headers={"User-Agent": "67Launcher", "Accept": "application/vnd.github.v3.raw"},
        )
        if response.status_code == 200:
            candidate = _extract_relay_candidate(response.text)
            source_used = "api"
        else:
            print(f"[relay] GitHub API вернул код {response.status_code}, пробую raw.githubusercontent.com")
    except Exception as e:
        print(f"[relay] GitHub API недоступен ({e}), пробую raw.githubusercontent.com")

    if not candidate:
        try:
            cache_buster = f"?_={int(time.time())}"
            response = requests.get(
                RELAY_URL_RAW_SOURCE + cache_buster,
                timeout=timeout,
                headers={"User-Agent": "67Launcher", "Cache-Control": "no-cache", "Pragma": "no-cache"},
            )
            if response.status_code == 200:
                candidate = _extract_relay_candidate(response.text)
                source_used = "raw"
            else:
                print(f"[relay] raw.githubusercontent.com вернул код {response.status_code}")
        except Exception as e:
            print(f"[relay] raw.githubusercontent.com недоступен: {e}")

    if candidate and (candidate.startswith("ws://") or candidate.startswith("wss://")):
        changed = candidate != RELAY_URL
        RELAY_URL = candidate
        print(f"[relay] Релей ({source_used}): {RELAY_URL}")
        if changed:
            # Релей приезжает с чужого сервера (GitHub) — показываем юзеру в UI,
            # куда именно уходят его сообщения, чтобы смена не была молчаливой
            _notify_relay_changed(RELAY_URL, source_used)
        return RELAY_URL, ("updated" if changed else "unchanged")
    elif candidate:
        print(f"[relay] relay.active.txt содержит не wss:// адрес ('{candidate}'), использую прежний: {RELAY_URL}")
        return RELAY_URL, "invalid_content"
    else:
        print(f"[relay] Не удалось получить relay.active.txt ни через API, ни через raw, использую прежний: {RELAY_URL}")
        return RELAY_URL, "network_error"


def _notify_relay_changed(url, source_used=None):
    """Релей приходит со стороны (файл relay.active.txt в чужом репозитории),
    поэтому его смена показывается в логе лаунчера, а не только в консоли."""
    try:
        app = LauncherApp.instance
        if app is None:
            return
        src = f" (источник: {source_used})" if source_used else ""

        def _show():
            app.log(f"⚠️ Релей ИЗМЕНЁН на {url}{src} — если не ожидал, открой Настройки чата и впиши свой.")

        app.after(0, _show)
    except Exception:
        pass


def _ws_sslopt():


    return {"cert_reqs": ssl.CERT_REQUIRED, "ca_certs": certifi.where()}


def check_room_active(relay_url, room, timeout=5):
    ws = ws_client.create_connection(relay_url, timeout=timeout, sslopt=_ws_sslopt())
    try:
        ws.settimeout(timeout)
        ws.send(json.dumps({"action": "check_room", "room": room}))
        raw = ws.recv()
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8')
        data = json.loads(raw)
        if data.get("type") != "room_status":
            raise RuntimeError(
                "релей не поддерживает проверку кода комнаты (нужно обновить relay.py на сервере)"
            )
        return bool(data.get("active")), int(data.get("count", 0)), int(data.get("max", 20))
    finally:
        try:
            ws.close()
        except:
            pass


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


def get_launcher_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def sanitize_shared_filename(name):
    name = unquote(name or "")
    name = os.path.basename(name.replace("\\", "/"))
    name = re.sub(r'[\\/:*?"<>|]', "_", name).strip().strip(".")
    if not name:
        name = "file.bin"
    return name[:150]


FIREWALL_RULE_NAMES = ("67Launcher Chat", "67Launcher Chat All")


def add_firewall_rule():
    """Добавляет правило фаервола для чата, но ТОЛЬКО после явного согласия юзера.
    Нужно лишь для прямого P2P-соединения; при работе через релей (по умолчанию)
    правило не требуется."""
    if sys.platform != "win32":
        return False

    try:
        result = subprocess.run(
            'netsh advfirewall firewall show rule name="67Launcher Chat"',
            capture_output=True, text=True, shell=True, encoding='cp866'
        )
        stdout = result.stdout or ""
        if "No rules match" not in stdout and "Не найдено" not in stdout:
            print("✅ Правило брандмауэра уже существует")
            return True
    except Exception as e:
        print(f"⚠️ Не удалось проверить правило брандмауэра: {e}")
        return False

    answer = messagebox.askyesno(
        "🔒 Добавить правило фаервола?",
        "Чат 67Launcher хочет открыть входящие TCP-порты 25565 и 25560–25570.\n\n"
        "Это нужно только для прямого P2P-соединения. Если ты используешь\n"
        "чат через релей (по умолчанию) — правило НЕ требуется.\n\n"
        "Добавить правило сейчас?\n"
        "(Позже можно удалить в Настройках → Безопасность)"
    )
    if not answer:
        print("ℹ️ Правило брандмауэра не добавлялось — отказ пользователя")
        return False

    try:
        for name, port in (
            ("67Launcher Chat", "25565"),
            ("67Launcher Chat All", "25560-25570"),
        ):
            subprocess.run(
                f'netsh advfirewall firewall add rule name="{name}" '
                f'dir=in action=allow protocol=TCP localport={port}',
                capture_output=True, text=True, shell=True, encoding='cp866'
            )
        print("✅ Правило брандмауэра добавлено (после согласия пользователя)")
        return True
    except Exception as e:
        print(f"⚠️ Не удалось добавить правило брандмауэра: {e}")
        return False


def remove_firewall_rule():
    """Удаляет правила 67Launcher из фаервола (для кнопки в настройках)."""
    if sys.platform != "win32":
        return False
    try:
        for name in FIREWALL_RULE_NAMES:
            subprocess.run(
                f'netsh advfirewall firewall delete rule name="{name}"',
                capture_output=True, text=True, shell=True, encoding='cp866'
            )
        print("🗑️ Правила брандмауэра 67Launcher удалены")
        return True
    except Exception as e:
        print(f"⚠️ Не удалось удалить правило брандмауэра: {e}")
        return False


def _url_domain(url):
    """Домен из ссылки для показа в диалоге подтверждения — чтобы юзер видел,
    КУДА он собирается перейти, а не только длинный адрес."""
    try:
        from urllib.parse import urlparse
        host = (urlparse(url).hostname or "").strip().lower()
        return host or "неизвестно"
    except Exception:
        return "неизвестно"


def _file_sha256(path, chunk_size=1 << 20):
    """SHA-256 файла блоками, чтобы не читать 500 МБ целиком в память.
    Возвращает None, если файл не удалось прочитать."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


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
        "ms_redirect_uri": "https://login.microsoftonline.com/common/oauth2/nativeclient",
        "user_id": "",
        "personal_chats": []
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


def generate_short_user_code():
    digits = "".join(random.choice("23456789") for _ in range(3))
    letters = "".join(random.choice("ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(3))
    return digits + letters


def ensure_user_id(settings):
    if not settings.get("user_id"):
        settings["user_id"] = generate_short_user_code()
        save_launcher_settings(settings)
    return settings["user_id"]


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


def has_microsoft_account():
    try:
        return any(acc.get("type") == "microsoft" for acc in load_accounts())
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
    try:
        parts = version.split('.')
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
        return (major, minor) < (1, 13)
    except Exception:
        return False


def get_forge_full_version(mc_version):
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


MAX_PERSONAL_CHATS = 10
class _ChatMessagebox:

    def __init__(self, window):
        self._window = window

    def __getattr__(self, name):
        func = getattr(messagebox, name)

        def call(*args, **kwargs):
            try:
                if "parent" not in kwargs and self._window.winfo_viewable():
                    kwargs["parent"] = self._window
            except Exception:
                pass
            return func(*args, **kwargs)
        return call


def release_and_destroy(window):
    try:
        window.grab_release()
    except Exception:
        pass
    window.destroy()


CHAT_HISTORY_MAX_LOAD = 200
CHAT_HISTORY_MAX_KEEP = 2000
_CHAT_HISTORY_LOCK = threading.Lock()

CHAT_URL_PATTERN = "https?://[^\\s<>\"']+"
CHAT_COMMAND_RE = re.compile(r"^/([A-Za-zА-Яа-яЁё?]+)(?:\s+(.*))?$", re.S)
CHAT_COMMAND_ALIASES = {
    "help": "help", "помощь": "help", "команды": "help", "?": "help",
    "roll": "roll", "кубик": "roll",
    "flip": "flip", "монетка": "flip",
    "choose": "choose", "выбери": "choose",
    "me": "me",
    "shrug": "shrug",
    "time": "time", "время": "time",
    "coords": "coords", "координаты": "coords", "коорд": "coords",
    "search": "search", "поиск": "search",
    "clear": "clear", "очистить": "clear",
    "export": "export", "экспорт": "export",
    "mute": "mute", "unmute": "unmute",
    "copy": "copy", "копировать": "copy",
}


def chat_history_path(contact_id):
    cid = str(contact_id or "")
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", cid)[:48] or "unknown"
    digest = hashlib.sha1(cid.encode("utf-8")).hexdigest()[:8]
    return os.path.join(os.path.dirname(SETTINGS_FILE), "chat_history", f"{safe}-{digest}.jsonl")


def append_chat_history(contact_id, text, mine):
    try:
        path = chat_history_path(contact_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        line = json.dumps({"ts": time.time(), "text": text, "mine": bool(mine)}, ensure_ascii=False)
        with _CHAT_HISTORY_LOCK:
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception:
        pass


def load_chat_history(contact_id, limit=CHAT_HISTORY_MAX_LOAD):
    path = chat_history_path(contact_id)
    entries = []
    try:
        with _CHAT_HISTORY_LOCK:
            if not os.path.exists(path):
                return []
            with open(path, "r", encoding="utf-8") as f:
                lines = f.read().split("\n")
            for line in lines:
                try:
                    item = json.loads(line)
                    msg = item["text"]
                    if isinstance(msg, str) and msg:
                        entries.append({"ts": float(item.get("ts", 0)), "text": msg,
                                        "mine": bool(item.get("mine"))})
                except Exception:
                    continue
            if len(entries) > CHAT_HISTORY_MAX_KEEP:
                entries = entries[-CHAT_HISTORY_MAX_KEEP:]
                try:
                    with open(path, "w", encoding="utf-8") as f:
                        for e in entries:
                            f.write(json.dumps(e, ensure_ascii=False) + "\n")
                except Exception:
                    pass
    except Exception:
        return []
    return entries[-limit:]


def delete_chat_history(contact_id):
    try:
        with _CHAT_HISTORY_LOCK:
            path = chat_history_path(contact_id)
            if os.path.exists(path):
                os.remove(path)
    except Exception:
        pass


def parse_roll_spec(arg):
    spec = (arg or "").strip().lower().replace("к", "d").replace("д", "d")
    if not spec:
        return 1, 6
    m = re.fullmatch(r"([0-9]{0,2})d([0-9]{1,4})", spec)
    if m:
        count, sides = int(m.group(1) or 1), int(m.group(2))
    elif re.fullmatch(r"[0-9]{1,4}", spec):
        count, sides = 1, int(spec)
    else:
        return None
    if not (1 <= count <= 20 and 2 <= sides <= 1000):
        return None
    return count, sides


def roll_dice(count, sides):
    rolls = [random.randint(1, sides) for _ in range(count)]
    return rolls, sum(rolls)


def convert_coords(arg):
    tokens = (arg or "").replace(",", " ").split()
    world = "overworld"
    if tokens and re.fullmatch(r"[A-Za-zА-Яа-яЁё]+", tokens[-1]):
        word = tokens.pop().lower()
        if word in ("nether", "незер", "ад", "нижний"):
            world = "nether"
        elif word in ("end", "энд", "край"):
            world = "end"
        elif word in ("overworld", "world", "верх", "верхний", "обычный", "овер", "мир"):
            world = "overworld"
        else:
            return None
    try:
        nums = [int(float(t)) for t in tokens]
    except (ValueError, OverflowError):
        return None
    if any(abs(n) > 30000000 for n in nums):
        return None
    if len(nums) == 2:
        x, z = nums
        y = None
    elif len(nums) == 3:
        x, y, z = nums
    else:
        return None
    names = {"overworld": "Верхний мир", "nether": "Незер", "end": "Энд"}
    pos = f"X {x}, " + (f"Y {y}, " if y is not None else "") + f"Z {z}"
    result = f"📍 {names[world]}: {pos}"
    if world == "overworld":
        result += f" → в Незере: X {x // 8}, Z {z // 8}"
    elif world == "nether":
        result += f" → в Верхнем мире: X {x * 8}, Z {z * 8}"
    return result


def format_utc_offset(minutes):
    sign = "+" if minutes >= 0 else "-"
    hours, mins = divmod(abs(int(minutes)), 60)
    return f"UTC{sign}{hours}" + (f":{mins:02d}" if mins else "")


def trim_link_tail(url):
    while url:
        last = url[-1]
        if last in ".,;:!?»]}":
            url = url[:-1]
        elif last == ")" and url.count(")") > url.count("("):
            url = url[:-1]
        else:
            break
    return url


SCREEN_SHARE_MAX_WIDTH = 640        
SCREEN_SHARE_JPEG_QUALITY = 25      
SCREEN_SHARE_INTERVAL = 1 / 6      
SCREEN_SHARE_REQUEST_TIMEOUT = 30
SCREEN_SHARE_MOVE_THROTTLE = 0.05  
SCREEN_SHARE_MAX_CONSECUTIVE_ERRORS = 8  

_TK_TO_PYAUTOGUI_KEYS = {
    "Return": "enter", "KP_Enter": "enter", "Escape": "esc", "BackSpace": "backspace",
    "Tab": "tab", "space": "space", "Delete": "delete", "Insert": "insert",
    "Up": "up", "Down": "down", "Left": "left", "Right": "right",
    "Home": "home", "End": "end", "Prior": "pageup", "Next": "pagedown",
    "Shift_L": "shiftleft", "Shift_R": "shiftright",
    "Control_L": "ctrlleft", "Control_R": "ctrlright",
    "Alt_L": "altleft", "Alt_R": "altright",
    "Super_L": "winleft", "Super_R": "winright",
    "Caps_Lock": "capslock", "Num_Lock": "numlock",
    "F1": "f1", "F2": "f2", "F3": "f3", "F4": "f4", "F5": "f5", "F6": "f6",
    "F7": "f7", "F8": "f8", "F9": "f9", "F10": "f10", "F11": "f11", "F12": "f12",
    "minus": "-", "equal": "=", "comma": ",", "period": ".", "slash": "/",
    "backslash": "\\", "bracketleft": "[", "bracketright": "]",
    "semicolon": ";", "apostrophe": "'", "grave": "`",
}


def _map_tk_keysym_to_pyautogui(keysym):
    if not keysym:
        return None
    if keysym in _TK_TO_PYAUTOGUI_KEYS:
        return _TK_TO_PYAUTOGUI_KEYS[keysym]
    if len(keysym) == 1:
        return keysym if keysym.isalpha() or keysym.isdigit() else keysym
    return None


class _ScreenShareHostBanner(ctk.CTkToplevel):

    def __init__(self, chat_window, viewer_username):
        super().__init__(chat_window)
        self.chat_window = chat_window
        try:
            self.overrideredirect(True)
        except Exception:
            pass
        try:
            self.attributes("-topmost", True)
        except Exception:
            pass
        try:
            self.attributes("-alpha", 0.94)
        except Exception:
            pass
        self.configure(fg_color="#8b2f2f")
        width, height = 380, 46
        try:
            sw = self.winfo_screenwidth()
        except Exception:
            sw = width
        self.geometry(f"{width}x{height}+{max(0, (sw - width) // 2)}+12")

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="both", expand=True, padx=8, pady=6)
        ctk.CTkLabel(
            row,
            text=f"🔴 Твой экран и управление транслируются «{viewer_username}»",
            text_color="white",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(side="left", padx=(4, 8))
        ctk.CTkButton(
            row, text="⏹ Стоп", width=70, fg_color="#5a1c1c", hover_color="#712323",
            command=self._stop,
        ).pack(side="right")

    def _stop(self):
        self.chat_window.stop_screen_share()


class RemoteScreenWindow(ctk.CTkToplevel):

    def __init__(self, chat_window, peer_username, request_id):
        super().__init__(chat_window)
        self.chat_window = chat_window
        self.peer_username = peer_username
        self.request_id = request_id

        self.title(f"🖥️ Экран «{peer_username}»")
        self.geometry("1040x660")
        self.minsize(480, 320)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.configure(fg_color="#0c0c0c")

        self._orig_w = 1920
        self._orig_h = 1080
        self._img_w = 0
        self._img_h = 0
        self._photo = None
        self._last_move_ts = 0.0

        top = ctk.CTkFrame(self, fg_color="#161616", height=34)
        top.pack(side="top", fill="x")
        ctk.CTkLabel(
            top,
            text=f"🖥️ Управляешь экраном «{peer_username}» — мышь и клавиатура передаются в реальном времени",
            text_color="#8fd18f",
            font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=10, pady=6)
        ctk.CTkButton(
            top, text="⏹ Остановить", width=120, fg_color="#8b2f2f", hover_color="#a53a3a",
            command=self._on_close,
        ).pack(side="right", padx=8, pady=4)

        self.canvas = tk.Label(self, bg="black", anchor="nw")
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<ButtonPress-1>", lambda e: self._on_button(e, "left", True))
        self.canvas.bind("<ButtonRelease-1>", lambda e: self._on_button(e, "left", False))
        self.canvas.bind("<ButtonPress-3>", lambda e: self._on_button(e, "right", True))
        self.canvas.bind("<ButtonRelease-3>", lambda e: self._on_button(e, "right", False))
        self.canvas.bind("<ButtonPress-2>", lambda e: self._on_button(e, "middle", True))
        self.canvas.bind("<ButtonRelease-2>", lambda e: self._on_button(e, "middle", False))
        self.canvas.bind("<Double-Button-1>", self._on_double_click)
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<Button-4>", lambda e: self._send_input({"action": "scroll", "dy": 60}))
        self.canvas.bind("<Button-5>", lambda e: self._send_input({"action": "scroll", "dy": -60}))

        self.canvas.bind("<KeyPress>", self._on_key_press, add=True)
        self.canvas.bind("<KeyRelease>", self._on_key_release, add=True)
        self.bind("<FocusIn>", lambda e: self.canvas.focus_set())
        self.canvas.focus_set()

    def update_frame(self, img, orig_w, orig_h):
        self._orig_w = max(1, orig_w)
        self._orig_h = max(1, orig_h)
        self._img_w = img.width
        self._img_h = img.height
        self._photo = ImageTk.PhotoImage(img)
        try:
            self.canvas.configure(image=self._photo)
        except Exception:
            pass

    def _scale(self, x, y):
        if not self._img_w or not self._img_h:
            return None
        x = max(0, min(x, self._img_w - 1))
        y = max(0, min(y, self._img_h - 1))
        rx = int(x * self._orig_w / self._img_w)
        ry = int(y * self._orig_h / self._img_h)
        return rx, ry

    def _send_input(self, extra):
        self.chat_window.send_remote_input(self.peer_username, self.request_id, extra)

    def _on_motion(self, event):
        now = time.time()
        if now - self._last_move_ts < SCREEN_SHARE_MOVE_THROTTLE:
            return
        self._last_move_ts = now
        pt = self._scale(event.x, event.y)
        if pt:
            self._send_input({"action": "move", "x": pt[0], "y": pt[1]})

    def _on_button(self, event, button, pressed):
        self.canvas.focus_set()
        pt = self._scale(event.x, event.y)
        if not pt:
            return
        self._send_input({"action": "down" if pressed else "up", "x": pt[0], "y": pt[1], "button": button})

    def _on_double_click(self, event):
        pt = self._scale(event.x, event.y)
        if pt:
            self._send_input({"action": "double_click", "x": pt[0], "y": pt[1], "button": "left"})

    def _on_wheel(self, event):
        delta = event.delta if getattr(event, "delta", 0) else 0
        self._send_input({"action": "scroll", "dy": delta})

    def _on_key_press(self, event):
        self._send_input({"action": "key_down", "key": event.keysym})

    def _on_key_release(self, event):
        self._send_input({"action": "key_up", "key": event.keysym})

    def _on_close(self):
        self.chat_window.stop_screen_share()


class ChatWindow(ctk.CTkToplevel):
    def __init__(self, master, mode="server", room="", relay_url=None, personal_contact=None):
        super().__init__(master)
        self.master = master
        self.mode = mode
        self.role = "streamer" if mode == "server" else "viewer"
        self.room = room
        self.relay_url = (relay_url or RELAY_URL).strip() or RELAY_URL
        self.personal_contact = personal_contact
        self.running = True
        self.connected = False
        self.client_socket = None
        self.username = "Игрок"
        self.message_history = []
        self.is_minimized = False
        self.unread_count = 0
        self.participant_count = 1
        self.max_room_size = 20


        self._socket_lock = threading.Lock()


        self._screen_share = {}
        self._screen_share_streaming = False
        self._remote_screen_window = None
        self._screen_share_banner = None
        self._screen_share_prompt_active = False

        self.muted = bool(personal_contact.get("muted", False)) if personal_contact else False
        self._input_history = []
        self._input_history_pos = None
        self._input_draft = ""
        self._search_visible = False
        self._search_matches = []
        self._search_index = -1
        self._search_last_query = None

        self.notifications_enabled = True
        self.notification_size = 100
        try:
            self.notifications_enabled = bool(master.settings.get("chat_notifications_enabled", True))
            self.notification_size = int(master.settings.get("chat_notification_size", 100))
        except:
            pass

        self.update_title()
        self._apply_chat_window_geometry()
        self.minsize(800, 800)
        self.resizable(True, True)
        self.after(80, self._apply_chat_window_geometry)

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
        self._clear_personal_unread()
        self._load_personal_history()
        self._show_chat_loading_overlay()
        self._start_connection()

    def _find_chat_loading_gif_path(self):
        candidates = [
            resource_path(os.path.join("resources", "zagruzkachat.gif")),
            os.path.join(get_launcher_dir(), "resources", "zagruzkachat.gif"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "zagruzkachat.gif"),
        ]
        if hasattr(sys, "_MEIPASS"):
            candidates.insert(0, os.path.join(sys._MEIPASS, "resources", "zagruzkachat.gif"))
        for path in candidates:
            if os.path.isfile(path):
                return path
        return None

    def _show_chat_loading_overlay(self):
        if getattr(self, "_chat_loading_overlay", None) is not None:
            return
        try:
            self._chat_loading_overlay = ctk.CTkFrame(self, fg_color="#16141f")
            self._chat_loading_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
            inner = ctk.CTkFrame(self._chat_loading_overlay, fg_color="transparent")
            inner.place(relx=0.5, rely=0.5, anchor="center")
            self._chat_loading_gif_label = ctk.CTkLabel(inner, text="")
            self._chat_loading_gif_label.pack()
            ctk.CTkLabel(inner, text="⏳ Подключение к чату...",
                         font=ctk.CTkFont(size=15, weight="bold"),
                         text_color="#a8a4bd").pack(pady=(12, 0))
        except Exception as e:
            print(f"[chat_loading] Не удалось создать оверлей загрузки: {e}")
            self._chat_loading_overlay = None
            return
        self._chat_loading_gif_running = True
        self._chat_loading_gif_frames = []
        self._load_chat_loading_gif()

    def _hide_chat_loading_overlay(self):
        self._chat_loading_gif_running = False
        overlay = getattr(self, "_chat_loading_overlay", None)
        if overlay is not None:
            try:
                overlay.destroy()
            except Exception:
                pass
            self._chat_loading_overlay = None

    def _load_chat_loading_gif(self):
        gif_path = self._find_chat_loading_gif_path()
        if not gif_path:
            print("[chat_loading] resources/zagruzkachat.gif не найден рядом ни с main.py, "
                  "ни в рабочей папке процесса — гифка загрузки чата не покажется")
            return
        try:
            img = Image.open(gif_path)
            frames = []
            for frame in ImageSequence.Iterator(img):
                duration = frame.info.get("duration", 80)
                frames.append((frame.convert("RGBA").copy(), max(int(duration), 20)))
            if not frames:
                return
        except Exception as e:
            print(f"[chat_loading] Не удалось загрузить {gif_path}: {e}")
            return
        self._start_chat_loading_gif(frames)

    def _start_chat_loading_gif(self, frames):
        if not getattr(self, "_chat_loading_gif_running", False):
            return
        try:
            if not self._chat_loading_gif_label.winfo_exists():
                return
        except Exception:
            return
        size = frames[0][0].size
        self._chat_loading_gif_frames = [
            (ctk.CTkImage(light_image=im, dark_image=im, size=size), dur) for im, dur in frames
        ]
        self._chat_loading_gif_index = 0
        self._animate_chat_loading_gif()

    def _animate_chat_loading_gif(self):
        if not self._chat_loading_gif_running or not self._chat_loading_gif_frames:
            return
        try:
            if not self._chat_loading_gif_label.winfo_exists():
                return
        except Exception:
            return
        image, duration = self._chat_loading_gif_frames[self._chat_loading_gif_index]
        try:
            self._chat_loading_gif_label.configure(image=image)
        except Exception:
            return
        self._chat_loading_gif_index = (self._chat_loading_gif_index + 1) % len(self._chat_loading_gif_frames)
        self.after(duration, self._animate_chat_loading_gif)

    def _start_connection(self, run_diagnostics=True):
        first_time = not getattr(self.master, "_chat_init_log_shown", False)
        if first_time:
            self.log(f"🔍 Инициализация чата в режиме: {self.mode} (комната «{self.room}»)")
            if run_diagnostics:
                threading.Thread(target=self.run_diagnostics, daemon=True).start()
        threading.Thread(target=self.run_relay, daemon=True).start()

    def _apply_chat_window_geometry(self):
        try:
            self.update_idletasks()
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()

            width = max(700, min(1400, int(screen_w * 0.72)))
            height = max(600, min(1000, int(screen_h * 0.80)))

            x = (screen_w - width) // 2
            y = (screen_h - height) // 2

            self._chat_window_size = (width, height)
            self.wm_geometry(f"{width}x{height}+{x}+{y}")
        except Exception:
            pass

    def run_diagnostics(self):
        self.log("━" * 50)
        self.log("🔧 ДИАГНОСТИКА СЕТИ:")
        try:
            socket.gethostbyname('google.com')
            self.log("✅ Интернет соединение: Есть")
        except:
            self.log("❌ Интернет соединение: Нет")
        self.log(f"🌐 Релей: {self.relay_url}")
        self.log(f"🚪 Комната: {self.room}")
        self.log("━" * 50)

    def restore_chat_only(self, event=None):
        self.deiconify()
        self.lift()
        try:


            self.attributes("-topmost", True)

            def _drop_topmost():
                try:
                    self.attributes("-topmost", False)
                except Exception:
                    pass
            self.after(300, _drop_topmost)
        except Exception:
            pass
        self.focus_force()
        try:
            self.master.active_chat_window = self
        except Exception:
            pass
        self.is_minimized = False
        self.unread_count = 0
        self.update_title()
        self._clear_personal_unread()

    def on_minimize(self, event):
        if event.widget is not self:
            return
        self.is_minimized = True

    def on_restore(self, event):
        if event.widget is not self:
            return
        self.is_minimized = False
        self.unread_count = 0
        self.update_title()
        self._clear_personal_unread()

    def update_title(self):
        if self.personal_contact:
            base = f"💬 Чат с «{self.personal_contact.get('name', '???')}»"
        else:
            base = "💬 Чат 67Launcher"
        if self.unread_count > 0:
            self.title(f"{base} ({self.unread_count} новых)")
        else:
            self.title(base)

    def _update_personal_preview(self, text, mine):
        if threading.current_thread() is not threading.main_thread():
            try:
                self.after(0, lambda: self._update_personal_preview(text, mine))
            except Exception:
                pass
            return
        if not self.personal_contact:
            return
        try:
            settings = getattr(self.master, "settings", None)
            if settings is None:
                return
            contact_id = self.personal_contact.get("id")
            contacts = settings.setdefault("personal_chats", [])
            changed = False
            for c in contacts:
                if c.get("id") == contact_id:
                    c["last_message"] = (text or "")[:200]
                    c["last_message_time"] = datetime.now().strftime("%d.%m %H:%M")
                    c["last_message_ts"] = datetime.now().timestamp()
                    c["last_message_mine"] = bool(mine)
                    c["unread"] = False if mine else True
                    changed = True
                    break
            if changed:
                save_launcher_settings(settings)
                refresh_cb = getattr(self.master, "chats_list_refresh_callback", None)
                if refresh_cb:
                    try:
                        refresh_cb()
                    except Exception:
                        pass
        except Exception:
            pass

    def _clear_personal_unread(self):
        if not self.personal_contact:
            return
        try:
            settings = getattr(self.master, "settings", None)
            if settings is None:
                return
            contact_id = self.personal_contact.get("id")
            contacts = settings.setdefault("personal_chats", [])
            changed = False
            for c in contacts:
                if c.get("id") == contact_id and c.get("unread"):
                    c["unread"] = False
                    changed = True
                    break
            if changed:
                save_launcher_settings(settings)
                refresh_cb = getattr(self.master, "chats_list_refresh_callback", None)
                if refresh_cb:
                    try:
                        refresh_cb()
                    except Exception:
                        pass
        except Exception:
            pass

    def _broadcast_dm_identity(self):
        if not self.personal_contact:
            return
        if not self.client_socket or not self.connected:
            return
        try:
            my_id = ensure_user_id(self.master.settings)
        except Exception:
            return


        contact_name = (self.personal_contact.get("name") or "").strip() or self.username
        try:
            self._socket_send(json.dumps({
                "type": "dm_identity",
                "user_id": my_id,
                "username": self.username,
                "contact_name": contact_name,
            }))
        except Exception:
            pass

    def _auto_add_contact(self, their_id, suggested_name):
        try:
            settings = getattr(self.master, "settings", None)
            if settings is None:
                return
            contacts = settings.setdefault("personal_chats", [])
            for c in contacts:
                if c.get("id") == their_id:


                    if (not c.get("name") or c.get("name") == c.get("id")) and suggested_name:
                        c["name"] = suggested_name
                        save_launcher_settings(settings)
                        refresh_cb = getattr(self.master, "chats_list_refresh_callback", None)
                        if refresh_cb:
                            try:
                                refresh_cb()
                            except Exception:
                                pass
                    return

            if len(contacts) >= MAX_PERSONAL_CHATS:
                return

            contacts.append({
                "id": their_id,
                "name": suggested_name or their_id,
                "last_message": "",
                "last_message_time": "",
                "last_message_ts": 0,
                "last_message_mine": False,
                "unread": False,
            })
            save_launcher_settings(settings)
            self.log(f"➕ «{suggested_name}» автоматически добавлен(а) в «Чаты» — писать можно в любое время")

            try:
                if not hasattr(self.master, "active_chat_windows"):
                    self.master.active_chat_windows = {}
                self.master.active_chat_windows[their_id] = self
            except Exception:
                pass

            refresh_cb = getattr(self.master, "chats_list_refresh_callback", None)
            if refresh_cb:
                try:
                    refresh_cb()
                except Exception:
                    pass
        except Exception:
            pass


    def _get_sorted_personal_chats(self):
        try:
            contacts = self.master.settings.get("personal_chats", [])
        except Exception:
            contacts = []
        return sorted(contacts, key=lambda c: c.get("last_message_ts", 0), reverse=True)

    def _go_to_sibling_chat(self, direction):
        if not self.personal_contact or getattr(self, "_transition_running", False):
            return
        contacts = self._get_sorted_personal_chats()
        if len(contacts) < 2:
            play_error()
            return
        my_contact_id = self.personal_contact.get("id")
        idx = next((i for i, c in enumerate(contacts) if c.get("id") == my_contact_id), None)
        if idx is None:
            idx = 0
        new_contact = contacts[(idx + direction) % len(contacts)]
        if new_contact.get("id") == my_contact_id:
            return
        play_click()
        self._slide_transition(lambda: self._apply_contact_switch(new_contact), direction=direction)

    def _apply_contact_switch(self, new_contact):
        old_contact = self.personal_contact
        try:
            if old_contact and hasattr(self.master, "active_chat_windows"):
                old_id = old_contact.get("id")
                if self.master.active_chat_windows.get(old_id) is self:
                    del self.master.active_chat_windows[old_id]
        except Exception:
            pass

        self.running = False
        self.disconnect()
        self.running = True

        self.personal_contact = new_contact
        self.muted = bool(new_contact.get("muted", False))
        try:
            self.mute_btn.configure(text="🔕 Без звука" if self.muted else "🔔 Уведомления")
        except Exception:
            pass

        try:
            my_id = ensure_user_id(self.master.settings)
        except Exception:
            my_id = ""
        their_id = new_contact.get("id")
        self.room = "dm-" + "-".join(sorted([my_id, their_id]))

        try:
            if not hasattr(self.master, "active_chat_windows"):
                self.master.active_chat_windows = {}
            self.master.active_chat_windows[their_id] = self
            self.master.active_chat_window = self
        except Exception:
            pass

        try:
            self.contact_name_lbl.configure(text=new_contact.get("name", "???"))
            self.contact_avatar_lbl.configure(image=make_avatar_image(new_contact.get("name") or "?", size=38))
        except Exception:
            pass
        self.update_title()

        try:
            self.chat_display.configure(state="normal")
            self.chat_display.delete("1.0", "end")
            self.chat_display.insert("1.0", "💬 Чат готов к работе... (команды — /help, поиск — Ctrl+F)\n")
            self.chat_display.insert("end", "━" * 50 + "\n")
            self.chat_display.configure(state="disabled")
        except Exception:
            pass

        self.message_history = []
        self.update_msg_count()
        self._clear_personal_unread()
        self._load_personal_history()
        self.participant_count = 1
        self.update_participant_status()

        try:
            if hasattr(self, "connection_info_label"):
                self.connection_info_label.configure(text=f"🔗 Комната: {self.room}")
        except Exception:
            pass
        try:
            self.status_label.configure(text="🔴 Ожидание", text_color="#d3453f")
        except Exception:
            pass

        relay_url = self.relay_url

        def do_negotiate():
            try:
                active, _c, _m = check_room_active(relay_url, self.room, timeout=5)
                negotiated_mode = "client" if active else "server"
            except Exception:
                negotiated_mode = "server"
            self.mode = negotiated_mode
            self.role = "streamer" if negotiated_mode == "server" else "viewer"
            try:
                self.after(0, lambda: self._start_connection(run_diagnostics=False))
            except Exception:
                pass

        threading.Thread(target=do_negotiate, daemon=True).start()

    def _safe_alive(self):
        try:
            return bool(self.winfo_exists())
        except Exception:
            return False

    def _slide_transition(self, swap_callback, direction=1):
        if getattr(self, "_transition_running", False):
            swap_callback()
            return
        try:
            self.chat_display.update_idletasks()
            parent = self.chat_display.master
            x = self.chat_display.winfo_x()
            y = self.chat_display.winfo_y()
            w = self.chat_display.winfo_width()
            h = self.chat_display.winfo_height()
            if w <= 1 or h <= 1:
                swap_callback()
                return
        except Exception:
            swap_callback()
            return

        self._transition_running = True
        sign = 1 if direction >= 0 else -1
        overlay = ctk.CTkFrame(parent, fg_color="#100e1a", corner_radius=8)
        steps = 8

        def step_in(i=0):
            if not self._safe_alive():
                self._transition_running = False
                return
            frac = (i + 1) / steps
            offset = int(w * (1 - frac)) * sign
            try:
                overlay.place(x=x + offset, y=y, width=w, height=h)
            except Exception:
                pass
            if i + 1 < steps:
                self.after(10, lambda: step_in(i + 1))
            else:
                try:
                    overlay.place(x=x, y=y, width=w, height=h)
                except Exception:
                    pass
                self.after(40, do_swap)

        def do_swap():
            try:
                swap_callback()
            except Exception:
                pass
            self.after(10, lambda: step_out(0))

        def step_out(i=0):
            if not self._safe_alive():
                try:
                    overlay.destroy()
                except Exception:
                    pass
                self._transition_running = False
                return
            frac = (i + 1) / steps
            offset = int(w * frac) * (-sign)
            try:
                overlay.place(x=x + offset, y=y, width=w, height=h)
            except Exception:
                pass
            if i + 1 < steps:
                self.after(10, lambda: step_out(i + 1))
            else:
                try:
                    overlay.destroy()
                except Exception:
                    pass
                self._transition_running = False

        step_in()

    def show_notification(self, message, sender="", title=None, force=False):
        if threading.current_thread() is not threading.main_thread():
            try:
                self.after(0, lambda: self.show_notification(message, sender, title, force))
            except:
                pass
            return
        if self.is_minimized:
            self.unread_count += 1
            self.update_title()
        if not force and (getattr(self, 'muted', False) or not getattr(self, 'notifications_enabled', True)):
            return
        try:
            scale = max(50, min(200, getattr(self, 'notification_size', 100))) / 100.0

            notif = tk.Toplevel(self)
            notif.title("")
            notif.overrideredirect(True)
            notif.attributes('-topmost', True)

            width, height = int(380 * scale), int(132 * scale)

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

            frame = tk.Frame(notif, bg="#100e1a", highlightbackground="#302c46", highlightthickness=1, cursor="hand2")
            frame.pack(fill="both", expand=True, padx=2, pady=2)

            def on_notif_click(e=None):
                notif.destroy()
                self.restore_chat_only()

            frame.bind("<Button-1>", on_notif_click)


            if self.personal_contact:
                kind_text, kind_color = "личные", "#ffb35c"
            else:
                kind_text, kind_color = "груп.чат", "#6fce7f"
            kind_label = tk.Label(frame, text=kind_text, font=("Segoe UI", max(6, int(8 * scale))),
                                  bg="#100e1a", fg=kind_color)
            kind_label.pack(anchor="w", padx=15, pady=(6, 0))
            kind_label.bind("<Button-1>", on_notif_click)

            header_frame = tk.Frame(frame, bg="#100e1a")
            header_frame.pack(fill="x", padx=15, pady=(2, 5))
            header_frame.bind("<Button-1>", on_notif_click)

            title_color = "#6d92ff"
            if sender:
                try:
                    accounts = load_accounts()
                    for acc in accounts:
                        if acc["username"] == sender and acc.get("type") == "microsoft":
                            title_color = "#FFD700"
                            break
                except:
                    pass

            title_text = title if title else (f"💬 {sender}" if sender else "💬 Новое сообщение")

            l1 = tk.Label(header_frame, text=title_text, font=("Segoe UI", max(8, int(12 * scale)), "bold"),
                         bg="#100e1a", fg=title_color)
            l1.pack(side="left")
            l1.bind("<Button-1>", on_notif_click)

            close_btn = tk.Button(header_frame, text="✕", command=notif.destroy,
                                  bg="#100e1a", fg="#e5e2f0", activebackground="#d3453f",
                                  activeforeground="#e5e2f0", relief="flat", bd=0,
                                  font=("Segoe UI", max(7, int(10 * scale))), cursor="hand2")
            close_btn.pack(side="right")

            msg_text = message[:80] + "..." if len(message) > 80 else message
            l2 = tk.Label(frame, text=msg_text, font=("Segoe UI", max(7, int(11 * scale))), bg="#100e1a", fg="#e5e2f0",
                         wraplength=int(350 * scale), justify="left")
            l2.pack(padx=15, pady=(5, 10), anchor="w")
            l2.bind("<Button-1>", on_notif_click)

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

    def _save_chat_settings(self):
        try:
            self.master.settings["chat_notifications_enabled"] = self.notifications_enabled
            self.master.settings["chat_notification_size"] = self.notification_size
            save_launcher_settings(self.master.settings)
        except:
            pass

    def open_chat_settings(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("⚙️ Настройки чата")
        dialog.geometry("420x360")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        dialog.update_idletasks()
        width = dialog.winfo_width()
        height = dialog.winfo_height()
        x = self.winfo_x() + (self.winfo_width() // 2) - (width // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (height // 2)
        dialog.geometry(f"{width}x{height}+{x}+{y}")

        main = ctk.CTkFrame(dialog, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(main, text="⚙️ Настройки уведомлений чата",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", pady=(0, 15))

        notif_switch_var = ctk.BooleanVar(value=self.notifications_enabled)

        def on_switch_toggle():
            self.notifications_enabled = bool(notif_switch_var.get())
            self._save_chat_settings()
            play_click()
            size_slider.configure(state="normal" if self.notifications_enabled else "disabled")
            preview_btn.configure(state="normal" if self.notifications_enabled else "disabled")

        notif_switch = ctk.CTkSwitch(main, text="🔔 Показывать всплывающие уведомления",
                                     variable=notif_switch_var, onvalue=True, offvalue=False,
                                     command=on_switch_toggle,
                                     font=ctk.CTkFont(size=13),
                                     progress_color="#6fce7f")
        notif_switch.pack(anchor="w", pady=(0, 20))

        size_header = ctk.CTkFrame(main, fg_color="transparent")
        size_header.pack(fill="x")
        ctk.CTkLabel(size_header, text="📏 Размер уведомлений",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        size_value_label = ctk.CTkLabel(size_header, text=f"{self.notification_size}%",
                                        font=ctk.CTkFont(size=13, weight="bold"), text_color="#6d92ff")
        size_value_label.pack(side="right")

        def on_size_change(value):
            size = int(round(value / 10.0) * 10)
            size_value_label.configure(text=f"{size}%")
            self.notification_size = size

        size_slider = ctk.CTkSlider(main, from_=50, to=200, number_of_steps=15,
                                    command=on_size_change,
                                    progress_color="#6d92ff", button_color="#6d92ff",
                                    button_hover_color="#5a7dd8")
        size_slider.set(self.notification_size)
        size_slider.pack(fill="x", pady=(8, 2))
        size_slider.configure(state="normal" if self.notifications_enabled else "disabled")

        scale_frame = ctk.CTkFrame(main, fg_color="transparent")
        scale_frame.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(scale_frame, text="Меньше", font=ctk.CTkFont(size=10), text_color="#a8a4bd").pack(side="left")
        ctk.CTkLabel(scale_frame, text="Больше", font=ctk.CTkFont(size=10), text_color="#a8a4bd").pack(side="right")

        def on_slider_release(event=None):
            self._save_chat_settings()
            play_click()

        size_slider.bind("<ButtonRelease-1>", on_slider_release)

        preview_btn = make_sound_button(main, text="👁️ Показать пример уведомления",
                                        command=lambda: self.show_notification(
                                            "Вот так будут выглядеть уведомления в чате",
                                            "Тест", title="🔔 Пример уведомления", force=True),
                                        fg_color="#6d92ff", hover_color="#5a7dd8", height=35,
                                        font=ctk.CTkFont(size=12))
        preview_btn.pack(fill="x", pady=(0, 10))
        preview_btn.configure(state="normal" if self.notifications_enabled else "disabled")

        def close_dialog():
            self._save_chat_settings()
            dialog.destroy()

        close_btn = make_sound_button(main, text="✅ Готово", command=close_dialog,
                                      fg_color="#6fce7f", hover_color="#5cb56c",
                                      text_color="#16141f", height=40,
                                      font=ctk.CTkFont(size=13, weight="bold"))
        close_btn.pack(fill="x", side="bottom")

        dialog.protocol("WM_DELETE_WINDOW", close_dialog)

    def copy_ip_to_clipboard(self, ip):
        try:
            self.clipboard_clear()
            self.clipboard_append(ip)
            play_click()
            self._mb.showinfo("Скопировано", f"Скопировано в буфер обмена:\n{ip}")
        except:
            play_error()
            self._mb.showerror("Ошибка", "Не скопировалось")

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
        left_header.pack(side="left", fill="x", expand=True)

        if self.personal_contact:
            self.prev_chat_btn = make_sound_button(left_header, text="‹",
                                                    command=lambda: self._go_to_sibling_chat(-1),
                                                    width=34, height=34,
                                                    fg_color="#201d30", hover_color="#3d3a52",
                                                    font=ctk.CTkFont(size=18, weight="bold"))
            self.prev_chat_btn.pack(side="left", padx=(0, 8))

            self.contact_avatar_lbl = ctk.CTkLabel(
                left_header, image=make_avatar_image(self.personal_contact.get("name") or "?", size=38), text="")
            self.contact_avatar_lbl.pack(side="left", padx=(0, 10))

            self.contact_name_lbl = ctk.CTkLabel(left_header, text=self.personal_contact.get("name", "???"),
                                                 font=ctk.CTkFont(size=20, weight="bold"), text_color="#6d92ff")
            self.contact_name_lbl.pack(side="left")

            self.next_chat_btn = make_sound_button(left_header, text="›",
                                                    command=lambda: self._go_to_sibling_chat(1),
                                                    width=34, height=34,
                                                    fg_color="#201d30", hover_color="#3d3a52",
                                                    font=ctk.CTkFont(size=18, weight="bold"))
            self.next_chat_btn.pack(side="left", padx=(8, 0))
        else:
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

        self.chat_display = ctk.CTkTextbox(main_frame, font=ctk.CTkFont(family="Segoe UI", size=14), height=350)
        self.chat_display.pack(fill="both", expand=True, pady=(0, 10))
        self.chat_display.insert("1.0", "💬 Чат готов к работе... (команды — /help, поиск — Ctrl+F)\n")
        self.chat_display.insert("end", "━" * 50 + "\n")
        self.chat_display.configure(state="disabled")

        try:
            tw = self.chat_display._textbox
            tw.configure(spacing1=3, spacing3=10)


            self.chat_display.tag_config("msg_mine", justify="left", foreground="#bcd2ff",
                                          rmargin=60)
            self.chat_display.tag_config("msg_theirs", justify="right", foreground="#e5e2f0",
                                          lmargin1=60, lmargin2=60)
            self.chat_display.tag_config("msg_system", justify="center", foreground="#8b87a3")
            self.chat_display.tag_config("msg_info", justify="left", foreground="#a8a4bd")


            tw.tag_config("chat_ts", foreground="#6d6785",
                          font=("Segoe UI", 11))

            self.chat_display.tag_config("gold_chat_nick", foreground="#FFD700")
            self.chat_display.tag_config("chat_link", foreground="#6d92ff", underline=True)
            self.chat_display.tag_config("chat_mention", foreground="#ffb35c")
            self.chat_display.tag_config("search_hit", background="#4a4666")
            self.chat_display.tag_config("search_current", background="#d9622f", foreground="#16141f")


            for _tag in ("gold_chat_nick", "chat_link", "chat_mention", "chat_ts", "search_hit", "search_current"):
                tw.tag_raise(_tag)
            self._bind_chat_links()


            self.search_bar = ctk.CTkFrame(main_frame, fg_color="#201d30")
            self.search_entry = ctk.CTkEntry(self.search_bar, placeholder_text="Что ищем?...", height=32)
            self.search_entry.pack(side="left", fill="x", expand=True, padx=(8, 6), pady=6)
            self.search_entry.bind("<KeyRelease>", self._on_search_key)
            self.search_entry.bind("<Return>", lambda e: self.search_step(-1))
            self.search_entry.bind("<Shift-Return>", lambda e: self.search_step(1))
            self.search_entry.bind("<Escape>", lambda e: self.close_search())
            self.search_count_label = ctk.CTkLabel(self.search_bar, text="", width=90,
                                                   font=ctk.CTkFont(size=12), text_color="#a8a4bd")
            self.search_count_label.pack(side="left", padx=(0, 6))
            make_sound_button(self.search_bar, text="▲", command=lambda: self.search_step(-1),
                              width=32, height=28, fg_color="#4a4666", hover_color="#3d3a52").pack(side="left", padx=2)
            make_sound_button(self.search_bar, text="▼", command=lambda: self.search_step(1),
                              width=32, height=28, fg_color="#4a4666", hover_color="#3d3a52").pack(side="left", padx=2)
            make_sound_button(self.search_bar, text="✕", command=self.close_search,
                              width=32, height=28, fg_color="#d3453f", hover_color="#b83530").pack(side="left", padx=(2, 8))


            self._chat_menu = tk.Menu(self, tearoff=0, bg="#201d30", fg="#e5e2f0",
                                      activebackground="#6d92ff", activeforeground="#16141f", bd=0)
            self._chat_menu.add_command(label="📋 Скопировать выделенное", command=self.copy_selection)
            self._chat_menu.add_command(label="📋 Скопировать весь чат", command=self.copy_all)
            self._chat_menu.add_command(label="📋 Скопировать последнее сообщение", command=self.copy_last_message)
            self._chat_menu.add_separator()
            self._chat_menu.add_command(label="🔍 Найти в чате (Ctrl+F)", command=self.open_search)
            self._chat_menu.add_command(label="📖 Что тут умеет чат", command=self.show_chat_help)
            self.chat_display._textbox.bind("<Button-3>", self._show_chat_menu)
        except Exception as _e:


            print(f"[chat_ui] Не удалось настроить подсветку/поиск чата: {_e}")
            traceback.print_exc()
            self.search_bar = ctk.CTkFrame(main_frame, fg_color="#201d30")
            self._chat_menu = None


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

        room_text = f"🚪 Код комнаты: {self.room}   |   🌐 Релей: {self.relay_url}"
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

        search_btn = make_sound_button(format_frame, text="🔍 Поиск",
                                       command=self.open_search,
                                       width=100, height=30,
                                       fg_color="#4a4666", hover_color="#3d3a52",
                                       font=ctk.CTkFont(size=12))
        search_btn.pack(side="left", padx=2)

        self.mute_btn = make_sound_button(format_frame,
                                          text="🔕 Без звука" if self.muted else "🔔 Уведомления",
                                          command=self.toggle_mute,
                                          width=150, height=30,
                                          fg_color="#4a4666", hover_color="#3d3a52",
                                          font=ctk.CTkFont(size=12))
        self.mute_btn.pack(side="left", padx=2)

        help_btn = make_sound_button(format_frame, text="❓ Команды",
                                     command=self.show_chat_help,
                                     width=110, height=30,
                                     fg_color="#4a4666", hover_color="#3d3a52",
                                     font=ctk.CTkFont(size=12))
        help_btn.pack(side="left", padx=2)

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

        settings_btn = make_sound_button(btn_frame, text="⚙️ Настройки",
                                         command=self.open_chat_settings,
                                         fg_color="#4a4666", hover_color="#3d3a52",
                                         height=35,
                                         font=ctk.CTkFont(size=12))
        settings_btn.pack(side="left", padx=(0, 10))

        reconnect_btn = make_sound_button(btn_frame, text="🔄 Переподключиться",
                                          command=self.reconnect,
                                          fg_color="#6fce7f", hover_color="#5cb56c",
                                          text_color="#16141f", height=35,
                                          font=ctk.CTkFont(size=12))
        reconnect_btn.pack(side="left", padx=(0, 10))

        leave_room_btn = make_sound_button(btn_frame, text="🚪 Выйти из комнаты",
                                           command=self.leave_room,
                                           fg_color="#d9622f", hover_color="#c14f26",
                                           text_color="#16141f", height=35,
                                           font=ctk.CTkFont(size=12))
        leave_room_btn.pack(side="right", padx=(0, 10))

        close_btn = make_sound_button(btn_frame, text="❌ Закрыть чат",
                                      command=self.on_close,
                                      fg_color="#d3453f", hover_color="#b83530",
                                      height=35,
                                      font=ctk.CTkFont(size=12))
        close_btn.pack(side="right")

        self.message_entry.bind("<Up>", self._history_prev)
        self.message_entry.bind("<Down>", self._history_next)
        for seq in ("<Control-f>", "<Control-F>", "<Control-Cyrillic_a>", "<Control-Cyrillic_A>"):
            self.bind(seq, self._on_ctrl_f)
        self.bind("<Escape>", lambda e: self.close_search() if self._search_visible else None)

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def clear_chat(self):
        question = "Точно очистить чат?"
        if self.personal_contact:
            question += "\n\nИстория этого чата на диске тоже сотрётся."
        if self._mb.askyesno("Очистка чата", question):
            self.chat_display.configure(state="normal")
            self.chat_display.delete("1.0", "end")
            self.chat_display.insert("1.0", "💬 Чат очищен\n")
            self.chat_display.insert("end", "━" * 50 + "\n")
            self.chat_display.configure(state="disabled")
            self.message_history = []
            self.update_msg_count()
            if self.personal_contact:
                delete_chat_history(self.personal_contact.get("id"))
            if self._search_visible:
                self._run_search()
            self.log("🗑️ Чат очищен")

    def export_chat(self):
        if not self.message_history:
            play_error()
            self._mb.showinfo("Информация", "Экспортировать нечего, чат пустой")
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
            self._mb.showinfo("Успешно", f"Сохранил чат сюда:\n{file_path}")
        except Exception as e:
            play_error()
            self._mb.showerror("Ошибка", f"Чат не сохранился:\n{e}")

    def update_msg_count(self):
        if threading.current_thread() is not threading.main_thread():
            try:
                self.after(0, self.update_msg_count)
            except Exception:
                pass
            return
        count = len(self.message_history)
        if count > 0:
            self.msg_count_label.configure(text=f"📨 {count}")
        else:
            self.msg_count_label.configure(text="")

    def log(self, message, ts=None):
        if threading.current_thread() is not threading.main_thread():
            try:
                self.after(0, lambda: self.log(message, ts))
            except:
                pass
            return
        try:
            if not self.winfo_exists():
                return
            self.chat_display.configure(state="normal")
            timestamp = ts or datetime.now().strftime("%H:%M:%S")

            start_index = self.chat_display.index("end-1c")

            clean_message = message.lstrip("💬 📤 📨 🔔 ")

            is_licensed_msg = False
            target_nick = ""

            if ": " in clean_message:
                possible_nick = clean_message.split(": ", 1)[0]
                if possible_nick in self._licensed_nicks():
                    is_licensed_msg = True
                    target_nick = possible_nick

            full_text = f"[{timestamp}] {message}\n"
            self.chat_display.insert("end", full_text)

            tw = self.chat_display._textbox
            if message.startswith("📤"):
                align_tag = "msg_mine"
            elif message.startswith("💬"):
                align_tag = "msg_theirs"
            elif message.startswith("🔔"):
                align_tag = "msg_system"
            else:
                align_tag = "msg_info"
            tw.tag_add(align_tag, f"{start_index} linestart", f"{start_index} lineend")

            ts_prefix_len = len(f"[{timestamp}] ")
            tw.tag_add("chat_ts", start_index, f"{start_index}+{ts_prefix_len}c")

            if is_licensed_msg and target_nick:
                current_line = start_index.split('.')[0]
                nick_len = tk.IntVar()
                nick_pos = self.chat_display._textbox.search(
                    target_nick, f"{current_line}.0", stopindex=f"{current_line}.end", count=nick_len)
                if nick_pos and nick_len.get() > 0:
                    self.chat_display.tag_add("gold_chat_nick", nick_pos, f"{nick_pos}+{nick_len.get()}c")

            self._decorate_chat_line(start_index, message)

            if self._search_visible and self._search_last_query:
                self._run_search(keep_position=True)
            if not (self._search_visible and self._search_matches):
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


        if getattr(self, "_connecting", False) or self.connected:
            return
        self._connecting = True
        try:
            self._run_relay_inner()
        finally:
            self._connecting = False

    def _run_relay_inner(self):
        role_text = "хостом (стример)" if self.role == "streamer" else "гостем (зритель)"
        first_time = not getattr(self.master, "_chat_init_log_shown", False)
        try:
            if first_time:
                self.log(f"🌐 Подключаюсь к релею {self.relay_url}...")
                self.log(f"🚪 Комната: {self.room}, роль: {role_text}")
            else:
                self.log(f"🌐 Подключаюсь к комнате «{self.room}»...")
            self.client_socket = ws_client.create_connection(self.relay_url, timeout=15, sslopt=_ws_sslopt())
            if not self.running:


                try:
                    self.client_socket.close()
                except Exception:
                    pass
                self.client_socket = None
                return
            self.client_socket.settimeout(0.5)
            hello = json.dumps({"room": self.room, "role": self.role, "username": self.username})
            self._socket_send(hello)
            self.connected = True
            self._reconnect_attempts = 0
            self.after(0, self._hide_chat_loading_overlay)
            self.safe_update_widget(self.status_label, text="🟢 Онлайн", text_color="#6fce7f")
            self.safe_update_widget(self.send_btn, state="normal")
            self.participant_count = 1
            self.update_participant_status()
            if first_time:
                self.log(f"✅ Подключено к релею! Комната: {self.room}")
                try:
                    self.master._chat_init_log_shown = True
                except Exception:
                    pass
            else:
                self.log(f"✅ Подключено (комната «{self.room}»)")
            self._broadcast_dm_identity()
            threading.Thread(target=self.receive_messages_thread, daemon=True).start()
        except Exception as e:
            self.log(f"❌ Не удалось подключиться к релею: {e}")
            self.log("💡 ПРОВЕРЬТЕ:")
            self.log("  1. Есть интернет?")
            self.log("  2. Релей-сервер сейчас работает (не уснул на бесплатном хостинге)?")
            self.log("  3. Код комнаты совпадает у обоих игроков?")
            self.connected = False
            self.safe_update_widget(self.status_label, text="🔴 Ожидание", text_color="#d3453f")


            self._auto_reconnect()

    def _auto_reconnect(self):
        if not self.running or not self.winfo_exists():
            return
        self._reconnect_attempts = getattr(self, "_reconnect_attempts", 0) + 1
        delay = min(3 * self._reconnect_attempts, 20)
        self.log(f"🔄 Повторная попытка через {delay} сек... (попытка {self._reconnect_attempts})")

        def _retry():
            if not self.running or not self.winfo_exists() or self.connected:
                return
            threading.Thread(target=self.run_relay, daemon=True).start()

        self.after(delay * 1000, _retry)

    def reconnect(self):
        self._reconnect_attempts = 0
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
                    elif message.startswith("{"):
                        self.handle_control_message(message)
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
                if ": " in message and not message.startswith("* "):
                    sender, text = message.split(": ", 1)
                else:
                    sender, text = "", message

                if sender and self.username and sender == self.username:


                    return

                self.message_history.append(message)
                self.update_msg_count()
                self._persist_message(message, mine=False)
                self.log(f"💬 {message}")

                if self._mentions_me(text):
                    self.show_notification(text, sender, title="📣 Тебя позвали")
                else:
                    self.show_notification(text, sender)
                self._update_personal_preview(text, mine=False)
            else:
                self.log(f"🔔 {message}")
                body = message.lstrip("👤 ").strip()
                if "присоединился" in message:
                    self.participant_count = min(self.participant_count + 1, self.max_room_size)
                    self.update_participant_status()
                    self.show_notification(body, title="🟢 Участник присоединился")
                elif "покинул" in message:
                    self.participant_count = max(self.participant_count - 1, 1)
                    self.update_participant_status()
                    self.show_notification(body, title="🔴 Участник покинул чат")
        except:
            pass

    def update_participant_status(self):
        if not hasattr(self, 'connection_status_label'):
            return
        if self.participant_count <= 1:
            text = f"👤 В комнате «{self.room}», ждём собеседника..."
        else:
            text = f"✅ В комнате «{self.room}»: {self.participant_count}/{self.max_room_size} участников"
        self.safe_update_widget(self.connection_status_label, text=text, text_color="#6fce7f")

    def handle_control_message(self, message):
        try:
            data = json.loads(message)
        except Exception:
            self.display_message(message)
            return

        msg_type = data.get("type")
        if msg_type == "error" and data.get("reason") == "room_full":
            max_size = data.get("max", self.max_room_size)
            self.log(f"❌ Комната «{self.room}» заполнена ({max_size}/{max_size})")
            self.connected = False
            self.after(0, lambda: self._mb.showerror(
                "Комната заполнена",
                f"В комнате «{self.room}» уже {max_size} участников — это максимум.\n"
                f"Попробуйте другой код комнаты или подождите, пока кто-то освободит место."
            ))
        elif msg_type == "assigned_username":
            new_username = data.get("username")
            if new_username:
                if new_username != self.username:
                    self.log(f"ℹ️ Ник «{self.username}» уже занят в комнате — вам присвоен ник «{new_username}»")
                    self.username = new_username
                    self.after(0, lambda: self._mb.showinfo(
                        "Ник изменён",
                        f"В комнате «{self.room}» уже есть участник с таким ником.\n"
                        f"Ваш ник в этом чате: «{new_username}»"
                    ))
                else:
                    self.username = new_username
                self.send_message_raw(f"👤 {self.username} присоединился к комнате!")
                self._broadcast_dm_identity()
        elif msg_type == "dm_identity":
            if not self.personal_contact:
                return
            their_id = data.get("user_id")
            their_username = (data.get("username") or "").strip() or "Игрок"


            their_contact_name = (data.get("contact_name") or "").strip()
            suggested_name = their_contact_name or their_username
            try:
                my_id = ensure_user_id(self.master.settings)
            except Exception:
                my_id = None
            if not their_id or their_id == my_id:
                return
            self._auto_add_contact(their_id, suggested_name)
        elif msg_type == "file_offer":
            sender = data.get("sender", "???")
            url = data.get("url", "")
            filename = sanitize_shared_filename(data.get("filename", "file.bin"))
            auto_launch = bool(data.get("auto_launch", False))
            if sender == self.username or not url:
                return
            self.after(0, lambda: self.prompt_file_offer(sender, url, filename, auto_launch=auto_launch))
        elif msg_type == "screen_share_request":
            if data.get("to") != self.username:
                return
            requester = data.get("from", "???")
            request_id = data.get("request_id")
            self.after(0, lambda: self.prompt_screen_share_request(requester, request_id))
        elif msg_type == "screen_share_response":
            if data.get("to") != self.username:
                return
            self.after(0, lambda d=data: self._on_screen_share_response(d))
        elif msg_type == "screen_frame":
            if data.get("to") != self.username:
                return
            self.after(0, lambda d=data: self._update_remote_frame(d))
        elif msg_type == "remote_input":


            if data.get("to") != self.username:
                return
            self._on_remote_input(data)
        elif msg_type == "screen_share_stop":
            if data.get("to") != self.username:
                return
            self.after(0, lambda d=data: self._on_screen_share_stop(d.get("from")))
        else:
            self.log(f"ℹ️ Служебное сообщение от релея: {message}")

    def send_message(self):
        message = self.message_entry.get().strip()
        if not message:
            return

        self._remember_input(message)

        if message.startswith("//"):

            message = message[1:]
        elif message.startswith("/") and self.handle_chat_command(message):
            self.message_entry.delete(0, 'end')
            return

        if not self.connected or self.client_socket is None:
            self.log("⚠️ Связи с чатом пока нет — подожди, пока подключится")
            return

        if message.startswith("&&download-all-file-start="):
            url = message.split("=", 1)[1].strip()
            self.message_entry.delete(0, 'end')
            self.offer_file_to_room(url, auto_launch=True)
            return

        if message.startswith("&&share-file=") or message.startswith("&&download-all-file="):
            url = message.split("=", 1)[1].strip()
            self.message_entry.delete(0, 'end')
            self.offer_file_to_room(url)
            return

        if message.startswith("&&screen-share-"):
            target = message[len("&&screen-share-"):].strip()
            self.message_entry.delete(0, 'end')
            if target.lower() in ("stop", "off", "cancel", "стоп"):
                self.stop_screen_share()
            else:
                self.request_screen_share(target)
            return

        full_message = f"{self.username}: {message}"
        self.send_message_raw(full_message)
        self.message_entry.delete(0, 'end')


    @property
    def _mb(self):
        return _ChatMessagebox(self)

    def _set_entry_text(self, value):
        self.message_entry.delete(0, 'end')
        self.message_entry.insert(0, value)

    def _remember_input(self, value):
        if not self._input_history or self._input_history[-1] != value:
            self._input_history.append(value)
            if len(self._input_history) > 50:
                del self._input_history[0]
        self._input_history_pos = None

    def _history_prev(self, event=None):
        if not self._input_history:
            return "break"
        if self._input_history_pos is None:
            self._input_draft = self.message_entry.get()
            self._input_history_pos = len(self._input_history) - 1
        elif self._input_history_pos > 0:
            self._input_history_pos -= 1
        self._set_entry_text(self._input_history[self._input_history_pos])
        return "break"

    def _history_next(self, event=None):
        if self._input_history_pos is None:
            return "break"
        if self._input_history_pos < len(self._input_history) - 1:
            self._input_history_pos += 1
            self._set_entry_text(self._input_history[self._input_history_pos])
        else:
            self._input_history_pos = None
            self._set_entry_text(self._input_draft)
        return "break"


    def _send_line(self, full_message):
        if not self.connected or self.client_socket is None:
            self.log("⚠️ Связи с чатом пока нет — подожди, пока подключится")
            return False
        self.send_message_raw(full_message)
        return True

    def _send_as_user(self, value):
        return self._send_line(f"{self.username}: {value}")

    def handle_chat_command(self, message):
        m = CHAT_COMMAND_RE.match(message)
        if not m:
            return False
        name = m.group(1).lower()
        arg = (m.group(2) or "").strip()
        action = CHAT_COMMAND_ALIASES.get(name)

        if action is None:
            play_error()
            self.log(f"⚠️ Команды /{name} у меня нет. Всё, что умею, — в /help. "
                     f"А если хотел просто написать текст со «/» в начале — поставь «//».")
            return True

        if action == "help":
            self.show_chat_help()
        elif action == "roll":
            spec = parse_roll_spec(arg)
            if spec is None:
                self.log("⚠️ Не понял, что кидать. Попробуй /roll, /roll 20 или /roll 2d6 (кубиков до 20, граней до 1000)")
                return True
            count, sides = spec
            rolls, total = roll_dice(count, sides)
            if count > 1:
                self._send_as_user(f"🎲 бросил {count}d{sides} → " + " + ".join(map(str, rolls)) + f" = {total}")
            else:
                self._send_as_user(f"🎲 бросил d{sides} → {total}")
        elif action == "flip":
            self._send_as_user(f"🪙 подбросил монетку → {random.choice(['Орёл', 'Решка'])}")
        elif action == "choose":
            sep = "|" if "|" in arg else ","
            options = [o.strip() for o in arg.split(sep) if o.strip()][:20]
            if len(options) < 2:
                self.log("⚠️ Из чего выбирать-то? Дай хотя бы два варианта: /choose пицца | суши")
                return True
            self._send_as_user(f"🎯 выбрал: {random.choice(options)} (из: {', '.join(options)})")
        elif action == "me":
            if not arg:
                self.log("⚠️ А что сделал-то? Например: /me пошёл за едой")
                return True
            self._send_line(f"* {self.username} {arg}")
        elif action == "shrug":
            self._send_as_user(f"{arg} ¯\\_(ツ)_/¯".strip())
        elif action == "time":
            offset = datetime.now().astimezone().utcoffset()
            minutes = int(offset.total_seconds() // 60) if offset is not None else 0
            self._send_as_user(f"🕒 у меня сейчас {datetime.now():%H:%M} ({format_utc_offset(minutes)})")
        elif action == "coords":
            result = convert_coords(arg)
            if result is None:
                self.log("⚠️ С координатами что-то не так. Пример: /coords 100 64 -200 (в конце можно дописать «незер» или «энд»)")
                return True
            self._send_as_user(result)
        elif action == "search":
            self.open_search(arg)
        elif action == "clear":
            self.clear_chat()
        elif action == "export":
            self.export_chat()
        elif action == "mute":
            self.set_muted(True)
        elif action == "unmute":
            self.set_muted(False)
        elif action == "copy":
            self.copy_last_message()
        return True

    def show_chat_help(self):
        self._append_plain_lines([
            "📖 Что тут вообще умеет чат:",
            "  /roll [20 | 2d6]  — кинуть кубик (без параметров — обычный d6)",
            "  /flip  — подбросить монетку, пусть судьба решает",
            "  /choose пицца | суши | шаурма  — выберу за вас, не вопрос",
            "  /time  — сказать, сколько сейчас у тебя времени",
            "  /me пошёл за едой  — выйдет «* Ник пошёл за едой»      /shrug [текст]  — ¯\\_(ツ)_/¯",
            "  /search слово  — найти в переписке (или Ctrl+F)      /copy  — скопировать последнее сообщение",
            "  /clear  — почистить чат      /export  — сохранить переписку в файл",
            "  /mute и /unmute  — заглушить этот чат или вернуть уведомления",
            "  ↑ / ↓ в поле ввода  — достать то, что уже писал",
            "  @ник в сообщении  — человеку придёт уведомление, а строка подсветится",
            "  Ссылки в чате кликаются, а по правой кнопке мыши можно копировать",
            "  &&download-all-file=(ссылка)  — предложить всем в комнате скачать файл",
            "  &&download-all-file-start=(ссылка)  — то же, но после скачивания получателю предложат ЗАПУСТИТЬ файл (с диалогом Да/Нет)",
            "  &&screen-share-Ник  — попросить у «Ника» разрешение посмотреть его экран и управлять мышью/клавиатурой",
            "  &&screen-share-stop  — остановить текущую трансляцию (свою или ту, что смотришь)",
            "━" * 50,
        ])


    def _screen_share_libs_ok(self):
        missing = []
        if mss is None:
            missing.append("mss")
        if pyautogui is None:
            missing.append("pyautogui")
        if missing:
            play_error()
            self._mb.showerror(
                "Не хватает библиотек",
                "Для трансляции и управления экраном нужны пакеты:\n"
                f"{', '.join(missing)}\n\n"
                f"Установи их командой:\npip install {' '.join(missing)}\n"
                "и перезапусти лаунчер."
            )
            return False
        return True

    def request_screen_share(self, target_username):
        target_username = (target_username or "").strip()
        if not target_username:
            self.log("⚠️ Укажи ник: &&screen-share-Ник")
            return
        if not self.connected or self.client_socket is None:
            self.log("⚠️ Связи с чатом пока нет — подожди, пока подключится")
            return
        if target_username == self.username:
            play_error()
            self.log("⚠️ Нельзя запросить трансляцию у самого себя")
            return
        if self._screen_share.get("state"):
            play_error()
            self.log("⚠️ Уже есть активный запрос/сессия трансляции — сначала останови её (&&screen-share-stop)")
            return
        if not self._screen_share_libs_ok():
            return

        request_id = uuid.uuid4().hex[:10]
        self._screen_share = {"role": "viewer", "peer": target_username, "id": request_id, "state": "pending_out"}
        try:
            self._socket_send(json.dumps({
                "type": "screen_share_request",
                "request_id": request_id,
                "from": self.username,
                "to": target_username,
            }))
        except Exception as e:
            self.log(f"❌ Не удалось отправить запрос: {e}")
            self._screen_share = {}
            return

        play_click()
        self.log(f"📤 Запросил(а) доступ к экрану «{target_username}» — жду подтверждения (до {SCREEN_SHARE_REQUEST_TIMEOUT} сек)...")
        self.after(SCREEN_SHARE_REQUEST_TIMEOUT * 1000, lambda rid=request_id: self._screen_share_request_timeout(rid))

    def _screen_share_request_timeout(self, request_id):
        if self._screen_share.get("id") == request_id and self._screen_share.get("state") == "pending_out":
            peer = self._screen_share.get("peer")
            self.log(f"⌛ «{peer}» не ответил(а) на запрос трансляции вовремя — запрос отменён")
            self._screen_share = {}

    def prompt_screen_share_request(self, requester, request_id):
        """Показывает получателю запрос на просмотр/управление его экраном.
        Это НЕ просто просмотр: собеседник получает полный контроль над мышью
        и клавиатурой. Поэтому требуется ДВА подтверждения — явное «Да/Нет»
        с объяснением последствий, а затем галка о полном осознании риска.
        Трансляция начинается ТОЛЬКО после обоих."""
        # Safe mode — отказ без диалога
        if getattr(self.master, "safe_mode", False):
            self._send_screen_share_response(requester, request_id, False, reason="safe_mode")
            self.log(f"🔒 Safe mode: отклонил запрос трансляции от «{requester}»")
            return

        # Пока открыт диалог подтверждения, второй запрос не должен вклиниться
        # в него ещё одним модальным окном: wait_window крутит вложенный цикл
        # событий, и внутри него продолжают приходить after-колбэки
        if self._screen_share_prompt_active:
            self._send_screen_share_response(requester, request_id, False, reason="busy")
            return
        if self._screen_share.get("state"):
            self._send_screen_share_response(requester, request_id, False, reason="busy")
            return
        if not self._screen_share_libs_ok():
            self._send_screen_share_response(requester, request_id, False, reason="missing_libs")
            return

        try:
            self.lift()
            self.focus_force()
        except Exception:
            pass

        self._screen_share_prompt_active = True
        try:
            accepted = self._run_screen_share_confirm(requester)
        finally:
            self._screen_share_prompt_active = False

        self._send_screen_share_response(requester, request_id, accepted)
        if accepted:
            self._start_screen_share_host(requester, request_id)
            # Громкое уведомление: сразу после согласия напоминаем, чем жертвуем
            self.show_notification(
                f"«{requester}» УПРАВЛЯЕТ ТВОИМ ПК. Останови: &&screen-share-stop",
                title="🔴 АКТИВНО УПРАВЛЕНИЕ",
                force=True
            )
        else:
            play_error()
            self.log(f"🚫 Отклонил(а) запрос «{requester}» на трансляцию экрана")

    def _run_screen_share_confirm(self, requester):
        """Два подтверждения подряд: объяснение последствий, затем галка
        о полном осознании риска. True — только если юзер прошёл оба шага."""
        # === Первый диалог: общее предупреждение ===
        first = self._mb.askyesno(
            "🖥️ ЗАПРОС ПОЛНОГО ДОСТУПА К ПК",
            f"⚠️⚠️⚠️ ВНИМАНИЕ ⚠️⚠️⚠️\n\n"
            f"Игрок «{requester}» просит ПОЛНЫЙ ДОСТУП к твоему компьютеру:\n\n"
            f"  • видеть всё, что происходит на экране\n"
            f"  • двигать твою мышь\n"
            f"  • кликать и нажимать клавиши ОТ ТВОЕГО ИМЕНИ\n"
            f"  • выполнять любые действия, пока окно открыто\n\n"
            f"Это НЕ просто просмотр экрана — это удалённое управление, как\n"
            f"будто «{requester}» сел за твой компьютер.\n\n"
            f"🔴 Разрешай ТОЛЬКО тем, кому доверяешь на 100%.\n"
            f"🔴 Не разрешай незнакомцам — даже если пишут «мне просто посмотреть».\n\n"
            f"Продолжить (показать второй диалог подтверждения)?"
        )
        if not first:
            return False

        # === Второй диалог: чекбокс осознания ===
        confirm_dialog = ctk.CTkToplevel(self)
        confirm_dialog.title("⚠️ Подтверждение доступа")
        confirm_dialog.geometry("480x340")
        confirm_dialog.resizable(False, False)
        confirm_dialog.grab_set()
        confirm_dialog.transient(self)

        ctk.CTkLabel(
            confirm_dialog,
            text="⚠️ ФИНАЛЬНОЕ ПОДТВЕРЖДЕНИЕ",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#d3453f"
        ).pack(pady=(20, 10))

        ctk.CTkLabel(
            confirm_dialog,
            text=f"«{requester}» получит полный контроль над твоей мышью и клавиатурой.",
            font=ctk.CTkFont(size=13),
            wraplength=420,
            justify="center"
        ).pack(pady=(0, 15))

        agree_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            confirm_dialog,
            text="Я понимаю, что даю полный удалённый доступ\nи что собеседник сможет делать что угодно на моём ПК",
            variable=agree_var,
            font=ctk.CTkFont(size=12)
        ).pack(pady=(0, 15))

        result = {"value": False}

        def on_yes():
            if not agree_var.get():
                play_error()
                messagebox.showwarning("Подтверждение", "Сначала поставь галочку", parent=self)
                return
            result["value"] = True
            release_and_destroy(confirm_dialog)

        def on_no():
            result["value"] = False
            release_and_destroy(confirm_dialog)

        confirm_dialog.protocol("WM_DELETE_WINDOW", on_no)

        btn_row = ctk.CTkFrame(confirm_dialog, fg_color="transparent")
        btn_row.pack(pady=(0, 20))

        make_sound_button(
            btn_row, text="✅ РАЗРЕШИТЬ ДОСТУП",
            command=on_yes,
            fg_color="#d3453f", hover_color="#b83530",
            height=44, width=200,
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(side="left", padx=8)

        make_sound_button(
            btn_row, text="❌ ОТМЕНА",
            command=on_no,
            fg_color="#4a4666", hover_color="#3d3a52",
            height=44, width=140,
            font=ctk.CTkFont(size=14)
        ).pack(side="left", padx=8)

        self.wait_window(confirm_dialog)
        return bool(result["value"])

    def _send_screen_share_response(self, requester, request_id, accepted, reason=None):
        if not self.client_socket or not self.connected:
            return
        payload = {
            "type": "screen_share_response",
            "request_id": request_id,
            "from": self.username,
            "to": requester,
            "accepted": bool(accepted),
        }
        if reason:
            payload["reason"] = reason
        try:
            self._socket_send(json.dumps(payload))
        except Exception as e:
            self.log(f"❌ Не удалось ответить на запрос трансляции: {e}")

    def _on_screen_share_response(self, data):
        session = self._screen_share
        if session.get("state") != "pending_out" or session.get("id") != data.get("request_id"):
            return
        peer = data.get("from", session.get("peer"))
        if data.get("accepted"):
            self._screen_share = {"role": "viewer", "peer": peer, "id": data.get("request_id"), "state": "active"}
            play_click()
            self.log(f"✅ «{peer}» разрешил(а) — открываю трансляцию его(её) экрана")
            self._remote_screen_window = RemoteScreenWindow(self, peer, data.get("request_id"))
        else:
            reason = data.get("reason")
            self._screen_share = {}
            play_error()
            if reason == "busy":
                self.log(f"🚫 «{peer}» сейчас занят(а) другой трансляцией")
            elif reason == "missing_libs":
                self.log(f"🚫 У «{peer}» не установлены нужные библиотеки для трансляции")
            elif reason == "safe_mode":
                self.log(f"🔒 У «{peer}» включён Safe mode — удалённое управление отключено")
            else:
                self.log(f"🚫 «{peer}» отклонил(а) запрос на трансляцию экрана")

    def _start_screen_share_host(self, viewer_username, request_id):
        self._screen_share = {"role": "host", "peer": viewer_username, "id": request_id, "state": "active"}
        self._screen_share_streaming = True
        
        
        self._screen_frame_queue = _queue_module.Queue(maxsize=2)
        # Плашка поверх всего: пока идёт трансляция, видно, что она идёт и кому,
        # и её можно остановить одним кликом (иначе _screen_share_banner остаётся
        # None и stop_screen_share нечего закрывать)
        try:
            self._screen_share_banner = _ScreenShareHostBanner(self, viewer_username)
        except Exception as e:
            self._screen_share_banner = None
            self.log(f"⚠️ Не удалось показать плашку трансляции: {e}")
        self.log(f"📺 ТРАНСЛЯЦИЯ ЭКРАНА + УПРАВЛЕНИЕ для «{viewer_username}» (стоп: &&screen-share-stop)")
        # Два отдельных потока: один захватывает, другой отправляет
        threading.Thread(target=self._screen_capture_loop, args=(viewer_username, request_id), daemon=True).start()
        threading.Thread(target=self._screen_frame_sender_loop, args=(viewer_username, request_id), daemon=True).start()

    def _screen_frame_sender_loop(self, viewer_username, request_id):
        consecutive_send_errors = 0
        while (
            self._screen_share_streaming
            and self._screen_share.get("id") == request_id
            and self._screen_share.get("state") == "active"
        ):
            try:
                payload = self._screen_frame_queue.get(timeout=1.0)
            except _queue_module.Empty:
                continue

            try:
                sock = self.client_socket
                if sock is None:
                    break
                
                with self._socket_lock:
                    try:
                        sock.sock.settimeout(5)
                        sock.send(payload)
                        sock.sock.settimeout(0.5)
                    except Exception:
                        try:
                            sock.sock.settimeout(0.5)
                        except Exception:
                            pass
                        raise
                consecutive_send_errors = 0
            except Exception as e:
                consecutive_send_errors += 1
                if consecutive_send_errors >= 6:
                    self.after(0, lambda: self.log(
                        "⏹ Отправка кадров зависла — трансляцию остановил(а) автоматически"
                    ))
                    self._screen_share_streaming = False
                    self.after(0, lambda: self.stop_screen_share(notify=True))
                    break
                

    def _screen_capture_loop(self, viewer_username, request_id):
        seq = 0
        last_error_log = 0.0
        consecutive_errors = 0
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                orig_w, orig_h = monitor["width"], monitor["height"]

                while (
                    self._screen_share_streaming
                    and self._screen_share.get("id") == request_id
                    and self._screen_share.get("state") == "active"
                ):
                    frame_start = time.time()
                    try:
                        if not (self.client_socket and self.connected):
                            break
                        shot = sct.grab(monitor)
                        img = Image.frombytes("RGB", (shot.width, shot.height), shot.rgb)
                        if img.width > SCREEN_SHARE_MAX_WIDTH:
                            ratio = SCREEN_SHARE_MAX_WIDTH / img.width
                            img = img.resize(
                                (SCREEN_SHARE_MAX_WIDTH, max(1, int(img.height * ratio))),
                                Image.BILINEAR,
                            )
                        buf = BytesIO()
                        img.save(buf, format="JPEG", quality=SCREEN_SHARE_JPEG_QUALITY)
                        b64 = base64.b64encode(buf.getvalue()).decode("ascii")

                        seq += 1
                        payload = {
                            "type": "screen_frame",
                            "request_id": request_id,
                            "from": self.username,
                            "to": viewer_username,
                            "seq": seq,
                            "w": img.width, "h": img.height,
                            "orig_w": orig_w, "orig_h": orig_h,
                            "data": b64,
                        }
                        
                        
                        try:
                            self._screen_frame_queue.put_nowait(json.dumps(payload))
                        except _queue_module.Full:
                            pass  
                        consecutive_errors = 0
                    except Exception as e:
                        consecutive_errors += 1
                        now = time.time()
                        if now - last_error_log > 5:
                            self.log(f"⚠️ Ошибка захвата экрана: {e}")
                            last_error_log = now
                        if consecutive_errors >= SCREEN_SHARE_MAX_CONSECUTIVE_ERRORS:
                            self.log("⏹ Слишком много ошибок подряд — трансляцию остановил(а) автоматически")
                            break

                    elapsed = time.time() - frame_start
                    sleep_left = SCREEN_SHARE_INTERVAL - elapsed
                    if sleep_left > 0:
                        time.sleep(sleep_left)
        except Exception as e:
            self.after(0, lambda: self.log(f"❌ Трансляция экрана прервана: {e}"))
        finally:


            if self._screen_share.get("id") == request_id and self._screen_share.get("role") == "host":
                self._screen_share_streaming = False
                self.after(0, lambda: self.stop_screen_share(notify=True))

    def _update_remote_frame(self, data):
        session = self._screen_share
        if session.get("role") != "viewer" or session.get("state") != "active":
            return
        if session.get("id") != data.get("request_id"):
            return
        if not self._remote_screen_window or not self._remote_screen_window.winfo_exists():
            return
        try:
            raw = base64.b64decode(data.get("data", ""))
            img = Image.open(BytesIO(raw))
            img.load()
        except Exception:
            return
        orig_w = int(data.get("orig_w") or img.width)
        orig_h = int(data.get("orig_h") or img.height)
        self._remote_screen_window.update_frame(img, orig_w, orig_h)

    def _on_remote_input(self, data):
        """Выполняет на ЭТОМ компьютере мышь/клавиатуру по команде зрителя.
        Работает только пока у нас активна сессия «host» с тем же request_id —
        никакие входящие remote_input не выполнятся без предварительного
        подтверждения запроса пользователем. В Safe mode не выполняется ничего."""
        if getattr(self.master, "safe_mode", False):
            return
        session = self._screen_share
        if session.get("role") != "host" or session.get("state") != "active":
            return
        if session.get("id") != data.get("request_id"):
            return
        if pyautogui is None:
            return

        # Лог того, что делает удалённый юзер (только значимые действия, чтобы
        # по логу было видно, если кто-то начнёт водить мышью без спроса)
        action = data.get("action")
        peer = session.get("peer", "?")
        if action in ("down", "double_click"):
            self.log(f"🖱️ «{peer}»: клик {data.get('button', 'left')} в ({data.get('x')},{data.get('y')})")
        elif action == "key_down":
            self.log(f"⌨️ «{peer}»: нажатие {data.get('key')}")

        try:
            if action == "move":
                pyautogui.moveTo(int(data.get("x", 0)), int(data.get("y", 0)), _pause=False)
            elif action == "down":
                pyautogui.moveTo(int(data.get("x", 0)), int(data.get("y", 0)), _pause=False)
                pyautogui.mouseDown(button=data.get("button", "left"), _pause=False)
            elif action == "up":
                pyautogui.moveTo(int(data.get("x", 0)), int(data.get("y", 0)), _pause=False)
                pyautogui.mouseUp(button=data.get("button", "left"), _pause=False)
            elif action == "double_click":
                pyautogui.moveTo(int(data.get("x", 0)), int(data.get("y", 0)), _pause=False)
                pyautogui.doubleClick(button=data.get("button", "left"), _pause=False)
            elif action == "scroll":
                dy = int(data.get("dy", 0))
                clicks = dy // 40 if abs(dy) >= 40 else (1 if dy > 0 else -1 if dy < 0 else 0)
                if clicks:
                    pyautogui.scroll(clicks, _pause=False)
            elif action == "key_down":
                key = _map_tk_keysym_to_pyautogui(data.get("key", ""))
                if key:
                    pyautogui.keyDown(key, _pause=False)
            elif action == "key_up":
                key = _map_tk_keysym_to_pyautogui(data.get("key", ""))
                if key:
                    pyautogui.keyUp(key, _pause=False)
        except Exception:
            pass

    def _on_screen_share_stop(self, peer):
        session = self._screen_share
        if not session.get("state") or session.get("peer") != peer:
            return
        self.log(f"⏹ «{peer}» завершил(а) трансляцию экрана")
        self.stop_screen_share(notify=False)

    def send_remote_input(self, target_username, request_id, extra):
        if not self.client_socket or not self.connected:
            return
        payload = {
            "type": "remote_input",
            "request_id": request_id,
            "from": self.username,
            "to": target_username,
        }
        payload.update(extra)
        try:
            self._socket_send(json.dumps(payload))
        except Exception:
            pass

    def stop_screen_share(self, notify=True):
        session = self._screen_share
        if not session.get("state"):
            self.log("ℹ️ Сейчас нет активной трансляции экрана")
            return

        peer = session.get("peer")
        request_id = session.get("id")
        role = session.get("role")
        self._screen_share_streaming = False
        self._screen_share = {}

        if role == "viewer":
            try:
                if self._remote_screen_window and self._remote_screen_window.winfo_exists():
                    self._remote_screen_window.destroy()
            except Exception:
                pass
            self._remote_screen_window = None

        if role == "host":
            try:
                if self._screen_share_banner and self._screen_share_banner.winfo_exists():
                    self._screen_share_banner.destroy()
            except Exception:
                pass
            self._screen_share_banner = None

        if notify and peer and self.client_socket and self.connected:
            try:
                self._socket_send(json.dumps({
                    "type": "screen_share_stop",
                    "request_id": request_id,
                    "from": self.username,
                    "to": peer,
                }))
            except Exception:
                pass

        play_click()
        self.log(f"⏹ Трансляция экрана с «{peer}» остановлена" if peer else "⏹ Трансляция остановлена")

    def _append_plain_lines(self, lines):
        try:
            self.chat_display.configure(state="normal")
            for line in lines:
                self.chat_display.insert("end", line + "\n")
            self.chat_display.see("end")
            self.chat_display.configure(state="disabled")
        except Exception:
            pass


    def _persist_message(self, message, mine):
        if not self.personal_contact:
            return
        append_chat_history(self.personal_contact.get("id"), message, mine)

    def _load_personal_history(self):
        if not self.personal_contact:
            return
        entries = load_chat_history(self.personal_contact.get("id"))
        if not entries:
            return
        self._append_plain_lines([f"── Прошлая переписка (последние {len(entries)}) ──"])
        today = datetime.now().date()
        for entry in entries:
            try:
                dt = datetime.fromtimestamp(entry["ts"])
                stamp = dt.strftime("%H:%M:%S") if dt.date() == today else dt.strftime("%d.%m %H:%M")
            except Exception:
                stamp = "--:--"
            self.log(f"{'📤' if entry['mine'] else '💬'} {entry['text']}", ts=stamp)
            self.message_history.append(entry["text"])
        self.update_msg_count()
        self._append_plain_lines(["── а дальше уже новое ──", "━" * 50])


    def _licensed_nicks(self):
        now = time.time()
        cache = getattr(self, "_licensed_cache", None)
        if cache is None or now - cache[0] > 5:
            try:
                nicks = {a.get("username") for a in load_accounts() if a.get("type") == "microsoft"}
            except Exception:
                nicks = set()
            self._licensed_cache = (now, nicks)
            return nicks
        return cache[1]

    def _mentions_me(self, value):
        name = (self.username or "").strip().lower()
        return bool(name) and f"@{name}" in (value or "").lower()

    def toggle_mute(self):
        self.set_muted(not self.muted)

    def set_muted(self, value):
        self.muted = bool(value)
        if self.personal_contact:
            try:
                self.personal_contact["muted"] = self.muted
                settings = getattr(self.master, "settings", None)
                if settings is not None:
                    cid = self.personal_contact.get("id")
                    for c in settings.setdefault("personal_chats", []):
                        if c.get("id") == cid:
                            c["muted"] = self.muted
                            break
                    save_launcher_settings(settings)
            except Exception:
                pass
        try:
            self.mute_btn.configure(text="🔕 Без звука" if self.muted else "🔔 Уведомления")
        except Exception:
            pass
        self.log("🔕 Всё, этот чат теперь молчит" if self.muted
                 else "🔔 Ок, уведомления снова включены")


    def _bind_chat_links(self):
        tw = self.chat_display._textbox
        tw.tag_bind("chat_link", "<ButtonRelease-1>", self._on_link_click)
        tw.tag_bind("chat_link", "<Enter>", lambda e: tw.configure(cursor="hand2"))
        tw.tag_bind("chat_link", "<Leave>", lambda e: tw.configure(cursor="xterm"))

    def _decorate_chat_line(self, start_index, message):
        try:
            tw = self.chat_display._textbox
            if message.startswith("💬") and self._mentions_me(message):
                tw.tag_add("chat_mention", f"{start_index} linestart", f"{start_index} lineend")

            count_var = tk.IntVar()
            pos = start_index
            line_end = f"{start_index} lineend"
            while True:
                hit = tw.search(CHAT_URL_PATTERN, pos, stopindex=line_end,
                                regexp=True, count=count_var)
                length = count_var.get()
                if not hit or length <= 0:
                    break
                found = tw.get(hit, f"{hit}+{length}c")
                trimmed = len(found) - len(trim_link_tail(found))
                end = f"{hit}+{max(1, length - trimmed)}c"
                tw.tag_add("chat_link", hit, end)
                pos = f"{hit}+{length}c"
        except Exception:
            pass

    def _on_link_click(self, event):
        tw = self.chat_display._textbox
        try:
            if tw.tag_ranges("sel"):
                return
            idx = tw.index(f"@{event.x},{event.y}")
            rng = tw.tag_prevrange("chat_link", f"{idx}+1c")
            if not rng:
                return
            url = tw.get(rng[0], rng[1]).strip()
        except tk.TclError:
            return
        if not url.lower().startswith(("http://", "https://")):
            return
        if self._mb.askyesno(
            "🔗 Открыть ссылку?",
            f"Открыть эту ссылку в браузере?\n\n{url}\n\n"
            f"🌐 Домен: {_url_domain(url)}\n\n"
            f"Что там внутри, я не проверяю — так что смотри сам."
        ):
            webbrowser.open(url)


    def _on_ctrl_f(self, event=None):
        self.open_search()
        return "break"

    def open_search(self, query=""):
        if not getattr(self, "search_entry", None):
            return
        if not self._search_visible:
            self.search_bar.pack(fill="x", pady=(0, 6), before=self.chat_display)
            self._search_visible = True
        self.search_entry.focus_set()
        if query:
            self.search_entry.delete(0, 'end')
            self.search_entry.insert(0, query)
            self._run_search()
        else:
            try:
                self.search_entry._entry.select_range(0, 'end')
            except Exception:
                pass

    def close_search(self):
        if not self._search_visible:
            return "break"
        try:
            tw = self.chat_display._textbox
            tw.tag_remove("search_hit", "1.0", "end")
            tw.tag_remove("search_current", "1.0", "end")
            self.search_bar.pack_forget()
        except Exception:
            pass
        self._search_visible = False
        self._search_matches = []
        self._search_index = -1
        self._search_last_query = None
        self.chat_display.see("end")
        self.message_entry.focus_set()
        return "break"

    def _on_search_key(self, event=None):
        if self.search_entry.get() != self._search_last_query:
            self._run_search()

    def _run_search(self, keep_position=False):
        tw = self.chat_display._textbox
        query = self.search_entry.get()
        prev_start = None
        if keep_position and 0 <= self._search_index < len(self._search_matches):
            prev_start = self._search_matches[self._search_index][0]
        self._search_last_query = query
        tw.tag_remove("search_hit", "1.0", "end")
        tw.tag_remove("search_current", "1.0", "end")
        self._search_matches = []
        self._search_index = -1
        if not query:
            self.search_count_label.configure(text="")
            return
        count_var = tk.IntVar()
        pos = "1.0"
        while len(self._search_matches) < 1000:
            hit = tw.search(query, pos, stopindex="end", nocase=True, count=count_var)
            length = count_var.get()
            if not hit or length <= 0:
                break
            end = f"{hit}+{length}c"
            tw.tag_add("search_hit", hit, end)
            self._search_matches.append((hit, end))
            pos = end
        if self._search_matches:
            index = len(self._search_matches) - 1
            if prev_start is not None:
                for i, (start, _end) in enumerate(self._search_matches):
                    if start == prev_start:
                        index = i
                        break
            self._search_index = index
            self._show_search_current(scroll=not keep_position)
        else:
            self.search_count_label.configure(text="не нашёл")

    def search_step(self, direction):
        if self._search_matches:
            self._search_index = (self._search_index + direction) % len(self._search_matches)
            self._show_search_current()
        return "break"

    def _show_search_current(self, scroll=True):
        tw = self.chat_display._textbox
        tw.tag_remove("search_current", "1.0", "end")
        start, end = self._search_matches[self._search_index]
        tw.tag_add("search_current", start, end)
        if scroll:
            tw.see(start)
        self.search_count_label.configure(text=f"{self._search_index + 1}/{len(self._search_matches)}")


    def _show_chat_menu(self, event):
        if not getattr(self, "_chat_menu", None):
            return
        try:
            self._chat_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._chat_menu.grab_release()

    def _copy_to_clipboard(self, value, what):
        try:
            self.clipboard_clear()
            self.clipboard_append(value)
            play_click()
            self.log(f"📋 Готово, скопировал: {what}")
        except Exception as e:
            play_error()
            self.log(f"❌ Не получилось скопировать: {e}")

    def copy_selection(self):
        try:
            value = self.chat_display._textbox.get("sel.first", "sel.last")
        except tk.TclError:
            value = ""
        if not value.strip():
            self.log("ℹ️ Сначала выдели что-нибудь в чате")
            return
        self._copy_to_clipboard(value, "выделенное")

    def copy_all(self):
        value = self.chat_display.get("1.0", "end").strip()
        if value:
            self._copy_to_clipboard(value, "весь чат")

    def copy_last_message(self):
        if not self.message_history:
            self.log("ℹ️ Пока и копировать нечего — сообщений нет")
            return
        last = self.message_history[-1]
        self._copy_to_clipboard(last.split(": ", 1)[1] if ": " in last else last, "последнее сообщение")

    def offer_file_to_room(self, url, auto_launch=False):
        if not self.connected or self.client_socket is None:
            self.log("⚠️ Связи с чатом пока нет — подожди, пока подключится")
            return

        if auto_launch and getattr(self.master, "safe_mode", False):
            play_error()
            self._mb.showwarning(
                "Safe mode",
                "В Safe mode запуск файлов отключён.\n\n"
                "Файл можно разослать без автозапуска — получатели всё равно "
                "увидят диалог и решат сами. Команда с автозапуском отменена."
            )
            auto_launch = False

        if not (url.startswith("http://") or url.startswith("https://")):
            play_error()
            self._mb.showwarning(
                "Некорректная ссылка",
                "Ссылка на файл должна начинаться с http:// или https://"
            )
            return

        filename = sanitize_shared_filename(os.path.basename(url.split("?", 1)[0]))

        launch_notice = (
            "\n\n🚀 После скачивания участникам будет предложено ЗАПУСТИТЬ файл."
            if auto_launch else
            "\nФайл никому не скачается автоматически — каждый участник увидит "
            "запрос и сам решит, принимать или нет."
        )

        if not self._mb.askyesno(
            "📎 Поделиться файлом",
            f"Предложить всем в комнате «{self.room}» скачать файл?\n\n"
            f"Имя: {filename}\n"
            f"Ссылка: {url}"
            f"{launch_notice}"
        ):
            return

        payload = {
            "type": "file_offer",
            "sender": self.username,
            "url": url,
            "filename": filename,
            "auto_launch": auto_launch,
        }
        try:
            self._socket_send(json.dumps(payload))
            self.log(f"📤 Предложил файл «{filename}» всем в комнате ({url})")
            self.message_history.append(f"{self.username} предложил файл: {filename}")
            self.update_msg_count()
            self._persist_message(f"📎 {self.username} предложил файл: {filename}", mine=True)
            self._update_personal_preview(f"📎 Файл: {filename}", mine=True)
            play_click()
        except Exception as e:
            self.log(f"❌ Не удалось отправить предложение файла: {e}")
            self.disconnect()

    def prompt_file_offer(self, sender, url, filename, auto_launch=False):
        self.log(f"📥 «{sender}» хочет поделиться файлом «{filename}»"
                 + (" (с запуском после скачивания)" if auto_launch else ""))
        self.show_notification(f"«{sender}» хочет поделиться файлом «{filename}»", "📎 Файл от игрока")
        self._update_personal_preview(f"📎 Файл: {filename}", mine=False)
        self._persist_message(f"📎 {sender} предложил файл: {filename}", mine=False)

        warn = ""
        ext = os.path.splitext(filename)[1].lower()
        if ext in (".exe", ".msi", ".bat", ".cmd", ".scr", ".dll", ".ps1", ".vbs", ".jar", ".com"):
            warn = (
                "\n\n⚠️ Это исполняемый файл. Скачивайте его, только если полностью "
                "доверяете отправителю — лаунчер не проверяет, что реально находится по ссылке."
            )

        launch_notice = (
            "\n\n🚀 После скачивания программа предложит ЗАПУСТИТЬ этот файл.\n"
            "Соглашайтесь только если полностью доверяете отправителю."
            if auto_launch else ""
        )

        accept = self._mb.askyesno(
            "📎 Игрок хочет поделиться файлом",
            f"Игрок «{sender}» хочет поделиться файлом:\n\n"
            f"Имя: {filename}\n"
            f"Ссылка: {url}\n\n"
            f"Скачать его в папку download рядом с лаунчером?"
            f"{warn}{launch_notice}"
        )
        if not accept:
            self.log(f"🚫 Отклонил файл «{filename}» от «{sender}»")
            return

        play_click()
        self.log(f"⏳ Скачиваю «{filename}» от «{sender}»...")
        threading.Thread(
            target=self._download_offered_file,
            args=(sender, url, filename),
            kwargs={"auto_launch": auto_launch},
            daemon=True
        ).start()

    def _prompt_launch_file(self, dest_path, filename):
        """Спрашивает пользователя, запустить ли только что скачанный файл.
        Для исполняемых файлов одного «Да/Нет» мало — там нужно осознанно
        вписать слово ЗАПУСТИТЬ, чтобы нельзя было запустить .exe случайно.
        Вызывается из главного потока через self.after(0, ...)."""
        if getattr(self.master, "safe_mode", False):
            self.log(f"🔒 Safe mode: запуск «{filename}» заблокирован")
            self._mb.showinfo(
                "Safe mode",
                f"Запуск файлов отключён в Safe mode.\n\n"
                f"Файл «{filename}» скачан в папку download, но не запущен."
            )
            return

        ext = os.path.splitext(filename)[1].lower()
        is_executable = ext in (".exe", ".msi", ".bat", ".cmd", ".scr", ".dll",
                                ".ps1", ".vbs", ".jar", ".com")

        if is_executable:
            dialog = ctk.CTkToplevel(self)
            dialog.title("⚠️ Запуск исполняемого файла")
            dialog.geometry("480x320")
            dialog.resizable(False, False)
            dialog.grab_set()
            dialog.transient(self)

            ctk.CTkLabel(
                dialog, text="⚠️ ОПАСНО: ИСПОЛНЯЕМЫЙ ФАЙЛ",
                font=ctk.CTkFont(size=18, weight="bold"), text_color="#d3453f"
            ).pack(pady=(20, 10))

            ctk.CTkLabel(
                dialog,
                text=f"Файл: {filename}\n"
                     f"Путь: {dest_path}\n\n"
                     f"Это исполняемый файл. После запуска он сможет делать на твоём ПК\n"
                     f"что угодно: воровать пароли, шифровать файлы, устанавливать вирусы.\n\n"
                     f"Запускай ТОЛЬКО если на 100% доверяешь отправителю.",
                font=ctk.CTkFont(size=12), wraplength=440, justify="left"
            ).pack(padx=20, pady=(0, 15))

            ctk.CTkLabel(
                dialog, text="Для подтверждения впиши слово ЗАПУСТИТЬ:",
                font=ctk.CTkFont(size=12, weight="bold")
            ).pack(pady=(0, 5))

            entry = ctk.CTkEntry(dialog, width=200, height=35)
            entry.pack(pady=(0, 15))
            entry.focus_set()

            def confirm():
                if entry.get().strip().upper() != "ЗАПУСТИТЬ":
                    play_error()
                    messagebox.showwarning("Неверно", "Впиши слово ЗАПУСТИТЬ заглавными буквами", parent=self)
                    return
                release_and_destroy(dialog)
                self._execute_file(dest_path, filename)

            def cancel():
                release_and_destroy(dialog)
                self.log(f"🚫 Запуск «{filename}» отменён")

            dialog.protocol("WM_DELETE_WINDOW", cancel)

            btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
            btn_row.pack()
            make_sound_button(btn_row, text="✅ Запустить", command=confirm,
                              fg_color="#d3453f", hover_color="#b83530", width=140, height=40).pack(side="left", padx=5)
            make_sound_button(btn_row, text="❌ Отмена", command=cancel,
                              fg_color="#4a4666", hover_color="#3d3a52", width=140, height=40).pack(side="left", padx=5)
        else:
            # не исполняемый — обычный диалог
            if self._mb.askyesno(
                "Открыть файл?",
                f"Открыть «{filename}»?\n\nПуть: {dest_path}"
            ):
                self._execute_file(dest_path, filename)
            else:
                self.log(f"🚫 Открытие «{filename}» отменено")

    def _execute_file(self, dest_path, filename):
        try:
            if sys.platform == "win32":
                os.startfile(dest_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", dest_path])
            else:
                subprocess.Popen(["xdg-open", dest_path])
            self.log(f"🚀 Файл «{filename}» запущен")
            play_click()
        except Exception as e:
            play_error()
            self._mb.showerror("Ошибка запуска", f"Не удалось запустить «{filename}»:\n{e}")

    def _download_offered_file(self, sender, url, filename, auto_launch=False):
        MAX_SIZE = 500 * 1024 * 1024

        try:
            download_dir = os.path.join(get_launcher_dir(), "download")
            os.makedirs(download_dir, exist_ok=True)

            dest_path = os.path.join(download_dir, filename)
            base, ext = os.path.splitext(dest_path)
            counter = 1
            while os.path.exists(dest_path):
                dest_path = f"{base} ({counter}){ext}"
                counter += 1

            with requests.get(url, stream=True, timeout=15) as r:
                r.raise_for_status()

                content_length = r.headers.get("Content-Length")
                if content_length and int(content_length) > MAX_SIZE:
                    self.after(0, lambda: (play_error(), self._mb.showerror(
                        "Файл слишком большой",
                        f"Файл «{filename}» больше 500 МБ — скачивание отменено."
                    )))
                    return

                downloaded = 0
                with open(dest_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=256 * 1024):
                        if not chunk:
                            continue
                        downloaded += len(chunk)
                        if downloaded > MAX_SIZE:
                            f.close()
                            try:
                                os.remove(dest_path)
                            except Exception:
                                pass
                            self.after(0, lambda: (play_error(), self._mb.showerror(
                                "Файл слишком большой",
                                f"Файл «{filename}» больше 500 МБ — скачивание прервано."
                            )))
                            return
                        f.write(chunk)

            self.log(f"✅ Файл «{filename}» от «{sender}» скачан: {dest_path}")
            self.after(0, lambda: self.show_notification(
                f"Файл «{filename}» от «{sender}» сохранён в папку download", "✅ Файл скачан"
            ))
            # SHA-256, чтобы юзер мог сверить файл с тем, что реально прислал
            # отправитель (лаунчер не проверяет содержимое по ссылке)
            digest = _file_sha256(dest_path)
            if digest:
                self.log(f"🔐 SHA-256 файла: {digest}")
                self.after(0, lambda d=digest, n=filename: self._mb.showinfo(
                    "Файл скачан",
                    f"«{n}» сохранён в папку download.\n\nSHA-256:\n{d}\n\n"
                    f"Можешь сверить с отправителем, если он прислал свой хеш."
                ))
            if auto_launch:
                _path = dest_path
                _name = filename
                self.after(300, lambda: self._prompt_launch_file(_path, _name))
        except Exception as e:
            error_text = str(e)
            self.log(f"❌ Не удалось скачать файл «{filename}»: {error_text}")
            self.after(0, lambda: (play_error(), self._mb.showerror(
                "Ошибка скачивания",
                f"Не удалось скачать файл «{filename}»:\n{error_text}"
            )))

    def _socket_send(self, payload):
        sock = self.client_socket
        if sock is None:
            raise RuntimeError("нет соединения с релеем")
        with self._socket_lock:
            return sock.send(payload)

    def send_message_raw(self, message):
        try:
            if self.client_socket and self.connected:
                self._socket_send(message)
                if not message.startswith("👤"):
                    self.message_history.append(message)
                    self.update_msg_count()
                    self._persist_message(message, mine=True)
                    self.log(f"📤 {message}")
                    text = message.split(": ", 1)[1] if ": " in message and not message.startswith("* ") else message
                    self._update_personal_preview(text, mine=True)

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
            self._socket_send(payload)
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
            size_kb = len(raw) / 1024.0
            self.log(f"🎨 Получил скин для ника '{username}' ({size_kb:.1f} КБ) "
                     f"— сохранил локально: {skin_path}")
            self.show_notification(
                f"Прислал(а) скин для ника «{username}» ({size_kb:.1f} КБ)", "🎨 Скин"
            )
        except Exception as e:
            self.log(f"❌ Не удалось сохранить присланный скин: {e}")

    def update_status(self):
        if self.connected and self.client_socket:
            self.safe_update_widget(self.status_label, text="🟢 Онлайн", text_color="#6fce7f")
        else:
            self.safe_update_widget(self.status_label, text="🔴 Офлайн", text_color="#d3453f")

    def disconnect(self):
        if self._screen_share.get("state"):
            try:
                self.stop_screen_share(notify=False)
            except Exception:
                pass
        if self.connected:
            try:
                if self.client_socket:
                    self._socket_send(f"👤 {self.username} покинул комнату!")
            except:
                pass
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


            if self.running:
                self._auto_reconnect()

    def on_close(self):
        self.withdraw()
        self.is_minimized = True
        play_click()

    def leave_room(self):
        if not self._mb.askyesno(
            "Выйти из комнаты",
            f"Выйти из комнаты «{self.room}»?\n"
            f"Соединение будет разорвано, окно чата закроется."
        ):
            return
        play_click()
        self.log(f"🚪 Выходим из комнаты «{self.room}»...")
        self.running = False
        self.disconnect()
        try:
            if hasattr(self.master, 'active_chat_window') and self.master.active_chat_window is self:
                self.master.active_chat_window = None
        except:
            pass
        try:
            if self.personal_contact and hasattr(self.master, 'active_chat_windows'):
                cid = self.personal_contact.get("id")
                if self.master.active_chat_windows.get(cid) is self:
                    del self.master.active_chat_windows[cid]
        except:
            pass
        try:
            self.destroy()
        except:
            pass

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


def _make_dropdown_chevron_image(size=14, thickness=2,
                                  color_light="#221f30", color_dark="#e5e2f0"):
    def draw(color):
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        pad = size * 0.22
        top_y = size * 0.36
        bottom_y = size * 0.64
        mid_x = size / 2
        d.line([(pad, top_y), (mid_x, bottom_y)], fill=color, width=thickness)
        d.line([(mid_x, bottom_y), (size - pad, top_y)], fill=color, width=thickness)
        return img

    return ctk.CTkImage(light_image=draw(color_light), dark_image=draw(color_dark), size=(size, size))


_AVATAR_COLORS = ["#6d92ff", "#6fce7f", "#d9622f", "#d3453f", "#a56fe0", "#e0a13f", "#4fb8c9", "#e05fa0"]


def make_avatar_image(label_text, size=44):
    label_text = (label_text or "?").strip()
    initial = label_text[0].upper() if label_text else "?"
    color = _AVATAR_COLORS[sum(ord(c) for c in label_text) % len(_AVATAR_COLORS)]

    scale = 4
    big = size * scale
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((0, 0, big - 1, big - 1), fill=color)

    try:
        font = ImageFont.truetype("arialbd.ttf", int(big * 0.45))
    except Exception:
        font = ImageFont.load_default()

    try:
        bbox = d.textbbox((0, 0), initial, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        d.text(((big - text_w) / 2 - bbox[0], (big - text_h) / 2 - bbox[1]),
               initial, fill="#16141f", font=font)
    except Exception:
        pass

    img = img.resize((size, size), Image.LANCZOS)
    return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))


class SearchableComboBox(ctk.CTkFrame):

    _ROW_HEIGHT = 30

    def __init__(self, master, values=None, width=300, height=35,
                 max_visible_items=10, placeholder_text="Поиск версий...",
                 command=None, **kwargs):
        super().__init__(master, width=width, height=height, fg_color="transparent")
        self.grid_propagate(False)
        self.pack_propagate(False)

        self._all_values = list(values) if values else []
        self._max_visible_items = max_visible_items
        self._command = command
        self._popup = None
        self._popup_buttons = []
        self._current_value = self._all_values[0] if self._all_values else ""

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.display_entry = ctk.CTkEntry(self, height=height, corner_radius=5)
        self.display_entry.grid(row=0, column=0, sticky="nsew")
        self.display_entry.configure(state="normal")
        self.display_entry.insert(0, self._current_value)
        self.display_entry.configure(state="readonly")
        self.display_entry.bind("<Button-1>", lambda e: self._toggle_popup())

        self._chevron_image = _make_dropdown_chevron_image()
        self.arrow_btn = ctk.CTkButton(
            self, text="", image=self._chevron_image, width=28, height=height, corner_radius=5,
            fg_color=["#e4e1f2", "#302c46"], hover_color=["#3d6bf0", "#3d6bf0"],
            command=self._toggle_popup
        )
        self.arrow_btn.grid(row=0, column=1, padx=(4, 0))

        self.bind("<Destroy>", lambda e: self._close_popup())

    def get(self):
        return self._current_value

    def set(self, value):
        self._current_value = value
        try:
            self.display_entry.configure(state="normal")
            self.display_entry.delete(0, "end")
            self.display_entry.insert(0, value)
            self.display_entry.configure(state="readonly")
        except Exception:
            pass

    def configure(self, **kwargs):
        if "values" in kwargs:
            values = kwargs.pop("values")
            self._all_values = list(values) if values else []
            if self._popup is not None:
                self._render_list(self._all_values)
        if "state" in kwargs:
            state = kwargs.pop("state")
            try:
                self.display_entry.configure(state="readonly" if state != "disabled" else "disabled")
                self.arrow_btn.configure(state=state)
            except Exception:
                pass
        if "text_color" in kwargs:
            tc = kwargs.pop("text_color")
            try:
                self.display_entry.configure(text_color=tc)
            except Exception:
                pass
        if "command" in kwargs:
            self._command = kwargs.pop("command")
        if kwargs:
            try:
                super().configure(**kwargs)
            except Exception:
                pass

    def _toggle_popup(self):
        if self._popup is not None and self._popup.winfo_exists():
            self._close_popup()
        else:
            self._open_popup()

    def _open_popup(self):
        if not self.winfo_exists():
            return

        self._popup = ctk.CTkToplevel(self)
        self._popup.overrideredirect(True)
        self._popup.attributes("-topmost", True)
        try:
            self._popup.transient(self.winfo_toplevel())
        except Exception:
            pass

        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height() + 2
        popup_width = max(self.winfo_width(), 220)
        self._popup.geometry(f"{popup_width}x10+{x}+{y}")

        container = ctk.CTkFrame(self._popup, corner_radius=6,
                                  fg_color=["#ffffff", "#1a1826"],
                                  border_width=1, border_color=["#c9c4de", "#302c46"])
        container.pack(fill="both", expand=True)

        self._search_var = tk.StringVar()
        search_entry = ctk.CTkEntry(container, height=30, corner_radius=4,
                                     placeholder_text="🔍 Поиск установленных версий",
                                     textvariable=self._search_var)
        search_entry.pack(fill="x", padx=6, pady=(6, 4))
        search_entry.bind("<KeyRelease>", lambda e: self._on_search())
        search_entry.bind("<Escape>", lambda e: self._close_popup())

        list_height = self._ROW_HEIGHT * min(len(self._all_values) or 1, self._max_visible_items)
        self._scroll_frame = ctk.CTkScrollableFrame(
            container, height=list_height, corner_radius=0,
            fg_color="transparent"
        )
        self._scroll_frame.pack(fill="both", expand=True, padx=4, pady=(0, 6))
        self._scroll_frame.columnconfigure(0, weight=1)

        self._render_list(self._all_values)

        self._popup.update_idletasks()
        total_height = search_entry.winfo_reqheight() + list_height + 24
        self._popup.geometry(f"{popup_width}x{total_height}+{x}+{y}")

        search_entry.focus_set()

        self._popup.bind("<FocusOut>", self._on_popup_focus_out)
        self._popup_click_id = self.winfo_toplevel().bind(
            "<Button-1>", self._on_root_click, add="+"
        )

    def _render_list(self, values):
        if self._popup is None or not self._popup.winfo_exists():
            return
        for btn in self._popup_buttons:
            try:
                btn.destroy()
            except Exception:
                pass
        self._popup_buttons = []

        if not values:
            empty_label = ctk.CTkLabel(self._scroll_frame, text="Ничего не найдено",
                                        text_color=["#8f89a8", "#7a7791"])
            empty_label.grid(row=0, column=0, sticky="ew", pady=6)
            self._popup_buttons.append(empty_label)
            return

        for i, val in enumerate(values):
            is_selected = (val == self._current_value)
            btn = ctk.CTkButton(
                self._scroll_frame, text=val, anchor="w", height=self._ROW_HEIGHT - 4,
                corner_radius=4,
                fg_color=["#e4e1f2", "#302c46"] if is_selected else "transparent",
                hover_color=["#dedaee", "#26243a"],
                text_color=["#221f30", "#e5e2f0"],
                command=lambda v=val: self._on_select(v)
            )
            btn.grid(row=i, column=0, sticky="ew", pady=1)
            self._popup_buttons.append(btn)

    def _on_search(self):
        query = self._search_var.get().strip().lower()
        if not query:
            filtered = self._all_values
        else:
            filtered = [v for v in self._all_values if query in v.lower()]
        self._render_list(filtered)

    def _on_select(self, value):
        self.set(value)
        self._close_popup()
        if self._command:
            try:
                self._command(value)
            except Exception:
                pass

    def _on_popup_focus_out(self, event):
        self.after(150, self._close_popup_if_unfocused)

    def _close_popup_if_unfocused(self):
        try:
            if self._popup is None or not self._popup.winfo_exists():
                return
            focused = self._popup.focus_get()
            if focused is None:
                self._close_popup()
        except Exception:
            self._close_popup()

    def _on_root_click(self, event):
        if self._popup is None or not self._popup.winfo_exists():
            return
        widget = event.widget
        try:
            if str(widget).startswith(str(self._popup)):
                return
            if str(widget).startswith(str(self)):
                return
        except Exception:
            pass
        self._close_popup()

    def _close_popup(self):
        if self._popup is not None:
            try:
                self.winfo_toplevel().unbind("<Button-1>", self._popup_click_id)
            except Exception:
                pass
            try:
                self._popup.destroy()
            except Exception:
                pass
            self._popup = None
            self._popup_buttons = []


class LauncherApp(ctk.CTk):
    instance = None

    def __init__(self):
        global MINECRAFT_DIR, GAME_DIR, ACCOUNTS_FILE, PROFILES_FILE, LAUNCHER_PROFILES_FILE

        super().__init__()
        LauncherApp.instance = self


        self.title("67Launcher - МЯУ")
        window_width, window_height = 1200, 950
        self.minsize(1000, 800)
        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (window_width // 2)
        y = (screen_height // 2) - (window_height // 2)
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self._splash = ctk.CTkFrame(self, fg_color="#16141f")
        self._splash.grid(row=0, column=0, sticky="nsew")
        self._splash.grid_columnconfigure(0, weight=1)
        self._splash.grid_rowconfigure(0, weight=1)

        
        
        self._splash_gif_label = ctk.CTkLabel(self._splash, text="")
        self._splash_gif_label.place(x=0, y=0, relwidth=1, relheight=1)
        self._splash_gif_frames = []
        self._splash_gif_running = True
        self._splash_size = (window_width, window_height)
        self._load_splash_gif()

        splash_inner = ctk.CTkFrame(self._splash, fg_color="transparent")
        splash_inner.grid(row=0, column=0)
        ctk.CTkLabel(splash_inner, text="⚡ 67Launcher", font=ctk.CTkFont(size=30, weight="bold"),
                     text_color="#6d92ff").pack(pady=(0, 14))
        self._splash_status = ctk.CTkLabel(splash_inner, text="⏳ Загрузка... бабайка.ехе",
                                            font=ctk.CTkFont(size=15), text_color="#a8a4bd")
        self._splash_status.pack()
        splash_inner.lift()

        try:
            self.update()
        except Exception:
            pass

        self.after(10, self._finish_startup)

    def _set_splash_status(self, text):
        try:
            if self._splash_status.winfo_exists():
                self._splash_status.configure(text=text)


                self.update()
        except Exception:
            pass

    def _find_splash_gif_path(self):
        base_dirs = []
        if hasattr(sys, "_MEIPASS"):
            base_dirs.append(os.path.join(sys._MEIPASS, "resources", "gif"))
        base_dirs.append(os.path.join(get_launcher_dir(), "resources", "gif"))
        base_dirs.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "gif"))
        base_dirs.append(os.path.join(os.path.abspath("."), "resources", "gif"))
        seen = set()
        for d in base_dirs:
            if d in seen:
                continue
            seen.add(d)
            try:
                if os.path.isdir(d):
                    gifs = [f for f in os.listdir(d) if f.lower().endswith(".gif")]
                    if gifs:
                        return os.path.join(d, random.choice(gifs))
            except Exception:
                pass
        return None

    def _load_splash_gif(self):
        gif_path = self._find_splash_gif_path()
        if not gif_path:
            print("[splash] В resources/gif не найдено ни одной .gif — "
                  "фон на загрузке не покажется")
            return
        target_w, target_h = getattr(self, "_splash_size", (1200, 950))
        try:
            img = Image.open(gif_path)
            frames = []
            for frame in ImageSequence.Iterator(img):
                duration = frame.info.get("duration", 80)
                fitted = self._fit_cover(frame.convert("RGBA"), target_w, target_h)
                frames.append((fitted, max(int(duration), 20)))
            if not frames:
                return
        except Exception as e:
            print(f"[splash] Не удалось загрузить {gif_path}: {e}")
            return
        self._start_splash_gif(frames, (target_w, target_h))

    @staticmethod
    def _fit_cover(im, target_w, target_h):
        src_w, src_h = im.size
        if src_w <= 0 or src_h <= 0 or target_w <= 0 or target_h <= 0:
            return im
        scale = max(target_w / src_w, target_h / src_h)
        new_w = max(1, round(src_w * scale))
        new_h = max(1, round(src_h * scale))
        resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS", Image.BICUBIC)
        im = im.resize((new_w, new_h), resample)
        left = max(0, (new_w - target_w) // 2)
        top = max(0, (new_h - target_h) // 2)
        return im.crop((left, top, left + target_w, top + target_h))

    def _start_splash_gif(self, frames, size):
        if not getattr(self, "_splash_gif_running", False):
            return
        try:
            if not self._splash_gif_label.winfo_exists():
                return
        except Exception:
            return
        self._splash_gif_frames = [
            (ctk.CTkImage(light_image=im, dark_image=im, size=size), dur) for im, dur in frames
        ]
        self._splash_gif_index = 0
        self._animate_splash_gif()

    def _animate_splash_gif(self):
        if not self._splash_gif_running or not self._splash_gif_frames:
            return
        try:
            if not self._splash_gif_label.winfo_exists():
                return
        except Exception:
            return
        image, duration = self._splash_gif_frames[self._splash_gif_index]
        try:
            self._splash_gif_label.configure(image=image)
        except Exception:
            return
        self._splash_gif_index = (self._splash_gif_index + 1) % len(self._splash_gif_frames)
        self.after(duration, self._animate_splash_gif)

    def _finish_startup(self):
        global MINECRAFT_DIR, GAME_DIR, ACCOUNTS_FILE, PROFILES_FILE, LAUNCHER_PROFILES_FILE

        LauncherApp.setup_tray_icons(self)
        self.settings = load_launcher_settings()
        ensure_user_id(self.settings)
        self.settings.setdefault("personal_chats", [])
        # Safe mode: глобальный тумблер «выключить всё опасное разом»
        # (удалённое управление, трансляция экрана, запуск файлов)
        self.safe_mode = bool(self.settings.get("safe_mode", False))
        self.stats = load_stats()
        self._secret_launcher = None
        self.game_console = None
        self.active_chat_window = None
        self.active_chat_windows = {}
        self.chats_list_refresh_callback = None
        self._chat_init_log_shown = False

        threading.Thread(target=fetch_active_relay_url, daemon=True).start()


        self._dm_inbox_running = True
        threading.Thread(target=self._dm_inbox_loop, daemon=True).start()

        self._set_splash_status("⏳ Загрузка настроек...")

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

        self._set_splash_status("⏳ Строим интерфейс...")
        self.create_widgets()


        try:
            self._splash.tkraise()
        except Exception:
            pass
        self._set_splash_status("⏳ Читаем аккаунты и моды...")
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

        self.start_idle_timer()


        self._splash_gif_running = False
        try:
            self._splash.destroy()
        except Exception:
            pass

    def create_emoji_icon(emoji_text="💬"):
        img = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("seguiemj.ttf", 48)
            d.text((8, 4), emoji_text, font=font, embedded_color=True)
        except:
            d.ellipse((8, 8, 56, 56), fill=(61, 107, 240))
            d.text((22, 16), "C", fill=(255, 255, 255))
        return img

    def create_launcher_icon():
        img = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rectangle((4, 4, 60, 60), fill="#3d6bf0", outline="#ffffff", width=2)
        try:
            font = ImageFont.truetype("arialbd.ttf", 28)
            d.text((14, 12), "67", fill=(255, 255, 255), font=font)
        except:
            d.text((14, 12), "67", fill=(255, 255, 255))
        return img

    @staticmethod
    def setup_tray_icons(launcher_app):
        def show_chat_only(icon, item):
            launcher_app.after(0, lambda: launcher_app.open_chat_from_tray(icon))

        def show_all_chats(icon, item):
            launcher_app.after(0, lambda: launcher_app.open_chat_from_tray(icon, show_all=True))

        def hide_chats(icon, item):
            launcher_app.after(0, launcher_app.hide_chats_from_tray)

        chat_menu = pystray.Menu(
            pystray.MenuItem("💬 Открыть Чат", show_chat_only, default=True),
            pystray.MenuItem("📚 Показать все чаты", show_all_chats),
            pystray.MenuItem("❌ Скрыть чаты", hide_chats)
        )
        chat_icon = pystray.Icon("67_chat", LauncherApp.create_emoji_icon("💬"), "Чат 67Launcher", chat_menu)

        def show_launcher_only(icon, item):
            launcher_app.after(0, lambda: (launcher_app.deiconify(), launcher_app.lift(), launcher_app.focus_force()))

        def quit_app(icon, item):
            chat_icon.stop()
            icon.stop()
            launcher_app.after(0, launcher_app.destroy)

        launcher_menu = pystray.Menu(
            pystray.MenuItem(" Открыть 67Launcher", show_launcher_only, default=True),
            pystray.MenuItem("❌ Полный выход", quit_app)
        )
        launcher_icon = pystray.Icon("67_launcher", LauncherApp.create_launcher_icon(), "67Launcher", launcher_menu)

        threading.Thread(target=chat_icon.run, daemon=True).start()
        threading.Thread(target=launcher_icon.run, daemon=True).start()

    def _live_chat_windows(self):
        windows, seen = [], set()
        for w in list(self.active_chat_windows.values()) + [self.active_chat_window]:
            if w is None or id(w) in seen:
                continue
            seen.add(id(w))
            try:
                if w.winfo_exists():
                    windows.append(w)
            except Exception:
                pass
        return windows

    def open_chat_from_tray(self, icon=None, show_all=False):
        windows = self._live_chat_windows()
        if not windows:
            self.log("ℹ️ Нажали на иконку чата, но открытых чатов нет")
            try:
                if icon is not None:
                    icon.notify("Чат сейчас не запущен. Открой его в лаунчере кнопкой «Чат».",
                                "Чат 67Launcher")
            except Exception:
                pass
            return
        if show_all:
            targets = windows
        else:
            with_unread = [w for w in windows if getattr(w, "unread_count", 0) > 0
                           or (getattr(w, "personal_contact", None) or {}).get("unread")]
            last = self.active_chat_window if self.active_chat_window in windows else windows[-1]
            targets = [with_unread[0] if with_unread else last]
        for w in targets:
            try:
                w.restore_chat_only()
            except Exception as e:
                self.log(f"❌ Чат из трея не открылся: {e}")

    def hide_chats_from_tray(self):
        for w in self._live_chat_windows():
            try:
                w.withdraw()
                w.is_minimized = True
            except Exception:
                pass

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

    def toggle_safe_mode(self):
        """Глобальный выключатель опасного: удалённый ввод, трансляция экрана
        и запуск файлов. Чат, комнаты, моды и игры продолжают работать."""
        switch = getattr(self, "safe_mode_switch", None)
        self.safe_mode = bool(switch.get()) if switch is not None else not self.safe_mode
        self.settings["safe_mode"] = self.safe_mode
        save_launcher_settings(self.settings)
        if self.safe_mode:
            # На всякий случай глушим всё, что могло остаться активным
            for w in self._live_chat_windows():
                try:
                    if w._screen_share.get("role") == "host":
                        w.stop_screen_share(notify=True)
                except Exception:
                    pass
            play_click()
            messagebox.showinfo(
                "Safe mode включён",
                "Удалённое управление, трансляция экрана и запуск файлов отключены.\n"
                "Чат, моды и игры работают как обычно."
            )
        else:
            play_click()
        self.log(f"🔒 Safe mode: {'включён' if self.safe_mode else 'выключен'}")

    def remove_firewall_rules_from_settings(self):
        """Кнопка в Настройки → Безопасность: снимает правила 67Launcher с фаервола."""
        if not messagebox.askyesno(
            "Удалить правило фаервола?",
            "Удалить правила брандмауэра «67Launcher Chat» и «67Launcher Chat All»?\n\n"
            "Прямое P2P-соединение перестанет работать (через релей — работает как обычно)."
        ):
            return
        if remove_firewall_rule():
            messagebox.showinfo("Готово", "Правило удалено")
        else:
            messagebox.showerror("Не удалось", "Не получилось удалить правило. Проверь права и попробуй вручную.")

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
        try:
            if hasattr(self, 'account_combo'):
                self.settings["last_account"] = self.account_combo.get()
            if hasattr(self, 'version_combo'):
                self.settings["last_version"] = self.version_combo.get()
            save_launcher_settings(self.settings)
        except Exception:
            pass

    def on_account_combo_change(self, selected_username=None):
        self.update_combo_text_color(selected_username)
        self.save_current_selection()

    def on_version_combo_change(self, selected_version=None):
        self.save_current_selection()

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

    def show_support_dialog(self):
        if self.settings.get("support_shown_5", False):
            return
        if has_microsoft_account():
            self.settings["support_shown_5"] = True
            save_launcher_settings(self.settings)
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
        current = self.account_combo.get()
        self.account_combo.configure(values=usernames)
        if current in usernames:
            self.account_combo.set(current)
        elif usernames and usernames[0] != "Нет аккаунтов":
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
                err_msg = str(e)
                self.after(0, lambda: login_failed(err_msg))

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
            command=self.on_account_combo_change
        )
        self.account_combo.grid(row=2, column=0, sticky="w", pady=(0, 15))
        try:
            self.account_combo._entry.bind("<KeyRelease>", lambda e: self.update_combo_text_color())
            self.account_combo._entry.bind("<FocusOut>", lambda e: self.on_account_combo_change())
        except Exception:
            pass

        ctk.CTkLabel(main_frame, text="📦 Версия:", font=ctk.CTkFont(size=14)).grid(row=3, column=0, sticky="w")
        self.version_combo = SearchableComboBox(main_frame, values=["Нет версий"], width=300, height=35,
                                                 max_visible_items=10, command=self.on_version_combo_change)
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

        ctk.CTkLabel(main_frame, text="🔒 Безопасность", font=ctk.CTkFont(size=14, weight="bold")).grid(row=9,
                                                                                                            column=0,
                                                                                                            sticky="w",
                                                                                                            pady=(15, 5))
        sec_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        sec_frame.grid(row=10, column=0, sticky="ew")
        sec_frame.grid_columnconfigure(0, weight=1)

        self.safe_mode_switch = ctk.CTkSwitch(
            sec_frame,
            text="Safe mode — отключить всё удалённое управление и запуск файлов",
            command=self.toggle_safe_mode,
            font=ctk.CTkFont(size=13)
        )
        if self.safe_mode:
            self.safe_mode_switch.select()
        else:
            self.safe_mode_switch.deselect()
        self.safe_mode_switch.grid(row=0, column=0, sticky="w", pady=2)

        ctk.CTkLabel(
            sec_frame,
            text=("В safe mode чат, моды и игры работают как обычно, но чужие игроки "
                  "не смогут смотреть твой экран, водить мышью и запускать присланные файлы. "
                  "Запросы на трансляцию будут отклоняться автоматически."),
            font=ctk.CTkFont(size=11), text_color="#a8a4bd",
            wraplength=640, justify="left"
        ).grid(row=1, column=0, sticky="w", pady=(2, 8))

        ctk.CTkLabel(sec_frame, text="Фаервол (нужен только для прямого P2P, через релей — не нужен):",
                     font=ctk.CTkFont(size=12, weight="bold"), text_color="#a8a4bd").grid(
            row=2, column=0, sticky="w", pady=(4, 4))
        ctk.CTkButton(
            sec_frame, text="🗑️ Удалить правило фаервола 67Launcher",
            command=self.remove_firewall_rules_from_settings,
            fg_color="#d3453f", hover_color="#b83530"
        ).grid(row=3, column=0, sticky="w", pady=(0, 15))

        ctk.CTkLabel(main_frame, text="🔗 Полезные ссылки", font=ctk.CTkFont(size=14, weight="bold")).grid(row=11,
                                                                                                           column=0,
                                                                                                           sticky="w",
                                                                                                           pady=(15, 10))
        links_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        links_frame.grid(row=12, column=0, sticky="w", pady=(0, 15))

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
                    # TODO(upstream): show_first_launch_server_dialog вызывается,
                    # но в KotiPlayYT/67launcher (495c0f7) такого метода нет —
                    # вызов падал с AttributeError на первом запуске игры.
                    # Своего диалога не придумываем: ждём реализации от автора.
                    # Когда метод появится в апстриме — раскомментировать.
                    # self.after(0, self.show_first_launch_server_dialog)
                    pass

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


        def _check_relay():
            try:
                new_relay, relay_status = fetch_active_relay_url(timeout=3)
                status_text = {
                    "updated": f"🌐 Релей обновлён из GitHub: {new_relay}",
                    "unchanged": f"🌐 Релей из GitHub (без изменений): {new_relay}",
                    "invalid_content": "⚠️ relay.active.txt на GitHub содержит некорректный адрес, использую прежний релей",
                    "network_error": "⚠️ Не удалось проверить relay.active.txt (нет сети/лимиты API), использую прежний релей",
                }.get(relay_status, f"🌐 Релей: {new_relay}")
                self.log(status_text)
            except Exception as e:
                self.log(f"⚠️ Ошибка проверки relay.active.txt: {e}")

        threading.Thread(target=_check_relay, daemon=True).start()

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
            self.chats_list_refresh_callback = None
            release_and_destroy(dialog)

        dialog.protocol("WM_DELETE_WINDOW", _save_setup_size_and_close)

        dialog.update_idletasks()
        width = dialog.winfo_width()
        height = dialog.winfo_height()
        x = (dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (dialog.winfo_screenheight() // 2) - (height // 2)
        dialog.geometry(f"{width}x{height}+{x}+{y}")

        main_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(main_frame, text="💬 Чат",
                     font=ctk.CTkFont(size=24, weight="bold"), text_color="#6d92ff").pack(pady=(0, 10))


        SHOW_PERSONAL_CHATS = False

        switch_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        if SHOW_PERSONAL_CHATS:
            switch_frame.pack(fill="x", pady=(0, 12))

        def switch_view(view, user_action=True):
            if not SHOW_PERSONAL_CHATS:
                view = "group"
            if view == "group":
                chats_container.pack_forget()
                group_container.pack(fill="both", expand=True)
                group_btn.configure(fg_color="#6d92ff", hover_color="#5a7dd8")
                chats_btn.configure(fg_color="#2b2840", hover_color="#3d3a52")
                self.chats_list_refresh_callback = None
            else:
                group_container.pack_forget()
                chats_container.pack(fill="both", expand=True)
                chats_btn.configure(fg_color="#6d92ff", hover_color="#5a7dd8")
                group_btn.configure(fg_color="#2b2840", hover_color="#3d3a52")
                self.chats_list_refresh_callback = refresh_chats_list
                refresh_chats_list()
            if user_action:
                play_click()

                if self.settings.get("chat_setup_last_view") != view:
                    self.settings["chat_setup_last_view"] = view
                    save_launcher_settings(self.settings)

        group_btn = make_sound_button(switch_frame, text="👥 Групповой чат",
                                      command=lambda: switch_view("group"),
                                      fg_color="#6d92ff", hover_color="#5a7dd8",
                                      height=36, font=ctk.CTkFont(size=13, weight="bold"))
        group_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))

        chats_btn = make_sound_button(switch_frame, text="💌 Чаты (новое!)",
                                      command=lambda: switch_view("chats"),
                                      fg_color="#2b2840", hover_color="#3d3a52",
                                      height=36, font=ctk.CTkFont(size=13, weight="bold"))
        chats_btn.pack(side="left", fill="x", expand=True, padx=(5, 0))

        group_container = ctk.CTkFrame(main_frame, fg_color="transparent")
        group_container.pack(fill="both", expand=True)

        chats_container = ctk.CTkFrame(main_frame, fg_color="transparent")


        relay_frame = ctk.CTkFrame(group_container, fg_color="#100e1a", corner_radius=10)
        relay_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(relay_frame, text="🌍 ПОДКЛЮЧЕНИЕ ЧЕРЕЗ РЕЛЕЙ (работает через интернет, без проброса портов):",
                     font=ctk.CTkFont(size=12, weight="bold"), text_color="#6fce7f",
                     wraplength=520, justify="center").pack(pady=(8, 4), padx=10)
        relay_row = ctk.CTkFrame(relay_frame, fg_color="transparent")
        relay_row.pack(pady=(0, 8), padx=10, fill="x")

        custom_relay_url = ""
        try:
            custom_relay_url = (self.settings.get("custom_relay_url", "") or "").strip()
        except:
            pass

        relay_entry = ctk.CTkEntry(relay_row, placeholder_text=RELAY_URL, height=32,
                                   font=ctk.CTkFont(size=12))
        relay_entry.pack(side="left", fill="x", expand=True)
        relay_entry.insert(0, custom_relay_url or RELAY_URL)

        # Куда реально уходят сообщения — показываем явно и цветом
        ctk.CTkLabel(
            relay_frame,
            text=f"📡 Сейчас чат подключается к: {RELAY_URL}",
            font=ctk.CTkFont(size=11, weight="bold"), text_color="#6fce7f",
            wraplength=520, justify="center"
        ).pack(pady=(0, 4), padx=10)
        ctk.CTkLabel(
            relay_frame,
            text="⚠️ Адрес подгружается автоматически с GitHub. Если он не совпадает с тем, что ты ожидал — сообщения идут чужому серверу. Впиши свой wss:// ниже.",
            font=ctk.CTkFont(size=10), text_color="#d9622f",
            wraplength=520, justify="center"
        ).pack(pady=(0, 4), padx=10)

        def reset_relay():
            relay_entry.delete(0, 'end')
            relay_entry.insert(0, RELAY_URL)
            play_click()

        reset_relay_btn = make_sound_button(relay_row, text="↩️ По умолчанию",
                                            command=reset_relay,
                                            width=110, height=32,
                                            fg_color="#2b2840", hover_color="#3d3a52",
                                            font=ctk.CTkFont(size=11))
        reset_relay_btn.pack(side="left", padx=(6, 0))

        ctk.CTkLabel(relay_frame, text="Можно вписать свой адрес релея (wss://...), если не хотите использовать релей по умолчанию",
                     font=ctk.CTkFont(size=10), text_color="#8b87a3",
                     wraplength=520, justify="center").pack(pady=(0, 8), padx=10)

        instr_frame = ctk.CTkFrame(group_container, fg_color="#201d30", corner_radius=10)
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

        mode_frame = ctk.CTkFrame(group_container, fg_color="transparent")
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

        settings_frame = ctk.CTkFrame(group_container, fg_color="transparent")
        settings_frame.pack(fill="x", pady=(0, 10))

        room_row = ctk.CTkFrame(settings_frame, fg_color="transparent")
        room_row.pack(fill="x", pady=3)

        ctk.CTkLabel(room_row, text="🚪 Код комнаты:", font=ctk.CTkFont(size=13, weight="bold"),
                     width=140).pack(side="left")
        room_entry = ctk.CTkEntry(room_row, placeholder_text="Код комнаты сюда", width=180, height=35,
                                  font=ctk.CTkFont(size=13))
        room_entry.pack(side="left", padx=(10, 0))

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

        btn_frame = ctk.CTkFrame(group_container, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(5, 0))

        def open_chat_and_finish(mode, room, relay_url):
            try:
                self.settings["custom_relay_url"] = relay_url if relay_url != RELAY_URL else ""
                save_launcher_settings(self.settings)
            except:
                pass
            _save_setup_size_only()
            self.chats_list_refresh_callback = None
            release_and_destroy(dialog)
            chat_window = ChatWindow(self, mode, room, relay_url=relay_url)
            self.active_chat_window = chat_window
            self.log(f"💬 Чат открыт в режиме: {mode}, комната: {room}, релей: {relay_url}")

        def start_chat():
            try:
                mode = mode_var.get()
                room = room_entry.get().strip()
                relay_url = relay_entry.get().strip() or RELAY_URL

                if not room:
                    play_error()
                    messagebox.showwarning("Ошибка", "Код комнаты пустой")
                    return

                if mode != "server":
                    open_chat_and_finish(mode, room, relay_url)
                    return

                start_btn.configure(state="disabled", text="⏳ Проверяем код...")
                cancel_btn.configure(state="disabled")

                def do_check():
                    try:
                        active, count, max_size = check_room_active(relay_url, room, timeout=5)
                        error_text = None
                    except Exception as e:
                        active, count, max_size, error_text = False, 0, 20, str(e)

                    def after_check():
                        try:
                            start_btn.configure(state="normal", text="🚀 ЗАПУСТИТЬ ЧАТ")
                            cancel_btn.configure(state="normal")
                        except:
                            return

                        if error_text:
                            self.log(f"⚠️ Не удалось проверить код комнаты ({error_text}) — создаю без проверки")
                            open_chat_and_finish(mode, room, relay_url)
                        elif active and count >= max_size:
                            play_error()
                            messagebox.showwarning(
                                "Комната заполнена",
                                f"Комната «{room}» уже существует и заполнена ({count}/{max_size}).\n"
                                f"Выберите другой код комнаты."
                            )
                        elif active:
                            play_click()
                            join_instead = messagebox.askyesno(
                                "Комната уже существует",
                                f"Комната «{room}» уже существует ({count}/{max_size} участников) —\n"
                                f"её создавать не нужно, можно просто присоединиться.\n\n"
                                f"Присоединиться к ней как гость?"
                            )
                            if join_instead:
                                open_chat_and_finish("client", room, relay_url)
                        else:
                            open_chat_and_finish(mode, room, relay_url)

                    try:
                        dialog.after(0, after_check)
                    except:
                        pass

                threading.Thread(target=do_check, daemon=True).start()

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


        my_user_id = ensure_user_id(self.settings)

        my_id_frame = ctk.CTkFrame(chats_container, fg_color="#100e1a", corner_radius=10)
        my_id_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(my_id_frame, text="🆔 Твой личный ID — дай его другу, чтобы он тебя добавил:",
                     font=ctk.CTkFont(size=12, weight="bold"), text_color="#6fce7f",
                     wraplength=520, justify="center").pack(pady=(8, 4), padx=10)

        my_id_row = ctk.CTkFrame(my_id_frame, fg_color="transparent")
        my_id_row.pack(pady=(0, 8), padx=10, fill="x")

        my_id_entry = ctk.CTkEntry(my_id_row, height=32, font=ctk.CTkFont(size=13, weight="bold"),
                                   justify="center")
        my_id_entry.insert(0, my_user_id)
        my_id_entry.configure(state="disabled")
        my_id_entry.pack(side="left", fill="x", expand=True)

        copy_my_id_btn = make_sound_button(my_id_row, text="📋 Копировать",
                                           command=lambda: self.copy_ip_to_clipboard(my_user_id),
                                           width=110, height=32,
                                           fg_color="#6d92ff", hover_color="#5a7dd8",
                                           font=ctk.CTkFont(size=11))
        copy_my_id_btn.pack(side="left", padx=(6, 0))

        add_user_btn = make_sound_button(chats_container, text="➕ Добавить пользователя",
                                         command=lambda: open_add_contact_dialog(),
                                         fg_color="#6fce7f", hover_color="#5cb56c", text_color="#16141f",
                                         font=ctk.CTkFont(size=14, weight="bold"), height=42)
        add_user_btn.pack(fill="x", pady=(0, 10))

        chats_scroll = ctk.CTkScrollableFrame(chats_container, fg_color="#100e1a", corner_radius=10)
        chats_scroll.pack(fill="both", expand=True)

        def remove_contact(contact):
            if not messagebox.askyesno(
                "Удалить чат",
                f"Удалить переписку с «{contact.get('name')}»?\n\n"
                f"История хранится только у вас локально — у собеседника его копия чата останется."
            ):
                return
            contacts = self.settings.get("personal_chats", [])
            self.settings["personal_chats"] = [c for c in contacts if c.get("id") != contact.get("id")]
            save_launcher_settings(self.settings)
            delete_chat_history(contact.get("id"))
            play_click()
            refresh_chats_list()

        def open_personal_chat_and_finish(contact):
            their_id = contact.get("id")

            existing = self.active_chat_windows.get(their_id)
            if existing:
                try:
                    if existing.winfo_exists():
                        existing.restore_chat_only()
                        self.active_chat_window = existing
                        _save_setup_size_and_close()
                        return
                except:
                    pass

            room = "dm-" + "-".join(sorted([my_user_id, their_id]))
            relay_url = relay_entry.get().strip() or RELAY_URL

            def do_negotiate():
                try:
                    active, _count, _max_size = check_room_active(relay_url, room, timeout=5)
                    negotiated_mode = "client" if active else "server"
                except Exception:
                    negotiated_mode = "server"

                def after_negotiate():
                    try:
                        self.settings["custom_relay_url"] = relay_url if relay_url != RELAY_URL else ""
                        save_launcher_settings(self.settings)
                    except:
                        pass
                    _save_setup_size_only()
                    self.chats_list_refresh_callback = None
                    release_and_destroy(dialog)
                    chat_window = ChatWindow(self, negotiated_mode, room, relay_url=relay_url,
                                             personal_contact=contact)
                    self.active_chat_window = chat_window
                    self.active_chat_windows[their_id] = chat_window
                    self.log(f"💬 Личный чат с «{contact.get('name')}» открыт (комната {room})")

                try:
                    dialog.after(0, after_negotiate)
                except:
                    pass

            threading.Thread(target=do_negotiate, daemon=True).start()

        def refresh_chats_list():
            try:
                for w in chats_scroll.winfo_children():
                    w.destroy()
            except:
                return

            contacts = self.settings.get("personal_chats", [])
            if not contacts:
                ctk.CTkLabel(chats_scroll,
                             text="Здесь пока пусто.\nНажми «Добавить пользователя», чтобы начать переписку.",
                             font=ctk.CTkFont(size=13), text_color="#8b87a3",
                             justify="center").pack(pady=30)
                return

            contacts_sorted = sorted(contacts, key=lambda c: c.get("last_message_ts", 0), reverse=True)
            for contact in contacts_sorted:
                row = ctk.CTkFrame(chats_scroll, fg_color="#201d30", corner_radius=10, cursor="hand2")
                row.pack(fill="x", pady=4, padx=4)

                display_name = contact.get("name") or contact.get("id", "???")

                avatar_lbl = ctk.CTkLabel(row, image=make_avatar_image(display_name), text="", cursor="hand2")
                avatar_lbl.pack(side="left", padx=(10, 8), pady=10)

                text_col = ctk.CTkFrame(row, fg_color="transparent", cursor="hand2")
                text_col.pack(side="left", fill="both", expand=True, pady=8)

                name_row = ctk.CTkFrame(text_col, fg_color="transparent", cursor="hand2")
                name_row.pack(fill="x")

                ctk.CTkLabel(name_row, text=display_name, font=ctk.CTkFont(size=14, weight="bold"),
                            anchor="w", cursor="hand2").pack(side="left")

                if contact.get("unread"):
                    ctk.CTkLabel(name_row, text="●", text_color="#6d92ff",
                                font=ctk.CTkFont(size=14), cursor="hand2").pack(side="left", padx=(6, 0))

                ctk.CTkLabel(name_row, text=contact.get("last_message_time", ""),
                            font=ctk.CTkFont(size=11), text_color="#8b87a3",
                            cursor="hand2").pack(side="right")

                preview_row = ctk.CTkFrame(text_col, fg_color="transparent", cursor="hand2")
                preview_row.pack(fill="x", pady=(2, 0))

                last_message = contact.get("last_message", "")
                if last_message and contact.get("last_message_mine"):
                    ctk.CTkLabel(preview_row, text="✓✓", font=ctk.CTkFont(size=11),
                                text_color="#6d92ff", cursor="hand2").pack(side="left", padx=(0, 4))

                preview_text = last_message[:60] if last_message else "Нажми, чтобы начать переписку"
                ctk.CTkLabel(preview_row, text=preview_text, font=ctk.CTkFont(size=12),
                            text_color="#8b87a3" if last_message else "#6d6785",
                            anchor="w", cursor="hand2").pack(side="left", fill="x")

                del_btn = make_sound_button(row, text="🗑️", command=lambda c=contact: remove_contact(c),
                                            width=32, height=32, fg_color="transparent",
                                            hover_color="#3d3a52", font=ctk.CTkFont(size=13))
                del_btn.pack(side="right", padx=(0, 8))

                def _bind_open(widget, c=contact):
                    widget.bind("<Button-1>", lambda e: open_personal_chat_and_finish(c))


                clickable_widgets = [row, avatar_lbl, text_col, name_row, preview_row]
                clickable_widgets += name_row.winfo_children()
                clickable_widgets += preview_row.winfo_children()
                for widget in clickable_widgets:
                    _bind_open(widget)

        def open_add_contact_dialog():
            add_dialog = ctk.CTkToplevel(dialog)
            add_dialog.title("➕ Добавить пользователя")
            add_dialog.geometry("420x320")
            add_dialog.resizable(False, False)
            add_dialog.grab_set()
            add_dialog.transient(dialog)

            frame = ctk.CTkFrame(add_dialog, fg_color="transparent")
            frame.pack(fill="both", expand=True, padx=20, pady=20)

            ctk.CTkLabel(frame, text="➕ Добавить пользователя",
                        font=ctk.CTkFont(size=18, weight="bold"), text_color="#6d92ff").pack(pady=(0, 12))

            ctk.CTkLabel(frame, text="ID пользователя (его дал тебе друг):",
                        font=ctk.CTkFont(size=12, weight="bold"), anchor="w").pack(fill="x")
            id_entry = ctk.CTkEntry(frame, placeholder_text="482KLM", height=35)
            id_entry.pack(fill="x", pady=(4, 12))

            ctk.CTkLabel(frame, text="Как подписать этот чат:",
                        font=ctk.CTkFont(size=12, weight="bold"), anchor="w").pack(fill="x")
            name_entry = ctk.CTkEntry(frame, placeholder_text="например, Егор", height=35)
            name_entry.pack(fill="x", pady=(4, 12))
            name_entry.focus_set()

            def confirm_add():
                cid = id_entry.get().strip().upper()
                cname = name_entry.get().strip()

                if not cid:
                    play_error()
                    messagebox.showwarning("Ошибка", "Введи ID пользователя")
                    return
                if cid == my_user_id:
                    play_error()
                    messagebox.showwarning("Ошибка", "Это твой собственный ID")
                    return

                contacts = self.settings.setdefault("personal_chats", [])
                if any(c.get("id") == cid for c in contacts):
                    play_error()
                    messagebox.showwarning("Уже есть", "Этот пользователь уже добавлен в «Чаты»")
                    return
                if len(contacts) >= MAX_PERSONAL_CHATS:
                    play_error()
                    messagebox.showwarning(
                        "Лимит чатов",
                        f"Больше {MAX_PERSONAL_CHATS} личных чатов не влезет.\n"
                        f"Удали ненужный (🗑️ в списке «Чаты») — и добавишь нового."
                    )
                    return

                contacts.append({
                    "id": cid,
                    "name": cname or cid,
                    "last_message": "",
                    "last_message_time": "",
                    "last_message_ts": 0,
                    "last_message_mine": False,
                    "unread": False,
                })
                save_launcher_settings(self.settings)
                self.send_friend_request_to(cid, cname)
                play_click()
                add_dialog.destroy()
                refresh_chats_list()

            make_sound_button(frame, text="✅ Добавить", command=confirm_add,
                              fg_color="#6fce7f", hover_color="#5cb56c", text_color="#16141f",
                              height=40, font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", pady=(6, 0))


        if SHOW_PERSONAL_CHATS and self.settings.get("chat_setup_last_view") == "chats":
            switch_view("chats", user_action=False)

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

    def _dm_inbox_loop(self):
        """Держит одно постоянное соединение с релеем в персональной комнате
        dm-inbox-<мой_ID>, пока лаунчер запущен, и присылает в «Чаты» заявки
        в друзья (см. send_friend_request_to). Заявка попадает в список только
        после явного подтверждения пользователя."""
        delay = 3
        while self._dm_inbox_running:
            ws = None
            try:
                my_id = ensure_user_id(self.settings)
                room = f"dm-inbox-{my_id}"
                ws = ws_client.create_connection(RELAY_URL, timeout=15, sslopt=_ws_sslopt())
                ws.settimeout(1.0)
                ws.send(json.dumps({"room": room, "role": "inbox", "username": "inbox"}))
                delay = 3
                while self._dm_inbox_running:
                    try:
                        raw = ws.recv()
                    except ws_client.WebSocketTimeoutException:
                        continue
                    if not raw:
                        break
                    if isinstance(raw, bytes):
                        try:
                            raw = raw.decode("utf-8")
                        except UnicodeDecodeError:
                            continue
                    if not raw.startswith("{"):
                        continue
                    try:
                        data = json.loads(raw)
                    except Exception:
                        continue
                    if data.get("type") == "friend_request":
                        their_id = (data.get("user_id") or "").strip().upper()
                        suggested_name = (data.get("contact_name") or data.get("username") or "").strip()
                        if their_id and their_id != my_id:
                            self.after(0, lambda tid=their_id, name=suggested_name:
                                        self._handle_incoming_friend_request(tid, name))
            except Exception:
                pass
            finally:
                try:
                    if ws:
                        ws.close()
                except Exception:
                    pass
            if not self._dm_inbox_running:
                break
            time.sleep(delay)
            delay = min(delay * 2, 30)

    def _handle_incoming_friend_request(self, their_id, suggested_name):
        """Выполняется в главном потоке: спрашивает разрешение и только потом
        добавляет отправителя заявки в «Чаты» — раньше любой, кто прислал
        friend_request, появлялся в списке молча."""
        contacts = self.settings.setdefault("personal_chats", [])
        for c in contacts:
            if c.get("id") == their_id:
                return
        if len(contacts) >= MAX_PERSONAL_CHATS:
            return
        if self.safe_mode:
            messagebox.showinfo(
                "Safe mode",
                f"В Safe mode заявки в «Чаты» автоматически не принимаются.\n\n"
                f"Игрок «{suggested_name or their_id}» (ID: {their_id}) хочет добавить тебя."
            )
            return
        if not messagebox.askyesno(
            "Заявка в друзья",
            f"Игрок «{suggested_name or their_id}» (ID: {their_id}) добавляет тебя в «Чаты».\n\n"
            f"Принять?"
        ):
            self.log(f"🚫 Заявка от «{suggested_name or their_id}» отклонена")
            return
        contacts.append({
            "id": their_id,
            "name": suggested_name or their_id,
            "last_message": "",
            "last_message_time": "",
            "last_message_ts": 0,
            "last_message_mine": False,
            "unread": False,
        })
        save_launcher_settings(self.settings)
        self.log(f"➕ Заявка от «{suggested_name or their_id}» принята — чат появился в «Чаты»")
        if self.chats_list_refresh_callback:
            try:
                self.chats_list_refresh_callback()
            except Exception:
                pass

    def send_friend_request_to(self, their_id, contact_name):
        def _worker():
            ws = None
            try:
                my_id = ensure_user_id(self.settings)
                ws = ws_client.create_connection(RELAY_URL, timeout=10, sslopt=_ws_sslopt())
                ws.settimeout(5)
                ws.send(json.dumps({"room": f"dm-inbox-{their_id}", "role": "inbox-sender", "username": "system"}))
                ws.send(json.dumps({
                    "type": "friend_request",
                    "user_id": my_id,
                    "username": contact_name or my_id,
                    "contact_name": contact_name or my_id,
                }))
            except Exception as e:
                self.log(f"⚠️ Не удалось отправить заявку {their_id}: {e}")
            finally:
                try:
                    if ws:
                        ws.close()
                except Exception:
                    pass
        threading.Thread(target=_worker, daemon=True).start()

    def on_closing(self):
        self._dm_inbox_running = False
        self.withdraw()
        self.log(".")

if __name__ == "__main__":
    multiprocessing.freeze_support()
    try:
        _boot_root.destroy()
    except Exception:
        pass
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
