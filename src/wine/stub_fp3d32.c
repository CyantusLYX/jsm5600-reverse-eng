/* Generated Stub FP3D32.DLL */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>

#define FB_SIZE (640 * 480 * 4)
static BYTE* g_FakeFramebuffer = NULL;

BOOL WINAPI DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpvReserved) {
    if (fdwReason == DLL_PROCESS_ATTACH) {
        g_FakeFramebuffer = (BYTE*)calloc(1, FB_SIZE);
        fprintf(stderr, "[StubFP3D] DLL Loaded. Fake FB at %p\n", g_FakeFramebuffer);
    } else if (fdwReason == DLL_PROCESS_DETACH) {
        if (g_FakeFramebuffer) free(g_FakeFramebuffer);
    }
    return TRUE;
}

__declspec(dllexport) long __stdcall FPV_AutoWindow(void) {
    return 1;
}

__declspec(dllexport) long __stdcall FPV_AutoWindowInfo(long a0) {
    return 1;
}

__declspec(dllexport) long __stdcall FPV_CheckSwitch(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_Cleanup(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_ClearIRQ(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_ClosePrivateProfileString(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_ConvertPixel(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_ConvertRgbToYuv(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_ConvertYuvToRgb(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_CopyVGARect(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_DumpViperRegs(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_EnableIRQ(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_EnableVideoMask(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_FileResInfo(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_GetCaptureBufferOffset(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_GetFieldType(long a0) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_GetFrameBufferPointer(void) {
    return (long)g_FakeFramebuffer;
}

__declspec(dllexport) long __stdcall FPV_GetI2CReg(long a0) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_GetIMAReg(long a0) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_GetIRQNumber(long a0) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_GetKeyMode(long a0) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_GetKeyValue(long a0) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_GetLibBuild(long a0) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_GetLiveStatus(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_GetMiscParm(long a0) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_GetMiscReg(long a0) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_GetOverlayRect(long a0) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_GetPrivateProfileString(long a0) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_GetSerialReg(long a0) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_GetSTVideoAdjustments(long a0) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_GetVersionInfo(long a0) {
    return 1;
}

__declspec(dllexport) long __stdcall FPV_GetVGAMode(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_GetVideoAdjustments(long a0) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_GetVideoRect(long a0) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_GetVideoSource(long a0) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_GetVideoStandard(long a0) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_GetVideoType(long a0) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_GetViperReg(long a0) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_GetXDelay(long a0) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_GetYDelay(long a0) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_Init(long a0) {
    return 1;
}

__declspec(dllexport) long __stdcall FPV_IsOverlayEnabled(void) {
    return 1;
}

__declspec(dllexport) long __stdcall FPV_LoadConfig(long a0) {
    return 1;
}

__declspec(dllexport) long __stdcall FPV_LoadFile(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_Locate(void) {
    return 1;
}

__declspec(dllexport) long __stdcall FPV_MaskDraw(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_OpenPrivateProfileString(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_OverlayEnable(long a0) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_PackYuv(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_ReadOverlayMemory(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_ReadSerialBytes(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_ReadVideoByte(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_ReadVideoMemory(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_SaveConfig(long a0) {
    return 1;
}

__declspec(dllexport) long __stdcall FPV_SaveConfigToEEPROM(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_SaveFile(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_ScreenToDIB(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_SendViperFS(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_SetAcqRect(long a0, long a1) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_SetColorSpace(long a0) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_SetI2CReg(long a0, long a1) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_SetIMAReg(long a0, long a1) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_SetInputOffset(long a0, long a1) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_SetInputWindow(long a0, long a1, long a2, long a3) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_SetIrisLevel(long a0, long a1) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_SetKeyMode(long a0, long a1) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_SetKeyValue(long a0, long a1) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_SetMaskDelay(long a0, long a1) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_SetMiscParm(long a0, long a1) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_SetMiscReg(long a0, long a1) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_SetPalette(long a0, long a1) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_SetRS170LUT(long a0, long a1) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_SetSerialReg(long a0, long a1) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_SetupSerial(long a0, long a1) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_SetVGAMode(long a0) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_SetVGAPixel(long a0, long a1) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_SetVGARect(long a0, long a1) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_SetVideoAdjustments(long a0) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_SetVideoConfig(long a0, long a1) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_SetVideoMask(long a0, long a1) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_SetVideoWindow(long a0, long a1, long a2, long a3) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_SetVidFreq(long a0, long a1) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_SetViperReg(long a0, long a1) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_SetW32ReadSeg(long a0, long a1) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_SetXYDelay(long a0, long a1) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_UnpackYuv(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_VGARectToMask(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_VideoGrab(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_VideoLive(long a0) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_VideoOffscreen(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_VideoOutput(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_WaitFieldType(long a0) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_WaitHSync(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_WaitMS(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_WaitVSync(void) {
    Sleep(16); return 0;
}

__declspec(dllexport) long __stdcall FPV_WritePrivateProfileString(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_WriteSerialBytes(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_WriteVideoByte(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_WriteVideoMemory(void) {
    return 0;
}

