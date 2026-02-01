import json
import os
import re
import sys


class ProtocolDecoder:
    def __init__(self, definition_file="protocol_definitions.json"):
        self.definitions = self.load_definitions(definition_file)

    def load_definitions(self, filename):
        if not os.path.exists(filename):
            return {}
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except:
            return {}

    def decode(self, cdb_bytes):
        if not cdb_bytes or len(cdb_bytes) == 0:
            return "Empty", "INFO"

        opcode_hex = f"0x{cdb_bytes[0]:02X}"

        # Logic for normal commands
        if "groups" in self.definitions and opcode_hex in self.definitions["groups"]:
            group = self.definitions["groups"][opcode_hex]
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
                        return rule.get("name", "Unknown"), rule.get("level", "INFO")
            return f"{group.get('name', 'Unknown')}_Generic", "WARN"
        return f"Unknown({opcode_hex})", "WARN"


def redecode_log(log_path, def_path):
    decoder = ProtocolDecoder(def_path)
    output_path = log_path.replace(".log", "_deep.log")

    # Updated pattern to handle varying spaces and potential trailing dots
    log_pattern = re.compile(
        r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+) \[(.*?)\] \[(.*?)\] (.*?) \| CDB: (.*?) \| DATA: (.*?) -> Status=(.*)$"
    )

    with open(log_path, "r") as f, open(output_path, "w") as out:
        for line in f:
            line = line.strip()
            match = log_pattern.match(line)
            if match:
                ts, level, direction, old_name, cdb_str, data_str, status = (
                    match.groups()
                )
                try:
                    cdb_bytes = bytes.fromhex(cdb_str.strip())

                    # 1. Base decoding
                    cmd_name, cmd_level = decoder.decode(cdb_bytes)
                    if cdb_bytes[0] == 0xFA:
                        cmd_name = "Generic10_Wrapper"

                    # 2. Deep decoding for 0xFA
                    if cdb_bytes[0] == 0xFA and "[Empty]" not in data_str:
                        if direction == "CMD":
                            # Only decode DATA as command if it's being SENT
                            hex_data = data_str.split("...")[0].strip()
                            try:
                                payload_bytes = bytes.fromhex(hex_data)
                                inner_name, inner_level = decoder.decode(payload_bytes)
                                if "Unknown" not in inner_name:
                                    cmd_name = f"FA<{inner_name}>"
                                    cmd_level = inner_level
                            except:
                                pass
                        else:
                            # It's a RESPONSE, label as response data
                            cmd_name = "FA_Response"

                    # 3. Final level override for errors
                    try:
                        status_val = int(status)
                        if status_val != 0 and status_val != 1:
                            cmd_level = "ERR " if status_val == 4 else "WARN"
                    except:
                        pass

                    new_line = f"{ts} [{cmd_level:<4}] [{direction:<4}] {cmd_name:<25} | CDB: {cdb_str.strip():<20} | DATA: {data_str.strip():<30} -> Status={status}\n"
                    out.write(new_line)
                except:
                    out.write(line + "\n")
            else:
                out.write(line + "\n")
    print(f"Deep decoded log saved to: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 deep_decode.py <log_file> <definitions_json>")
        sys.exit(1)
    redecode_log(sys.argv[1], sys.argv[2])
