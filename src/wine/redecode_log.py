import json
import os
import re
import sys


class ProtocolDecoder:
    def __init__(self, definition_file="protocol_definitions.json"):
        # Resolve path relative to script
        base_dir = os.path.dirname(os.path.abspath(__file__))
        if not os.path.isabs(definition_file):
            definition_file = os.path.join(base_dir, definition_file)
        self.definitions = self.load_definitions(definition_file)

    def load_definitions(self, filename):
        if not os.path.exists(filename):
            print(f"Warning: Protocol definitions not found at {filename}")
            return {}
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error: Failed to load protocol definitions: {e}")
            return {}

    def decode(self, cdb_bytes, data_bytes=None, direction="CMD"):
        if not cdb_bytes:
            return "EmptyCDB", "WARN"

        opcode_hex = f"0x{cdb_bytes[0]:02X}"
        cmd_name = f"Unknown({opcode_hex})"
        cmd_level = "WARN"

        # 1. Base Lookup
        if "groups" in self.definitions and opcode_hex in self.definitions["groups"]:
            group = self.definitions["groups"][opcode_hex]
            cmd_name = f"{group.get('name', 'Unknown')}_Generic"

            if "matches" in group:
                for rule in group["matches"]:
                    match_map = rule.get("match", {})
                    matched = True
                    for offset_str, hex_val in match_map.items():
                        offset = int(offset_str)
                        if offset >= len(cdb_bytes) or cdb_bytes[offset] != int(
                            hex_val, 16
                        ):
                            matched = False
                            break

                    if matched:
                        cmd_name = rule.get("name", "UnknownGroupCmd")
                        cmd_level = rule.get("level", "INFO")
                        break

        # 2. Deep Decoding for 0xFA (Tunneling)
        if cdb_bytes[0] == 0xFA:
            if direction == "CMD" and data_bytes and len(data_bytes) > 0:
                # Try to decode the inner command
                inner_name, inner_level = self.decode(data_bytes, direction="CMD")
                if "Unknown" not in inner_name:
                    cmd_name = f"FA<{inner_name}>"
                    cmd_level = inner_level
            elif direction == "RES":
                cmd_name = "FA_Response"

        return cmd_name, cmd_level


def redecode_log(log_path, def_path):
    decoder = ProtocolDecoder(def_path)
    output_path = log_path.replace(".log", "_decoded.log")

    # Updated pattern to handle various spacings and the "DATA" part
    log_pattern = re.compile(
        r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+) \[(.*?)\] \[(.*?)\] (.*?) \| CDB: (.*?) (\| DATA: (.*?) )?-> Status=(.*)$"
    )

    with open(log_path, "r") as f, open(output_path, "w") as out:
        for line in f:
            line = line.strip()
            match = log_pattern.match(line)
            if match:
                ts, level, direction, old_name, cdb_str, data_full, data_hex, status = (
                    match.groups()
                )

                try:
                    cdb_bytes = bytes.fromhex(cdb_str.strip())

                    # For deep decoding, we need data_bytes if available
                    data_bytes = None
                    if data_hex and "Empty" not in data_hex:
                        # Strip "..." if present
                        clean_hex = data_hex.split("...")[0].strip()
                        try:
                            data_bytes = bytes.fromhex(clean_hex)
                        except:
                            pass

                    new_name, new_level = decoder.decode(
                        cdb_bytes, data_bytes=data_bytes, direction=direction.strip()
                    )

                    # Format levels and status
                    status_val = int(status)
                    final_level = new_level
                    if status_val != 0 and status_val != 1:
                        if status_val == 4:
                            final_level = "ERR "
                        else:
                            final_level = "WARN"

                    # Reconstruct line
                    data_part = data_full if data_full else "| DATA: [Empty] "
                    new_line = f"{ts} [{final_level:<4}] [{direction:<4}] {new_name:<25} | CDB: {cdb_str.strip():<20} {data_part}-> Status={status}\n"
                    out.write(new_line)
                except Exception as e:
                    out.write(line + "\n")
            else:
                out.write(line + "\n")

    print(f"Redecoded log saved to: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 redecode_log.py <log_file> <definitions_json>")
        sys.exit(1)

    redecode_log(sys.argv[1], sys.argv[2])
