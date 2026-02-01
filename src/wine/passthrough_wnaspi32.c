/*
 * Passthrough WNASPI32.DLL for Wine (Linux SG Driver)
 * Bridges ASPI calls directly to /dev/sg* devices via ioctl(SG_IO).
 * Auto-detects JEOL/SEM devices.
 */

// Include Wine/Windows headers FIRST to avoid conflicts
#include <winsock2.h>
#include <windows.h>
#include "wnaspi32.h"

#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <scsi/sg.h>
#include <string.h>
#include <errno.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <limits.h>

// --- Configuration ---
// Map ASPI Host/Target to Linux Device
// Example: HA 0, Target 0 -> /dev/sg1
//#define SG_DEVICE_PATH "/dev/sg1" 


static int sg_fd = -1;
static char sg_device_name[64] = "UNKNOWN";

static void LogMsg(const char* fmt, ...) {
    char buffer[1024];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buffer, sizeof(buffer), fmt, args);
    va_end(args);
    fprintf(stderr, "[RealASPI] %s\n", buffer);
}

// Helper to perform a SCSI INQUIRY to identify the device
static int IdentifyDevice(int fd, char *vendor, char *product) {
    unsigned char cdb[6] = {0x12, 0, 0, 0, 96, 0}; // INQUIRY, 96 bytes
    unsigned char buffer[96];
    sg_io_hdr_t io_hdr;

    memset(&io_hdr, 0, sizeof(io_hdr));
    memset(buffer, 0, sizeof(buffer));

    io_hdr.interface_id = 'S';
    io_hdr.cmd_len = 6;
    io_hdr.mx_sb_len = 0;
    io_hdr.dxfer_len = sizeof(buffer);
    io_hdr.dxferp = buffer;
    io_hdr.cmdp = cdb;
    io_hdr.dxfer_direction = SG_DXFER_FROM_DEV;
    io_hdr.timeout = 2000;

    if (ioctl(fd, SG_IO, &io_hdr) < 0) {
        return -1;
    }

    // Parse INQUIRY data
    // Vendor: offset 8, len 8
    // Product: offset 16, len 16
    char v[9] = {0};
    char p[17] = {0};
    memcpy(v, buffer + 8, 8);
    memcpy(p, buffer + 16, 16);
    
    // Trim spaces
    for (int i=7; i>=0; i--) if (v[i]==' ') v[i]=0; else break;
    for (int i=15; i>=0; i--) if (p[i]==' ') p[i]=0; else break;

    strcpy(vendor, v);
    strcpy(product, p);
    return 0;
}

static void ScanDevices() {
    char path[32];
    char vendor[32], product[32];

    LogMsg("Scanning for SCSI devices...");

    for (int i = 0; i < 32; i++) {
        sprintf(path, "/dev/sg%d", i);
        int fd = open(path, O_RDWR | O_NONBLOCK);
        if (fd < 0) continue;

        if (IdentifyDevice(fd, vendor, product) == 0) {
            LogMsg("Found %s: Vendor='%s' Product='%s'", path, vendor, product);
            
            // Heuristic to match JEOL SEM
            // Adjust these strings if the user provides specific IDs
            // Identifying based on "JEOL" or "SEM" (case insensitive check usually preferred, but using exact for now)
            if (strstr(vendor, "JEOL") || strstr(product, "SEM") || strstr(product, "sem")) {
                LogMsg("MATCHED TARGET DEVICE: %s", path);
                sg_fd = fd;
                strcpy(sg_device_name, path);
                return; // Stop scanning
            }
        }
        close(fd);
    }
    
    LogMsg("No specific SEM device found in auto-scan. Will try manual /dev/sg0 if available as fallback.");
    // Fallback? Or leave -1? 
    // If we leave -1, specific commands will fail.
}

