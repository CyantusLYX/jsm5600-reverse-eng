# JEOL 5600 控制軟體需求規格書 (使用者操作視角)

**專案名稱:** J5600-Linux-ModernUI
**文件版本:** 1.0 (User Ops)
**目標用戶:** 電子顯微鏡操作員、研究人員、實驗室管理員
**核心理念:** 直覺、防呆、將複雜的物理操作簡化為圖形互動。

---

## 3. 使用者互動流程與邏輯 (User Interaction Logic)

此章節描述使用者在操作 SEM 時的標準工作流，以及軟體應有的反應。

### 3.1 啟動與真空管理 (Startup & Vacuum)

*   **USR-001: 系統狀態概覽**
    *   **需求:** 使用者開啟軟體後，應能立即由「儀表板」得知當前機器狀態。
    *   **顯示內容:**
        *   真空狀態：大氣 (Air) / 抽氣中 (Pumping) / 就緒 (Ready)。
        *   真空規讀數：以圖像化 (綠色/紅色燈號) 或模擬指針顯示。
*   **USR-002: 抽真空 (Evacuation)**
    *   **操作:** 使用者點擊 `EVAC` 按鈕。
    *   **軟體反應:**
        1.  鎖定 `VENT` 按鈕，防止誤觸。
        2.  顯示 "Pumping..." 動畫或進度條。
        3.  當 SCSI 回傳真空度達標後，狀態轉為綠色 "READY"，並解鎖 `HT` (高壓) 控制區。
*   **USR-003: 洩壓與換樣 (Venting)**
    *   **操作:** 使用者點擊 `VENT` 按鈕。
    *   **軟體反應:**
        1.  (若 HT 開啟中) 自動執行 HT OFF 序列，關閉高壓。
        2.  (若燈絲熱) 自動關閉燈絲電流。
        3.  發送洩壓指令，狀態轉為 "Venting"。
        4.  當氣壓回到大氣壓，提示使用者「可開啟樣品室」。

### 3.2 電子束生成 (Beam Generation)

*   **USR-010: 加速電壓設定 (kV Selection)**
    *   **操作:** 使用者從下拉選單選擇電壓 (例如 15kV)。
    *   **限制:** 在 HT ON 狀態下，禁止大幅度切換電壓（例如從 5kV 直接跳到 30kV），軟體應強制使用者先 OFF 再切換，或軟體自動執行 Ramp-down/Ramp-up。
*   **USR-011: 開啟高壓 (HT ON)**
    *   **操作:** 點擊 `HT` 開關。
    *   **軟體反應:**
        1.  按鈕變色 (如變紅或黃) 表示高壓啟用。
        2.  自動載入該 kV 對應的 Gun Alignment 與 Bias 記憶值。
        3.  開始顯示即時影像。
*   **USR-012: 燈絲飽和 (Saturation)**
    *   **痛點:** 舊機器需手動旋轉旋鈕尋找飽和點。
    *   **新操作:** 使用者只需點擊 `Auto Saturate` 按鈕。
    *   **軟體反應:** 軟體自動接管燈絲電流，繪製發射電流曲線，找到最佳工作點後鎖定，並通知使用者 "Beam Ready"。

### 3.3 影像導航與調整 (Navigation & Tuning)

*   **USR-020: 放大倍率控制 (Magnification)**
    *   **操作:**
        *   方式 A: 滾動滑鼠滾輪 (粗調)。
        *   方式 B: 點擊預設倍率按鈕 (例如 x500, x1000, x5000)。
    *   **軟體反應:**
        1.  影像視野 (FOV) 改變。
        2.  **關鍵:** 畫面上的「標尺 (Micron Bar)」必須即時更新長度與數值，確保測量正確。
*   **USR-021: 對焦 (Focus)**
    *   **操作:**
        *   **虛擬旋鈕:** 滑鼠游標懸停在 Focus 旋鈕圖示上，滾動滾輪進行微調 (Fine Focus)，按住左鍵拖曳進行粗調 (Coarse Focus)。
        *   **Wobbler 輔助:** 使用者點擊 `Wobbler` 按鈕，影像開始左右晃動。使用者調整光欄直到影像重合，再次點擊取消 Wobbler。
*   **USR-022: 消像散 (Stigmator)**
    *   **痛點:** 初學者很難理解像散。
    *   **操作:** 提供一個二維座標板 (XY Pad)，使用者可以拖曳其中的「點」來同時調整 Stig X 與 Stig Y，直觀地觀察影像銳利度變化。

### 3.4 影像優化 (Optimization)

*   **USR-030: 自動畫質調整 (ACB)**
    *   **操作:** 當影像太暗或過曝時，點擊 `ACB` (Auto Contrast/Brightness)。
    *   **軟體反應:** 系統自動分析影像直方圖，調整 PMT 參數，使影像灰階分佈均勻。
*   **USR-031: 掃描速度切換 (Scan Speed)**
    *   **操作:**
        *   `Fast/TV`: 用於尋找視野、移動樣品台時（流暢但有雜訊）。
        *   `Slow`: 用於觀察細節（低雜訊但更新慢）。
        *   `Freeze`: 凍結當前畫面，用於詳細檢視或暫存。

### 3.5 影像擷取與存檔 (Capture & Documentation)

*   **USR-040: 拍照 (Photo)**
    *   **操作:** 點擊 `Photo` 按鈕。
    *   **軟體反應:**
        1.  自動切換至極慢速掃描 (高信噪比)。
        2.  掃描完成後，彈出預覽視窗。
        3.  將所有參數 (kV, Mag, Date, WD) 燒錄在圖片下方的資訊列 (Data Strip)。
