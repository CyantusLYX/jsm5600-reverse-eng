# JSM-5600 所有操作無回應 — 問題分析報告（含根因定位）

> **日期:** 2026-02-11（更新：2026-02-12）  
> **機型:** JSM-5600  
> **軟體版本:** 5610E Ver5.26（Jsm5000.exe + SEM32.DLL）  
> **運行環境:** Linux + Wine shim（fake_wnaspi32.dll → TCP bridge → /dev/sgX）  
> **sem.ini:** `[System] Type=JSM-5600`（已修正，原為 JSM-5610）

---

## 〇、根因總結 ⭐

**所有問題的根本原因：Bridge 層未正確轉發 SCSI sense data（感測資料）。**

### 因果鏈
```
1. SEM 硬體在開機後首次通訊時回報 UNIT ATTENTION (Sense Key=0x06, ASC=0x29)
   → 表示「Power On / Reset」

2. SEM32.DLL 的 CheckSemStatus() 嘗試偵測此狀態
   → 需要讀取 SRB 結構中的 SRB_TargStat (=0x02) + SenseArea[2] (=0x06) + SenseArea[12] (=0x29)

3. ❌ Bridge (fake_wnaspi32.c) 未轉發 SCSI target status 和 sense data
   → SRB_TargStat 被設為 4 (SS_ERR) 而非 0x02 (CHECK_CONDITION)
   → SenseArea 完全沒有填入

4. CheckSemStatus() 無法偵測 power-on → 返回 0 而非 2

5. sem_InitSystem() 跳過 sem_ReqVacuumStatus()
   → 三條真空初始化指令 (63 FF, 64 FF, 65 FF) 從未發送

6. 硬體停在「Wait」(未初始化) 狀態 → VacuumStatus = 1 (Wait)

7. 所有後續操作命令（HT、Vent、Evac、AccV）被硬體靜默忽略
```

### 需要修復的程式碼
- **`bridge_sem.py`**: TCP 回應加入 `scsi_target_status` + `sense_data`
- **`fake_wnaspi32.c`**: 接收並填入 `SRB_TgtStat` 和 `SRB_SenseArea[]`

---

## 一、症狀

### 初始症狀（sem.ini 修正前）
- 按下「HT Ready」，SetHT(1) SCSI 回應成功，但 GetHTStatus 始終返回 0
- VacuumStatus = 4 (Ready)，真空似乎正常

### 修正 sem.ini 後的症狀（JSM-5610 → JSM-5600）
- HT 仍然無法開啟
- **Vent（通氣）**：按下無反應，VacStatus 不變
- **Evac（抽真空）**：按下無反應
- **AccV（加速電壓調整）**：改為 27kV 或 7kV 均無反應
- VacuumStatus 退化為 **1 (Wait)**（之前是 4=Ready）
- **所有操作指令的 SCSI 回應都是成功（Status=1），但硬體完全不執行**

---

## 二、Bridge 層 SCSI Sense Data 缺失（根因詳述）

### 2.1 正確流程（原始 Windows + WNASPI32）

```
SEM32.DLL → SendASPI32Command(SRB)
         → WNASPI32.DLL → Adaptec SCSI 卡 → 硬體
         ← WNASPI32 填入完整 SRB：
             SRB_Status    = SS_ERR (0x04)
             SRB_TargStat  = CHECK_CONDITION (0x02)
             SRB_SenseArea = [70 00 06 ... 29 ...]  ← sense data 完整
         ← SEM32.DLL 讀取 SRB → 偵測到 UNIT ATTENTION → 返回 2
```

### 2.2 實際流程（Wine + Bridge）

```
SEM32.DLL → SendASPI32Command(SRB)
         → fake_wnaspi32.dll → TCP socket → bridge_sem.py → /dev/sgX
         ← bridge_sem.py 收到 Linux SG_IO 結果：
             status = 0x02 (CHECK_CONDITION)
             sense  = 70 00 06 ... 29 ...
         ← bridge_sem.py 簡化為 1 byte: status=4 (SS_ERR) 經 TCP 回傳
         ← fake_wnaspi32.c 設定：
             SRB_Status   = SS_ERR (0x04)     ← ✅ 正確
             SRB_TargStat = 4 (SS_ERR)        ← ❌ 應該是 0x02
             SRB_SenseArea = [未填入]          ← ❌ 完全缺失
         ← SEM32.DLL 讀取 SRB_TargStat：4 ≠ 0x02 → 跳過 sense 檢查 → 返回 0
```

