# JSM-5600 HT 無法開啟 — 問題分析報告

> **日期:** 2026-02-11  
> **機型:** JSM-5600（實際可能為 JSM-5610，見下文）  
> **軟體版本:** 5610E Ver5.26（Jsm5000.exe + SEM32.DLL）  
> **運行環境:** Linux + Wine shim（fake_wnaspi32.dll → TCP bridge → /dev/sgX）  

---

## 一、症狀

按下「HT Ready」按鈕後：
- 軟體發送 SetHT(1) 指令，SCSI 裝置**回應成功**（status=1）
- 但隨後讀取 GetHTStatus 始終返回 `0`（HT OFF）
- HT 高壓**沒有實際開啟**

---

## 二、初始化序列分析（從 SCSI 日誌）

以下是 `sem_InitSystem` 的完整初始化過程，從日誌 `sem_session_20260210_170826.log` 開頭擷取：

### 2.1 裝置識別

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

### 2.2 型號通知

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

**已確認：** `C:\windows\Sem.ini` 中設定 `[System] Type=JSM-5610`，與日誌中的 `3E 01` 完全吻合。

```ini
; 實際檔案位置: ~/.wine/drive_c/windows/Sem.ini
[System]
Type=JSM-5610
Version=5.26
Copyright=2001,2005
UserMode=0
Path=C:\SEM
[Image File]
SaveComp=50
[Option]
DTP=ON
```

### 2.3 電源狀態檢查

| 順序 | 時間 | 指令 | 結果 | 解讀 |
|------|------|------|------|------|
| 5 | 17:08:26.910 | `02 00 00 00 00 00` | Status=1（成功，無 sense data） | SEM 非冷開機狀態 |

`CheckSemStatus`（`FUN_10021475`）判斷邏輯：
- Status 成功 + 無 sense data → 返回 **1**（SEM 正在運行）
- 只有返回 **2**（`UNIT ATTENTION` + `ASC=0x29` Power On Reset）才會觸發 `sem_ReqVacuumStatus`

### 2.4 ⚠️ 真空初始化 — 未執行

因為 CheckSemStatus 返回 1（非冷開機），`sem_ReqVacuumStatus` **完全沒有被呼叫**。

以下三條指令在日誌中**完全不存在**：
```
01 01 00 02 63 FF   (真空監控初始化 1)
01 01 00 02 65 FF   (真空監控初始化 2)
01 01 00 02 64 FF   (真空監控初始化 3)
```

如果 SEM 硬體端需要這些初始化指令才能正確回報狀態或允許 HT 操作，這可能是問題之一。

### 2.5 後續初始化（正常完成）

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

## 三、HdwType / Mode 系統（逆向 SEM32.DLL）

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
| 1 | Wait | 等待中 |
| 2 | Pre Evac | 預抽真空 |
| 3 | Evac | 正在抽真空 |
| **4** | **Ready** | **真空就緒** ✅ |
| 5 | Vent | 通氣/破真空中 |
| 6 | EV Ready | 低真空就緒 |

日誌中 `GetVacStatus`（`C4 01`）返回 `00 01 00 04`，解析後 = **4（Ready）**。  
**真空是就緒的，不是問題所在。**

---

## 五、HT Ready 操作時序（第二個 session 日誌）

```
17:09:11.518  FA → 03 00 00 02 56 00    (未知初始化指令)
17:09:11.562  C2 01                      SetFreeze
17:09:11.606  FA → 06 00 00 02 70 31    (未知)
17:09:11.693  C2 00 00 00 01 00         SetScanSpeed(1) legacy
17:09:12.013  FA → 03 01 00 02 51 03    SetFilter(3)
17:09:12.056  FA → 03 01 00 02 4B 01    SetScanSpeed(1) via FA

--- 使用者按下 HT Ready ---

17:09:23.236  FA → 02 01 00 02 40 01    SetHT(1) ← 第一次嘗試
17:09:23.237  Status=1 (成功)

17:10:11.551  FA → 02 01 00 02 40 01    SetHT(1) ← 再次嘗試
17:10:11.552  Status=1 (成功)

17:10:31.227  C4 01                     GetVacStatus → 00 01 00 04 (Ready)
17:10:31.354  FA → 01 01 00 02 43 21    (未知指令)
17:10:57.012  FA → 02 01 00 02 00 01    (未知指令)

17:11:17~18   FA → 02 01 00 02 40 01    SetHT(1) × 3 次重複

17:11:22.636  C6 10                     GetHTStatus → 00 00 00 00 (HT OFF) ❌
17:11:24.387  Session Ended
```

**SetHT 指令格式完全正確（Mode 0），SCSI 回應成功，但硬體沒有執行。**

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
- `CC 81` 對 JSM-5600/5610 應該返回什麼 model code？
- 預期是 `0x15E0`（5600）還是其他值？

### ~~問題 2：sem.ini 的 Type 設定~~ ✅ 已確認
`C:\windows\Sem.ini` 中 `[System] Type=JSM-5610`，與軟體版本 5610E_Ver5.26 一致。
日誌中的 `3E 01` 完全正確。**此項不是問題。**

### 問題 3：HT ON 的前置條件
SetHT 指令 `02 01 00 02 40 01` SCSI 回應成功，但 GetHTStatus 始終為 0。
- HT 開啟是否需要燈絲先加熱？（FIS 全部返回零）
- 硬體是否有其他 interlock 條件（如 gun chamber 真空、emission current 等）？
- 硬體拒絕 HT ON 時是否有任何方式回報原因？

### 問題 4：ReqVacuumStatus 是否需要
`sem_ReqVacuumStatus`（三條 `01 01 00 02 63/64/65 FF` 指令）在非冷開機時不會發送。
- 在原始 Windows 環境下，這三條指令是否只在第一次上電時發送一次就夠了？
- 還是每次軟體啟動都需要重新發送？

### 問題 5：Wine/Bridge 透明度
所有 SCSI 指令都是原封不動 pass-through 到 /dev/sgX（Linux SCSI Generic），沒有任何修改或過濾。
- 是否有任何 ASPI 層面的行為（例如 timeout 設定、abort 機制）在 Linux SG_IO 中沒有正確模擬？
- 原始環境使用 WNASPI32 的 Adaptec SCSI 卡，現在用的是什麼 SCSI 控制器？

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
