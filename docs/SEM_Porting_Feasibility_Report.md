# JEOL SEM 控制軟體 (5610E Ver 5.26) 移植 Linux 與現代硬體可行性研究報告

## 1. 專案背景與目標
本專案旨在研究將 2000 年代初期開發的 JEOL JSM-5610E 系列掃描式電子顯微鏡（SEM）控制軟體從 Windows XP/Legacy 環境移植到現代 Linux 系統，並適配套現代硬體運作。

---

## 2. 目前研究進度與已解決問題

### 2.1 軟體包提取 (已解決)
*   **格式鑑定**：確認原始軟體包採用 **InstallShield 3.0** 封裝（特徵碼 `13 5D 65 8C`）。
*   **工具鏈建立**：成功部署 `idecomp.py` 腳本，完整解開了 `sem.z`, `lib.z`, `system.z` 中的隱藏檔案。
*   **核心組件定位**：
    *   **核心抽象層**：`SEM32.DLL` (具備 640+ 導出函數，控制 SEM 核心邏輯)。
    *   **影像驅動層**：`fp3d32.dll` / `fpv32.dll` (操作 FlashPoint 擷取卡)。
    *   **前端 UI**：`Jsm5000.exe` (控制面板主體)。

### 2.2 通訊機制逆向 (已解決)
*   **通訊協定**：經過反編譯 `SEM32.DLL` 調用鏈，確認該軟體並非操作標準 RS-232/485 串口，而是透過 **SCSI (ASPI)** 介面通訊。
*   **設備識別**：軟體會搜尋 SCSI 匯流排上 Vendor ID 為 **`JEOL`** 的設備。
*   **指令封裝**：控制指令（如加速電壓、倍率）被封裝在非標準的 SCSI CDB (Command Descriptor Block) 中，例如 `0xDC` (發送指令) 和 `0xC1` (接收數據)。

### 2.3 影像擷取硬體分析 (已解決)
*   **硬體規格**：確認擷取卡為 **Integral Technologies FlashPoint 3D** (PCI 介面)。
*   **架構**：採用 **Tseng Labs ET6100** 控制記憶體，**Philips SAA7110A** 進行類比影像（S-Video）數位化。

---

## 3. 面臨的問題與挑戰 (未有現成解決方案)

| 領域 | 挑戰描述 | 風險等級 |
| :--- | :--- | :--- |
| **實體介面** | 現代主板缺乏 **32-bit PCI** 插槽（用於擷取卡）與 **Legacy SCSI** 介面。 | 高 |
| **驅動相容性** | 原始 `.sys` 驅動為 32 位元，無法在 64 位元 Linux 或現代 Windows 運行。 | 高 |
| **影像品質** | 原始方案受限於 NTSC/PAL 類比規格（約 480 條掃描線），無法發揮 SEM 潛力。 | 中 |
| **封閉協定** | SCSI 指令中的 Vendor Specific Data 部分仍需逐一逆向對應功能。 | 中 |

---

## 4. 可行性設計思路

### 思路 A：半虛擬化混合方案 (Hybrid Model)
*   **架構**：`Wine` + `Shim DLL` (墊片 DLL)。
*   **做法**：
    *   在 Linux 下使用 Wine 執行 `Jsm5000.exe`。
    *   編寫自定義的 `SEM32.DLL` 與 `fp3d32.dll`。
    *   **控制部**：將調用轉化為 Linux 原生 `sg3_utils` 指令，傳送到 PCIe-to-SCSI 轉接卡。
    *   **影像部**：將調用轉化為 V4L2 指令，從現代 USB 影像擷取卡讀取 S-Video 訊號。
*   **優點**：可保留原始軟體介面，開發成本中等。

### 思路 B：全原生 Linux 重寫 (Native Model)
*   **架構**：Python/C++ + `OpenCV` + `libsgutils`。
*   **做法**：
    *   完全棄用原始 EXE，根據反編譯出的指令集重寫控制程式。
    *   直接在 Linux 下發送 SCSI 報文。
*   **優點**：效能最佳，方便整合現代影像算法（如 AI 降噪、自動拼接）。

### 思路 C：硬體數位化現代化 (Hardware Expansion)
*   **架構**：`FPGA/DAQ` + `Linux Driver`。
*   **做法**：
    *   徹底棄用 S-Video 擷取，直接從 SEM 電路引出 **類比 Video 訊號** 與 **掃描同步訊號**。
    *   使用現代高速 ADC (20Msps+) 進行採樣。
*   **優點**：可獲得遠超原始軟體的高解析度純淨影像 (2K~4K)。

---

## 5. 下一步建言
1.  **指令表完善**：繼續靜態分析 `SEM32.DLL`，建立完整的 `功能 <-> SCSI Hex` 對照手冊。
2.  **硬體採購評估**：尋找 PCIe 介面的 SCSI 轉接卡以及現代 S-Video 轉 USB 模組。
3.  **通訊測試**：嘗試在 Linux 下使用 `sg_raw` 發送簡易清單指令（如 `CheckDev`）確認 SEM 硬體反應。

---
報告人：Antigravity (Advanced Agentic Coding Team)
日期：2026-01-26