*   **USR-041: 快速測量 (Measurement)**
    *   **操作:** 在凍結或即時影像上，按住右鍵拖曳畫出一條線。
    *   **軟體反應:** 即時顯示該線段的長度 (例如 `25.4 μm`)，基於當前放大倍率自動換算。

---

## 4. 使用者介面設計規範 (GUI Specification)

目標是建立一個類似現代醫療儀器或高階相機的介面，而非傳統 Windows 視窗控制項的堆疊。

### 4.1 視覺風格 (Visual Style)
*   **配色:** 深灰色背景 (#2D2D2D)，文字為淺灰色 (#E0E0E0)。強調色使用 JEOL 傳統藍色或高對比的琥珀色/青色。
*   **低光環境優化:** 實驗室通常關燈操作，介面不得有大面積的刺眼白色背景。

### 4.2 視窗佈局 (Layout Definition)

介面分為三個主要區域：

#### A. 中央影像區 (The Stage) - 佔據 75% 面積
这是使用者 90% 時間注視的地方。
*   **Live Viewport:** 顯示來自 ADC 的影像串流。
*   **Overlay (OSD):** 浮動顯示在影像角落的參數（半透明背景）。
    *   左上：探測器類型 (SEI/BEI)、掃描速度 (Slow/TV)。
    *   右下：標尺 (Scale Bar)、放大倍率、電壓。
*   **互動層:** 支援滑鼠操作（雙擊置中、滾輪縮放、右鍵畫線測量）。

#### B. 右側控制台 (The Console) - 佔據 25% 面積
模仿實體控制面板的邏輯，由上而下排列：

1.  **Beam Control (電子束):**
    *   [HT ON/OFF] (大型帶燈開關)
    *   [kV] (下拉選單)
    *   [Filament] (飽和度條 + Auto 按鈕)
2.  **Optics (光學):**
    *   [Focus] (大型虛擬旋鈕，需有數字顯示目前的 DAC 值或 WD)
    *   [Stigmator X/Y] (小型雙旋鈕或 XY Pad)
    *   [Wobbler] (Toggle 按鈕)
3.  **Detector (檢測器):**
    *   [Contrast] / [Brightness] (滑桿)
    *   [ACB] (自動調整按鈕)
    *   [Signal Select] (SEI / AUX)
4.  **Stage (樣品台):**
    *   方向鍵盤 (上/下/左/右)
    *   [Stop] (緊急停止馬達)

#### C. 底部狀態列 (Status Bar)
顯示系統的「生命徵象」：
*   **最左側:** 真空狀態圖示 (如：渦輪扇葉旋轉動畫)。文字顯示 "High Vacuum < 10^-4 Pa"。
*   **中間:** 系統訊息 (如："Ready", "Communicating...", "Error: Filament Open")。
*   **最右側:** 連線狀態 (SCSI Link)、FPS 數值。

### 4.3 操作回饋設計 (Feedback Design)

*   **延遲處理:** 由於 SCSI 通訊有物理延遲，當使用者旋轉虛擬 Focus 旋鈕時：
    1.  UI 旋鈕應立即轉動（無延遲感）。
    2.  後端將指令放入 Queue 發送。
    3.  若 SCSI 繁忙，游標旁顯示微小的「沙漏」或「傳輸中」圖示，但不應卡死介面。
*   **安全警示:**
    *   當真空未達標時，HT 按鈕應呈現「灰色禁用 (Disabled)」狀態，並有 Tooltip 提示 "Waiting for Vacuum"。
    *   若發生錯誤（如斷線），應彈出醒目的紅色 Toast 訊息，而非傳統的 MessageBox（避免中斷操作）。

### 4.4 快捷鍵定義 (Hotkeys)

為了讓熟練的操作員能盲操作：
*   `NumPad + / -`: 放大 / 縮小
*   `Arrow Keys`: 移動樣品台 (Stage Shift)
*   `Ctrl + Scroll`: 粗調 Focus
*   `Shift + Scroll`: 微調 Focus
*   `F12`: 立即拍照 (Snap)
*   `Space`: 凍結/解凍影像

---

## 5. 軟體架構對應 (User -> Software Mapping)

| 使用者動作 | UI 層反應 | 邏輯層 (Business Logic) 處理 | 硬體層 (SCSI/Driver) 動作 |
| :--- | :--- | :--- | :--- |
| **點擊 "HT ON"** | 按鈕閃爍黃燈 (暖機中) | 檢查 Vacuum=Ready? <br> 檢查 Filament=OK? <br> 啟動 HT 序列 | 發送 `CMD_HT_ON` <br> 發送 `CMD_FILAMENT_RAMP` |
| **滾動 Focus 滾輪** | 旋鈕動畫轉動 <br> 數值更新 | 計算新的 Focus DAC 值 <br> 限制在 0-65535 範圍 | 發送 `CMD_SET_LENS_OL` (含數值) |
| **點擊 "ACB"** | 顯示 "Auto Adjusting..." | 截取當前 Frame <br> 計算 Histogram <br> 計算最佳 Gain/Offset | 發送 `CMD_SET_PMT_GAIN` <br> 發送 `CMD_SET_PMT_OFFSET` |
| **點擊 "Photo"** | 畫面凍結 <br> 顯示進度條 | 切換 ADC 取樣率 (Oversampling) <br> 等待 SCSI 掃描觸發 | 監聽 V-Sync 同步信號 <br> 啟動高解析度採集 |