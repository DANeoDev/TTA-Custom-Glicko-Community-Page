"""Sync tournament data from public Google Sheets / web sources and ingest into SQLite."""
import os
import re
import sys
import glob
import urllib.request
import urllib.error
from pathlib import Path

# Add src to python path
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR / 'src'))

from data.parse_tournaments import parse_all_tournaments

DATA_DIR = ROOT_DIR / 'data'
TOURNAMENTS_DIR = DATA_DIR / 'tournaments'

# Known direct public sync targets mapped from sources.md
SYNC_TARGETS = [
    {
        'name': 'Royal League Standings (S01/Active)',
        'folder': TOURNAMENTS_DIR / 'Royal_League',
        'filename': 'TtA Royal League - S_01.csv',
        'sheet_id': '1WA_3sSKrnfOY12r30E3h-qolPCSq2ZdSI-gM2Os5QjE',
        'gid': '0'
    },
    {
        'name': 'Sodium Ladder Hall of Fame',
        'folder': TOURNAMENTS_DIR / 'Sodium_Ladder',
        'filename': 'TtA Sodium Ladder - Hall of Fame.csv',
        'sheet_id': '1cT0XhREQlpH7fnuXGq7WW6LNToB2QStQ904KEIQ01NE',
        'gid': '985225650'
    },
    {
        'name': 'Australian Open 2026',
        'folder': TOURNAMENTS_DIR / 'Australien_Open',
        'filename': 'Aussie Open 2026 - AussieOpen2026.csv',
        'sheet_id': '15_r_piGEfnj-TU39_uWLP5qaju0OS71eFEZ-3UZVkIo',
        'gid': '1168751304'
    }
]


def extract_google_sheet_csv_url(raw_url: str):
    """Extract CSV download URL from Google Sheets URL."""
    match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', raw_url)
    if not match:
        return None
    sheet_id = match.group(1)
    gid_match = re.search(r'[#&?]gid=([0-9]+)', raw_url)
    gid = gid_match.group(1) if gid_match else '0'
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"


def download_csv(url: str, target_path: Path, timeout: int = 15) -> bool:
    """Download CSV file with user agent and save to target path."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            content = response.read()
            if len(content) > 50 and b'<html' not in content[:200].lower():
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with open(target_path, 'wb') as f:
                    f.write(content)
                return True
            else:
                print(f"  [WARN] Downloaded content from {url} is HTML or too small ({len(content)} bytes), skipping overwrite.")
                return False
    except Exception as exc:
        print(f"  [WARN] Failed to fetch {url}: {exc}")
        return False


def sync_all_sources():
    print("=" * 65)
    print("  TTA TOURNAMENT ARCHIVE SYNC & INGESTION")
    print("=" * 65)

    # 1. Process configured direct targets
    print("\n[Phase 1] Syncing live Google Sheet public exports...")
    for target in SYNC_TARGETS:
        csv_url = f"https://docs.google.com/spreadsheets/d/{target['sheet_id']}/export?format=csv&gid={target['gid']}"
        dest_file = target['folder'] / target['filename']
        print(f" -> Fetching {target['name']}...")
        success = download_csv(csv_url, dest_file)
        if success:
            print(f"    [OK] Saved {dest_file.stat().st_size:,} bytes to {dest_file.name}")
        else:
            print(f"    [INFO] Using existing local copy: {dest_file.name}")

    # 2. Inspect all *_sources.md in data/tournaments to discover any additional Google Sheet links
    print("\n[Phase 2] Scanning data/tournaments/*_sources.md for any additional links...")
    for md_path in glob.glob(str(TOURNAMENTS_DIR / '**' / '*_sources.md'), recursive=True):
        p = Path(md_path)
        with open(p, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                line = line.strip()
                if 'docs.google.com/spreadsheets' in line:
                    csv_url = extract_google_sheet_csv_url(line)
                    if csv_url:
                        print(f" -> Discovered sheet URL in {p.relative_to(ROOT_DIR)}: {csv_url}")

    # 3. Ingest all tournament data into SQLite
    print("\n[Phase 3] Ingesting all tournament records into SQLite database...")
    parse_all_tournaments()
    print("\n[Done] Tournament data synchronization and ingestion complete!")


if __name__ == '__main__':
    sync_all_sources()
