# SCSI 控制指令細節 (Reverse Engineered)

本文件詳列 `SEM32.DLL` 與 SEM 硬體通訊的底層報文結構。

## 指令公共結構 (CDB Context)
- **傳輸層**: SCSI Vendor Specific Commands (ASPI)
- **發送指令**: `FUN_10021aee(cdb, len)`
- **讀取數據**: `FUN_1002177c(opcode, sub_opcode, buffer, len)`
- **大數據寫入 (LUT)**: `FUN_1002221a(param, buffer)` -> Opcode `0xE0`
- **基礎延遲**: 5000ms (Timeout)
- **字節序**: 
  - Mode 0: 大端序 (Big-Endian) `[high low]`
  - Mode 1: 小端序 (Little-Endian) `[low high]` (0x40系列指令)

---

## [0x00 / 0x04 / 0x08] 影像採集與掃描控制 (Imaging & Scan)

### 1. 掃描基本控制 (Group 0)
- **速度 (Set Speed)**: `[00 01 00 04 00 00 high low]`
- **區域 (Area/Window)**: `[00 01 00 04 01 00 high low]`
- **啟動 (Start Scan)**: `[00 01 00 02 09 01]`
- **停止/同步 (Stop Scan)**: `[00 01 00 02 09 00]`
- **凍結 (Freeze)**:
  - Mode 0: `[03 00 00 02 56 state]`
  - Mode 1: `[06 00 00 02 56 state]`
- **同步觸發 (Sync)**: `[00 01 00 02 0A state]`
- **幾何與窗口 (Geometric & Scan Window)**:
  - **幾何模式 (Geo Mode)**: `[00 01 00 04 07 00 state]` (0:Normal, 5:SRT)
  - **水平起點 (Hor Start)**: `[00 01 00 04 07 01 high low]`
  - **水平終點 (Hor End)**: `[00 01 00 04 07 02 high low]`
  - **垂直起點 (Vert Start)**: `[00 01 00 04 07 03 high low]`
  - **垂直終點 (Vert End)**: `[00 01 00 04 07 04 high low]`
- **電源同步 (Power Sync)**:
  - Mode 0: `[03 01 00 02 57 (00:50Hz/01:60Hz)]`
  - Mode 1:
    - `[00 01 00 04 10 00 00 (00:50Hz/01:60Hz)]`
    - `[06 00 00 02 57 (02:50Hz/04:60Hz)]`
    - `[03 01 00 06 40 50 0F 01 00 (32:50Hz/3C:60Hz)]`

- **字元數據 (Char Data)**:
  - Mode 0: `[00 01 00 05 05 00 char x y]`
  - Mode 1: `[06 00 00 08 70 40 00 char 00 x 00 y]`
- **命令字串 (Command String)**:
  - Mode 1: `[03 00 00 (strlen+7) 40 20 0A (strlen+2) 00 string... 0D]`
    - 總長度字段 = strlen + 7
    - 內部長度字段 = strlen + 2
    - 字串後跟 0x0D 結束符
    - 最大長度限制: 40 (0x28) 字符
- **清除文字 (Clear Text)**:
  - Mode 0: `[00 01 00 02 06 00]`
  - Mode 1: `[06 00 00 02 70 38]`
- **發送文字 (Set Tx Chr)**: `[03 01 00 06 40 01 00 01 00 val]` (M1)

### 2. 影像採集與輔助 (Group 4 / E0)
- **採集請求 (Req Video)**: `[04 01 00 04 1e 07 00 01]`
- **採集停止 (Stop Video)**: `[04 00 00 04 1e 07 01 01]`
- **自動增益 (Auto Gain)**: `[04 01 00 04 1E 06 01 val]`
- **自動偏置 (Auto Offset)**: `[04 01 00 04 1E 06 00 val]`
- **Stig X Wobb**: `[04 00 00 04 1E 15 00 val]`
- **Stig Y Wobb**: `[04 00 00 04 1E 16 00 val]`
- **Z-Sensor Gain**: `[04 01 00 04 1E 05 01 val]`
- **Z-Sensor Offset**: `[04 01 00 04 1E 05 00 val]`
- **Z-Sensor AD 請求**: `[04 01 00 04 1E 07 00 00]`
- **曝光調整 (Exp Adj)**: `[04 00 00 04 1E 0C param1 param2]`
- **平均化 LUT (Averaging)**: `[E0 00 (sub) 00 00 00 01 00 00 00]`
  - Sub參數：0=主掃描LUT, 1=SCAN1, 2=SCAN2, 3=SCAN3
  - Payload: 64KB (0x10000 bytes) buffer

