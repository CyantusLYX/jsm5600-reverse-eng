/*
 * Stub FP3D32.DLL
 * Emulates the FlashPoint 3D Frame Grabber API to satisfy Jsm5000.exe
 */

#include <windows.h>
#include <stdio.h>
#include <stdlib.h>

// --- Global State ---
// We allocate a fake framebuffer so the app doesn't crash if it tries to read/write directly.
// 640x480 resolution * 4 bytes per pixel (RGBA) = 1,228,800 bytes
#define FB_SIZE (640 * 480 * 4)
static BYTE* g_FakeFramebuffer = NULL;

// --- DllMain ---
BOOL WINAPI DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpvReserved) {
    if (fdwReason == DLL_PROCESS_ATTACH) {
        // Allocate zeroed memory for the fake framebuffer
        g_FakeFramebuffer = (BYTE*)calloc(1, FB_SIZE);
        
        // Debug output
        fprintf(stderr, "[StubFP3D] DLL Loaded. Fake FB at %p\n", g_FakeFramebuffer);
    } else if (fdwReason == DLL_PROCESS_DETACH) {
        if (g_FakeFramebuffer) {
            free(g_FakeFramebuffer);
            g_FakeFramebuffer = NULL;
        }
    }
    return TRUE;
}

// --- Exported Functions ---

// 1. Board Detection
__declspec(dllexport) long __stdcall FPV_Locate(void) {
    fprintf(stderr, "[StubFP3D] FPV_Locate called -> Returning 1 (Found)\n");
    return 1; 
}

// 2. Initialization
__declspec(dllexport) long __stdcall FPV_Init(long mode) {
    fprintf(stderr, "[StubFP3D] FPV_Init(mode=%ld) called -> Success (1)\n", mode);
    return 1; // CHANGED from 0 to 1. If 0 is Fail, this might fix initialization.
}

__declspec(dllexport) long __stdcall FPV_Cleanup(void) {
    return 0;
}

// 3. Configuration / Version
__declspec(dllexport) long __stdcall FPV_LoadConfig(char* filename) {
    fprintf(stderr, "[StubFP3D] FPV_LoadConfig(%s)\n", filename ? filename : "NULL");
    return 1; // CHANGED from 0 to 1, to test if VB boolean convention is preferred
}

__declspec(dllexport) long __stdcall FPV_SaveConfig(char* filename) {
    return 1;
}

__declspec(dllexport) long __stdcall FPV_GetVersionInfo(void* ptr) {
    // Populate struct? 
    // Assuming simple return code for now.
    return 1; 
}

// 4. Video Control
__declspec(dllexport) long __stdcall FPV_SetVideoConfig(long a, long b) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_VideoLive(long on) {
    fprintf(stderr, "[StubFP3D] FPV_VideoLive(%ld)\n", on);
    return 0;
}

__declspec(dllexport) long __stdcall FPV_VideoGrab(void) {
    fprintf(stderr, "[StubFP3D] FPV_VideoGrab\n");
    return 0;
}

// 5. Synchronization (CRITICAL)
// If we return immediately, the app will spin 100% CPU.
__declspec(dllexport) long __stdcall FPV_WaitVSync(void) {
    // Sleep ~16ms to simulate 60Hz Vertical Sync
    Sleep(16); 
    return 0;
}

__declspec(dllexport) long __stdcall FPV_WaitHSync(void) {
    return 0;
}

__declspec(dllexport) long __stdcall FPV_WaitFieldType(long field) {
    Sleep(8); // Half frame
    return 0;
}

// 6. Direct Memory Access (CRITICAL)
// The app likely wants a pointer to the VRAM to draw overlays or read pixels.
__declspec(dllexport) void* __stdcall FPV_GetFrameBufferPointer(void) {
    // fprintf(stderr, "[StubFP3D] FPV_GetFrameBufferPointer -> %p\n", g_FakeFramebuffer);
    return g_FakeFramebuffer;
}

__declspec(dllexport) long __stdcall FPV_GetCaptureBufferOffset(void) {
    return 0;
}

// 7. Stubs for other discovered functions to prevent "Entry Point Not Found" errors
// We stub the most likely ones found in strings.

__declspec(dllexport) long __stdcall FPV_SetVGAMode(long mode) { return 0; }
__declspec(dllexport) long __stdcall FPV_GetVGAMode(void) { return 0; }
__declspec(dllexport) long __stdcall FPV_SetColorSpace(long space) { return 0; }
__declspec(dllexport) long __stdcall FPV_SetVideoWindow(long a, long b, long c, long d) { return 0; }
__declspec(dllexport) long __stdcall FPV_SetInputWindow(long a, long b, long c, long d) { return 0; }
__declspec(dllexport) long __stdcall FPV_SetVideoAdjustments(void* ptr) { return 0; }
__declspec(dllexport) long __stdcall FPV_GetVideoAdjustments(void* ptr) { return 0; }
__declspec(dllexport) long __stdcall FPV_OverlayEnable(long enable) { return 0; }
__declspec(dllexport) long __stdcall FPV_IsOverlayEnabled(void) { return 1; }
__declspec(dllexport) long __stdcall FPV_GetOverlayRect(void* ptr) { return 0; }

