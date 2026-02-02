/*
 * Fake WNASPI32.DLL for Wine
 * Redirects ASPI commands to a local TCP socket (Virtual SEM Emulator)
 */

#include <winsock2.h>
#include <windows.h>
#include <stdio.h>
#include <stdarg.h>
#include "wnaspi32.h"

#pragma pack(1)
typedef struct {
    BYTE  SRB_Cmd;
    BYTE  SRB_Status;
    BYTE  SRB_HaId;
    BYTE  SRB_Flags;
    DWORD SRB_Hdr_Rsvd;
    BYTE  HA_Count;
    BYTE  HA_SCSI_ID;
    BYTE  HA_ManagerId[16];
    BYTE  HA_Identifier[16];
    BYTE  HA_Unique[16];
    WORD  HA_Rsvd1;
} SRB_HAInquiry, *PSRB_HAInquiry;

typedef struct {
    BYTE  SRB_Cmd;
    BYTE  SRB_Status;
    BYTE  SRB_HaId;
    BYTE  SRB_Flags;
    DWORD SRB_Hdr_Rsvd;
    BYTE  SRB_Target;
    BYTE  SRB_Lun;
    BYTE  SRB_DeviceType;
    BYTE  SRB_Rsvd1;
} SRB_GDEVBlock, *PSRB_GDEVBlock;
#pragma pack()

BOOL WINAPI DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpvReserved) {
    if (fdwReason == DLL_PROCESS_ATTACH) {
        // We can't use LogMsg easily here if it depends on winsock not init yet?
        // Just fprintf to stderr
        fprintf(stderr, "[FakeASPI] DLL Loaded! (Process Attach)\n");
    }
    return TRUE;
}

/* --- Global State --- */
static SOCKET emu_socket = INVALID_SOCKET;
static BOOL winsock_init = FALSE;

static void LogMsg(const char* fmt, ...) {
    char buffer[1024];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buffer, sizeof(buffer), fmt, args);
    va_end(args);
    // Write to a log file or stderr
    fprintf(stderr, "[FakeASPI] %s\n", buffer);
}

static BOOL ConnectToEmulator() {
    struct sockaddr_in server;
    WSADATA wsaData;

    if (!winsock_init) {
        if (WSAStartup(MAKEWORD(2, 2), &wsaData) != 0) {
            LogMsg("WSAStartup failed");
            return FALSE;
        }
        winsock_init = TRUE;
    }

    if (emu_socket != INVALID_SOCKET) return TRUE;

    emu_socket = socket(AF_INET, SOCK_STREAM, 0);
    if (emu_socket == INVALID_SOCKET) {
        LogMsg("Socket creation failed");
        return FALSE;
    }

    server.sin_family = AF_INET;
    server.sin_addr.s_addr = inet_addr("127.0.0.1");
    server.sin_port = htons(9999);

    if (connect(emu_socket, (struct sockaddr*)&server, sizeof(server)) < 0) {
        LogMsg("Connection to emulator failed. Error: %d", WSAGetLastError());
        closesocket(emu_socket);
        emu_socket = INVALID_SOCKET;
        return FALSE;
    }

    LogMsg("Connected to Virtual SEM Emulator");
    return TRUE;
}

static int SendAll(SOCKET sock, const char *data, int length) {
    int sent = 0;
    while (sent < length) {
        int r = send(sock, data + sent, length - sent, 0);
        if (r <= 0) {
            return -1;
        }
        sent += r;
    }
    return sent;
}

static int RecvAll(SOCKET sock, char *data, int length) {
    int received = 0;
    while (received < length) {
        int r = recv(sock, data + received, length - received, 0);
        if (r <= 0) {
            return -1;
        }
        received += r;
    }
    return received;
}

/* --- Exported Functions --- */

DWORD __cdecl GetASPI32SupportInfo(void) {
    LogMsg("GetASPI32SupportInfo called");
    // LOBYTE: Adapters (1), HIBYTE: Status (SS_COMP = 1)
    return (1 << 8) | 1;
}

