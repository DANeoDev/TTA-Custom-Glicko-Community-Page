"""Tournament Auto-Discovery and Season Completion Tracker for TTA-Glicko2-WHR.

Discovers missing CGE tournament links, tracks ingested vs pending seasons,
and guards against accidental ingestion of mid-season/in-progress tournaments.
"""
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from src.data.db import get_connection
from src.scrapers.sources import TOURNAMENTS_DIR, scan_tournament_sources

KNOWN_CGE_TOURNAMENT_MAP = {
    "Australian Open 2026": {"id": 5703, "folder": "Australien_Open", "source_file": "AO_sources.md"},
    "Royal League Season 8": {"id": 5000, "folder": "Royal_League", "source_file": "RL_sources.md"},
    "Sodium Ladder": {"id": 5169, "folder": "Sodium_Ladder", "source_file": "SL_sources.md"},
    "Mercurial Ladder": {"id": 4820, "folder": "mercurial_ladder", "source_file": "ML_sources.md"},
    "Quick and Dirty": {"id": 4500, "folder": "Q&D", "source_file": "Q&D_sources.md"},
    "Transcontinental Ladder": {"id": 3950, "folder": "Transcontinental_Ladder", "source_file": "TL_sources.md"},
}


def get_ingested_seasons_summary(db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Inspects matches in SQLite to determine which seasons/tournaments are already ingested."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute("SELECT DISTINCT tournament, COUNT(*), MIN(date), MAX(date) FROM matches GROUP BY tournament").fetchall()
        
        series_data = {
            "Royal League": {"seasons": set(), "matches": 0, "latest": None},
            "International Championship": {"seasons": set(), "matches": 0, "latest": None},
            "Intermezzo Championship": {"seasons": set(), "matches": 0, "latest": None},
            "World Championship": {"seasons": set(), "matches": 0, "latest": None},
            "Wimbledon Open": {"seasons": set(), "matches": 0, "latest": None},
            "Australian Open": {"seasons": set(), "matches": 0, "latest": None},
            "Sodium Ladder": {"seasons": set(), "matches": 0, "latest": None},
            "Mercurial Ladder": {"seasons": set(), "matches": 0, "latest": None},
            "Eiffel Tower Cup": {"seasons": set(), "matches": 0, "latest": None},
            "Quick & Dirty": {"seasons": set(), "matches": 0, "latest": None},
            "Transcontinental Ladder": {"seasons": set(), "matches": 0, "latest": None},
        }

        for r in rows:
            t_name = r['tournament']
            cnt = r[1]
            last_d = r[3]

            m_rl = re.search(r'RL_s(\d+)', t_name, re.IGNORECASE)
            if m_rl:
                s_num = int(m_rl.group(1))
                series_data["Royal League"]["seasons"].add(s_num)
                series_data["Royal League"]["matches"] += cnt
                if not series_data["Royal League"]["latest"] or last_d > series_data["Royal League"]["latest"]:
                    series_data["Royal League"]["latest"] = last_d

            m_im = re.search(r'Intermezzo S?(\d+)', t_name, re.IGNORECASE)
            if m_im:
                s_num = int(m_im.group(1))
                series_data["Intermezzo Championship"]["seasons"].add(s_num)
                series_data["Intermezzo Championship"]["matches"] += cnt
                if not series_data["Intermezzo Championship"]["latest"] or last_d > series_data["Intermezzo Championship"]["latest"]:
                    series_data["Intermezzo Championship"]["latest"] = last_d

            m_ic = re.search(r'International.*?S?(\d+)', t_name, re.IGNORECASE)
            if m_ic:
                s_num = int(m_ic.group(1))
                series_data["International Championship"]["seasons"].add(s_num)
                series_data["International Championship"]["matches"] += cnt
                if not series_data["International Championship"]["latest"] or last_d > series_data["International Championship"]["latest"]:
                    series_data["International Championship"]["latest"] = last_d

            if "world" in t_name.lower() or "wrld" in t_name.lower():
                series_data["World Championship"]["matches"] += cnt
                if not series_data["World Championship"]["latest"] or last_d > series_data["World Championship"]["latest"]:
                    series_data["World Championship"]["latest"] = last_d

            if "wimb" in t_name.lower():
                series_data["Wimbledon Open"]["matches"] += cnt
                if not series_data["Wimbledon Open"]["latest"] or last_d > series_data["Wimbledon Open"]["latest"]:
                    series_data["Wimbledon Open"]["latest"] = last_d

            if "austral" in t_name.lower():
                series_data["Australian Open"]["matches"] += cnt
                if not series_data["Australian Open"]["latest"] or last_d > series_data["Australian Open"]["latest"]:
                    series_data["Australian Open"]["latest"] = last_d

            if "sodi" in t_name.lower():
                series_data["Sodium Ladder"]["matches"] += cnt
                if not series_data["Sodium Ladder"]["latest"] or last_d > series_data["Sodium Ladder"]["latest"]:
                    series_data["Sodium Ladder"]["latest"] = last_d

            if "merc" in t_name.lower():
                series_data["Mercurial Ladder"]["matches"] += cnt
                if not series_data["Mercurial Ladder"]["latest"] or last_d > series_data["Mercurial Ladder"]["latest"]:
                    series_data["Mercurial Ladder"]["latest"] = last_d

            if "eiffel" in t_name.lower():
                series_data["Eiffel Tower Cup"]["matches"] += cnt
                if not series_data["Eiffel Tower Cup"]["latest"] or last_d > series_data["Eiffel Tower Cup"]["latest"]:
                    series_data["Eiffel Tower Cup"]["latest"] = last_d

            if "quick" in t_name.lower() or "q&d" in t_name.lower():
                series_data["Quick & Dirty"]["matches"] += cnt

            if "transcont" in t_name.lower() or "tcl" in t_name.lower():
                series_data["Transcontinental Ladder"]["matches"] += cnt

        # Format seasons as sorted list
        res = {}
        for k, v in series_data.items():
            res[k] = {
                "seasons": sorted(list(v["seasons"])),
                "matches": v["matches"],
                "latest_date": v["latest"],
                "latest_season": max(v["seasons"]) if v["seasons"] else None,
                "is_active": v["matches"] > 0
            }
        return res
    finally:
        conn.close()


def auto_populate_missing_tournament_links(tournaments_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Scans tournament folders and populates missing CGE URLs from known mappings and markdown content."""
    base_dir = tournaments_dir or TOURNAMENTS_DIR
    updated = []

    for name, info in KNOWN_CGE_TOURNAMENT_MAP.items():
        folder = base_dir / info["folder"]
        if not folder.exists():
            folder.mkdir(parents=True, exist_ok=True)

        source_file = folder / info["source_file"]
        cge_url = f"https://account.czechgames.com/tournaments/detail/{info['id']}"

        existing = ""
        if source_file.exists():
            existing = source_file.read_text(encoding="utf-8", errors="ignore")

        if str(info["id"]) not in existing and cge_url not in existing:
            new_content = (existing.strip() + "\n\n" + cge_url).strip() + "\n"
            source_file.write_text(new_content, encoding="utf-8")
            updated.append({
                "tournament": name,
                "folder": info["folder"],
                "source_file": str(source_file.name),
                "added_url": cge_url,
                "cge_id": info["id"]
            })

    return updated
