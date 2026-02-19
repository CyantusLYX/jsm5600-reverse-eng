#!/bin/bash
# Wrapper to run JSM5600 with the patched 16-bit kernel and ASPI DLLs
# This is necessary because we couldn't overwrite the system Wine files.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILD_DIR="${REPO_ROOT}/packaging/arch/wine-jsm5600/src/build32"

# Paths to our patched DLLs
KRNL386_DIR="${BUILD_DIR}/dlls/krnl386.exe16/i386-windows"
WINASPI_DIR="${BUILD_DIR}/dlls/winaspi.dll16/i386-windows"

export WINEDLLPATH="${KRNL386_DIR}:${WINASPI_DIR}:${WINEDLLPATH:-}"

echo "Running JSM5600 with patched DLLs from: ${BUILD_DIR}"
echo "WINEDLLPATH=${WINEDLLPATH}"

# Run the original script
"${REPO_ROOT}/src/wine/run_jsm5600_with_logs.sh" "$@"
