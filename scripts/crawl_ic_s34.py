"""Crawls International Championship Season 34 (CGE target 21/25) all division groups and commits to database and CSV."""
import sys
import logging
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

from src.scrapers.cge import CGEClient
from src.data.merger import preview_scraped_matches, commit_new_matches, export_update_snapshot

def main():
    target = "21/25"
    logger.info(f"Starting crawl for International Championship Season 34 (target: {target})...")
    client = CGEClient(min_delay=1.5, max_delay=3.0)
    
    parsed = client.crawl_season_all_groups(target, force_refresh=False)
    games = parsed.get("games", [])
    logger.info(f"Total games parsed from season 25: {len(games)}")
    
    if not games:
        logger.error("No games found! Aborting.")
        return
        
    diff = preview_scraped_matches(games)
    logger.info(f"Diff preview: Total scraped = {diff['total_scraped']}, Duplicates = {diff['duplicate_count']}, New matches = {diff['new_matches_count']}")
    
    if diff["new_matches_count"] == 0:
        logger.info("No new matches to commit (all duplicates or filtered).")
        return
        
    logger.info(f"Committing {diff['new_matches_count']} new matches...")
    result = commit_new_matches(diff["new_matches"], glicko_eligible=True, export_snapshot=True)
    logger.info(f"Commit result: {result}")
    
    snap = export_update_snapshot()
    logger.info(f"Update snapshot exported to: {snap}")

if __name__ == "__main__":
    main()
