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


def exit_from_menu(handle: int) -> None:
    """Activate only the tested process's real Qt context-menu Exit item."""
    import time
    assert handle, 'Missing test window'
    owner = wintypes.DWORD()
    user32.GetWindowThreadProcessId(handle, ctypes.byref(owner))
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow(handle)
    user32.PostMessageW(handle, 0x204, 2, (28 << 16) | 28)
    time.sleep(.4)
    user32.PostMessageW(handle, 0x205, 0, (28 << 16) | 28)
    found = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(candidate, unused):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(candidate, ctypes.byref(pid))
        name = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(candidate, name, 256)
        if pid.value == owner.value and user32.IsWindowVisible(candidate) and 'Popup' in name.value:
            found.append(candidate)
        return True
    user32.EnumWindows(callback_type(visit), 0)
    assert found, 'Native SMO context menu did not open'
    menu = found[0]
    rect = wintypes.RECT()
    user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetClientRect(menu, ctypes.byref(rect))
    position = ((rect.bottom - 14) << 16) | (rect.right // 2)
    user32.PostMessageW(menu, 0x200, 0, position)
    user32.PostMessageW(menu, 0x201, 1, position)
    user32.PostMessageW(menu, 0x202, 0, position)
