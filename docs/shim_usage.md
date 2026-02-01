# SEM32.DLL Wine Shim & Emulator Guide

This guide explains how to run `SEM32.DLL` on Linux using Wine, with a "Shim" DLL (`wnaspi32.dll`) that redirects hardware commands to a Python-based emulator.

## 1. Prerequisites

*   **Linux Machine** (Dev Machine)
*   **Wine** (Installed and configured)
*   **Wine Development Tools** (`winegcc`, `wine32-tools`, `libwine-dev:i386`)
    *   *Note: Since `SEM32.DLL` is 32-bit, you MUST have the 32-bit Wine development libraries installed.*
*   **Python 3**

## 2. Directory Structure

Ensure the files are in `content/src/wine/`:
*   `fake_wnaspi32.c`: The C source for the Shim DLL.
*   `virtual_sem.py`: The Python Emulator.
*   `test_sem.c`: A test harness to load the DLL.
*   `Makefile`: Build script.

## 3. Compilation

1.  Navigate to the directory:
    ```bash
    cd content/src/wine
    ```
2.  Compile the Shim and Test Harness:
    ```bash
    make
    ```
    **CRITICAL**: `SEM32.DLL` is a 32-bit application. You **MUST** compile `wnaspi32.dll` as 32-bit.
    If you see errors like `/usr/bin/ld: cannot find -lkernel32` or `winegcc: /usr/bin/gcc failed`, it means your development environment lacks 32-bit Wine libraries.
    
    **Fix (Debian/Ubuntu):**
    ```bash
    sudo dpkg --add-architecture i386
    sudo apt update
    sudo apt install wine32-tools libwine-dev:i386 gcc-multilib
    ```

## 4. Running the Emulator

1.  Open a terminal and start the Python Emulator:
    ```bash
    python3 virtual_sem.py
    ```
    *It will listen on `127.0.0.1:9999`.*

## 5. Running the Test Harness (Wine)

1.  Open a new terminal.
2.  Run the test harness using Wine, forcing it to use our local `wnaspi32.dll`:
    ```bash
    WINEDLLOVERRIDES="wnaspi32=n" wine test_sem.exe
    ```
3.  **Expected Output**:
    *   **Emulator Console**: You should see "Client connected", followed by hex dumps of commands (`CMD: GetHardwareID`, `CMD: GetVacuumStatus`, etc.).
    *   **Wine Console**: You should see logs from `[FakeASPI]` indicating connection success and `SEM32.DLL` loading successfully.

## 6. Running with Real Software (VB App)

1.  Copy `SEM32.DLL` and your VB Application (e.g., `SemMain.exe`) into the same directory as `wnaspi32.dll` (or copy `wnaspi32.dll.so` to the app directory).
2.  Run the application:
    ```bash
    WINEDLLOVERRIDES="wnaspi32=n" wine SemMain.exe
    ```

## 7. Troubleshooting

*   **"Socket creation failed"**: Ensure `virtual_sem.py` is running and port 9999 is free.
*   **"Bad EXE format"**: You are likely trying to load a 32-bit DLL into a 64-bit process or vice versa. Ensure you compiled with `-m32` (or `i686-w64-mingw32-gcc`).
*   **Permissions**: Ensure your user has permissions to open sockets.
*   **"Connection to emulator failed"**:
    *   Verify the Python script is running: `ps aux | grep python`
    *   Verify the port is open: `netstat -an | grep 9999`
    *   Check `emulator.log` for connection attempts.
*   **Protocol Mismatches**:
    *   The Shim includes logic to "drain" excess bytes if the Emulator sends more data than the DLL requested. This is crucial for protocol synchronization. If you see "Drained X bytes" in the logs, it is working as intended.


## 8. Switching to Real Hardware (Adaptec 2940A)

You have two options to communicate with real hardware:

### Option A: The Python Bridge (Recommended for "Pure WOW64" / Compilation Issues)
If you cannot compile 32-bit C code due to missing libraries (common on Arch Pure WOW64), use this method.

