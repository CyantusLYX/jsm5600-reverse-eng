import socket
import struct
import threading
import logging
import os
import fcntl
import sys
import ctypes
import json
import time
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - [SEM_BRIDGE] - %(message)s"
)
logger = logging.getLogger("BridgeSEM")

# --- SG IOCTL Definitions ---
SG_IO = 0x2285
SG_DXFER_NONE = -1
SG_DXFER_TO_DEV = -2
SG_DXFER_FROM_DEV = -3


class SgIoHdr(ctypes.Structure):
    _fields_ = [
        ("interface_id", ctypes.c_int),
        ("dxfer_direction", ctypes.c_int),
        ("cmd_len", ctypes.c_ubyte),
        ("mx_sb_len", ctypes.c_ubyte),
        ("iovec_count", ctypes.c_ushort),
        ("dxfer_len", ctypes.c_uint),
        ("dxferp", ctypes.c_void_p),
        ("cmdp", ctypes.c_void_p),
        ("sbp", ctypes.c_void_p),
        ("timeout", ctypes.c_uint),
        ("flags", ctypes.c_uint),
        ("pack_id", ctypes.c_int),
        ("usr_ptr", ctypes.c_void_p),
        ("status", ctypes.c_ubyte),
        ("masked_status", ctypes.c_ubyte),
        ("msg_status", ctypes.c_ubyte),
        ("sb_len_wr", ctypes.c_ubyte),
        ("host_status", ctypes.c_ushort),
        ("driver_status", ctypes.c_ushort),
        ("resid", ctypes.c_int),
        ("duration", ctypes.c_uint),
        ("info", ctypes.c_uint),
    ]


# --- Protocol Decoder ---
class ProtocolDecoder:
    def __init__(self, definition_file="protocol_definitions.json"):
        self.definitions = self.load_definitions(definition_file)

    def load_definitions(self, filename):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        if not os.path.exists(path):
            logger.warning(f"Protocol definitions not found at {path}")
            return {}
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load protocol definitions: {e}")
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


# --- Session Logger ---
class SCSILogger:
    def __init__(self, log_dir="logs"):
        self.log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), log_dir)
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filename = os.path.join(self.log_dir, f"sem_session_{timestamp}.log")
        self.file = open(self.filename, "w", buffering=1)  # Line buffering
        self.write_meta("Session Started", level="INFO")

    def close(self):
        if self.file:
            self.write_meta("Session Ended", level="INFO")
            self.file.close()
            self.file = None

    def write_meta(self, msg, level="INFO"):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        self.file.write(f"{ts} [{level:<4}] [EVT] {msg}\n")

    def log_transaction(
        self, cdb_bytes, data_bytes, direction, status, cmd_name, defined_level="INFO"
    ):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        # Use defined level unless there's an error
        level = defined_level

        # Override if Error Status
        if status != 0 and status != 1:
            if status == 4:
                level = "ERR "
            elif status != 1:
                level = "WARN"

        cdb_str = " ".join([f"{b:02X}" for b in cdb_bytes])

        # Data snippet
        data_str = ""
        if data_bytes and len(data_bytes) > 0:
            snippet = " ".join([f"{b:02X}" for b in data_bytes[:16]])
            if len(data_bytes) > 16:
                snippet += " ..."
            data_str = f"| DATA: {snippet} "
        else:
            data_str = "| DATA: [Empty] "

        # Format: [TIMESTAMP] [LEVEL] [DIRECTION] [NAME] | CDB: ... | DATA: ... -> STATUS
        line = f"{ts} [{level:<4}] [{direction}] {cmd_name:<20} | CDB: {cdb_str:<20} {data_str}-> Status={status}\n"
        self.file.write(line)


# Auto-scan function
def find_sem_device():
    # Scan sg0 to sg32
    for i in range(32):
        path = f"/dev/sg{i}"
        if not os.path.exists(path):
            continue

        try:
            fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
        except OSError:
            continue

        try:
            # Send INQUIRY
            cdb = b"\x12\x00\x00\x00\x60\x00"  # 96 bytes
            inq_buff = ctypes.create_string_buffer(96)
            sense_buff = ctypes.create_string_buffer(32)
            cmd_buff = ctypes.create_string_buffer(cdb)

            io_hdr = SgIoHdr()
            io_hdr.interface_id = ord("S")
            io_hdr.dxfer_direction = SG_DXFER_FROM_DEV
            io_hdr.cmd_len = len(cdb)
            io_hdr.mx_sb_len = 32
            io_hdr.dxfer_len = 96
            io_hdr.dxferp = ctypes.cast(inq_buff, ctypes.c_void_p)
            io_hdr.cmdp = ctypes.cast(cmd_buff, ctypes.c_void_p)
            io_hdr.sbp = ctypes.cast(sense_buff, ctypes.c_void_p)
            io_hdr.timeout = 2000

            fcntl.ioctl(fd, SG_IO, io_hdr)

            # Check Vendor (offset 8) and Product (offset 16)
            # data is in inq_buff
            data = inq_buff.raw
            vendor = data[8:16].decode("ascii", errors="ignore").strip()
            product = data[16:32].decode("ascii", errors="ignore").strip()

            logger.info(f"Checked {path}: Vendor='{vendor}' Product='{product}'")

            if "JEOL" in vendor or "SEM" in product or "SEM" in vendor:
                logger.info(f"Found SEM Device: {path}")
                os.close(fd)
                return path

            os.close(fd)
        except Exception as e:
            logger.debug(f"Error checking {path}: {e}")
            os.close(fd)

    return None