DWORD __cdecl SendASPI32Command(PSRB srb_ptr) {
    SRB_Header *header = (SRB_Header*)srb_ptr;
    SRB_ExecSCSICmd *cmd = (SRB_ExecSCSICmd*)srb_ptr;
    
    // LogMsg("SendASPI32Command: Cmd=%d", header->SRB_Cmd);

    header->SRB_Status = SS_PENDING;

    if (header->SRB_Cmd == SC_HA_INQUIRY) {
        PSRB_HAInquiry inq = (PSRB_HAInquiry)srb_ptr;
        memset(inq, 0, sizeof(*inq));
        inq->SRB_Cmd = SC_HA_INQUIRY;
        inq->SRB_Status = SS_COMP;
        inq->SRB_HaId = 0;
        inq->HA_Count = 1;
        inq->HA_SCSI_ID = 7;
        memcpy(inq->HA_ManagerId, "FakeASPI", 8);
        memcpy(inq->HA_Identifier, "JEOL SEM", 8);
        memcpy(inq->HA_Unique, "VSEM", 4);
        return SS_COMP;
    }

    if (header->SRB_Cmd == SC_GET_DEV_TYPE) {
        PSRB_GDEVBlock dev = (PSRB_GDEVBlock)srb_ptr;
        dev->SRB_Status = SS_COMP;
        dev->SRB_DeviceType = 0x03;
        return SS_COMP;
    }

    if (header->SRB_Cmd == SC_EXEC_SCSI_CMD) {
        if (!ConnectToEmulator()) {
            header->SRB_Status = SS_ERR;
            return SS_ERR;
        }

        DWORD cdb_len = cmd->SRB_CDBLen;
        BYTE dir = 0;
        if (cmd->SRB_Flags & SRB_DIR_IN) {
            dir = 1;
        } else if (cmd->SRB_Flags & SRB_DIR_OUT) {
            dir = 2;
        }
        DWORD xfer_len = cmd->SRB_BufLen;

        // 1. Send Header (CDB len + direction + transfer len)
        char header_buf[9];
        memcpy(header_buf, &cdb_len, 4);
        memcpy(header_buf + 4, &dir, 1);
        memcpy(header_buf + 5, &xfer_len, 4);
        if (SendAll(emu_socket, header_buf, sizeof(header_buf)) != sizeof(header_buf)) {
            LogMsg("Send Header failed");
            closesocket(emu_socket);
            emu_socket = INVALID_SOCKET;
            header->SRB_Status = SS_ERR;
            return SS_ERR;
        }

        // 2. Send CDB
        if (SendAll(emu_socket, (char*)cmd->CDBByte, cdb_len) != (int)cdb_len) {
            LogMsg("Send CDB failed");
            closesocket(emu_socket);
            emu_socket = INVALID_SOCKET;
            header->SRB_Status = SS_ERR;
            return SS_ERR;
        }

        // 3. Send Data-Out if needed
        if (dir == 2 && xfer_len > 0) {
            if (!cmd->SRB_BufPointer) {
                LogMsg("Send Data-Out failed: NULL buffer");
                closesocket(emu_socket);
                emu_socket = INVALID_SOCKET;
                header->SRB_Status = SS_ERR;
                return SS_ERR;
            }
            if (SendAll(emu_socket, (char*)cmd->SRB_BufPointer, xfer_len) != (int)xfer_len) {
                LogMsg("Send Data-Out failed");
                closesocket(emu_socket);
                emu_socket = INVALID_SOCKET;
                header->SRB_Status = SS_ERR;
                return SS_ERR;
            }
        }

        // 4. Receive Status (1 byte)
        BYTE status = 0;
        if (RecvAll(emu_socket, (char*)&status, 1) <= 0) {
            LogMsg("Recv Status failed");
            closesocket(emu_socket);
            emu_socket = INVALID_SOCKET;
            header->SRB_Status = SS_ERR;
            return SS_ERR;
        }

        // 5. Receive Data Len (4 bytes)
        DWORD data_len = 0;
        if (RecvAll(emu_socket, (char*)&data_len, 4) <= 0) {
            LogMsg("Recv DataLen failed");
            closesocket(emu_socket);
            emu_socket = INVALID_SOCKET;
            header->SRB_Status = SS_ERR;
            return SS_ERR;
        }

        // 6. Receive Data
        if (data_len > 0) {
            // Ensure we don't overflow the SRB buffer
            if (data_len > cmd->SRB_BufLen) {
                LogMsg("Warning: Emu returned %d bytes, buffer is %d", data_len, cmd->SRB_BufLen);
            }
            
            DWORD bytes_to_read = (data_len < cmd->SRB_BufLen) ? data_len : cmd->SRB_BufLen;
            DWORD bytes_read = 0;
            
            // Log pointer address
            // LogMsg("Writing %d bytes to buffer at %p", bytes_to_read, cmd->SRB_BufPointer);

            if (RecvAll(emu_socket, (char*)(cmd->SRB_BufPointer), bytes_to_read) <= 0) {
                LogMsg("Recv Data failed");
                closesocket(emu_socket);
                emu_socket = INVALID_SOCKET;
                header->SRB_Status = SS_ERR;
                return SS_ERR;
            }
            bytes_read = bytes_to_read;
            
            // Drain excess data if emulator sent more than buffer size
            if (data_len > cmd->SRB_BufLen) {
                DWORD excess = data_len - cmd->SRB_BufLen;
                char trash[1024];
                DWORD drained = 0;
                while (drained < excess) {
                    int chunk = (excess - drained) > sizeof(trash) ? sizeof(trash) : (excess - drained);
                    int r = RecvAll(emu_socket, trash, chunk);
                    if (r <= 0) {
                          // If drain fails, close socket to be safe
                        closesocket(emu_socket);
                        emu_socket = INVALID_SOCKET;
                        break;
                    }
                    drained += r;
                }
                LogMsg("Drained %d excess bytes", drained);
            }
            
            // Debug: Print first 16 bytes of buffer
            if (bytes_read >= 8 && cmd->SRB_BufPointer) {
                 char *b = (char*)cmd->SRB_BufPointer;
                 LogMsg("Buffer[0-15]: %02X %02X %02X %02X %02X %02X %02X %02X %c%c%c%c %02X %02X %02X %02X",
                    b[0]&0xFF, b[1]&0xFF, b[2]&0xFF, b[3]&0xFF, 
                    b[4]&0xFF, b[5]&0xFF, b[6]&0xFF, b[7]&0xFF,
                    b[8], b[9], b[10], b[11], // Print as chars for VendorID
                    b[12]&0xFF, b[13]&0xFF, b[14]&0xFF, b[15]&0xFF);
            }
        }

        header->SRB_Status = (status == SS_COMP) ? SS_COMP : SS_ERR;
        cmd->SRB_HaStat = 0;
        cmd->SRB_TgtStat = (status == SS_COMP) ? 0 : status;
        
        // Handle PostProc (Event or Callback)
        if (cmd->SRB_Flags & SRB_EVENT_NOTIFY) { 
             SetEvent((HANDLE)cmd->SRB_PostProc);
        }
        
        return header->SRB_Status;
    }

    return SS_ERR;
}
