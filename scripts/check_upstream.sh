#!/usr/bin/env bash
# check_upstream.sh — тонкая обёртка над check_upstream.py.
#
# Вся логика аудита живёт в Python (это Python-проект, и Python-версия
# покрыта тестами). Этот скрипт существует, чтобы аудит запускался одной
# командой и на Windows (Git Bash), и на Linux/macOS.
#
#   ./scripts/check_upstream.sh            # полный отчёт
#   ./scripts/check_upstream.sh --quiet    # только вердикт, одной строкой
#   ./scripts/check_upstream.sh --no-fetch # не ходить в сеть
#
# Коды возврата: 0 — обновляться не нужно, 1 — нужен разбор,
#                2 — ошибка окружения, 3 — нет сети.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY_SCRIPT="$SCRIPT_DIR/check_upstream.py"

if [ ! -f "$PY_SCRIPT" ]; then
  echo "ОШИБКА: не найден $PY_SCRIPT" >&2
  exit 2
fi

# Ищем интерпретатор: сначала системный python, потом launcher (Windows).
PY=""
for cand in python python3 py; do
  if command -v "$cand" >/dev/null 2>&1; then
    PY="$cand"
    break
  fi
done

if [ -z "$PY" ]; then
  echo "ОШИБКА: не найден интерпретатор Python (python / python3 / py)." >&2
  echo "Запусти напрямую:  python scripts/check_upstream.py" >&2
  exit 2
fi

# На Windows Git Bash превращает пути в /c/... — Python их не поймёт,
# поэтому отдаём относительный путь, а рабочий каталог не меняем.
exec "$PY" "$PY_SCRIPT" "$@"
