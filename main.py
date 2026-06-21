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

# ===================================================================
# НАСТРОЙКА ВНЕШНЕГО ВИДА
# ===================================================================

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ===================================================================
# 1. НАСТРОЙКИ И ПЕРЕМЕННЫЕ
# ===================================================================

GAME_DIR = os.path.join(os.environ['APPDATA'], ".ionux")
MINECRAFT_DIR = GAME_DIR

ACCOUNTS_FILE = os.path.join(MINECRAFT_DIR, "accounts.json")
PROFILES_FILE = os.path.join(MINECRAFT_DIR, "profile.json")
LAUNCHER_PROFILES_FILE = os.path.join(MINECRAFT_DIR, "launcher_profiles.json")

REQUIRED_FOLDERS = [
    "assets",
    "config",
    "libraries",
    "logs",
    "mods",
    "resourcepacks",
    "resources",
    "runtime",
    "saves",
    "stats",
    "texturepacks",
    "versions"
]

log_callback = None


def set_log_callback(callback):
    global log_callback
    log_callback = callback


def log_message(message):
    global log_callback
    if log_callback:
        log_callback(message)


def create_launcher_profiles():
    launcher_profiles = {
        "profiles": {},
        "settings": {
            "enableSnapshots": False,
            "enableHistorical": False,
            "keepLauncherOpen": False
        },
        "selectedProfile": "Latest Release",
        "clientToken": "ionux-launcher-token",
        "authenticationDatabase": {}
    }

    os.makedirs(os.path.dirname(LAUNCHER_PROFILES_FILE), exist_ok=True)
    with open(LAUNCHER_PROFILES_FILE, 'w', encoding='utf-8') as f:
        json.dump(launcher_profiles, f, indent=2)
    log_message("✅ Создан launcher_profiles.json")


def cleanup_forge_temp():
    """Удаляет временные папки Forge, которые могли остаться после ошибки"""
    temp_dir = tempfile.gettempdir()
    for item in os.listdir(temp_dir):
        if item.startswith("minecraft-launcher-lib-forge"):
            temp_path = os.path.join(temp_dir, item)
            try:
                shutil.rmtree(temp_path, ignore_errors=True)
                log_message(f"🧹 Очищена временная папка: {temp_path}")
            except Exception:
                pass


def ensure_game_folder_structure():
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

    log_message(f"✅ Структура папки игры создана: {MINECRAFT_DIR}")


# ===================================================================
# 2. РАБОТА С АККАУНТАМИ
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
            print(f"Ошибка загрузки аккаунтов: {e}")
            return []
    return []


