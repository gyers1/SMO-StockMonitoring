import ctypes
from ctypes import wintypes

user32 = ctypes.WinDLL('user32', use_last_error=True)
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]


def find_window(pid: int, title: str) -> int | None:
    found: list[int] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(handle: int, unused: int) -> bool:
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(handle, ctypes.byref(owner))
        if owner.value == pid:
            text = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(handle, text, 512)
            if text.value == title:
                found.append(handle)
                return False
        return True
    user32.EnumWindows(callback_type(visit), 0)
    return found[0] if found else None


def installed_window(executable: str) -> tuple[int, int] | None:
    from pathlib import Path
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    matches: list[tuple[int,int]] = []
    callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    def visit(handle: int, unused: int) -> bool:
        title=ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(handle,title,512)
        if title.value != 'SMO · Stock Monitor':
            return True
        pid=wintypes.DWORD()
        user32.GetWindowThreadProcessId(handle,ctypes.byref(pid))
        process=kernel.OpenProcess(0x1000,False,pid.value)
        if process:
            try:
                buffer=ctypes.create_unicode_buffer(32768)
                length=wintypes.DWORD(len(buffer))
                if kernel.QueryFullProcessImageNameW(process,0,buffer,ctypes.byref(length)) and Path(buffer.value)==Path(executable):
                    matches.append((pid.value,handle))
                    return False
            finally:
                kernel.CloseHandle(process)
        return True
    user32.EnumWindows(callback_type(visit),0)
    return matches[0] if matches else None
