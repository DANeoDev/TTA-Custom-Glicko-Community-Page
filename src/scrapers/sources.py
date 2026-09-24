"""Tournament source manager and directory inspector for TTA-Glicko2-WHR.

Discovers, parses, and auto-registers tournament source files (***_sources.md)
and associated result tables (result.csv, *.xlsx) across data/tournaments/.
"""
import re
from pathlib import Path
from typing import Dict, List, Optional, Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOURNAMENTS_DIR = PROJECT_ROOT / "data" / "tournaments"

CGE_URL_PATTERN = re.compile(r'https?://account\.czechgames\.com/tournaments/detail/(\d+)', re.IGNORECASE)
GSHEET_URL_PATTERN = re.compile(r'https?://docs\.google\.com/spreadsheets/[^\s]+', re.IGNORECASE)


def scan_tournament_sources(tournaments_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Scans all tournament subdirectories for ***_sources.md and result files."""
    base_dir = tournaments_dir or TOURNAMENTS_DIR
    if not base_dir.exists():
        return []

    results = []
    for item in sorted(base_dir.iterdir()):
        if not item.is_dir() or item.name.startswith(('.', '_')):
            continue

        folder_name = item.name
        # Community Leaderboard is an external Google Sheet calculation, not a CGE tournament
        if folder_name.lower() == "community_leaderboard":
            continue

        source_files = list(item.glob("*_sources.md"))
        cge_urls = []
        cge_ids = []
        gsheet_urls = []
        other_urls = []

        standings_urls = []
        for sf in source_files:
            try:
                content = sf.read_text(encoding="utf-8", errors="ignore")
                is_standings_section = False
                for line in content.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    if "standings" in line.lower() or "result" in line.lower():
                        is_standings_section = True
                        continue
                    if line.startswith("#"):
                        is_standings_section = False
                        continue
                    m_cge = CGE_URL_PATTERN.search(line)
                    if m_cge:
                        cge_urls.append(m_cge.group(0))
                        cge_ids.append(int(m_cge.group(1)))
                    elif GSHEET_URL_PATTERN.search(line):
                        gsheet_urls.append(line)
                        standings_urls.append(line)
                    elif is_standings_section and (line.startswith("http://") or line.startswith("https://")):
                        standings_urls.append(line)
                    elif line.startswith("http://") or line.startswith("https://"):
                        other_urls.append(line)
            except Exception:
                pass

        # Check for results files
        result_files = []
        for ext in ("*.csv", "*.xlsx", "*.xls"):
            for rf in item.glob(ext):
                result_files.append(rf.name)

        results.append({
            "folder": folder_name,
            "path": str(item),
            "source_files": [f.name for f in source_files],
            "cge_ids": sorted(list(set(cge_ids))),
            "cge_urls": sorted(list(set(cge_urls))),
            "gsheet_urls": sorted(list(set(gsheet_urls))),
            "other_urls": sorted(list(set(other_urls))),
            "standings_url": standings_urls[0] if standings_urls else None,
            "result_files": sorted(result_files),
        })

    return results


def register_tournament_source(
    tournament_name: str,
    source_url: str,
    standings_url: Optional[str] = None,
    result_csv_content: Optional[str] = None,
    result_filename: str = "result.csv",
    tournaments_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """Auto-creates or updates tournament folder, ***_sources.md, and optional result.csv / standings_url.
    
    Args:
        tournament_name: Clean directory name (e.g. 'Royal_League', 'International Championship')
        source_url: CGE URL or Google Sheets URL to add
        standings_url: Optional URL to online standings (Google Sheets or web page)
        result_csv_content: Optional raw text of results CSV
        result_filename: File name to save results under
        tournaments_dir: Override path to tournaments directory
    """
    base_dir = tournaments_dir or TOURNAMENTS_DIR
    clean_folder = re.sub(r'[\\/*?:"<>|]', '_', tournament_name.strip()).replace(' ', '_')
    if not clean_folder:
        clean_folder = "Custom_Tournament"

    target_dir = base_dir / clean_folder
    target_dir.mkdir(parents=True, exist_ok=True)

    # Determine source file name
    prefix = clean_folder.split('_')[0]
    source_file = target_dir / f"{prefix}_sources.md"

    # Read existing content if exists
    existing_lines = []
    if source_file.exists():
        existing_lines = [l.strip() for l in source_file.read_text(encoding="utf-8").splitlines() if l.strip()]

    url_clean = source_url.strip()
    if url_clean and url_clean not in existing_lines:
        existing_lines.append(url_clean)

    if standings_url and standings_url.strip():
        s_url = standings_url.strip()
        if s_url not in existing_lines:
            existing_lines.append("# Official Standings URL")
            existing_lines.append(s_url)

    source_file.write_text("\n\n".join(existing_lines) + "\n", encoding="utf-8")

    saved_result_file = None
    if result_csv_content and result_csv_content.strip():
        r_file = target_dir / result_filename
        r_file.write_text(result_csv_content.strip() + "\n", encoding="utf-8")
        saved_result_file = str(r_file.name)

    return {
        "success": True,
        "folder": clean_folder,
        "directory": str(target_dir),
        "source_file": str(source_file.name),
        "saved_result_file": saved_result_file,
        "standings_url": standings_url,
        "urls": existing_lines,
    }


def get_tournament_source_details(
    folder_name: str,
    tournaments_dir: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    """Retrieves full details for a specific tournament including raw sources text."""
    base_dir = tournaments_dir or TOURNAMENTS_DIR
    target_dir = base_dir / folder_name
    if not target_dir.exists() or not target_dir.is_dir():
        return None

    source_files = list(target_dir.glob("*_sources.md"))
    sources_content = ""
    source_filename = None
    standings_url = None
    cge_urls = []
    gsheet_urls = []
    other_urls = []

    if source_files:
        sf = source_files[0]
        source_filename = sf.name
        try:
            sources_content = sf.read_text(encoding="utf-8", errors="ignore")
            is_standings = False
            for line in sources_content.splitlines():
                line = line.strip()
                if not line:
                    continue
                if "standings" in line.lower() or "result" in line.lower():
                    is_standings = True
                    continue
                if line.startswith("#"):
                    is_standings = False
                    continue
                m_cge = CGE_URL_PATTERN.search(line)
                if m_cge:
                    cge_urls.append(m_cge.group(0))
                elif GSHEET_URL_PATTERN.search(line):
                    gsheet_urls.append(line)
                    standings_url = line
                elif is_standings and (line.startswith("http://") or line.startswith("https://")):
                    standings_url = line
                elif line.startswith("http://") or line.startswith("https://"):
                    other_urls.append(line)
        except Exception:
            pass

    result_files = [rf.name for ext in ("*.csv", "*.xlsx", "*.xls") for rf in target_dir.glob(ext)]

    return {
        "folder": folder_name,
        "directory": str(target_dir),
        "source_file": source_filename,
        "sources_content": sources_content,
        "standings_url": standings_url,
        "cge_urls": sorted(list(set(cge_urls))),
        "gsheet_urls": sorted(list(set(gsheet_urls))),
        "other_urls": sorted(list(set(other_urls))),
        "result_files": sorted(result_files),
    }


def update_tournament_source(
    folder_name: str,
    new_folder_name: Optional[str] = None,
    sources_content: Optional[str] = None,
    standings_url: Optional[str] = None,
    tournaments_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """Updates tournament folder name, sources file, and/or standings URL."""
    base_dir = tournaments_dir or TOURNAMENTS_DIR
    target_dir = base_dir / folder_name
    if not target_dir.exists() or not target_dir.is_dir():
        raise FileNotFoundError(f"Tournament directory '{folder_name}' does not exist.")

    # 1. Handle renaming directory if requested
    current_folder = folder_name
    if new_folder_name and new_folder_name.strip() and new_folder_name.strip() != folder_name:
        clean_new = re.sub(r'[\\/*?:"<>|]', '_', new_folder_name.strip()).replace(' ', '_')
        new_target_dir = base_dir / clean_new
        if new_target_dir.exists() and new_target_dir != target_dir:
            raise ValueError(f"Target directory '{clean_new}' already exists.")
        target_dir.rename(new_target_dir)
        target_dir = new_target_dir
        current_folder = clean_new

    # 2. Update sources file
    source_files = list(target_dir.glob("*_sources.md"))
    if source_files:
        sf = source_files[0]
    else:
        prefix = current_folder.split('_')[0]
        sf = target_dir / f"{prefix}_sources.md"

    if sources_content is not None:
        content_to_write = sources_content.strip()
        # If standings_url is provided and not already in content, append it
        if standings_url and standings_url.strip() and standings_url.strip() not in content_to_write:
            content_to_write += f"\n\n# Official Standings URL\n{standings_url.strip()}"
        sf.write_text(content_to_write + "\n", encoding="utf-8")
    elif standings_url and standings_url.strip():
        curr_text = sf.read_text(encoding="utf-8") if sf.exists() else ""
        if standings_url.strip() not in curr_text:
            curr_text = curr_text.strip() + f"\n\n# Official Standings URL\n{standings_url.strip()}\n"
            sf.write_text(curr_text, encoding="utf-8")

    return {
        "success": True,
        "folder": current_folder,
        "directory": str(target_dir),
        "source_file": sf.name
    }


def delete_tournament_source(
    folder_name: str,
    tournaments_dir: Optional[Path] = None
) -> bool:
    """Deletes a tournament directory from data/tournaments/."""
    import shutil
    base_dir = tournaments_dir or TOURNAMENTS_DIR
    target_dir = base_dir / folder_name
    if target_dir.exists() and target_dir.is_dir():
        shutil.rmtree(target_dir)
        return True
    return False


def infer_tournament_folder_from_title(title: str) -> str:
    """Infers an organized folder name from a scraped tournament title."""
    t = title.strip()
    t_lower = t.lower()
    if "royal league" in t_lower or "rl_" in t_lower or "rl " in t_lower:
        return "Royal_League"
    elif "international" in t_lower:
        return "International_Championship"
    elif "intermezzo" in t_lower:
        return "Intermezzo_Championship"
    elif "australien" in t_lower or "aussie" in t_lower:
        return "Australien_Open"
    elif "mercurial" in t_lower:
        return "Mercurial_Ladder"
    elif "sodium" in t_lower:
        return "Sodium_Ladder"
    elif "transcontinental" in t_lower or "tcl" in t_lower:
        return "Transcontinental_Ladder"
    elif "world" in t_lower:
        return "World_Championship"
    elif "q&d" in t_lower or "quick and dirty" in t_lower:
        return "Q&D"

    # Default: sanitize title as folder
    clean = re.sub(r'[^\w\s-]', '', t).strip().replace(' ', '_')
    return clean or "Tournaments"
