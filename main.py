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
import re
import traceback


# ===================================================================
# ПРОВЕРКА ЗАВИСИМОСТЕЙ
# ===================================================================

def check_dependencies():
    """Проверка установленных пакетов"""
    required = ['customtkinter', 'minecraft_launcher_lib', 'requests', 'PIL', 'certifi']
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"❌ Отсутствуют пакеты: {', '.join(missing)}")
        print("Установите их командой:")
        print(f"pip install {' '.join(missing)}")
        input("Нажмите Enter для выхода...")
        sys.exit(1)


check_dependencies()


# ===================================================================
# ФУНКЦИЯ ДЛЯ ПУТЕЙ В .EXE
# ===================================================================

def resource_path(relative_path):
    """Получить путь к ресурсам для .exe и .py"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# ===================================================================
# ДОБАВЛЕНИЕ ПРАВИЛА В БРАНДМАУЭР WINDOWS
# ===================================================================

def add_firewall_rule():
    """Добавление правила в брандмауэр Windows"""
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


# ===================================================================
# ВОСПРОИЗВЕДЕНИЕ ЗВУКОВ
# ===================================================================

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


def make_sound_button(master, text, command, **kwargs):
    def wrapped_command():
        play_click()
        if command:
            command()

    return ctk.CTkButton(master, text=text, command=wrapped_command, **kwargs)


# ===================================================================
# ОПРЕДЕЛЕНИЕ ПУТИ К ФАЙЛУ НАСТРОЕК
# ===================================================================

def get_settings_path():
    docs_path = os.path.join(os.path.expanduser("~"), "Documents", "67Launcher")
    try:
        os.makedirs(docs_path, exist_ok=True)
    except:
        pass
    settings_path = os.path.join(docs_path, "launcher_settings.json")
    return settings_path


# ===================================================================
# FIX SSL ДЛЯ WINDOWS
# ===================================================================

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

# ===================================================================
# НАСТРОЙКА ВНЕШНЕГО ВИДА
# ===================================================================

# ===================================================================
# КАСТОМНАЯ ТЕМА "67LAUNCHER" (по мотивам сайта — тёмно-фиолетовый фон,
# синий акцент #6d92ff/#3d6bf0, консоль в стиле сайта)
# ===================================================================

_THEME_67LAUNCHER = {
    "CTk": {"fg_color": ["#16141f", "#16141f"]},
    "CTkToplevel": {"fg_color": ["#16141f", "#16141f"]},
    "CTkFrame": {
        "corner_radius": 6, "border_width": 0,
        "fg_color": ["#1a1826", "#1a1826"],
        "top_fg_color": ["#1c1a29", "#1c1a29"],
        "border_color": ["#26243a", "#26243a"]
    },
    "CTkButton": {
        "corner_radius": 5, "border_width": 0,
        "fg_color": ["#3d6bf0", "#3d6bf0"],
        "hover_color": ["#3157c4", "#3157c4"],
        "border_color": ["#302c46", "#302c46"],
        "text_color": ["#ffffff", "#ffffff"],
        "text_color_disabled": ["#7a7791", "#7a7791"]
    },
    "CTkLabel": {
        "corner_radius": 0, "fg_color": "transparent",
        "text_color": ["#e5e2f0", "#e5e2f0"]
    },
    "CTkEntry": {
        "corner_radius": 5, "border_width": 1,
        "fg_color": ["#201d30", "#201d30"],
        "border_color": ["#302c46", "#302c46"],
        "text_color": ["#e5e2f0", "#e5e2f0"],
        "placeholder_text_color": ["#7a7791", "#7a7791"]
    },
    "CTkCheckBox": {
        "corner_radius": 4, "border_width": 2,
        "fg_color": ["#3d6bf0", "#3d6bf0"],
        "border_color": ["#4a4664", "#4a4664"],
        "hover_color": ["#3157c4", "#3157c4"],
        "checkmark_color": ["#ffffff", "#ffffff"],
        "text_color": ["#e5e2f0", "#e5e2f0"],
        "text_color_disabled": ["#7a7791", "#7a7791"]
    },
    "CTkSwitch": {
        "corner_radius": 1000, "border_width": 3, "button_length": 0,
        "fg_color": ["#302c46", "#302c46"],
        "progress_color": ["#3d6bf0", "#3d6bf0"],
        "button_color": ["#e5e2f0", "#e5e2f0"],
        "button_hover_color": ["#ffffff", "#ffffff"],
        "text_color": ["#e5e2f0", "#e5e2f0"],
        "text_color_disabled": ["#7a7791", "#7a7791"]
    },
    "CTkRadioButton": {
        "corner_radius": 1000, "border_width_checked": 4, "border_width_unchecked": 2,
        "fg_color": ["#6d92ff", "#6d92ff"],
        "border_color": ["#4a4664", "#4a4664"],
        "hover_color": ["#5a7dd8", "#5a7dd8"],
        "text_color": ["#cfcbe0", "#cfcbe0"],
        "text_color_disabled": ["#7a7791", "#7a7791"]
    },
    "CTkProgressBar": {
        "corner_radius": 3, "border_width": 0,
        "fg_color": ["#2b2840", "#2b2840"],
        "progress_color": ["#6d92ff", "#6d92ff"],
        "border_color": ["#26243a", "#26243a"]
    },
    "CTkSlider": {
        "corner_radius": 1000, "button_corner_radius": 1000, "border_width": 6,
        "fg_color": ["#2b2840", "#2b2840"],
        "progress_color": ["#302c46", "#302c46"],
        "button_color": ["#3d6bf0", "#3d6bf0"],
        "button_hover_color": ["#3157c4", "#3157c4"]
    },
    "CTkOptionMenu": {
        "corner_radius": 5,
        "fg_color": ["#201d30", "#201d30"],
        "button_color": ["#302c46", "#302c46"],
        "button_hover_color": ["#3d6bf0", "#3d6bf0"],
        "text_color": ["#e5e2f0", "#e5e2f0"],
        "text_color_disabled": ["#7a7791", "#7a7791"]
    },
    "CTkComboBox": {
        "corner_radius": 5, "border_width": 1,
        "fg_color": ["#201d30", "#201d30"],
        "border_color": ["#302c46", "#302c46"],
        "button_color": ["#302c46", "#302c46"],
        "button_hover_color": ["#3d6bf0", "#3d6bf0"],
        "text_color": ["#e5e2f0", "#e5e2f0"],
        "text_color_disabled": ["#7a7791", "#7a7791"]
    },
    "CTkScrollbar": {
        "corner_radius": 1000, "border_spacing": 4, "fg_color": "transparent",
        "button_color": ["#302c46", "#302c46"],
        "button_hover_color": ["#3d6bf0", "#3d6bf0"]
    },
    "CTkSegmentedButton": {
        "corner_radius": 5, "border_width": 2,
        "fg_color": ["#201d30", "#201d30"],
        "selected_color": ["#3d6bf0", "#3d6bf0"],
        "selected_hover_color": ["#3157c4", "#3157c4"],
        "unselected_color": ["#201d30", "#201d30"],
        "unselected_hover_color": ["#2b2840", "#2b2840"],
        "text_color": ["#e5e2f0", "#e5e2f0"],
        "text_color_disabled": ["#7a7791", "#7a7791"]
    },
    "CTkTextbox": {
        "corner_radius": 5, "border_width": 0,
        "fg_color": ["#100e1a", "#100e1a"],
        "border_color": ["#26243a", "#26243a"],
        "text_color": ["#8f8ba6", "#8f8ba6"],
        "scrollbar_button_color": ["#302c46", "#302c46"],
        "scrollbar_button_hover_color": ["#3d6bf0", "#3d6bf0"]
    },
    "CTkScrollableFrame": {"label_fg_color": ["#1a1826", "#1a1826"]},
    "CTkTabview": {
        "corner_radius": 6, "border_width": 0,
        "fg_color": ["#1a1826", "#1a1826"],
        "segmented_button_fg_color": ["#1a1826", "#1a1826"],
        "segmented_button_selected_color": ["#1c1a29", "#1c1a29"],
        "segmented_button_selected_hover_color": ["#1c1a29", "#1c1a29"],
        "segmented_button_unselected_color": ["#1a1826", "#1a1826"],
        "segmented_button_unselected_hover_color": ["#201d30", "#201d30"],
        "text_color": ["#a8a4bd", "#a8a4bd"],
        "text_color_disabled": ["#4a4664", "#4a4664"]
    },
    "DropdownMenu": {
        "fg_color": ["#201d30", "#201d30"],
        "hover_color": ["#2b2840", "#2b2840"],
        "text_color": ["#e5e2f0", "#e5e2f0"]
    },
    "CTkFont": {
        "macOS": {"family": "SF Display", "size": -13, "weight": "normal"},
        "Windows": {"family": "Segoe UI", "size": -13, "weight": "normal"},
        "Linux": {"family": "Roboto", "size": -13, "weight": "normal"}
    }
}


def _load_67launcher_theme():
    """Строим тему ПОВЕРХ встроенной темы customtkinter (файл blue.json,
    который ставится вместе с библиотекой), подмешивая туда цвета сайта.

    Раньше тема писалась вручную с нуля — это оказалось хрупко: разные
    версии customtkinter требуют разный набор обязательных ключей для
    каждого виджета (например 'text_color_disabled' у CTkSwitch/CTkCheckBox),
    и пропуск любого ключа приводит к KeyError при старте. Начиная с
    официальной темы библиотеки, мы гарантированно получаем все нужные
    ключи для установленной у пользователя версии, а сверху просто
    заменяем цвета на наши."""
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

# ===================================================================
# 1. НАСТРОЙКИ И ПЕРЕМЕННЫЕ
# ===================================================================

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


# ===================================================================
# 2. РАБОТА С НАСТРОЙКАМИ
# ===================================================================

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
        "secret_clicks": 0,
        "show_game_logs": False
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


# ===================================================================
# 3. СТАТИСТИКА
# ===================================================================

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
    # update_stats() вызывается из фонового потока запуска игры (do_launch),
    # поэтому UI-обновления обязательно перекидываем в главный поток.
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


# ===================================================================
# 4. РАБОТА С ПАПКОЙ ИГРЫ
# ===================================================================

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


# ===================================================================
# 5. РАБОТА С АККАУНТАМИ
# ===================================================================

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


# ===================================================================
# 6. РАБОТА С ПРОФИЛЯМИ И ВЕРСИЯМИ
# ===================================================================

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


# ===================================================================
# 7. УСТАНОВКА JAVA
# ===================================================================

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


# ===================================================================
# 8. РАБОТА С МОДАМИ
# ===================================================================

def get_mods_folder():
    mods_path = os.path.join(MINECRAFT_DIR, "mods")
    os.makedirs(mods_path, exist_ok=True)
    return mods_path


_icon_cache = {}


def load_image_from_url(url, size=(48, 48)):
    """Скачивает картинку по URL и возвращает CTkImage. Кэширует результат."""
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


def delete_mod(mod_name):
    filepath = os.path.join(get_mods_folder(), mod_name)
    if os.path.exists(filepath):
        os.remove(filepath)
        return True
    return False


# ===================================================================
# 9. РАБОТА СО СКИНАМИ
# ===================================================================

def get_skins_folder():
    skins_path = os.path.join(MINECRAFT_DIR, "skins")
    os.makedirs(skins_path, exist_ok=True)
    return skins_path


# ===================================================================
# 10. КОЛБЭК ДЛЯ MLL
# ===================================================================

def mll_set_status(text):
    log_message(f"📌 {text}")


def mll_set_progress(current, total):
    if total > 0:
        percent = int((current / total) * 100)
        log_message(f"📊 Прогресс: {percent}%")


mll_callback = {
    "setStatus": mll_set_status,
    "setProgress": lambda v: None,
    "setMax": lambda v: None,
    "setProgressMax": mll_set_progress
}


# ===================================================================
# 11. КЛАСС ДЛЯ АНИМИРОВАННОГО ПРОГРЕСС-БАРА
# ===================================================================

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


# ===================================================================
# 12. КЛАСС ДЛЯ АНИМИРОВАННОГО СПИННЕРА
# ===================================================================

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


# ===================================================================
# КЛАСС ВИДЕО ПЛЕЕРА (МАКСИМАЛЬНО ПРОСТОЙ)
# ===================================================================

class VideoPlayer(ctk.CTkToplevel):
    def __init__(self, master, video_path, title="🎁 Подарок", sound_type="good"):
        super().__init__(master)
        self.master = master
        self.title(title)
        self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")
        self.attributes('-fullscreen', True)
        self.attributes('-topmost', True)
        self.grab_set()

        self.video_path = video_path
        self.sound_type = sound_type
        self.cap = None
        self.frame_delay = 33
        self.fps = 30
        self.playback_start = None
        self.frame_index = 0
        self.audio_player = None

        # Canvas для видео
        self.canvas = tk.Canvas(self, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        # ТОЛЬКО КНОПКА ЗАКРЫТЬ
        close_btn = ctk.CTkButton(
            self,
            text="✕ ЗАКРЫТЬ",
            command=self.close_player,
            fg_color="#d3453f",
            hover_color="#b83530",
            font=ctk.CTkFont(size=18, weight="bold"),
            width=200,
            height=50
        )
        close_btn.place(relx=0.5, rely=0.92, anchor="center")

        self.bind("<Escape>", lambda e: self.close_player())
        self.after(100, self.init_video)

    def init_video(self):
        try:
            import cv2
            from PIL import Image, ImageTk

            if not os.path.exists(self.video_path):
                return

            self.cap = cv2.VideoCapture(self.video_path)
            if not self.cap.isOpened():
                return

            fps = self.cap.get(cv2.CAP_PROP_FPS)
            self.fps = fps if fps > 0 else 30
            self.frame_delay = int(1000 / self.fps)

            # Запускаем звук
            self.play_mp3()

            # Запускаем видео
            self.update_frame()

        except:
            pass

    def play_mp3(self):
        def play():
            try:
                import pyglet

                mp3_file = "good.mp3" if self.sound_type == "good" else "bad.mp3"

                # Ищем файл
                sound_path = None
                for path in [mp3_file, os.path.join(os.getcwd(), mp3_file), os.path.join("resources", mp3_file)]:
                    if os.path.exists(path):
                        sound_path = path
                        break

                if sound_path:
                    self.audio_player = pyglet.media.Player()
                    source = pyglet.media.load(sound_path)
                    self.audio_player.queue(source)
                    self.audio_player.play()
            except:
                pass

        threading.Thread(target=play, daemon=True).start()

    def update_frame(self):
        try:
            import cv2
            from PIL import Image, ImageTk

            if self.cap is None or not self.cap.isOpened():
                self.after(100, self.update_frame)
                return

            if self.playback_start is None:
                self.playback_start = time.time()

            ret, frame = self.cap.read()
            if not ret:
                # Видео закончилось
                if self.sound_type == "bad":
                    self.after(1000, self.close_launcher)
                return

            self.frame_index += 1

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)

            w = self.canvas.winfo_width()
            h = self.canvas.winfo_height()

            if w > 1 and h > 1:
                ratio = img.width / img.height
                if ratio > w / h:
                    new_w = w
                    new_h = int(w / ratio)
                else:
                    new_h = h
                    new_w = int(h * ratio)
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                x = (w - new_w) // 2
                y = (h - new_h) // 2
            else:
                x = 0
                y = 0

            photo = ImageTk.PhotoImage(img)
            self.canvas.delete("all")
            self.canvas.create_image(x, y, image=photo, anchor="nw")
            self.canvas.image = photo

            # Синхронизация по реальному времени: считаем, сколько времени
            # ДОЛЖНО было пройти к этому кадру, и сколько прошло на самом деле.
            # Это не даёт видео накапливать отставание от звука из-за времени
            # на декодирование/ресайз каждого кадра.
            expected_elapsed = self.frame_index / self.fps
            actual_elapsed = time.time() - self.playback_start
            delay_seconds = expected_elapsed - actual_elapsed
            delay_ms = max(1, int(delay_seconds * 1000))

            self.after(delay_ms, self.update_frame)

        except:
            self.after(50, self.update_frame)

    def close_launcher(self):
        """Закрыть лаунчер"""
        try:
            self.destroy()
            if self.master:
                self.master.quit()
                self.master.destroy()
            sys.exit(0)
        except:
            sys.exit(0)

    def close_player(self):
        """Закрыть плеер"""
        try:
            if self.audio_player:
                try:
                    self.audio_player.pause()
                except:
                    pass
            if self.cap:
                self.cap.release()
            self.destroy()
        except:
            self.destroy()


# ===================================================================
# 14. СЕКРЕТНЫЙ ЛАУНЧЕР GEOMETRY DASH
# ===================================================================

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

        update_btn = ctk.CTkButton(main_frame, text="🔄 Обновить статус",
                                   command=self.check_installation,
                                   width=200, height=35,
                                   fg_color="#d9622f", hover_color="#c14f26",
                                   text_color="#16141f",
                                   font=ctk.CTkFont(size=13, weight="bold"))
        update_btn.pack(pady=(10, 5))

        close_btn = make_sound_button(main_frame, text="❌ Закрыть",
                                      command=self.destroy,
                                      width=120, height=35,
                                      fg_color="#d3453f", hover_color="#b83530",
                                      font=ctk.CTkFont(size=13))
        close_btn.pack(pady=(5, 0))

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
                    size = os.path.getsize(self.exe_path)
                    size_text = self.format_size(size)
                    self.status_label.configure(text=f"✅ Geometry Dash установлен! ({size_text})", text_color="#6fce7f")
                except:
                    pass
                messagebox.showinfo("Статус", "✅ Geometry Dash установлен и готов к запуску!")
            else:
                self.status_label.configure(text="❌ Geometry Dash не установлен", text_color="#d3453f")
                self.launch_btn.configure(state="disabled")
                self.install_btn.configure(text="📥 Установить GD")
                self.progressbar.set(0)
                self.percent_label.configure(text="0%", text_color="#d9622f")
                messagebox.showinfo("Статус", "❌ Geometry Dash не установлен.\nНажмите 'Установить GD'.")
        except Exception as e:
            self.status_label.configure(text=f"❌ Ошибка: {e}", text_color="#d3453f")
            play_error()

    def format_size(self, size):
        for unit in ['Б', 'КБ', 'МБ', 'ГБ']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} ТБ"

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
                self.update_idletasks()
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
                messagebox.showerror("Ошибка", "GeometryDash.exe не найден!\n\nПроверьте папку:\n" + self.gd_path)
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
            self.after(2000, self.destroy)
        except Exception as e:
            self.status_label.configure(text="❌ Ошибка запуска", text_color="#d3453f")
            self.launch_btn.configure(state="normal")
            play_error()
            messagebox.showerror("Ошибка", f"Не удалось запустить:\n{e}")


# ===================================================================
# 15. КЛАСС ЧАТА
# ===================================================================

class ChatWindow(ctk.CTkToplevel):
    def __init__(self, master, mode="server", host="127.0.0.1", port=25565):
        super().__init__(master)
        self.master = master
        self.mode = mode
        self.host = host
        self.port = port
        self.running = True
        self.connected = False
        self.server_socket = None
        self.client_socket = None
        self.username = "Игрок"
        self.message_history = []
        self.is_minimized = False
        self.unread_count = 0

        try:
            self.local_ip = socket.gethostbyname(socket.gethostname())
        except:
            self.local_ip = "Не определен"
        # Раньше get_external_ip() (сетевой запрос до 5 сек) и add_firewall_rule()
        # (subprocess.run 'netsh', может ждать UAC) вызывались прямо здесь, на
        # главном потоке — при открытии окна чата в режиме сервера это
        # замораживало весь интерфейс на несколько секунд. Теперь оба выполняются
        # в фоне после создания окна, а виджеты обновляются по готовности.
        self.external_ip = None

        self.title("💬 Чат 67Launcher")
        self.geometry("800x850")
        self.minsize(650, 600)
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
        self.log(f"🔍 Инициализация чата в режиме: {mode}")
        self.log(f"🖥️ Локальный IP: {self.local_ip}")

        # run_diagnostics() делает DNS-запрос к google.com и вызывает netsh —
        # оба могут занять заметное время, поэтому тоже уходят в фон
        threading.Thread(target=self.run_diagnostics, daemon=True).start()

        # Настройка брандмауэра (только для сервера) и получение внешнего IP —
        # оба потенциально медленные/блокирующие, поэтому выполняются в фоне
        threading.Thread(target=self._background_setup, daemon=True).start()

        if mode == "server":
            threading.Thread(target=self.run_server, daemon=True).start()
        else:
            threading.Thread(target=self.run_client, daemon=True).start()

    def _background_setup(self):
        """Настройка брандмауэра и получение внешнего IP — выполняется в
        фоновом потоке, чтобы не морозить окно чата при открытии."""
        if self.mode == "server":
            try:
                add_firewall_rule()
            except:
                pass
        ip = self.get_external_ip()
        self.external_ip = ip
        if ip:
            self.log(f"🌍 Внешний IP: {ip}")
        if self.mode == "server" and hasattr(self, 'ip_info_label'):
            def _update_label():
                try:
                    if self.ip_info_label.winfo_exists():
                        text = f"🌐 Локальный: {self.local_ip}:{self.port}"
                        text += f"  |  🌍 Внешний: {ip}:{self.port}" if ip else "  |  🌍 Внешний: недоступен"
                        self.ip_info_label.configure(text=text)
                except:
                    pass
            self.after(0, _update_label)

    def get_external_ip(self):
        try:
            response = requests.get('https://api.ipify.org', timeout=5)
            if response.status_code == 200:
                return response.text
        except:
            pass
        return None

    def run_diagnostics(self):
        self.log("━" * 50)
        self.log("🔧 ДИАГНОСТИКА СЕТИ:")
        try:
            socket.gethostbyname('google.com')
            self.log("✅ Интернет соединение: Есть")
        except:
            self.log("❌ Интернет соединение: Нет")
        if sys.platform == "win32":
            try:
                result = subprocess.run('netsh advfirewall show allprofiles state',
                                        capture_output=True, text=True, shell=True, encoding='cp866')
                if "ON" in result.stdout.upper():
                    self.log("🛡️ Брандмауэр: Включен")
                    self.log("💡 Если подключение не работает, добавьте исключение в брандмауэр")
                else:
                    self.log("🛡️ Брандмауэр: Выключен")
            except:
                self.log("🛡️ Брандмауэр: Неизвестно")
        if self.mode == "server":
            # Раньше здесь был дополнительный тестовый bind()/close() порта.
            # Теперь run_diagnostics() выполняется в отдельном потоке параллельно
            # с run_server(), и этот тест мог конфликтовать по времени с реальным
            # bind() сервера, выдавая ложное "порт уже используется". run_server()
            # и так честно сообщает об ошибке bind в своём except — тест здесь избыточен.
            self.log(f"🔌 Сервер будет слушать порт {self.port}...")
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
        if not self.is_minimized:
            return
        self.unread_count += 1
        self.update_title()
        try:
            notif = ctk.CTkToplevel(self)
            notif.title("")
            notif.geometry("380x120")
            notif.overrideredirect(True)
            notif.attributes('-topmost', True)
            screen_width = notif.winfo_screenwidth()
            screen_height = notif.winfo_screenheight()
            x = screen_width - 400
            y = screen_height - 160
            notif.geometry(f"380x120+{x}+{y}")
            frame = ctk.CTkFrame(notif, fg_color="#100e1a", corner_radius=10)
            frame.pack(fill="both", expand=True, padx=2, pady=2)
            header_frame = ctk.CTkFrame(frame, fg_color="transparent")
            header_frame.pack(fill="x", padx=15, pady=(10, 5))
            title_text = f"💬 {sender}" if sender else "💬 Новое сообщение"
            ctk.CTkLabel(header_frame, text=title_text,
                         font=ctk.CTkFont(size=14, weight="bold"),
                         text_color="#6d92ff").pack(side="left")
            close_btn = ctk.CTkButton(header_frame, text="✕",
                                      command=notif.destroy,
                                      width=25, height=25,
                                      fg_color="transparent",
                                      hover_color="#d3453f",
                                      text_color="#e5e2f0")
            close_btn.pack(side="right")
            msg_text = message[:80] + "..." if len(message) > 80 else message
            ctk.CTkLabel(frame, text=msg_text,
                         font=ctk.CTkFont(size=13),
                         text_color="#e5e2f0",
                         wraplength=350,
                         justify="left").pack(padx=15, pady=(5, 10))
            notif.after(5000, notif.destroy)
            notif.attributes('-alpha', 0.0)

            def fade_in(alpha=0.0):
                if alpha <= 1.0:
                    notif.attributes('-alpha', alpha)
                    notif.after(50, lambda: fade_in(alpha + 0.1))

            fade_in()
        except Exception as e:
            print(f"Ошибка уведомления: {e}")

    def copy_ip_to_clipboard(self, ip):
        try:
            self.clipboard_clear()
            self.clipboard_append(ip)
            play_click()
            messagebox.showinfo("Скопировано", f"IP-адрес скопирован в буфер обмена:\n{ip}")
        except:
            play_error()
            messagebox.showerror("Ошибка", "Не удалось скопировать IP")

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

        mode_text = "🖥️ Сервер" if self.mode == "server" else "💻 Клиент"
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

        info_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        info_frame.pack(fill="x", pady=(0, 10))

        if self.mode == "server":
            self.connection_info_label = ctk.CTkLabel(info_frame, text=f"🔗 Сервер запущен на порту: {self.port}",
                                                      font=ctk.CTkFont(size=13), text_color="#6d92ff")
            self.connection_info_label.pack(side="left")
            self.connection_status_label = ctk.CTkLabel(info_frame, text=f"👤 Ожидание подключения...",
                                                        font=ctk.CTkFont(size=13), text_color="#d9622f")
            self.connection_status_label.pack(side="right")
        else:
            ctk.CTkLabel(info_frame, text=f"🌐 Подключение к: {self.host}:{self.port}",
                         font=ctk.CTkFont(size=13), text_color="#6d92ff").pack(side="left")
            ctk.CTkLabel(info_frame, text=f"👤 {self.username}",
                         font=ctk.CTkFont(size=13), text_color="#6fce7f").pack(side="right")

        ip_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        ip_frame.pack(fill="x", pady=(5, 10))

        if self.mode == "server":
            ip_text = f"🌐 Локальный: {self.local_ip}:{self.port}"
            if self.external_ip:
                ip_text += f"  |  🌍 Внешний: {self.external_ip}:{self.port}"
            else:
                ip_text += "  |  🌍 Внешний: определяется..."
            self.ip_info_label = ctk.CTkLabel(ip_frame, text=ip_text,
                         font=ctk.CTkFont(size=12), text_color="#d9622f")
            self.ip_info_label.pack(side="left")
            copy_btn = make_sound_button(ip_frame, text="📋 Копировать IP",
                                         command=lambda: self.copy_ip_to_clipboard(self.external_ip or self.local_ip),
                                         width=130, height=30,
                                         fg_color="#6d92ff", hover_color="#5a7dd8",
                                         font=ctk.CTkFont(size=11))
            copy_btn.pack(side="right")
        else:
            ctk.CTkLabel(ip_frame, text=f"🌐 Подключен к: {self.host}:{self.port}",
                         font=ctk.CTkFont(size=12), text_color="#d9622f").pack(side="left")

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

        self.message_entry = ctk.CTkEntry(input_frame, placeholder_text="Введите сообщение...",
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
            messagebox.showinfo("Информация", "Нет сообщений для экспорта")
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
            messagebox.showinfo("Успешно", f"Чат сохранен в файл:\n{file_path}")
        except Exception as e:
            play_error()
            messagebox.showerror("Ошибка", f"Не удалось сохранить чат:\n{e}")

    def update_msg_count(self):
        count = len(self.message_history)
        if count > 0:
            self.msg_count_label.configure(text=f"📨 {count}")
        else:
            self.msg_count_label.configure(text="")

    def log(self, message):
        # Этот метод вызывается из фоновых потоков (run_server, run_client,
        # receive_messages_thread), а Tkinter нельзя трогать из фонового потока —
        # это была одна из причин зависаний/крашей окна чата. Перекидываем
        # выполнение в главный поток через self.after.
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
            self.chat_display.insert("end", f"[{timestamp}] {message}\n")
            self.chat_display.see("end")
            self.chat_display.configure(state="disabled")
        except:
            pass

    def test_connection_advanced(self):
        """Диагностика перед подключением.

        ВАЖНО: раньше здесь делался пробный TCP-коннект (connect_ex) к серверу
        перед основным подключением. Это была причина бага 'сразу теряет
        соединение': сервер вызывает accept() только один раз, и он принимал
        именно этот пробный коннект (который сразу закрывался), а не реальный.
        В итоге сервер оставался 'подключён' к уже закрытому сокету, и чат
        переставал работать. Теперь здесь только проверка DNS, без открытия
        реального соединения — это не мешает серверному accept()."""
        self.log("🔍 ДИАГНОСТИКА ПОДКЛЮЧЕНИЯ:")
        self.log(f"   Хост: {self.host}")
        self.log(f"   Порт: {self.port}")
        try:
            ip = socket.gethostbyname(self.host)
            self.log(f"   ✅ IP разрешен: {ip}")
            return True
        except:
            self.log("   ❌ Не удалось разрешить хост")
            return False

    def safe_update_widget(self, widget, **kwargs):
        # Тоже вызывается из фоновых потоков сокетов — перекидываем в главный поток
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

    def run_server(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('0.0.0.0', self.port))
            self.server_socket.listen(5)
            self.server_socket.settimeout(None)
            self.log(f"🟢 Сервер запущен на порту {self.port}")
            self.log(f"🌐 Подключайтесь по адресу: {self.local_ip}:{self.port}")
            self.log("━" * 50)
            self.log("⏳ Ожидание подключения...")
            self.client_socket, address = self.server_socket.accept()
            self.client_socket.settimeout(None)
            self.connected = True
            self.safe_update_widget(self.status_label, text="🟢 Онлайн", text_color="#6fce7f")
            self.safe_update_widget(self.send_btn, state="normal")
            if hasattr(self, 'connection_status_label'):
                self.safe_update_widget(
                    self.connection_status_label,
                    text=f"👤 Подключен: {address[0]}:{address[1]}",
                    text_color="#6fce7f"
                )
            self.log(f"✅ Подключено! {address[0]}:{address[1]}")
            self.after(100, lambda: self.send_message_raw("👤 Сервер приветствует вас!"))
            threading.Thread(target=self.receive_messages_thread, daemon=True).start()
        except Exception as e:
            self.log(f"❌ Ошибка сервера: {e}")
            self.disconnect()

    def run_client(self):
        """Запуск клиента с исправленной логикой"""
        if not self.test_connection_advanced():
            self.log("💡 ПРОВЕРЬТЕ:")
            self.log("  1. Сервер запущен?")
            self.log("  2. Правильный IP?")
            self.log("  3. Если на одном ПК - используйте 127.0.0.1")
            self.log("  4. Брандмауэр не блокирует?")
            return
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.settimeout(10)
            self.client_socket.connect((self.host, self.port))
            self.client_socket.settimeout(None)
            self.connected = True
            self.safe_update_widget(self.status_label, text="🟢 Онлайн", text_color="#6fce7f")
            self.safe_update_widget(self.send_btn, state="normal")
            self.log(f"✅ Подключено к серверу {self.host}:{self.port}")
            try:
                self.client_socket.send(f"👤 {self.username} присоединился к чату!".encode('utf-8'))
            except:
                pass
            threading.Thread(target=self.receive_messages_thread, daemon=True).start()
        except ConnectionRefusedError:
            self.log("❌ Ошибка: соединение отклонено")
            self.log("💡 Убедитесь что сервер запущен")
            self.connected = False
        except socket.timeout:
            self.log("❌ Таймаут подключения")
            self.log("💡 Проверьте сетевое соединение")
            self.connected = False
        except Exception as e:
            self.log(f"❌ Ошибка подключения: {e}")
            self.connected = False

    def reconnect(self):
        if self.mode != "client":
            return
        if self.connected:
            self.disconnect()
        self.log("🔄 Попытка переподключения...")
        # run_client() блокирующий (до 10 сек ожидания соединения) — раньше вызывался
        # прямо из клика по кнопке и замораживал окно чата на это время.
        threading.Thread(target=self.run_client, daemon=True).start()

    def receive_messages_thread(self):
        """Поток для приема сообщений"""
        while self.running and self.connected:
            try:
                if self.client_socket is None:
                    break
                self.client_socket.settimeout(0.5)
                try:
                    data = self.client_socket.recv(4096)
                    if not data:
                        self.log("⚠️ Соединение закрыто сервером")
                        self.after(0, self.disconnect)
                        break
                    try:
                        message = data.decode('utf-8')
                        self.display_message(message)
                    except UnicodeDecodeError:
                        continue
                except socket.timeout:
                    continue
                except socket.error as e:
                    if self.running:
                        error_str = str(e)
                        if "10053" in error_str or "10054" in error_str:
                            self.log("⚠️ Соединение разорвано")
                            self.after(0, self.disconnect)
                        else:
                            self.log(f"❌ Ошибка приема: {error_str}")
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
                self.client_socket.send(message.encode('utf-8'))
                if not message.startswith("👤"):
                    self.message_history.append(message)
                    self.update_msg_count()
                    self.log(f"📤 {message}")
        except Exception as e:
            self.log(f"❌ Ошибка отправки: {e}")
            self.disconnect()

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
                if self.server_socket:
                    self.server_socket.close()
                    self.server_socket = None
            except:
                pass

    def on_close(self):
        self.running = False
        self.disconnect()
        self.destroy()
        play_click()


# ===================================================================
# 16. КЛАСС EMOJI PICKER
# ===================================================================

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
            btn = ctk.CTkButton(scroll_frame, text=emoji, width=50, height=50,
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


# ===================================================================
# 16.5 ОКНО КОНСОЛИ ИГРЫ
# ===================================================================

class GameConsoleWindow(ctk.CTkToplevel):
    """Отдельное окно с логами запущенной игры.

    Раньше игра запускалась с creationflags=CREATE_NEW_CONSOLE — это открывало
    нативное окно консоли Windows для java-процесса. Проблема в том, что Java
    в таком режиме часть вывода пишет напрямую в хендл этой консоли, в обход
    перенаправленных stdout/stderr pipe — из-за этого консоль лаунчера почти
    ничего не получала и оставалась пустой.

    Теперь отдельная нативная консоль не создаётся вообще. Вместо неё — это
    окно, которое получает те же самые строки из того же pipe, что и основная
    консоль лаунчера, поэтому логи гарантированно совпадают в обоих местах."""

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


# ===================================================================
# 17. ФУНКЦИЯ ПАСХАЛКИ С ПОДАРКОМ
# ===================================================================

def show_gift_dialog(master):
    """Показать диалог с подарком"""
    dialog = ctk.CTkToplevel(master)
    dialog.title("🎁 Секретный подарок!")
    dialog.geometry("500x450")
    dialog.resizable(False, False)
    dialog.grab_set()
    dialog.transient(master)

    # Центрируем окно
    dialog.update_idletasks()
    width = dialog.winfo_width()
    height = dialog.winfo_height()
    x = (dialog.winfo_screenwidth() // 2) - (width // 2)
    y = (dialog.winfo_screenheight() // 2) - (height // 2)
    dialog.geometry(f"{width}x{height}+{x}+{y}")

    main_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    main_frame.pack(fill="both", expand=True, padx=30, pady=30)

    # Заголовок
    ctk.CTkLabel(
        main_frame,
        text="🎁 СЮРПРИЗ!",
        font=ctk.CTkFont(size=32, weight="bold"),
        text_color="#d9622f"
    ).pack(pady=(0, 10))

    ctk.CTkLabel(
        main_frame,
        text="Выберите свой подарок:",
        font=ctk.CTkFont(size=18),
        text_color="#e5e2f0"
    ).pack(pady=(0, 20))

    # Контейнер для кнопок
    btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
    btn_frame.pack(pady=10)

    # Пути к видео
    exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    good_video = os.path.join(exe_dir, "good.mp4")
    bad_video = os.path.join(exe_dir, "bad.mp4")

    # Если файлов нет - используем заглушку
    if not os.path.exists(good_video):
        good_video = None
    if not os.path.exists(bad_video):
        bad_video = None

    def choose_good():
        dialog.destroy()
        play_click()
        master.log("🎁 Открыт хороший подарок!")

        if good_video and os.path.exists(good_video):
            VideoPlayer(master, good_video, "🎁 Хороший подарок!")
        else:
            # Показываем сообщение, если видео нет
            msg = ctk.CTkToplevel(master)
            msg.title("🎉 Поздравляем!")
            msg.geometry("500x300")
            msg.grab_set()

            frame = ctk.CTkFrame(msg, fg_color="transparent")
            frame.pack(fill="both", expand=True, padx=20, pady=20)

            ctk.CTkLabel(frame, text="🎉", font=ctk.CTkFont(size=80)).pack(pady=10)
            ctk.CTkLabel(frame, text="ХОРОШИЙ ПОДАРОК!",
                         font=ctk.CTkFont(size=24, weight="bold"),
                         text_color="#6fce7f").pack(pady=10)
            ctk.CTkLabel(frame, text="Спасибо, что поддерживаете автора! ❤️",
                         font=ctk.CTkFont(size=16)).pack(pady=10)
            ctk.CTkButton(frame, text="Закрыть", command=msg.destroy,
                          fg_color="#6d92ff", hover_color="#5a7dd8",
                          width=150, height=40).pack(pady=20)

            msg.after(5000, msg.destroy)

        # Показываем сообщение
        master.after(1000, lambda: messagebox.showinfo(
            "🎉 Поздравляем!",
            "Вы получили ХОРОШИЙ подарок!\n\n"
            "✨ Спасибо, что поддерживаете разработчика!\n"
            "❤️ Ваша поддержка очень важна!"
        ))

    def choose_bad():
        dialog.destroy()
        play_error()
        master.log("💀 Открыт плохой подарок!")

        if bad_video and os.path.exists(bad_video):
            VideoPlayer(master, bad_video, "💀 Плохой подарок!")
        else:
            # Показываем сообщение, если видео нет
            msg = ctk.CTkToplevel(master)
            msg.title("💀 Ой-ой!")
            msg.geometry("500x300")
            msg.grab_set()

            frame = ctk.CTkFrame(msg, fg_color="transparent")
            frame.pack(fill="both", expand=True, padx=20, pady=20)

            ctk.CTkLabel(frame, text="💀", font=ctk.CTkFont(size=80)).pack(pady=10)
            ctk.CTkLabel(frame, text="ПЛОХОЙ ПОДАРОК!",
                         font=ctk.CTkFont(size=24, weight="bold"),
                         text_color="#d3453f").pack(pady=10)
            ctk.CTkLabel(frame, text="Ничего личного, но вы упустили шанс! 😈",
                         font=ctk.CTkFont(size=16)).pack(pady=10)
            ctk.CTkButton(frame, text="Закрыть", command=msg.destroy,
                          fg_color="#d3453f", hover_color="#b83530",
                          width=150, height=40).pack(pady=20)

            msg.after(5000, msg.destroy)

        # Показываем сообщение
        master.after(1000, lambda: messagebox.showwarning(
            "😈 Ой-ой!",
            "Вы получили ПЛОХОЙ подарок!\n\n"
            "💀 Ничего личного, но вы упустили шанс!\n"
            "😊 В следующий раз поддержите автора!"
        ))

    # Кнопка "Хороший подарок"
    good_btn = ctk.CTkButton(
        btn_frame,
        text="🎁 Получить хороший подарок",
        command=choose_good,
        fg_color="#6fce7f",
        hover_color="#5cb56c",
        text_color="#16141f",
        font=ctk.CTkFont(size=16, weight="bold"),
        height=60,
        width=350
    )
    good_btn.pack(pady=10)

    # Описание
    ctk.CTkLabel(
        btn_frame,
        text="💖 Поддержать автора",
        font=ctk.CTkFont(size=13),
        text_color="#6fce7f"
    ).pack(pady=(0, 15))

    # Кнопка "Плохой подарок"
    bad_btn = ctk.CTkButton(
        btn_frame,
        text="💀 Получить плохой подарок",
        command=choose_bad,
        fg_color="#d3453f",
        hover_color="#b83530",
        text_color="#16141f",
        font=ctk.CTkFont(size=16, weight="bold"),
        height=60,
        width=350
    )
    bad_btn.pack(pady=10)

    # Описание
    ctk.CTkLabel(
        btn_frame,
        text="👎 Не поддержать автора",
        font=ctk.CTkFont(size=13),
        text_color="#d3453f"
    ).pack(pady=(0, 5))

    # Информация
    ctk.CTkLabel(
        main_frame,
        text="Выбор нельзя будет изменить после открытия",
        font=ctk.CTkFont(size=12),
        text_color="#6d92ff",
        justify="center"
    ).pack(pady=(20, 0))


# ===================================================================
# 18. ОСНОВНОЙ КЛАСС ПРИЛОЖЕНИЯ
# ===================================================================

class LauncherApp(ctk.CTk):
    instance = None

    def __init__(self):
        global MINECRAFT_DIR, GAME_DIR, ACCOUNTS_FILE, PROFILES_FILE, LAUNCHER_PROFILES_FILE

        super().__init__()
        LauncherApp.instance = self

        # Загружаем настройки
        self.settings = load_launcher_settings()
        self.stats = load_stats()
        self._secret_launcher = None
        self.game_console = None

        # Применяем тему
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
        self.geometry("1200x950")
        self.minsize(1000, 800)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        set_log_callback(self.log)

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

        ensure_game_folder_structure()

        self.create_widgets()
        self.refresh_accounts()
        self.refresh_accounts_listbox()
        self.refresh_mods_list()
        self.scan_and_update_versions()
        # Раньше это был прямой (блокирующий) сетевой запрос прямо в __init__ —
        # окно лаунчера не появлялось, пока не придёт ответ от серверов Mojang.
        # При медленном интернете это могло выглядеть как "лаунчер завис при
        # запуске". Теперь список версий грузится в фоне.
        threading.Thread(target=self.load_available_versions, daemon=True).start()
        self.refresh_resourcepacks()
        self.refresh_skins()

        self.restore_last_selection()

        self.log(f"📁 Папка игры: {MINECRAFT_DIR}")
        self.log(f"📊 Запусков игры: {self.stats.get('launches', 0)}")

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.start_idle_timer()

    def apply_theme(self):
        theme = self.settings.get("theme", "dark")
        ctk.set_appearance_mode("Dark" if theme == "dark" else "Light")

    def get_theme_colors(self):
        """Единая тёмная палитра (по дизайну сайта 67launcher) — переключатель
        светлой темы убран, т.к. сайт не имеет светлого варианта дизайна, а
        частичное переключение только части виджетов выглядело как баг."""
        return {
            "listbox_bg": "#100e1a",
            "listbox_fg": "#e5e2f0",
            "listbox_select": "#6d92ff",
            "card_bg": "#201d30",
            "card_bg_selected": "#2b2840",
        }

    def register_themed_widget(self, widget):
        """Регистрирует tk.Listbox/tk.Text для автоматической перекраски при смене темы"""
        if not hasattr(self, 'themed_widgets'):
            self.themed_widgets = []
        self.themed_widgets.append(widget)

    def apply_widget_theme(self):
        """Перекрашивает все обычные tk-виджеты и карточки модов под текущую тему"""
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

    # =================================================================
    # ФОРМАТИРОВАНИЕ
    # =================================================================

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

    # =================================================================
    # ТАЙМЕРЫ И СТАТИСТИКА
    # =================================================================

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
        last_skin = self.settings.get("last_skin", "")
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
        if last_skin:
            try:
                self.skin_combo.set(last_skin)
            except:
                pass

    def save_current_selection(self):
        self.settings["last_account"] = self.account_combo.get()
        self.settings["last_version"] = self.version_combo.get()
        self.settings["last_skin"] = self.skin_combo.get()
        save_launcher_settings(self.settings)

    def load_available_versions(self):
        try:
            self.log("🔄 Загрузка списка версий...")
            versions = mll.utils.get_available_versions(MINECRAFT_DIR)
            self.available_versions = [v["id"] for v in versions if "snapshot" not in v.get("type", "").lower()]
            self.log(f"✅ Загружено {len(self.available_versions)} версий")
        except Exception as e:
            self.log(f"❌ Ошибка загрузки версий: {e}")
            self.available_versions = []

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
                messagebox.showwarning("Ошибка", "Для установки OptiFine используйте .jar версию установщика!")
                return
            self.selected_installer_path = file_path
            self.install_file_label.configure(text=f"✅ Файл выбран: {os.path.basename(file_path)}",
                                              text_color="#6fce7f")
            self.log(f"📂 Выбран файл OptiFine: {file_path}")
            play_click()

    # =================================================================
    # ДИАГНОСТИКА
    # =================================================================

    def show_download_panel(self, show=True):
        try:
            if hasattr(self, 'download_panel'):
                if show:
                    self.download_panel.grid()
                else:
                    self.download_panel.grid_remove()
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

    # =================================================================
    # ТЕМА
    # =================================================================

    def toggle_game_logs(self):
        """Включает/выключает вывод логов игры и в консоль лаунчера, и в
        отдельное окно GameConsoleWindow. По умолчанию выключено — раньше
        лог Minecraft (сотни строк вроде 'Created ... atlas') сыпался в
        консоль лаунчера при каждом запуске без возможности это выключить."""
        enabled = bool(self.game_logs_switch.get())
        self.settings["show_game_logs"] = enabled
        save_launcher_settings(self.settings)
        self.log(f"🎮 Логи игры: {'включены' if enabled else 'выключены'}")

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

        msg = """Если тебе нравится 67Launcher, рассмотри возможность небольшого доната.