### 3. 高級模式與圖形 (Group 8)
- **PCD 模式**:
  - Mode 0: `[08 01 00 02 73 state]`
  - Mode 1 ON: `[08 01 00 0E 40 20 0A 09 00 ...]` (Length 18)
  - Mode 1 OFF: `[08 01 00 0F 40 20 0A 0A 00 ...]` (Length 19)

---

## [0x01] 真空與排氣 (Vacuum & Vent)
- **啟動抽真空 (Start Evac)**:
  - Mode 0: `[01 01 00 02 40 01]`
  - Mode 1: `[01 01 00 06 40 38 00 01 00 01]`
- **請求真空狀態 (Req Vac Status)**:
  - Mode 0: `[01 00 00 02 44 00]`
- **請求到達壓力 (Req Arrival Pres)**:
  - Mode 0: `[01 00 00 02 44 01]`
- **請求閥門位置 (Req Valve Pos)**:
  - Mode 0: `[01 00 00 02 44 02]`
- **啟動放氣 (Start Vent)**:
  - Mode 0: `[01 01 00 02 41 01]`
  - Mode 1: `[01 01 00 06 40 38 00 01 00 00]`
- **ALC 抽真空 (ALC Evac)**:
  - Mode 0: `[01 01 00 02 45 01]`
  - Mode 1: `[01 01 00 06 40 38 00 01 00 02]`
- **ALC 放氣 (ALC Vent)**:
  - Mode 0: `[01 01 00 02 46 01]`
  - Mode 1: `[01 01 00 06 40 38 00 01 00 03]`
- **LBG 抽真空 (LBG Evac)**:
  - Mode 0: `[01 01 00 02 42 01]`
  - Mode 1: `[01 01 00 06 40 38 00 01 00 01]`
- **Evac 操作模式**: `[01 00 00 02 77 (E1:OFF/E0:ON)]`
- **真空模式設置 (Vacuum Mode)**: `[01 01 00 04 40 44 ...]` (M1)


- **Evac 系統類型**:
  - Mode 0: `[F0 00 00 02 65 flag]`
  - Mode 1: `[F0 00 00 06 40 18 04 01 00 val]`
- **壓力調整模式**: `[05 00 00 04 71 00 high low]`
- **壓力自動**: `[05 00 00 04 71 05 high low]`
- **壓力手動**: `[05 00 00 04 71 16 00 val]`
- **啟動壓力搜尋 (Start Pressure Search)**: `[05 00 00 04 71 01 00 01]`
- **孔徑選擇 (Orifice Diam)**: `[05 00 00 04 71 02 high low]`
- **釋放閥門鎖 (Release Valve Lock)**: `[05 00 00 04 71 03 00 00]`

### 2. 高壓與燈絲 (Group 2 / 7)
- **加速電壓 (Accv)**: `[02 01 00 08 40 02 01 03 00 00 val 00]` (M1)
- **HT On/Off**: `[02 01 00 07 40 02 00 02 00 30 state]` (M1)
- **燈絲數值 (Fila)**: `[02 01 00 08 40 02 01 03 00 14 val 00]` (M1)
- **燈絲模式 (Fila Mode)**: `[07 01 00 07 40 1A 04 02 00 01 mode]` (M1)
- **重置電子槍偏壓 (Reset Gun Bias)**:
  - Mode 0: `[02 01 00 02 1F (82:Normal/8B:LBG)]`
  - Mode 1: `[02 01 00 08 40 41 24 03]`

### 3. 光學透鏡 (Group 3)
- **倍率 (Mag)**: `[03 01 00 08 40 02 01 03 00 10 low high]` (M1)
- **倍率相對 (Mag Rel)**:
  - Mode 0: `[03 01 00 02 2D step]`
  - Mode 1: `[03 01 00 05 42 33 00 low high]`
- **物鏡微調 (OL Fine)**: `[03 01 00 08 40 02 01 03 00 03 low high]`
- **工作距離 (WD)**: `[03 01 00 08 40 02 01 03 00 11 low high]`
- **OL Wobbler**: `[03 01 00 07 40 02 00 02 00 14 state]` (M1)
- **蜂鳴器 (Buzzer)**:
  - Mode 1: `[03 01 00 06 40 02 00 01 00 ID]`
    - IDs: `0x28` (Short), `0x29` (Long), `0x2A` (Error), `0x2B` (Off)
