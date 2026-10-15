from __future__ import annotations

import base64
import binascii
import ctypes
import json
import os
import tempfile
from ctypes import wintypes
from dataclasses import dataclass, field
from pathlib import Path


from app_paths import DATA_DIR


class SettingsError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class BrokerCredentials:
    provider: str
    key: str = field(repr=False)
    secret: str = field(repr=False)


class _Blob(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]


def _crypt(value: bytes, *, decrypt: bool = False) -> bytes:
    if os.name != 'nt':
        raise SettingsError('API 키 보관은 Windows에서만 지원합니다.')
    source_buffer = ctypes.create_string_buffer(value)
    source = _Blob(len(value), ctypes.cast(source_buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = _Blob()
    crypt32 = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    operation = crypt32.CryptUnprotectData if decrypt else crypt32.CryptProtectData
    operation.argtypes = [ctypes.POINTER(_Blob), ctypes.c_void_p, ctypes.c_void_p,
                          ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_Blob)]
    operation.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    if not operation(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise SettingsError('현재 Windows 계정에서 API 키를 암호화하거나 읽을 수 없습니다.')
    try:
        return ctypes.string_at(output.data, output.size)
    finally:
        kernel32.LocalFree(output.data)


class BrokerSettings:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DATA_DIR / 'broker_credentials.json'

    def load(self) -> BrokerCredentials | None:
        try:
            raw = json.loads(self.path.read_text(encoding='utf-8'))
            provider = raw['provider']
            if provider not in ('toss', 'kiwoom', 'mirae', 'kis'):
                raise SettingsError('저장된 증권사 설정 형식을 확인해 주세요.')
            payload = json.loads(_crypt(base64.b64decode(raw['encrypted'], validate=True), decrypt=True))
            if payload['provider'] != provider:
                raise SettingsError('저장된 증권사 정보가 변경되었습니다. 다시 입력해 주세요.')
            key, secret = payload['key'], payload['secret']
            if not isinstance(key, str) or not isinstance(secret, str) or not key or not secret:
                raise SettingsError('저장된 API 키 형식을 확인해 주세요.')
            return BrokerCredentials(provider, key, secret)
        except FileNotFoundError:
            return None
        except (OSError, ValueError, KeyError, TypeError, binascii.Error):
            raise SettingsError('API 키 설정을 읽을 수 없습니다. 다시 입력해 주세요.') from None

    def save(self, credentials: BrokerCredentials) -> None:
        if credentials.provider not in ('toss', 'kiwoom', 'mirae', 'kis') or not credentials.key or not credentials.secret:
            raise SettingsError('증권사와 API 키 두 항목을 입력해 주세요.')
        plaintext = json.dumps({'provider': credentials.provider, 'key': credentials.key, 'secret': credentials.secret}).encode('utf-8')
        encrypted = base64.b64encode(_crypt(plaintext)).decode('ascii')
        temporary: Path | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.path.parent, delete=False) as handle:
                temporary = Path(handle.name)
                json.dump({'provider': credentials.provider, 'encrypted': encrypted}, handle)
            os.replace(temporary, self.path)
        except OSError:
            raise SettingsError('API 키를 저장하지 못했습니다. 폴더 권한을 확인해 주세요.') from None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def clear(self) -> None:
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            raise SettingsError('API 키를 삭제하지 못했습니다. 폴더 권한을 확인해 주세요.') from None
