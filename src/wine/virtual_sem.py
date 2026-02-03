import socket
import struct
import threading
import logging
import time
import json

try:
    import zmq

    HAS_ZMQ = True
except ImportError:
    HAS_ZMQ = False

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - [SEM_EMU] - %(message)s")
logger = logging.getLogger("VirtualSEM")


class VirtualSEM:
    def __init__(self, host="127.0.0.1", port=9999):
        self.host = host
        self.port = port
        self.running = False
        self.server_socket = None

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
        else:
            logger.warning(
                "IPC: ZeroMQ not installed. Video Shim integration will not work."
            )

        # --- SEM Internal State ---
        self.state = {
            "ht_status": 0,  # 0: Off, 1: On
            "accv": 15000,  # 15kV default
            "filament": 0,
            "vacuum_status": 3,  # 3: VAC_READY (High Vac)
            "vacuum_mode": 0,  # 0: High, 1: Low
            "mag_index": 100,  # Arbitrary index
            "stage_x": 0,
            "stage_y": 0,
            "stage_z": 10000,  # 10mm
            "stage_r": 0,
            "stage_t": 0,
            "scan_speed": 1,
            "probe_current": 100,
            "emission_current": 50,
            "hardware_id": 0x170C,  # Mode 1 ID (6330?)
        }

    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(1)
            self.running = True
            logger.info(f"Virtual SEM started on {self.host}:{self.port}")
            logger.info(f"Emulating Hardware ID: 0x{self.state['hardware_id']:04X}")

            while self.running:
                conn, addr = self.server_socket.accept()
                logger.info(f"Client connected: {addr}")
                client_thread = threading.Thread(
                    target=self.handle_client, args=(conn,)
                )
                client_thread.start()

        except Exception as e:
            logger.error(f"Server error: {e}")
        finally:
            if self.server_socket:
                self.server_socket.close()

    def handle_client(self, conn):
        try:
            while True:
                # 1. Read Header (4 bytes: Command Length)
                # We expect the Shim to send [Len(4)][CDB...]
                header = conn.recv(4)
                if not header or len(header) < 4:
                    break

                cdb_len = struct.unpack("<I", header)[0]

                # 2. Read CDB
                cdb = conn.recv(cdb_len)
                if len(cdb) != cdb_len:
                    logger.warning("Incomplete CDB received")
                    break

                # 3. Process CDB
                response_data, status = self.process_scsi_command(cdb)

                # 4. Send Response Header [Status(1)][DataLen(4)]
                resp_header = struct.pack("<BI", status, len(response_data))
                conn.sendall(resp_header)

                # 5. Send Response Data
                if len(response_data) > 0:
                    conn.sendall(response_data)

        except ConnectionResetError:
            logger.info("Client disconnected")
        except Exception as e:
            logger.error(f"Handler error: {e}")
        finally:
            conn.close()

    def _publish_state(self, event_type, value):
        """Publish state change to Video Shim via ZMQ"""
        if self.zmq_pub:
            try:
                msg = json.dumps({"event": event_type, "value": value})
                self.zmq_pub.send_string(msg)
            except Exception as e:
                logger.error(f"IPC: Publish failed: {e}")

    def process_scsi_command(self, cdb):
        """
        Parses the raw CDB bytes and returns (response_bytes, status_code).
        Status 1 = Success, 0 = Error.
        """
        if not cdb:
            return b"", 0

        opcode = cdb[0]
        group = opcode  # In standard SCSI, opcode defines group, but here it's custom.

        hex_cdb = " ".join([f"{b:02X}" for b in cdb])
        # logger.info(f"CDB: [{hex_cdb}]")

        response = b""
        status = 1  # SS_COMP

        # --- Standard SCSI Commands ---
        if opcode == 0x00:  # SC_HA_INQUIRY / TEST UNIT READY
            # sem_InitCom (FUN_10022bb9) sends opcode 0x00?
            # Actually, standard SCSI Inquiry is 0x12.
            # But the protocol analysis showed [00 01 00 04 ...] for Scan Speed.
            # Let's check the Group ID.
            # sem_InitCom sets CDB[0] = 0x12 (Standard SCSI INQUIRY)?
            pass

        if opcode == 0x12:  # INQUIRY
            # Standard SCSI Inquiry response
            # Format:
            # Byte 0: Peripheral Device Type (0x03 = Processor)
            # Byte 1: RMB (Removable)
            # Byte 2: Version
            # Byte 3: Response Data Format
            # Byte 4: Additional Length (n-4)
            # Byte 8-15: Vendor ID (ASCII) -> "JEOL    "
            # Byte 16-31: Product ID (ASCII)

            # sem_InitCom checks memcmp(buffer, "JEOL", 4) at offset 8 (Standard Vendor ID location)

            # Construct standard Inquiry data (36 bytes minimum)
            # Type 0x03 (Processor), Removable 0
            resp = bytearray(36)
            resp[0] = 0x03
            resp[4] = 31  # Additional length

            # Vendor ID "JEOL    " (8 bytes)
            vendor = b"JEOL    "
            resp[8:16] = vendor

            # Product ID "SEM             " (16 bytes)
            product = b"SEM             "
            resp[16:32] = product

            # Revision
            rev = b"1.0 "
            resp[32:36] = rev

            response = bytes(resp)
            logger.info(f"CMD: INQUIRY -> {response}")
            return response, 1

        # --- [0xCC] Identification ---
        if opcode == 0xCC:
            if cdb[1] == 0x81:  # Get Hardware ID
                # Return 2 bytes (Hardware ID) + 2 bytes padding?
                # Protocol says [CC 81 00 04] -> reads 4 bytes.
                # Usually returns 2 bytes swapped? Let's return 4 bytes to be safe.
                # ID 0x170C
                response = struct.pack("<Hxx", self.state["hardware_id"])
                logger.info(f"CMD: GetHardwareID -> {self.state['hardware_id']:04X}")

        # --- [0xC4] Vacuum Status ---
        elif opcode == 0xC4:
            if cdb[1] == 0x01:  # Get Vacuum Status
                # Return 2 bytes status
                response = struct.pack("<Hxx", self.state["vacuum_status"])
                logger.info(f"CMD: GetVacuumStatus -> {self.state['vacuum_status']}")
            elif cdb[1] == 0x00:  # Get Vacuum Mode
                response = struct.pack("<Hxx", self.state["vacuum_mode"])
                logger.info(f"CMD: GetVacuumMode -> {self.state['vacuum_mode']}")

        # --- [0xC6] Gun Status ---
        elif opcode == 0xC6:
            if cdb[1] == 0x10:  # Get HT Status
                response = struct.pack("<Hxx", self.state["ht_status"])
                logger.info(f"CMD: GetHTStatus -> {self.state['ht_status']}")
            elif cdb[1] == 0x11:  # Get Accv
                response = struct.pack("<Hxx", self.state["accv"])
                logger.info(f"CMD: GetAccv -> {self.state['accv']}")
            elif cdb[1] == 0x12:  # Get Filament
                response = struct.pack("<Hxx", self.state["filament"])
                logger.info("CMD: GetFilament")

        # --- [0xC5] Pressure ---
        elif opcode == 0xC5:
            if cdb[1] == 0x09:  # Get Valve Pos
                response = struct.pack("<Hxx", 1)  # Open?
                logger.info("CMD: GetValvePos")

        # --- [0x01] Vacuum Control ---
        elif opcode == 0x01:
            # Mode 1: [01 01 00 06 40 44 04 01 00 val] (Set Vacuum Mode)
            if cdb[1] == 0x01 and cdb[4] == 0x06 and cdb[5] == 0x40 and cdb[6] == 0x44:
                val = cdb[9]
                self.state["vacuum_mode"] = val
                logger.info(f"CMD: SetVacuumMode -> {val}")
                return b"", status

            # Mode 1: [01 01 00 06 40 38 00 01 00 01] (Evac)
            # Mode 1: [01 01 00 06 40 38 00 01 00 00] (Vent)
            if cdb[1] == 0x01 and cdb[4] == 0x06 and cdb[5] == 0x40 and cdb[6] == 0x38:
                action = cdb[9]
                if action == 1:
                    logger.info("CMD: StartEvac")
                    self.state["vacuum_status"] = 2  # VAC_EVAC?
                    # Simulate transition to Ready after short delay?
                    # For now just set to Ready immediately or keep 2 then 3
                    self.state["vacuum_status"] = 3  # VAC_READY
                else:
                    logger.info("CMD: StartVent")
                    self.state["vacuum_status"] = 0  # VAC_OFF?
                return b"", status

        # --- [0x02] Gun Control ---
        elif opcode == 0x02:
            # Mode 1: [02 01 00 07 40 02 00 02 00 30 state]
            if cdb[1] == 0x01 and cdb[4] == 0x07:  # HT Set
                new_state = cdb[9]
                self.state["ht_status"] = new_state
                logger.info(f"CMD: SetHT -> {new_state}")

            # Mode 1: [02 01 00 08 40 02 01 03 00 00 val 00] (Accv)
            elif cdb[1] == 0x01 and cdb[4] == 0x08:
                sub_cmd = cdb[8]
                val = struct.unpack("<H", cdb[9:11])[0]
                if sub_cmd == 0x00:
                    self.state["accv"] = val
                    logger.info(f"CMD: SetAccv -> {val}")
                    self._publish_state("ACCV", val)
                elif sub_cmd == 0x14:  # Filament
                    self.state["filament"] = val
                    logger.info(f"CMD: SetFilament -> {val}")

        # --- [0x03] Lens Control (Mag) ---
        elif opcode == 0x03:
            # SetMag: { "0": "0x03", "1": "0x01", "8": "0x10" }
            if cdb[1] == 0x01 and len(cdb) > 8 and cdb[8] == 0x10:
                # Mag value location guess: bytes 9-10
                if len(cdb) >= 11:
                    mag = struct.unpack("<H", cdb[9:11])[0]
                    self.state["mag_index"] = mag
                    logger.info(f"CMD: SetMag -> {mag}")
                    self._publish_state("MAG", mag)

        # --- [0x00] Scan Control ---
        elif opcode == 0x00:
            if cdb[1] == 0x01 and cdb[4] == 0x00:  # Set Speed
                # [00 01 00 04 00 00 high low]
                speed = struct.unpack(">H", cdb[6:8])[
                    0
                ]  # Big Endian in CDB? Need to check protocol.
                # Protocol doc says: [00 01 00 04 00 00 high low].
                # Let's assume input is Big Endian for 16-bit values in CDBs usually?
                # Actually earlier analysis: "speed 0 -> 0x0000".
                self.state["scan_speed"] = speed
                logger.info(f"CMD: SetScanSpeed -> {speed}")
                self._publish_state("SPEED", speed)
            elif cdb[4] == 0x09:  # Start/Stop
                is_start = cdb[5]
                logger.info(f"CMD: Scan {'Start' if is_start else 'Stop'}")
                self._publish_state("SCAN_STATUS", 1 if is_start else 0)

        # --- [0x04] Video Request ---
        elif opcode == 0x04:
            if cdb[4] == 0x1E and cdb[5] == 0x07:  # Req Video
                # Logic: In real hardware, this triggers DMA.
                # For Emulator, we might just acknowledge.
                # The DLL expects data later via ReadData? Or via a specific "Get Image" command?
                # Actually, video usually comes via a separate high-speed path or specific READ commands.
                # We will just say OK for now.
                logger.info("CMD: ReqVideoAD")

        # --- Default Fallback ---
        else:
            # If it's a read command (checking group C* usually), return dummy zeros
            if (opcode & 0xF0) == 0xC0:
                response = b"\x00\x00\x00\x00"
                logger.debug(f"CMD: Unknown Read {hex_cdb} -> 0000")
            else:
                logger.debug(f"CMD: Unknown Write {hex_cdb}")

        return response, status


if __name__ == "__main__":
    emu = VirtualSEM()
    emu.start()
