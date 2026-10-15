from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from pathlib import Path
from threading import Event
from typing import ClassVar

import httpx2
from pydantic import BaseModel, ConfigDict, ValidationError

from app_version import UPDATE_REPOSITORY, VERSION


class UpdateError(Exception):
    pass


class ReleaseAsset(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    name: str
    size: int
    browser_download_url: str
    digest: str | None = None


class Release(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    tag_name: str
    draft: bool = False
    prerelease: bool = False
    assets: list[ReleaseAsset]

    def installer(self) -> ReleaseAsset:
        version_tuple(self.tag_name)
        name = f'SMO-Setup-{self.tag_name.removeprefix("v")}.exe'
        matches = [asset for asset in self.assets if asset.name == name]
        if len(matches) != 1:
            raise UpdateError('업데이트 설치파일이 아직 준비되지 않았습니다.')
        asset = matches[0]
        expected = f'https://github.com/{UPDATE_REPOSITORY}/releases/download/{self.tag_name}/{name}'
        if asset.browser_download_url != expected or not 0 < asset.size <= 150_000_000:
            raise UpdateError('업데이트 파일 정보를 확인할 수 없습니다.')
        if not asset.digest or not re.fullmatch(r'sha256:[0-9a-f]{64}', asset.digest):
            raise UpdateError('파일 검증 정보가 없어 업데이트를 중단했습니다.')
        return asset


def version_tuple(value: str) -> tuple[int, ...]:
    if not re.fullmatch(r'v?\d+\.\d+\.\d+', value):
        raise UpdateError('업데이트 버전 형식을 확인할 수 없습니다.')
    return tuple(int(part) for part in value.removeprefix('v').split('.'))


def check_release() -> Release | None:
    try:
        with httpx2.Client(http2=True, timeout=10, follow_redirects=False) as client:
            response = client.get(f'https://api.github.com/repos/{UPDATE_REPOSITORY}/releases/latest',
                                  headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'SMO-Update'})
        if response.status_code == 404:
            return None
        response.raise_for_status()
        release = Release.model_validate_json(response.content)
        if release.draft or release.prerelease:
            raise UpdateError('정식 업데이트 정보를 확인할 수 없습니다.')
        version_tuple(release.tag_name)
        return release
    except (httpx2.HTTPError, ValidationError):
        raise UpdateError('업데이트 서버에 연결하지 못했습니다. 잠시 후 다시 확인해 주세요.') from None


def is_newer(release: Release) -> bool:
    return version_tuple(release.tag_name) > version_tuple(VERSION)


def download_release(release: Release, destination: Path, progress: Callable[[int], None], cancel: Event) -> Path:
    asset = release.installer()
    final = destination / asset.name
    partial = final.with_suffix('.part')
    digest = hashlib.sha256()
    received = 0
    try:
        destination.mkdir(parents=True, exist_ok=True)
        with httpx2.Client(http2=True, timeout=httpx2.Timeout(20, connect=5), follow_redirects=True) as client:
            with client.stream('GET', asset.browser_download_url) as response:
                response.raise_for_status()
                with partial.open('wb') as output:
                    for chunk in response.iter_bytes(64 * 1024):
                        if cancel.is_set():
                            raise UpdateError('다운로드를 취소했습니다.')
                        received += len(chunk)
                        if received > asset.size:
                            raise UpdateError('업데이트 파일 크기가 일치하지 않습니다.')
                        output.write(chunk)
                        digest.update(chunk)
                        progress(min(99, received * 100 // asset.size))
        if cancel.is_set():
            raise UpdateError('다운로드를 취소했습니다.')
        if received != asset.size or 'sha256:' + digest.hexdigest() != asset.digest:
            raise UpdateError('파일 검증에 실패했습니다. 다시 다운로드해 주세요.')
        partial.replace(final)
        progress(100)
        return final
    except (httpx2.HTTPError, OSError):
        raise UpdateError('업데이트 파일을 받지 못했습니다. 네트워크와 저장 공간을 확인해 주세요.') from None
    finally:
        try:
            partial.unlink(missing_ok=True)
        except OSError:
            raise UpdateError('임시 파일을 정리하지 못했습니다. 저장 폴더 권한을 확인해 주세요.') from None