BOOL WINAPI DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpvReserved) {
    if (fdwReason == DLL_PROCESS_ATTACH) {
        LogMsg("Passthrough Shim Loaded (Build w/ AutoScan).");
        ScanDevices();
        
        if (sg_fd < 0) {
             // Optional: Try opening default device or check env var
             const char* env_dev = getenv("SEM_DEVICE");
             if (env_dev) {
                 sg_fd = open(env_dev, O_RDWR);
                 if (sg_fd >= 0) LogMsg("Opened configured device: %s", env_dev);
             }
        }
        
    } else if (fdwReason == DLL_PROCESS_DETACH) {
        if (sg_fd >= 0) close(sg_fd);
    }
    return TRUE;
}

DWORD __cdecl GetASPI32SupportInfo(void) {
    // 1 Adapter, Status COMP
    // If we have a device, maybe report it? 
    // But ASPI usually reports adapters.
    int status = (sg_fd >= 0) ? 1 : 0;
    return (1 << 8) | status; // Supported | Adapter Count
}

DWORD __cdecl SendASPI32Command(PSRB srb_ptr) {
    SRB_Header *header = (SRB_Header*)srb_ptr;
    SRB_ExecSCSICmd *cmd = (SRB_ExecSCSICmd*)srb_ptr;

    header->SRB_Status = SS_PENDING;

    if (header->SRB_Cmd == SC_HA_INQUIRY) {
        // Return dummy inquiry data
        // Apps often check this to count adapters
        header->SRB_Status = SS_COMP;
        return SS_COMP;
    }

    if (header->SRB_Cmd == SC_EXEC_SCSI_CMD) {
        if (sg_fd < 0) {
            LogMsg("Scan failed to find device and no device open. failing command.");
            header->SRB_Status = SS_NO_DEVICE;
            return SS_NO_DEVICE;
        }

        // We ignore SRB_Target/Lun because we are mapped one-to-one
        // But we could warn if it changes
        
        sg_io_hdr_t io_hdr;
        memset(&io_hdr, 0, sizeof(sg_io_hdr_t));

        io_hdr.interface_id = 'S';
        io_hdr.cmd_len = cmd->SRB_CDBLen;
        
        // Sense buffer mapping
        io_hdr.mx_sb_len = sizeof(cmd->SenseArea); 
        io_hdr.sbp = cmd->SenseArea;
        
        io_hdr.dxfer_len = cmd->SRB_BufLen;
        io_hdr.dxferp = cmd->SRB_BufPointer;
        io_hdr.cmdp = cmd->CDBByte;
        
        // Default timeout 5s, maybe increase?
        io_hdr.timeout = 10000; 

        // Direction mapping
        if (cmd->SRB_Flags & SRB_DIR_IN)
            io_hdr.dxfer_direction = SG_DXFER_FROM_DEV;
        else if (cmd->SRB_Flags & SRB_DIR_OUT)
            io_hdr.dxfer_direction = SG_DXFER_TO_DEV;
        else
            io_hdr.dxfer_direction = SG_DXFER_NONE;

        // Log non-read/write commands or periodic? 
        // Verbose log for now
        // LogMsg("CDB[0]=%02X Target=%d", cmd->CDBByte[0], cmd->SRB_Target);

        if (ioctl(sg_fd, SG_IO, &io_hdr) < 0) {
            LogMsg("ioctl failed: %s", strerror(errno));
            header->SRB_Status = SS_ERR;
            return SS_ERR;
        }

        // Check SCSI Status
        if (io_hdr.status != 0) {
            LogMsg("SCSI Error Status: 0x%x", io_hdr.status);
            header->SRB_Status = SS_ERR;
            // ASPI has specific error codes for Target Status but SS_ERR is generic catch-all
            // Could map SRB_TgtStat = io_hdr.status;
            cmd->SRB_TgtStat = io_hdr.status;
            // Also SRB_HaStat
        } else {
            header->SRB_Status = SS_COMP;
        }
        
        // Handle PostProc (Event)
        if (cmd->SRB_Flags & SRB_EVENT_NOTIFY) { 
             SetEvent((HANDLE)cmd->SRB_PostProc);
        }

        return SS_COMP;
    }

    return SS_ERR;
}
