#!/bin/bash
# ==============================================================================
# entrypoint.sh — запуск GUI-приложения в контейнере.
#
# Поднимает:
#   - Xvfb        (виртуальный дисплей :99)
#   - fluxbox     (оконный менеджер)
#   - x11vnc      (VNC-сервер, порт 5900)
#   - FinanceApp  (python -m APP.main) — в foreground
# ==============================================================================

set -e

DISPLAY_NUM="${DISPLAY:-:99}"
SCREEN="${SCREEN_WIDTH:-1280}x${SCREEN_HEIGHT:-800}x${SCREEN_DEPTH:-24}"
VNC_PORT="${VNC_PORT:-5900}"

# ── 1. Виртуальный дисплей ─────────────────────────────────────────────────
echo "[entrypoint] Starting Xvfb on ${DISPLAY_NUM} (${SCREEN})..."
Xvfb "${DISPLAY_NUM}" \
    -screen 0 "${SCREEN}" \
    -ac +extension GLX +render -noreset &
XVFB_PID=$!

# Ждём готовности X-сервера (до 10 секунд)
for _ in $(seq 1 30); do
    if xdpyinfo -display "${DISPLAY_NUM}" >/dev/null 2>&1; then
        echo "[entrypoint] Xvfb ready."
        break
    fi
    sleep 0.3
done

# ── 2. Оконный менеджер ────────────────────────────────────────────────────
echo "[entrypoint] Starting fluxbox..."
fluxbox &
FLUXBOX_PID=$!

# ── 3. VNC-сервер ──────────────────────────────────────────────────────────
echo "[entrypoint] Starting x11vnc on port ${VNC_PORT}..."
x11vnc -display "${DISPLAY_NUM}" \
    -forever -shared -nopw \
    -rfbport "${VNC_PORT}" \
    -quiet &
X11VNC_PID=$!

# ── 4. Cleanup при остановке контейнера ────────────────────────────────────
cleanup() {
    echo "[entrypoint] Shutting down..."
    kill "${FLUXBOX_PID}" "${X11VNC_PID}" "${XVFB_PID}" 2>/dev/null || true
    wait 2>/dev/null || true
}
trap cleanup TERM INT

# ── 5. Приложение (foreground) ─────────────────────────────────────────────
echo "[entrypoint] Starting FinanceApp..."
exec python -m APP.main