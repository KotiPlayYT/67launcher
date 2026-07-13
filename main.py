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


# ===================================================================
# ОПРЕДЕЛЕНИЕ ПУТИ К ФАЙЛУ НАСТРОЕК
# ===================================================================

def get_settings_path():
    """Возвращает ЕДИНЫЙ путь к файлу настроек"""
    docs_path = os.path.join(os.path.expanduser("~"), "Documents", "67Launcher")

    try:
        os.makedirs(docs_path, exist_ok=True)
    except:
        pass

    settings_path = os.path.join(docs_path, "launcher_settings.json")
    return settings_path


# ===================================================================
# FIX SSL ДЛЯ WINDOWS И PYINSTALLER
# ===================================================================

def get_resource_path(relative_path):
    """Получает правильный путь к ресурсам для PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def get_cert_path():
    """Находит путь к сертификату"""
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
        cert_path = get_resource_path("cacert.pem")
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
    """Исправляет проблемы с SSL на Windows"""
    try:
        cert_path = get_cert_path()

        if cert_path and os.path.exists(cert_path):
            print(f"✅ Найден сертификат: {cert_path}")
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

            try:
                import certifi
                if hasattr(certifi, 'where'):
                    def new_where():
                        return cert_path

                    certifi.where = new_where
            except:
                pass

            print("✅ SSL fix applied")
            return True
        else:
            return False

    except Exception as e:
        print(f"⚠️ SSL fix error: {e}")
        return False


if sys.platform == "win32":
    try:
        fix_ssl_for_windows()
    except Exception as e:
        print(f"⚠️ SSL fix error: {e}")

# ===================================================================
# НАСТРОЙКА ВНЕШНЕГО ВИДА
# ===================================================================

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ===================================================================
# 1. НАСТРОЙКИ И ПЕРЕМЕННЫЕ
# ===================================================================

DEFAULT_GAME_DIR = os.path.join(os.environ['APPDATA'], ".minecraft")
GAME_DIR = DEFAULT_GAME_DIR
MINECRAFT_DIR = GAME_DIR

# Файлы настроек
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


# ПРИНУДИТЕЛЬНО ИСПРАВЛЯЕМ ПУТЬ В НАСТРОЙКАХ
def fix_game_path():
    """Принудительно исправляет путь к папке игры в настройках"""
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
                print(f"✅ Путь исправлен с '{old_path}' на '{DEFAULT_GAME_DIR}'")
        except Exception as e:
            print(f"⚠️ Ошибка исправления пути: {e}")


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
# 2. РАБОТА С НАСТРОЙКАМИ ЛАУНЧЕРА
# ===================================================================

def load_launcher_settings():
    """Загружает настройки лаунчера"""
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
        "theme": "dark"
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
        except Exception as e:
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
    """Сохраняет настройки лаунчера"""
    try:
        if 'support_shown' in settings:
            del settings['support_shown']

        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)

        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)

        return True
    except Exception as e:
        return False


# ===================================================================
# 3. СТАТИСТИКА
# ===================================================================

def load_stats():
    default_stats = {
        "launches": 0,
        "total_play_time": 0,
        "last_launch": None,
        "launch_history": []
    }

    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                stats = json.load(f)
                return stats
        except:
            return default_stats
    return default_stats


def save_stats(stats):
    try:
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
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
        LauncherApp.instance.update_info_display()
        LauncherApp.instance.update_subtitle()


def update_play_time(seconds):
    stats = load_stats()
    stats["total_play_time"] = stats.get("total_play_time", 0) + seconds
    save_stats(stats)

    if LauncherApp.instance:
        LauncherApp.instance.stats = stats
        LauncherApp.instance.update_info_display()


# ===================================================================
# 4. РАБОТА С ПАПКОЙ ИГРЫ
# ===================================================================

def create_launcher_profiles():
    launcher_profiles = {
        "profiles": {},
        "settings": {
            "enableSnapshots": False,
            "enableHistorical": False,
            "keepLauncherOpen": False
        },
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
            except Exception:
                pass


def ensure_game_folder_structure():
    global MINECRAFT_DIR
    os.makedirs(MINECRAFT_DIR, exist_ok=True)
    for folder in REQUIRED_FOLDERS:
        folder_path = os.path.join(MINECRAFT_DIR, folder)
        os.makedirs(folder_path, exist_ok=True)

    create_launcher_profiles()

    empty_files = [
        "accounts.json",
        "options.txt",
        "profile.json",
        "profiles.json",
        "servers.dat",
        "usercache.json"
    ]

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
        except Exception as e:
            return []
    return []


def save_accounts(accounts):
    os.makedirs(os.path.dirname(ACCOUNTS_FILE), exist_ok=True)
    try:
        with open(ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(accounts, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        return False


def create_offline_account(username):
    return {
        "type": "offline",
        "username": username,
        "created": time.strftime("%Y-%m-%d %H:%M:%S")
    }


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
    except Exception as e:
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
    except Exception as e:
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
    except Exception as e:
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
        """Запускает анимацию спиннера"""
        if self.running:
            return
        self.running = True
        self.idx = 0
        self._animate()

    def _animate(self):
        """Анимирует спиннер"""
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
        """Останавливает анимацию спиннера"""
        self.running = False
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
                self._after_id = None
            except:
                pass
        self.configure(text="✅")


# ===================================================================
# 13. ОСНОВНОЙ КЛАСС ПРИЛОЖЕНИЯ
# ===================================================================

class LauncherApp(ctk.CTk):
    instance = None

    def __init__(self):
        global MINECRAFT_DIR, GAME_DIR, ACCOUNTS_FILE, PROFILES_FILE, LAUNCHER_PROFILES_FILE

        super().__init__()
        LauncherApp.instance = self

        print(f"📁 ПУТЬ К НАСТРОЙКАМ: {SETTINGS_FILE}")
        print(f"📁 ПАПКА ИГРЫ: {MINECRAFT_DIR}")

        self.settings = load_launcher_settings()
        self.stats = load_stats()

        # УВЕЛИЧИВАЕМ СЧЕТЧИК ЗАПУСКОВ ПРИ КАЖДОМ ЗАПУСКЕ
        # УВЕЛИЧИВАЕМ СЧЕТЧИК ЗАПУСКОВ ПРИ КАЖДОМ ЗАПУСКЕ
        launch_count = self.settings.get("launch_count", 0) + 1

        # ЕСЛИ ДОСТИГЛИ 5 - ОБНУЛЯЕМ И ПОКАЗЫВАЕМ ОКНО ПОДДЕРЖКИ
        if launch_count >= 5:
            launch_count = 0
            self.settings["support_shown_5"] = False  # СБРАСЫВАЕМ ФЛАГ
            save_launcher_settings(self.settings)
            # ПОКАЗЫВАЕМ ОКНО ПОДДЕРЖКИ
            self.after(100, self.show_support_dialog)

        self.settings["launch_count"] = launch_count
        save_launcher_settings(self.settings)

        self.apply_theme()

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
        self._last_j_press = 0

        ensure_game_folder_structure()

        self.create_widgets()
        self.refresh_accounts()
        self.refresh_accounts_listbox()
        self.refresh_mods_list()
        self.scan_and_update_versions()
        self.load_available_versions()
        self.refresh_resourcepacks()
        self.refresh_skins()

        self.restore_last_selection()

        self.log(f"📁 Папка игры: {MINECRAFT_DIR}")
        self.log(f"📊 Запусков игры: {self.stats.get('launches', 0)}")
        self.log(f"📊 Запуск лаунчера #{launch_count if launch_count > 0 else 'обнулен'}")

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.start_idle_timer()

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
        """Форматирует размер файла"""
        for unit in ['Б', 'КБ', 'МБ', 'ГБ']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} ТБ"

    def get_folder_size(self, folder_path):
        """Вычисляет размер папки рекурсивно"""
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
    # МЕТОДЫ ДЛЯ ТАЙМЕРОВ И СТАТИСТИКИ
    # =================================================================

    def start_idle_timer(self):
        """Запускает таймер бездействия для обновления статистики"""
        self.after(1000, self.update_stats_display)

    def update_stats_display(self):
        """Обновляет отображение статистики"""
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
            history_text = "\n".join([
                f"  • {h.get('time', '')[:16]} - {h.get('version', 'unknown')}"
                for h in history[-10:]
            ])

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

    # =================================================================
    # МЕТОДЫ ДЛЯ СКАЧИВАНИЯ С ПРОГРЕССОМ
    # =================================================================

    def show_download_panel(self, show=True):
        """Показывает или скрывает панель скачивания"""
        try:
            if hasattr(self, 'download_panel'):
                if show:
                    self.download_panel.grid()
                else:
                    self.download_panel.grid_remove()
        except:
            pass

    def download_with_progress(self, url, filepath, description="Скачивание"):
        """Скачивает файл с отображением прогресса"""
        try:
            # Показываем панель
            self.after(0, lambda: self.show_download_panel(True))

            self.log(f"📥 {description}...")

            # Показываем спиннер
            if hasattr(self, 'download_spinner'):
                self.download_spinner.start()

            # Обновляем статус
            if hasattr(self, 'download_status_label'):
                self.download_status_label.configure(text=f"⏳ {description}...", text_color="#f9e2af")

            # Активируем прогресс-бар
            if hasattr(self, 'download_progressbar'):
                self.download_progressbar.start_animation()

            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            block_size = 8192

            # Создаем папку если её нет
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=block_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = int((downloaded / total_size) * 100)
                            # Обновляем прогресс-бар
                            if hasattr(self, 'download_progressbar'):
                                self.download_progressbar.set_progress(percent)
                            # Логируем каждые 10%
                            if percent % 10 == 0:
                                self.log(f"📊 {description}: {percent}%")

            # Завершаем
            if hasattr(self, 'download_progressbar'):
                self.download_progressbar.stop_animation()
                self.download_progressbar.set(1.0)
                self.download_progressbar.configure(progress_color="#a6e3a1")

            if hasattr(self, 'download_spinner'):
                self.download_spinner.stop()

            if hasattr(self, 'download_status_label'):
                self.download_status_label.configure(text=f"✅ {description} завершено!", text_color="#a6e3a1")

            self.log(f"✅ {description} завершено!")

            # Скрываем панель через 2 секунды
            self.after(2000, lambda: self.show_download_panel(False))
            return True

        except Exception as e:
            self.log(f"❌ Ошибка скачивания: {e}")
            if hasattr(self, 'download_spinner'):
                self.download_spinner.stop()
            if hasattr(self, 'download_status_label'):
                self.download_status_label.configure(text=f"❌ Ошибка: {e}", text_color="#f38ba8")
            if hasattr(self, 'download_progressbar'):
                self.download_progressbar.stop_animation()
                self.download_progressbar.set(0.3)
                self.download_progressbar.configure(progress_color="#f38ba8")

            # Скрываем панель через 3 секунды
            self.after(3000, lambda: self.show_download_panel(False))
            return False

    # =================================================================
    # МЕТОДЫ ДЛЯ ПЕРЕКЛЮЧЕНИЯ ТЕМЫ
    # =================================================================

    def toggle_theme(self):
        """Переключает тему между темной и светлой"""
        current = ctk.get_appearance_mode()
        new_theme = "Light" if current == "Dark" else "Dark"
        ctk.set_appearance_mode(new_theme)
        self.settings["theme"] = new_theme.lower()
        save_launcher_settings(self.settings)

        # Обновляем текст кнопок
        theme_text = "🌙 Тёмная" if new_theme == "Dark" else "☀️ Светлая"
        if hasattr(self, 'theme_btn'):
            self.theme_btn.configure(text=theme_text)
        if hasattr(self, 'theme_btn_settings'):
            self.theme_btn_settings.configure(text=theme_text)

        self.log(f"🌓 Переключено на {new_theme} тему")

    def apply_theme(self):
        """Применяет сохраненную тему"""
        theme = self.settings.get("theme", "dark")
        ctk.set_appearance_mode("Dark" if theme == "dark" else "Light")
        self.configure(fg_color="#1e1e2e" if theme == "dark" else "#f0f0f0")

    # =================================================================
    # МЕТОДЫ ДЛЯ ОКНА ПОДДЕРЖКИ
    # =================================================================

    def show_support_dialog(self):
        """Показывает диалог поддержки автора (при 5-м запуске)"""
        # Проверяем, не показывали ли уже окно
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

        dialog.update_idletasks()
        width = dialog.winfo_width()
        height = dialog.winfo_height()
        x = (dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (dialog.winfo_screenheight() // 2) - (height // 2)
        dialog.geometry(f"{width}x{height}+{x}+{y}")

        # Основной фрейм с отступами
        main_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Иконка
        icon_label = ctk.CTkLabel(
            main_frame,
            text="🌟",
            font=ctk.CTkFont(size=70)
        )
        icon_label.pack(pady=(10, 5))

        # Заголовок
        header = ctk.CTkLabel(
            main_frame,
            text="FOR MEEE",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#89b4fa"
        )
        header.pack(pady=(0, 5))

        sub_header = ctk.CTkLabel(
            main_frame,
            text="lolipop",
            font=ctk.CTkFont(size=15),
            text_color="#f9e2af"
        )
        sub_header.pack(pady=(0, 15))

        # Разделитель
        ctk.CTkFrame(main_frame, height=2, fg_color="#89b4fa").pack(fill="x", pady=(0, 15))

        # Текст
        msg = """Если тебе нравится 67Launcher задонать пжж и рассмотри возможность 