- **電子束遮斷 (Blanking)**:
  - Mode 0: `[03 01 00 02 47 state]`
  - Mode 1: `[03 01 00 06 40 02 00 01 00 12]` (Toggle)
- **濾鏡/增益 (Filter/Gain)**: `[03 01 00 02 51 val]` (Mask 0x03=Filter, 0x04=Gain)
- **陰影 (Shadow)**: `[03 01 00 02 50 val]`
- **動態聚焦 (DFU)**: `[03 01 00 07 40 02 00 02 00 15 val]` (M1)
- **SCS 模式**: `[03 01 00 06 40 1C 04 01 00 val]` (M1)
- **極性控制 (Polarity)**: `[03 01 00 02 5C state]`
- **WD 校正 (WD Correct)**:
  - Mode 0: `[03 00 00 02 1D val]`
  - Mode 1: `[03 01 00 07 40 04 02 02 00 01 val]`
- **AFC 絕對值**: `[03 01 00 04 10 00 high low]` (Mode 0 Only)

### 3a. 相對調整 (Relative Adjustments) - Group 3 (Mode 1 uses 0x42)
- **亮度相對 (Brt Rel)**:
  - Mode 0: `[03 01 00 02 36 step]`
  - Mode 1 Coarse: `[03 01 00 05 42 35 00 low high]`
  - Mode 1 Fine: `[03 01 00 05 42 36 00 low high]`
- **對比相對 (Cont Rel)**:
  - Mode 0: `[03 01 00 02 35 step]`
  - Mode 1: `[03 01 00 05 42 34 00 low high]`
- **聚光鏡相對 (CL Rel)**:
  - Mode 0 Coarse: `[03 01 00 02 28 step]`
  - Mode 1 Coarse: `[03 01 00 05 42 39 00 low high]`
  - Mode 0 Fine: `[03 01 00 04 08 01 high low]`
  - Mode 1 Fine: `[03 01 00 05 42 3d 00 low high]`
- **物鏡相對 (OL Rel)**:
  - Mode 1 Coarse: `[03 01 00 05 42 32 00 low high]`
  - Mode 1 Fine: `[03 01 00 05 42 37 00 low high]`
  - Mode 0: `[03 01 00 04 29 ID high low]`
- **校準相對 (Alin Rel)**:
  - Afc Alin Y: `[03 01 00 02 32 step]`
  - Gun Tilt Y:
    - Mode 0: `[03 01 00 02 26 step]`
    - Mode 1: `[03 01 00 08 40 02 01 03 00 1B 03 step]`

### 4. 校準與增益 (Group 3 / Sub 1E)
- **增益與偏置 (Gain & Offset)**:
  - **水平偏置 (Hor Offset)**: `0x00`
  - **垂直偏置 (Vert Offset)**: `0x01`
  - **水平增益 (Hor Gain)**: `0x02`
  - **垂直增益 (Vert Gain)**: `0x03`
  - **指令格式 (Mode 0)**: `[03 01 00 04 1E ID channel val]`
  - **指令格式 (Mode 1)**: `[03 01 00 05 1E (08-0B) (mode<<4 | channel) high low]`
    - `08`: Hor Offset
    - `09`: Vert Offset
    - `0A`: Hor Gain
    - `0B`: Vert Gain

### 5. 影像位移 (Fine Shift / Image Shift) - Group 3
- **Fine Shift X Abs**:
  - Mode 0: `[03 01 00 04 0E 00 high low]`
  - Mode 1: `[03 01 00 08 40 02 01 03 00 23 low high]`
- **Fine Shift Y Abs**:
  - Mode 0: `[03 01 00 04 0F 00 high low]`
  - Mode 1: `[03 01 00 08 40 02 01 03 00 26 low high]`
- **Fine Shift X Rel**:
  - Mode 0: `[03 01 00 02 2E low]`
  - Mode 1: `[03 01 00 05 42 3E 00 low high]`
- **Fine Shift Y Rel**:
  - Mode 0: `[03 01 00 02 2F low]`
  - Mode 1: `[03 01 00 05 42 3F 00 low high]`