class BridgeSEM:
    def __init__(self, device_path, host="127.0.0.1", port=9999):
        self.device_path = device_path
        self.host = host
        self.port = port
        self.running = False
        self.addr = None
        self.dev_fd = -1
        self.decoder = ProtocolDecoder()

    def start(self):
        try:
            self.dev_fd = os.open(self.device_path, os.O_RDWR)
            logger.info(f"Opened SCSI device: {self.device_path}")
        except Exception as e:
            logger.error(f"Failed to open device {self.device_path}: {e}")
            return

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(1)
            self.running = True
            logger.info(f"Bridge listening on {self.host}:{self.port}")

            while self.running:
                conn, addr = self.server_socket.accept()
                logger.info(f"Client connected: {addr}")
                t = threading.Thread(target=self.handle_client, args=(conn, addr))
                t.start()
        except Exception as e:
            logger.error(f"Server error: {e}")
        finally:
            if self.dev_fd >= 0:
                os.close(self.dev_fd)

    def handle_client(self, conn, addr):
        session_logger = None
        try:
            session_logger = SCSILogger()
            session_logger.write_meta(f"Client Connected: {addr}")

            while True:
                # 1. Read CDB Len
                header = conn.recv(4)
                if not header or len(header) < 4:
                    break
                cdb_len = struct.unpack("<I", header)[0]

                # 2. Read CDB
                cdb = conn.recv(cdb_len)
                if len(cdb) != cdb_len:
                    break

                # Decode Command Name
                cmd_name, cmd_level = self.decoder.decode(cdb)

                # Log Command (Before execution)
                session_logger.log_transaction(
                    cdb, None, "CMD", 0, cmd_name, defined_level=cmd_level
                )

                # 3. Execute on Real Device
                resp_data, status = self.send_scsi_cmd(cdb)

                # For RES, we can pass resp_data to decoder for FA_Response logic
                cmd_name_res, cmd_level_res = self.decoder.decode(
                    cdb, data_bytes=resp_data, direction="RES"
                )

                # Log Response
                session_logger.log_transaction(
                    cdb,
                    resp_data,
                    "RES",
                    status,
                    cmd_name_res,
                    defined_level=cmd_level_res,
                )

                # 4. Send Response
                resp_header = struct.pack("<BI", status, len(resp_data))
                conn.sendall(resp_header)
                if len(resp_data) > 0:
                    conn.sendall(resp_data)

        except Exception as e:
            logger.error(f"Handler error: {e}")
            if session_logger:
                session_logger.write_meta(f"Error: {e}", level="ERR")
        finally:
            if session_logger:
                session_logger.close()
            conn.close()

    def send_scsi_cmd(self, cdb_bytes):
        # We assume default read buffer of 4KB
        buff_size = 4096
        data_buff = ctypes.create_string_buffer(buff_size)
        sense_buff = ctypes.create_string_buffer(32)
        cmd_buff = ctypes.create_string_buffer(cdb_bytes)

        io_hdr = SgIoHdr()
        io_hdr.interface_id = ord("S")
        io_hdr.dxfer_direction = SG_DXFER_FROM_DEV
        io_hdr.cmd_len = len(cdb_bytes)
        io_hdr.mx_sb_len = 32
        io_hdr.dxfer_len = buff_size
        io_hdr.dxferp = ctypes.cast(data_buff, ctypes.c_void_p)
        io_hdr.cmdp = ctypes.cast(cmd_buff, ctypes.c_void_p)
        io_hdr.sbp = ctypes.cast(sense_buff, ctypes.c_void_p)
        io_hdr.timeout = 5000

        try:
            fcntl.ioctl(self.dev_fd, SG_IO, io_hdr)
            status = io_hdr.status
            if status == 0:
                # We return the whole buffer, let caller slice?
                # Actually for cleaner logs we might want true length but we don't know it easily
                return data_buff.raw, 1  # SS_COMP
            else:
                return b"", 4  # SS_ERR
        except Exception as e:
            logger.error(f"IOCTL failed: {e}")
            return b"", 4


if __name__ == "__main__":
    if len(sys.argv) > 1:
        dev = sys.argv[1]
    else:
        dev = find_sem_device()

    if not dev:
        logger.error("No SEM device found and none specified.")
        sys.exit(1)

    logger.info(f"Targeting device: {dev}")
    bridge = BridgeSEM(dev)
    bridge.start()
