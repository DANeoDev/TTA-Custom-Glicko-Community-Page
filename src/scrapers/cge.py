"""CGE Tournament Scraper for Through the Ages.

Provides authenticated, rate-limited, and privacy-respecting scraping of
tournament details, games, players, and match outcomes from Czech Games Edition
(account.czechgames.com).
"""
import os
import re
import time
import random
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union, Set
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

logger = logging.getLogger(__name__)

MIN_CRAWL_DATE = "2026-01-01"
DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache" / "cge"
BASE_URL = "https://account.czechgames.com"
LOGIN_URL = "https://account.czechgames.com/sign/in"
TOURNAMENT_URL_TEMPLATE = "https://account.czechgames.com/tournaments/detail/{path}"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": BASE_URL,
}


def clean_target_path(target: Union[int, str]) -> str:
    """Normalizes an ID, path, or URL into a clean CGE relative path (e.g. '5000/9')."""
    s = str(target).strip()
    m = re.search(r'/tournaments/detail/([0-9/]+)', s, re.IGNORECASE)
    if m:
        return m.group(1).strip('/')
    m_path = re.search(r'(\d+(?:/\d+)*)', s)
    if m_path:
        return m_path.group(1).strip('/')
    return s.strip('/')


MONTHS = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
}


def parse_cge_date(text: str, default_year: int = 2026, ref_date: Optional[datetime] = None) -> str:
    """Parses CGE date formats including ISO ('2026-08-16'), Month Day ('Aug 16'), and relative ('11 days ago')."""
    if not text:
        return ""
    if ref_date is None:
        ref_date = datetime.now()
    t = text.strip()

    # 1. Full ISO date: YYYY-MM-DD
    m_iso = re.search(r'\b(202\d-\d{2}-\d{2})\b', t)
    if m_iso:
        return m_iso.group(1)

    # 2. Month Day, optional Year: e.g. "Aug 16" or "Jul 18, 2026"
    m_md = re.search(r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{1,2})(?:,?\s+(\d{4}))?\b', t, re.IGNORECASE)
    if m_md:
        month = MONTHS[m_md.group(1).lower()[:3]]
        day = int(m_md.group(2))
        year = int(m_md.group(3)) if m_md.group(3) else default_year
        return f"{year:04d}-{month:02d}-{day:02d}"

    # 3. Relative: "11 days ago", "yesterday", "today", "2 hours ago"
    m_days = re.search(r'\b(\d+)\s+days?\s+ago\b', t, re.IGNORECASE)
    if m_days:
        d = ref_date - timedelta(days=int(m_days.group(1)))
        return d.strftime("%Y-%m-%d")

    m_weeks = re.search(r'\b(\d+)\s+weeks?\s+ago\b', t, re.IGNORECASE)
    if m_weeks:
        d = ref_date - timedelta(days=int(m_weeks.group(1)) * 7)
        return d.strftime("%Y-%m-%d")

    if re.search(r'\byesterday\b', t, re.IGNORECASE):
        d = ref_date - timedelta(days=1)
        return d.strftime("%Y-%m-%d")

    if re.search(r'\b(?:today|hours?\s+ago|minutes?\s+ago)\b', t, re.IGNORECASE):
        return ref_date.strftime("%Y-%m-%d")

    return ""


def parse_player_result_item(text: str) -> Optional[Dict[str, Any]]:
    """Parses a raw CGE player result cell or popover entry.

    Detects normal finished scores, resignations, and timeouts regardless of
    whether a leading rank number (e.g. '1.') is present.
    """
    t = text.strip()
    if not t:
        return None

    if re.search(r'\bTIMED\s*OUT\b|\bTIMEOUT\b', t, re.IGNORECASE):
        status = 'timeout'
    elif re.search(r'\bRESIGNED?\b', t, re.IGNORECASE):
        status = 'resigned'
    else:
        status = 'finished'

    m_rank = re.match(r'^\s*(\d+)\.\s*', t)
    rank = int(m_rank.group(1)) if m_rank else None
    cleaned = re.sub(r'^\s*\d+\.\s*', '', t).strip()

    if status in ('timeout', 'resigned'):
        name = re.sub(r'[\(\[\{]?\s*(?:TIMED\s*OUT|TIMEOUT|RESIGNED?)\s*[\)\]\}]?', '', cleaned, flags=re.IGNORECASE).strip()
        score = None
    else:
        m_s = re.search(r'\(\s*(-?\d+(?:\.\d+)?)\s*\)', cleaned) or re.search(r'\s+(-?\d+(?:\.\d+)?)\s*$', cleaned)
        if not m_s:
            return None
        score = float(m_s.group(1))
        name = cleaned[:m_s.start()].strip()

    name = re.sub(r'[,()]+', '', name).strip()
    if not name or "players :" in name.lower() or "/ ∞" in name:
        return None

    return {"name": name, "status": status, "score": score, "rank": rank}