1.  **Use the "Fake/Network" Shim**: Ensure `wnaspi32.dll` is the version compiled from `fake_wnaspi32.c` (this uses TCP to talk to localhost:9999).
2.  **Run the Bridge Script**:
    Instead of `virtual_sem.py` (which emulates a device), run `bridge_sem.py`. This script connects to the real `/dev/sg` device and forwards commands from the DLL.
    ```bash
    sudo python3 bridge_sem.py
    ```
    *Note: Sudo is required to access /dev/sg* unless your user is in the `disk` or `optical` group.*
    
    The script will auto-detect a JEOL/SEM device. If it fails, specify the device manually:
    ```bash
    sudo python3 bridge_sem.py /dev/sg2
    ```

### Option B: Native Passthrough Shim (Higher Performance)

This requires compiling `passthrough_wnaspi32.c` into a DLL that directly calls Linux `ioctl`.

1.  **Prerequisites**:
    *   You MUST have 32-bit development libraries installed (`lib32-glibc`, `lib32-gcc-libs`).
    *   On Arch Linux:
        ```bash
        sudo pacman -S lib32-glibc lib32-gcc-libs
        ```
    *   If `winegcc` fails with `gnu/stubs-32.h: No such file`, you are missing these libraries.

2.  **Compile**:
    ```bash
    winegcc -m32 -O2 -shared -o wnaspi32.dll passthrough_wnaspi32.c
    ```

3.  **Deploy**:
    Copy the resulting `wnaspi32.dll` (and `wnaspi32.dll.so` if created) to the application directory.

---


# Target Host Deployment Guide

This guide describes how to deploy the SEM software and SCSI Shim on the target Linux machine with the actual hardware.

## 1. Prerequisites

*   **OS**: Linux (Arch/Debian/etc) with 32-bit support enabled.
*   **Hardware**: Adaptec 2940A SCSI Card installed and recognized (`ls /dev/sg*` should show devices).
*   **Software**: Wine (32-bit capable), `make`, `gcc`.

## 2. Directory Setup

The application expects to be located in `C:\JEOL\SEM`.

```bash
# Create the directory structure in Wine prefix
mkdir -p ~/.wine/drive_c/JEOL/SEM

# Copy extracted application files
cp -r /path/to/extracted_sem/* ~/.wine/drive_c/JEOL/SEM/
```

## 3. Library Setup (Critical)

The application relies on legacy VB6 and MFC libraries. Ensure `mfc40.dll`, `mfc42.dll`, `msvcrt.dll`, `msvbvm60.dll` are present in `C:\JEOL\SEM` or `C:\windows\system32`.

Register the OCX controls:

```bash
cd ~/.wine/drive_c/JEOL/SEM
export WINEPATH="C:\\JEOL\\SEM;C:\\windows\\system32"
export WINEDLLOVERRIDES="mfc40,mfc42,msvcrt,dwspy32=n,b"

for f in *.OCX *.ocx; do
    wine regsvr32 /s "$f"
done
```

## 4. Building the Shim (Real Hardware)

*Currently, the source code (`fake_wnaspi32.c`) implements a TCP bridge to a Python emulator. To use real hardware, you must implement the SCSI Passthrough logic.*

1.  **Develop `passthrough_wnaspi32.c`**:
    *   Use `ioctl(fd, SG_IO, &io_hdr)` to send the CDBs received from the DLL directly to the Linux SCSI driver.
    *   Map ASPI Target/LUN ID to `/dev/sgN` (e.g. Target 0 -> `/dev/sg1`).

2.  **Compile**:
    ```bash
    winegcc -m32 -O2 -shared -o wnaspi32.dll passthrough_wnaspi32.c
    ```

3.  **Deploy**:
    Copy `wnaspi32.dll` and `wnaspi32.dll.so` to `~/.wine/drive_c/JEOL/SEM/`.

## 5. Running the Application

```bash
cd ~/.wine/drive_c/JEOL/SEM
export WINEPATH="C:\\JEOL\\SEM;C:\\windows\\system32"
# Force native shim and legacy libs
WINEDLLOVERRIDES="wnaspi32=n;mfc40,mfc42,msvcrt,dwspy32=n,b" wine Jsm5000.exe
```
