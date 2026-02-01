# Wine Shim Design for SEM32.DLL

## 1. Overview
This document details the architecture for running `SEM32.DLL` on Linux using Wine, bridging its ASPI (Advanced SCSI Programming Interface) calls to the Linux native SCSI subsystem (`sg` driver).

## 2. The Problem
`SEM32.DLL` communicates with the SEM hardware using the **ASPI** protocol, specifically by importing `WNASPI32.DLL` and calling `SendASPI32Command` (Ordinal 2).
It sends Vendor Specific SCSI commands (CDBs) defined in our reverse-engineered protocol.

## 3. Solution Strategy
We will utilize Wine's built-in ASPI support but verify it handles the specific "Vendor Specific" (Group 0-7) commands correctly. If Wine's built-in DLL fails, we will implement a custom `wnaspi32.dll` shim.

### 3.1. Architecture
```mermaid
graph TD
    A[VB App / SEM32.DLL] -->|ASPI Call (Ordinal 2)| B(Wine WNASPI32.DLL)
    B -->|IOCTL| C[Linux SG Driver]
    C -->|SCSI Command| D[SEM Hardware / Emulator]
```

## 4. ASPI Protocol Implementation

### 4.1. Key Functions
*   **SendASPI32Command (Ordinal 2)**: The core function.
    *   Input: `LPSRB` (Pointer to SCSI Request Block).
    *   SRB Structure (as seen in `FUN_10021aee`):
        ```c
        typedef struct {
            BYTE  SRB_Cmd;        // 0x02 = SC_EXEC_SCSI_CMD
            BYTE  SRB_Status;
            BYTE  SRB_HaId;       // Host Adapter ID
            BYTE  SRB_Flags;
            DWORD SRB_Hdr_Rsvd;
            BYTE  SRB_Target;     // Target ID
            BYTE  SRB_Lun;
            WORD  SRB_Rsvd1;
            DWORD SRB_BufLen;     // Data Buffer Length
            BYTE  *SRB_BufPointer;// Data Buffer Pointer
            BYTE  SRB_SenseLen;
            BYTE  SRB_CDBLen;     // CDB Length (6, 10, 12, 16)
            BYTE  SRB_HaStat;
            BYTE  SRB_TgtStat;
            void  (*SRB_PostProc)(); // Post routine or Event Handle
            void  *SRB_Rsvd2;
            BYTE  SRB_Rsvd3[16];
            BYTE  CDBByte[16];    // Command Data Block
        } SRB_ExecSCSICmd, *LPSRB_ExecSCSICmd;
        ```

### 4.2. Linux Mapping
The Shim must translate the `SRB` into a Linux `sg_io_hdr_t` structure.

*   **Interface**: `/dev/sgX` (SCSI Generic).
*   **Translation**:
    *   `SRB_CDBLen` -> `cmd_len`
    *   `CDBByte` -> `cmdp`
    *   `SRB_BufLen` -> `dxfer_len`
    *   `SRB_BufPointer` -> `dxferp`
    *   `SRB_Flags` (Direction) -> `dxfer_direction` (SG_DXFER_TO_DEV / FROM_DEV)

## 5. Implementation Plan

### Phase 1: Wine Configuration
1.  Enable Wine's ASPI layer.
    *   `regedit`: `HKEY_LOCAL_MACHINE\Software\Wine\Drivers\Wine\ASPI` -> `Enable`="Y"
2.  Map Linux SG devices to ASPI.
    *   Wine usually maps `/dev/sg0` -> HA 0, ID 0 (or similar).
3.  Test with `SEM32.DLL` inside Wine.

### Phase 2: Custom Shim (Fallback)
If Wine's ASPI strips non-standard CDBs (unlikely but possible):
1.  Compile a Linux shared object (`.so`) that exposes `SendASPI32Command`.
2.  Compile a dummy `wnaspi32.dll.so` for Wine that links to our implementation.
3.  Directly use `ioctl(fd, SG_IO, &io_hdr)`.

## 6. Hardware Emulator (Virtual SEM)
To test without physical hardware, we will build a **Python-based Virtual SEM** that mimics the hardware behavior.
*   **Role**: Acts as the "Device" receiving SCSI commands.
*   **Mechanism**:
    *   **Option A**: Use `targetcli` (LIO) to create a virtual SCSI target on Linux.
    *   **Option B (Simpler)**: Intercept the Shim's calls via a named pipe instead of `/dev/sg`.

**Recommended Path**: Build the **Python Emulator** first, talking via a Named Pipe. The Shim will detect if it's in "Emulation Mode" and write to the pipe instead of ASPI. This allows full protocol verification on a dev machine.

## 7. Action Items
1.  [ ] Create `virtual_sem.py`: A Python script that parses CDBs and returns mock responses (Status, Images).
2.  [ ] Create `fake_wnaspi32.c`: A simple DLL replacement that talks to `virtual_sem.py` via Named Pipes (`\\.\pipe\sem_emulator`).
3.  [ ] Run `SEM32.DLL` + `VB App` in Wine, using the fake DLL.
