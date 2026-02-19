import ctypes
import fcntl
import sys
import os

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
        ("info", ctypes.c_uint)
    ]

SG_IO = 0x2285
SG_DXFER_NONE = -1
SG_DXFER_TO_DEV = -2
SG_DXFER_FROM_DEV = -3

def send_scsi(dev_fd, name, cdb_bytes, direction, length, retries=1):
    print(f"--- [ {name} ] ---")
    print(f"CDB: {' '.join([f'{b:02X}' for b in cdb_bytes])} | Dir: {direction} | Len: {length}")
    
    for attempt in range(retries + 1):
        if direction == 1:
            data_buff = ctypes.create_string_buffer(length if length > 0 else 1)
            dxfer_dir = SG_DXFER_FROM_DEV
            dxfer_len = length
            dxferp = ctypes.cast(data_buff, ctypes.c_void_p)
        elif direction == 2:
            data_buff = ctypes.create_string_buffer(cdb_bytes[8:] if hasattr(cdb_bytes, "__len__") and len(cdb_bytes) > 8 else b"\x00" * length)
            dxfer_dir = SG_DXFER_TO_DEV
            dxfer_len = length
            dxferp = ctypes.cast(data_buff, ctypes.c_void_p)
        else:
            dxfer_dir = SG_DXFER_NONE
            dxfer_len = 0
            dxferp = None

        sense_buff = ctypes.create_string_buffer(32)
        cmd_buff = ctypes.create_string_buffer(cdb_bytes[:6] if len(cdb_bytes) == 6 else cdb_bytes[:10])

        io_hdr = SgIoHdr()
        io_hdr.interface_id = ord("S")
        io_hdr.cmd_len = 6 if len(cdb_bytes) <= 6 else 10
        io_hdr.mx_sb_len = 32
        io_hdr.timeout = 5000
        
        io_hdr.dxfer_direction = dxfer_dir
        io_hdr.dxfer_len = dxfer_len
        io_hdr.dxferp = dxferp

        io_hdr.cmdp = ctypes.cast(cmd_buff, ctypes.c_void_p)
        io_hdr.sbp = ctypes.cast(sense_buff, ctypes.c_void_p)

        try:
            fcntl.ioctl(dev_fd, SG_IO, io_hdr)
            status = io_hdr.status
            sense_len = min(int(io_hdr.sb_len_wr), 32)
            sense_bytes = bytes(sense_buff.raw[:sense_len]) if sense_len > 0 else b""
            print(f"Attempt {attempt+1}: Status={status:02X} Host={io_hdr.host_status:02X} Driver={io_hdr.driver_status:02X}")
            if sense_bytes:
                print(f"Sense: {' '.join([f'{b:02X}' for b in sense_bytes])}")
            
            if status == 2 and sense_bytes and len(sense_bytes) > 2 and (sense_bytes[2] & 0x0F) == 0x06:
                print(" -> UNIT ATTENTION! Retrying...")
                continue # Retry on power on / reset
            
            if status == 0 and io_hdr.host_status == 0 and direction == 1 and io_hdr.resid < dxfer_len:
                xfered = dxfer_len - io_hdr.resid
                print(f"Data IN ({xfered} bytes): {' '.join([f'{b:02X}' for b in bytes(data_buff.raw[:xfered])])}")
            break
        except Exception as e:
            print(f"Exception: {e}")
            break
    print()


def main():
    import glob
    devs = glob.glob("/dev/sg*")
    if not devs:
        print("No /dev/sgX devices found!")
        return
    dev = devs[0]
    print(f"Opening {dev}\n")
    fd = os.open(dev, os.O_RDWR)
    
    # 1. Standard Inquiry to ensure connection
    send_scsi(fd, "Test 1: Standard Inquiry (Native)", b"\x12\x00\x00\x00\x24\x00", direction=1, length=36)
    
    # 2. HT ON Wrapped (Current Implementation - seems to do nothing)
    # 02 01 00 02 40 01  wrapped in FA
    send_scsi(fd, "Test 2: HT ON Wrapped in FA", b"\xFA\x00\x00\x00\x00\x00\x00\x06\x00\x00\x02\x01\x00\x02\x40\x01", direction=2, length=6)
    
    # 3. HT ON Natively Unwrapped - direction=0 (No Data)
    send_scsi(fd, "Test 3: HT ON Unwrapped (Dir=0)", b"\x02\x01\x00\x02\x40\x01", direction=0, length=0)

    # 4. HT ON Natively Unwrapped - direction=1 (Data In 6 bytes)
    # Some older SCSI stacks might interpret Opcode 02 as having a data-in phase regardless of what we set
    send_scsi(fd, "Test 4: HT ON Unwrapped (Dir=1/IN)", b"\x02\x01\x00\x02\x40\x01", direction=1, length=64)

    # 5. HT ON Natively Unwrapped - direction=2 (Data Out 6 bytes)
    send_scsi(fd, "Test 5: HT ON Unwrapped (Dir=2/OUT)", b"\x02\x01\x00\x02\x40\x01", direction=2, length=64)

    os.close(fd)
    print("Done. Please share the output of this script and check if the SEM hardware clicked/responded to any of these tests.")

if __name__ == "__main__":
    main()