💝 Даже 50 рублей помогут продолжить разработку!

❤️ Спасибо, что пользуешься 67Launcher!"""
        ctk.CTkLabel(main_frame, text=msg, font=ctk.CTkFont(size=14), justify="center", wraplength=420).pack(
            pady=(0, 20))

        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(pady=(10, 5))

        donate_btn = make_sound_button(btn_frame, text="💝 Поддержать",
                                       command=lambda: webbrowser.open("https://www.donationalerts.com/r/ionux"),
                                       width=170, height=50, fg_color="#d9622f", hover_color="#c14f26",
                                       font=ctk.CTkFont(size=15, weight="bold"))
        donate_btn.grid(row=0, column=0, padx=10, pady=5)

        close_btn = make_sound_button(btn_frame, text="Пропустить", command=dialog.destroy,
                                      width=120, height=35, fg_color="#d3453f", hover_color="#b83530",
                                      font=ctk.CTkFont(size=13))
        close_btn.grid(row=0, column=1, padx=10, pady=5)

    # =================================================================
    # СКИНЫ И МОДЫ
    # =================================================================

    def install_custom_skin_loader(self):
        """Точка входа — вызывается из кнопок Forge/Fabric на вкладке скинов.
        Раньше скачивание шло синхронно прямо в обработчике клика и замораживало
        весь интерфейс на время загрузки файла. Теперь быстрая проверка
        (уже установлен или нет) выполняется сразу, а само скачивание уходит
        в фоновый поток."""
        mods_path = os.path.join(MINECRAFT_DIR, "mods")
        os.makedirs(mods_path, exist_ok=True)
        for file in os.listdir(mods_path):
            if "CustomSkinLoader" in file or "SkinLoader" in file:
                self.log("✅ CustomSkinLoader уже установлен")
                play_click()
                messagebox.showinfo("Информация", "Мод CustomSkinLoader уже установлен!")
                return True

        threading.Thread(target=self._install_custom_skin_loader_worker, daemon=True).start()
        return True

    def _install_custom_skin_loader_worker(self):
        try:
            mods_path = os.path.join(MINECRAFT_DIR, "mods")
            self.log("📥 Скачивание CustomSkinLoader Universal...")
            mod_url = "https://github.com/xfl03/MCCustomSkinLoader/releases/download/v15.0.1/CustomSkinLoader_Universal-15.0.1.jar"
            mod_file = os.path.join(mods_path, "CustomSkinLoader.jar")
            success = self.download_with_progress(mod_url, mod_file, "Скачивание CustomSkinLoader")
            if not success:
                return
            self.log("✅ CustomSkinLoader Universal установлен!")
            config_path = os.path.join(MINECRAFT_DIR, "config", "CustomSkinLoader")
            os.makedirs(config_path, exist_ok=True)
            config_file = os.path.join(config_path, "skinloader.json")
            config_data = {
                "enable": True,
                "loadlist": [
                    {"name": "LocalSkin", "type": "LocalSkin", "skin": "LocalSkin/%s.png"},
                    {"name": "Mojang", "type": "MojangAPI"}
                ]
            }
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            self.log("✅ Конфиг CustomSkinLoader создан")
            skins_local_path = os.path.join(MINECRAFT_DIR, "CustomSkinLoader", "LocalSkin")
            os.makedirs(skins_local_path, exist_ok=True)
            play_click()
            self.after(0, lambda: messagebox.showinfo("Успешно", "Мод CustomSkinLoader Universal успешно установлен!"))
        except Exception as e:
            err = str(e)
            self.log(f"❌ Ошибка установки CustomSkinLoader: {err}")
            play_error()
            self.after(0, lambda: messagebox.showerror("Ошибка", f"Не удалось установить CustomSkinLoader.\n\nОшибка: {err}"))

    def install_skin_loader_for_fabric(self):
        self.log("🧵 Установка CustomSkinLoader для Fabric...")
        return self.install_custom_skin_loader()

    def create_skin_data(self, username, skin_path):
        try:
            skins_local_path = os.path.join(MINECRAFT_DIR, "CustomSkinLoader", "LocalSkin")
            os.makedirs(skins_local_path, exist_ok=True)
            skin_filename = f"{username}.png"
            skin_dest = os.path.join(skins_local_path, skin_filename)
            shutil.copy2(skin_path, skin_dest)
            self.log(f"✅ Скин скопирован: .minecraft/CustomSkinLoader/LocalSkin/{skin_filename}")
            return True
        except Exception as e:
            self.log(f"❌ Ошибка установки скина: {e}")
            return False

    def open_mods_folder(self):
        mods_path = os.path.join(MINECRAFT_DIR, "mods")
        os.makedirs(mods_path, exist_ok=True)
        os.startfile(mods_path)
        self.log(f"📂 Открыта папка mods")
        play_click()

    # =================================================================
    # АККАУНТЫ
    # =================================================================

    def refresh_accounts(self):
        accounts = load_accounts()
        usernames = [acc['username'] for acc in accounts]
        if not usernames:
            usernames = ["Нет аккаунтов"]
        self.account_combo.configure(values=usernames)
        if usernames and usernames[0] != "Нет аккаунтов":
            self.account_combo.set(usernames[0])

    def refresh_accounts_listbox(self):
        accounts = load_accounts()
        self.accounts_listbox.delete("1.0", "end")
        if not accounts:
            self.accounts_listbox.insert("1.0", "Нет аккаунтов")
            return
        for acc in accounts:
            created = acc.get('created', 'неизвестно')
            self.accounts_listbox.insert("end", f"👤 {acc['username']}  (создан: {created})\n")

    def add_account_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Добавление аккаунта")
        dialog.geometry("350x180")
        dialog.grab_set()
        ctk.CTkLabel(dialog, text="Введите имя пользователя:", font=ctk.CTkFont(size=13)).pack(pady=(20, 5))
        entry = ctk.CTkEntry(dialog, width=280, height=35)
        entry.pack(pady=(5, 10))

        def confirm():
            username = entry.get().strip()
            if not username:
                play_error()
                messagebox.showwarning("Ошибка", "Имя не может быть пустым")
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

    def delete_selected_account(self):
        selection = self.accounts_listbox.get("1.0", "end").strip()
        if not selection or selection == "Нет аккаунтов":
            play_error()
            messagebox.showwarning("Ошибка", "Нет аккаунтов для удаления")
            return
        username = selection.split("👤")[1].split("(")[0].strip()
        if messagebox.askyesno("Подтверждение", f"Удалить аккаунт '{username}'?"):
            success, msg = delete_account(username)
            if success:
                self.refresh_accounts()
                self.refresh_accounts_listbox()
                play_click()
                messagebox.showinfo("Успешно", msg)
            else:
                play_error()
                messagebox.showerror("Ошибка", msg)

    # =================================================================
    # МОДЫ
    # =================================================================

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
            messagebox.showwarning("Ошибка", "Выберите мод для удаления")
            return
        mod_name = self.installed_listbox.get(selection[0])
        if "Моды не установлены" in mod_name:
            return
        mod_name = mod_name.replace("📦 ", "").strip()
        if messagebox.askyesno("Подтверждение", f"Удалить мод '{mod_name}'?"):
            if delete_mod(mod_name):
                self.refresh_mods_list()
                play_click()
                messagebox.showinfo("Успешно", "Мод удалён")
            else:
                play_error()
                messagebox.showerror("Ошибка", "Не удалось удалить мод")

    # =================================================================
    # РЕСУРСПАКИ
    # =================================================================

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
            messagebox.showinfo("Успешно", f"Ресурспак '{filename}' установлен!")
            self.refresh_resourcepacks()
            return True
        except Exception as e:
            self.log(f"❌ Ошибка установки ресурспака: {e}")
            play_error()
            messagebox.showerror("Ошибка", f"Не удалось установить ресурспак:\n{e}")
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
            messagebox.showinfo("Успешно", f"Ресурспак '{pack_name}' удален!")
            self.refresh_resourcepacks()
            return True
        except Exception as e:
            self.log(f"❌ Ошибка удаления ресурспака: {e}")
            play_error()
            messagebox.showerror("Ошибка", f"Не удалось удалить ресурспак:\n{e}")
            return False

    def delete_selected_resourcepack(self):
        selection = self.resourcepacks_listbox.curselection()
        if not selection:
            play_error()
            messagebox.showwarning("Ошибка", "Выберите ресурспак для удаления")
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

    # =================================================================
    # СКИНЫ
    # =================================================================

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
            self.skin_combo.configure(values=["Нет скинов"])
            return
        skin_names = []
        for skin in skins:
            info = f"🎨 {skin['name']} ({skin['size']})"
            self.skins_listbox.insert("end", info)
            skin_names.append(skin['name'])
        self.skin_combo.configure(values=skin_names)
        if skin_names:
            self.skin_combo.set(skin_names[0])

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
            messagebox.showinfo("Успешно", f"Скин '{filename}' импортирован!")
            self.refresh_skins()
            return True
        except Exception as e:
            self.log(f"❌ Ошибка импорта скина: {e}")
            play_error()
            messagebox.showerror("Ошибка", f"Не удалось импортировать скин:\n{e}")
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
            messagebox.showinfo("Успешно", f"Скин '{skin_name}' удален!")
            self.refresh_skins()
            return True
        except Exception as e:
            self.log(f"❌ Ошибка удаления скина: {e}")
            play_error()
            messagebox.showerror("Ошибка", f"Не удалось удалить скин:\n{e}")
            return False

    def delete_selected_skin(self):
        selection = self.skins_listbox.curselection()
        if not selection:
            play_error()
            messagebox.showwarning("Ошибка", "Выберите скин для удаления")
            return
        selected_text = self.skins_listbox.get(selection[0])
        if "📭" in selected_text:
            return
        name = selected_text.split("🎨 ")[1].split(" (")[0].strip()
        self.delete_skin(name)

    def preview_skin(self):
        skin_name = self.skin_combo.get()
        if not skin_name or skin_name == "Нет скинов":
            play_error()
            messagebox.showinfo("Информация", "Скин не выбран")
            return
        skins_path = get_skins_folder()
        skin_path = os.path.join(skins_path, skin_name)
        if not os.path.exists(skin_path):
            play_error()
            messagebox.showerror("Ошибка", f"Скин '{skin_name}' не найден")
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
            messagebox.showerror("Ошибка", f"Не удалось открыть скин:\n{e}")

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

💡 Для использования выберите этот скин на вкладке "Игра"
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

    def on_resourcepack_double_click(self, event):
        selection = self.resourcepacks_listbox.curselection()
        if not selection:
            return
        selected_text = self.resourcepacks_listbox.get(selection[0])
        if "📭" in selected_text:
            return
        name = selected_text.split("📦 ")[1].split(" -")[0].strip()
        messagebox.showinfo("Информация о ресурспаке", f"Ресурспак: {name}")

    # =================================================================
    # СОЗДАНИЕ ВКЛАДОК
    # =================================================================

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
                                           font=ctk.CTkFont(size=11), text_color="#a8a4bd")
        self.subtitle_label.pack(side="left", padx=(10, 0))

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
        self.account_combo = ctk.CTkComboBox(main_frame, values=["Нет аккаунтов"], width=300, height=35)
        self.account_combo.grid(row=2, column=0, sticky="w", pady=(0, 15))

        ctk.CTkLabel(main_frame, text="📦 Версия:", font=ctk.CTkFont(size=14)).grid(row=3, column=0, sticky="w")
        self.version_combo = ctk.CTkComboBox(main_frame, values=["Нет версий"], width=300, height=35)
        self.version_combo.grid(row=4, column=0, sticky="w", pady=(0, 15))

        ctk.CTkLabel(main_frame, text="🎨 Скин:", font=ctk.CTkFont(size=14)).grid(row=5, column=0, sticky="w")
        self.skin_combo = ctk.CTkComboBox(main_frame, values=["Нет скинов"], width=300, height=35)
        self.skin_combo.grid(row=6, column=0, sticky="w", pady=(0, 15))

        ctk.CTkLabel(main_frame, text="💾 RAM:", font=ctk.CTkFont(size=14)).grid(row=7, column=0, sticky="w")
        self.ram_var = ctk.StringVar(value="2G")
        ram_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        ram_frame.grid(row=8, column=0, sticky="w", pady=(0, 20))
        for ram in ["1G", "2G", "3G", "4G", "6G", "8G"]:
            ctk.CTkRadioButton(ram_frame, text=ram, variable=self.ram_var, value=ram).pack(side="left", padx=5)

        self.launch_status_label = ctk.CTkLabel(main_frame, text="✅ Готов к запуску", font=ctk.CTkFont(size=13))
        self.launch_status_label.grid(row=9, column=0, sticky="w", pady=(0, 10))

        self.launch_progressbar = AnimatedProgressBar(main_frame, width=300, height=15)
        self.launch_progressbar.grid(row=10, column=0, sticky="ew", pady=(0, 15))

        self.launch_btn = make_sound_button(main_frame, text="🚀 ЗАПУСТИТЬ ИГРУ", command=self.launch_game, height=50,
                                            font=ctk.CTkFont(size=16, weight="bold"), fg_color="#7896f7",
                                            hover_color="#5f7fe0")
        self.launch_btn.grid(row=11, column=0, sticky="ew", pady=(0, 10))

        self.timer_label = ctk.CTkLabel(main_frame, text="⏱ Время игры: 0с", font=ctk.CTkFont(size=13))
        self.timer_label.grid(row=12, column=0, sticky="w")

    def create_install_tab(self):
        tab = self.tab_view.tab("📦 Установка")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        main_frame = ctk.CTkFrame(tab)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        main_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(main_frame, text="📦 Установка клиентов", font=ctk.CTkFont(size=24, weight="bold")).grid(row=0,
                                                                                                             column=0,
                                                                                                             pady=(0,
                                                                                                                   20))
        ctk.CTkLabel(main_frame, text="Тип установки:", font=ctk.CTkFont(size=14)).grid(row=1, column=0, sticky="w")

        self.install_type_var = ctk.StringVar(value="vanilla")
        type_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        type_frame.grid(row=2, column=0, sticky="w", pady=(0, 10))
        types = [("🌐 Vanilla", "vanilla"), ("🧵 Fabric", "fabric"), ("🔥 Forge", "forge"), ("✨ OptiFine", "optifine")]
        for text, value in types:
            ctk.CTkRadioButton(type_frame, text=text, variable=self.install_type_var, value=value).pack(side="left",
                                                                                                        padx=10)

        ctk.CTkLabel(main_frame, text="Версия Minecraft:", font=ctk.CTkFont(size=14)).grid(row=3, column=0, sticky="w")
        self.install_version_entry = ctk.CTkEntry(main_frame, placeholder_text="Например: 1.20.4", width=300, height=35)
        self.install_version_entry.grid(row=4, column=0, sticky="w", pady=(0, 10))

        self.install_file_label = ctk.CTkLabel(main_frame, text="❌ Файл не выбран (только для OptiFine)",
                                               text_color="#d3453f")
        self.install_file_label.grid(row=5, column=0, sticky="w", pady=(0, 5))

        select_file_btn = make_sound_button(main_frame, text="📂 Выбрать файл OptiFine",
                                            command=self.select_optifine_file, fg_color="#d9622f",
                                            hover_color="#c14f26", text_color="#16141f")
        select_file_btn.grid(row=6, column=0, sticky="w", pady=(0, 15))

        self.install_status_label = ctk.CTkLabel(main_frame, text="✅ Готов к установке", font=ctk.CTkFont(size=13))
        self.install_status_label.grid(row=7, column=0, sticky="w", pady=(0, 10))

        self.install_progressbar = AnimatedProgressBar(main_frame, width=300, height=15)
        self.install_progressbar.grid(row=8, column=0, sticky="ew", pady=(0, 15))

        self.install_btn = make_sound_button(main_frame, text="📥 УСТАНОВИТЬ", command=self.install_selected_client,
                                             height=50, font=ctk.CTkFont(size=16, weight="bold"), fg_color="#6fce7f",
                                             hover_color="#5cb56c", text_color="#16141f")
        self.install_btn.grid(row=9, column=0, sticky="ew")

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
        self.accounts_listbox = tk.Text(left_frame, bg=_c["listbox_bg"], fg=_c["listbox_fg"], font=("Consolas", 11), height=15,
                                        relief="flat")
        self.accounts_listbox.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        self.register_themed_widget(self.accounts_listbox)

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

        right_frame = ctk.CTkFrame(tab)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 20), pady=20)
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(0, weight=1)

        ctk.CTkLabel(right_frame, text="ℹ️ Информация", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0,
                                                                                                       pady=(0, 10))
        info_text = """📌 Инструкция:

