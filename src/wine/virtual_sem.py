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
                header = self._recvall(conn, 9)
                if not header or len(header) < 9:
                    break

                cdb_len, direction, xfer_len = struct.unpack("<IBI", header)

                cdb = self._recvall(conn, cdb_len)
                if not cdb or len(cdb) != cdb_len:
                    logger.warning("Incomplete CDB received")
                    break

                data_out = None
                if direction == 2 and xfer_len > 0:
                    data_out = self._recvall(conn, xfer_len)
                    if not data_out or len(data_out) != xfer_len:
                        logger.warning("Incomplete Data-Out received")
                        break

                response_data, status = self.process_scsi_command(
                    cdb, direction=direction, data_out=data_out, xfer_len=xfer_len
                )

                resp_header = struct.pack("<BI", status, len(response_data))
                conn.sendall(resp_header)

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

    def _recvall(self, conn, length):
        data = bytearray()
        while len(data) < length:
            chunk = conn.recv(length - len(data))
            if not chunk:
                return None
            data.extend(chunk)
        return bytes(data)

    def _build_response(self, payload, xfer_len, fallback_len=None):
        if payload is None:
            payload = b""
        if xfer_len:
            if len(payload) >= xfer_len:
                return payload[:xfer_len]
            return payload + bytes(xfer_len - len(payload))
        if fallback_len is None:
            return payload
        if len(payload) >= fallback_len:
            return payload[:fallback_len]
        return payload + bytes(fallback_len - len(payload))

    def _alloc_len_from_cdb(self, cdb, default=4):
        if not cdb or len(cdb) <= 4:
            return default
        alloc_len = cdb[4]
        if alloc_len == 0:
            return default
        if alloc_len > 256:
            return default
        return alloc_len

    def _publish_from_cdb(self, cdb):
        if not cdb or len(cdb) < 2:
            return
        opcode = cdb[0]
        cdb_len = len(cdb)
        if (
            opcode == 0x02
            and len(cdb) > 9
            and cdb[1] == 0x01
            and cdb[4] == 0x08
            and cdb[8] == 0x00
        ):
            val = struct.unpack("<H", cdb[9:11])[0]
            self._publish_state("ACCV", val)
        elif opcode == 0x00 and len(cdb) > 7 and cdb[1] == 0x01 and cdb[4] == 0x00:
            val = struct.unpack(">H", cdb[6:8])[0]
            self._publish_state("SPEED", val)
        elif opcode == 0x00 and len(cdb) > 5 and cdb[4] == 0x09:
            is_start = cdb[5]
            self._publish_state("SCAN_STATUS", 1 if is_start else 0)
        elif opcode == 0x03 and len(cdb) > 9 and cdb[1] == 0x01 and cdb[8] == 0x10:
            val = struct.unpack("<H", cdb[9:11])[0]
            self._publish_state("MAG", val)

    def process_scsi_command(self, cdb, direction=0, data_out=None, xfer_len=0):
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

            response = self._build_response(bytes(resp), xfer_len, fallback_len=36)
            logger.info(f"CMD: INQUIRY -> {response}")
            return response, 1

        # --- [0xCC] Identification ---
        if opcode == 0xCC and cdb_len > 1:
            if cdb[1] == 0x81:  # Get Hardware ID
                response = struct.pack("<Hxx", self.state["hardware_id"])
                logger.info(f"CMD: GetHardwareID -> {self.state['hardware_id']:04X}")
            elif cdb[1] == 0x80:  # Get Status Size
                response = struct.pack("<HH", 0x0002, 0x8000)
                logger.info("CMD: GetStatusSize -> 0x0002 0x8000")
            response = self._build_response(response, xfer_len, fallback_len=4)

        # --- [0xC4] Vacuum Status ---
        elif opcode == 0xC4 and cdb_len > 1:
            if cdb[1] == 0x01:  # Get Vacuum Status
                response = struct.pack("<Hxx", self.state["vacuum_status"])
                logger.info(f"CMD: GetVacuumStatus -> {self.state['vacuum_status']}")
            elif cdb[1] == 0x00:  # Get Vacuum Mode
                response = struct.pack("<Hxx", self.state["vacuum_mode"])
                logger.info(f"CMD: GetVacuumMode -> {self.state['vacuum_mode']}")
            elif cdb[1] == 0x03:  # Get ALS
                response = b"\x00\x00\x00\x00"
                logger.info("CMD: GetALS -> 0")
            response = self._build_response(response, xfer_len, fallback_len=4)

        # --- [0xC6] Gun Status ---
        elif opcode == 0xC6 and cdb_len > 1:
            if cdb[1] == 0x10:  # Get HT Status
                response = struct.pack("<Hxx", self.state["ht_status"])
                logger.info(f"CMD: GetHTStatus -> {self.state['ht_status']}")
            elif cdb[1] == 0x11:  # Get Accv
                response = struct.pack("<Hxx", self.state["accv"])
                logger.info(f"CMD: GetAccv -> {self.state['accv']}")
            elif cdb[1] == 0x12:  # Get Filament
                response = struct.pack("<Hxx", self.state["filament"])
                logger.info("CMD: GetFilament")
            elif cdb[1] == 0x15:  # Get Emission
                response = struct.pack("<Hxx", self.state["emission_current"])
                logger.info("CMD: GetEmission")
            response = self._build_response(response, xfer_len, fallback_len=4)

        # --- [0xC7] Gun Detail (LaB6) ---
        elif opcode == 0xC7 and cdb_len > 1:
            if cdb[1] == 0x00:  # Get Lbg Status
                response = bytes(18)
                logger.info("CMD: GetLbgStatus (18b)")
            response = self._build_response(response, xfer_len, fallback_len=18)

        # --- [0xCE] Extended Status ---
        elif opcode == 0xCE and cdb_len > 1:
            # Most seem to ask for 4 bytes based on log
            response = b"\x00\x00\x00\x00"
            name = "UnknownExt"
            if cdb[1] == 0x02:
                name = "GetEsitfStatus"
            elif cdb[1] == 0x08:
                name = "GetPcdStatus"
            elif cdb[1] == 0x0B:
                name = "GetBcxStatus"
            logger.info(f"CMD: {name} -> 0")
            response = self._build_response(response, xfer_len, fallback_len=4)

        # --- [0xC5] Pressure ---
        elif opcode == 0xC5 and cdb_len > 1:
            if cdb[1] == 0x09:  # Get Valve Pos
                response = struct.pack("<Hxx", 1)  # Open?
                logger.info("CMD: GetValvePos")
            response = self._build_response(response, xfer_len, fallback_len=4)

        # --- [0x01] Vacuum Control ---
        elif opcode == 0x01:
            # Mode 1: [01 01 00 06 40 44 04 01 00 val] (Set Vacuum Mode)
            if (
                cdb_len > 9
                and cdb[1] == 0x01
                and cdb[4] == 0x06
                and cdb[5] == 0x40
                and cdb[6] == 0x44
            ):
                val = cdb[9]
                self.state["vacuum_mode"] = val
                logger.info(f"CMD: SetVacuumMode -> {val}")
                self._publish_state("VAC_MODE", val)
                return b"", status

            # Mode 1: [01 01 00 06 40 38 00 01 00 01] (Evac)
            # Mode 1: [01 01 00 06 40 38 00 01 00 00] (Vent)
            if (
                cdb_len > 9
                and cdb[1] == 0x01
                and cdb[4] == 0x06
                and cdb[5] == 0x40
                and cdb[6] == 0x38
            ):
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
            if cdb_len > 9 and cdb[1] == 0x01 and cdb[4] == 0x07:  # HT Set
                new_state = cdb[9]
                self.state["ht_status"] = new_state
                logger.info(f"CMD: SetHT -> {new_state}")
                self._publish_state("HT_STATUS", new_state)

            # Mode 1: [02 01 00 08 40 02 01 03 00 00 val 00] (Accv)
            elif cdb_len > 10 and cdb[1] == 0x01 and cdb[4] == 0x08:
                sub_cmd = cdb[8]
                val = struct.unpack("<H", cdb[9:11])[0]
                if sub_cmd == 0x00:
                    self.state["accv"] = val
                    logger.info(f"CMD: SetAccv -> {val}")
                    self._publish_state("ACCV", val)
                elif sub_cmd == 0x14:  # Filament
                    self.state["filament"] = val
                    logger.info(f"CMD: SetFilament -> {val}")
                    self._publish_state("FILAMENT", val)

        # --- [0x03] Lens Control (Mag) ---
        elif opcode == 0x03:
            # SetMag: { "0": "0x03", "1": "0x01", "8": "0x10" }
            if cdb_len > 10 and cdb[1] == 0x01 and cdb[8] == 0x10:
                # Mag value location guess: bytes 9-10
                if len(cdb) >= 11:
                    mag = struct.unpack("<H", cdb[9:11])[0]
                    self.state["mag_index"] = mag
                    logger.info(f"CMD: SetMag -> {mag}")
                    self._publish_state("MAG", mag)

        # --- [0x00] Scan Control ---
        elif opcode == 0x00:
            if cdb_len > 7 and cdb[1] == 0x01 and cdb[4] == 0x00:  # Set Speed
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
            elif cdb_len > 5 and cdb[4] == 0x09:  # Start/Stop
                is_start = cdb[5]
                logger.info(f"CMD: Scan {'Start' if is_start else 'Stop'}")
                self._publish_state("SCAN_STATUS", 1 if is_start else 0)

        # --- [0x04] Video Request ---
        elif opcode == 0x04:
            if cdb_len > 5 and cdb[4] == 0x1E and cdb[5] == 0x07:  # Req Video
                # Logic: In real hardware, this triggers DMA.
                # For Emulator, we might just acknowledge.
                # The DLL expects data later via ReadData? Or via a specific "Get Image" command?
                # Actually, video usually comes via a separate high-speed path or specific READ commands.
                # We will just say OK for now.
                logger.info("CMD: ReqVideoAD")

        # --- [0xC2] Legacy Set ---
        elif opcode == 0xC2:
            if cdb_len > 1 and cdb[1] == 0x00:  # SetScanSpeed (Legacy)
                logger.info("CMD: SetScanSpeed (Legacy)")
            elif cdb_len > 1 and cdb[1] == 0x01:  # SetFreeze (Legacy)
                logger.info("CMD: SetFreeze (Legacy)")
            elif cdb_len > 1 and cdb[1] == 0x02:  # SetArea (Legacy)
                logger.info("CMD: SetArea (Legacy)")

        # --- [0xC3] Legacy Read ---
        elif opcode == 0xC3:
            alloc_len = self._alloc_len_from_cdb(cdb)
            response = self._build_response(b"", xfer_len, fallback_len=alloc_len)
            logger.info("CMD: GetLegacyStatus")

        # --- [0xC8] Lens Read ---
        elif opcode == 0xC8 and cdb_len > 1:
            if cdb[1] == 0x50:  # Get Mag
                response = struct.pack("<Hxx", self.state["mag_index"])
                logger.info("CMD: GetMag")
            elif cdb[1] == 0x38:  # Get WD
                response = struct.pack("<Hxx", 0)
                logger.info("CMD: GetWD")
            else:
                response = b"\x00\x00\x00\x00"
                logger.info("CMD: GetLensValue")
            response = self._build_response(response, xfer_len, fallback_len=4)

        # --- [0xCB] Stage Read ---
        elif opcode == 0xCB:
            payload = struct.pack(
                "<5i",
                self.state["stage_x"],
                self.state["stage_y"],
                self.state["stage_z"],
                self.state["stage_r"],
                self.state["stage_t"],
            )
            response = self._build_response(
                payload, xfer_len, fallback_len=len(payload)
            )
            logger.info("CMD: GetStagePosAll")

        # --- [0xD0] Status Block ---
        elif opcode == 0xD0:
            response = self._build_response(b"", xfer_len, fallback_len=128)
            logger.info("CMD: GetStatusBlock")

        # --- [0xDE] FIS Read ---
        elif opcode == 0xDE:
            response = self._build_response(b"", xfer_len, fallback_len=4)
            logger.info("CMD: GetFis")

        # --- [0xFA] Wrapper ---
        elif opcode == 0xFA:
            if data_out:
                self._publish_from_cdb(data_out)
            response = self._build_response(b"", xfer_len, fallback_len=0)
            logger.info("CMD: Generic10_Wrapper")

        # --- [0xE0] Write LUT ---
        elif opcode == 0xE0:
            logger.info("CMD: WriteLUT")

        # --- [0xED] Large Data Read ---
        elif opcode == 0xED:
            response = self._build_response(b"", xfer_len, fallback_len=0)
            logger.info("CMD: ReadSemData")

        # --- Default Fallback ---
        else:
            # If it's a read command (checking group C* usually), return dummy zeros
            if (
                (opcode & 0xF0) == 0xC0
                or (opcode & 0xF0) == 0xD0
                or (opcode & 0xF0) == 0xE0
            ):
                alloc_len = self._alloc_len_from_cdb(cdb)
                response = self._build_response(b"", xfer_len, fallback_len=alloc_len)
                logger.debug(f"CMD: Unknown Read {hex_cdb} -> {alloc_len} bytes")
            else:
                logger.debug(f"CMD: Unknown Write {hex_cdb}")

        return response, status


if __name__ == "__main__":
    emu = VirtualSEM()
    emu.start()