def order_and_score_participants(candidates: List[Dict[str, Any]]) -> List[Tuple[str, float]]:
    """Orders participants and assigns scores according to TTA tournament rules.

    Placement & Score Hierarchy:
      1. Finished players: sorted by culture score DESC (scores >= 0).
      2. Resigned players: placed behind all finished players.
         - First to resign is placed last; second to resign is second-to-last, etc.
         - Score = -float(final_position) (e.g. 2nd: -2.0, 3rd: -3.0, 4th: -4.0).
      3. Timed out players: placed behind all resignees.
         - First to time out is placed last; second to time out is second-to-last, etc.
         - Score = -5.0.
    """
    finished = []
    resigned = []
    timed_out = []

    seen = set()
    for c in candidates:
        if not c or not isinstance(c, dict):
            continue
        name = c.get('name', '').strip()
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        st = c.get('status', 'finished')
        if st == 'finished':
            finished.append(c)
        elif st == 'resigned':
            resigned.append(c)
        elif st == 'timeout':
            timed_out.append(c)

    # Sort finished by score DESC
    finished.sort(key=lambda x: (x['score'] if x.get('score') is not None else -999), reverse=True)

    # Sort resigned: lower explicit rank first (e.g. 2nd before 3rd); preserve sequence otherwise
    resigned.sort(key=lambda x: (x['rank'] if x.get('rank') is not None else 999))

    # Sort timed out: lower explicit rank first; preserve sequence otherwise
    timed_out.sort(key=lambda x: (x['rank'] if x.get('rank') is not None else 999))

    ordered = finished + resigned + timed_out
    result = []
    for pos, p in enumerate(ordered, start=1):
        if p['status'] == 'finished':
            score = float(p['score'])
        elif p['status'] == 'resigned':
            score = -float(pos)
        else: # timeout
            score = -5.0
        result.append((p['name'], score))

    return result


def format_tournament_match_name(
    base_title: str,
    active_season_num: Optional[int],
    game_title: str,
    stage_name: Optional[str] = None
) -> str:
    """Formats scraped game title into standard all_matches.csv naming conventions."""
    title_clean = base_title.strip()
    t_lower = title_clean.lower()
    st_clean = stage_name.strip() if stage_name else None

    # Clean game_title: strip repeated tournament prefixes if present
    g_title = game_title.strip()

    # 1. Royal League
    if "royal league" in t_lower or re.search(r'\brl\b', t_lower):
        s_num = active_season_num or 1
        m = re.search(r'Royal League\s+(.+?)\s+game\s+(\d+)', g_title, re.IGNORECASE)
        if m:
            div = m.group(1).strip()
            g_num = m.group(2).strip()
            return f"RL_s{s_num:02d} - {div} - game {g_num}"
        return f"RL_s{s_num:02d} - {g_title}"

    # 2. International Championship (CGE season 1 = Community season 10; CGE 25 = Season 34)
    elif "international" in t_lower:
        s_num = active_season_num or 1
        if s_num <= 30:
            s_num = s_num + 9
        m = re.search(r'(.+?)\s+game\s+(\d+)', g_title, re.IGNORECASE)
        if m:
            raw_div = m.group(1).strip()
            g_num = m.group(2).strip()
            clean_div = re.sub(r'^(?:International|Inter\S*)(?:\s+Championship)?\s*', '', raw_div, flags=re.IGNORECASE).strip()
            div_part = f" - {clean_div}" if clean_div else ""
            return f"International S{s_num}{div_part} game {g_num}"
        return f"International S{s_num} - {g_title}"

    # 3. Intermezzo Championship
    elif "intermezzo" in t_lower:
        s_num = active_season_num or 1
        return f"Intermezzo S{s_num} - {g_title}"

    # 4. Survivors Cup (Multi-stage)
    elif "survivor" in t_lower:
        st_label = st_clean or (f"Stage {active_season_num}" if active_season_num else "Stage 1")
        return f"{title_clean} {st_label} - {g_title}"

    # 5. French Open (Multi-stage with odd/even games)
    elif "french open" in t_lower:
        st_label = st_clean or (f"Stage {active_season_num}" if active_season_num else "Stage 1")
        return f"{title_clean} {st_label} - {g_title}"

    # 6. World Championship / Worlds (Multi-stage)
    elif "world" in t_lower:
        st_label = st_clean or (f"Stage {active_season_num}" if active_season_num else "Stage 1")
        return f"{title_clean} {st_label} - {g_title}"

    # 7. Transcontinental Ladder (TCL) (CGE round 84 = Community round 138)
    elif "transcontinental" in t_lower or "tcl" in t_lower:
        r_num = active_season_num or 1
        if r_num < 100:
            r_num = r_num + 54
        r_label = st_clean or f"Round {r_num}"
        if not r_label.lower().startswith("round"):
            r_label = f"Round {r_label}"
        return f"TCL {r_label} - {g_title}"

    # 8. Slow Burn (distinguish First Edition vs Second Edition)
    elif "slow burn" in t_lower:
        edition = "Second Edition" if ("second" in t_lower or "edition 2" in t_lower or "season 2" in t_lower) else "First Edition"
        s_label = f"Season {active_season_num}" if active_season_num else (st_clean or "Season 1")
        return f"Slow Burn {edition} {s_label} - {g_title}"

    # 9. General multi-stage with custom stage name
    if st_clean:
        return f"{title_clean} {st_clean} - {g_title}"
    elif active_season_num:
        return f"{title_clean} Season {active_season_num} - {g_title}"

    return f"{title_clean} - {g_title}"


