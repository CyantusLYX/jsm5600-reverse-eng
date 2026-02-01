import json
import os
import re
import sys


class ProtocolDecoder:
    def __init__(self, definition_file="protocol_definitions.json"):
        self.definitions = self.load_definitions(definition_file)

    def load_definitions(self, filename):
        if not os.path.exists(filename):
            print(f"Error: Protocol definitions not found at {filename}")
            return {}
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error: Failed to load protocol definitions: {e}")
            return {}

    def decode(self, cdb_bytes):
        if not cdb_bytes:
            return "EmptyCDB", "WARN"

        opcode_hex = f"0x{cdb_bytes[0]:02X}"

        if "groups" in self.definitions and opcode_hex in self.definitions["groups"]:
            group = self.definitions["groups"][opcode_hex]
            if "matches" in group:
                for rule in group["matches"]:
                    match_map = rule.get("match", {})
                    matched = True
                    for offset_str, hex_val in match_map.items():
                        offset = int(offset_str)
                        if offset >= len(cdb_bytes):
                            matched = False
                            break
                        byte_val = cdb_bytes[offset]
                        try:
                            target_val = int(hex_val, 16)
                            if byte_val != target_val:
                                matched = False
                                break
                        except:
                            matched = False
                            break

                    if matched:
                        return rule.get("name", "UnknownGroupCmd"), rule.get(
                            "level", "INFO"
                        )

            return f"{group.get('name', 'Unknown')}_Generic", "WARN"

        return f"Unknown({opcode_hex})", "WARN"


def redecode_log(log_path, def_path):
    decoder = ProtocolDecoder(def_path)
    output_path = log_path.replace(".log", "_decoded.log")

    # Format: [TIMESTAMP] [LEVEL] [DIRECTION] [NAME] | CDB: ... | DATA: ... -> Status=status
    # 2026-02-01 22:04:24.498 [INFO] [RES ] GetMag               | CDB: C8 50 00 04          | DATA: 50 00 00 00  -> Status=1
    log_pattern = re.compile(
        r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+) \[(.*?)\] \[(.*?)\] (.*?) \| CDB: (.*?) (\| DATA: .*? )?-> Status=(.*)$"
    )

    with open(log_path, "r") as f, open(output_path, "w") as out:
        for line in f:
            match = log_pattern.match(line)
            if match:
                ts, level, direction, old_name, cdb_str, data_part, status = (
                    match.groups()
                )

                # Parse CDB
                try:
                    cdb_bytes = bytes.fromhex(cdb_str.strip())
                    new_name, new_level = decoder.decode(cdb_bytes)

                    # Construct new line
                    # We keep the original timestamp and direction
                    # We update name and potentially level (if status is success)

                    # Formatting logic similar to bridge_sem.py
                    status_val = int(status)
                    final_level = new_level
                    if status_val != 0 and status_val != 1:
                        if status_val == 4:
                            final_level = "ERR "
                        else:
                            final_level = "WARN"

                    if not data_part:
                        data_part = "| DATA: [Empty] "

                    new_line = f"{ts} [{final_level:<4}] [{direction:<4}] {new_name:<20} | CDB: {cdb_str.strip():<20} {data_part}-> Status={status}\n"
                    out.write(new_line)
                except Exception as e:
                    # If parsing fails, write original line
                    out.write(line)
            else:
                # Meta lines or non-matching lines
                out.write(line)

    print(f"Decoded log saved to: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 redecode_log.py <log_file> <definitions_json>")
        sys.exit(1)

    redecode_log(sys.argv[1], sys.argv[2])