### 2.3 CheckSemStatus 函式邏輯（FUN_10021475 @ SEM32.DLL）

```c
// SRB 結構偏移（基於 ASPI Win32 定義）
// Offset 0x01: SRB_Status    → 需要 == 0x04 (SS_ERR)         ✅ bridge 有設定
// Offset 0x17: SRB_TargStat  → 需要 == 0x02 (CHECK_CONDITION) ❌ bridge 設成 4
// Offset 0x42: SenseArea[2]  → 需要 == 0x06 (UNIT ATTENTION)  ❌ bridge 未填入
// Offset 0x4C: SenseArea[12] → 需要 == 0x29 (Power On/Reset)  ❌ bridge 未填入

if (SRB_Status == 0x04) {                          // SS_ERR
    if (SRB_TargStat == 0x02) {                    // CHECK_CONDITION  ← 失敗位置!
        if (SenseArea[2] == 0x06 && SenseArea[12] == 0x29) {
            OutputDebugString("SCSI PowerON or Reset");
            return 2;                               // ← 觸發真空初始化
        }
    }
}
return 0;                                          // ← 實際走到這裡
```

### 2.4 日誌中的證據

**Init session log (221057)**，第 12 行：
```
[ERR] GetHTHeartbeat | CDB: 02 00 00 00 00 00 | Status=4 
  | SCSI=0x02 Host=0x00 Driver=0x08 
  | Sense=70 00 06 00 00 00 00 0A 00 00 00 00 29 00 00 00 00 00
```

bridge_sem.py **正確偵測到** SCSI status=0x02 和完整 sense data，但只把 `status=4` 送回 fake_wnaspi32.c。

### 2.5 修復方案

**`bridge_sem.py`** — 修改 TCP 回應格式：
```python
# 現在的格式（5 bytes）:
resp_header = struct.pack("<BI", status, len(resp_data))

# 修改為（5 + 1 + 1 + N bytes）:
resp_header = struct.pack("<BIBB", 
    status,                    # ASPI 狀態 (1=COMP, 4=ERR)
    len(resp_data),            # 資料長度
    scsi_target_status,        # SCSI target status (0x00/0x02)
    len(sense_bytes)           # sense data 長度
)
conn.sendall(resp_header)
if resp_data:
    conn.sendall(resp_data)
if sense_bytes:
    conn.sendall(sense_bytes)  # 追加 sense data
```

**`fake_wnaspi32.c`** — 接收並填入 SRB：
```c
// 接收額外的 target status 和 sense data
BYTE scsi_tgt_status = 0;
BYTE sense_len = 0;
RecvAll(emu_socket, (char*)&scsi_tgt_status, 1);
RecvAll(emu_socket, (char*)&sense_len, 1);

cmd->SRB_TgtStat = scsi_tgt_status;   // 填入正確的 SCSI target status

if (sense_len > 0) {
    BYTE sense_buf[32];
    int to_read = (sense_len < 32) ? sense_len : 32;
    RecvAll(emu_socket, (char*)sense_buf, to_read);
    // 複製到 SRB 的 SenseArea
    int to_copy = (to_read < cmd->SRB_SenseLen) ? to_read : cmd->SRB_SenseLen;
    memcpy(cmd->SenseArea, sense_buf, to_copy);
}
```

---

## 三、初始化序列分析

### 3.1 裝置識別

| 順序 | 時間 | 指令 | 返回資料 | 解讀 |
|------|------|------|---------|------|
| 1 | 17:08:26.654 | `12 00 00 00 24 00` (INQUIRY) | `4A 45 4F 4C...` | 回應 "JEOL"，裝置正常 |
| 2 | 17:08:26.696 | `CC 80` (GetStatusSize) | `02 00 00 80` | StatusSize 相關 |
| 3 | 17:08:26.779 | **`CC 81` (GetHardwareID)** | **`02 00 00 80`** | ⚠️ **與 CC 80 返回完全相同** |

**`CC 81` 返回值解析：**
- Raw data: `02 00 00 80`
- SEM32.DLL 取後 2 bytes `00 80`，做 byte-swap → model code = **`0x0080`**（十進位 128）
- 此值 **不在已知型號表中**（見第三節），走 default 分支
- 結果：`SemType = 0`，`HdwType = 0`