class CGEClient:
    """Client for navigating and scraping CGE tournament platform."""

    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        session_cookie: Optional[str] = None,
        min_delay: Optional[float] = None,
        max_delay: Optional[float] = None,
        cache_dir: Optional[Path] = None,
    ):
        self.username = username or os.getenv("CGE_USERNAME")
        self.password = password or os.getenv("CGE_PASSWORD")
        self.session_cookie = session_cookie or os.getenv("CGE_SESSION_COOKIE")
        
        # Rate-limiting parameters: explicit arguments take precedence over environment variables
        try:
            self.min_delay = float(min_delay) if min_delay is not None else float(os.getenv("CGE_MIN_DELAY", 2.5))
            self.max_delay = float(max_delay) if max_delay is not None else float(os.getenv("CGE_MAX_DELAY", 5.0))
        except (ValueError, TypeError):
            self.min_delay = 2.5
            self.max_delay = 5.0

        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.is_authenticated = False

        if self.session_cookie:
            self.session.cookies.set("PHPSESSID", self.session_cookie.strip(), domain="account.czechgames.com")
            self.is_authenticated = True

    def polite_sleep(self):
        """Randomized pause between requests to respect CGE anti-bot etiquette."""
        delay = random.uniform(self.min_delay, self.max_delay)
        time.sleep(delay)

    def login(self) -> bool:
        """Authenticates with CGE using credentials via Nette login form."""
        if not self.username or not self.password:
            logger.warning("CGE username or password not provided; skipping automated login.")
            return False

        try:
            resp = self.session.get(LOGIN_URL, timeout=20)
            if resp.status_code != 200:
                logger.error(f"Failed to load CGE login page: HTTP {resp.status_code}")
                return False

            soup = BeautifulSoup(resp.text, "html.parser")
            form = soup.find("form", id=re.compile(r"signIn", re.IGNORECASE)) or soup.find("form", action=re.compile(r"sign/in", re.IGNORECASE))
            
            action = LOGIN_URL
            if form and form.get("action"):
                action = urljoin(LOGIN_URL, form["action"])

            data = {
                "email": self.username,
                "password": self.password,
                "_do": "signInHeaderForm-form-submit",
                "_submit": "Sign in",
            }

            if form:
                for hidden in form.find_all("input", type="hidden"):
                    name = hidden.get("name")
                    val = hidden.get("value", "")
                    if name:
                        data[name] = val

            self.polite_sleep()
            post_resp = self.session.post(action, data=data, timeout=20, allow_redirects=True)

            if "Sign in" not in post_resp.text or "Sign out" in post_resp.text or "/sign/out" in post_resp.text:
                self.is_authenticated = True
                logger.info("Successfully authenticated with CGE.")
                return True
            else:
                logger.warning("CGE login submitted, but session does not appear authenticated.")
                return False

        except Exception as e:
            logger.error(f"Exception during CGE login: {e}")
            return False

    def fetch_tournament_html(self, target: Union[int, str], force_refresh: bool = False) -> str:
        """Fetches tournament detail HTML, using local cache when available."""
        path_str = clean_target_path(target)
        cache_slug = path_str.replace('/', '_')
        cache_file = self.cache_dir / f"{cache_slug}.html"

        if not force_refresh and cache_file.exists():
            return cache_file.read_text(encoding="utf-8", errors="ignore")

        if not self.is_authenticated and (self.username or self.password):
            self.login()

        url = TOURNAMENT_URL_TEMPLATE.format(path=path_str)
        self.polite_sleep()
        
        resp = self.session.get(url, timeout=25)
        if resp.status_code == 200:
            if "Sign in" in resp.text and ("frm-signInHeaderForm-form" in resp.text or "sign/in" in resp.url):
                logger.info(f"Target '{path_str}' requires login. Attempting authentication...")
                if self.login():
                    self.polite_sleep()
                    resp = self.session.get(url, timeout=25)

            html = resp.text
            cache_file.write_text(html, encoding="utf-8")
            return html
        else:
            raise RuntimeError(f"Failed to fetch tournament '{path_str}': HTTP {resp.status_code}")

    @staticmethod
    def parse_tournament_html(
        html: str, 
        target: Optional[Union[int, str]] = None,
        tournament_id: Optional[Union[int, str]] = None
    ) -> Dict[str, Any]:
        """Parses CGE tournament detail HTML into structured tournament metadata, stages, and games."""
        effective_target = target if target is not None else tournament_id
        soup = BeautifulSoup(html, "html.parser")
        path_str = clean_target_path(effective_target) if effective_target is not None else ""

        # Check for CGE error message or access restrictions
        danger_alert = soup.find(class_=re.compile(r"alert-(?:danger|warning|info)"))
        if danger_alert:
            alert_text = danger_alert.get_text(strip=True).lower()
            if "tournament does not exist" in alert_text:
                logger.warning(f"Tournament does not exist on CGE for target '{path_str}'")
                return {
                    "title": f"Tournament {path_str or ''} (Not Found)",
                    "is_finished": False,
                    "status_label": "Not Found",
                    "stages": [],
                    "games": [],
                    "error": "Tournament does not exist"
                }
            if "cannot view this tournament" in alert_text or "access denied" in alert_text or "not authorized" in alert_text:
                logger.warning(f"Access restricted / cannot view tournament on CGE for target '{path_str}': {alert_text}")
                return {
                    "title": f"Tournament {path_str or ''} (Private / Access Restricted)",
                    "is_finished": False,
                    "status_label": "Private / Restricted",
                    "stages": [],
                    "games": [],
                    "error": "Private / Access Restricted"
                }

        # 1. Extract Tournament Title
        title_el = (
            soup.find("h1") or
            soup.find("h2", class_=re.compile(r"title|header", re.IGNORECASE))
        )
        if not title_el:
            page_title = soup.find("title")
            if page_title and page_title.get_text(strip=True).replace('| CGE Online', '').strip().lower() not in ("cge online", ""):
                title_el = page_title

        raw_title = title_el.get_text(strip=True) if title_el else ""
        raw_title = re.sub(r'[\r\n\t]+', ' ', raw_title).replace('| CGE Online', '').strip()

        # Guard: If CGE redirected to general directory without tournament table
        if (not raw_title or raw_title.lower() == "cge online") and not soup.find("table", class_="tournaments-games"):
            logger.warning(f"Target '{path_str}' returned generic CGE page without tournament content.")
            return {
                "title": f"Tournament {path_str or ''} (Invalid / Restricted)",
                "is_finished": False,
                "status_label": "Invalid / Restricted",
                "stages": [],
                "games": [],
                "error": "Generic CGE page returned"
            }

        title = raw_title or f"Tournament {path_str or ''}"

        # 2. Extract Finish Date or Tournament Dates
        finish_date = "2026-06-01"
        finished_raw = re.findall(r'finished\s+([^\n<]+)', html, re.IGNORECASE)
        parsed_dates = [parse_cge_date(d) for d in finished_raw]
        parsed_dates = [d for d in parsed_dates if d]
        if parsed_dates:
            finish_date = max(parsed_dates)
        else:
            started_dates = re.findall(r'(?:stage|season)\s+started\s+at\s+(\d{4}-\d{2}-\d{2})', html, re.IGNORECASE)
            if started_dates:
                finish_date = max(started_dates)
            else:
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', html)
                finish_date = date_match.group(1) if date_match else "2026-06-01"

        # 3. Detect Stages / Seasons from dropdown
        stages = []
        dropdown = soup.find(class_='dropdown-menu')
        if dropdown:
            for a in dropdown.find_all('a', href=True):
                s_text = a.get_text(strip=True).replace('\n', ' ').strip()
                s_href = a['href']
                m_st = re.search(r'/detail/\d+/(\d+)', s_href)
                if m_st:
                    stages.append({
                        "season_num": int(m_st.group(1)),
                        "name": s_text,
                        "url": s_href,
                        "path": f"{path_str.split('/')[0]}/{m_st.group(1)}"
                    })

        # Active Season Number & Stage Name
        active_season_num = None
        active_stage_name = None
        active_btn = soup.find(id='dropdownMenuLink')
        if active_btn:
            active_stage_name = active_btn.get_text(strip=True).replace('\n', ' ').strip()
            m_btn = re.search(r'season\s*(\d+)|stage\s*(\d+)|round\s*(\d+)', active_stage_name, re.IGNORECASE)
            if m_btn:
                active_season_num = int(m_btn.group(1) or m_btn.group(2) or m_btn.group(3))

        # If not detected from button, check path_str (e.g. 5000/9)
        if not active_season_num and '/' in path_str:
            parts = path_str.split('/')
            if len(parts) >= 2 and parts[1].isdigit():
                active_season_num = int(parts[1])

        # If active_stage_name still not set or generic, look up in stages list
        if active_season_num and stages and not active_stage_name:
            for st in stages:
                if st.get("season_num") == active_season_num:
                    active_stage_name = st.get("name")
                    break

        # 4. Check Tournament Completion Status (Accurate CGE badge detection)
        is_finished = True
        status_label = "Finished"
        status_badge = soup.find(class_=re.compile(r'progress-bg-(finished|running|registration)'))
        if status_badge:
            classes = status_badge.get('class', [])
            badge_txt = status_badge.get_text(strip=True)
            if any('progress-bg-running' in c or 'progress-bg-registration' in c for c in classes):
                is_finished = False
                status_label = "In Progress"
            elif any('progress-bg-finished' in c for c in classes) or "finished" in badge_txt.lower():
                is_finished = True
                status_label = "Finished"
            else:
                status_label = badge_txt
        elif "registration" in html.lower():
            is_finished = False
            status_label = "Registration"
        elif "after stage" in html.lower():
            m_after = re.search(r'after\s+stage\s+(\d+)', html, re.IGNORECASE)
            if m_after:
                status_label = f"after stage {m_after.group(1)}"
            is_finished = True
        else:
            # Check for finished badges
            for b in soup.find_all(class_=re.compile(r'badge')):
                bt = b.get_text(strip=True).lower()
                if 'finished' in bt or 'after season' in bt:
                    is_finished = True
                    status_label = b.get_text(strip=True)
                    break
                elif 'running' in bt or 'in progress' in bt:
                    is_finished = False
                    status_label = "In Progress"

        # 5. Extract Groups if present in tournament view
        groups = []
        base_id = path_str.split('/')[0] if path_str else ""
        season_id = str(active_season_num or 1)
        group_pattern = re.compile(rf'/tournaments/detail/{base_id}/{season_id}/(\d+)', re.IGNORECASE)

        seen_groups = set()
        for a in soup.find_all('a', href=True):
            href = a['href']
            m_grp = group_pattern.search(href)
            if m_grp:
                gid = int(m_grp.group(1))
                g_name = a.get_text(strip=True)
                if gid not in seen_groups and g_name:
                    seen_groups.add(gid)
                    groups.append({
                        "group_id": gid,
                        "name": g_name,
                        "url": href,
                        "path": f"{base_id}/{season_id}/{gid}"
                    })

        # 6. Extract Games
        games: List[Dict[str, Any]] = []

        # Strategy 1: CGE table.tournaments-games with session titles and popovers
        for t in soup.find_all("table", class_="tournaments-games"):
            # Collect all title spans and pair each with the next <tr> sibling (the game row).
            # This is safer than the old i += 2 stride which skipped games on DOM variation.
            all_rows = t.find_all("tr")
            row_index = {id(r): idx for idx, r in enumerate(all_rows)}

            for r in all_rows:
                span_t = r.find(class_="session-name-title")
                if not span_t:
                    continue
                g_title = span_t.get_text(strip=True)

                # Find the immediately following <tr> in the table — it is the game row
                my_idx = row_index.get(id(r))
                if my_idx is None or my_idx + 1 >= len(all_rows):
                    continue
                r_game = all_rows[my_idx + 1]

                # Skip if this row also has a session-name-title (two titles in a row = no game between)
                if r_game.find(class_="session-name-title"):
                    continue

                matched_parts = None

                # 1. First check visible player columns in r_game (removes popovers to get exact per-game scores)
                td_cell = r_game.find('td')
                if td_cell:
                    td_copy = BeautifulSoup(str(td_cell), 'html.parser').find('td')
                    for pop in td_copy.find_all(id=re.compile(r'popover-user')):
                        pop.decompose()
                    visible_parts = []
                    for div in td_copy.find_all('div', recursive=False):
                        txt = div.get_text(' ', strip=True)
                        item = parse_player_result_item(txt)
                        if item:
                            visible_parts.append(item)
                    if len(visible_parts) >= 2:
                        matched_parts = order_and_score_participants(visible_parts)

                # 2. If not matched from visible columns, search popover blocks
                if not matched_parts:
                    player_anchors = r_game.find_all('a', class_='player-tooltip')
                    target_players = [re.sub(r'^\d+\.\s*', '', a.get_text(strip=True)) for a in player_anchors]
                    target_set = {p.lower() for p in target_players if p}

                    for pop in r_game.find_all(id=re.compile(r'popover-user')):
                        for block in pop.find_all('div', recursive=False):
                            items = block.find_all(class_='player-tooltip-result')
                            if not items:
                                continue
                            parts = []
                            for item in items:
                                txt = item.get_text(' ', strip=True)
                                p_item = parse_player_result_item(txt)
                                if p_item:
                                    parts.append(p_item)
                            if len(parts) >= len(target_players) and len(parts) >= 2:
                                part_names = {p['name'].lower() for p in parts}
                                if target_set.issubset(part_names):
                                    matched_parts = order_and_score_participants(parts)
                                    break
                        if matched_parts:
                            break

                # 3. Fallback if still no target set matched
                if not matched_parts:
                    pop = r_game.find(id=re.compile(r"popover-user"))
                    if pop:
                        res_div = pop.find(class_="player-tooltip-result")
                        if res_div and res_div.parent:
                            parts = []
                            for item in res_div.parent.find_all(class_="player-tooltip-result"):
                                txt = item.get_text(" ", strip=True)
                                p_item = parse_player_result_item(txt)
                                if p_item:
                                    parts.append(p_item)
                            if len(parts) >= 2:
                                matched_parts = order_and_score_participants(parts)

                if matched_parts:
                    # Extract game-specific date if present in title row or row itself, fallback to finish_date
                    parsed_gdate = parse_cge_date(r.get_text()) or parse_cge_date(r_game.get_text())
                    game_date = parsed_gdate if parsed_gdate else finish_date
                    if game_date < MIN_CRAWL_DATE:
                        # Allow French Open Stage 1 even if finished in mid-2025
                        if not ("french" in title.lower() and active_season_num == 1):
                            continue

                    tourney_match_name = format_tournament_match_name(
                        title, active_season_num, g_title, stage_name=active_stage_name
                    )

                    # Extract replay / spectate code (e.g. FIBECICOMA)
                    replay_code = None
                    spec_el = r.find(class_=re.compile(r"spectate-code|session-code")) or r_game.find(class_=re.compile(r"spectate-code|session-code"))
                    if spec_el:
                        code_txt = spec_el.get_text(strip=True)
                        if code_txt and len(code_txt) >= 4 and code_txt.isupper():
                            replay_code = code_txt

                    games.append({
                        "tournament": tourney_match_name,
                        "date": game_date,
                        "player_count": len(matched_parts),
                        "participants": matched_parts,
                        "seating_order": None,
                        "raw_row": g_title,
                        "replay_code": replay_code
                    })

        # Strategy 2: Fallback to explicit games-table (used in test mocks or custom table views)
        if not games and soup.find("table", class_=re.compile(r"games-table|tournament-games", re.IGNORECASE)):
            tables = soup.find_all("table", class_=re.compile(r"games-table|tournament-games", re.IGNORECASE))
            for table in tables:
                rows = table.find_all("tr")
                for tr in rows:
                    cells = tr.find_all(["td", "th"])
                    if len(cells) < 2:
                        continue

                    row_text = tr.get_text(separator=" ", strip=True)
                    if "players :" in row_text.lower() or "/ ∞" in row_text or "no finished games" in row_text.lower():
                        continue

                    participants = []
                    seating = []

                    # Check for player links
                    player_links = tr.find_all("a", href=re.compile(r"/users/|/player/|/profile/|/u/", re.IGNORECASE))
                    if len(player_links) >= 2:
                        for pl in player_links:
                            p_name = pl.get_text(strip=True)
                            if not p_name or "players :" in p_name.lower():
                                continue
                            seating.append(p_name)
                            score = 0.0
                            if pl.next_sibling:
                                score_m = re.search(r'(-?\d+(?:\.\d+)?)', str(pl.next_sibling))
                                if score_m:
                                    score = float(score_m.group(1))
                            if score == 0.0:
                                next_tag = pl.find_next_sibling()
                                if next_tag:
                                    score_m = re.search(r'(-?\d+(?:\.\d+)?)', next_tag.get_text(strip=True))
                                    if score_m:
                                        score = float(score_m.group(1))
                            participants.append((p_name, score))

                    # Check cell text structures
                    if len(participants) < 2:
                        cell_texts = [c.get_text(strip=True) for c in cells]
                        parsed_pairs = []
                        idx = 0
                        while idx < len(cell_texts):
                            val = cell_texts[idx]
                            if idx + 1 < len(cell_texts):
                                next_val = cell_texts[idx + 1]
                                if re.match(r'^-?\d+(?:\.\d+)?$', next_val) and not re.match(r'^-?\d+$', val):
                                    parsed_pairs.append((val, float(next_val)))
                                    idx += 2
                                    continue
                            idx += 1
                        if len(parsed_pairs) >= 2:
                            participants = parsed_pairs
                            seating = [p[0] for p in parsed_pairs]

                    if len(participants) in (2, 3, 4):
                        # Domain sanity check on scores
                        if any(s > 1000.0 or s < -5.0 for _, s in participants):
                            continue
                        if any("players :" in p[0].lower() or "no finished games" in p[0].lower() for p in participants):
                            continue

                        parsed_gdate = parse_cge_date(row_text)
                        game_date = parsed_gdate if parsed_gdate else finish_date
                        if game_date < MIN_CRAWL_DATE:
                            if not ("french" in title.lower() and active_season_num == 1):
                                continue

                        sorted_participants = sorted(participants, key=lambda x: x[1], reverse=True)
                        tourney_match_name = format_tournament_match_name(
                            title, active_season_num, row_text[:50], stage_name=active_stage_name
                        )
                        # Extract replay / spectate code
                        replay_code = None
                        spec_el = tr.find(class_=re.compile(r"spectate-code|session-code"))
                        if spec_el:
                            code_txt = spec_el.get_text(strip=True)
                            if code_txt and len(code_txt) >= 4 and code_txt.isupper():
                                replay_code = code_txt

                        games.append({
                            "tournament": tourney_match_name,
                            "date": game_date,
                            "player_count": len(sorted_participants),
                            "participants": sorted_participants,
                            "seating_order": seating if seating != [p[0] for p in sorted_participants] else None,
                            "raw_row": row_text[:120],
                            "replay_code": replay_code
                        })

        tid = None
        if tournament_id is not None:
            try:
                tid = int(tournament_id)
            except (ValueError, TypeError):
                tid = tournament_id
        elif path_str:
            p_first = path_str.split('/')[0]
            if p_first.isdigit():
                tid = int(p_first)
            else:
                tid = p_first

        return {
            "title": title,
            "target": path_str,
            "tournament_id": tid,
            "finish_date": finish_date,
            "is_finished": is_finished,
            "status_label": status_label,
            "active_season_num": active_season_num,
            "active_stage_name": active_stage_name,
            "stages": stages,
            "groups": groups,
            "games_count": len(games),
            "games": games,
        }

    def crawl_season_all_groups(
        self,
        target: Union[int, str],
        max_groups: Optional[int] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Crawls all division groups for a season, aggregating all finished games.

        Args:
            target:        Season URL / path (e.g. '5000/9').
            max_groups:    Optional limit on number of groups to crawl (for testing).
            force_refresh: If True, bypass cache and re-fetch all pages from CGE.
                           Use this for commit-grade scrapes to avoid stale data.
        """
        main_html = self.fetch_tournament_html(target, force_refresh=force_refresh)
        main_parsed = self.parse_tournament_html(main_html, target=target)

        all_games = list(main_parsed["games"])
        seen_matches = {g["raw_row"] for g in all_games}

        groups = main_parsed.get("groups", [])
        if max_groups:
            groups = groups[:max_groups]

        group_completeness = []  # per-group completeness metadata

        for grp in groups:
            grp_path = grp.get("path")
            if not grp_path:
                continue

            try:
                g_html = self.fetch_tournament_html(grp_path, force_refresh=force_refresh)
                g_parsed = self.parse_tournament_html(g_html, target=grp_path)
                grp_games = g_parsed.get("games", [])

                new_count = 0
                for g in grp_games:
                    if g["raw_row"] not in seen_matches:
                        seen_matches.add(g["raw_row"])
                        all_games.append(g)
                        new_count += 1

                # Per-group completeness: count unique players and expected games
                grp_players: set = set()
                for g in grp_games:
                    for p_name, _ in g.get("participants", []):
                        grp_players.add(p_name.lower())
                n = len(grp_players)
                expected = n * (n - 1) // 2 if n >= 2 else 0

                group_completeness.append({
                    "group_name": grp.get("name", grp_path),
                    "group_path": grp_path,
                    "players": sorted(grp_players),
                    "player_count": n,
                    "expected_games": expected,
                    "scraped_games": len(grp_games),
                    "new_games": new_count,
                    "complete": len(grp_games) >= expected if expected > 0 else None,
                })
            except Exception as e:
                logger.warning(f"Error crawling group {grp_path}: {e}")
                group_completeness.append({
                    "group_name": grp.get("name", grp_path),
                    "group_path": grp_path,
                    "error": str(e),
                    "complete": False,
                })

        main_parsed["games"] = all_games
        main_parsed["games_count"] = len(all_games)
        main_parsed["group_completeness"] = group_completeness
        return main_parsed

    def crawl_tournament_all_stages(
        self,
        target: Union[int, str],
        crawl_all_groups: bool = True,
        force_refresh: bool = False,
        stage_nums: Optional[List[int]] = None,
        skip_seasons: Optional[Set[int]] = None
    ) -> Dict[str, Any]:
        """Crawls all stages or seasons of a multi-stage tournament.

        Discovers all stages from the tournament root's dropdown menu,
        then systematically crawls each stage and its groups, aggregating
        games from all stages into a unified dataset.
        """
        main_html = self.fetch_tournament_html(target, force_refresh=force_refresh)
        main_parsed = self.parse_tournament_html(main_html, target=target)

        stages = main_parsed.get("stages", [])
        if not stages:
            if crawl_all_groups:
                return self.crawl_season_all_groups(target, force_refresh=force_refresh)
            return main_parsed

        target_stages = stages
        if stage_nums:
            target_stages = [s for s in stages if s.get("season_num") in stage_nums]

        # Crawl newest stages first (e.g. Season 26, Season 25...)
        target_stages = sorted(target_stages, key=lambda s: s.get("season_num") or 0, reverse=True)

        all_games = []
        seen_matches = set()
        stages_summary = []
        all_group_completeness = []

        logger.info(f"Crawling {len(target_stages)} stages (newest first) for '{main_parsed.get('title')}'...")

        for st in target_stages:
            st_path = st.get("path")
            st_num = st.get("season_num")
            if not st_path:
                continue

            # Account for community season offsets when checking skip_seasons
            check_num = st_num
            t_title_lower = main_parsed.get("title", "").lower()
            if "international" in t_title_lower and st_num is not None and st_num <= 30:
                check_num = st_num + 9
            elif ("transcontinental" in t_title_lower or "tcl" in t_title_lower) and st_num is not None and st_num < 100:
                check_num = st_num + 54

            if skip_seasons and check_num is not None and check_num in skip_seasons:
                logger.info(f"Skipping Stage/Season {st_num} (Community {check_num} '{st.get('name')}') — already present in all_matches.csv")
                stages_summary.append({
                    "stage_num": st_num,
                    "community_season_num": check_num,
                    "name": st.get("name"),
                    "path": st_path,
                    "games_count": 0,
                    "new_games": 0,
                    "skipped": True,
                    "reason": "already in all_matches.csv"
                })
                # Fast skip: if all stages <= check_num are already in skip_seasons, break reverse crawl
                if all(n in skip_seasons for n in range(min(skip_seasons), check_num + 1)):
                    logger.info(f"All earlier stages (<= {check_num}) already ingested. Halting reverse crawl.")
                    break
                continue

            is_special_fo = ("french" in t_title_lower and st_num == 1)

            if not is_special_fo and st.get("name") and re.search(r'\b(201\d|202[0-5])\b', st.get("name", "")):
                logger.info(f"Skipping Stage/Season {st_num} ('{st.get('name')}') — prior to 2026 cutoff")
                stages_summary.append({
                    "stage_num": st_num,
                    "community_season_num": check_num,
                    "name": st.get("name"),
                    "path": st_path,
                    "games_count": 0,
                    "new_games": 0,
                    "skipped": True,
                    "reason": "prior to 2026 cutoff"
                })
                continue

            # Pre-flight check on stage main page before crawling all division groups
            try:
                st_main_html = self.fetch_tournament_html(st_path, force_refresh=force_refresh)
                st_main_parsed = self.parse_tournament_html(st_main_html, target=st_path)
            except Exception as e:
                logger.warning(f"Failed to fetch stage {st_path}: {e}")
                st_main_parsed = {}

            if st_main_parsed.get("is_finished") is False:
                logger.info(f"Stage {st_num} ('{st.get('name')}') is still in progress — skipping.")
                stages_summary.append({
                    "stage_num": st_num,
                    "community_season_num": check_num,
                    "name": st.get("name"),
                    "path": st_path,
                    "games_count": 0,
                    "new_games": 0,
                    "skipped": True,
                    "reason": "in progress"
                })
                continue

            if not is_special_fo and st_main_parsed.get("finish_date", "") < MIN_CRAWL_DATE:
                logger.info(f"Stage {st_num} ('{st.get('name')}') concluded on {st_main_parsed.get('finish_date')}, prior to 2026 cutoff. Stopping backward crawl.")
                stages_summary.append({
                    "stage_num": st_num,
                    "community_season_num": check_num,
                    "name": st.get("name"),
                    "path": st_path,
                    "games_count": 0,
                    "new_games": 0,
                    "skipped": True,
                    "reason": "prior to 2026 cutoff"
                })
                break  # Stop reverse chronological crawl: earlier seasons are also pre-2026

            try:
                if crawl_all_groups:
                    st_result = self.crawl_season_all_groups(st_path, force_refresh=force_refresh)
                else:
                    st_html = self.fetch_tournament_html(st_path, force_refresh=force_refresh)
                    st_result = self.parse_tournament_html(st_html, target=st_path)

                st_games = st_result.get("games", [])
                st_added = 0
                for g in st_games:
                    match_key = (g.get("tournament"), g.get("raw_row"))
                    if match_key not in seen_matches:
                        seen_matches.add(match_key)
                        all_games.append(g)
                        st_added += 1

                stages_summary.append({
                    "stage_num": st.get("season_num"),
                    "name": st.get("name"),
                    "path": st_path,
                    "games_count": len(st_games),
                    "new_games": st_added
                })

                if "group_completeness" in st_result:
                    all_group_completeness.extend(st_result["group_completeness"])

            except Exception as e:
                logger.warning(f"Error crawling stage {st_path}: {e}")
                stages_summary.append({
                    "stage_num": st.get("season_num"),
                    "name": st.get("name"),
                    "path": st_path,
                    "error": str(e)
                })

        main_parsed["games"] = all_games
        main_parsed["games_count"] = len(all_games)
        main_parsed["stages_summary"] = stages_summary
        main_parsed["group_completeness"] = all_group_completeness
        return main_parsed

