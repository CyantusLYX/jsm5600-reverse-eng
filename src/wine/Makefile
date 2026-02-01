# Makefile for Fake WNASPI32.DLL and Test Harness using MinGW

CC = i686-w64-mingw32-gcc
CFLAGS = -O2 -Wall
LDFLAGS = -lws2_32

all: wnaspi32.dll test_sem.exe

wnaspi32.dll: fake_wnaspi32.c wnaspi32.def
	$(CC) $(CFLAGS) -shared -o $@ fake_wnaspi32.c wnaspi32.def $(LDFLAGS)

test_sem.exe: test_sem.c
	$(CC) $(CFLAGS) -o $@ test_sem.c

clean:
	rm -f wnaspi32.dll test_sem.exe
