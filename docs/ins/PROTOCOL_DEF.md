# Protocol Definition Format (JSON)

This document describes the structure of `protocol_definitions.json`, which is used by the `bridge_sem.py` script to decode SCSI CDBs.

## JSON Structure

The root is an object containing `groups` and `opcodes` (optional global opcodes).

```json
{
  "groups": {
    "0x00": {
      "name": "Group0_ScanControl",
      "commands": [ ... ]
    },
    "0xC4": {
      "name": "GroupC4_Status",
      "commands": [ ... ]
    }
  }
}
```

### Command Definition

Each command entry defines pattern matching rules.

```json
{
  "name": "CommandName",
  "level": "INFO", 
  "match": {
    "byte_index": "expected_value",
    "4": "0x04"
  },
  "decode": [
    { "offset": 6, "type": "uint16", "name": "Speed" }
  ]
}
```

*   `name`: Human readable name.
*   `level`: (Optional) Log level (`LOG`, `INFO`, `WARN`, `ERROR`). Defaults to `INFO`.
*   `match`: Key-value pairs where key is CDB byte offset and value is the hex string to match.
*   `decode`: (Optional) Rules to extract parameters from CDB (for Commands) or Data (for Responses).
