---

# JEOL 5600 控制軟體需求規格書 (Logic & GUI)

**專案代號:** J5600-Linux-Rehost
**適用機型:** JEOL 5600 (High Vacuum Only)
**硬體介面:** SCSI (控制信號) + ADC/S-Video (影像信號)

---

## 3. 功能邏輯需求 (Functional Logic Requirements)

此部分定義軟體後端 (Backend) 的運作邏輯，負責將高階操作轉換為 SCSI 指令序列，並處理自動化演算法。

### 3.1 電子槍與高壓控制邏輯 (Electron Gun & HT)

*   **REQ-LOG-001: 燈絲飽和自動化 (Auto Saturation)**
    *   **描述:** 自動尋找燈絲電流的最佳工作點，以獲得最大發射電流同時延長壽命。
    *   **演算法流程:**
        1.  記錄當前發射電流 (Emission Current, I_e)。
        2.  以微小步進增加 SCSI 燈絲電流指令 (Filament Current)。
        3.  等待 200ms 穩定。
        4.  監測 I_e 的變化率 (`dI_e / dFilament`)。
        5.  當變化率低於設定閾值（進入飽和區）時停止增加。
        6.  將燈絲電流設定值回退 1-2 個步進（工作於飽和點膝部）。
*   **REQ-LOG-002: 偏壓自動調整 (Auto Bias)**
    *   **描述:** 根據使用者選擇的加速電壓 (kV)，自動查表或計算並發送對應的 Wehnelt Bias SCSI 指令，確保束流穩定。
*   **REQ-LOG-003: 軟體安全互鎖 (Software Interlock)**
    *   若 SCSI 回傳的真空狀態非 "READY"，軟體必須拒絕發送任何 HT ON 或 Filament Heat 指令。
    *   若運作中偵測到 SCSI 通訊超時 (>500ms)，必須觸發 GUI 警報並嘗試發送 HT OFF 安全指令。

### 3.2 透鏡與掃描控制邏輯 (Lens & Scan Control)

*   **REQ-LOG-010: 放大倍率映射 (Magnification Mapping)**
    *   **描述:** 建立一個查找表 (Lookup Table) 或數學模型，將使用者介面上的 "Mag X" 數值轉換為 JEOL 內部能理解的 SCSI Hex Code。
    *   **邏輯:** 當倍率改變時，軟體需同時計算並調整掃描線圈的電流增益設定。
*   **REQ-LOG-011: 動態步進解析度 (Dynamic Step Resolution)**
    *   **描述:** Focus (物鏡) 與 Stigmator (消像散) 的調整靈敏度需隨放大倍率改變。
    *   **邏輯:**
        *   低倍率時：旋鈕轉動一格 = SCSI 數值改變量大 (Coarse)。
        *   高倍率時 (>10k)：旋鈕轉動一格 = SCSI 數值改變量小 (Fine)。
*   **REQ-LOG-012: 搖擺對中 (Wobbler)**
    *   **描述:** 用於輔助光欄 (Aperture) 對中。
    *   **邏輯:** 軟體以 2-5Hz 的頻率，在當前 Focus SCSI 數值基礎上疊加一個正弦波或方波偏移量 (`Base_Focus ± Delta`)，使影像產生呼吸效應。

### 3.3 影像處理與自動化演算法 (Image Processing & Automation)

由於 PC 無法直接控制掃描速度（由機器內部硬體決定），自動化功能需基於影像回饋迴路 (Image-based Feedback Loop)。

*   **REQ-LOG-020: 自動對焦 (Auto Focus)**
    *   **演算法:**
        1.  定義影像中心 ROI (Region of Interest)。
        2.  切換至 Fast Scan 模式。
        3.  使用爬山演算法 (Hill Climbing) 或搜尋法，調整物鏡電流 (Focus DAC)。
        4.  **評價函數:** 計算 ROI 內的梯度幅值 (Sobel/Laplacian) 或頻域高頻能量 (FFT)。數值越高代表越清晰。
        5.  找到峰值後，發送最終 Focus SCSI 指令。
