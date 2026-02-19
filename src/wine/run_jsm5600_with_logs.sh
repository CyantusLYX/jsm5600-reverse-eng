#!/usr/bin/env bash
set -u

BACKEND="virtual"
if [[ $# -ge 1 ]]; then
  case "$1" in
    virtual|bridge|none)
      BACKEND="$1"
      shift
      ;;
    *)
      echo "Usage: $0 [virtual|bridge|none]"
      exit 2
      ;;
  esac
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

JSM_BASE="${JSM_BASE:-/home/cyantus/sd/sem/jsm5600}"
WINE_BIN="${WINE_BIN:-/opt/wine-jsm5600/bin/wine}"
WINESERVER_BIN="${WINESERVER_BIN:-/opt/wine-jsm5600/bin/wineserver}"
WINEPREFIX_PATH="${WINEPREFIX_PATH:-${JSM_BASE}/WINDOWS32}"
JSM_EXE="${JSM_EXE:-${JSM_BASE}/SEM/Jsm5600.exe}"

LOG_ROOT="${LOG_ROOT:-${REPO_ROOT}/logs/jsm5600}"
mkdir -p "${LOG_ROOT}"
RUN_ID="$(date +%Y%m%d_%H%M%S)"
RUN_DIR="${LOG_ROOT}/${RUN_ID}"
mkdir -p "${RUN_DIR}"

WINE_LOG="${RUN_DIR}/wine.log"
BACKEND_LOG="${RUN_DIR}/${BACKEND}.log"
META_LOG="${RUN_DIR}/meta.txt"

WINEDEBUG_VALUE="${WINEDEBUG_VALUE:--all,+aspi,+seh,+loaddll}"
WINEDLLOVERRIDES_VALUE="${WINEDLLOVERRIDES_VALUE:-wnaspi32=n,b;vb40016=n,b;oc25=n,b}"

BACKEND_PID=""
cleanup() {
  if [[ -n "${BACKEND_PID}" ]]; then
    kill "${BACKEND_PID}" >/dev/null 2>&1 || true
    wait "${BACKEND_PID}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

if [[ ! -x "${WINE_BIN}" ]]; then
  echo "wine binary not executable: ${WINE_BIN}"
  exit 1
fi

if [[ ! -x "${WINESERVER_BIN}" ]]; then
  echo "wineserver binary not executable: ${WINESERVER_BIN}"
  exit 1
fi

if [[ ! -f "${JSM_EXE}" ]]; then
  echo "Jsm5600.exe not found: ${JSM_EXE}"
  exit 1
fi

if [[ "${BACKEND}" == "virtual" ]]; then
  python3 "${SCRIPT_DIR}/virtual_sem.py" >"${BACKEND_LOG}" 2>&1 &
  BACKEND_PID="$!"
  sleep 1
elif [[ "${BACKEND}" == "bridge" ]]; then
  python3 "${SCRIPT_DIR}/bridge_sem.py" >"${BACKEND_LOG}" 2>&1 &
  BACKEND_PID="$!"
  sleep 1
fi

{
  echo "run_id=${RUN_ID}"
  echo "backend=${BACKEND}"
  echo "jsm_base=${JSM_BASE}"
  echo "wine_bin=${WINE_BIN}"
  echo "wineserver_bin=${WINESERVER_BIN}"
  echo "wineprefix=${WINEPREFIX_PATH}"
  echo "jsm_exe=${JSM_EXE}"
  echo "winedebug=${WINEDEBUG_VALUE}"
  echo "winedlloverrides=${WINEDLLOVERRIDES_VALUE}"
  echo "run_dir=${RUN_DIR}"
} >"${META_LOG}"

echo "Logs: ${RUN_DIR}"
echo "Launching JSM5600..."

WINEPREFIX="${WINEPREFIX_PATH}" \
WINESERVER="${WINESERVER_BIN}" \
WINEDEBUG="${WINEDEBUG_VALUE}" \
WINEDLLOVERRIDES="${WINEDLLOVERRIDES_VALUE}" \
"${WINE_BIN}" "${JSM_EXE}" 2>&1 | tee "${WINE_LOG}"

exit ${PIPESTATUS[0]}