1. Нажмите "Добавить"
2. Введите имя пользователя
3. Аккаунт будет создан

💡 Аккаунты сохраняются в папке игры
💡 Можно создать несколько аккаунтов"""
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

        self.mod_status_label = ctk.CTkLabel(left_frame, text="Введите запрос и нажмите 'Искать'",
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
        self.installed_listbox = tk.Listbox(right_frame, bg=_c["listbox_bg"], fg=_c["listbox_fg"], font=("Consolas", 11), height=12,
                                            relief="flat")
        self.installed_listbox.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
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

        self.mod_desc_title = ctk.CTkLabel(self.mod_desc_card, text="Выберите мод в списке слева",
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
        self.skins_listbox = tk.Listbox(left_frame, bg=_c["listbox_bg"], fg=_c["listbox_fg"], selectbackground=_c["listbox_select"],
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

        mod_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        mod_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(10, 0))

        ctk.CTkLabel(mod_frame, text="📦 Установка мода для скинов:", font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#6d92ff").pack(anchor="w")

        forge_btn = make_sound_button(mod_frame, text="🔥 Forge", command=self.install_custom_skin_loader,
                                      fg_color="#e67e22", hover_color="#d35400", text_color="white", height=30)
        forge_btn.pack(side="left", padx=2, pady=2)

        fabric_btn = make_sound_button(mod_frame, text="🧵 Fabric", command=self.install_skin_loader_for_fabric,
                                       fg_color="#2ecc71", hover_color="#27ae60", text_color="white", height=30)
        fabric_btn.pack(side="left", padx=2, pady=2)

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
        self.skin_info.insert("1.0", "Выберите скин для просмотра информации")
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
        left_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(left_frame, text="📦 Ресурспаки", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0,
                                                                                                     pady=(0, 10))

        _c = self.get_theme_colors()
        self.resourcepacks_listbox = tk.Listbox(left_frame, bg=_c["listbox_bg"], fg=_c["listbox_fg"], selectbackground=_c["listbox_select"],
                                                font=("Consolas", 11), height=12, relief="flat")
        self.resourcepacks_listbox.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        self.resourcepacks_listbox.bind("<Double-Button-1>", self.on_resourcepack_double_click)
        self.register_themed_widget(self.resourcepacks_listbox)

        btn_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew")
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)
        btn_frame.grid_columnconfigure(2, weight=1)

        install_btn = make_sound_button(btn_frame, text="📥 Установить", command=self.install_resourcepack,
                                        fg_color="#6fce7f", hover_color="#5cb56c", text_color="#16141f")
        install_btn.grid(row=0, column=0, padx=2)

        delete_btn = make_sound_button(btn_frame, text="🗑️ Удалить", command=self.delete_selected_resourcepack,
                                       fg_color="#d3453f", hover_color="#b83530")
        delete_btn.grid(row=0, column=1, padx=2)

        open_folder_btn = make_sound_button(btn_frame, text="📂 Открыть папку", command=self.open_resourcepacks_folder,
                                            fg_color="#6d92ff", hover_color="#5a7dd8")
        open_folder_btn.grid(row=0, column=2, padx=2)

        right_frame = ctk.CTkFrame(tab)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 20), pady=20)
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(right_frame, text="ℹ️ Информация", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0,
                                                                                                       pady=(0, 10))

        self.resourcepack_info = ctk.CTkTextbox(right_frame, font=ctk.CTkFont(family="Consolas", size=11), height=200)
        self.resourcepack_info.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        self.resourcepack_info.insert("1.0", "Выберите ресурспак для просмотра информации")
        self.resourcepack_info.configure(state="disabled")

    def create_settings_tab(self):
        tab = self.tab_view.tab("⚙️ Настройки")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        main_frame = ctk.CTkFrame(tab)
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
        self.game_logs_switch = ctk.CTkSwitch(logs_frame, text="Показывать логи игры (консоль лаунчера + отдельное окно)",
                                              command=self.toggle_game_logs, font=ctk.CTkFont(size=13))
        if self.settings.get("show_game_logs", False):
            self.game_logs_switch.select()
        else:
            self.game_logs_switch.deselect()
        self.game_logs_switch.pack(side="left")

        # ================ ПАСХАЛКА - КНОПКА ПОДАРКА ================
        ctk.CTkLabel(main_frame, text="🎁 Секретный подарок", font=ctk.CTkFont(size=14, weight="bold")).grid(row=3,
                                                                                                            column=0,
                                                                                                            sticky="w",
                                                                                                            pady=(15,
                                                                                                                  5))

        gift_btn = ctk.CTkButton(
            main_frame,
            text="🎁 ПОЛУЧИТЬ ПОДАРОК",
            command=lambda: show_gift_dialog(self),
            fg_color="#d9622f",
            hover_color="#c14f26",
            text_color="#16141f",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=50,
            width=300
        )
        gift_btn.grid(row=4, column=0, sticky="w", pady=(0, 15))

        ctk.CTkLabel(
            main_frame,
            text="💡 Нажмите, чтобы получить секретный подарок!",
            font=ctk.CTkFont(size=12),
            text_color="#6d92ff"
        ).grid(row=5, column=0, sticky="w", pady=(0, 15))

        ctk.CTkLabel(main_frame, text="🔗 Полезные ссылки", font=ctk.CTkFont(size=14, weight="bold")).grid(row=6,
                                                                                                          column=0,
                                                                                                          sticky="w",
                                                                                                          pady=(5, 10))
        links_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        links_frame.grid(row=7, column=0, sticky="w", pady=(0, 15))

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

    # =================================================================
    # ПОИСК МОДОВ
    # =================================================================

    def show_mod_results_placeholder(self):
        """Заглушка для области результатов поиска, пока ничего не искали —
        раньше там была просто пустая рамка без текста, выглядело как баг."""
        for widget in self.results_frame.winfo_children():
            widget.destroy()
        placeholder = ctk.CTkFrame(self.results_frame, fg_color="transparent")
        placeholder.pack(fill="both", expand=True, pady=40)
        ctk.CTkLabel(placeholder, text="🔍", font=ctk.CTkFont(size=36)).pack()
        ctk.CTkLabel(placeholder, text="Введите название мода и нажмите «Искать»",
                     font=ctk.CTkFont(size=13), text_color="#6d92ff").pack(pady=(5, 0))

    def search_mods(self):
        query = self.mod_search_entry.get().strip()
        if not query:
            play_error()
            messagebox.showwarning("Ошибка", "Введите название мода")
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

        self.mod_desc_open_btn.configure(state="normal")

    def open_selected_mod_page(self):
        if self.selected_mod_index < 0 or self.selected_mod_index >= len(self.search_results):
            return
        mod = self.search_results[self.selected_mod_index]
        slug = mod.get('slug') or mod.get('project_id')
        if slug:
            webbrowser.open(f"https://modrinth.com/mod/{slug}")
            play_click()

    def reset_mod_description(self):
        self.mod_desc_title.configure(text="Выберите мод в списке слева")
        self.mod_desc_meta.configure(text="")
        self.mod_desc_icon.configure(text="📦", image=None)
        self.mod_desc_text.configure(state="normal")
        self.mod_desc_text.delete("1.0", "end")
        self.mod_desc_text.configure(state="disabled")
        self.mod_desc_open_btn.configure(state="disabled")

    def install_selected_mod(self):
        if self.selected_mod_index < 0 or self.selected_mod_index >= len(self.search_results):
            play_error()
            messagebox.showwarning("Ошибка", "Сначала выберите мод")
            return
        mod = self.search_results[self.selected_mod_index]
        project_id = mod.get('project_id')
        if not project_id:
            play_error()
            messagebox.showerror("Ошибка", "ID мода не найден")
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
            messagebox.showinfo("Успешно", f"✅ Мод '{result}' установлен!")
        else:
            self.mod_status_label.configure(text=f"❌ Ошибка: {result}", text_color="#d3453f")
            play_error()
            messagebox.showerror("Ошибка", f"❌ Не удалось установить мод:\n{result}")

    # =================================================================
    # ЗАПУСК ИГРЫ
    # =================================================================

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

    def launch_game(self):
        if self.is_launching:
            return

        username = self.account_combo.get()
        if username == "Нет аккаунтов" or not username:
            play_error()
            messagebox.showwarning("Ошибка", "Сначала создайте аккаунт")
            return

        version = self.version_combo.get()
        if version == "Нет версий" or not version:
            play_error()
            messagebox.showwarning("Ошибка", "Сначала установите версию Minecraft")
            return

        ram = self.ram_var.get()
        skin_name = self.skin_combo.get()
        skin_path = None
        if skin_name and skin_name != "Нет скинов":
            skin_path = os.path.join(get_skins_folder(), skin_name)
            if not os.path.exists(skin_path):
                skin_path = None

        self.is_launching = True
        self.launch_btn.configure(state="disabled", text="⏳ ЗАПУСК...")
        self.launch_progressbar.start_animation()
        self.launch_status_label.configure(text="⏳ Запуск Minecraft...", text_color="#d9622f")
        self.log(f"🚀 Запуск: {version} от {username} с памятью {ram}")
        self.update_idletasks()

        def do_launch():
            error_message = None
            success = False
            try:
                java_path = get_java_for_version(version)
                self.log(f"☕ Java: {java_path}")

                version_path = os.path.join(MINECRAFT_DIR, "versions", version)
                if not os.path.exists(version_path):
                    error_message = f"Версия {version} не найдена"
                    self.after(0, lambda: self.launch_finish(False, error_message))
                    return

                jar_path = os.path.join(version_path, f"{version}.jar")
                if not os.path.exists(jar_path):
                    error_message = f"JAR файл не найден: {jar_path}"
                    self.log(f"❌ {error_message}")
                    self.after(0, lambda: self.launch_finish(False, error_message))
                    return

                if skin_path and os.path.exists(skin_path):
                    self.create_skin_data(username, skin_path)
                    self.log(f"🎨 Скин установлен для {username}")

                command = mll.command.get_minecraft_command(
                    version=version,
                    minecraft_directory=MINECRAFT_DIR,
                    options=mll.utils.generate_test_options()
                )

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
                command.extend(["--username", username])
                command.extend(["--uuid", "00000000-0000-0000-0000-000000000000"])
                command.extend(["--accessToken", "0"])
                command.extend(["--userType", "mojang"])

                if java_path != "java":
                    command.insert(0, java_path)

                self.log(f"📋 Команда запуска: {' '.join(command[:6])}...")

                self.minecraft_process = subprocess.Popen(
                    command,
                    cwd=MINECRAFT_DIR,
                    # Раньше здесь стоял creationflags=CREATE_NEW_CONSOLE — это
                    # открывало нативное окно консоли Windows, в которое Java
                    # писала часть вывода в обход pipe, из-за чего консоль
                    # лаунчера оставалась пустой. Теперь весь вывод идёт только
                    # через pipe и попадает и в лаунчер, и в отдельное окно
                    # GameConsoleWindow (см. read_output ниже).
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    errors='ignore'
                )

                # Отдельное окно логов игры и вывод в консоль лаунчера — теперь
                # управляются настройкой show_game_logs (по умолчанию выключено).
                # Раньше окно открывалось всегда, а логи (сотни строк вроде
                # 'Created ... atlas') всегда сыпались в консоль лаунчера.
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
                success = True
                update_stats()
                self.stats = load_stats()
                # start_game_timer() трогает Tkinter-виджеты (лейбл таймера) —
                # эта строка запускается на фоновом потоке do_launch, поэтому
                # диспетчеризуем через after, а не вызываем напрямую.
                self.after(0, self.start_game_timer)

                def monitor_process():
                    if self.minecraft_process:
                        self.minecraft_process.wait()
                        self.after(0, self.stop_game_timer)
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
        self.launch_progressbar.stop_animation()

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
            messagebox.showerror("Ошибка запуска", f"Не удалось запустить игру.\n\nОшибка: {message}")

    # =================================================================
    # УСТАНОВКА КЛИЕНТОВ
    # =================================================================

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

            if hasattr(mll.forge, 'install_forge'):
                mll.forge.install_forge(version, MINECRAFT_DIR, mll_callback)
            elif hasattr(mll.install, 'install_forge'):
                mll.install.install_forge(version, MINECRAFT_DIR, mll_callback)
            else:
                return self.install_forge_manual(version)

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
        version = self.install_version_entry.get().strip()

        if not version:
            play_error()
            messagebox.showwarning("Ошибка", "Введите версию Minecraft")
            return

        if install_type == "optifine":
            if not hasattr(self, 'selected_installer_path') or not self.selected_installer_path:
                play_error()
                messagebox.showwarning("Ошибка", "Сначала выберите файл установщика OptiFine")
                return

        self.log(f"📦 Установка {install_type} {version}")
        self.install_btn.configure(state="disabled", text="⏳ УСТАНОВКА...")
        self.install_progressbar.start_animation()
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

            # Весь блок ниже раньше выполнялся прямо на фоновом потоке (кроме
            # двух отдельных self.after ниже) — обращения к progressbar,
            # install_status_label, scan_and_update_versions() и messagebox
            # напрямую из фонового потока небезопасны для Tkinter. Собрали всё
            # в один блок и диспетчеризуем через after единожды.
            def finish_ui():
                self.install_btn.configure(state="normal", text="📥 УСТАНОВИТЬ")
                self.install_progressbar.stop_animation()
                if success:
                    self.log(f"✅ {install_type.capitalize()} {version} установлен!")
                    self.install_progressbar.set(1.0)
                    self.install_progressbar.configure(progress_color="#6fce7f")
                    self.install_status_label.configure(text=f"✅ {install_type.capitalize()} {version} установлен!",
                                                        text_color="#6fce7f")
                    self.scan_and_update_versions()
                    play_click()
                    messagebox.showinfo("Успешно", f"{install_type.capitalize()} {version} успешно установлен!")
                else:
                    self.log(f"❌ Ошибка установки {install_type}")
                    self.install_progressbar.set(0.3)
                    self.install_progressbar.configure(progress_color="#d3453f")
                    self.install_status_label.configure(text=f"❌ Ошибка установки {install_type}", text_color="#d3453f")
                    play_error()
                    messagebox.showerror("Ошибка", f"Не удалось установить {install_type} {version}")

            self.after(0, finish_ui)

        threading.Thread(target=do_install, daemon=True).start()

    # =================================================================
    # ЧАТ
    # =================================================================

    def open_chat_window(self):
        """Открытие окна выбора режима чата"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("💬 Настройка чата")
        dialog.geometry("600x620")
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
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(main_frame, text="💬 Настройка чата",
                     font=ctk.CTkFont(size=24, weight="bold"), text_color="#6d92ff").pack(pady=(0, 10))

        try:
            local_ip = socket.gethostbyname(socket.gethostname())
        except:
            local_ip = "Не определен"

        ip_frame = ctk.CTkFrame(main_frame, fg_color="#100e1a", corner_radius=10)
        ip_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(ip_frame, text="🌐 ВАШ IP В ЛОКАЛЬНОЙ СЕТИ:",
                     font=ctk.CTkFont(size=13, weight="bold"), text_color="#6fce7f").pack(pady=(5, 2))
        ctk.CTkLabel(ip_frame, text=local_ip,
                     font=ctk.CTkFont(size=20, weight="bold"), text_color="#6d92ff").pack(pady=(2, 5))
        ctk.CTkLabel(ip_frame, text="📋 Скопируйте этот IP и отправьте ДРУГОМУ игроку",
                     font=ctk.CTkFont(size=11), text_color="#d9622f").pack(pady=(0, 2))

        copy_btn = make_sound_button(ip_frame, text="📋 Копировать IP",
                                     command=lambda: self.copy_ip_to_clipboard(local_ip),
                                     width=150, height=32,
                                     fg_color="#6d92ff", hover_color="#5a7dd8",
                                     font=ctk.CTkFont(size=12))
        copy_btn.pack(pady=(5, 8))

        instr_frame = ctk.CTkFrame(main_frame, fg_color="#201d30", corner_radius=10)
        instr_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(instr_frame, text="📝 КАК ПОДКЛЮЧИТЬСЯ:",
                     font=ctk.CTkFont(size=13, weight="bold"), text_color="#d9622f").pack(pady=(5, 5))

        instr_text = """1️⃣ ОДИН игрок запускает режим "Сервер"
2️⃣ Сервер копирует свой IP (написан выше)
3️⃣ Сервер отправляет IP ВТОРОМУ игроку
4️⃣ ВТОРОЙ игрок запускает режим "Клиент"
5️⃣ Клиент вставляет полученный IP
6️⃣ Клиент нажимает "Запустить чат"

⚠️ НЕ используйте 127.0.0.1 - это ваш компьютер!
✅ Используйте IP, который показывает сервер"""

        ctk.CTkLabel(instr_frame, text=instr_text,
                     font=ctk.CTkFont(size=12), text_color="#e5e2f0",
                     justify="left", wraplength=520).pack(pady=5, padx=10)

        mode_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        mode_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(mode_frame, text="Выберите режим:",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w")

        mode_var = ctk.StringVar(value="server")

        server_rb = ctk.CTkRadioButton(mode_frame, text="🖥️ Я СЕРВЕР (создать комнату) - запустите ПЕРВЫМ",
                                       variable=mode_var, value="server",
                                       font=ctk.CTkFont(size=13))
        server_rb.pack(anchor="w", pady=3)

        client_rb = ctk.CTkRadioButton(mode_frame, text="💻 Я КЛИЕНТ (подключиться) - запустите ВТОРЫМ",
                                       variable=mode_var, value="client",
                                       font=ctk.CTkFont(size=13))
        client_rb.pack(anchor="w", pady=3)

        settings_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        settings_frame.pack(fill="x", pady=(0, 10))

        ip_row = ctk.CTkFrame(settings_frame, fg_color="transparent")
        ip_row.pack(fill="x", pady=3)

        ctk.CTkLabel(ip_row, text="🌐 IP адрес сервера:", font=ctk.CTkFont(size=13, weight="bold"),
                     width=140).pack(side="left")
        host_entry = ctk.CTkEntry(ip_row, placeholder_text="Введите IP сервера", width=220, height=35,
                                  font=ctk.CTkFont(size=13))
        host_entry.pack(side="left", padx=(10, 0))
        host_entry.insert(0, local_ip if local_ip != "Не определен" else "")

        paste_btn = make_sound_button(ip_row, text="📋 Вставить",
                                      command=lambda: self.paste_ip_to_entry(host_entry),
                                      width=80, height=30,
                                      fg_color="#d9622f", hover_color="#c14f26",
                                      text_color="#16141f", font=ctk.CTkFont(size=11))
        paste_btn.pack(side="left", padx=(5, 0))

        port_row = ctk.CTkFrame(settings_frame, fg_color="transparent")
        port_row.pack(fill="x", pady=3)

        ctk.CTkLabel(port_row, text="🔌 Порт:", font=ctk.CTkFont(size=13, weight="bold"),
                     width=140).pack(side="left")
        port_entry = ctk.CTkEntry(port_row, placeholder_text="25565", width=150, height=35,
                                  font=ctk.CTkFont(size=13))
        port_entry.pack(side="left", padx=(10, 0))
        port_entry.insert(0, "25565")

        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(5, 0))

        def start_chat():
            try:
                mode = mode_var.get()
                host = host_entry.get().strip()
                port = int(port_entry.get().strip())

                if mode == "client" and not host:
                    play_error()
                    messagebox.showwarning("Ошибка", "Введите IP адрес сервера!")
                    return

                if port < 1024 or port > 65535:
                    play_error()
                    messagebox.showwarning("Ошибка", "Порт должен быть в диапазоне 1024-65535")
                    return

                if mode == "client" and host == "127.0.0.1":
                    if not messagebox.askyesno("⚠️ ВНИМАНИЕ!",
                                               "Вы используете 127.0.0.1 - это ваш собственный компьютер!\n\n"
                                               "Для подключения к ДРУГОМУ компьютеру используйте ЕГО IP.\n\n"
                                               "Продолжить с 127.0.0.1?"):
                        return

                dialog.destroy()
                chat_window = ChatWindow(self, mode, host, port)
                self.log(f"💬 Чат открыт в режиме: {mode} с IP: {host}")

            except ValueError:
                play_error()
                messagebox.showerror("Ошибка", "Порт должен быть числом!")
            except Exception as e:
                play_error()
                messagebox.showerror("Ошибка", f"Не удалось открыть чат:\n{e}")

        start_btn = make_sound_button(btn_frame, text="🚀 ЗАПУСТИТЬ ЧАТ", command=start_chat,
                                      fg_color="#6fce7f", hover_color="#5cb56c", text_color="#16141f",
                                      font=ctk.CTkFont(size=16, weight="bold"), height=50)
        start_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))

        cancel_btn = make_sound_button(btn_frame, text="❌ ОТМЕНА", command=dialog.destroy,
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
            messagebox.showinfo("Информация", "Буфер обмена пуст")

    def copy_ip_to_clipboard(self, ip):
        try:
            self.clipboard_clear()
            self.clipboard_append(ip)
            play_click()
            messagebox.showinfo("Скопировано", f"IP-адрес скопирован в буфер обмена:\n{ip}")
        except:
            play_error()
            messagebox.showerror("Ошибка", "Не удалось скопировать IP")

    # =================================================================
    # СЕКРЕТНЫЙ ЛАУНЧЕР
    # =================================================================

    def on_stats_refresh_click(self):
        self.settings["secret_clicks"] = self.settings.get("secret_clicks", 0) + 1
        save_launcher_settings(self.settings)
        clicks = self.settings["secret_clicks"]

        if clicks <= 5:
            self.log(f"🔍 Клик {clicks}/5")
            self.update_stats_display()
            if clicks == 5:
                self.log("🎮 Открываем секретный лаунчер!")
                self.after(500, self.open_secret_launcher)
        else:
            self.settings["secret_clicks"] = 0
            save_launcher_settings(self.settings)
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
                self._secret_launcher = None

            self._secret_launcher.protocol("WM_DELETE_WINDOW", on_close)

        except Exception as e:
            self.log(f"❌ Ошибка открытия секретного лаунчера: {e}")
            play_error()
            messagebox.showerror("Ошибка",
                                 f"Не удалось открыть секретный лаунчер:\n{e}\n\n"
                                 "Попробуйте перезапустить лаунчер.")

    # =================================================================
    # КОНСОЛЬ И ЗАКРЫТИЕ
    # =================================================================

    def clear_console(self):
        self.console_text.delete("1.0", "end")
        self.console_text.insert("1.0", "[00:00:00] Консоль очищена\n")

    def copy_console_log(self):
        try:
            text = self.console_text.get("1.0", "end").strip()
            if not text:
                play_error()
                messagebox.showinfo("Информация", "Консоль пуста")
                return
            self.clipboard_clear()
            self.clipboard_append(text)
            play_click()
            messagebox.showinfo("Скопировано", "Лог консоли скопирован в буфер обмена.\nМожно вставить в чат поддержки или отчёт об ошибке.")
        except Exception as e:
            play_error()
            messagebox.showerror("Ошибка", f"Не удалось скопировать лог:\n{e}")

    def log(self, message):
        # self.log() вызывается из множества фоновых потоков (установка модов,
        # скачивание файлов, запуск игры, поиск версий) — прямые вызовы Tkinter
        # оттуда небезопасны и могут приводить к подвисаниям/крашам. Перекидываем
        # выполнение в главный поток.
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


# ===================================================================
# ЗАПУСК
# ===================================================================

if __name__ == "__main__":
    try:
        app = LauncherApp()
        app.mainloop()
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        import traceback

        traceback.print_exc()
        # Создаем файл с ошибкой
        with open("error_log.txt", "w", encoding="utf-8") as f:
            f.write(f"Ошибка: {e}\n")
            f.write(traceback.format_exc())
        play_error()
        input("\nНажмите Enter для выхода...")
