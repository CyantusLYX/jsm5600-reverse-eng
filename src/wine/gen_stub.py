functions = [
    "FPV_AutoWindow",
    "FPV_AutoWindowInfo",
    "FPV_CheckSwitch",
    "FPV_Cleanup",
    "FPV_ClearIRQ",
    "FPV_ClosePrivateProfileString",
    "FPV_ConvertPixel",
    "FPV_ConvertRgbToYuv",
    "FPV_ConvertYuvToRgb",
    "FPV_CopyVGARect",
    "FPV_DumpViperRegs",
    "FPV_EnableIRQ",
    "FPV_EnableVideoMask",
    "FPV_FileResInfo",
    "FPV_GetCaptureBufferOffset",
    "FPV_GetFieldType",
    "FPV_GetFrameBufferPointer",
    "FPV_GetI2CReg",
    "FPV_GetIMAReg",
    "FPV_GetIRQNumber",
    "FPV_GetKeyMode",
    "FPV_GetKeyValue",
    "FPV_GetLibBuild",
    "FPV_GetLiveStatus",
    "FPV_GetMiscParm",
    "FPV_GetMiscReg",
    "FPV_GetOverlayRect",
    "FPV_GetPrivateProfileString",
    "FPV_GetSerialReg",
    "FPV_GetSTVideoAdjustments",
    "FPV_GetVersionInfo",
    "FPV_GetVGAMode",
    "FPV_GetVideoAdjustments",
    "FPV_GetVideoRect",
    "FPV_GetVideoSource",
    "FPV_GetVideoStandard",
    "FPV_GetVideoType",
    "FPV_GetViperReg",
    "FPV_GetXDelay",
    "FPV_GetYDelay",
    "FPV_Init",
    "FPV_IsOverlayEnabled",
    "FPV_LoadConfig",
    "FPV_LoadFile",
    "FPV_Locate",
    "FPV_MaskDraw",
    "FPV_OpenPrivateProfileString",
    "FPV_OverlayEnable",
    "FPV_PackYuv",
    "FPV_ReadOverlayMemory",
    "FPV_ReadSerialBytes",
    "FPV_ReadVideoByte",
    "FPV_ReadVideoMemory",
    "FPV_SaveConfig",
    "FPV_SaveConfigToEEPROM",
    "FPV_SaveFile",
    "FPV_ScreenToDIB",
    "FPV_SendViperFS",
    "FPV_SetAcqRect",
    "FPV_SetColorSpace",
    "FPV_SetI2CReg",
    "FPV_SetIMAReg",
    "FPV_SetInputOffset",
    "FPV_SetInputWindow",
    "FPV_SetIrisLevel",
    "FPV_SetKeyMode",
    "FPV_SetKeyValue",
    "FPV_SetMaskDelay",
    "FPV_SetMiscParm",
    "FPV_SetMiscReg",
    "FPV_SetPalette",
    "FPV_SetRS170LUT",
    "FPV_SetSerialReg",
    "FPV_SetupSerial",
    "FPV_SetVGAMode",
    "FPV_SetVGAPixel",
    "FPV_SetVGARect",
    "FPV_SetVideoAdjustments",
    "FPV_SetVideoConfig",
    "FPV_SetVideoMask",
    "FPV_SetVideoWindow",
    "FPV_SetVidFreq",
    "FPV_SetViperReg",
    "FPV_SetW32ReadSeg",
    "FPV_SetXYDelay",
    "FPV_UnpackYuv",
    "FPV_VGARectToMask",
    "FPV_VideoGrab",
    "FPV_VideoLive",
    "FPV_VideoOffscreen",
    "FPV_VideoOutput",
    "FPV_WaitFieldType",
    "FPV_WaitHSync",
    "FPV_WaitMS",
    "FPV_WaitVSync",
    "FPV_WritePrivateProfileString",
    "FPV_WriteSerialBytes",
    "FPV_WriteVideoByte",
    "FPV_WriteVideoMemory",
]

