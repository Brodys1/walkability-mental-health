"""Download the raw data used in the walkability / mental-health analysis.

The script is intentionally idempotent: existing files are skipped unless
``--force`` is passed.  All downloads are public and do not require an API key.

Usage
-----
    python src/download_data.py
    python src/download_data.py --force
    python src/download_data.py --skip-sld   # keep an existing SLD geodatabase
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------
PLACES_URL = (
    "https://data.cdc.gov/api/views/yjkw-uj5s/rows.csv?accessType=DOWNLOAD"
)
PLACES_PATH = RAW / (
    "PLACES__Census_Tract_Data_(GIS_Friendly_Format),_2025_release_20261010.csv"
)

SLD_URL = "https://edg.epa.gov/EPADataCommons/public/OA/SLD/SmartLocationDatabaseV3.zip"
SLD_DIR = RAW / "SmartLocationDatabaseV3"
SLD_GDB = SLD_DIR / "SmartLocationDatabase.gdb"

# ACS 5-year table-based summary file.  The 2024 5-year release (published
# December 2025) is the most recent release available for this project.
ACS_YEAR = 2024
ACS_BASE = (
    f"https://www2.census.gov/programs-surveys/acs/summary_file/{ACS_YEAR}/"
    "table-based-SF/data/5YRData"
)
ACS_TABLES = {
    "b01003": "Total population",
    "b08301": "Means of transportation to work",
    "b19013": "Median household income",
    "b25003": "Tenure",
    "b25064": "Median gross rent",
    "b25070": "Gross rent as a percentage of household income",
    "b25071": "Median gross rent as a percentage of household income",
}
ACS_DIR = RAW / "acs"

# 2020 census tract <-> 2010 census tract relationship file.  Used to move the
# block-group walkability index from the SLD's 2010/2019 tract boundaries to the
# 2020 tract boundaries used by PLACES and the 2024 ACS release.
CROSSWALK_URL = (
    "https://www2.census.gov/geo/docs/maps-data/data/rel2020/tract/"
    "tab20_tract20_tract10_natl.txt"
)
CROSSWALK_PATH = RAW / "crosswalks" / "tab20_tract20_tract10_natl.txt"


def _session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update(
        {"User-Agent": "walkability-mental-health/1.0 (academic research project)"}
    )
    return session


def download_file(url: str, dest: Path, *, force: bool = False) -> Path:
    """Download ``url`` to ``dest`` with a simple progress indicator."""
    if dest.exists() and dest.stat().st_size > 0 and not force:
        print(f"  skip (exists): {dest.relative_to(ROOT)}")
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    print(f"  downloading {urlparse(url).netloc}{urlparse(url).path}")
    with _session() as session:
        with session.get(url, stream=True, timeout=120) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length") or 0)
            written = 0
            with tmp.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    handle.write(chunk)
                    written += len(chunk)
                    if total:
                        pct = written / total * 100
                        print(
                            f"\r    {written / 1e6:,.1f} / {total / 1e6:,.1f} MB "
                            f"({pct:5.1f}%)",
                            end="",
                            flush=True,
                        )
            if total:
                print()
    tmp.replace(dest)
    print(f"  saved: {dest.relative_to(ROOT)} ({dest.stat().st_size / 1e6:,.1f} MB)")
    return dest


def download_places(force: bool = False) -> None:
    print("CDC PLACES 2025 census-tract release")
    download_file(PLACES_URL, PLACES_PATH, force=force)


def download_sld(force: bool = False, skip: bool = False) -> None:
    print("EPA Smart Location Database v3")
    if SLD_GDB.exists() and not force:
        print(f"  skip (exists): {SLD_GDB.relative_to(ROOT)}")
        return
    if skip:
        print("  --skip-sld set and no geodatabase found; skipping.")
        return

    zip_path = RAW / "SmartLocationDatabaseV3.zip"
    download_file(SLD_URL, zip_path, force=force)
    print(f"  extracting {zip_path.name} -> {SLD_DIR.relative_to(ROOT)}")
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(RAW)
    if not SLD_GDB.exists():
        # The archive layout has changed before; find the .gdb if needed.
        candidates = list(RAW.rglob("SmartLocationDatabase.gdb"))
        if not candidates:
            raise FileNotFoundError(
                "Downloaded SLD archive did not contain SmartLocationDatabase.gdb"
            )
        SLD_DIR.parent.mkdir(parents=True, exist_ok=True)
        if candidates[0] != SLD_GDB:
            candidates[0].rename(SLD_GDB)
    print(f"  ready: {SLD_GDB.relative_to(ROOT)}")


def download_acs(force: bool = False) -> None:
    print(f"ACS {ACS_YEAR} 5-year table-based summary file")
    for table, label in ACS_TABLES.items():
        dest = ACS_DIR / f"acsdt5y{ACS_YEAR}-{table}.dat"
        print(f"  {table.upper()}: {label}")
        download_file(f"{ACS_BASE}/acsdt5y{ACS_YEAR}-{table}.dat", dest, force=force)


def download_crosswalk(force: bool = False) -> None:
    print("2020 <-> 2010 census tract relationship file")
    download_file(CROSSWALK_URL, CROSSWALK_PATH, force=force)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="re-download existing files")
    parser.add_argument(
        "--skip-sld",
        action="store_true",
        help="do not download the large SLD archive if it is missing",
    )
    args = parser.parse_args(argv)

    RAW.mkdir(parents=True, exist_ok=True)
    download_places(force=args.force)
    download_sld(force=args.force, skip=args.skip_sld)
    download_acs(force=args.force)
    download_crosswalk(force=args.force)
    print("\nAll requested raw files are present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