небольшого доната.

💝 Даже 50 рублей помогут продолжить разработку!(наверное)

❤️ Спасибо, что пользуешься 67Launcher!"""

        text_label = ctk.CTkLabel(
            main_frame,
            text=msg,
            font=ctk.CTkFont(size=14),
            justify="center",
            wraplength=420
        )
        text_label.pack(pady=(0, 20))

        # Разделитель
        ctk.CTkFrame(main_frame, height=2, fg_color="#89b4fa").pack(fill="x", pady=(0, 15))

        # Кнопки
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(pady=(10, 5))

        def open_donate():
            webbrowser.open("https://www.donationalerts.com/r/ionux")
            dialog.destroy()
            messagebox.showinfo(
                "Спасибо! 🙏",
                "Спасибо за поддержку! ❤️\n\nКаждый донат помогает делать лаунчер лучше!(надеюсь)"
            )

        def open_github():
            webbrowser.open("https://github.com/KotiPlayYT/")

        def close_dialog():
            dialog.destroy()

        donate_btn = ctk.CTkButton(
            btn_frame,
            text="💝 Поддержать",
            command=open_donate,
            width=170,
            height=50,
            fg_color="#ff6b6b",
            hover_color="#ee5a24",
            font=ctk.CTkFont(size=15, weight="bold")
        )
        donate_btn.grid(row=0, column=0, padx=10, pady=5)

        github_btn = ctk.CTkButton(
            btn_frame,
            text="⭐ GitHub",
            command=open_github,
            width=150,
            height=50,
            fg_color="#333333",
            hover_color="#555555",
            font=ctk.CTkFont(size=15)
        )
        github_btn.grid(row=0, column=1, padx=10, pady=5)

        close_btn = ctk.CTkButton(
            main_frame,
            text="Пропустить",
            command=close_dialog,
            width=120,
            height=35,
            fg_color="#f38ba8",
            hover_color="#e64553",
            font=ctk.CTkFont(size=13)
        )
        close_btn.pack(pady=(10, 5))

    # =================================================================
    # МЕТОДЫ ДЛЯ УСТАНОВКИ МОДА СКИНОВ
    # =================================================================

    def install_custom_skin_loader(self):
        """Устанавливает мод CustomSkinLoader (Universal версия) в папку .minecraft"""
        try:
            mods_path = os.path.join(MINECRAFT_DIR, "mods")
            os.makedirs(mods_path, exist_ok=True)

            for file in os.listdir(mods_path):
                if "CustomSkinLoader" in file or "SkinLoader" in file:
                    self.log("✅ CustomSkinLoader уже установлен")
                    messagebox.showinfo("Информация", "Мод CustomSkinLoader уже установлен!")
                    return True

            self.log("📥 Скачивание CustomSkinLoader Universal...")

            mod_url = "https://github.com/xfl03/MCCustomSkinLoader/releases/download/v15.0.1/CustomSkinLoader_Universal-15.0.1.jar"
            mod_file = os.path.join(mods_path, "CustomSkinLoader.jar")

            # Используем метод с прогрессом
            success = self.download_with_progress(mod_url, mod_file, "Скачивание CustomSkinLoader")

            if not success:
                return False

            self.log("✅ CustomSkinLoader Universal установлен!")

            config_path = os.path.join(MINECRAFT_DIR, "config", "CustomSkinLoader")
            os.makedirs(config_path, exist_ok=True)

            config_file = os.path.join(config_path, "skinloader.json")
            config_data = {
                "enable": True,
                "loadlist": [
                    {
                        "name": "LocalSkin",
                        "type": "LocalSkin",
                        "skin": "LocalSkin/%s.png"
                    },
                    {
                        "name": "Mojang",
                        "type": "MojangAPI"
                    }
                ]
            }

            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            self.log("✅ Конфиг CustomSkinLoader создан")

            skins_local_path = os.path.join(MINECRAFT_DIR, "CustomSkinLoader", "LocalSkin")
            os.makedirs(skins_local_path, exist_ok=True)
            self.log(f"📁 Папка для скинов: {skins_local_path}")

            messagebox.showinfo(
                "Успешно",
                "Мод CustomSkinLoader Universal успешно установлен!\n\n"
                "📁 Скины нужно помещать в папку:\n"
                f"{skins_local_path}\n\n"
                "💡 Скин должен называться: имя_пользователя.png\n"
                "Например: Steve.png\n\n"
                "⚠️ После установки скина перезапустите игру!"
            )
            return True

        except Exception as e:
            self.log(f"❌ Ошибка установки CustomSkinLoader: {e}")
            messagebox.showerror(
                "Ошибка",
                f"Не удалось установить CustomSkinLoader.\n\n"
                f"Ошибка: {e}\n\n"
                "Попробуйте скачать вручную:\n"
                "https://github.com/xfl03/MCCustomSkinLoader/releases\n\n"
                "1. Скачайте CustomSkinLoader_Universal-15.0.1.jar\n"
                "2. Поместите в папку mods\n"
                "3. Перезапустите игру"
            )
            return False

    def install_skin_loader_for_fabric(self):
        """Устанавливает CustomSkinLoader для Fabric (использует Universal версию)"""
        self.log("🧵 Установка CustomSkinLoader для Fabric...")
        return self.install_custom_skin_loader()

    # =================================================================
    # МЕТОД ДЛЯ УСТАНОВКИ СКИНА
    # =================================================================

    def create_skin_data(self, username, skin_path):
        """Создает данные для скина в папке .minecraft"""
        try:
            skins_local_path = os.path.join(MINECRAFT_DIR, "CustomSkinLoader", "LocalSkin")
            os.makedirs(skins_local_path, exist_ok=True)

            skin_filename = f"{username}.png"
            skin_dest = os.path.join(skins_local_path, skin_filename)
            shutil.copy2(skin_path, skin_dest)
            self.log(f"✅ Скин скопирован: .minecraft/CustomSkinLoader/LocalSkin/{skin_filename}")

            self.log(f"🎨 Скин {skin_filename} успешно установлен для {username}!")
            return True

        except Exception as e:
            self.log(f"❌ Ошибка установки скина: {e}")
            return False

    def open_mods_folder(self):
        """Открывает папку с модами в .minecraft"""
        mods_path = os.path.join(MINECRAFT_DIR, "mods")
        os.makedirs(mods_path, exist_ok=True)
        os.startfile(mods_path)
        self.log(f"📂 Открыта папка mods")
        messagebox.showinfo(
            "Установка мода вручную",
            "1. Скачайте CustomSkinLoader с:\n"
            "https://github.com/xfl03/MCCustomSkinLoader/releases\n\n"
            "2. Скачайте CustomSkinLoader_Universal-15.0.1.jar\n"
            "3. Скопируйте .jar файл в открывшуюся папку mods\n\n"
            "📁 После установки скины кладите в:\n"
            f"{os.path.join(MINECRAFT_DIR, 'CustomSkinLoader', 'LocalSkin')}\n"
            "Имя файла: имя_пользователя.png"
        )

    # =================================================================
    # МЕТОДЫ ВКЛАДКИ АККАУНТОВ
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
                messagebox.showwarning("Ошибка", "Имя не может быть пустым")
                return
            success, msg = add_account(username)
            if success:
                self.refresh_accounts()
                self.refresh_accounts_listbox()
                dialog.destroy()
                messagebox.showinfo("Успешно", msg)
            else:
                messagebox.showerror("Ошибка", msg)

        ctk.CTkButton(
            dialog,
            text="Добавить",
            command=confirm,
            fg_color="#a6e3a1",
            hover_color="#7ecb8f",
            text_color="#1e1e2e"
        ).pack(pady=10)

    def delete_selected_account(self):
        selection = self.accounts_listbox.get("1.0", "end").strip()
        if not selection or selection == "Нет аккаунтов":
            messagebox.showwarning("Ошибка", "Нет аккаунтов для удаления")
            return

        username = selection.split("👤")[1].split("(")[0].strip()
        if messagebox.askyesno("Подтверждение", f"Удалить аккаунт '{username}'?"):
            success, msg = delete_account(username)
            if success:
                self.refresh_accounts()
                self.refresh_accounts_listbox()
                messagebox.showinfo("Успешно", msg)
            else:
                messagebox.showerror("Ошибка", msg)

    # =================================================================
    # МЕТОДЫ ВКЛАДКИ МОДОВ
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
            messagebox.showwarning("Ошибка", "Выберите мод для удаления")
            return

        mod_name = self.installed_listbox.get(selection[0])
        if "Моды не установлены" in mod_name:
            return

        mod_name = mod_name.replace("📦 ", "").strip()
        if messagebox.askyesno("Подтверждение", f"Удалить мод '{mod_name}'?"):
            if delete_mod(mod_name):
                self.refresh_mods_list()
                messagebox.showinfo("Успешно", "Мод удалён")
            else:
                messagebox.showerror("Ошибка", "Не удалось удалить мод")

    # =================================================================
    # МЕТОДЫ ВКЛАДКИ РЕСУРСПАКОВ
    # =================================================================

    def read_pack_meta(self, pack_path):
        info = {"description": "Без описания", "pack_format": "неизвестно"}

        try:
            import zipfile
            import json

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

        except Exception as e:
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
                        "is_zip": item.endswith('.zip'),
                        "size": self.format_size(
                            os.path.getsize(item_path) if os.path.isfile(item_path) else self.get_folder_size(
                                item_path)),
                        "modified": datetime.fromtimestamp(os.path.getmtime(item_path)).strftime("%d.%m.%Y %H:%M"),
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
            self.resourcepacks_listbox.insert("end", "Нажмите 'Установить' для добавления")
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
            filetypes=[
                ("ZIP архивы", "*.zip"),
                ("Все файлы", "*.*")
            ]
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
            messagebox.showinfo("Успешно", f"Ресурспак '{filename}' установлен!")
            self.refresh_resourcepacks()
            return True
        except Exception as e:
            self.log(f"❌ Ошибка установки ресурспака: {e}")
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
            messagebox.showinfo("Успешно", f"Ресурспак '{pack_name}' удален!")
            self.refresh_resourcepacks()
            return True
        except Exception as e:
            self.log(f"❌ Ошибка удаления ресурспака: {e}")
            messagebox.showerror("Ошибка", f"Не удалось удалить ресурспак:\n{e}")
            return False

    def show_resourcepack_info(self, pack_name):
        packs_path = os.path.join(MINECRAFT_DIR, "resourcepacks")
        pack_path = os.path.join(packs_path, pack_name)

        if not os.path.exists(pack_path):
            return

        info = self.read_pack_meta(pack_path)

        info_text = f"""