- **Fine Shift XY Abs (Combined)**:
  - Mode 0: `[03 01 00 06 0E 01 x_high x_low y_high y_low]`
- **影像位移點位 (Fine Shift Point)**:
  - Mode 0: `[03 00 00 04 3D sub angle_high angle_low]`
  - Mode 1: `[03 00 00 0A 40 06 02 05 00 sub x_high x_low y_high y_low]`
- **重置影像位移 (Reset Fine Shift)**:
  - Mode 0: `[03 01 00 02 4c 80]`
  - Mode 1: `[03 01 00 06 40 02 00 01 00 24]`
- **重置消像散 (Reset Stigma)**:
  - Mode 0: `[03 01 00 02 58 01]`
  - Mode 1: `[03 01 00 06 40 02 00 01 00 48]`
- **重置透鏡 (OL/CL Reset)**:
  - Mode 0: `[03 01 00 02 48 (01:Normal/11:SemType2)]`
  - Mode 1: `[03 01 00 06 40 02 00 01 00 13]`

### 6. 掃描旋轉 (RRD) - Group 3
- **RRD Angle Abs**:
  - **Mode 0**: `[03 01 00 0A 14 00 b6 b7 b8 b9 ba bb bc bd]`
    - 構建2x2旋轉矩陣: [cos, -sin; sin, cos]
    - Payload (8 bytes): `[cos_high cos_low sin_high sin_low -sin_high -sin_low cos_high cos_low]`
    - 12-bit fixed point (0x000-0xFFF)
    - 角度分象限處理 (0°, 90°, 180°, 270°)
    - 負值自動鉗位到0x000
  - **Mode 1**: `[03 01 00 08 40 02 01 03 00 25 low high]`
    - Parameter ID `0x25`, angle in 0.1 degree steps (0-3600)

---

## [0xC4 - 0xCE] 狀態讀取 (Status Readback)

### 1. 真空與環境 (Group C4 / C5)
- **真空狀態 (Vac Status)**: `[C4 01 00 04]`
- **真空模式 (Vac Mode)**: `[C4 00 00 04]`
- **ALS 狀態**: `[C4 03 00 04]`
- **ALC 序列**: `[C4 04 00 04]`
- **排氣模式 (Vent Mode)**: `[C4 05 00 04]`
- **Evac 系統類型**: `[C4 06 00 04]`
- **閥門詳細狀態**: `[C4 07 00 0C]` (12 bytes)
- **壓力調整模式**: `[C5 04 00 04]`
- **孔徑直徑 (Orifice Diam)**: `[C5 05 00 04]`
- **到達壓力**: `[C5 06 00 04]`
- **手動壓力**: `[C5 07 00 04]`
- **閥門位置 (Valve Pos)**: `[C5 09 00 04]`
- **LV 表讀取**: `[C5 10 00 64]` (100 bytes)
- **LV 表狀態**: `[C5 11 00 04]`
- **字元數據讀取**: 無直接SCSI命令，由應用層 `sem_CallApp` 處理

---

## [0xFA] 通用封裝 (Generic 10-byte Wrapper)
- **Opcode**: `0xFA`
- **結構**: `[FA 00 00 00 00 00 00 00 len_high len_low]`
- 常用於發送 Mode 1 指令的 10 字節 CDB 封裝。

---

## [0xED] 大數據讀取 (Large Data Read)
- **Save Sem Data**: `[ED 82 ...]` (Length 0x1418)
- **Save Auto Data**: `[ED 84 ...]`

---

## [0xC2 / 0xC3] 舊版協議轉發 (Legacy Passthrough)
這是 JSM-5610 軟體為了相容 JSM-5600 硬體 (Hardware Type 0) 而設計的翻譯機制。由 `FUN_10021aee` 動態生成。

### 轉發邏輯
- **C2 隧道**: 用於原本 Group 0 的子代碼 `0x00, 0x01, 0x02, 0x10`。
- **C3 隧道**: 用於原本 Group 0 的子代碼 `0x03` 到 `0x0A`。
  - **算法**: 硬體指令子代碼 = 原始子代碼 - 2。

