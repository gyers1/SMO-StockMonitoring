"""Complete Korean listings from Korea Investment's public exchange masters."""
from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Final
from urllib.request import urlopen
from zipfile import BadZipFile, ZipFile


from app_paths import DATA_DIR

BASE_URL: Final = "https://new.real.download.dws.co.kr/common/master/"
BUNDLE: Final = Path(__file__).with_name("korean_stocks.json")
CACHE: Final = DATA_DIR / "korean_stocks_cache.json"
LOGGER: Final = logging.getLogger(__name__)
KINDS: Final = {"EF": "ETF", "EN": "ETN", "RT": "리츠", "DR": "예탁증서",
               "IF": "인프라펀드", "MF": "펀드", "PF": "펀드", "SW": "신주인수권"}


@dataclass(frozen=True, slots=True)
class Listing:
    code: str
    name: str
    market: str
    kind: str
    cap: int


class CatalogError(ValueError):
    """Invalid exchange master."""


def validate(listings: tuple[Listing, ...]) -> tuple[Listing, ...]:
    codes: set[tuple[str, str]] = set()
    counts = {"KS": 0, "KQ": 0}
    for item in listings:
        if not all(isinstance(value, str) for value in (item.code, item.name, item.market, item.kind)) or not isinstance(item.cap, int):
            raise CatalogError("Invalid listing field types")
        key = (item.market, item.code)
        if (not re.fullmatch(r"[0-9A-Z]{6}", item.code) or not item.name.strip()
                or item.market not in counts or key in codes or item.cap < 0):
            raise CatalogError("Invalid or duplicate listing")
        codes.add(key)
        counts[item.market] += 1
    if counts["KS"] < 800 or counts["KQ"] < 1000:
        raise CatalogError("Incomplete exchange master")
    return listings


def _read(path: Path) -> tuple[Listing, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    listings = tuple(Listing(**row) for row in payload["listings"])
    return validate(listings)


def load_catalog() -> tuple[Listing, ...]:
    """Prefer a valid local refresh; the bundled master works offline."""
    if CACHE.exists():
        try:
            return _read(CACHE)
        except (OSError, ValueError, TypeError, KeyError) as error:
            LOGGER.warning("Ignoring invalid local catalog: %s", error)
    return _read(BUNDLE)


def parse_master(data: bytes, market: str) -> tuple[Listing, ...]:
    """Parse official fixed-width fields after removing newline characters.

    Field layouts: koreainvestment/open-trading-api/stocks_info/
    kis_kospi_code_mst.py and kis_kosdaq_code_mst.py.
    """
    tail_size = {"KS": 227, "KQ": 221}[market]
    result: list[Listing] = []
    for row in data.decode("cp949").splitlines():
        if len(row) <= 21 + tail_size:
            raise CatalogError("Truncated master record")
        code = row[:9].strip()
        # Nine-character non-exchange fund IDs are not stock symbols.
        if len(code) != 6:
            continue
        name = row[21:-tail_size].strip()
        tail = row[-tail_size:]
        cap = int(tail[-15:-6].strip() or "0")
        result.append(Listing(code, name, market, KINDS.get(tail[:2], ""), cap))
    return tuple(result)


def download_catalog() -> tuple[Listing, ...]:
    """Blocking download; must run on a worker, never during autocomplete."""
    listings: list[Listing] = []
    for name, market in (("kospi", "KS"), ("kosdaq", "KQ")):
        filename = f"{name}_code.mst"
        with urlopen(BASE_URL + filename + ".zip", timeout=15) as response:
            archive = response.read()
        with ZipFile(BytesIO(archive)) as zipped:
            listings.extend(parse_master(zipped.read(filename), market))
    return validate(tuple(listings))


def write_catalog(path: Path, listings: tuple[Listing, ...]) -> None:
    """Atomically replace a complete cache, preserving the old file on failure."""
    validate(listings)
    payload = {"source": "Korea Investment & Securities public exchange masters",
               "source_urls": [BASE_URL + name + "_code.mst.zip" for name in ("kospi", "kosdaq")],
               "retrieved_at": datetime.now(timezone.utc).isoformat(),
               "listings": [asdict(item) for item in listings]}
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         suffix=".tmp", delete=False) as output:
            temporary = Path(output.name)
            json.dump(payload, output, ensure_ascii=False, separators=(",", ":"))
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def refresh_catalog() -> tuple[Listing, ...] | None:
    """Refresh daily in the background; any failure retains the last catalog."""
    try:
        if CACHE.exists() and datetime.now().timestamp() - CACHE.stat().st_mtime < 86400:
            try:
                _read(CACHE)
            except (OSError, ValueError, TypeError, KeyError) as error:
                LOGGER.warning("Replacing invalid catalog cache: %s", error)
            else:
                return None
        previous = load_catalog()
        fresh = download_catalog()
        for market in ("KS", "KQ"):
            if sum(item.market == market for item in fresh) < sum(item.market == market for item in previous) * .9:
                raise CatalogError("Unexpectedly incomplete refresh")
        write_catalog(CACHE, fresh)
        return fresh
    except (OSError, ValueError, TypeError, KeyError, BadZipFile) as error:
        LOGGER.warning("Catalog refresh unavailable; retaining local listings: %s", error)
        return None
