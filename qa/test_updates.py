import hashlib
from pathlib import Path
from threading import Event
from unittest.mock import patch

import httpx2
import pytest

from app_version import UPDATE_REPOSITORY
from update_service import Release, ReleaseAsset, UpdateError, check_release, download_release, version_tuple
from update_install import install_and_restart


def release(data=b'fixture', digest=None, url=None):
    name='SMO-Setup-9.0.0.exe'
    return Release(tag_name='v9.0.0', assets=[ReleaseAsset(name=name,size=len(data),digest=digest or 'sha256:'+hashlib.sha256(data).hexdigest(),browser_download_url=url or f'https://github.com/{UPDATE_REPOSITORY}/releases/download/v9.0.0/{name}')])


def test_versions_are_numeric():
    assert version_tuple('v1.10.0') > version_tuple('1.9.0')
    with pytest.raises(UpdateError): version_tuple('1.2.3/evil')


def test_foreign_download_rejected():
    with pytest.raises(UpdateError): release(url='https://example.com/file.exe').installer()


def test_missing_integrity_rejected():
    item=release().model_copy(update={'assets':[release().assets[0].model_copy(update={'digest':None})]})
    with pytest.raises(UpdateError): item.installer()


def client(data):
    return httpx2.Client(transport=httpx2.MockTransport(lambda req:httpx2.Response(200,content=data)))


def test_verified_download_and_real_progress(tmp_path):
    progress=[]
    with patch('update_service.httpx2.Client',return_value=client(b'fixture')):
        file=download_release(release(),tmp_path,progress.append,Event())
    assert file.read_bytes()==b'fixture'
    assert progress==[99,100]
    assert not list(tmp_path.glob('*.part'))


def test_hash_failure_never_completes(tmp_path):
    progress=[]
    with patch('update_service.httpx2.Client',return_value=client(b'changed')):
        with pytest.raises(UpdateError): download_release(release(),tmp_path,progress.append,Event())
    assert 100 not in progress
    assert not list(tmp_path.iterdir())


def test_cancel_removes_partial_file(tmp_path):
    cancel=Event(); cancel.set()
    with patch('update_service.httpx2.Client',return_value=client(b'fixture')):
        with pytest.raises(UpdateError): download_release(release(),tmp_path,lambda n:None,cancel)
    assert not list(tmp_path.iterdir())


def test_no_release_is_not_latest_claim():
    transport=httpx2.MockTransport(lambda req:httpx2.Response(404))
    with patch('update_service.httpx2.Client',return_value=httpx2.Client(transport=transport)):
        assert check_release() is None


def test_development_cannot_install():
    with pytest.raises(UpdateError): install_and_restart(Path('fixture.exe'))


def test_directory_failure_has_user_message(tmp_path):
    with patch.object(Path,'mkdir',side_effect=PermissionError('fixture')):
        with pytest.raises(UpdateError): download_release(release(),tmp_path,lambda n:None,Event())


def test_cleanup_failure_has_user_message(tmp_path):
    with patch('update_service.httpx2.Client',return_value=client(b'fixture')):
        with patch.object(Path,'unlink',side_effect=PermissionError('fixture')):
            with pytest.raises(UpdateError): download_release(release(),tmp_path,lambda n:None,Event())


def test_windows_helper_executes_command_in_hidden_process():
    import subprocess
    with patch('update_install.sys.frozen',True,create=True), patch('update_install.subprocess.Popen') as launch:
        install_and_restart(Path('fixture.exe'))
    flags=launch.call_args.kwargs['creationflags']
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command','exit 13'],
                          creationflags=flags,capture_output=True,timeout=15)
    assert result.returncode==13, 'Hidden helper exited without executing its command'