### 指令映射表 (Hardware Type 0)
| 5600 指令 (CDB) | 功能名稱 | 說明 |
| :--- | :--- | :--- |
| `[C2 00 ...]` | **SetScanSpeed** | 設置掃描速度索引 (0-3) |
| `[C2 01 ...]` | **SetFreeze** | 影像凍結控制 |
| `[C2 10 ...]` | **PowerSync** | 電源頻率同步 (50/60Hz) |
| `[C3 04 00]` | **ClearText** | 清除文字疊加 (原 0x06) |
| `[C3 05 00]` | **GeoMode** | 幾何校正模式 (原 0x07) |
| `[C3 07 01]` | **StartScan** | 啟動掃描 (原 0x09) |
| `[C3 07 00]` | **StopScan** | 停止掃描 (原 0x09) |
| `[C3 08 ...]` | **Sync** | 掃描同步 (原 0x0A) |

---

### 2. 電子槍與高壓 (Group C6 / C7)
- **HT Status**: `[C6 10 00 04]`
- **HT Status (Alt)**: `[C6 19 00 04]`
- **Accv Status**: `[C6 11 00 04]`
- **Fila Value**: `[C6 12 00 04]`
- **Bias Crs/Fine**: `[C6 13/14 00 04]`
- **Emission Current**: `[C6 15 00 04]`
- **Fila Lamp**: `[C6 16 00 04]`
- **Fila DA**: `[C6 17 00 04]`
- **Gun Status (LBG)**: `[C7 00 00 12]` (18 bytes payload)

### 3. 光學與影像狀態 (Group C8)
- **倍率索引 (Mag)**: `[C8 50 00 04]`
- **CL Value (Extended)**: `[C8 30 00 04]`
- **OL Crs Raw**: `[C8 32 00 04]`
- **OL Crs/Fine**: `[C8 32/33 00 04]`
- **物鏡晃動器 (OL Wobbler)**: `[C8 37 00 04]`
- **工作距離 (WD Value)**: `[C8 38 00 04]`
- **消像散 (Stig X/Y)**: `[C8 40/41 00 04]`
- **影像位移 (Fine Shift X/Y)**: `[C8 60/61 00 04]`
- **影像訊號源 (IMS)**: `[C8 82 00 04]`
- **電子束遮斷 (Beam Blank)**: `[C8 24 00 04]`
- **動態聚焦 (DFU)**: `[C8 36 00 04]`
- **AFC Alin X/Y**: `[C8 62/63 00 04]`
- **AFC Value**: `[C8 70 00 04]`
- **AFC Wobbler**: `[C8 71 00 04]`
- **Brightness**: `[C8 81 00 04]`
- **Contrast**: `[C8 80 00 04]`
- **Filter**: `[C8 87 00 04]` (Mask 0x03)
- **Shadow Level**: `[C8 84 00 04]`
- **Gain Status**: `[C8 87 00 04]` (Mask 0x04)
- **EMP Mode**: `[C8 25 00 04]`

### 4. 自動功能數值 (Group CA)
- **ACB Value**: `[CA 90 00 04]`
- **ASD Value**: `[CA 91 00 04]`
- **AFD Value**: `[CA 92 00 04]`
- **PH Auto**: `[CA 94 00 04]`
- **OL WD Adj**: `[CA 97 00 04]`
- **Auto AD Adjust**: `[CA 98 00 04]`
- **Stig X/Y Wobb**: `[CA 9A/9B 00 04]`
- **AGC Type**: `[CA 9D 00 04]`
- **AFS Value**: `[CA 9E 00 04]`

### 5. 樣品台 (Group CB)
- **Holder Type**: `[CB E7 00 04]`
- **Stage Status**: `[CB E5 00 04]`
- **Stage Coords**: `[CB E6 00 1E]`

### 6. 接口與識別 (Group CC / CE / DE)
- **硬體 ID**: `[CC 81 00 04]`
- **Status Size/Count**: `[CC 80 00 04]`
- **FIS 版本**: `[DE 00 00 00 18 00]`
- **FIS 狀態**: `[DE 01 00 00 18 00]`
- **ROM 版本**:
  - **Mode 0**: `[group 00 00 02 6F sub]`
    - Groups: `0, 4, 3, 2, 1, 6, 5, 8, 7`
    - Subs: `0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x30, 0x31, 0x32, 0x33`
  - **Mode 1**: `[group 00 00 06 40 00 0F 01 00 ID]`
    - IDs: `0x01` (Grp 3), `0x02` (Grp 4), `0x10` (Grp 1), `0x11` (Grp 9), `0x12` (Grp 2)
