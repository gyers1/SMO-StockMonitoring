# SMO — Stock Monitor

작고 조용한 Windows 주식 현황판입니다. 원형 아이콘에서 한 줄 시세를 펼치고, 관심종목을 그룹별로 관리합니다.

## 소스코드로 실행하기

Windows 10 2004 이상 / Windows 11 **x64**에서 사용합니다. 검증한 환경은 Python **3.14**입니다. macOS·Linux는 지원하지 않습니다.

Git과 Python이 설치되어 있다면 PowerShell에서:

```powershell
git clone https://github.com/gyers1/SMO-StockMonitoring.git
cd SMO-StockMonitoring
python -m pip install uv
python -m uv venv --python 3.14 .venv
python -m uv pip sync --python .venv\Scripts\python.exe requirements-lock.txt
.\.venv\Scripts\python.exe SMO.py
```

uv가 필요한 Python 3.14와 고정 버전 의존성을 준비합니다. 설치 과정에는 인터넷 연결이 필요합니다. 기존 Python이 3.14가 아니어도 uv로 별도 환경을 만들 수 있습니다.

이미 `uv` 명령을 사용할 수 있다면 클론한 폴더의 `run-dev.bat`를 실행해도 됩니다. 이후에는 `.venv\Scripts\pythonw.exe SMO.py`로 콘솔 없이 실행할 수 있습니다. 같은 사용자 데이터로 실행 중인 SMO가 있다면 먼저 종료하세요.

Git을 사용하지 않으면 저장소의 **Code → Download ZIP**으로 받아 압축을 푼 뒤, 해당 폴더에서 위 명령 중 `python -m pip install uv`부터 진행하세요.

## 처음 사용하기

1. 첫 실행의 안내에서 아이콘 클릭·마우스 올리기 등 표시된 동작을 직접 해봅니다.
2. 조작 안내가 끝나면 증권사 설정에서 **본인의** API 키를 입력하고 저장합니다. 연결 테스트에 성공해야 저장됩니다.
3. 돋보기에서 회사명을 검색하고 추천 종목을 눌러 관심그룹에 추가합니다.
4. 원에 마우스를 올리면 잠깐 펼쳐지고, 밖으로 옮기면 접힙니다. 클릭하면 한 줄 시세가 고정됩니다. 접기 버튼으로 고정을 해제합니다.
5. 별은 관심종목 보기입니다. 펼친 페이지 밖을 클릭하면 원으로 접힙니다.

자세한 설명: [사용방법.md](사용방법.md).

토스·키움·한국투자증권 연결 코드가 포함되어 있습니다. 미래에셋 연결은 준비 중입니다. 시세 이용 범위와 지연 여부는 증권사 API 권한에 따릅니다. API 연결 없이 임의 가격을 표시하지 않습니다.

## 업데이트

소스 실행판은 앱의 설치파일 업데이트 대신, 앱을 종료한 뒤 다음과 같이 갱신합니다.

```powershell
git pull --ff-only
python -m uv pip sync --python .venv\Scripts\python.exe requirements-lock.txt
.\.venv\Scripts\python.exe SMO.py
```

직접 수정한 코드는 별도 브랜치에 보관하세요. 설치형 사용자는 [Releases](https://github.com/gyers1/SMO-StockMonitoring/releases/latest)에서 설치하거나 앱 설정에서 업데이트할 수 있습니다.

## 개인 데이터

API 키·계좌정보·개인 설정은 저장소에 포함하지 않습니다. 실행 후 관심그룹·위치·캐시·암호화된 API 키는 `%LOCALAPPDATA%\SMO`에 저장됩니다. 설치형과 소스 실행판은 이 데이터를 함께 사용합니다. 키는 Windows 사용자별로 암호화되므로 친구에게 해당 폴더를 복사하지 마세요.

## 개발 및 빌드

- `SMO.py`: 실행 진입점
- `qt_*.py`, `glass_paint.py`: UI
- `broker_*.py`, `quote_service.py`: 증권사 시세 연결
- `stock_catalog.py`, `krx_catalog.py`, `korean_stocks.json`: 종목 검색
- `assets/`: 폰트·국기·라이선스
- `qa/`: 테스트와 네이티브 검증 스크립트

자동 테스트:

```powershell
.\.venv\Scripts\python.exe -m pytest qa/test_broker_quotes.py qa/test_kis.py qa/test_revision.py qa/test_startup.py qa/test_updates.py -q
```

설치파일을 직접 만들려면 uv와 Inno Setup 6을 설치한 뒤 `build.bat`를 실행합니다. Inno Setup 설치 위치가 다르면 build.bat의 ISCC 경로를 조정하세요. `build/`, `dist/`, `release/`, `.venv/`는 생성 산출물이며 저장소에서 제외됩니다. GitHub 자동 배포 워크플로는 이 소스 공유에 포함하지 않습니다.

외부 구성요소 라이선스: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