*   **REQ-LOG-021: 自動消像散 (Auto Stigmator)**
    *   **演算法:** 類似自動對焦，但在 Stig X 和 Stig Y 兩個維度上進行多變數優化，尋找銳利度最大值。
*   **REQ-LOG-022: 自動對比/亮度 (ACB - Auto Contrast Brightness)**
    *   **演算法:**
        1.  計算當前影像的灰階直方圖 (Histogram)。
        2.  **目標:** 將直方圖拉伸至全動態範圍 (0-255) 且分佈均勻。
        3.  **調整:** 透過 SCSI 調整 PMT Gain (Contrast) 和 DC Offset (Brightness)。
        4.  重複採樣直到直方圖符合目標。
*   **REQ-LOG-023: 影像降噪 (Noise Reduction)**
    *   **平均法:** 在 Slow Scan 或 Photo 模式下，對連續擷取的多幀影像進行像素級平均 (Pixel-averaging) 或卡爾曼濾波 (Kalman Filter)，以消除散粒雜訊 (Shot Noise)。
    *   **去交錯 (De-interlacing):** 若訊號源為 S-Video，需實作反交錯演算法以消除梳狀條紋。

### 3.4 真空系統邏輯

*   **REQ-LOG-030: 狀態輪詢 (Status Polling)**
    *   軟體需建立一條獨立的執行緒 (Thread)，每隔固定時間 (如 200ms) 發送 SCSI 查詢指令，獲取真空規讀數、閥門狀態及錯誤代碼。
*   **REQ-LOG-031: 模式切換**
    *   **EVAC:** 發送指令啟動抽氣 -> 監控真空度 -> 達到閾值後更新狀態為 "Ready"。
    *   **VENT:** 發送指令啟動洩壓 -> 監控狀態 -> 更新狀態為 "Air"。

---

## 4. 使用者界面需求 (User Interface Requirements)

目標是建立一個現代化、基於 Qt (C++/Python) 的操作介面，取代舊版 Win98 風格，並支援高解析度螢幕。

### 4.1 主視窗佈局 (Main Layout)

*   **REQ-GUI-001: 整體風格**
    *   採用暗色系主題 (Dark Mode)，減少螢幕光線對操作者觀察螢光屏或暗室環境的干擾。
    *   字體需清晰易讀 (如 Roboto 或 Segoe UI)。
*   **REQ-GUI-002: 影像視窗 (Viewport)**
    *   佔據螢幕最大面積 (至少 70%)。
    *   支援 OpenGL 加速渲染。
    *   **互動:**
        *   滾輪：數位變焦 (Digital Zoom In/Out)。
        *   滑鼠拖曳：在數位變焦狀態下平移影像 (Pan)。
        *   雙擊：將點擊處置中 (透過 Image Shift 或 Stage Move)。
        *   右鍵選單：快速執行 ACB、Auto Focus、Save Image。
*   **REQ-GUI-003: 資訊疊加 (OSD - On Screen Display)**
    *   在影像角落即時顯示（可開關）：
        *   加速電壓 (Ex: `20.0 kV`)
        *   放大倍率 (Ex: `x 5,000`)
        *   標尺 (Scale Bar) (Ex: `----- 10 μm`)
        *   工作距離 (Ex: `WD 10 mm`)

### 4.2 控制面板 (Right Dock / Control Panel)

控制面板應分為多個摺疊式群組 (Collapsible Groups)。

*   **REQ-GUI-010: 電子束控制群組 (Beam Control)**
    *   **HT 開關:** 大型 Toggle Button (ON/OFF)，帶有顏色指示 (綠=Ready, 紅=ON, 灰=OFF)。
    *   **kV 選擇:** 下拉選單 (0.5, 1, 5, 10, 15, 20, 30 kV)。
    *   **Filament:** 顯示飽和度進度條，並提供 "Auto Saturate" 按鈕。
    *   **Spot Size:** 數字選值框 (0-99) 或滑桿。
