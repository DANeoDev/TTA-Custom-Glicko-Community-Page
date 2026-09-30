"""Crawler for missing CGE tournament and stage group pages to backfill replays."""
import sys
import argparse
import re
import time
from pathlib import Path
from bs4 import BeautifulSoup

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from src.scrapers.cge import CGEClient, clean_target_path

def get_group_urls_from_stage(client: CGEClient, stage_path: str):
    """Fetches stage HTML and extracts all group sub-page relative paths."""
    html = client.fetch_tournament_html(stage_path)
    soup = BeautifulSoup(html, "html.parser")
    tid = stage_path.split("/")[0]
    stage_num = stage_path.split("/")[1]
    
    group_paths = set()
    for a in soup.find_all("a"):
        href = a.get("href", "")
        # Matches /tournaments/detail/{tid}/{stage_num}/{group_id}
        m = re.search(rf'/tournaments/detail/({tid}/{stage_num}/\d+)\b', href)
        if m:
            group_paths.add(m.group(1))
            
    return sorted(group_paths)

def crawl_stage_groups(client: CGEClient, stage_path: str, max_groups: int = None):
    """Discovers and downloads all group pages for a given tournament stage."""
    print(f"\n=== Discovering groups for Stage {stage_path} ===")
    group_paths = get_group_urls_from_stage(client, stage_path)
    print(f"Found {len(group_paths)} group URLs in Stage {stage_path}")
    
    if max_groups:
        group_paths = group_paths[:max_groups]
        print(f"Limited to first {max_groups} groups")
        
    downloaded = 0
    skipped = 0
    t0 = time.time()
    
    for i, gp in enumerate(group_paths, start=1):
        slug = gp.replace("/", "_")
        cache_file = client.cache_dir / f"{slug}.html"
        
        if cache_file.exists() and cache_file.stat().st_size > 1000:
            skipped += 1
            continue
            
        try:
            client.fetch_tournament_html(gp, force_refresh=True)
            downloaded += 1
            if downloaded % 20 == 0 or i == len(group_paths):
                elapsed = time.time() - t0
                rate = downloaded / elapsed if elapsed > 0 else 0
                print(f"  [{i}/{len(group_paths)}] Downloaded {downloaded}, Skipped {skipped} ({rate:.1f} pages/sec)")
        except Exception as e:
            print(f"  Error fetching {gp}: {e}")
            
    elapsed = time.time() - t0
    print(f"Stage {stage_path} complete: {downloaded} downloaded, {skipped} skipped in {elapsed:.1f}s")
    return downloaded

def main():
    parser = argparse.ArgumentParser(description="Crawl missing CGE tournament group pages")
    parser.add_argument("--stages", nargs="+", help="Specific stages to crawl, e.g. 5860/1 5495/1")
    parser.add_argument("--max-groups", type=int, default=None, help="Max groups per stage")
    parser.add_argument("--delay-min", type=float, default=0.25, help="Min delay between requests")
    parser.add_argument("--delay-max", type=float, default=0.5, help="Max delay between requests")
    args = parser.parse_args()

    client = CGEClient(min_delay=args.delay_min, max_delay=args.delay_max)
    print("Authenticating with CGE...")
    client.login()
    
    stages_to_crawl = args.stages or ["5860/1"]
    total_downloaded = 0
    for st in stages_to_crawl:
        total_downloaded += crawl_stage_groups(client, st, max_groups=args.max_groups)
        
    print(f"\nAll done! Total pages downloaded: {total_downloaded}")

if __name__ == "__main__":
    main()