### 3.2 型號通知

| 順序 | 時間 | Payload | 解讀 |
|------|------|---------|------|
| 4 | 17:08:26.865 | `03 00 00 02 3E 01` | 通知硬體型號配置，**CDB[5] = 0x01** |

`FUN_1002a157` 讀取 `sem.ini` → `[System]` → `Type`，比對字串決定 CDB[5]：

| sem.ini Type | SemType | CDB[5] |
|-------------|---------|--------|
| JSM-5600 | 0 | 0x00 |
| JSM-5500 | 2 | 0x01 |
| **JSM-5610** | **0** | **0x01** ← 日誌吻合 ✅ |
| JSM-5510 | 2 | 0x01 |

**已確認並修正：** `C:\windows\Sem.ini` 原設定為 `Type=JSM-5610`（CDB[5]=0x01），已改為 `Type=JSM-5600`。
新日誌（221057）確認發送 `3E 00`（正確的 JSM-5600 值）。

```ini
; 修正後: ~/.wine/drive_c/windows/Sem.ini
[System]
Type=JSM-5600
Version=5.26
UserMode=0
Path=C:\SEM
[Image File]
SaveComp=50
[Option]
DTP=ON
```

### 3.3 電源狀態檢查（關鍵問題所在）

| 順序 | 時間 | 指令 | 結果 | 解讀 |
|------|------|------|------|------|
| 5 (舊日誌) | 17:08:26.910 | `02 00 00 00 00 00` | Status=1 | 成功（非冷開機？）|
| 5 (新日誌) | 22:10:57.439 | `02 00 00 00 00 00` | **Status=4**, SCSI=0x02, Sense=70 00 **06** ... **29** | ⚠️ **UNIT ATTENTION / Power On Reset** |

`CheckSemStatus`（`FUN_10021475`）判斷邏輯：
- 需要 SRB_TargStat=0x02 + Sense Key=0x06 + ASC=0x29 → 返回 **2**（觸發真空初始化）
- **但因為 bridge 未轉發 sense data，實際返回 0** ← 根因（見第二節）

### 3.4 ⚠️ 真空初始化 — 未執行（根因後果）

因為 CheckSemStatus 返回 1（非冷開機），`sem_ReqVacuumStatus` **完全沒有被呼叫**。

以下三條指令在日誌中**完全不存在**：
```
01 01 00 02 63 FF   (真空監控初始化 1)
01 01 00 02 65 FF   (真空監控初始化 2)
01 01 00 02 64 FF   (真空監控初始化 3)
```

如果 SEM 硬體端需要這些初始化指令才能正確回報狀態或允許 HT 操作，這可能是問題之一。

### 3.5 後續初始化（部分完成）

| 時間 | 指令 | 說明 |
|------|------|------|
| 17:08:28.848 | `C3` × 4 | LegacyStatus 讀取 |
| 17:08:29.024 | `03 00 00 02 56 00` | 未知初始化 |
| 17:08:29.068 | `C2 01` | SetFreeze |
| 17:08:29.112 | `06 00 00 02 70 31` | 未知初始化 |
| 17:08:29.201 | `C2 00 00 00 01 00` | SetScanSpeed(1) ✅ |
| 17:08:29.522 | `03 01 00 02 51 03` | SetFilter(3) ✅ |
| 17:08:29.566 | `03 01 00 02 4B 01` | SetScanSpeed(1) via FA ✅ |
| 17:08:29.829 | `E0` × 2 | WriteLUT（65536 bytes × 2）✅ |
| 17:08:30~42 | 大量校準/設定指令 | 正常 |
| 17:08:43~52 | FIS（燈絲）反覆讀取 | **全部返回零** ⚠️ |

---

## 六、HdwType / Mode 系統（逆向 SEM32.DLL）

SEM32.DLL 只有 **兩個 Mode**，由 `HdwType` 全域變數控制：

| HdwType | 指令格式 | 範例 SetHT |
|---------|---------|-----------|
| **0**（舊型機） | 6-byte 短格式 | `02 01 00 02 40 01` |
| **1**（新型機） | 10-11 byte 長格式 | `02 01 00 07 40 02 00 02 00 30 01` |

**已知 model code → HdwType 映射：**

