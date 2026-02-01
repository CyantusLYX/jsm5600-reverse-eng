import json
import os


def test_decoder():
    def_path = "/home/cyantus/sd/sem/sem/5610E_Ver526/jsm5600-reverse-eng/src/wine/protocol_definitions.json"
    with open(def_path, "r") as f:
        defs = json.load(f)

    cdb = bytes.fromhex("12 00 00 00 24 00")
    opcode_hex = f"0x{cdb[0]:02X}"
    print(f"Opcode Hex: {opcode_hex}")
    print(f"Opcode in groups: {opcode_hex in defs['groups']}")

    if opcode_hex in defs["groups"]:
        group = defs["groups"][opcode_hex]
        print(f"Group: {group['name']}")
        for rule in group.get("matches", []):
            print(f"Checking rule: {rule['name']}")
            match_map = rule.get("match", {})
            matched = True
            for offset_str, hex_val in match_map.items():
                offset = int(offset_str)
                byte_val = cdb[offset]
                target_val = int(hex_val, 16)
                if byte_val != target_val:
                    matched = False
                    break
            if matched:
                print(f"MATCHED: {rule['name']}")
                return
    print("NOT MATCHED")


test_decoder()
