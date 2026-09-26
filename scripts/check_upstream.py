#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Аудит апстрима перед rebase — форк 67launcher-safe.

Форк держится на зеркале апстрима KotiPlayYT/67launcher, но не доверяет ему
слепо. Скрипт НИЧЕГО не применяет к рабочей копии: только читает историю
и печатает отчёт. Решение о rebase всегда принимает человек.

Три вопроса:
  1. Менялся ли код?        main.py, requirements.txt, setup.py, pyproject.toml
  2. Появились ли .exe и т.п.?
  3. Менялся ли адрес релея? relay.active.txt

Если все три — пусто, апстрим тронул только resources/ (картинки/звуки),
и обновляться не нужно: форк остаётся на своём коммите.

Использование:
    python scripts/check_upstream.py            # полный отчёт
    python scripts/check_upstream.py --quiet    # только вердикт, одной строкой
    python scripts/check_upstream.py --no-fetch # не ходить в сеть

Коды возврата:
    0 — апстрим чисто, обновляться не нужно (или мы уже на последней версии)
    1 — апстрим что-то менял, нужен разбор
    2 — ошибка окружения / нет remote
    3 — сеть недоступна
"""
import argparse
import os
import re
import subprocess
import sys

UPSTREAM = os.environ.get("UPSTREAM", "upstream")
REMOTE_BRANCH = os.environ.get("UPSTREAM_BRANCH", "main")
OUR_REF = os.environ.get("OUR_REF", "main")

# Изменение любого из них = «надо разбираться»
CODE_FILES = [
    "main.py", "requirements.txt", "setup.py", "pyproject.toml",
    "Pipfile", "setup.cfg", "constraints.txt",
]
RELAY_FILE = "relay.active.txt"

# Расширения, которые не должны просто так появляться
EXEC_EXTS = [
    ".exe", ".dll", ".jar", ".zip", ".scr", ".com", ".bat", ".cmd",
    ".ps1", ".vbs", ".msi", ".pif", ".cpl", ".hta", ".reg",
]

# Медиафайлы — безобидный шум
MEDIA_EXTS = {".gif", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".mp3", ".wav", ".ogg", ".ico"}

# Опасные вызовы, если они добавляются в коде.
# Список широкий намеренно: цена ложного срабатывания (посмотреть лишний раз)
# намного ниже цены пропуска (вредный код в форке).
DANGER_PATTERNS = [
    # выполнение кода
    "eval(", "exec(", "compile(", "__import__", "importlib", "marshal",
    "pickle.loads", "getattr(", "globals()[", "locals()[", "ctypes",
    # процессы и файловая система
    "os.startfile", "startfile", "subprocess", "Popen", "os.system",
    "os.popen", "run(", "check_output", "winreg", "powershell", "cmd.exe",
    # сеть
    "urllib", "urlopen", "requests.get", "requests.post", "requests.put",
    "requests.delete", "socket.socket", "httpx", "aiohttp", "ftplib",
    "smtplib", "webbrowser.open",
    # секреты
    "accounts.json", "accessToken", "refreshToken", "access_token",
    "refresh_token", "password", "credentials",
    # ввод-вывод и логгер
    "pyautogui", "mss.", "ImageGrab", "GetWindows", "keylog",
]


def die(code, msg):
    sys.stderr.write(msg.rstrip() + "\n")
    sys.exit(code)


def git(*args, check=True):
    """Запускает git и возвращает stdout. check=False -> (rc, out, err).

    -c core.quotePath=false обязателен: иначе git экранирует не-ASCII пути
    как "resources/gif/\\320\\273...gif" — с кавычками, и проверка
    расширения .gif ломается (ложное «не-медиафайл»)."""
    p = subprocess.run(["git", "-c", "core.quotePath=false"] + list(args),
                       capture_output=True)
    out = p.stdout.decode("utf-8", "replace")
    err = p.stderr.decode("utf-8", "replace")
    if check and p.returncode != 0:
        die(2, "ОШИБКА git %s:\n%s" % (" ".join(args), err))
    return p.returncode, out, err


def ext_of(path):
    return os.path.splitext(path)[1].lower()


def name_status(base, tip, *paths):
    """-> список (status, path) для добавленных/изменённых/удалённых."""
    rc, out, _ = git("diff", "--name-status", base, tip, "--", *paths, check=False)
    rows = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0]
        # переименования: R100\old\tnew
        if status[0] in ("R", "C") and len(parts) >= 3:
            status, path = status[0], parts[2]
        else:
            path = parts[1]
        rows.append((status, path))
    return rows


def changed(base, tip, path):
    rc, _, _ = git("diff", "--quiet", base, tip, "--", path, check=False)
    return rc != 0


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--quiet", action="store_true", help="только вердикт одной строкой")
    ap.add_argument("--no-fetch", action="store_true", help="не ходить в сеть")
    args = ap.parse_args()

    def say(*a):
        if not args.quiet:
            print(*a)

    def hr():
        say("-" * 70)

    if git("rev-parse", "--git-dir", check=False)[0] != 0:
        die(2, "ОШИБКА: не git-репозиторий")
    if git("remote", "get-url", UPSTREAM, check=False)[0] != 0:
        die(2, "ОШИБКА: нет remote '%s'.\nДобавь:  git remote add %s https://github.com/KotiPlayYT/67launcher"
             % (UPSTREAM, UPSTREAM))

    hr()
    say("Аудит апстрима %s/%s" % (UPSTREAM, REMOTE_BRANCH))
    hr()

    if not args.no_fetch:
        say("Обновляю список коммитов (git fetch)...")
        rc, _, err = git("fetch", "--quiet", UPSTREAM, REMOTE_BRANCH, check=False)
        if rc != 0:
            die(3, "ОШИБКА: git fetch не удался — нет сети или удалённый репозиторий недоступен.\n%s" % err)
        say("fetch OK")
        say("")

    rc, base, err = git("merge-base", OUR_REF, "%s/%s" % (UPSTREAM, REMOTE_BRANCH), check=False)
    base = base.strip()
    if not base:
        hint = ""
        if args.no_fetch:
            hint = ("\nПодсказка: с --no-fetch скрипт не видит новые remote-ы. "
                    "Сначала выполни:  git fetch %s %s" % (UPSTREAM, REMOTE_BRANCH))
        die(2, "ОШИБКА: нет общей базы с %s/%s — форк не от этого апстрима?%s"
             % (UPSTREAM, REMOTE_BRANCH, hint))
    tip_sha = git("rev-parse", "%s/%s" % (UPSTREAM, REMOTE_BRANCH))[1].strip()

    say("Наш HEAD          : %s" % git("rev-parse", "--short", OUR_REF)[1].strip())
    say("Апстрим           : %s" % git("rev-parse", "--short", tip_sha)[1].strip())
    say("Уже впитано (base): %s" % base[:7])
    say("")

    if base == tip_sha:
        say("Новых коммитов в апстриме нет — мы на последней версии.")
        say("")
        hr()
        if args.quiet:
            print("Апстрим чисто, обновляться не нужно")
        return 0

    say("Новые коммиты в апстриме:")
    for line in git("log", "--oneline", "%s..%s" % (base, tip_sha))[1].splitlines():
        say("    " + line)
    say("")
    hr()

    # ---------- 1. КОД ----------
    code_changed = [f for f in CODE_FILES if changed(base, tip_sha, f)]
    py_rows = name_status(base, tip_sha, "*.py")
    new_py = [p for s, p in py_rows if s.startswith("A")]
    del_py = [p for s, p in py_rows if s.startswith("D")]

    say("1) ИЗМЕНЕНИЯ КОДА")
    if code_changed:
        say("    ИЗМЕНЕНЫ: %s" % ", ".join(code_changed))
    else:
        say("    код не менялся")
    if new_py:
        say("    НОВЫЕ .py — прочитай их глазами:")
        for p in new_py:
            say("        %s" % p)
    if del_py:
        say("    УДАЛЁННЫЕ .py:")
        for p in del_py:
            say("        %s" % p)

    # точечный diff по опасным зонам
    if changed(base, tip_sha, "main.py"):
        say("")
        say("   Опасные добавления в main.py:")
        rc, diff, _ = git("diff", "--unified=0", base, tip_sha, "--", "main.py")
        found = set()
        for line in diff.splitlines():
            if not line.startswith("+") or line.startswith("+++"):
                continue
            low = line.lower()
            for pat in DANGER_PATTERNS:
                if pat.lower() in low:
                    found.add(line.strip()[:150])
                    break
            # голый URL — всегда показываем, это главный канал утечки
            for m in re.findall(r"https?://[^\s\"'<>)]+", line):
                found.add("URL: %s" % m)
        if found:
            for f in sorted(found):
                say("       %s" % f)
        else:
            say("       подозрительных добавлений не найдено")
    say("")

    # ---------- 2. ИСПОЛНЯЕМЫЕ ----------
    say("2) ИСПОЛНЯЕМЫЕ / АРХИВНЫЕ ФАЙЛЫ")
    found_exec = []
    for st, path in name_status(base, tip_sha):
        if st.startswith("D"):
            continue
        if ext_of(path) in EXEC_EXTS:
            found_exec.append(path)
    if found_exec:
        say("    НАЙДЕНЫ (не применяй, разбирайся):")
        for p in found_exec:
            say("        %s" % p)
    else:
        say("    новых исполняемых/архивных файлов нет")

    say("")
    say("   Проверка resources/ (по расширению):")
    res_rows = [p for st, p in name_status(base, tip_sha, "resources/*")
                if not st.startswith("D")]
    res_bad = [p for p in res_rows if ext_of(p) not in MEDIA_EXTS]
    if res_bad:
        say("    В resources/ есть НЕ-медиафайлы:")
        for p in res_bad:
            say("        %s" % p)
    else:
        say("    в resources/ только медиафайлы (%s)"
            % ", ".join(sorted({ext_of(p) for p in res_rows}) or "—"))
    say("")

    # ---------- 3. РЕЛЕЙ ----------
    say("3) АДРЕС РЕЛЕЯ")
    if changed(base, tip_sha, RELAY_FILE):
        say("    %s ИЗМЕНЁН:" % RELAY_FILE)
        for line in git("diff", base, tip_sha, "--", RELAY_FILE)[1].splitlines():
            say("        " + line)
        rc, content, _ = git("show", "%s:%s" % (tip_sha, RELAY_FILE), check=False)
        if content:
            say("    Новый адрес релея:")
            for line in content.splitlines():
                say("          %s" % line.strip())
    else:
        say("    %s не менялся" % RELAY_FILE)
    say("")
    hr()

    # ---------- ВЕРДИКТ ----------
    assets_only = (
        not code_changed and not found_exec and not res_bad
        and not changed(base, tip_sha, RELAY_FILE)
        and not new_py and not del_py
    )

    if assets_only:
        if args.quiet:
            print("Апстрим чисто, обновляться не нужно")
            return 0
        say("ВЕРДИКТ: АПСТРИМ ЧИСТО, ОБНОВЛЯТЬСЯ НЕ НУЖНО")
        say("  Изменились только resources/ (картинки и звуки).")
        say("  main.py, requirements.txt, setup.py, pyproject.toml и relay.active.txt")
        say("  не тронуты, исполняемых файлов нет.")
        say("  Форк остаётся на своём коммите.")
        hr()
        return 0

    if args.quiet:
        print("Апстрим изменил код/релей — нужен разбор")
        return 1

    say("ВЕРДИКТ: АПСТРИМ ЧТО-ТО МЕНЯЛ — РАЗБИРАТЬСЯ, НЕ МЕРЖИТЬ АВТОМАТИЧЕСКИ")
    if code_changed:
        say("  изменён код: %s" % ", ".join(code_changed))
    if new_py:
        say("  добавлены .py-файлы — прочитай их глазами")
    if found_exec:
        say("  появились исполняемые/архивные файлы")
    if res_bad:
        say("  в resources/ появились не-медиафайлы")
    if changed(base, tip_sha, RELAY_FILE):
        say("  сменился адрес релея — сообщения пойдут на другой сервер")
    hr()
    return 1


if __name__ == "__main__":
    sys.exit(main())