| Model Code (hex) | 十進位 | SemType | HdwType |
|------------------|--------|---------|---------|
| 0x157C | 5500 | 2 | 0 |
| 0x1388 | 5000 | 3 | 0 |
| 0x15AE | 5550 | 6 | 0 |
| 0x15E0 | 5600 | 0 | 0 |
| 0x1612 | 5650 | 5 | 0 |
| 0x170C | 5900 | 1 | **1** |
| 0x1716 | 5910 | 1 | **1** |
| 0x170D | 5901 | 4 | **1** |
| 0x173E | 5950 | 4 | **1** |
| **0x0080**（你的機器） | **128** | **0 (default)** | **0 (default)** |

你的機器返回 `0x0080`，不在任何已知型號中，走了 default。最終 HdwType=0 是正確的（JSM-5600/5610 都是 HdwType=0），但 **`CC 81` 和 `CC 80` 返回完全相同的值很不正常**。

---

## 四、VacuumStatus 對照表

從 Jsm5000.exe UI 處理器逆向而來：

| 值 | 狀態 | 說明 |
|----|------|------|
| 0 | ALC | Airlock Chamber 狀態 |
| **1** | **Wait** | **等待中 / 未初始化** ← 目前的狀態 ⚠️ |
| 2 | Pre Evac | 預抽真空 |
| 3 | Evac | 正在抽真空 |
| 4 | Ready | 真空就緒 |
| 5 | Vent | 通氣/破真空中 |
| 6 | EV Ready | 低真空就緒 |

### 狀態變化紀錄
| 日誌 | GetVacStatus 返回 | VacuumStatus 值 |
|------|-------------------|----------------|
| 舊日誌（sem.ini=JSM-5610）| `00 01 00 04` | 4 (Ready) |
| **新日誌（sem.ini=JSM-5600）** | **`00 01 00 00`** | **1 (Wait)** ← 退化 ⚠️ |

VacStatus 從 Ready 退化為 Wait，因為真空初始化從未執行。

---

## 五、用戶操作測試結果（第二個 session：221139）

### 5.1 Vent（通氣）操作

```
22:12:06.426  FA → 01 01 00 02 42 01    sem_StartEvac() ← DLL 先檢查 LBG
22:13:12.957  FA → 01 01 00 02 42 01    sem_StartEvac() 再次嘗試
22:13:47.282  FA → 01 01 00 02 43 01    sem_StartVent() ← 用戶按 Vent
22:14:05.755  FA → 01 01 00 02 42 01    sem_StartEvac() ← 用戶按 Evac
22:14:15.418  FA → 01 01 00 02 42 01    sem_StartEvac() ← 再次
```
**所有指令 SCSI Status=1（成功），但 VacStatus 始終保持 `00 01 00 00` (Wait)**

### 5.2 AccV（加速電壓）調整

```
22:18:27.336  FA → 02 01 00 02 00 03    sem_SetAccvAbs() index=3 → 27 kV
22:18:46.058  FA → 02 01 00 02 00 17    sem_SetAccvAbs() index=23 → 7 kV
```
**所有指令 SCSI Status=1（成功），但 GetAccvValue 不變**

### 5.3 命令格式對照（Mode 0 = HdwType=0, 6-byte 短格式）

| 功能 | DLL 函式 | CDB[4] | Payload | 狀態 |
|------|---------|--------|---------|------|
| HT ON | sem_SetHT(1) | 0x40 | `02 01 00 02 40 01` | ❌ 無回應 |
| Evac | sem_StartEvac() | 0x42 | `01 01 00 02 42 01` | ❌ 無回應 |
| Vent | sem_StartVent() | 0x43 | `01 01 00 02 43 01` | ❌ 無回應 |
| SetVacMode | sem_SetVacuumMode() | 0x44 | `01 01 00 02 44 XX` | 未測試 |
| AccV | sem_SetAccvAbs() | 0x00 | `02 01 00 02 00 [idx]` | ❌ 無回應 |
| ScanSpeed | sem_SetScanSpeed() | 0x4B | `03 01 00 02 4B XX` | 未確認 |
| Filter | sem_SetFilter() | 0x51 | `03 01 00 02 51 XX` | 未確認 |

---

## 六、FIS（燈絲系統）狀態 — ⚠️ 可疑

初始化期間（17:08:43~52），軟體對 FIS 做了大量讀取：

