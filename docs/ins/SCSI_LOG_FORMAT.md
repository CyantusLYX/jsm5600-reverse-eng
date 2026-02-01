# SCSI Command Log Format

## Overview
This document defines the log format used by the `bridge_sem.py` tool to record SCSI transactions between the Wine Shim and the SEM Hardware.

The logs are designed to be human-readable and machine-parsable, facilitating protocol analysis and debugging.

## Log File Location
Logs are stored in the `logs/` directory relative to the script execution path.
File naming convention: `sem_session_YYYYMMDD_HHMMSS.log`

## Log Entry Format
Each line represents a single command transaction or a system event.

```text
[TIMESTAMP] [LEVEL] [DIRECTION] [OPCODE_NAME] | CDB: [HEX_BYTES] | DATA: [HEX_BYTES/Snippet] -> STATUS
```

### Fields

1.  **TIMESTAMP**: ISO 8601 time (HH:MM:SS.mmm)
2.  **LEVEL**:
    *   `INFO`: Normal operation.
    *   `WARN`: Unknown commands or non-zero status.
    *   `ERR`: IOCTL failures or Exceptions.
    *   `DBG`: Detailed trace (optional).
3.  **DIRECTION**:
    *   `CMD`: Command from PC to Hardware
    *   `RES`: Response from Hardware to PC
    *   `EVT`: System Event (Connect, Disconnect, Error)
3.  **OPCODE_NAME**: Decoded name of the command (e.g., `SetSpeed`, `GetVacuumStatus`). If unknown, shows `Unknown(0xXX)`.
4.  **CDB**: The raw Command Descriptor Block in hex (e.g., `00 01 00 04 ...`).
5.  **DATA**: (Optional) Data sent or received.
    *   For `CMD`, this is Data Out.
    *   For `RES`, this is Data In.
    *   Large buffers may be truncated or summarized `[96 bytes]`.
6.  **STATUS**: The SCSI Status byte (0=Good, 2=Check Condition, etc.).

## Example Log

```text
2023-10-27 10:00:01.123 [EVT] Bridge Started on 127.0.0.1:9999
2023-10-27 10:00:05.456 [EVT] Client Connected: ('127.0.0.1', 54321)
2023-10-27 10:00:05.500 [CMD] INQUIRY         | CDB: 12 00 00 00 60 00 | len=96
2023-10-27 10:00:05.510 [RES] INQUIRY         | DATA: 03 00 02 02 ... JEOL SEM ... | OK
2023-10-27 10:00:06.000 [CMD] GetVacuumStatus | CDB: C4 01 00 04
2023-10-27 10:00:06.005 [RES] GetVacuumStatus | DATA: 03 00 00 00 (Ready) | OK
2023-10-27 10:00:07.100 [CMD] Unknown(0x99)   | CDB: 99 00 00 00
2023-10-27 10:00:07.105 [RES] Unknown(0x99)   | DATA: [Empty] | CheckCondition
```

## Parsing Rules (Reference)
*   Lines starting with `#` are comments.
*   The separator `|` divides major sections.