# Manual overrides for signatures I implemented or strongly suspect
# Format: "Name": (arg_count, return_val_code)
# return_val_code: 0=return 0, 1=return 1, 2=return buffer, 3=sleep
sigs = {
    "FPV_Locate": (0, 1),
    "FPV_Init": (1, 1),  # mode
    "FPV_Cleanup": (0, 0),
    "FPV_LoadConfig": (1, 1),  # filename
    "FPV_SaveConfig": (1, 1),  # filename
    "FPV_GetVersionInfo": (1, 1),  # ptr
    "FPV_SetVideoConfig": (2, 0),  # a, b
    "FPV_VideoLive": (1, 0),  # on/off
    "FPV_VideoGrab": (0, 0),
    "FPV_WaitVSync": (0, 3),  # Sleep
    "FPV_WaitHSync": (0, 0),
    "FPV_WaitFieldType": (1, 0),  # field
    "FPV_GetFrameBufferPointer": (0, 2),  # Buffer
    "FPV_GetCaptureBufferOffset": (0, 0),
    "FPV_SetVGAMode": (1, 0),
    "FPV_GetVGAMode": (0, 0),
    "FPV_SetColorSpace": (1, 0),
    "FPV_SetVideoWindow": (4, 0),  # x,y,w,h likely
    "FPV_SetInputWindow": (4, 0),  # x,y,w,h likely
    "FPV_SetVideoAdjustments": (1, 0),  # ptr
    "FPV_GetVideoAdjustments": (1, 0),  # ptr
    "FPV_OverlayEnable": (1, 0),  # bool
    "FPV_IsOverlayEnabled": (0, 1),
    "FPV_GetOverlayRect": (1, 0),  # ptr
    # New guesses
    "FPV_AutoWindow": (0, 1),  # Trigger?
    "FPV_AutoWindowInfo": (1, 1),  # ptr?
    "FPV_CheckSwitch": (0, 0),
    "FPV_ClearIRQ": (0, 0),
    "FPV_GetLiveStatus": (0, 0),
    "FPV_SetXYDelay": (2, 0),
    "FPV_SetInputOffset": (2, 0),
}

print("""/* Generated Stub FP3D32.DLL */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>

#define FB_SIZE (640 * 480 * 4)
static BYTE* g_FakeFramebuffer = NULL;

BOOL WINAPI DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpvReserved) {
    if (fdwReason == DLL_PROCESS_ATTACH) {
        g_FakeFramebuffer = (BYTE*)calloc(1, FB_SIZE);
        fprintf(stderr, "[StubFP3D] DLL Loaded. Fake FB at %p\\n", g_FakeFramebuffer);
    } else if (fdwReason == DLL_PROCESS_DETACH) {
        if (g_FakeFramebuffer) free(g_FakeFramebuffer);
    }
    return TRUE;
}
""")

def_lines = ["LIBRARY fp3d32.dll", "EXPORTS"]

for func in functions:
    def_lines.append(f"    {func}")

    if func in sigs:
        argc, ret_type = sigs[func]
    else:
        # Default: 0 args, return 0. Safest for "Get" but dangerous for "Set".
        # If function name contains "Set", assume 2 args?
        if "Set" in func:
            argc, ret_type = 2, 0
        elif "Get" in func:
            argc, ret_type = 1, 0
        else:
            argc, ret_type = 0, 0

    args_str = ", ".join([f"long a{i}" for i in range(argc)])
    if argc == 0:
        args_str = "void"

    ret_type_c = "long"
    body = ""
    if ret_type == 3:  # Sleep
        body = "Sleep(16); return 0;"
    elif ret_type == 2:  # Buffer
        body = "return (long)g_FakeFramebuffer;"
    elif ret_type == 1:  # Return 1
        body = "return 1;"
    else:
        body = "return 0;"

    print(f"__declspec(dllexport) {ret_type_c} __stdcall {func}({args_str}) {{")
    # print(f"    fprintf(stderr, \"[Stub] {func}\\n\");")
    print(f"    {body}")
    print("}\n")


with open("src/wine/fp3d32.def", "w") as f:
    f.write("\n".join(def_lines))
