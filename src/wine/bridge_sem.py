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

try:
    import zmq

    HAS_ZMQ = True
except ImportError:
    HAS_ZMQ = False

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
        self,
        cdb_bytes,
        data_bytes,
        direction,
        status,
        cmd_name,
        defined_level="INFO",
        extra_info="",
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
        extra = f" {extra_info}" if extra_info else ""
        line = (
            f"{ts} [{level:<4}] [{direction}] {cmd_name:<20} | CDB: {cdb_str:<20} "
            f"{data_str}-> Status={status}{extra}\n"
        )
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

        # --- IPC (ZeroMQ) ---
        self.zmq_pub = None
        if HAS_ZMQ:
            try:
                self.zmq_ctx = zmq.Context()
                self.zmq_pub = self.zmq_ctx.socket(zmq.PUB)
                self.zmq_pub.bind("tcp://127.0.0.1:5556")
                logger.info("IPC: ZeroMQ Publisher bound to tcp://127.0.0.1:5556")
            except Exception as e:
                logger.error(f"IPC: Failed to bind ZeroMQ: {e}")
                self.zmq_pub = None

    def _publish_state(self, event_type, value):
        if self.zmq_pub:
            try:
                msg = json.dumps({"event": event_type, "value": value})
                self.zmq_pub.send_string(msg)
            except Exception as e:
                logger.error(f"IPC: Publish failed: {e}")

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

            def recvall(sock, length):
                data = bytearray()
                while len(data) < length:
                    chunk = sock.recv(length - len(data))
                    if not chunk:
                        return None
                    data.extend(chunk)
                return bytes(data)

            while True:
                # 1. Read CDB Len
                header = recvall(conn, 9)
                if not header or len(header) < 9:
                    break
                cdb_len, dir_byte, xfer_len = struct.unpack("<IBI", header)

                # 2. Read CDB
                cdb = recvall(conn, cdb_len)
                if not cdb or len(cdb) != cdb_len:
                    break

                data_out = None
                if dir_byte == 2 and xfer_len > 0:
                    data_out = recvall(conn, xfer_len)
                    if not data_out or len(data_out) != xfer_len:
                        break

                # Decode Command Name
                cmd_name, cmd_level = self.decoder.decode(cdb)

                # Log Command (Before execution)
                session_logger.log_transaction(
                    cdb, None, "CMD", 0, cmd_name, defined_level=cmd_level
                )

                # --- 2.5 Intercept / Patch Logic ---
                # Some commands fail on the target or need to be faked for the Shim to work.

                intercepted = False
                resp_data = b""
                status = 1  # Success
                detail = "Intercepted"

                opcode = cdb[0]

                # Intercept Set Commands (Publish to ZMQ)
                if (
                    opcode == 0x02
                    and cdb[1] == 0x01
                    and cdb[4] == 0x08
                    and cdb[8] == 0x00
                ):  # SetAccv
                    val = struct.unpack("<H", cdb[9:11])[0]
                    self._publish_state("ACCV", val)

                elif opcode == 0x00 and cdb[1] == 0x01 and cdb[4] == 0x00:  # SetSpeed
                    val = struct.unpack(">H", cdb[6:8])[
                        0
                    ]  # Big Endian usually for this group
                    self._publish_state("SPEED", val)

                elif opcode == 0x00 and cdb[4] == 0x09:  # Start/Stop Scan
                    is_start = cdb[5]
                    self._publish_state("SCAN_STATUS", 1 if is_start else 0)

                elif opcode == 0x03 and cdb[1] == 0x01 and cdb[8] == 0x10:  # SetMag
                    if len(cdb) >= 11:
                        val = struct.unpack("<H", cdb[9:11])[0]
                        self._publish_state("MAG", val)

                # Intercept Problematic Get Commands
                if opcode == 0xC4 and cdb[1] == 0x03:  # GetALS
                    intercepted = True
                    resp_data = b"\x00\x00\x00\x00"  # 4 bytes

                elif opcode == 0xCE:  # Extended Status (PCD, ESITF, BCX)
                    intercepted = True
                    resp_data = b"\x00\x00\x00\x00"  # 4 bytes

                elif opcode == 0xC7 and cdb[1] == 0x00:  # GetLbgStatus
                    intercepted = True
                    resp_data = bytes(18)  # 18 bytes of zeros

                # --- 3. Execute ---
                if not intercepted:
                    resp_data, status, detail = self.send_scsi_cmd(
                        cdb, direction=dir_byte, data_out=data_out, xfer_len=xfer_len
                    )

                # --- 3.5 Intercept / Patch Responses (Read Synch) ---
                # Sniff responses to "Get" commands to sync the shim
                if status == 1 and len(resp_data) >= 2:
                    opcode = cdb[0]
                    # GetMag (0xC8 50)
                    if opcode == 0xC8 and cdb[1] == 0x50:
                        val = struct.unpack("<H", resp_data[:2])[0]
                        self._publish_state("MAG", val)

                    # GetAccv (0xC6 11)
                    elif opcode == 0xC6 and cdb[1] == 0x11:
                        val = struct.unpack("<H", resp_data[:2])[0]
                        self._publish_state("ACCV", val)

                    # GetAccv2 (0x02 01 ... 08 ... 00)
                    # This is tricky as it's a SET command but sometimes apps read back?
                    # No, usually apps read via C6/C8.

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
                    extra_info=detail,
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

    def send_scsi_cmd(self, cdb_bytes, direction=1, data_out=None, xfer_len=0):
        buff_size = max(int(xfer_len), 0)
        if buff_size == 0:
            buff_size = 4096

        data_buff = ctypes.create_string_buffer(buff_size)
        sense_buff = ctypes.create_string_buffer(32)
        cmd_buff = ctypes.create_string_buffer(cdb_bytes)

        io_hdr = SgIoHdr()
        io_hdr.interface_id = ord("S")
        io_hdr.cmd_len = len(cdb_bytes)
        io_hdr.mx_sb_len = 32
        io_hdr.timeout = 5000

        if direction == 2:
            io_hdr.dxfer_direction = SG_DXFER_TO_DEV
            if data_out is None:
                data_out = b""
            out_len = len(data_out)
            out_buff = ctypes.create_string_buffer(data_out, out_len)
            io_hdr.dxfer_len = out_len
            io_hdr.dxferp = ctypes.cast(out_buff, ctypes.c_void_p)
        elif direction == 1:
            io_hdr.dxfer_direction = SG_DXFER_FROM_DEV
            io_hdr.dxfer_len = buff_size
            io_hdr.dxferp = ctypes.cast(data_buff, ctypes.c_void_p)
        else:
            io_hdr.dxfer_direction = SG_DXFER_NONE
            io_hdr.dxfer_len = 0
            io_hdr.dxferp = None

        io_hdr.cmdp = ctypes.cast(cmd_buff, ctypes.c_void_p)
        io_hdr.sbp = ctypes.cast(sense_buff, ctypes.c_void_p)

        try:
            fcntl.ioctl(self.dev_fd, SG_IO, io_hdr)
            status = io_hdr.status
            sense_len = min(int(io_hdr.sb_len_wr), 32)
            sense_bytes = bytes(sense_buff.raw[:sense_len]) if sense_len > 0 else b""
            detail = ""
            if status != 0 or io_hdr.host_status != 0 or io_hdr.driver_status != 0:
                sense_hex = (
                    " ".join(f"{b:02X}" for b in sense_bytes) if sense_bytes else ""
                )
                detail = (
                    f"| SCSI=0x{status:02X} Host=0x{io_hdr.host_status:02X} "
                    f"Driver=0x{io_hdr.driver_status:02X}"
                )
                if sense_hex:
                    detail += f" Sense={sense_hex}"

            if status == 0:
                if direction == 1:
                    xfered = int(io_hdr.dxfer_len - io_hdr.resid)
                    return data_buff.raw[:xfered], 1, detail
                return b"", 1, detail
            return b"", 4, detail
        except Exception as e:
            logger.error(f"IOCTL failed: {e}")
            return b"", 4, f"| IOCTL={e}"


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
