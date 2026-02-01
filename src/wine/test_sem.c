/*
 * Test Harness for SEM32.DLL
 * Loads the DLL and calls initialization functions to verify Shim connectivity.
 */

#include <windows.h>
#include <stdio.h>

typedef int (WINAPI *P_sem_InitSystem)(void);
typedef int (WINAPI *P_sem_GetHdwType)(void);
typedef int (WINAPI *P_sem_GetVacuumStatus)(void);

int main() {
    printf("Loading SEM32.DLL...\n");
    HMODULE hSem = LoadLibrary("SEM32.DLL");
    if (!hSem) {
        printf("Failed to load SEM32.DLL. Error: %lu\n", GetLastError());
        return 1;
    }
    printf("SEM32.DLL Loaded.\n");

    P_sem_InitSystem sem_InitSystem = (P_sem_InitSystem)GetProcAddress(hSem, "sem_InitSystem");
    P_sem_GetHdwType sem_GetHdwType = (P_sem_GetHdwType)GetProcAddress(hSem, "sem_GetHdwType");
    P_sem_GetVacuumStatus sem_GetVacuumStatus = (P_sem_GetVacuumStatus)GetProcAddress(hSem, "sem_GetVacuumStatus");

    if (!sem_InitSystem) {
        printf("Failed to find sem_InitSystem\n");
        return 1;
    }

    printf("Calling sem_InitSystem()...\n");
    int res = sem_InitSystem();
    printf("sem_InitSystem returned: %d\n", res);

    if (sem_GetHdwType) {
        int hdw = sem_GetHdwType();
        printf("sem_GetHdwType returned: %d\n", hdw);
    }

    if (sem_GetVacuumStatus) {
        int vac = sem_GetVacuumStatus();
        printf("sem_GetVacuumStatus returned: %d\n", vac);
    }

    // Keep alive for a bit to ensure async threads run
    Sleep(2000);

    return 0;
}