📦 Ресурспак: {pack_name}

📝 Описание: {info.get('description', 'Без описания')}
📋 Формат: {info.get('pack_format', 'неизвестно')}

📁 Путь: {pack_path}
📏 Размер: {self.format_size(os.path.getsize(pack_path) if os.path.isfile(pack_path) else self.get_folder_size(pack_path))}
🕐 Изменен: {datetime.fromtimestamp(os.path.getmtime(pack_path)).strftime("%d.%m.%Y %H:%M:%S")}

📂 Тип: {"ZIP архив" if pack_name.endswith('.zip') else "Папка"}
        """

        self.resourcepack_info.configure(state="normal")
        self.resourcepack_info.delete("1.0", "end")
        self.resourcepack_info.insert("1.0", info_text)
        self.resourcepack_info.configure(state="disabled")

    def delete_selected_resourcepack(self):
        selection = self.resourcepacks_listbox.curselection()
        if not selection:
            messagebox.showwarning("Ошибка", "Выберите ресурспак для удаления")
            return

        selected_text = self.resourcepacks_listbox.get(selection[0])
        if "📭" in selected_text or "Нажмите" in selected_text:
            return

        name = selected_text.split("📦 ")[1].split(" -")[0].strip()
        self.delete_resourcepack(name)

    def on_resourcepack_double_click(self, event):
        selection = self.resourcepacks_listbox.curselection()
        if not selection:
            return

        selected_text = self.resourcepacks_listbox.get(selection[0])
        if "📭" in selected_text or "Нажмите" in selected_text:
            return

        name = selected_text.split("📦 ")[1].split(" -")[0].strip()
        self.show_resourcepack_info(name)

    def open_resourcepacks_folder(self):
        packs_path = os.path.join(MINECRAFT_DIR, "resourcepacks")
        if not os.path.exists(packs_path):
            os.makedirs(packs_path, exist_ok=True)
        os.startfile(packs_path)

    # =================================================================
    # МЕТОДЫ ВКЛАДКИ СКИНОВ
    # =================================================================

    def get_skins_list(self):
        """Получает список установленных скинов"""
        skins_path = get_skins_folder()
        skins = []

        if os.path.exists(skins_path):
            for file in os.listdir(skins_path):
                if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                    file_path = os.path.join(skins_path, file)
                    skins.append({
                        "name": file,
                        "path": file_path,
                        "size": self.format_size(os.path.getsize(file_path)),
                        "modified": datetime.fromtimestamp(os.path.getmtime(file_path)).strftime("%d.%m.%Y %H:%M")
                    })

        return sorted(skins, key=lambda x: x['name'].lower())

    def refresh_skins(self):
        """Обновляет список скинов в интерфейсе"""
        skins = self.get_skins_list()

        self.skins_listbox.delete(0, "end")

        if not skins:
            self.skins_listbox.insert("end", "📭 Скины не установлены")
            self.skins_listbox.insert("end", "Нажмите 'Добавить скин' для импорта")
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
        """Импортирует скин из файла"""
        file_path = filedialog.askopenfilename(
            title="Выберите скин (PNG или JPG)",
            filetypes=[
                ("PNG изображения", "*.png"),
                ("JPG изображения", "*.jpg"),
                ("JPEG изображения", "*.jpeg"),
                ("Все файлы", "*.*")
            ]
        )

        if not file_path:
            return False

        skins_path = get_skins_folder()
        filename = os.path.basename(file_path)
        dest_path = os.path.join(skins_path, filename)

        if os.path.exists(dest_path):
            if not messagebox.askyesno(
                    "Файл существует",
                    f"Скин '{filename}' уже существует.\n\nЗаменить?"
            ):
                return False

        try:
            shutil.copy2(file_path, dest_path)
            self.log(f"✅ Скин импортирован: {filename}")
            messagebox.showinfo("Успешно", f"Скин '{filename}' импортирован!")
            self.refresh_skins()
            return True
        except Exception as e:
            self.log(f"❌ Ошибка импорта скина: {e}")
            messagebox.showerror("Ошибка", f"Не удалось импортировать скин:\n{e}")
            return False

    def delete_skin(self, skin_name):
        """Удаляет скин"""
        if not messagebox.askyesno("Подтверждение", f"Удалить скин '{skin_name}'?"):
            return False

        skins_path = get_skins_folder()
        skin_path = os.path.join(skins_path, skin_name)

        try:
            os.remove(skin_path)
            self.log(f"🗑️ Скин удален: {skin_name}")
            messagebox.showinfo("Успешно", f"Скин '{skin_name}' удален!")
            self.refresh_skins()
            return True
        except Exception as e:
            self.log(f"❌ Ошибка удаления скина: {e}")
            messagebox.showerror("Ошибка", f"Не удалось удалить скин:\n{e}")
            return False

    def delete_selected_skin(self):
        """Удаляет выбранный скин"""
        selection = self.skins_listbox.curselection()
        if not selection:
            messagebox.showwarning("Ошибка", "Выберите скин для удаления")
            return

        selected_text = self.skins_listbox.get(selection[0])
        if "📭" in selected_text or "Нажмите" in selected_text:
            return

        name = selected_text.split("🎨 ")[1].split(" (")[0].strip()
        self.delete_skin(name)

    def preview_skin(self):
        """Показывает превью выбранного скина"""
        skin_name = self.skin_combo.get()
        if not skin_name or skin_name == "Нет скинов" or skin_name == "Загрузка...":
            messagebox.showinfo("Информация", "Скин не выбран")
            return

        skins_path = get_skins_folder()
        skin_path = os.path.join(skins_path, skin_name)

        if not os.path.exists(skin_path):
            messagebox.showerror("Ошибка", f"Скин '{skin_name}' не найден")
            return

        try:
            from PIL import Image, ImageTk

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
🕐 Изменен: {datetime.fromtimestamp(os.path.getmtime(skin_path)).strftime("%d.%m.%Y %H:%M")}
            """
            info_label = ctk.CTkLabel(
                preview_window,
                text=info_text,
                font=ctk.CTkFont(size=12),
                justify="left"
            )
            info_label.pack(pady=10)

            close_btn = ctk.CTkButton(
                preview_window,
                text="Закрыть",
                command=preview_window.destroy,
                width=100,
                height=35
            )
            close_btn.pack(pady=10)

            def on_close():
                try:
                    os.remove(temp_path)
                except:
                    pass
                preview_window.destroy()

            preview_window.protocol("WM_DELETE_WINDOW", on_close)

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось открыть скин:\n{e}")

    def open_skins_folder(self):
        """Открывает папку со скинами"""
        skins_path = get_skins_folder()
        os.startfile(skins_path)
        self.log(f"📂 Открыта папка скинов")

    def on_skin_double_click(self, event):
        """Обработка двойного клика по скину - показывает превью"""
        selection = self.skins_listbox.curselection()
        if not selection:
            return

        selected_text = self.skins_listbox.get(selection[0])
        if "📭" in selected_text or "Нажмите" in selected_text:
            return

        name = selected_text.split("🎨 ")[1].split(" (")[0].strip()
        self.show_skin_info(name)

    def show_skin_info(self, skin_name):
        """Показывает подробную информацию о скине"""
        skins_path = get_skins_folder()
        skin_path = os.path.join(skins_path, skin_name)

        if not os.path.exists(skin_path):
            return

        info_text = f"""
🎨 Скин: {skin_name}

📁 Путь: {skin_path}
📏 Размер: {self.format_size(os.path.getsize(skin_path))}
🕐 Изменен: {datetime.fromtimestamp(os.path.getmtime(skin_path)).strftime("%d.%m.%Y %H:%M:%S")}

📂 Тип: {skin_name.split('.')[-1].upper()}
💡 Для использования выберите этот скин на вкладке "Игра"
        """

        self.skin_info.configure(state="normal")
        self.skin_info.delete("1.0", "end")
        self.skin_info.insert("1.0", info_text)
        self.skin_info.configure(state="disabled")

    def create_skins_tab(self):
        """Создает вкладку управления скинами с кнопками установки мода"""
        tab = self.tab_view.tab("🎨 Скины")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        header_frame = ctk.CTkFrame(tab, fg_color="transparent")
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=20, pady=(15, 10))

        ctk.CTkLabel(
            header_frame,
            text="🎨 Управление скинами",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(side="left")

        left_frame = ctk.CTkFrame(tab)
        left_frame.grid(row=1, column=0, sticky="nsew", padx=(20, 10), pady=(0, 10))
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            left_frame,
            text="📋 Установленные скины",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(0, 5))

        self.skins_listbox = tk.Listbox(
            left_frame,
            bg="#1a1a2e",
            fg="#cdd6f4",
            selectbackground="#89b4fa",
            selectforeground="#1e1e2e",
            font=("Consolas", 11),
            height=12,
            relief="flat"
        )
        self.skins_listbox.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.skins_listbox.bind("<Double-Button-1>", self.on_skin_double_click)

        btn_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)
        btn_frame.grid_columnconfigure(2, weight=1)
        btn_frame.grid_columnconfigure(3, weight=1)

        import_btn = ctk.CTkButton(
            btn_frame,
            text="📥 Добавить",
            command=self.import_skin,
            fg_color="#a6e3a1",
            hover_color="#7ecb8f",
            text_color="#1e1e2e",
            height=35
        )
        import_btn.grid(row=0, column=0, padx=2)

        preview_btn = ctk.CTkButton(
            btn_frame,
            text="👁️ Превью",
            command=self.preview_skin,
            fg_color="#89b4fa",
            hover_color="#74c7ec",
            height=35
        )
        preview_btn.grid(row=0, column=1, padx=2)

        delete_btn = ctk.CTkButton(
            btn_frame,
            text="🗑️ Удалить",
            command=self.delete_selected_skin,
            fg_color="#f38ba8",
            hover_color="#e64553",
            height=35
        )
        delete_btn.grid(row=0, column=2, padx=2)

        refresh_btn = ctk.CTkButton(
            btn_frame,
            text="🔄 Обновить",
            command=self.refresh_skins,
            fg_color="#f9e2af",
            hover_color="#f5d742",
            text_color="#1e1e2e",
            height=35
        )
        refresh_btn.grid(row=0, column=3, padx=2)

        mod_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        mod_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(10, 0))
        mod_frame.grid_columnconfigure(0, weight=1)
        mod_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            mod_frame,
            text="📦 Установка мода для скинов:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#89b4fa"
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))

        forge_btn = ctk.CTkButton(
            mod_frame,
            text="🔥 Forge",
            command=self.install_custom_skin_loader,
            fg_color="#e67e22",
            hover_color="#d35400",
            text_color="white",
            height=35,
            font=ctk.CTkFont(size=12, weight="bold")
        )
        forge_btn.grid(row=1, column=0, padx=2, sticky="ew")

        fabric_btn = ctk.CTkButton(
            mod_frame,
            text="🧵 Fabric",
            command=self.install_skin_loader_for_fabric,
            fg_color="#2ecc71",
            hover_color="#27ae60",
            text_color="white",
            height=35,
            font=ctk.CTkFont(size=12, weight="bold")
        )
        fabric_btn.grid(row=1, column=1, padx=2, sticky="ew")

        open_mods_btn = ctk.CTkButton(
            mod_frame,
            text="📂 Открыть папку mods",
            command=self.open_mods_folder,
            fg_color="#89b4fa",
            hover_color="#74c7ec",
            height=35,
            font=ctk.CTkFont(size=12)
        )
        open_mods_btn.grid(row=2, column=0, columnspan=2, padx=2, pady=(5, 0), sticky="ew")

        info_label = ctk.CTkLabel(
            left_frame,
            text="💡 CustomSkinLoader - мод для отображения скинов в офлайн режиме\nДля Fabric и Forge",
            font=ctk.CTkFont(size=11),
            text_color="#89b4fa",
            justify="left"
        )
        info_label.grid(row=4, column=0, sticky="w", padx=10, pady=(10, 5))

        right_frame = ctk.CTkFrame(tab)
        right_frame.grid(row=1, column=1, sticky="nsew", padx=(10, 20), pady=(0, 10))
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            right_frame,
            text="ℹ️ Информация о скине",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(0, 5))

        self.skin_info = ctk.CTkTextbox(
            right_frame,
            font=ctk.CTkFont(family="Consolas", size=11),
            height=200
        )
        self.skin_info.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.skin_info.insert("1.0", "Выберите скин для просмотра информации\n\nДвойной клик для просмотра")
        self.skin_info.configure(state="disabled")

        open_folder_btn = ctk.CTkButton(
            right_frame,
            text="📂 Открыть папку со скинами",
            command=self.open_skins_folder,
            fg_color="#f9e2af",
            hover_color="#f5d742",
            text_color="#1e1e2e",
            height=35
        )
        open_folder_btn.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))

        info_label = ctk.CTkLabel(
            right_frame,
            text="💡 Двойной клик для просмотра информации\nПоддерживаются .png, .jpg, .jpeg",
            font=ctk.CTkFont(size=11),
            text_color="#89b4fa",
            justify="left"
        )
        info_label.grid(row=3, column=0, sticky="w", padx=10, pady=(0, 5))

    # =================================================================
    # ТАЙМЕР ИГРЫ
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
            self.start_hygiene_reminder()

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

    # =================================================================
    # НАПОМИНАНИЯ
    # =================================================================

    def get_funny_hygiene_message(self):
        messages = [
            "ТЕБЕ НОРМАС?",
            "ПОВЕРБАНК",
            "... ждет своего часа! Не заставляй его ждать!",
            "Беги быстрее!",
            "💧",
            "🧽 Губка БОБ",
            "🫧 Пена СКИЛЛ",
            "ТИРАНЫ",
            "ОЙ ДА КОНЧНО)",
            "ВЫРУБАЙ!",
            "Я СБРОШУ 250К ТОН ДРОТИЛА",
            "Время!",
            "🫧",
            "ТЫ ЧЕГО",
            "...",
            "?",
            ":Р",
            ":З",
            "ЫЫЫ",
            "Не забудь про ждет! Не разочаровывай её!"
        ]
        return random.choice(messages)

    def start_hygiene_reminder(self):
        if not self.settings.get("hygiene_reminders", True):
            self.log("Напоминания отключены в настройках")
            return

        def reminder_thread():
            INTERVAL = 1500  # 25 минут

            while True:
                if self._closing or not self.timer_running:
                    break

                time.sleep(INTERVAL)

                if self._closing or not self.timer_running:
                    break

                if self.settings.get("hygiene_reminders", True):
                    message = self.get_funny_hygiene_message()
                    self.after(0, lambda msg=message: self.show_hygiene_notification(msg))

        threading.Thread(target=reminder_thread, daemon=True).start()
        self.log("⏰ Напоминания каждые 25 минут запущены!")

    def manual_hygiene_reminder(self):
        if not self.settings.get("hygiene_reminders", True):
            if messagebox.askyesno(
                    "Напоминания отключены",
                    "Напоминания отключены в настройках.\n\nВключить сейчас?"
            ):
                self.settings["hygiene_reminders"] = True
                self.hygiene_reminders_var.set(True)
                save_launcher_settings(self.settings)
                self.log("Напоминания включены")
                self.start_hygiene_reminder()
            return

        message = self.get_funny_hygiene_message()
        self.show_hygiene_notification(message)

    def show_hygiene_notification(self, message):
        dialog = ctk.CTkToplevel(self)
        dialog.title("ам ам")
        dialog.geometry("450x350")
        dialog.resizable(False, False)
        dialog.grab_set()

        dialog.update_idletasks()
        width = dialog.winfo_width()
        height = dialog.winfo_height()
        x = (dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (dialog.winfo_screenheight() // 2) - (height // 2)
        dialog.geometry(f"{width}x{height}+{x}+{y}")

        icon_label = ctk.CTkLabel(
            dialog,
            text="🧼",
            font=ctk.CTkFont(size=70)
        )
        icon_label.pack(pady=(20, 10))

        header = ctk.CTkLabel(
            dialog,
            text="Время покажет",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#89b4fa"
        )
        header.pack(pady=(0, 10))

        time_label = ctk.CTkLabel(
            dialog,
            text=f"🕐 Ты играешь уже: {self.format_time(self.timer_seconds)}",
            font=ctk.CTkFont(size=13),
            text_color="#f9e2af"
        )
        time_label.pack(pady=(0, 10))

        msg_label = ctk.CTkLabel(
            dialog,
            text=message,
            font=ctk.CTkFont(size=14),
            wraplength=380,
            justify="center"
        )
        msg_label.pack(pady=(10, 20), padx=20)

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=(0, 20))

        def go_shower():
            self.log("🚿 Пользователь пошел мыться! Отличное решение!")
            messagebox.showinfo(
                "🌟 Молодец!",
                "\n\nА когда вернешься - игра не не будет тебя ждать"
            )
            dialog.destroy()

        def later():
            self.log("😅 Пользователь отложил...")
            if messagebox.askyesno(
                    "Напомнить позже?",
                    "Хочешь, чтобы я напомнил тебе через 15 минут?"
            ):
                self.log("⏰ Установлено напоминание через 15 минут")
                threading.Thread(target=lambda: self.delayed_reminder(900), daemon=True).start()
            dialog.destroy()

        def never_remind():
            self.log("🚫 Пользователь отключил напоминания ")
            self.settings["hygiene_reminders"] = False
            self.hygiene_reminders_var.set(False)
            save_launcher_settings(self.settings)
            dialog.destroy()
            messagebox.showinfo(
                "🧼 Напоминания отключены",
                "Напоминания е отключены.\n\nТы всегда можешь включить их в настройках или нажать кнопку '🧼 Напомнить ' в любое время."
            )

        shower_btn = ctk.CTkButton(
            btn_frame,
            text="да конечно",
            command=go_shower,
            fg_color="#a6e3a1",
            hover_color="#7ecb8f",
            text_color="#1e1e2e",
            font=ctk.CTkFont(size=14, weight="bold"),
            width=130,
            height=45
        )
        shower_btn.grid(row=0, column=0, padx=5)

        later_btn = ctk.CTkButton(
            btn_frame,
            text="⏰ Позже",
            command=later,
            fg_color="#f9e2af",
            hover_color="#f5d742",
            text_color="#1e1e2e",
            width=100,
            height=45
        )
        later_btn.grid(row=0, column=1, padx=5)

        never_btn = ctk.CTkButton(
            btn_frame,
            text="🔕 Не напоминать",
            command=never_remind,
            fg_color="#f38ba8",
            hover_color="#e64553",
            width=130,
            height=45
        )
        never_btn.grid(row=0, column=2, padx=5)

        try:
            import winsound
            winsound.Beep(1000, 500)
            winsound.Beep(1200, 300)
        except:
            pass

        self.show_system_notification("дядя", message)

    def delayed_reminder(self, delay_seconds):
        time.sleep(delay_seconds)
        if not self._closing and self.settings.get("hygiene_reminders", True):
            self.after(0, lambda: self.show_hygiene_notification("Я же говорил! Время не ждет!"))

    def show_system_notification(self, title, message):
        if sys.platform == "win32":
            try:
                from win10toast import ToastNotifier
                toaster = ToastNotifier()
                toaster.show_toast(title, message, duration=10, threaded=True)
            except:
                pass

    # =================================================================
    # ЗАПУСК ИГРЫ
    # =================================================================

    def launch_game(self):
        if self.is_launching:
            return

        username = self.account_combo.get()
        if username == "Нет аккаунтов" or not username:
            messagebox.showwarning("Ошибка", "Сначала создайте аккаунт")
            return

        version = self.version_combo.get()
        if version == "Нет версий" or not version:
            messagebox.showwarning("Ошибка", "Сначала установите версию Minecraft")
            return

        ram = self.ram_var.get()

        skin_name = self.skin_combo.get()
        skin_path = None
        if skin_name and skin_name != "Нет скинов" and skin_name != "Загрузка...":
            skin_path = os.path.join(get_skins_folder(), skin_name)
            if not os.path.exists(skin_path):
                skin_path = None

        self.is_launching = True
        self.launch_btn.configure(state="disabled", text="⏳ ЗАПУСК...")
        self.launch_progressbar.start_animation()
        self.launch_status_label.configure(text="⏳ Запуск Minecraft...", text_color="#f9e2af")
        self.log(f"🚀 Запуск: {version} от {username} с памятью {ram}")
        if skin_path:
            self.log(f"🎨 Используется скин: {skin_name}")
        self.update_idletasks()

        def do_launch():
            error_message = None
            success = False

            try:
                java_path = get_java_for_version(version)
                self.log(f"☕ Java: {java_path}")

                java_ver = get_java_version(java_path)
                self.log(f"☕ Java версия: {java_ver}")

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
                    self.log(f"🎨 Скин {skin_name} установлен для {username}")

                self.log("⏳ Запуск через minecraft_launcher_lib...")

                # ========== ИСПРАВЛЕННЫЙ КОД ЗАПУСКА ==========
                # Получаем команду с options
                command = mll.command.get_minecraft_command(
                    version=version,
                    minecraft_directory=MINECRAFT_DIR,
                    options=mll.utils.generate_test_options()
                )

                # Очищаем старые аргументы
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

                # Добавляем правильные аргументы
                command.extend(["--username", username])
                command.extend(["--uuid", "00000000-0000-0000-0000-000000000000"])
                command.extend(["--accessToken", "0"])
                command.extend(["--userType", "mojang"])

                if java_path != "java":
                    command.insert(0, java_path)

                self.log(f"📋 Команда: {' '.join(command[:8])}...")

                if sys.platform == "win32":
                    self.minecraft_process = subprocess.Popen(
                        command,
                        cwd=MINECRAFT_DIR,
                        creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
                    )
                else:
                    self.minecraft_process = subprocess.Popen(
                        command,
                        cwd=MINECRAFT_DIR,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        bufsize=1
                    )

                def read_output(pipe, name):
                    try:
                        for line in iter(pipe.readline, ''):
                            if line:
                                line = line.strip()
                                if line:
                                    self.log(f"[{name}] {line}")
                    except:
                        pass

                threading.Thread(target=read_output, args=(self.minecraft_process.stdout, "Minecraft"),
                                 daemon=True).start()
                threading.Thread(target=read_output, args=(self.minecraft_process.stderr, "ERROR"), daemon=True).start()

                self.log("✅ Процесс запущен!")
                success = True
                error_message = "Игра запущена!"

                update_stats()
                self.stats = load_stats()
                self.start_game_timer()

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
            self.launch_status_label.configure(text="✅ Игра запущена!", text_color="#a6e3a1")
            self.launch_progressbar.set(1.0)
            self.launch_progressbar.configure(progress_color="#a6e3a1")
            self.log("✅ Игра успешно запущена")
            self.save_current_selection()
            self.stats = load_stats()
            self.update_info_display()
            self.update_subtitle()
        else:
            self.launch_status_label.configure(text="❌ Ошибка запуска", text_color="#f38ba8")
            self.launch_progressbar.set(0.3)
            self.launch_progressbar.configure(progress_color="#f38ba8")
            self.log(f"❌ Ошибка запуска: {message}")
            self.stop_game_timer()

            java_ver = '17' if '1.20' in self.version_combo.get() else '8'
            messagebox.showerror(
                "Ошибка запуска",
                f"Не удалось запустить игру.\n\nОшибка: {message}\n\nУбедитесь, что установлена Java {java_ver}."
            )

    # =================================================================
    # УСТАНОВКА КЛИЕНТОВ
    # =================================================================

    def install_vanilla(self, version):
        try:
            is_snapshot = "snapshot" in version.lower() or "pre" in version.lower() or "rc" in version.lower()

            if is_snapshot:
                self.log(f"⚠️ Устанавливается снапшот: {version}")
                self.install_status_label.configure(text="⚠️ Устанавливается снапшот!")
                self.update_idletasks()

            self.log(f"📦 Установка Vanilla {version}...")
            self.install_status_label.configure(text="Установка Vanilla...")
            self.update_idletasks()

            mll.install.install_minecraft_version(version, MINECRAFT_DIR, mll_callback)
            self.log(f"✅ Vanilla {version} установлен!")

            version_name = f"Vanilla {version}"
            if is_snapshot:
                version_name = f"🔬 Snapshot {version}"

            create_profile(version, version_name)
            return True
        except Exception as e:
            self.log(f"❌ Ошибка: {e}")
            return False

    def install_fabric(self, version):
        try:
            self.log(f"📦 Установка Fabric {version}...")
            self.install_status_label.configure(text="Загрузка Fabric...")
            self.update_idletasks()

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    self.log(f"🔄 Попытка {attempt + 1} из {max_retries}")
                    mll.fabric.install_fabric(version, MINECRAFT_DIR, callback=mll_callback)
                    break
                except Exception as e:
                    self.log(f"⚠️ Ошибка попытки {attempt + 1}: {e}")
                    if attempt == max_retries - 1:
                        raise
                    time.sleep(2)

            self.log(f"✅ Fabric {version} установлен!")
            self.install_status_label.configure(text="✅ Fabric установлен!")
            self.update_idletasks()

            installed = mll.utils.get_installed_versions(MINECRAFT_DIR)
            fabric_versions = [v for v in installed if "fabric" in v["id"].lower()]
            if fabric_versions:
                fabric_id = fabric_versions[-1]["id"]
                create_profile(fabric_id, f"Fabric {version}")
                self.log(f"✅ Профиль создан для: {fabric_id}")
            else:
                fabric_id = f"fabric-loader-0.14.22-{version}"
                create_profile(fabric_id, f"Fabric {version}")

            self.scan_and_update_versions()
            return True

        except Exception as e:
            self.log(f"❌ Ошибка установки Fabric: {e}")
            return False

    def install_forge(self, version):
        try:
            self.log(f"📦 Установка Forge {version}...")

            self.log(f"📦 Шаг 1/2: Установка оригинальной версии {version}...")
            self.install_status_label.configure(text="Установка Vanilla...")
            self.update_idletasks()

            mll.install.install_minecraft_version(version, MINECRAFT_DIR, mll_callback)

            self.log(f"📦 Шаг 2/2: Установка Forge...")
            self.install_status_label.configure(text="Установка Forge...")
            self.update_idletasks()

            forge_installed = False

            if hasattr(mll.forge, 'install_forge'):
                try:
                    self.log("🔧 Способ 1: mll.forge.install_forge")
                    mll.forge.install_forge(version, MINECRAFT_DIR, mll_callback)
                    forge_installed = True
                except Exception as e:
                    self.log(f"⚠️ Способ 1 не сработал: {e}")

            if not forge_installed and hasattr(mll.install, 'install_forge'):
                try:
                    self.log("🔧 Способ 2: mll.install.install_forge")
                    mll.install.install_forge(version, MINECRAFT_DIR, mll_callback)
                    forge_installed = True
                except Exception as e:
                    self.log(f"⚠️ Способ 2 не сработал: {e}")

            if not forge_installed and hasattr(mll.forge, 'install'):
                try:
                    self.log("🔧 Способ 3: mll.forge.install")
                    mll.forge.install(version, MINECRAFT_DIR, mll_callback)
                    forge_installed = True
                except Exception as e:
                    self.log(f"⚠️ Способ 3 не сработал: {e}")

            if not forge_installed:
                self.log("🔧 Способ 4: Ручная установка через официальный установщик")
                forge_installed = self.install_forge_manual(version)

            if not forge_installed:
                raise Exception("Не удалось установить Forge ни одним способом")

            self.log(f"✅ Forge {version} установлен!")
            self.install_status_label.configure(text="✅ Forge установлен!")
            self.update_idletasks()

            installed = mll.utils.get_installed_versions(MINECRAFT_DIR)
            forge_versions = [v for v in installed if "forge" in v["id"].lower()]
            if forge_versions:
                forge_id = forge_versions[-1]["id"]
                create_profile(forge_id, f"Forge {version}")
                self.log(f"✅ Профиль создан для: {forge_id}")
            else:
                forge_id = f"forge-{version}"
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
            cmd = [
                java_path,
                "-jar",
                installer_path,
                "--installClient",
                MINECRAFT_DIR
            ]

            process = subprocess.Popen(
                cmd,
                cwd=MINECRAFT_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

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

            self.log(f"📦 Установка OptiFine {version} из файла...")
            self.install_status_label.configure(text="Установка OptiFine...")
            self.update_idletasks()

            self.log(f"📦 Шаг 1/2: Установка оригинальной версии {version}...")
            self.install_status_label.configure(text="Установка Vanilla...")
            self.update_idletasks()

            mll.install.install_minecraft_version(version, MINECRAFT_DIR, mll_callback)

            self.log(f"📦 Шаг 2/2: Установка OptiFine...")
            self.install_status_label.configure(text="Установка OptiFine...")
            self.update_idletasks()

            mll.optifine.install_optifine(self.selected_installer_path, MINECRAFT_DIR, mll_callback)

            self.log(f"✅ OptiFine {version} установлен!")
            self.install_status_label.configure(text="✅ OptiFine установлен!")
            self.update_idletasks()

            installed = mll.utils.get_installed_versions(MINECRAFT_DIR)
            optifine_versions = [v for v in installed if "optifine" in v["id"].lower() or "of" in v["id"].lower()]
            if optifine_versions:
                optifine_id = optifine_versions[-1]["id"]
                create_profile(optifine_id, f"OptiFine {version}")
                self.log(f"✅ Профиль создан для: {optifine_id}")
            else:
                optifine_id = f"OptiFine_{version}"
                create_profile(optifine_id, f"OptiFine {version}")

            self.scan_and_update_versions()
            self.selected_installer_path = None
            self.install_file_label.configure(text="❌ Файл не выбран (только для OptiFine)", text_color="#f38ba8")
            return True

        except Exception as e:
            self.log(f"❌ Ошибка установки OptiFine: {e}")
            return False

    def install_selected_client(self):
        install_type = self.install_type_var.get()
        version = self.install_version_entry.get().strip()

        if not version:
            messagebox.showwarning("Ошибка", "Введите версию Minecraft")
            return

        if install_type == "optifine":
            if not hasattr(self, 'selected_installer_path') or not self.selected_installer_path:
                messagebox.showwarning("Ошибка", "Сначала выберите файл установщика OptiFine")
                return

            if self.selected_installer_path.lower().endswith('.exe'):
                messagebox.showwarning(
                    "Ошибка",
                    "Для установки OptiFine используйте .jar версию установщика!\nСкачайте установщик (.jar) с официального сайта."
                )
                return

        self.log(f"📦 Установка {install_type} {version}")
        self.install_btn.configure(state="disabled", text="⏳ УСТАНОВКА...")
        self.install_progressbar.start_animation()
        self.install_status_label.configure(text="Подготовка...", text_color="#f9e2af")
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

            self.after(0, lambda: self.install_btn.configure(state="normal", text="📥 УСТАНОВИТЬ"))
            self.after(0, lambda: self.install_progressbar.stop_animation())

            if success:
                self.log(f"✅ {install_type.capitalize()} {version} установлен!")
                self.install_progressbar.set(1.0)
                self.install_progressbar.configure(progress_color="#a6e3a1")
                self.install_status_label.configure(
                    text=f"✅ {install_type.capitalize()} {version} установлен!",
                    text_color="#a6e3a1"
                )
                self.scan_and_update_versions()
                messagebox.showinfo("Успешно", f"{install_type.capitalize()} {version} успешно установлен!")
            else:
                self.log(f"❌ Ошибка установки {install_type}")
                self.install_progressbar.set(0.3)
                self.install_progressbar.configure(progress_color="#f38ba8")
                self.install_status_label.configure(
                    text=f"❌ Ошибка установки {install_type}",
                    text_color="#f38ba8"
                )
                messagebox.showerror("Ошибка", f"Не удалось установить {install_type} {version}")

            cleanup_forge_temp()

        threading.Thread(target=do_install, daemon=True).start()

    # =================================================================
    # КОНСОЛЬ И ЛОГИ
    # =================================================================

    def log(self, message):
        try:
            if hasattr(self, 'console_text') and self.console_text:
                timestamp = time.strftime("%H:%M:%S")
                self.console_text.insert("end", f"[{timestamp}] {message}\n")
                self.console_text.see("end")
        except:
            print(f"LOG: {message}")

    def clear_console(self):
        self.console_text.delete("1.0", "end")
        self.console_text.insert("1.0", "[00:00:00] Консоль очищена\n")

    # =================================================================
    # МЕТОДЫ ДЛЯ ИНТЕРФЕЙСА
    # =================================================================

    def create_widgets(self):
        """Создает все виджеты интерфейса"""
        # Основной контейнер
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(1, weight=1)

        # Верхняя панель с заголовком и кнопкой темы
        top_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        top_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        top_frame.grid_columnconfigure(0, weight=1)

        title_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            title_frame,
            text="⚡ 67Launcher",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color="#89b4fa"
        ).pack(side="left")

        # Отображаем счетчик запусков (обнулен если 0)
        launch_display = self.settings.get('launch_count', 0)
        if launch_display == 0:
            launch_text = "обнулен"
        else:
            launch_text = str(launch_display)

        self.subtitle_label = ctk.CTkLabel(
            title_frame,
            text=f"📁 {MINECRAFT_DIR} | Запуск #{launch_text}",
            font=ctk.CTkFont(size=11),
            text_color="#a6a6a6"
        )
        self.subtitle_label.pack(side="left", padx=(10, 0))

        # Кнопка переключения темы
        self.theme_btn = ctk.CTkButton(
            top_frame,
            text="🌙 Тёмная" if ctk.get_appearance_mode() == "Dark" else "☀️ Светлая",
            command=self.toggle_theme,
            width=120,
            height=30,
            fg_color="#89b4fa",
            hover_color="#74c7ec",
            font=ctk.CTkFont(size=12)
        )
        self.theme_btn.grid(row=0, column=1, sticky="e", padx=(10, 0))

        # Вкладки
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

        # Панель скачивания
        self.create_download_panel()

        # Консоль
        self.create_console()

    def create_mods_tab(self):
        """Создает вкладку модов с поиском на Modrinth"""
        tab = self.tab_view.tab("📦 Моды")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        # ЛЕВАЯ ПАНЕЛЬ - ПОИСК И УСТАНОВКА МОДОВ
        left_frame = ctk.CTkFrame(tab)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(20, 10), pady=20)
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(4, weight=1)

        ctk.CTkLabel(
            left_frame,
            text="🔍 Поиск модов на Modrinth",
            font=ctk.CTkFont(size=18, weight="bold")
        ).grid(row=0, column=0, pady=(0, 10))

        # Версия Minecraft
        ctk.CTkLabel(left_frame, text="🎮 Версия Minecraft:", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=1, column=0, sticky="w", padx=10, pady=(5, 2)
        )
        self.mod_version_entry = ctk.CTkEntry(
            left_frame,
            placeholder_text="1.20.4",
            height=32,
            width=200
        )
        self.mod_version_entry.insert(0, "1.20.1")
        self.mod_version_entry.grid(row=2, column=0, sticky="w", padx=10, pady=(0, 8))

        # Загрузчик
        ctk.CTkLabel(left_frame, text="🔧 Загрузчик:", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=3, column=0, sticky="w", padx=10, pady=(0, 2)
        )

        loader_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        loader_frame.grid(row=4, column=0, sticky="w", padx=10, pady=(0, 8))

        self.mod_loader_var = ctk.StringVar(value="fabric")
        loaders = [
            ("🧵 Fabric", "fabric"),
            ("🔥 Forge", "forge"),
            ("🧶 Quilt", "quilt")
        ]

        for i, (text, value) in enumerate(loaders):
            rb = ctk.CTkRadioButton(
                loader_frame,
                text=text,
                variable=self.mod_loader_var,
                value=value
            )
            rb.grid(row=0, column=i, padx=(0, 15))

        # Поиск
        ctk.CTkLabel(left_frame, text="🔍 Название мода:", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=5, column=0, sticky="w", padx=10, pady=(0, 2)
        )

        search_row = ctk.CTkFrame(left_frame, fg_color="transparent")
        search_row.grid(row=6, column=0, sticky="ew", padx=10, pady=(0, 8))
        search_row.grid_columnconfigure(0, weight=1)

        self.mod_search_entry = ctk.CTkEntry(
            search_row,
            placeholder_text="Введите название мода...",
            height=32
        )
        self.mod_search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.mod_search_entry.bind("<Return>", lambda e: self.search_mods())

        search_btn = ctk.CTkButton(
            search_row,
            text="🔍 Искать",
            command=self.search_mods,
            width=100,
            height=32,
            fg_color="#89b4fa",
            hover_color="#74c7ec"
        )
        search_btn.grid(row=0, column=1)

        # Результаты поиска
        ctk.CTkLabel(left_frame, text="📋 Результаты поиска:", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=7, column=0, sticky="w", padx=10, pady=(5, 2)
        )

        self.results_listbox = tk.Listbox(
            left_frame,
            bg="#1a1a2e",
            fg="#cdd6f4",
            selectbackground="#89b4fa",
            selectforeground="#1e1e2e",
            font=("Consolas", 11),
            height=10,
            relief="flat"
        )
        self.results_listbox.grid(row=8, column=0, sticky="nsew", padx=10, pady=(0, 8))
        self.results_listbox.bind("<<ListboxSelect>>", self.on_mod_select)
        self.results_listbox.bind("<Double-Button-1>", self.on_mod_double_click)

        # Кнопка установки мода
        self.install_mod_btn = ctk.CTkButton(
            left_frame,
            text="📥 УСТАНОВИТЬ ВЫБРАННЫЙ МОД",
            command=self.install_selected_mod,
            height=45,
            fg_color="#a6e3a1",
            hover_color="#7ecb8f",
            text_color="#1e1e2e",
            font=ctk.CTkFont(size=14, weight="bold"),
            corner_radius=10,
            state="disabled"
        )
        self.install_mod_btn.grid(row=9, column=0, sticky="ew", padx=10, pady=(0, 5))

        self.mod_progressbar = AnimatedProgressBar(
            left_frame,
            height=12,
            corner_radius=5,
            progress_color="#f9e2af"
        )
        self.mod_progressbar.grid(row=10, column=0, sticky="ew", padx=10, pady=(0, 2))
        self.mod_progressbar.set(0)

        self.mod_status_label = ctk.CTkLabel(
            left_frame,
            text="Введите запрос и нажмите 'Искать'",
            font=ctk.CTkFont(size=11),
            text_color="#89b4fa"
        )
        self.mod_status_label.grid(row=11, column=0, sticky="w", padx=10, pady=(2, 2))

        self.selected_mod_label = ctk.CTkLabel(
            left_frame,
            text="❌ Мод не выбран",
            font=ctk.CTkFont(size=12),
            text_color="#f38ba8"
        )
        self.selected_mod_label.grid(row=12, column=0, sticky="w", padx=10, pady=(2, 5))

        # ПРАВАЯ ПАНЕЛЬ - УСТАНОВЛЕННЫЕ МОДЫ
        right_frame = ctk.CTkFrame(tab)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 20), pady=20)
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            right_frame,
            text="📦 Установленные моды",
            font=ctk.CTkFont(size=18, weight="bold")
        ).grid(row=0, column=0, pady=(0, 10))

        self.installed_listbox = tk.Listbox(
            right_frame,
            bg="#1a1a2e",
            fg="#cdd6f4",
            font=("Consolas", 11),
            height=15,
            relief="flat"
        )
        self.installed_listbox.grid(row=1, column=0, sticky="nsew", pady=(0, 10))

        btn_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew")
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)

        refresh_btn = ctk.CTkButton(
            btn_frame,
            text="🔄 Обновить список",
            command=self.refresh_mods_list,
            height=35,
            fg_color="#89b4fa",
            hover_color="#74c7ec"
        )
        refresh_btn.grid(row=0, column=0, padx=5)

        delete_mod_btn = ctk.CTkButton(
            btn_frame,
            text="🗑️ Удалить мод",
            command=self.delete_selected_mod,
            height=35,
            fg_color="#f38ba8",
            hover_color="#e64553"
        )
        delete_mod_btn.grid(row=0, column=1, padx=5)

    def search_mods(self):
        """Выполняет поиск модов на Modrinth"""
        query = self.mod_search_entry.get().strip()
        if not query:
            messagebox.showwarning("Ошибка", "Введите название мода")
            return

        version = self.mod_version_entry.get().strip()
        if not version:
            version = "1.20.1"

        loader = self.mod_loader_var.get()

        self.results_listbox.delete(0, "end")
        self.results_listbox.insert("end", f"⏳ Поиск {query}...")
        self.mod_status_label.configure(text="⏳ Поиск...", text_color="#f9e2af")
        self.update_idletasks()

        def do_search():
            results = search_mods(query, version, loader)
            self.after(0, lambda: self.display_search_results(results))

        threading.Thread(target=do_search, daemon=True).start()

    def display_search_results(self, results):
        """Отображает результаты поиска"""
        self.results_listbox.delete(0, "end")
        self.search_results = results

        if not results:
            self.results_listbox.insert("end", "❌ Ничего не найдено")
            self.mod_status_label.configure(text="❌ Моды не найдены", text_color="#f38ba8")
            return

        for i, mod in enumerate(results):
            title = mod.get('title', 'Без названия')
            author = mod.get('author', 'неизвестен')
            downloads = mod.get('downloads', 0)
            self.results_listbox.insert("end", f"{i + 1}. {title} (👤 {author}) ⬇️{downloads}")

        self.mod_status_label.configure(text=f"✅ Найдено {len(results)} модов", text_color="#a6e3a1")

    def on_mod_select(self, event):
        """Обработка выбора мода из списка"""
        selection = self.results_listbox.curselection()
        if not selection:
            return

        idx = selection[0]
        if idx >= len(self.search_results):
            return

        self.selected_mod_index = idx
        mod = self.search_results[idx]
        title = mod.get('title', 'Без названия')
        self.selected_mod_label.configure(text=f"✅ Выбран: {title}", text_color="#a6e3a1")
        self.install_mod_btn.configure(state="normal")
        self.mod_status_label.configure(text=f"📦 Выбран мод: {title}")

    def on_mod_double_click(self, event):
        """Обработка двойного клика по моду - показывает информацию"""
        selection = self.results_listbox.curselection()
        if not selection:
            return

        idx = selection[0]
        if idx >= len(self.search_results):
            return

        mod = self.search_results[idx]
        name = mod.get('title', 'Без названия')
        author = mod.get('author', 'Неизвестен')
        description = mod.get('description', 'Нет описания')
        downloads = mod.get('downloads', 0)
        follows = mod.get('follows', 0)
        versions = mod.get('versions', [])

        info_text = f"""
📦 Мод: {name}
👤 Автор: {author}
📝 Описание: {description}
⬇️ Скачиваний: {downloads}
⭐ Подписок: {follows}
📋 Версии: {', '.join(versions[:5]) if versions else 'Неизвестно'}

💡 Двойной клик для установки
        """

        messagebox.showinfo(f"Информация о моде", info_text)

    def install_selected_mod(self):
        """Устанавливает выбранный мод с предупреждением о VPN"""
        if self.selected_mod_index < 0 or self.selected_mod_index >= len(self.search_results):
            messagebox.showwarning("Ошибка", "Сначала выберите мод из списка")
            return

        mod = self.search_results[self.selected_mod_index]
        project_id = mod.get('project_id')
        if not project_id:
            messagebox.showerror("Ошибка", "ID мода не найден")
            return

        version = self.mod_version_entry.get().strip()
        if not version:
            version = "1.20.1"

        loader = self.mod_loader_var.get()

        # Предупреждение о VPN
        if not messagebox.askyesno(
                "⚠️ ВНИМАНИЕ!",
                "Для установки модов с Modrinth рекомендуется использовать VPN!\n\n"
                "🌐 Без VPN могут быть проблемы с подключением.\n"
                "🔒 VPN обеспечит стабильное соединение.\n\n"
                "❓ Продолжить установку?"
        ):
            self.log("❌ Установка отменена")
            return

        self.install_mod_btn.configure(state="disabled", text="⏳ УСТАНОВКА...")
        self.mod_progressbar.start_animation()
        self.mod_status_label.configure(text="⏳ Установка мода...", text_color="#f9e2af")
        self.update_idletasks()

        def do_install():
            success, result = install_mod(project_id, version, loader)
            self.after(0, lambda: self.install_mod_finish(success, result))

        threading.Thread(target=do_install, daemon=True).start()

    def install_mod_finish(self, success, result):
        """Завершение установки мода"""
        self.install_mod_btn.configure(state="normal", text="📥 УСТАНОВИТЬ ВЫБРАННЫЙ МОД")
        self.mod_progressbar.stop_animation()

        if success:
            self.mod_status_label.configure(text=f"✅ Мод установлен: {result}", text_color="#a6e3a1")
            self.mod_progressbar.set(1.0)
            self.mod_progressbar.configure(progress_color="#a6e3a1")
            self.refresh_mods_list()
            messagebox.showinfo(
                "Успешно",
                f"✅ Мод '{result}' установлен!\n\n"
                "💡 Если возникли проблемы с подключением, используйте VPN."
            )
        else:
            self.mod_status_label.configure(text=f"❌ Ошибка: {result}", text_color="#f38ba8")
            self.mod_progressbar.set(0.3)
            self.mod_progressbar.configure(progress_color="#f38ba8")
            messagebox.showerror(
                "Ошибка",
                f"❌ Не удалось установить мод:\n{result}\n\n"
                "💡 Рекомендации:\n"
                "1. 🔒 Включите VPN\n"
                "2. 🌐 Проверьте интернет-соединение\n"
                "3. ⏰ Попробуйте позже"
            )

    def create_console(self):
        """Создает консоль для логов внизу окна"""
        console_frame = ctk.CTkFrame(self.main_container)
        console_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        console_frame.grid_columnconfigure(0, weight=1)

        header_frame = ctk.CTkFrame(console_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(5, 0))
        header_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header_frame,
            text="📋 Консоль",
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=5)

        ctk.CTkButton(
            header_frame,
            text="🗑️ Очистить",
            command=self.clear_console,
            fg_color="#f38ba8",
            hover_color="#e64553",
            height=25,
            width=80,
            font=ctk.CTkFont(size=11)
        ).grid(row=0, column=1, padx=5)

        self.console_text = ctk.CTkTextbox(
            console_frame,
            font=ctk.CTkFont(family="Consolas", size=11),
            height=200
        )
        self.console_text.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 5))
        self.console_text.insert("1.0", "[00:00:00] Лаунчер запущен\n")

    def create_download_panel(self):
        """Создает панель для отображения скачивания"""
        self.download_panel = ctk.CTkFrame(self.main_container, fg_color="transparent", height=40)
        self.download_panel.grid(row=2, column=0, sticky="ew", pady=(5, 0))
        self.download_panel.grid_columnconfigure(1, weight=1)
        self.download_panel.grid_remove()

        # Спиннер загрузки
        self.download_spinner = LoadingSpinner(self.download_panel)
        self.download_spinner.grid(row=0, column=0, padx=(0, 10))
        self.download_spinner.stop()

        # Статус
        self.download_status_label = ctk.CTkLabel(
            self.download_panel,
            text="Готов к работе",
            font=ctk.CTkFont(size=12),
            text_color="#89b4fa"
        )
        self.download_status_label.grid(row=0, column=1, sticky="w")

        # Прогресс-бар скачивания
        self.download_progressbar = AnimatedProgressBar(
            self.download_panel,
            height=10,
            corner_radius=5,
            progress_color="#89b4fa",
            width=300
        )
        self.download_progressbar.grid(row=0, column=2, padx=(10, 0))
        self.download_progressbar.set(0)

    def create_game_tab(self):
        """Создает вкладку игры"""
        tab = self.tab_view.tab("🎮 Игра")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        main_frame = ctk.CTkFrame(tab)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        main_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            main_frame,
            text="🎮 Запуск игры",
            font=ctk.CTkFont(size=24, weight="bold")
        ).grid(row=0, column=0, pady=(0, 20))

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
            ctk.CTkRadioButton(
                ram_frame,
                text=ram,
                variable=self.ram_var,
                value=ram
            ).pack(side="left", padx=5)

        self.launch_status_label = ctk.CTkLabel(main_frame, text="✅ Готов к запуску", font=ctk.CTkFont(size=13))
        self.launch_status_label.grid(row=9, column=0, sticky="w", pady=(0, 10))

        self.launch_progressbar = AnimatedProgressBar(main_frame, width=300, height=15)
        self.launch_progressbar.grid(row=10, column=0, sticky="ew", pady=(0, 15))

        self.launch_btn = ctk.CTkButton(
            main_frame,
            text="🚀 ЗАПУСТИТЬ ИГРУ",
            command=self.launch_game,
            height=50,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color="#89b4fa",
            hover_color="#74c7ec"
        )
        self.launch_btn.grid(row=11, column=0, sticky="ew", pady=(0, 10))

        self.timer_label = ctk.CTkLabel(main_frame, text="⏱ Время игры: 0с", font=ctk.CTkFont(size=13))
        self.timer_label.grid(row=12, column=0, sticky="w")

    def create_install_tab(self):
        """Создает вкладку установки"""
        tab = self.tab_view.tab("📦 Установка")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        main_frame = ctk.CTkFrame(tab)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        main_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            main_frame,
            text="📦 Установка клиентов",
            font=ctk.CTkFont(size=24, weight="bold")
        ).grid(row=0, column=0, pady=(0, 20))

        ctk.CTkLabel(main_frame, text="Тип установки:", font=ctk.CTkFont(size=14)).grid(row=1, column=0, sticky="w")
        self.install_type_var = ctk.StringVar(value="vanilla")
        type_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        type_frame.grid(row=2, column=0, sticky="w", pady=(0, 10))

        types = [
            ("🌐 Vanilla", "vanilla"),
            ("🧵 Fabric", "fabric"),
            ("🔥 Forge", "forge"),
            ("✨ OptiFine", "optifine")
        ]

        for text, value in types:
            ctk.CTkRadioButton(
                type_frame,
                text=text,
                variable=self.install_type_var,
                value=value
            ).pack(side="left", padx=10)

        ctk.CTkLabel(main_frame, text="Версия Minecraft:", font=ctk.CTkFont(size=14)).grid(row=3, column=0, sticky="w")
        self.install_version_entry = ctk.CTkEntry(main_frame, placeholder_text="Например: 1.20.4", width=300, height=35)
        self.install_version_entry.grid(row=4, column=0, sticky="w", pady=(0, 10))

        self.install_file_label = ctk.CTkLabel(
            main_frame,
            text="❌ Файл не выбран (только для OptiFine)",
            text_color="#f38ba8"
        )
        self.install_file_label.grid(row=5, column=0, sticky="w", pady=(0, 5))

        ctk.CTkButton(
            main_frame,
            text="📂 Выбрать файл OptiFine",
            command=self.select_optifine_file,
            fg_color="#f9e2af",
            hover_color="#f5d742",
            text_color="#1e1e2e"
        ).grid(row=6, column=0, sticky="w", pady=(0, 15))

        self.install_status_label = ctk.CTkLabel(main_frame, text="✅ Готов к установке", font=ctk.CTkFont(size=13))
        self.install_status_label.grid(row=7, column=0, sticky="w", pady=(0, 10))

        self.install_progressbar = AnimatedProgressBar(main_frame, width=300, height=15)
        self.install_progressbar.grid(row=8, column=0, sticky="ew", pady=(0, 15))

        self.install_btn = ctk.CTkButton(
            main_frame,
            text="📥 УСТАНОВИТЬ",
            command=self.install_selected_client,
            height=50,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color="#a6e3a1",
            hover_color="#7ecb8f",
            text_color="#1e1e2e"
        )
        self.install_btn.grid(row=9, column=0, sticky="ew")

    def create_accounts_tab(self):
        """Создает вкладку аккаунтов"""
        tab = self.tab_view.tab("👤 Аккаунты")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        left_frame = ctk.CTkFrame(tab)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(20, 10), pady=20)
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            left_frame,
            text="👤 Управление аккаунтами",
            font=ctk.CTkFont(size=18, weight="bold")
        ).grid(row=0, column=0, pady=(0, 10))

        self.accounts_listbox = tk.Text(
            left_frame,
            bg="#1a1a2e",
            fg="#cdd6f4",
            font=("Consolas", 11),
            height=15,
            relief="flat"
        )
        self.accounts_listbox.grid(row=1, column=0, sticky="nsew", pady=(0, 10))

        btn_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew")
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            btn_frame,
            text="➕ Добавить",
            command=self.add_account_dialog,
            fg_color="#a6e3a1",
            hover_color="#7ecb8f",
            text_color="#1e1e2e"
        ).grid(row=0, column=0, padx=5)

        ctk.CTkButton(
            btn_frame,
            text="🗑️ Удалить",
            command=self.delete_selected_account,
            fg_color="#f38ba8",
            hover_color="#e64553"
        ).grid(row=0, column=1, padx=5)

        right_frame = ctk.CTkFrame(tab)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 20), pady=20)
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(0, weight=1)

        ctk.CTkLabel(
            right_frame,
            text="ℹ️ Информация",
            font=ctk.CTkFont(size=18, weight="bold")
        ).grid(row=0, column=0, pady=(0, 10))

        info_text = """📌 Инструкция:

1. Нажмите "Добавить"
2. Введите имя пользователя3. Аккаунт будет создан

💡 Аккаунты сохраняются в папке игры
💡 Можно создать несколько аккаунтов"""

        info_label = ctk.CTkLabel(
            right_frame,
            text=info_text,
            font=ctk.CTkFont(size=13),
            justify="left"
        )
        info_label.grid(row=1, column=0, sticky="n")

    def create_skins_tab(self):
        """Создает вкладку управления скинами с кнопками установки мода"""
        tab = self.tab_view.tab("🎨 Скины")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        header_frame = ctk.CTkFrame(tab, fg_color="transparent")
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=20, pady=(15, 10))

        ctk.CTkLabel(
            header_frame,
            text="🎨 Управление скинами",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(side="left")

        left_frame = ctk.CTkFrame(tab)
        left_frame.grid(row=1, column=0, sticky="nsew", padx=(20, 10), pady=(0, 10))
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            left_frame,
            text="📋 Установленные скины",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(0, 5))

        self.skins_listbox = tk.Listbox(
            left_frame,
            bg="#1a1a2e",
            fg="#cdd6f4",
            selectbackground="#89b4fa",
            selectforeground="#1e1e2e",
            font=("Consolas", 11),
            height=12,
            relief="flat"
        )
        self.skins_listbox.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.skins_listbox.bind("<Double-Button-1>", self.on_skin_double_click)

        btn_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)
        btn_frame.grid_columnconfigure(2, weight=1)
        btn_frame.grid_columnconfigure(3, weight=1)

        import_btn = ctk.CTkButton(
            btn_frame,
            text="📥 Добавить",
            command=self.import_skin,
            fg_color="#a6e3a1",
            hover_color="#7ecb8f",
            text_color="#1e1e2e",
            height=35
        )
        import_btn.grid(row=0, column=0, padx=2)

        preview_btn = ctk.CTkButton(
            btn_frame,
            text="👁️ Превью",
            command=self.preview_skin,
            fg_color="#89b4fa",
            hover_color="#74c7ec",
            height=35
        )
        preview_btn.grid(row=0, column=1, padx=2)

        delete_btn = ctk.CTkButton(
            btn_frame,
            text="🗑️ Удалить",
            command=self.delete_selected_skin,
            fg_color="#f38ba8",
            hover_color="#e64553",
            height=35
        )
        delete_btn.grid(row=0, column=2, padx=2)

        refresh_btn = ctk.CTkButton(
            btn_frame,
            text="🔄 Обновить",
            command=self.refresh_skins,
            fg_color="#f9e2af",
            hover_color="#f5d742",
            text_color="#1e1e2e",
            height=35
        )
        refresh_btn.grid(row=0, column=3, padx=2)

        mod_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        mod_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(10, 0))
        mod_frame.grid_columnconfigure(0, weight=1)
        mod_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            mod_frame,
            text="📦 Установка мода для скинов:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#89b4fa"
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))

        forge_btn = ctk.CTkButton(
            mod_frame,
            text="🔥 Forge",
            command=self.install_custom_skin_loader,
            fg_color="#e67e22",
            hover_color="#d35400",
            text_color="white",
            height=35,
            font=ctk.CTkFont(size=12, weight="bold")
        )
        forge_btn.grid(row=1, column=0, padx=2, sticky="ew")

        fabric_btn = ctk.CTkButton(
            mod_frame,
            text="🧵 Fabric",
            command=self.install_skin_loader_for_fabric,
            fg_color="#2ecc71",
            hover_color="#27ae60",
            text_color="white",
            height=35,
            font=ctk.CTkFont(size=12, weight="bold")
        )
        fabric_btn.grid(row=1, column=1, padx=2, sticky="ew")

        open_mods_btn = ctk.CTkButton(
            mod_frame,
            text="📂 Открыть папку mods",
            command=self.open_mods_folder,
            fg_color="#89b4fa",
            hover_color="#74c7ec",
            height=35,
            font=ctk.CTkFont(size=12)
        )
        open_mods_btn.grid(row=2, column=0, columnspan=2, padx=2, pady=(5, 0), sticky="ew")

        info_label = ctk.CTkLabel(
            left_frame,
            text="💡 CustomSkinLoader - мод для отображения скинов в офлайн режиме\nДля Fabric и Forge",
            font=ctk.CTkFont(size=11),
            text_color="#89b4fa",
            justify="left"
        )
        info_label.grid(row=4, column=0, sticky="w", padx=10, pady=(10, 5))

        right_frame = ctk.CTkFrame(tab)
        right_frame.grid(row=1, column=1, sticky="nsew", padx=(10, 20), pady=(0, 10))
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            right_frame,
            text="ℹ️ Информация о скине",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(0, 5))

        self.skin_info = ctk.CTkTextbox(
            right_frame,
            font=ctk.CTkFont(family="Consolas", size=11),
            height=200
        )
        self.skin_info.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.skin_info.insert("1.0", "Выберите скин для просмотра информации\n\nДвойной клик для просмотра")
        self.skin_info.configure(state="disabled")

        open_folder_btn = ctk.CTkButton(
            right_frame,
            text="📂 Открыть папку со скинами",
            command=self.open_skins_folder,
            fg_color="#f9e2af",
            hover_color="#f5d742",
            text_color="#1e1e2e",
            height=35
        )
        open_folder_btn.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))

        info_label = ctk.CTkLabel(
            right_frame,
            text="💡 Двойной клик для просмотра информации\nПоддерживаются .png, .jpg, .jpeg",
            font=ctk.CTkFont(size=11),
            text_color="#89b4fa",
            justify="left"
        )
        info_label.grid(row=3, column=0, sticky="w", padx=10, pady=(0, 5))

    def create_resourcepacks_tab(self):
        """Создает вкладку ресурспаков"""
        tab = self.tab_view.tab("📦 Ресурспаки")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        left_frame = ctk.CTkFrame(tab)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(20, 10), pady=20)
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            left_frame,
            text="📦 Ресурспаки",
            font=ctk.CTkFont(size=18, weight="bold")
        ).grid(row=0, column=0, pady=(0, 10))

        self.resourcepacks_listbox = tk.Listbox(
            left_frame,
            bg="#1a1a2e",
            fg="#cdd6f4",
            selectbackground="#89b4fa",
            selectforeground="#1e1e2e",
            font=("Consolas", 11),
            height=15,
            relief="flat"
        )
        self.resourcepacks_listbox.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        self.resourcepacks_listbox.bind("<Double-Button-1>", self.on_resourcepack_double_click)

        btn_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew")
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)
        btn_frame.grid_columnconfigure(2, weight=1)

        ctk.CTkButton(
            btn_frame,
            text="📥 Установить",
            command=self.install_resourcepack,
            fg_color="#a6e3a1",
            hover_color="#7ecb8f",
            text_color="#1e1e2e"
        ).grid(row=0, column=0, padx=2)

        ctk.CTkButton(
            btn_frame,
            text="🗑️ Удалить",
            command=self.delete_selected_resourcepack,
            fg_color="#f38ba8",
            hover_color="#e64553"
        ).grid(row=0, column=1, padx=2)

        ctk.CTkButton(
            btn_frame,
            text="📂 Открыть папку",
            command=self.open_resourcepacks_folder,
            fg_color="#89b4fa",
            hover_color="#74c7ec"
        ).grid(row=0, column=2, padx=2)

        right_frame = ctk.CTkFrame(tab)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 20), pady=20)
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            right_frame,
            text="ℹ️ Информация",
            font=ctk.CTkFont(size=18, weight="bold")
        ).grid(row=0, column=0, pady=(0, 10))

        self.resourcepack_info = ctk.CTkTextbox(
            right_frame,
            font=ctk.CTkFont(family="Consolas", size=11),
            height=200
        )
        self.resourcepack_info.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        self.resourcepack_info.insert("1.0", "Выберите ресурспак для просмотра информации")
        self.resourcepack_info.configure(state="disabled")

    def create_settings_tab(self):
        """Создает вкладку настроек с ссылками"""
        tab = self.tab_view.tab("⚙️ Настройки")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        main_frame = ctk.CTkFrame(tab)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        main_frame.grid_columnconfigure(0, weight=1)

        # Заголовок
        ctk.CTkLabel(
            main_frame,
            text="⚙️ Настройки лаунчера",
            font=ctk.CTkFont(size=24, weight="bold")
        ).grid(row=0, column=0, pady=(0, 20))

        # ============================================================
        # ТЕМА
        # ============================================================
        ctk.CTkLabel(
            main_frame,
            text="🌓 Тема оформления",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=1, column=0, sticky="w", pady=(0, 5))

        theme_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        theme_frame.grid(row=2, column=0, sticky="w", pady=(0, 15))

        self.theme_btn_settings = ctk.CTkButton(
            theme_frame,
            text="🌙 Тёмная" if ctk.get_appearance_mode() == "Dark" else "☀️ Светлая",
            command=self.toggle_theme,
            width=150,
            height=35,
            fg_color="#89b4fa",
            hover_color="#74c7ec"
        )
        self.theme_btn_settings.pack(side="left")

        # ============================================================
        # НАПОМИНАНИЯ
        # ============================================================
        ctk.CTkLabel(
            main_frame,
            text="🧼 Напоминания",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=3, column=0, sticky="w", pady=(5, 5))

        self.hygiene_reminders_var = ctk.BooleanVar(value=self.settings.get("hygiene_reminders", True))
        ctk.CTkCheckBox(
            main_frame,
            text="Включить напоминания о перерыве (каждые 25 минут)",
            variable=self.hygiene_reminders_var,
            command=self.toggle_hygiene_reminders
        ).grid(row=4, column=0, sticky="w", pady=(0, 5))

        ctk.CTkButton(
            main_frame,
            text="🧼 Напомнить сейчас",
            command=self.manual_hygiene_reminder,
            fg_color="#f9e2af",
            hover_color="#f5d742",
            text_color="#1e1e2e",
            width=200,
            height=35
        ).grid(row=5, column=0, sticky="w", pady=(0, 15))

        # ============================================================
        # СТАТИСТИКА
        # ============================================================
        ctk.CTkLabel(
            main_frame,
            text="📊 Статистика",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=6, column=0, sticky="w", pady=(5, 5))

        ctk.CTkButton(
            main_frame,
            text="🔄 Сбросить статистику",
            command=self.reset_stats,
            fg_color="#f38ba8",
            hover_color="#e64553",
            width=200,
            height=35
        ).grid(row=7, column=0, sticky="w", pady=(0, 15))

        # ============================================================
        # ССЫЛКИ (GitHub и DonationAlerts)
        # ============================================================
        ctk.CTkLabel(
            main_frame,
            text="🔗 Полезные ссылки",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=8, column=0, sticky="w", pady=(5, 10))

        # Контейнер для кнопок ссылок
        links_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        links_frame.grid(row=9, column=0, sticky="w", pady=(0, 15))

        # GitHub
        github_btn = ctk.CTkButton(
            links_frame,
            text="⭐ GitHub",
            command=lambda: webbrowser.open("https://github.com/KotiPlayYT/67launcher/"),
            width=180,
            height=40,
            fg_color="#333333",
            hover_color="#555555",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        github_btn.grid(row=0, column=0, padx=(0, 15), pady=5)

        # DonationAlerts
        donate_btn = ctk.CTkButton(
            links_frame,
            text="💝 Поддержать (DonationAlerts)",
            command=lambda: webbrowser.open("https://www.donationalerts.com/r/ionux"),
            width=180,
            height=40,
            fg_color="#ff6b6b",
            hover_color="#ee5a24",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        donate_btn.grid(row=0, column=1, pady=5)

        # Описание
        info_text = """
💡 GitHub - исходный код лаунчера
💝 DonationAlerts - поддержка разработчика
        """
        info_label = ctk.CTkLabel(
            main_frame,
            text=info_text,
            font=ctk.CTkFont(size=12),
            text_color="#89b4fa",
            justify="left"
        )
        info_label.grid(row=10, column=0, sticky="w", pady=(0, 10))

        # Разделитель
        ctk.CTkLabel(
            main_frame,
            text="",
            height=20
        ).grid(row=11, column=0)

    def create_stats_tab(self):
        """Создает вкладку статистики"""
        tab = self.tab_view.tab("📊 Статистика")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        main_frame = ctk.CTkFrame(tab)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            main_frame,
            text="📊 Статистика",
            font=ctk.CTkFont(size=24, weight="bold")
        ).grid(row=0, column=0, pady=(0, 20))

        self.stats_text = ctk.CTkTextbox(
            main_frame,
            font=ctk.CTkFont(family="Consolas", size=13),
            height=300
        )
        self.stats_text.grid(row=1, column=0, sticky="nsew", pady=(0, 10))

        ctk.CTkButton(
            main_frame,
            text="🔄 Обновить",
            command=self.update_stats_display,
            fg_color="#89b4fa",
            hover_color="#74c7ec",
            width=200
        ).grid(row=2, column=0)

        self.update_stats_display()

    # =================================================================
    # ДОПОЛНИТЕЛЬНЫЕ МЕТОДЫ
    # =================================================================

    def toggle_hygiene_reminders(self):
        """Включает/выключает напоминания"""
        self.settings["hygiene_reminders"] = self.hygiene_reminders_var.get()
        save_launcher_settings(self.settings)
        if self.hygiene_reminders_var.get():
            self.log("🧼 Напоминания включены")
            self.start_hygiene_reminder()
        else:
            self.log("🧼 Напоминания отключены")

    def reset_stats(self):
        """Сбрасывает статистику"""
        if messagebox.askyesno("Подтверждение", "Сбросить всю статистику?"):
            stats = {"launches": 0, "total_play_time": 0, "last_launch": None, "launch_history": []}
            save_stats(stats)
            self.stats = stats
            self.update_stats_display()
            self.log("📊 Статистика сброшена")

    def update_info_display(self):
        """Обновляет информацию на главном экране"""
        stats = load_stats()
        self.stats = stats
        self.update_stats_display()

    def update_subtitle(self):
        """Обновляет подзаголовок окна"""
        launches = self.stats.get("launches", 0)
        play_time = self.stats.get("total_play_time", 0)
        self.title(f"67Launcher - МЯУ | Запусков: {launches} | Время: {self.format_time(play_time)}")

    def restore_last_selection(self):
        """Восстанавливает последний выбранный аккаунт и версию"""
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
        """Сохраняет текущий выбор"""
        self.settings["last_account"] = self.account_combo.get()
        self.settings["last_version"] = self.version_combo.get()
        self.settings["last_skin"] = self.skin_combo.get()
        save_launcher_settings(self.settings)

    def load_available_versions(self):
        """Загружает доступные версии из интернета"""
        try:
            self.log("🔄 Загрузка списка версий...")
            versions = mll.utils.get_available_versions(MINECRAFT_DIR)
            self.available_versions = [v["id"] for v in versions if "snapshot" not in v.get("type", "").lower()]
            self.log(f"✅ Загружено {len(self.available_versions)} версий")
        except Exception as e:
            self.log(f"❌ Ошибка загрузки версий: {e}")
            self.available_versions = []

    def scan_and_update_versions(self):
        """Сканирует установленные версии и обновляет список"""
        installed = []
        versions_dir = os.path.join(MINECRAFT_DIR, "versions")
        if os.path.exists(versions_dir):
            for folder in os.listdir(versions_dir):
                if os.path.isdir(os.path.join(versions_dir, folder)):
                    installed.append(folder)

        self.installed_versions = installed
        self.update_version_combo()

    def update_version_combo(self):
        """Обновляет комбобокс с версиями"""
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
        """Выбирает файл установщика OptiFine"""
        file_path = filedialog.askopenfilename(
            title="Выберите установщик OptiFine (.jar)",
            filetypes=[("JAR файлы", "*.jar"), ("Все файлы", "*.*")]
        )

        if file_path:
            if file_path.lower().endswith('.exe'):
                messagebox.showwarning(
                    "Ошибка",
                    "Для установки OptiFine используйте .jar версию установщика!\n\n"
                    "Скачайте установщик (.jar) с официального сайта OptiFine."
                )
                return

            self.selected_installer_path = file_path
            self.install_file_label.configure(
                text=f"✅ Файл выбран: {os.path.basename(file_path)}",
                text_color="#a6e3a1"
            )
            self.log(f"📂 Выбран файл OptiFine: {file_path}")

    def open_mods_folder_gui(self):
        """Открывает папку с модами"""
        mods_path = os.path.join(MINECRAFT_DIR, "mods")
        os.makedirs(mods_path, exist_ok=True)
        os.startfile(mods_path)
        self.log(f"📂 Открыта папка mods")

    def on_closing(self):
        """Обработка закрытия окна"""
        if self.timer_running:
            self.stop_game_timer()

        self._closing = True
        self.save_current_selection()

        try:
            self.destroy()
        except:
            pass


# ===================================================================
# спасибо
# ===================================================================

if __name__ == "__main__":
    try:
        app = LauncherApp()
        app.mainloop()
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        input("\nНажмите Enter для выхода...")
