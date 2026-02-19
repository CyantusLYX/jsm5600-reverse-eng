#ifndef _WNASPI32_H_
#define _WNASPI32_H_

#ifdef __cplusplus
extern "C" {
#endif

#include <windef.h>

#define SC_HA_INQUIRY       0x00
#define SC_GET_DEV_TYPE     0x01
#define SC_EXEC_SCSI_CMD    0x02
#define SC_ABORT_SRB        0x03
#define SC_RESET_DEV        0x04
#define SC_SET_HA_PARMS     0x05
#define SC_GET_DISK_INFO    0x06
#define SC_RESCAN_SCSI_BUS  0x07
#define SC_GETSET_TIMEOUTS  0x08

#define SS_PENDING          0x00
#define SS_COMP             0x01
#define SS_ABORTED          0x02
#define SS_ABORT_FAIL       0x03
#define SS_ERR              0x04
#define SS_INVALID_CMD      0x80
#define SS_INVALID_HA       0x81
#define SS_NO_DEVICE        0x82

#define SRB_POSTING         0x01
#define SRB_ENABLE_RESIDUAL_COUNT 0x04
#define SRB_DIR_IN          0x08
#define SRB_DIR_OUT         0x10
#define SRB_EVENT_NOTIFY    0x40

#pragma pack(1)

typedef struct {
    BYTE  SRB_Cmd;
    BYTE  SRB_Status;
    BYTE  SRB_HaId;
    BYTE  SRB_Flags;
    DWORD SRB_Hdr_Rsvd;
} SRB_Header, *PSRB_Header;

typedef struct {
    BYTE  SRB_Cmd;
    BYTE  SRB_Status;
    BYTE  SRB_HaId;
    BYTE  SRB_Flags;
    DWORD SRB_Hdr_Rsvd;
    BYTE  SRB_Target;
    BYTE  SRB_Lun;
    WORD  SRB_Rsvd1;
    DWORD SRB_BufLen;
    BYTE  *SRB_BufPointer;
    BYTE  SRB_SenseLen;
    BYTE  SRB_CDBLen;
    BYTE  SRB_HaStat;
    BYTE  SRB_TgtStat;
    void  (__cdecl *SRB_PostProc)(void *);
    void  *SRB_Rsvd2;
    BYTE  SRB_Rsvd3[16];
    BYTE  CDBByte[16];
    BYTE  SenseArea[32+2];
} SRB_ExecSCSICmd, *PSRB_ExecSCSICmd;

typedef union {
    SRB_Header      common;
    SRB_ExecSCSICmd cmd;
} SRB, *PSRB, *LPSRB;

#pragma pack()

DWORD __cdecl GetASPI32SupportInfo(void);
DWORD __cdecl SendASPI32Command(LPSRB);

#ifdef __cplusplus
}
#endif

#endif