def save_accounts(accounts):
    os.makedirs(os.path.dirname(ACCOUNTS_FILE), exist_ok=True)
    try:
        with open(ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(accounts, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Ошибка сохранения аккаунтов: {e}")
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
# 3. РАБОТА С ПРОФИЛЯМИ И ВЕРСИЯМИ
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
        print(f"Ошибка сохранения профилей: {e}")
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
        log_message(f"✅ Профиль создан: {version_id}")
        return True
    return False


def delete_profile(version_id):
    profiles = load_profiles()
    if not isinstance(profiles, dict):
        return False

    if version_id in profiles:
        del profiles[version_id]
        save_profiles(profiles)
        log_message(f"🗑️ Профиль удалён: {version_id}")
        return True
    return False


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

                versions.append({
                    "id": folder,
                    "type": version_type,
                    "jar": jar_file,
                    "json": json_file,
                    "path": folder_path
                })

    return versions


# ===================================================================
# 4. УСТАНОВКА JAVA
# ===================================================================

def download_with_progress(url, dest_path, callback=None):
    try:
        def report_progress(count, block_size, total_size):
            if total_size > 0 and callback:
                percent = int(count * block_size * 100 / total_size)
                callback(percent)

        urllib.request.urlretrieve(url, dest_path, report_progress)
        return True
    except Exception as e:
        log_message(f"❌ Ошибка скачивания: {e}")
        return False


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
    major = 0
    try:
        major = int(minecraft_version.split('.')[0])
    except:
        pass

    if major <= 16:
        try:
            result = subprocess.run(["java", "-version"], capture_output=True, text=True)
            if result.returncode == 0:
                output = (result.stderr + result.stdout).lower()
                if "1.8" in output or '"8.' in output:
                    log_message("✅ Найдена Java 8 для старых версий")
                    return "java"
        except:
            pass

        local_java_dir = os.path.join(MINECRAFT_DIR, "java")
        java8_exe = os.path.join(local_java_dir, "bin", "java.exe")
        if os.path.exists(java8_exe):
            ver = get_java_version(java8_exe)
            if ver == 8:
                log_message("✅ Найдена локальная Java 8")
                return java8_exe

        log_message("⚠️ Java 8 не найдена! Скачивание...")
        java8_url = "https://github.com/adoptium/temurin8-binaries/releases/download/jdk8u392-b08/OpenJDK8U-jdk_x64_windows_hotspot_8u392b08.zip"
        temp_dir = os.path.join(tempfile.gettempdir(), "ionux_java8")
        os.makedirs(temp_dir, exist_ok=True)
        zip_path = os.path.join(temp_dir, "java8.zip")
        local_java_dir = os.path.join(MINECRAFT_DIR, "java")

        if download_with_progress(java8_url, zip_path):
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(local_java_dir)
                os.remove(zip_path)
                shutil.rmtree(temp_dir, ignore_errors=True)
                log_message("✅ Java 8 установлена!")
                return os.path.join(local_java_dir, "bin", "java.exe")
            except Exception as e:
                log_message(f"❌ Ошибка установки Java 8: {e}")

    else:
        try:
            result = subprocess.run(["java", "-version"], capture_output=True, text=True)
            if result.returncode == 0:
                output = (result.stderr + result.stdout).lower()
                if "17." in output or '"17' in output:
                    log_message("✅ Найдена Java 17 для новых версий")
                    return "java"
        except:
            pass

        local_java_dir = os.path.join(MINECRAFT_DIR, "java")
        java17_exe = os.path.join(local_java_dir, "bin", "java.exe")
        if os.path.exists(java17_exe):
            ver = get_java_version(java17_exe)
            if ver == 17:
                log_message("✅ Найдена локальная Java 17")
                return java17_exe

        log_message("⚠️ Java 17 не найдена! Скачивание...")
        java17_url = "https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.9%2B9/OpenJDK17U-jdk_x64_windows_hotspot_17.0.9_9.zip"
        temp_dir = os.path.join(tempfile.gettempdir(), "ionux_java17")
        os.makedirs(temp_dir, exist_ok=True)
        zip_path = os.path.join(temp_dir, "java17.zip")
        local_java_dir = os.path.join(MINECRAFT_DIR, "java")

        if download_with_progress(java17_url, zip_path):
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(local_java_dir)
                os.remove(zip_path)
                shutil.rmtree(temp_dir, ignore_errors=True)
                log_message("✅ Java 17 установлена!")
                return os.path.join(local_java_dir, "bin", "java.exe")
            except Exception as e:
                log_message(f"❌ Ошибка установки Java 17: {e}")

    return "java"


# ===================================================================
# 5. РАБОТА С МОДАМИ
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
                                headers={"User-Agent": "IonuxLauncher/1.0"})
        response.raise_for_status()
        return response.json().get("hits", [])
    except Exception as e:
        log_message(f"❌ Ошибка поиска: {e}")
        return []


def install_mod(project_id, game_version, mod_loader):
    try:
        params = {"game_versions": f'["{game_version}"]', "loaders": f'["{mod_loader}"]'}
        response = requests.get(f"https://api.modrinth.com/v2/project/{project_id}/version",
                                params=params, headers={"User-Agent": "IonuxLauncher/1.0"})
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
# 6. КОЛБЭК ДЛЯ MLL
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
# 7. КЛАСС ДЛЯ АНИМИРОВАННОГО ПРОГРЕСС-БАРА
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

    def start_animation(self):
        self.animating = True
        self.current_value = 0
        self.target_value = 100
        self._animate()

    def stop_animation(self):
        self.animating = False
        self.set(1.0)

    def set_progress(self, value):
        self.target_value = min(100, max(0, value))
        if not self.animating:
            self.current_value = self.target_value
            self.set(self.current_value / 100)

    def _animate(self):
        if not self.animating:
            return
        if self.current_value >= 95:
            self.step = -2
        elif self.current_value <= 5:
            self.step = 2
        self.current_value += self.step
        self.set(self.current_value / 100)
        self.after(self.animation_speed, self._animate)


# ===================================================================
# 8. ОСНОВНОЙ КЛАСС ПРИЛОЖЕНИЯ
# ===================================================================

class LauncherApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("67 Launcher - Minecraft Launcher")
        self.geometry("1100x850")
        self.minsize(1000, 750)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        set_log_callback(self.log)
        self.search_results = []
        self.selected_mod_index = -1
        self.is_launching = False
        self.installed_versions = []
        self.selected_installer_path = None
        self.install_cancelled = False

        ensure_game_folder_structure()

        self.create_widgets()
        self.refresh_accounts()
        self.refresh_accounts_listbox()
        self.refresh_mods_list()
        self.scan_and_update_versions()

        self.log(f"📁 Папка игры: {MINECRAFT_DIR}")

    def create_widgets(self):
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)

        banner_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        banner_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        title_label = ctk.CTkLabel(
            banner_frame,
            text="⚡ 67 Launcher RELEASE!",
            font=ctk.CTkFont(size=32, weight="bold"),
            text_color="#89b4fa"
        )
        title_label.pack()

        subtitle_label = ctk.CTkLabel(
            banner_frame,
            text=f"Папка: {MINECRAFT_DIR}",
            font=ctk.CTkFont(size=12)
        )
        subtitle_label.pack()

        self.tab_view = ctk.CTkTabview(self.main_frame)
        self.tab_view.grid(row=1, column=0, sticky="nsew", pady=(0, 10))

        self.tab_view.add("🎮 Игра")
        self.tab_view.add("📦 Моды")
        self.tab_view.add("👤 Аккаунты")
        self.tab_view.add("⚡ Установка")
        self.tab_view.add("🔧 Версии")
        self.tab_view.add("📁 Файлы")
        self.tab_view.add("⚙️ Настройки")

        self.create_game_tab()
        self.create_mods_tab()
        self.create_accounts_tab()
        self.create_install_tab()
        self.create_versions_tab()
        self.create_files_tab()
        self.create_settings_tab()

        console_frame = ctk.CTkFrame(self.main_frame)
        console_frame.grid(row=2, column=0, sticky="nsew")
        console_frame.grid_columnconfigure(0, weight=1)
        console_frame.grid_rowconfigure(1, weight=1)

        console_header = ctk.CTkFrame(console_frame, fg_color="transparent")
        console_header.grid(row=0, column=0, sticky="ew", pady=(5, 5))

        ctk.CTkLabel(console_header, text="📋 Консоль", font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")

        clear_btn = ctk.CTkButton(
            console_header,
            text="Очистить",
            command=self.clear_console,
            width=100,
            height=30,
            fg_color="#f38ba8",
            hover_color="#e64553"
        )
        clear_btn.pack(side="right")

        self.console_text = ctk.CTkTextbox(console_frame, font=ctk.CTkFont(family="Consolas", size=11))
        self.console_text.grid(row=1, column=0, sticky="nsew", pady=(0, 5))

        self.main_frame.grid_rowconfigure(2, weight=1)

    def create_game_tab(self):
        tab = self.tab_view.tab("🎮 Игра")
        tab.grid_columnconfigure(0, weight=2)
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        left_frame = ctk.CTkFrame(tab)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(left_frame, text="Аккаунт", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0,
                                                                                                sticky="w",
                                                                                                pady=(10, 5), padx=10)

        self.account_combo = ctk.CTkComboBox(
            left_frame,
            values=["Загрузка..."],
            state="readonly",
            width=300
        )
        self.account_combo.grid(row=1, column=0, sticky="w", padx=10, pady=(0, 15))

        ctk.CTkLabel(left_frame, text="Версия Minecraft", font=ctk.CTkFont(size=14, weight="bold")).grid(row=2,
                                                                                                         column=0,
                                                                                                         sticky="w",
                                                                                                         padx=10,
                                                                                                         pady=(0, 5))

        self.version_combo = ctk.CTkComboBox(
            left_frame,
            values=["Загрузка..."],
            state="readonly",
            width=350
        )
        self.version_combo.grid(row=3, column=0, sticky="w", padx=10, pady=(0, 15))

        ctk.CTkLabel(left_frame, text="Выделение памяти", font=ctk.CTkFont(size=14, weight="bold")).grid(row=4,
                                                                                                         column=0,
                                                                                                         sticky="w",
                                                                                                         padx=10,
                                                                                                         pady=(0, 5))

        ram_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        ram_frame.grid(row=5, column=0, sticky="w", padx=10, pady=(0, 20))

        self.ram_var = ctk.StringVar(value="2G")
        rams = ["1G", "2G", "4G", "6G", "8G"]

        for i, ram in enumerate(rams):
            rb = ctk.CTkRadioButton(
                ram_frame,
                text=ram,
                variable=self.ram_var,
                value=ram
            )
            rb.grid(row=0, column=i, padx=(0, 10))

        self.launch_btn = ctk.CTkButton(
            left_frame,
            text="🚀 ЗАПУСТИТЬ ИГРУ",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=55,
            fg_color="#a6e3a1",
            hover_color="#7ecb8f",
            text_color="#1e1e2e",
            command=self.launch_game,
            corner_radius=10
        )
        self.launch_btn.grid(row=6, column=0, sticky="ew", padx=10, pady=(0, 5))

        self.launch_progressbar = AnimatedProgressBar(
            left_frame,
            height=15,
            corner_radius=5,
            progress_color="#f9e2af"
        )
        self.launch_progressbar.grid(row=7, column=0, sticky="ew", padx=10, pady=(0, 2))
        self.launch_progressbar.set(0)

        self.launch_status_label = ctk.CTkLabel(
            left_frame,
            text="Готов к запуску",
            font=ctk.CTkFont(size=11),
            text_color="#a6e3a1"
        )
        self.launch_status_label.grid(row=8, column=0, sticky="w", padx=10, pady=(0, 5))

        right_frame = ctk.CTkFrame(tab)
        right_frame.grid(row=0, column=1, sticky="nsew")
        right_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            right_frame,
            text="ℹ️ Информация",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=15, pady=(15, 10))

        info_text = f"""
📁 Папка с игрой:
{os.path.abspath(MINECRAFT_DIR)}

📁 Структура папки игры:
   📁 assets/     - ресурсы игры
   📁 config/     - конфиги модов
   📁 libraries/  - библиотеки Java
   📁 logs/       - логи игры
   📁 mods/       - установленные моды
   📁 resourcepacks/ - ресурспаки
   📁 saves/      - сохранения (миры)
   📁 versions/   - установленные версии

📄 Важные файлы:
   А для чего тебе это)
        """

        info_display = ctk.CTkTextbox(right_frame, font=ctk.CTkFont(family="Consolas", size=11))
        info_display.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        info_display.insert("1.0", info_text)
        info_display.configure(state="disabled")

        right_frame.grid_rowconfigure(1, weight=1)

    def create_mods_tab(self):
        tab = self.tab_view.tab("📦 Моды")
        tab.grid_columnconfigure(0, weight=2)
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        header_frame = ctk.CTkFrame(tab, fg_color="transparent")
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=20, pady=(10, 5))

        ctk.CTkLabel(
            header_frame,
            text="🔍 Поиск и установка модов",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(side="left")

        left_frame = ctk.CTkFrame(tab)
        left_frame.grid(row=1, column=0, sticky="nsew", padx=(20, 10), pady=(0, 10))
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(7, weight=1)

        ctk.CTkLabel(left_frame, text="🎮 Версия Minecraft:", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(5, 2)
        )
        self.mod_version_entry = ctk.CTkEntry(
            left_frame,
            placeholder_text="1.20.4",
            height=32
        )
        self.mod_version_entry.insert(0, "1.20.1")
        self.mod_version_entry.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))

        ctk.CTkLabel(left_frame, text="🔧 Загрузчик:", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=2, column=0, sticky="w", padx=10, pady=(0, 2)
        )

        loader_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        loader_frame.grid(row=3, column=0, sticky="w", padx=10, pady=(0, 8))

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

        ctk.CTkLabel(left_frame, text="🔍 Название мода:", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=4, column=0, sticky="w", padx=10, pady=(0, 2)
        )

        search_row = ctk.CTkFrame(left_frame, fg_color="transparent")
        search_row.grid(row=5, column=0, sticky="ew", padx=10, pady=(0, 8))
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

        ctk.CTkLabel(left_frame, text="📋 Результаты поиска (кликните для выбора):",
                     font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=6, column=0, sticky="w", padx=10, pady=(5, 2)
        )

        self.results_listbox = tk.Listbox(
            left_frame,
            bg="#1a1a2e",
            fg="#cdd6f4",
            selectbackground="#89b4fa",
            selectforeground="#1e1e2e",
            font=("Consolas", 11),
            height=6,
            relief="flat"
        )
        self.results_listbox.grid(row=7, column=0, sticky="nsew", padx=10, pady=(0, 8))
        self.results_listbox.bind("<<ListboxSelect>>", self.on_mod_select)

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
        self.install_mod_btn.grid(row=8, column=0, sticky="ew", padx=10, pady=(0, 5))

        self.mod_progressbar = AnimatedProgressBar(
            left_frame,
            height=12,
            corner_radius=5,
            progress_color="#f9e2af"
        )
        self.mod_progressbar.grid(row=9, column=0, sticky="ew", padx=10, pady=(0, 2))
        self.mod_progressbar.set(0)

        self.mod_status_label = ctk.CTkLabel(
            left_frame,
            text="Выберите мод из списка",
            font=ctk.CTkFont(size=11),
            text_color="#89b4fa"
        )
        self.mod_status_label.grid(row=10, column=0, sticky="w", padx=10, pady=(0, 2))

        self.selected_mod_label = ctk.CTkLabel(
            left_frame,
            text="❌ Мод не выбран",
            font=ctk.CTkFont(size=12),
            text_color="#f38ba8"
        )
        self.selected_mod_label.grid(row=11, column=0, sticky="w", padx=10, pady=(2, 5))

        right_frame = ctk.CTkFrame(tab)
        right_frame.grid(row=1, column=1, sticky="nsew", padx=(10, 20), pady=(0, 10))
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            right_frame,
            text="📦 Установленные моды",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 5))

        self.installed_listbox = tk.Listbox(
            right_frame,
            bg="#1a1a2e",
            fg="#cdd6f4",
            font=("Consolas", 11),
            height=6,
            relief="flat"
        )
        self.installed_listbox.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        btn_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))

        refresh_btn = ctk.CTkButton(
            btn_frame,
            text="🔄 Обновить",
            command=self.refresh_mods_list,
            width=100,
            height=32
        )
        refresh_btn.grid(row=0, column=0, padx=(0, 10))

        delete_mod_btn = ctk.CTkButton(
            btn_frame,
            text="🗑️ Удалить мод",
            command=self.delete_selected_mod,
            width=100,
            height=32,
            fg_color="#f38ba8",
            hover_color="#e64553"
        )
        delete_mod_btn.grid(row=0, column=1)

    def create_accounts_tab(self):
        tab = self.tab_view.tab("👤 Аккаунты")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            tab,
            text="Управление аккаунтами",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(15, 10))

        self.accounts_listbox = ctk.CTkTextbox(tab, font=ctk.CTkFont(family="Consolas", size=12))
        self.accounts_listbox.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 10))

        btn_frame = ctk.CTkFrame(tab, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="w", padx=20, pady=(0, 15))

        add_btn = ctk.CTkButton(
            btn_frame,
            text="➕ Добавить аккаунт",
            command=self.add_account_dialog,
            fg_color="#a6e3a1",
            hover_color="#7ecb8f",
            text_color="#1e1e2e"
        )
        add_btn.grid(row=0, column=0, padx=(0, 10))

        delete_btn = ctk.CTkButton(
            btn_frame,
            text="🗑️ Удалить аккаунт",
            command=self.delete_selected_account,
            fg_color="#f38ba8",
            hover_color="#e64553"
        )
        delete_btn.grid(row=0, column=1)

    def create_install_tab(self):
        tab = self.tab_view.tab("⚡ Установка")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        main_frame = ctk.CTkFrame(tab)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(6, weight=1)

        ctk.CTkLabel(
            main_frame,
            text="⚡ Установка клиентов",
            font=ctk.CTkFont(size=18, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=15, pady=(0, 10))

        ctk.CTkLabel(
            main_frame,
            text="Установка Vanilla, Fabric, Forge или OptiFine\n"
                 "Выберите тип и нажмите кнопку установки",
            font=ctk.CTkFont(size=13),
            justify="left"
        ).grid(row=1, column=0, sticky="w", padx=15, pady=(0, 15))

        type_frame = ctk.CTkFrame(main_frame)
        type_frame.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 10))

        ctk.CTkLabel(type_frame, text="Тип клиента:", font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0,
                                                                                                     padx=10,
                                                                                                     sticky="w")

        self.install_type_var = ctk.StringVar(value="vanilla")
        types = [
            ("📦 Vanilla", "vanilla"),
            ("🧵 Fabric", "fabric"),
            ("🔥 Forge", "forge"),
            ("⚡ OptiFine", "optifine")
        ]

        for i, (text, value) in enumerate(types):
            rb = ctk.CTkRadioButton(
                type_frame,
                text=text,
                variable=self.install_type_var,
                value=value
            )
            rb.grid(row=0, column=i + 1, padx=10)

        version_frame = ctk.CTkFrame(main_frame)
        version_frame.grid(row=3, column=0, sticky="ew", padx=15, pady=(0, 10))
        version_frame.grid_columnconfigure(0, weight=1)
        version_frame.grid_columnconfigure(1, weight=0)

        ctk.CTkLabel(version_frame, text="Версия Minecraft:", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(5, 2)
        )

        self.install_version_entry = ctk.CTkEntry(
            version_frame,
            placeholder_text="1.20.4",
            height=35,
            width=200
        )
        self.install_version_entry.insert(0, "1.20.1")
        self.install_version_entry.grid(row=0, column=0, sticky="w", padx=(10, 10), pady=(0, 5))

        popular_btn = ctk.CTkButton(
            version_frame,
            text="Популярные",
            command=self.show_install_popular_versions,
            width=120,
            height=35,
            fg_color="#89b4fa",
            hover_color="#74c7ec"
        )
        popular_btn.grid(row=0, column=1)

        self.install_btn = ctk.CTkButton(
            main_frame,
            text="📥 УСТАНОВИТЬ",
            command=self.install_selected_client,
            height=40,
            fg_color="#a6e3a1",
            hover_color="#7ecb8f",
            text_color="#1e1e2e",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.install_btn.grid(row=4, column=0, sticky="ew", padx=15, pady=(0, 10))

        self.install_progressbar = AnimatedProgressBar(
            main_frame,
            height=15,
            corner_radius=5,
            progress_color="#f9e2af"
        )
        self.install_progressbar.grid(row=5, column=0, sticky="ew", padx=15, pady=(0, 2))
        self.install_progressbar.set(0)

        self.install_status_label = ctk.CTkLabel(
            main_frame,
            text="Выберите тип и версию, затем нажмите 'Установить'",
            font=ctk.CTkFont(size=13),
            text_color="#89b4fa"
        )
        self.install_status_label.grid(row=6, column=0, sticky="w", padx=15, pady=(5, 0))

        info_frame = ctk.CTkFrame(main_frame)
        info_frame.grid(row=7, column=0, sticky="nsew", padx=15, pady=(15, 0))
        info_frame.grid_columnconfigure(0, weight=1)
        info_frame.grid_rowconfigure(0, weight=1)

        info_text = """
📌 Fabric/Forge устанавливаются автоматически через интернет
   (может занять несколько минут)

📌 Для Vanilla:
   Просто выберите версию и нажмите "УСТАНОВИТЬ"

📌 Для OptiFine:
   1. Скачайте установщик с официального сайта (.jar)
   2. Нажмите "Выбрать файл" и укажите его
   3. Нажмите "УСТАНОВИТЬ"

⚠️ Для Forge 1.12.2 и ниже требуется Java 8!
   Лаунчер автоматически установит её при необходимости

💡 После установки нажмите "Обновить список" на вкладке "Версии"
        """

        info_display = ctk.CTkTextbox(info_frame, font=ctk.CTkFont(family="Consolas", size=11))
        info_display.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        info_display.insert("1.0", info_text)
        info_display.configure(state="disabled")

        file_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        file_frame.grid(row=8, column=0, sticky="ew", padx=15, pady=(0, 10))

        self.install_file_label = ctk.CTkLabel(
            file_frame,
            text="❌ Файл не выбран (только для OptiFine)",
            font=ctk.CTkFont(size=12),
            text_color="#f38ba8"
        )
        self.install_file_label.grid(row=0, column=0, sticky="w", padx=10, pady=(5, 5))

        select_btn = ctk.CTkButton(
            file_frame,
            text="📂 Выбрать файл установщика",
            command=self.select_installer_file,
            width=250,
            height=30,
            fg_color="#89b4fa",
            hover_color="#74c7ec"
        )
        select_btn.grid(row=1, column=0, padx=10, pady=(0, 5))

        main_frame.grid_rowconfigure(7, weight=1)

    def create_versions_tab(self):
        tab = self.tab_view.tab("🔧 Версии")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            tab,
            text="🔧 Установленные версии",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(15, 10))

        self.versions_listbox = tk.Listbox(
            tab,
            bg="#1a1a2e",
            fg="#cdd6f4",
            selectbackground="#89b4fa",
            selectforeground="#1e1e2e",
            font=("Consolas", 11),
            height=10,
            relief="flat"
        )
        self.versions_listbox.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 10))

        btn_frame = ctk.CTkFrame(tab, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 15))

        refresh_btn = ctk.CTkButton(
            btn_frame,
            text="🔄 Обновить список",
            command=self.scan_and_update_versions,
            width=150,
            height=35,
            fg_color="#89b4fa",
            hover_color="#74c7ec",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        refresh_btn.grid(row=0, column=0, padx=(0, 10))

        delete_btn = ctk.CTkButton(
            btn_frame,
            text="🗑️ Удалить версию",
            command=self.delete_selected_version,
            width=150,
            height=35,
            fg_color="#f38ba8",
            hover_color="#e64553"
        )
        delete_btn.grid(row=0, column=1)

        info_frame = ctk.CTkFrame(tab, fg_color="transparent")
        info_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 10))

        self.version_info_label = ctk.CTkLabel(
            info_frame,
            text="💡 Нажмите 'Обновить список' для поиска новых версий\n"
                 "📁 Версии хранятся в: versions/",
            font=ctk.CTkFont(size=12),
            text_color="#89b4fa",
            justify="left"
        )
        self.version_info_label.pack(anchor="w")

    def create_files_tab(self):
        tab = self.tab_view.tab("📁 Файлы")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            tab,
            text="📁 Структура папки игры",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(15, 10))

        main_frame = ctk.CTkFrame(tab)
        main_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 10))
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)

        files_frame = ctk.CTkFrame(main_frame)
        files_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        files_frame.grid_columnconfigure(0, weight=1)
        files_frame.grid_rowconfigure(1, weight=1)

        info_text = f"""
📁 ПАПКА ИГРЫ: {MINECRAFT_DIR}

📁 ПАПКИ:

📁 assets/          Все игровые ресурсы: текстуры, звуки, шрифты, модели
📁 config/          Конфиги модов (Forge / Fabric / Quilt)
📁 libraries/       Библиотеки Java (LWJGL, логирование и пр.)
📁 logs/            Логи игры (latest.log — последний)
📁 mods/            Папка для установленных модов
📁 resourcepacks/   Ресурспаки (.zip или папки)
📁 runtime/         Встроенный Java Runtime
📁 saves/           Твои сохранения (миры)
📁 versions/        Установленные версии Minecraft

📄 ФАЙЛЫ:

???
        """

        info_display = ctk.CTkTextbox(files_frame, font=ctk.CTkFont(family="Consolas", size=11))
        info_display.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        info_display.insert("1.0", info_text)
        info_display.configure(state="disabled")

        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        btn_frame.grid_columnconfigure(0, weight=1)

        row1 = ctk.CTkFrame(btn_frame, fg_color="transparent")
        row1.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        row1.grid_columnconfigure(0, weight=1)

        btn_mods = ctk.CTkButton(
            row1,
            text="📦 Моды",
            command=lambda: self.open_subfolder("mods"),
            width=100,
            height=30,
            fg_color="#89b4fa",
            hover_color="#74c7ec"
        )
        btn_mods.grid(row=0, column=0, padx=5)

        btn_saves = ctk.CTkButton(
            row1,
            text="💾 Сохранения",
            command=lambda: self.open_subfolder("saves"),
            width=100,
            height=30,
            fg_color="#89b4fa",
            hover_color="#74c7ec"
        )
        btn_saves.grid(row=0, column=1, padx=5)

        btn_resourcepacks = ctk.CTkButton(
            row1,
            text="🎨 Ресурспаки",
            command=lambda: self.open_subfolder("resourcepacks"),
            width=100,
            height=30,
            fg_color="#89b4fa",
            hover_color="#74c7ec"
        )
        btn_resourcepacks.grid(row=0, column=2, padx=5)

        btn_config = ctk.CTkButton(
            row1,
            text="⚙️ Конфиги",
            command=lambda: self.open_subfolder("config"),
            width=100,
            height=30,
            fg_color="#89b4fa",
            hover_color="#74c7ec"
        )
        btn_config.grid(row=0, column=3, padx=5)

        row2 = ctk.CTkFrame(btn_frame, fg_color="transparent")
        row2.grid(row=1, column=0, sticky="ew")
        row2.grid_columnconfigure(0, weight=1)

        btn_logs = ctk.CTkButton(
            row2,
            text="📋 Логи",
            command=lambda: self.open_subfolder("logs"),
            width=100,
            height=30,
            fg_color="#f9e2af",
            hover_color="#f5d742",
            text_color="#1e1e2e"
        )
        btn_logs.grid(row=0, column=0, padx=5)

        btn_options = ctk.CTkButton(
            row2,
            text="⚙️ Настройки игры",
            command=lambda: self.open_file("options.txt"),
            width=100,
            height=30,
            fg_color="#f9e2af",
            hover_color="#f5d742",
            text_color="#1e1e2e"
        )
        btn_options.grid(row=0, column=1, padx=5)

        btn_servers = ctk.CTkButton(
            row2,
            text="🌐 Серверы",
            command=lambda: self.open_file("servers.dat"),
            width=100,
            height=30,
            fg_color="#f9e2af",
            hover_color="#f5d742",
            text_color="#1e1e2e"
        )
        btn_servers.grid(row=0, column=2, padx=5)

        btn_versions = ctk.CTkButton(
            row2,
            text="📂 Версии",
            command=lambda: self.open_subfolder("versions"),
            width=100,
            height=30,
            fg_color="#f9e2af",
            hover_color="#f5d742",
            text_color="#1e1e2e"
        )
        btn_versions.grid(row=0, column=3, padx=5)

        open_root_btn = ctk.CTkButton(
            btn_frame,
            text="📂 Открыть папку игры",
            command=self.open_game_folder,
            height=35,
            fg_color="#a6e3a1",
            hover_color="#7ecb8f",
            text_color="#1e1e2e",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        open_root_btn.grid(row=2, column=0, sticky="ew", padx=5, pady=(10, 0))

    def open_subfolder(self, folder_name):
        path = os.path.join(MINECRAFT_DIR, folder_name)
        if os.path.exists(path):
            os.startfile(path)
            self.log(f"📂 Открыта папка: {folder_name}")
        else:
            try:
                os.makedirs(path, exist_ok=True)
                os.startfile(path)
                self.log(f"📂 Создана и открыта папка: {folder_name}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось открыть папку:\n{e}")
                self.log(f"❌ Ошибка открытия папки {folder_name}: {e}")

    def open_file(self, filename):
        path = os.path.join(MINECRAFT_DIR, filename)
        if os.path.exists(path):
            try:
                os.startfile(path)
                self.log(f"📄 Открыт файл: {filename}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось открыть файл:\n{e}")
                self.log(f"❌ Ошибка открытия файла {filename}: {e}")
        else:
            messagebox.showinfo("Информация",
                                f"Файл {filename} не найден\n\nВозможно, он будет создан после запуска игры.")
            self.log(f"ℹ️ Файл не найден: {filename}")

    def create_settings_tab(self):
        tab = self.tab_view.tab("⚙️ Настройки")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        settings_frame = ctk.CTkFrame(tab)
        settings_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        settings_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            settings_frame,
            text="📁 Путь к файлам игры",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=15, pady=(15, 5))

        path_entry = ctk.CTkEntry(
            settings_frame,
            font=ctk.CTkFont(family="Consolas", size=11),
            state="readonly"
        )
        path_entry.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 15))
        path_entry.insert(0, os.path.abspath(MINECRAFT_DIR))

        ctk.CTkLabel(
            settings_frame,
            text="ℹ️ О программе",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=2, column=0, sticky="w", padx=15, pady=(0, 5))

        about_text = f"""
IONUX Launcher - Minecraft Launcher

Версия: 1.0 (CustomTkinter)
Разработчик: IONUX

Особенности:
• Автоматическая установка Java
• Установка модов через Modrinth
• Установка Vanilla/Fabric/Forge/OptiFine
• Автоматическое сканирование установленных версий
• Автоматическое создание профилей (profile.json)
• Управление версиями
• Доступ к структуре папки игры
• Несколько офлайн-аккаунтов
• Настройка выделения памяти
• Современный дизайн

📁 Папка игры:
{os.path.abspath(MINECRAFT_DIR)}
        """

        about_display = ctk.CTkTextbox(settings_frame, font=ctk.CTkFont(family="Consolas", size=11))
        about_display.grid(row=3, column=0, sticky="nsew", padx=15, pady=(0, 15))
        about_display.insert("1.0", about_text)
        about_display.configure(state="disabled")

        open_btn = ctk.CTkButton(
            settings_frame,
            text="📂 Открыть папку с игрой",
            command=self.open_game_folder,
            width=200
        )
        open_btn.grid(row=4, column=0, pady=(0, 15))

        settings_frame.grid_rowconfigure(3, weight=1)

    def show_install_popular_versions(self):
        versions = ["1.21", "1.20.4", "1.20.1", "1.19.2", "1.18.2", "1.17.1", "1.16.5", "1.15.2", "1.12.2", "1.8.9"]

        dialog = ctk.CTkToplevel(self)
        dialog.title("Популярные версии")
        dialog.geometry("250x350")
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Выберите версию:", font=ctk.CTkFont(size=13)).pack(pady=(15, 10))

        listbox = tk.Listbox(
            dialog,
            bg="#1a1a2e",
            fg="#cdd6f4",
            selectbackground="#89b4fa",
            font=("Consolas", 12)
        )
        listbox.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        for v in versions:
            listbox.insert("end", v)

        def select():
            selection = listbox.curselection()
            if selection:
                self.install_version_entry.delete(0, "end")
                self.install_version_entry.insert(0, versions[selection[0]])
                dialog.destroy()

        ctk.CTkButton(
            dialog,
            text="Выбрать",
            command=select
        ).pack(pady=(0, 15))

    def select_installer_file(self):
        file_path = filedialog.askopenfilename(
            title="Выберите установщик клиента",
            filetypes=[
                ("JAR файлы", "*.jar"),
                ("Все файлы", "*.*")
            ]
        )

        if file_path:
            if file_path.lower().endswith('.exe'):
                messagebox.showwarning(
                    "Предупреждение",
                    "Вы выбрали .exe файл!\n\n"
                    "Для установки OptiFine используйте .jar версию установщика.\n"
                    "Скачайте установщик (.jar) с официального сайта."
                )
                self.selected_installer_path = None
                self.install_file_label.configure(
                    text="❌ Неверный формат! Используйте .jar файл",
                    text_color="#f38ba8"
                )
                return

            self.selected_installer_path = file_path
            filename = os.path.basename(file_path)
            self.install_file_label.configure(
                text=f"✅ Выбран: {filename}",
                text_color="#a6e3a1"
            )
            self.log(f"📂 Выбран файл: {file_path}")

    # =================================================================
    # УСТАНОВКА КЛИЕНТОВ - ИСПРАВЛЕННАЯ
    # =================================================================

    def install_selected_client(self):
        install_type = self.install_type_var.get()
        version = self.install_version_entry.get().strip()

        if not version:
            messagebox.showwarning("Ошибка", "Введите версию Minecraft")
            return

        # Для OptiFine нужен файл установщика
        if install_type == "optifine":
            if not hasattr(self, 'selected_installer_path') or not self.selected_installer_path:
                messagebox.showwarning("Ошибка", "Сначала выберите файл установщика OptiFine")
                return

            if self.selected_installer_path.lower().endswith('.exe'):
                messagebox.showwarning(
                    "Ошибка",
                    "Для установки OptiFine используйте .jar версию установщика!\n"
                    "Скачайте установщик (.jar) с официального сайта."
                )
                return

        self.log(f"📦 Установка {install_type} {version}")
        self.install_btn.configure(state="disabled", text="⏳ УСТАНОВКА...")
        self.install_progressbar.start_animation()
        self.install_status_label.configure(text="Установка...", text_color="#f9e2af")

        def do_install():
            success = False

            # Очищаем временные папки перед установкой
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

            # Очищаем временные папки после установки
            cleanup_forge_temp()

        threading.Thread(target=do_install, daemon=True).start()

    def install_vanilla(self, version):
        try:
            log_message(f"📦 Установка Vanilla {version}...")
            mll.install.install_minecraft_version(version, MINECRAFT_DIR, mll_callback)
            log_message(f"✅ Vanilla {version} установлен!")
            create_profile(version, f"Vanilla {version}")
            return True
        except Exception as e:
            log_message(f"❌ Ошибка: {e}")
            return False

    def install_fabric(self, version):
        try:
            log_message(f"📦 Установка Fabric {version}...")

            # Устанавливаем Fabric напрямую через MLL (как в рабочей версии)
            mll.fabric.install_fabric(version, MINECRAFT_DIR, callback=mll_callback)

            log_message(f"✅ Fabric {version} установлен!")

            # Находим установленную версию Fabric
            installed = mll.utils.get_installed_versions(MINECRAFT_DIR)
            fabric_versions = [v for v in installed if "fabric" in v["id"].lower()]
            if fabric_versions:
                fabric_id = fabric_versions[-1]["id"]
                create_profile(fabric_id, f"Fabric {version}")
                log_message(f"✅ Профиль создан для: {fabric_id}")
            else:
                # Если не нашли, создаём профиль с предполагаемым именем
                fabric_id = f"fabric-loader-0.14.22-{version}"
                create_profile(fabric_id, f"Fabric {version}")

            self.scan_and_update_versions()
            return True

        except Exception as e:
            log_message(f"❌ Ошибка установки Fabric: {e}")
            return False

    def install_forge(self, version):
        try:
            log_message(f"📦 Установка Forge {version}...")

            # Шаг 1: Устанавливаем оригинальную версию Minecraft
            log_message(f"📦 Шаг 1/2: Установка оригинальной версии {version}...")
            mll.install.install_minecraft_version(version, MINECRAFT_DIR, callback=mll_callback)
            log_message(f"✅ Оригинальная версия установлена!")

            # Шаг 2: Находим версию Forge
            log_message(f"🔍 Поиск Forge для версии {version}...")
            forge_version = mll.forge.find_forge_version(version)
            if forge_version is None:
                log_message(f"❌ Forge не поддерживает версию {version}")
                return False

            log_message(f"✅ Найдена Forge версия: {forge_version}")

            # Шаг 3: Устанавливаем Forge поверх оригинальной версии
            log_message(f"📦 Шаг 2/2: Установка Forge {forge_version}...")
            mll.forge.install_forge_version(forge_version, MINECRAFT_DIR, callback=mll_callback)

            # Получаем ID версии Forge для запуска
            installed = mll.utils.get_installed_versions(MINECRAFT_DIR)
            forge_versions = [v for v in installed if "forge" in v["id"].lower()]
            if forge_versions:
                forge_id = forge_versions[-1]["id"]
                create_profile(forge_id, f"Forge {version}")
                log_message(f"✅ Профиль создан для: {forge_id}")

            log_message(f"✅ Forge {version} установлен!")
            self.scan_and_update_versions()
            return True

        except Exception as e:
            log_message(f"❌ Ошибка установки Forge: {e}")
            return False

    def install_optifine(self, version):
        try:
            installer_path = self.selected_installer_path

            if not installer_path.lower().endswith('.jar'):
                messagebox.showerror("Ошибка", "Для установки OptiFine используйте .jar версию установщика!")
                return False

            java_path = get_java_for_version(version)

            log_message(f"📦 Установка OptiFine {version}...")
            log_message(f"☕ Используется Java: {java_path}")

            # Устанавливаем Vanilla если нет
            versions_dir = os.path.join(MINECRAFT_DIR, "versions", version)
            if not os.path.exists(versions_dir):
                log_message(f"📦 Установка Vanilla {version}...")
                mll.install.install_minecraft_version(version, MINECRAFT_DIR, mll_callback)
                log_message(f"✅ Vanilla {version} установлен!")

            cmd = [java_path, "-jar", installer_path]
            log_message(f"⚙️ Запуск: {' '.join(cmd)}")

            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0,
                timeout=300
            )

            if process.returncode != 0:
                log_message(f"⚠️ Ошибка: {process.stderr}")
                return False

            log_message(f"✅ OptiFine {version} установлен!")
            self.scan_and_update_versions()
            return True

        except subprocess.TimeoutExpired:
            log_message("❌ Таймаут установки OptiFine")
            return False
        except Exception as e:
            log_message(f"❌ Ошибка: {e}")
            return False

    def scan_and_update_versions(self):
        self.versions_listbox.delete(0, tk.END)
        versions = scan_versions()
        self.installed_versions = versions

        profiles = load_profiles()

        version_names = [v["id"] for v in versions]
        self.version_combo.configure(values=version_names)
        if version_names:
            self.version_combo.set(version_names[0])
        else:
            self.version_combo.set("Нет версий")

        if not versions:
            self.versions_listbox.insert(0, "⚠️ Нет установленных версий")
            self.versions_listbox.insert(1, "💡 Нажмите 'Обновить список' для поиска")
            self.versions_listbox.insert(2, "📁 Или добавьте версии в папку versions/")
        else:
            for v in versions:
                type_icon = {
                    "vanilla": "📦",
                    "fabric": "🧵",
                    "forge": "🔥",
                    "optifine": "⚡"
                }.get(v["type"], "❓")

                profile_mark = "✅" if v["id"] in profiles else "❌"

                files_status = ""
                if v["jar"] and v["json"]:
                    files_status = "✅"
                elif v["json"] and not v["jar"]:
                    files_status = "📄 (только .json)"
                elif v["jar"]:
                    files_status = "⚠️ (нет .json)"
                else:
                    files_status = "❌ (нет файлов)"

                self.versions_listbox.insert(tk.END, f"{type_icon} {v['id']} {profile_mark} {files_status}")

        self.log(f"📋 Найдено версий: {len(versions)}")

    def delete_selected_version(self):
        selection = self.versions_listbox.curselection()
        if not selection:
            messagebox.showwarning("Ошибка", "Выберите версию для удаления")
            return

        if selection[0] >= len(self.installed_versions):
            return

        version = self.installed_versions[selection[0]]
        version_id = version["id"]

        if not messagebox.askyesno("Подтверждение", f"Удалить версию {version_id}?"):
            return

        try:
            shutil.rmtree(version["path"])
            delete_profile(version_id)
            self.log(f"🗑️ Версия удалена: {version_id}")
            self.scan_and_update_versions()
            messagebox.showinfo("Успешно", f"Версия {version_id} удалена")
        except Exception as e:
            self.log(f"❌ Ошибка удаления: {e}")
            messagebox.showerror("Ошибка", f"Не удалось удалить версию: {e}")

    def on_mod_select(self, event):
        selection = self.results_listbox.curselection()
        if selection:
            index = selection[0]
            if index < len(self.search_results):
                self.selected_mod_index = index
                mod = self.search_results[index]
                self.selected_mod_label.configure(
                    text=f"✅ Выбран: {mod.get('title', '?')}",
                    text_color="#a6e3a1"
                )
                self.install_mod_btn.configure(state="normal")
                self.mod_status_label.configure(text="Готов к установке", text_color="#a6e3a1")
            else:
                self.selected_mod_label.configure(text="❌ Мод не выбран", text_color="#f38ba8")
                self.install_mod_btn.configure(state="disabled")
                self.mod_status_label.configure(text="Выберите мод из списка", text_color="#89b4fa")
        else:
            self.selected_mod_label.configure(text="❌ Мод не выбран", text_color="#f38ba8")
            self.install_mod_btn.configure(state="disabled")

    def search_mods(self):
        query = self.mod_search_entry.get().strip()
        if not query:
            messagebox.showwarning("Ошибка", "Введите название мода")
            return

        game_ver = self.mod_version_entry.get().strip()
        mod_loader = self.mod_loader_var.get()

        self.log(f"🔍 Поиск модов: '{query}' для {game_ver} ({mod_loader})")

        self.results_listbox.delete(0, tk.END)
        self.search_results = []
        self.selected_mod_index = -1
        self.selected_mod_label.configure(text="⏳ Поиск...", text_color="#f9e2af")
        self.install_mod_btn.configure(state="disabled")

        def do_search():
            try:
                results = search_mods(query, game_ver, mod_loader)
                self.search_results = results
                self.after(0, lambda: self.update_search_results(results))
            except Exception as e:
                self.log(f"❌ Ошибка поиска: {e}")
                self.after(0, lambda: self.results_listbox.insert(0, f"❌ Ошибка: {e}"))

        threading.Thread(target=do_search, daemon=True).start()

    def update_search_results(self, results):
        self.results_listbox.delete(0, tk.END)

        if not results:
            self.results_listbox.insert(0, "❌ Моды не найдены")
            self.selected_mod_label.configure(text="❌ Моды не найдены", text_color="#f38ba8")
            self.mod_status_label.configure(text="Моды не найдены", text_color="#f38ba8")
            self.log("❌ Моды не найдены")
            return

        for i, mod in enumerate(results[:20]):
            title = mod.get('title', '?')
            downloads = mod.get('downloads', 0)
            self.results_listbox.insert(tk.END, f"{i + 1:2}. {title[:30]:<30} ⬇ {downloads:,}")

        self.selected_mod_label.configure(text=f"✅ Найдено {len(results)} модов", text_color="#a6e3a1")
        self.mod_status_label.configure(text="Выберите мод из списка", text_color="#89b4fa")
        self.log(f"✅ Найдено {len(results)} модов")

    def install_selected_mod(self):
        if self.selected_mod_index < 0 or self.selected_mod_index >= len(self.search_results):
            messagebox.showwarning("Ошибка", "Сначала выберите мод из списка")
            return

        mod = self.search_results[self.selected_mod_index]
        project_id = mod.get('project_id')
        game_ver = self.mod_version_entry.get().strip()
        mod_loader = self.mod_loader_var.get()

        mod_title = mod.get('title', '?')

        self.log(f"📦 Установка мода: {mod_title}")
        self.install_mod_btn.configure(state="disabled", text="⏳ УСТАНОВКА...")
        self.mod_progressbar.start_animation()
        self.mod_status_label.configure(text="Установка...", text_color="#f9e2af")
        self.mod_progressbar.configure(progress_color="#f9e2af")

        def do_install():
            try:
                success, result = install_mod(project_id, game_ver, mod_loader)

                self.after(0, lambda: self.install_mod_btn.configure(state="normal", text="📥 УСТАНОВИТЬ ВЫБРАННЫЙ МОД"))
                self.after(0, lambda: self.mod_progressbar.stop_animation())

                if success:
                    self.log(f"✅ Мод установлен: {result}")
                    self.mod_progressbar.set(1.0)
                    self.mod_progressbar.configure(progress_color="#a6e3a1")
                    self.mod_status_label.configure(text="✅ Установлено!", text_color="#a6e3a1")
                    messagebox.showinfo("Успешно", f"Мод '{mod_title}' успешно установлен!")
                    self.refresh_mods_list()
                else:
                    self.log(f"❌ Ошибка: {result}")
                    self.mod_progressbar.set(0.3)
                    self.mod_progressbar.configure(progress_color="#f38ba8")
                    self.mod_status_label.configure(text=f"❌ Ошибка", text_color="#f38ba8")
                    messagebox.showerror("Ошибка", f"Не удалось установить мод: {result}")
            except Exception as e:
                self.log(f"❌ Ошибка: {e}")
                self.mod_progressbar.set(0.3)
                self.mod_progressbar.configure(progress_color="#f38ba8")
                self.mod_status_label.configure(text=f"❌ Ошибка", text_color="#f38ba8")
                messagebox.showerror("Ошибка", f"Не удалось установить мод: {e}")

            self.after(2000, lambda: self.reset_mod_progress())

        threading.Thread(target=do_install, daemon=True).start()

    def reset_mod_progress(self):
        self.mod_progressbar.set(0)
        self.mod_progressbar.configure(progress_color="#f9e2af")
        self.mod_status_label.configure(text="Готов к установке", text_color="#a6e3a1")

    def refresh_mods_list(self):
        self.installed_listbox.delete(0, tk.END)
        mods = list_mods()

        if not mods:
            self.installed_listbox.insert(0, "⚠️ Нет установленных модов")
        else:
            for mod in mods:
                try:
                    size = os.path.getsize(os.path.join(get_mods_folder(), mod)) / (1024 * 1024)
                    self.installed_listbox.insert(tk.END, f"📦 {mod} ({size:.1f} MB)")
                except:
                    self.installed_listbox.insert(tk.END, f"📦 {mod}")

        self.log(f"📋 Установлено модов: {len(mods)}")

    def delete_selected_mod(self):
        selection = self.installed_listbox.curselection()
        if not selection:
            messagebox.showwarning("Ошибка", "Выберите мод для удаления")
            return

        mod_text = self.installed_listbox.get(selection[0])
        mod_name = mod_text.split("(")[0].replace("📦", "").strip()

        if mod_name and delete_mod(mod_name):
            self.log(f"🗑️ Мод удалён: {mod_name}")
            self.refresh_mods_list()
            messagebox.showinfo("Успешно", f"Мод '{mod_name}' удалён!")

    def refresh_accounts(self):
        accounts = load_accounts()
        values = [acc['username'] for acc in accounts]
        self.account_combo.configure(values=values)
        if values:
            self.account_combo.set(values[0])
        else:
            self.account_combo.set("Нет аккаунтов")

    def refresh_accounts_listbox(self):
        self.accounts_listbox.configure(state="normal")
        self.accounts_listbox.delete("1.0", "end")
        accounts = load_accounts()
        if not accounts:
            self.accounts_listbox.insert("end", "⚠️ Нет добавленных аккаунтов\n")
            self.accounts_listbox.insert("end", "💡 Нажмите 'Добавить аккаунт' для создания")
        else:
            for acc in accounts:
                created = acc.get('created', 'давно')
                self.accounts_listbox.insert("end", f"👤 {acc['username']}  |  {created}\n")
        self.accounts_listbox.configure(state="disabled")

    def add_account_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Новый аккаунт")
        dialog.geometry("350x220")
        dialog.resizable(False, False)
        dialog.grab_set()

        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 350) // 2
        y = self.winfo_y() + (self.winfo_height() - 220) // 2
        dialog.geometry(f"+{x}+{y}")

        ctk.CTkLabel(
            dialog,
            text="➕ Создание нового аккаунта",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=(20, 10))

        ctk.CTkLabel(dialog, text="Введите никнейм:", font=ctk.CTkFont(size=13)).pack(pady=(0, 5))

        entry = ctk.CTkEntry(
            dialog,
            width=250,
            height=35,
            placeholder_text="Игровой никнейм"
        )
        entry.pack(pady=10)
        entry.focus()

        def save():
            username = entry.get().strip()
            if not username:
                messagebox.showwarning("Ошибка", "Введите никнейм!")
                return
            success, message = add_account(username)
            if success:
                self.refresh_accounts()
                self.refresh_accounts_listbox()
                dialog.destroy()
                self.log(f"✅ Аккаунт '{username}' добавлен")
                messagebox.showinfo("Успешно", f"Аккаунт '{username}' создан!")
            else:
                messagebox.showwarning("Ошибка", message)

        def on_enter(event):
            save()

        entry.bind("<Return>", on_enter)

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=15)

        create_btn = ctk.CTkButton(
            btn_frame,
            text="✅ Создать",
            command=save,
            fg_color="#a6e3a1",
            hover_color="#7ecb8f",
            text_color="#1e1e2e",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=35,
            width=120
        )
        create_btn.grid(row=0, column=0, padx=5)

        cancel_btn = ctk.CTkButton(
            btn_frame,
            text="❌ Отмена",
            command=dialog.destroy,
            fg_color="#f38ba8",
            hover_color="#e64553",
            font=ctk.CTkFont(size=13),
            height=35,
            width=120
        )
        cancel_btn.grid(row=0, column=1, padx=5)

    def delete_selected_account(self):
        accounts = load_accounts()
        if not accounts:
            messagebox.showwarning("Ошибка", "Нет аккаунтов для удаления")
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Удаление аккаунта")
        dialog.geometry("350x200")
        dialog.resizable(False, False)
        dialog.grab_set()

        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 350) // 2
        y = self.winfo_y() + (self.winfo_height() - 200) // 2
        dialog.geometry(f"+{x}+{y}")

        ctk.CTkLabel(
            dialog,
            text="🗑️ Выберите аккаунт для удаления:",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=(20, 15))

        values = [acc['username'] for acc in accounts]
        combo = ctk.CTkComboBox(
            dialog,
            values=values,
            width=250,
            state="readonly"
        )
        combo.pack(pady=10)
        if values:
            combo.set(values[0])

        def delete():
            username = combo.get()
            if username:
                success, result = delete_account(username)
                if success:
                    self.refresh_accounts()
                    self.refresh_accounts_listbox()
                    dialog.destroy()
                    self.log(f"🗑️ Аккаунт '{username}' удалён")
                    messagebox.showinfo("Успешно", f"Аккаунт '{username}' удалён!")
                else:
                    messagebox.showerror("Ошибка", result)

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=15)

        delete_btn = ctk.CTkButton(
            btn_frame,
            text="🗑️ Удалить",
            command=delete,
            fg_color="#f38ba8",
            hover_color="#e64553",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=35,
            width=120
        )
        delete_btn.grid(row=0, column=0, padx=5)

        cancel_btn = ctk.CTkButton(
            btn_frame,
            text="❌ Отмена",
            command=dialog.destroy,
            fg_color="#89b4fa",
            hover_color="#74c7ec",
            font=ctk.CTkFont(size=13),
            height=35,
            width=120
        )
        cancel_btn.grid(row=0, column=1, padx=5)

    def open_game_folder(self):
        if os.path.exists(MINECRAFT_DIR):
            os.startfile(MINECRAFT_DIR)
        else:
            try:
                os.makedirs(MINECRAFT_DIR, exist_ok=True)
                os.startfile(MINECRAFT_DIR)
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось открыть папку:\n{e}")

    def log(self, message):
        if hasattr(self, 'console_text'):
            self.console_text.configure(state="normal")
            timestamp = time.strftime("%H:%M:%S")
            self.console_text.insert("end", f"[{timestamp}] {message}\n")
            self.console_text.see("end")
            self.console_text.configure(state="disabled")
            self.update_idletasks()

    def clear_console(self):
        if hasattr(self, 'console_text'):
            self.console_text.configure(state="normal")
            self.console_text.delete("1.0", "end")
            self.console_text.configure(state="disabled")

    # ================================================================
    # ЗАПУСК ИГРЫ
    # ================================================================

    def launch_game(self):
        if self.is_launching:
            return

        account_name = self.account_combo.get()
        if not account_name or account_name == "Нет аккаунтов":
            messagebox.showwarning("Ошибка", "Выберите аккаунт")
            return

        accounts = load_accounts()
        account = None
        for acc in accounts:
            if acc['username'] == account_name:
                account = acc
                break

        if not account:
            messagebox.showwarning("Ошибка", "Аккаунт не найден")
            return

        version = self.version_combo.get()
        if not version or version == "Нет версий":
            messagebox.showwarning("Ошибка", "Выберите версию Minecraft")
            return

        ram = self.ram_var.get()

        self.is_launching = True
        self.launch_btn.configure(state="disabled", text="⏳ ЗАГРУЗКА...")

        self.launch_progressbar.start_animation()
        self.launch_status_label.configure(text="Подготовка...", text_color="#f9e2af")
        self.launch_progressbar.configure(progress_color="#f9e2af")

        self.log("=" * 50)
        self.log(f"🚀 Запуск Minecraft {version} с аккаунтом: {account['username']}")
        self.log(f"💾 Память: {ram}")
        self.log(f"📁 Папка игры: {MINECRAFT_DIR}")
        self.log("=" * 50)

        def do_launch():
            try:
                java_path = get_java_for_version(version)
                log_message(f"☕ Используется Java: {java_path}")

                # Проверяем установку через scan_versions
                versions = scan_versions()
                is_installed = False
                for v in versions:
                    if v["id"] == version:
                        is_installed = True
                        break

                if not is_installed:
                    log_message(f"📦 Установка Minecraft {version}...")
                    try:
                        mll.install.install_minecraft_version(version, MINECRAFT_DIR, mll_callback)
                        log_message("✅ Версия установлена!")
                        create_profile(version, f"Vanilla {version}")
                    except Exception as e:
                        log_message(f"⚠️ Ошибка установки: {e}")
                else:
                    log_message(f"✅ Версия {version} уже установлена")

                # Создаём профиль если нет
                profiles = load_profiles()
                if not isinstance(profiles, dict):
                    profiles = {}

                if version not in profiles:
                    create_profile(version, f"Profile {version}")

                log_message(f"🚀 Запуск Minecraft {version}...")
                log_message("⏳ Ожидание закрытия игры...")

                # Используем MLL для запуска
                options = {
                    "username": account["username"],
                    "jvmArguments": [f"-Xmx{ram}", "-Xms512M"]
                }
                if java_path and java_path != "java":
                    options["executablePath"] = java_path

                # Получаем команду через MLL
                command = mll.command.get_minecraft_command(version, MINECRAFT_DIR, options)
                log_message(f"⚙️ Команда запуска: {' '.join(command)}")

                # Запускаем игру
                if platform.system() == "Windows":
                    process = subprocess.Popen(
                        command,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )

                    # Читаем вывод
                    while True:
                        output = process.stdout.readline()
                        if output == '' and process.poll() is not None:
                            break
                        if output:
                            log_message(f"📤 {output.strip()}")

                    process.wait()
                else:
                    subprocess.run(command)

                log_message("✅ Игра завершена!")
                self.reset_launch_state()

            except Exception as e:
                log_message(f"❌ Ошибка: {e}")
                import traceback
                log_message(traceback.format_exc())
                self.launch_status_label.configure(text="Ошибка запуска", text_color="#f38ba8")
                self.launch_progressbar.configure(progress_color="#f38ba8")
                self.launch_progressbar.stop_animation()
                self.launch_btn.configure(state="normal", text="🚀 ЗАПУСТИТЬ ИГРУ")
                self.is_launching = False
                messagebox.showerror("Ошибка", f"Произошла ошибка:\n{str(e)}")

        threading.Thread(target=do_launch, daemon=True).start()

    def reset_launch_state(self):
        self.launch_progressbar.stop_animation()
        self.launch_progressbar.set(1.0)
        self.launch_progressbar.configure(progress_color="#a6e3a1")
        self.launch_status_label.configure(text="✅ Игра завершена", text_color="#a6e3a1")
        self.launch_btn.configure(state="normal", text="🚀 ЗАПУСТИТЬ ИГРУ")
        self.is_launching = False

        self.after(3000, lambda: self.launch_progressbar.set(0))
        self.after(3000, lambda: self.launch_status_label.configure(text="Готов к запуску", text_color="#a6e3a1"))
        self.after(3000, lambda: self.launch_progressbar.configure(progress_color="#f9e2af"))


# ===================================================================
# 9. ЗАПУСК
# ===================================================================

if __name__ == "__main__":
    ensure_game_folder_structure()
    app = LauncherApp()
    app.mainloop()