- **硬體測試 (Test Command)**: `[F0 00 len_high len_low payload...]`
- **備份系統數據 (Save SEM Data)**:
  - **請求備份**: `[03 00 00 07 40 08 0F 02 00 01 42]`
  - **讀取數據**: `[ED 82 ...]` (Size 0x1418)
- **Status Size/Count**: `[CC 80 00 04]`
- **VSITF 狀態**: `[CE 00 00 04]`
- **Vent Lock Mode**: `[CE 01 00 04]`
- **ESITF 狀態**: `[CE 02 00 04]`
- **ESITF 擴展**: `[CE 03 00 04]`
- **ESITF 通道**: `[CE 04 00 04]`
- **ESITF 端口**: `[CE 05 00 04]`
- **PCD 狀態**: `[CE 08 00 04]`
- **BCX 狀態**: `[CE 0B 00 04]`
- **SCS 模式**: `[CE 0C 00 04]`
- **EBSD 狀態**: `[CE 0D 00 04]`
- **EBSD Mode**: `[CE 0E 00 04]`
- **MPL 模式**: `[CE 0F 00 04]`
- **DFU Level**: `[CE 35 00 04]`
- **DFU Value**: `[CE 36 00 04]`

---

## [0x09] 樣品台控制 (Stage Control)
- **移動樣品台 (Stage Move Abs)**:
  - Mode 1: `[09 00 00 23 40 06 0A 1E 00 ...]` (Length 39)
- **設置原點 (Set Stage Origin)**:
  - Mode 1: `[09 00 00 10 40 20 0A 0B 00 ...]` (Length 20)
- **背隙補償 (Backlash Correction)**:
  - Mode 1: `[09 00 00 07 40 34 00 02 00 00 01]`
- **樣品台類型 (Stage Type)**:
  - Mode 0: `[01 00 00 02 78 mode]`

---

## [0x08] 輔助偏轉 (Auxiliary Deflection / BCX)
- **BCX 模式**:
  - Mode 0: `[08 00 00 04 72 00 00 00]`
  - Mode 1: `[03 01 00 06 40 08 04 01 00 04]`
- **BCX 點位 (Spot)**:
  - Mode 0: `[08 00 00 04 99 high low]` (X), `[08 00 00 04 9A high low]` (Y)
  - Mode 1: `[08 00 00 0A 40 08 04 05 00 02 x_high x_low y_high y_low]`
- **BCX 區域 (Area)**:
  - Mode 1: `[08 00 00 0E 40 08 04 09 00 11 mid_x_high mid_x_low mid_y_high mid_y_low w_high w_low h_high h_low]`
- **取消 BCX 調整 (Cancel BCX Adj)**:
  - `sem_CancelBcxAdjData` -> software side.

---

## [0x04] 自動化調整 (Auto Functions)
- **Start ACB**: `[04 00 00 02 52 01]`
- **Start AFD**: `[04 00 00 02 53 01]`
- **Start ASD**: `[04 00 00 02 54 01]`
- **Start AFS**: `[04 00 00 02 61 A0]`
- **Start AGA**: `[04 00 00 02 61 B0]`
- **Start AGC**: `[04 00 00 02 61 80]`
- **Start AGB**: `[04 00 00 06 1E 10 00 01 high low]`
- **Start PH Auto**: `[04 01 00 02 5E 01]`
- **Start Auto AD Adjust**: `[04 00 00 04 1E 13 00 01]`
- **Start Z-Sensor Adj**: `[04 00 00 04 1E 14 param 01]`
- **Start OL WD Adj**: `[04 00 00 04 1E 12 param 01]`
- **Stop Auto**: `[04 00 00 02 5B 01]`
- **Auto Gain**: `[04 01 00 04 1E 06 01 val]`
- **Auto Offset**: `[04 01 00 04 1E 06 00 val]`

---

## [Legacy Mode 0] Windows 消息控制 (Messaging)
部分指令在 Mode 0 下通過 `SendMessageA(HWND, 0x4D0, sub_code, 0)` 委託給 `semmgr.exe`。
- **獲取座標 (Get Pos)**: `sub_code = 0x14`
- **獲取原點 (Get Origin)**: `sub_code = 0x21`
- **相對移動 (Relative Move)**: `sub_code = 0x30015` (XY/Z/T/R)
- **倍率鏈接 (Mag Link)**: `sub_code = 0x1F`
- **啟動應用 (Call App)**: 消息 `0x4D5` / `0x466`