| 指令 | 說明 | 返回 |
|------|------|------|
| `DE 00` (GetFisVersion) | FIS 韌體版本 | `"FIS     Ver1.21 "` ✅ 正常 |
| `DE 01` (GetFisStatus) × ~15次 | FIS 狀態 | **全部 `00 00 00 00...`** ⚠️ |
| `DE 02` (GetFisData) × ~15次 | FIS 資料 | **全部 `00 00 00 00...`** ⚠️ |
| `DE 03` (GetFisExtStatus) × ~15次 | FIS 擴展狀態 | **全部 `00 00 00 00...`** ⚠️ |

FIS 版本號有正確回應，但所有**狀態和資料都是零**。

**需要確認：燈絲未加熱的情況下，硬體是否會靜默拒絕 HT ON？**

---

## 七、需要向專家確認的問題

### 問題 1：CC 81 返回值
`CC 80`（GetStatusSize）和 `CC 81`（GetHardwareID）返回**完全相同的** `02 00 00 80`。
- 這正常嗎？
- `CC 81` 對 JSM-5600 應該返回什麼 model code？
- 預期是 `0x15E0`（5600）還是其他值？
- 目前走 default 分支（SemType=0, HdwType=0），功能上應該正確。

### 問題 2：UNIT ATTENTION / Power On Reset
新日誌顯示硬體確實回報了 UNIT ATTENTION（Sense Key=0x06, ASC=0x29），表示硬體需要初始化。
- 這是否是 JSM-5600 每次冷開機後的正常行為？
- 如果我們不透過 ASPI，而是直接從 Python 發送 `sem_ReqVacuumStatus` 的三條命令（`63 FF`, `64 FF`, `65 FF`），能否手動完成初始化？

### 問題 3：HT ON 前置條件
- 在真空 Wait 狀態下，硬體是否會靜默拒絕所有操作命令？
- HT 開啟是否需要 VacuumStatus 為 Ready (4)？
- 是否還有其他 interlock（燈絲、emission current 等）？

### 問題 4：感測資料修復後的預期行為
如果修復 bridge 讓 sense data 正確回傳，預期流程：
```
CheckSemStatus() → 偵測到 Power On/Reset → 返回 2
→ sem_ReqVacuumStatus() 發送 63 FF, 64 FF, 65 FF
→ 硬體初始化真空系統
→ VacuumStatus 從 Wait(1) → 最終 Ready(4)
→ HT/Vent/Evac/AccV 命令開始正常工作
```
這個理解是否正確？

---

## 八、Wine 環境 INI 檔案地圖

所有 INI 都在 `~/.wine/drive_c/` 下：

| 路徑 (Wine C:\) | 說明 | 內容摘要 |
|-----------------|------|---------|
| `windows\Sem.ini` | **主設定檔**（SEM32.DLL 讀取） | `[System] Type=JSM-5610` ✅ |
| `windows\SEMINFO.INI` | SEM 儀器狀態備份 | GUN/CL/OL/SCAN/AFC 等參數 |
| `windows\SEMMGR.INI` | SEM Manager 設定 | 檔案對話、stage、計時器設定 |
| `windows\SEMGUI.INI` | GUI 視窗位置/偏好 | 視窗座標、EDS 設定 |
| `windows\ADJUST.INI` | 校準資料 | 電源同步、視訊、MAG offset/gain |
| `windows\AFCALIN.INI` | AFC 校準 | |
| `windows\GUNBIAS.INI` | 電子槍偏壓 | |
| `windows\941stage.ini` | 載台驅動設定 | |
| `windows\DtpNew.ini` | DTP 相關 | |
| `JEOL\SEM\seminfo.ini` | 應用程式目錄副本 | `[System]`（空） |
| `JEOL\SEM\semmgr.ini` | 應用程式目錄副本 | |

**專案副本：** `src/wine/Sem.ini`

---

## 九、檔案參考

| 檔案 | 說明 |
|------|------|
| `src/wine/logs/sem_session_20260210_170826.log` | 完整初始化 session（4314 行）|
| `src/wine/logs/sem_session_20260210_170909.log` | HT Ready 操作 session（114 行）|
| `src/wine/bridge_sem.py` | SCSI pass-through bridge |
| `src/wine/fake_wnaspi32.c` | Wine DLL shim |
| `src/wine/Sem.ini` | SEM 主設定檔（專案副本）|
| SEM32.DLL (Ghidra port 8193) | JEOL SCSI 通訊程式庫 |
| Jsm5000.exe (Ghidra port 8194) | VB6 主程式 |