*   **REQ-GUI-011: 影像調整群組 (Image Adjust)**
    *   **虛擬旋鈕 (Virtual Knobs):** 這是核心互動元件。
        *   **Focus:** 大型旋鈕。支援滑鼠滾輪微調，拖曳粗調。
        *   **Stig X / Stig Y:** 小型雙旋鈕。
        *   **Contrast / Brightness:** 雙旋鈕或滑桿。
    *   **自動按鈕:** ACB, Auto Focus, Auto Stig 快捷鍵。
    *   **Wobbler:** 開關按鈕 (Checkable Button)。
*   **REQ-GUI-012: 掃描模式群組 (Scan Mode)**
    *   **按鈕列:**
        *   `TV` (快速預覽)
        *   `Slow` (高品質觀察)
        *   `Photo` (高畫質擷取，觸發 SCSI 拍照序列)
        *   `Freeze` (凍結當前畫面)
*   **REQ-GUI-013: 樣品台控制 (Stage Control) (若有馬達台)**
    *   顯示 X, Y, Z, R, T 座標數值。
    *   提供 4 向方向鍵 (Joystick simulation)。
    *   提供 "Stage Map" 視窗按鈕。

### 4.3 狀態列 (Status Bar)

*   **REQ-GUI-020: 底部狀態顯示**
    *   **真空狀態:** 圖示 (幫浦動畫) + 文字 (High Vac / Low Vac / Air)。
    *   **發射電流:** 即時數值 (Ex: `Emission: 45 uA`)。
    *   **SCSI 狀態:** 指示燈 (綠=通訊正常, 紅=超時/錯誤)。
    *   **FPS:** 當前影像更新率。

### 4.4 進階功能視窗 (Dialogs & Windows)

*   **REQ-GUI-030: 配方管理器 (Recipe Manager)**
    *   允許使用者儲存/載入一組設定 (kV, WD, Spot Size, Lens Settings)。
    *   應用場景：快速切換 "高解析度模式" 或 "EDX 分析模式"。
*   **REQ-GUI-031: 圖片存檔視窗**
    *   預覽擷取的圖片。
    *   設定存檔路徑、檔名格式 (自動編號/時間戳)。
    *   選擇是否燒錄 OSD 資訊 (Burn-in metadata) 或僅存於 TIFF Header。
*   **REQ-GUI-032: 維護與校正 (Setup & Maintenance)**
    *   **Gun Alignment:** 提供 X/Y 偏轉控制介面，調整電子槍對中。
    *   **Calibration:** 用於校正放大倍率與標尺的精確度 (Pixel to Micron ratio)。

### 4.5 互動邏輯細節

*   **REQ-GUI-040: 旋鈕靈敏度**
    *   當滑鼠游標懸停在虛擬旋鈕上時，滾輪滾動一格對應 SCSI 數值的變化量應可設定 (Coarse/Fine/Super Fine)。
*   **REQ-GUI-041: 快捷鍵 (Hotkeys)**
    *   支援鍵盤操作常用功能，例如：
        *   `Space`: Freeze/Unfreeze
        *   `F2`: Save Image
        *   `F5`: Auto Focus
        *   `+ / -`: Mag Up / Mag Down

---

## 5. 實作優先級建議 (Implementation Roadmap)

1.  **P0 (核心):** 建立 SCSI 通訊，實現真空讀取、HT 開關、影像即時顯示 (TV Mode)。
2.  **P1 (基本操作):** Mag 調整、Focus/Stig 虛擬旋鈕控制、Photo 模式擷取。
3.  **P2 (自動化):** ACB、Auto Focus、Auto Saturation。
4.  **P3 (優化):** Recipe 系統、測量工具、OSD 燒錄。