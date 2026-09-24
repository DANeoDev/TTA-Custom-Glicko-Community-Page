# Web Portal User Guide

The Through the Ages (TTA) Rating Portal provides an intuitive, antique-themed web dashboard for analyzing competitive players.

---

## 1. Global Model Switcher
Located in the upper-right corner of the top navigation bar. Clicking any model immediately switches the active rating model across the entire session:
- **GlickoD* (Gold Standard by DANeo)**: Flagship predictive model uniting Golden Ratio ($\phi^{N-2}$) multiplayer decomposition, dual-criterion prior recalibration, and decoupled season resets.
- **Glicko-2 Standard**: Official online leaderboard benchmark (naive 1v1 pairwise).
- **Glicko-2 MP-Weighted**: Scientifically calibrated for 3p and 4p matches with fractional weighting ($w = 1/(N-1)$).
- **Glicko-2 Adaptive-T**: Analytical research model evaluating thermal probability scaling.
- **Whole-History Rating (WHR)**: Rémi Coulom's retrospective Brownian motion model.

### 1.1 Season Reset Selector
Allows switching between rating continuity paradigms:
- **Continuous (Career)**: Standard uninterrupted Bayesian career trajectory across all historical tournaments.
- **Season Reset (Softer)**: Calibrated annual reset balancing career achievement with current season form ($\alpha \approx 1.45, \lambda \approx 0.118$).

---

## 2. Leaderboard View (`/`)
- **Ranking Column**: Ranked strictly by **Conservative Rating** ($C = \mu - 3\sigma$).
- **Format Selector**: Instantly switch between **All Formats**, **2-Player (Duel)**, **3-Player**, and **4-Player** ratings and leaderboards.
- **Provisional Calibration Indicator (`⏳`)**: Displayed directly next to the names of players who have completed fewer than 15 matches and are active within the past year. Hovering shows an informative tooltip explaining their calibration progress.
- **Inactivity Filter**: Standard default view hides inactive players (no tournament game in >12 months), with toggles to view all competitors or retired players only.
- **RB48 Deltas Filter**: Toggle performance deltas across selectable time windows: **Off**, **Last Month (30d)**, **Last Quarter (90d)**, **Last Year (365d)**, or **Official Baseline**.
- **Hover Explainers**: Interactive tooltips on all table headers explaining C-Rating, RD, W-L-D, Win%, and inactivity.
- **Nationality Flags**: Displays country flags derived from ISO 3166-1 alpha-2 codes.
- **Title Badges**: `WC` (World Champion), `GM` (Grandmaster), `M` (Master), `P` (Platinum), `G` (Gold), `S` (Silver), `B` (Bronze), `W` (Wood).
- **Interactive Search & Title Filter**: Filter instantly by player name, country code, or title.
- **Sorting & Pagination**: Click any column header to sort ascending or descending.

---

## 3. Player Profile View (`/player/<name>`)
- **Format Switcher**: View career rating and rank in All Formats, 2p, 3p, or 4p.
- **Multi-Model Summary Cards**: Direct side-by-side comparison of the player's rating, RD, conservative rating, and rank across models.
- **Provisional Calibration Badge (`⏳`)**: If a player has completed $< 15$ matches and is active within the past year, their profile header displays `⏳ Prior Calibration (X/15)` and an hourglass symbol next to their name.
- **Transparent Match History**: Every match in the Game History table displays its authentic rating delta ($\Delta R$, e.g. `+12.4`, `-8.1`) normally, providing immediate continuous feedback.
- **Historical Trajectory Chart**:
  - Interactive Chart.js graph plotting the player's entire 2017--2026 career evolution.
  - Displays GlickoD*, Glicko-2 Standard, MP-Weighted, and WHR.
- **Recent Matches Table**: Displays the player's tournament games with final placement badges, scores, participants, and replay links.
- **Head-to-Head Records**: Table showing records against the player's top rivals.

---

## 4. FAQ & Model Guide (`/faq`)
- Dedicated comprehensive reference guide with tabbed categories:
  - **Philosophy & Purpose**: The role of predictive rating engines vs. achievement boards, Brier score, ECE, and walk-forward out-of-sample validation.
  - **Gold Standard (DANeo)**: The full-circle journey, retirement of temperature scaling, and $\phi$-multiplayer decomposition.
  - **🔬 15-Game Recalibration**: Eliminating newcomer bleed (1471 vs 1521), transition month splitting, and the dual-criterion recalibration for inactive accounts ($K \in [1, 14]$).
  - **Rating Models**: Mathematical principles of Standard Glicko, MP-Weighted, Adaptive-T, and WHR.
  - **Conservative Rating (C)**: Formula $C = \mu - 3\sigma$ and volatility suppression.
  - **Season Resets**: Continuous vs Softer Season Reset dynamics.
  - **Game Formats**: Strategic differences in 2p, 3p, and 4p games.
  - **Inactivity & Retirement**: The 12-month activity rule and unretirement.
  - **RB48 Deltas**: Time windows and delta badges.
  - **Titles & Badges**: Competitive classification tiers and title standards.

---

## 5. Model Analysis & Subpages (`/analysis`)
- **Subpage Navigation Tabs**:
  - **Overview (`/analysis`)**: Cross-Model Agreement Matrix (Spearman Rank Correlation $\rho$, Pearson Correlation $r$), summary statistics, rating density histograms, and calibration chart preview.
  - **Calibration & Reliability (`/analysis/calibration`)**: Detailed reliability diagram comparing predicted vs observed win rates across 10 probability bins with Brier scores and calibration error.
  - **Top Movers & Divergence (`/analysis/movers`)**: Dedicated analysis of players experiencing the largest rank shifts between models (Standard vs MP-Weighted, Standard vs WHR, MP vs WHR), filterable by format and min games.
  - **Activity & Demographics (`/analysis/activity`)**: Community breakdown of active vs inactive players, match volume by format, title holders, and top 15 participating nations.

---

## 6. Webmaster In-Place Card & Header CMS

The portal provides an in-place Content Management System (CMS) designed for tournament webmasters and community maintainers. It allows immediate text editing, guideline updates, and mathematical documentation adjustments without modifying source code or restarting servers.

### 6.1 Authentication & Privileges
- Webmasters authenticate via the secure admin route: [`/admin/login`](http://127.0.0.1:5050/admin/login).
- Successful login sets `session['is_admin'] = True`, unlocking administrative controls and in-place editing across the entire site.

### 6.2 Visual Inline Triggers (`✎ Edit`)
- When logged in as webmaster, every registered content card (`.cms-card`), descriptive header (`.cms-header`), and footnote block displays an antique gold edit trigger (`✎ Edit`) upon hovering.
- Clicking `✎ Edit` opens the **Universal Webmaster Editor Modal**.

### 6.3 Universal Markdown & KaTeX Math Editor
- **Title Field**: Customize or refine the card/header title.
- **KaTeX Mathematical Protection**: Formulas placed inside inline delimiters (`$...$`) and display block delimiters (`$$...$$`) are automatically shielded from Markdown collisions. Markdown formatting characters (such as underscores `_` in subscripts $r_A - r_B$, asterisks, exponents, and backslashes `\`) are never converted to italics or stripped during compilation.
- **KaTeX Mathematical Toolbar**: Quick-insert buttons for inline math (`$x$`), block equations (`$$...$$`), fractions (`\frac{a}{b}`), Greek symbols ($\phi, \mu, \sigma$), uncertainty parameters ($\mathrm{RD}$), subscripts ($x_i$), and superscripts ($x^2$).
- **Live Math Preview Tab**: Toggle between **✍ Write Markdown** and **👁 Live Math Preview** directly inside the modal to inspect exact KaTeX rendering before committing changes.

### 6.4 Dual Save Modes & Content Storage Architecture
The CMS supports two distinct persistence strategies:

1. **Mode 1: `💾 Save (Overridable)` (Dynamic Database Draft)**:
   - **Where is it stored?**: In the SQLite application database (`data/tta_ratings.db`) inside the `cms_content_blocks` table.
   - **How it works**: Records the raw Markdown, compiled HTML, and timestamp as a database row.
   - **Characteristics**: Instantaneous live DOM update with zero server restart or page refresh needed; can be reverted at any time back to template default via `↺ Revert`.
   
2. **Mode 2: `⚡ Hardcode to HTML` (Permanent Disk Bake-in)**:
   - **Where is it stored?**: Directly in the Jinja2 HTML template file on disk (e.g., `src/web/templates/faq.html`, `leaderboard.html`).
   - **How it works**: Dispatches to `POST /admin/cms/hardcode_block`, which parses the template file on disk and updates the card's default title, default HTML content, and `<template class="cms-default-source">` markup directly.
   - **Characteristics**: The changes become part of the repository source code and git history. Any dynamic database override is automatically cleared because the template file itself is now the official baseline source of truth.

### 6.5 Zero-Downtime Rollback & How to Revert
For any dynamic database override (`💾 Save (Overridable)`), changes can be reverted with a single click:
1. **Directly on the Card**: Whenever a card has an active custom override, an antique-red **`↺ Revert`** button appears right next to `✎ Edit` in the card's action container. Clicking it triggers an instant confirmation prompt and immediately restores the original template code.
2. **Inside the Editor Modal**:
   - When opening a customized card, the modal header displays an active status badge: `⚡ Custom Override Active`.
   - A warning banner alerts the webmaster that an override is active.
   - Clicking the prominent **`↺ Revert to Default`** button in the modal footer deletes the database override via `POST /admin/cms/revert_block` and refreshes the page.
3. **Bulk Reset API**: The endpoint `POST /admin/cms/revert_all` allows webmasters to clear all database overrides in bulk if a global reset to pristine code is ever needed.


### 6.6 Deleting Cards & Restoring Hidden Default Cards
- **One-Click Deletion**:
  - Inside the Universal Webmaster Editor Modal, a prominent red **`🗑 Delete Card`** button is positioned in the footer.
  - Clicking `🗑 Delete Card` prompts for confirmation before dispatching a secure request to `POST /admin/cms/delete_block`.
- **Soft Delete for Template Defaults**:
  - For default system cards defined in templates, deletion safely records `is_deleted = 1` in the database. The card is immediately hidden from public visitors while preserving the underlying source code.
  - Default cards can be unhidden at any time by clicking `↺ Revert to Default` or calling `/admin/cms/restore_block`.
- **Custom Dynamic Cards**:
  - Custom dynamic cards spawned via the CMS are marked deleted and instantly removed from the active DOM.

### 6.7 Adding Custom Dynamic Cards (Above / Below Anchors)
- **Contextual Card Insertion**:
  - To avoid convoluting the UI with floating buttons across the page, insertion controls are embedded directly in the editor header of any existing card: **`➕ Add Above`** and **`➕ Add Below`**.
  - Clicking either button converts the editor into insertion mode, anchoring the new card relative to the current card (`relative_to = <current_key>`, `placement = 'above' | 'below'`).
- **Dynamic Key Generation & Placement**:
  - A unique block key is generated automatically (e.g., `card_custom_<timestamp>`), and the card is marked with `is_custom_card = 1`.
  - The webmaster inputs the card title and body markdown (with optional KaTeX formulas and tables).
- **Instant Live DOM Injection & Persistence**:
  - Upon saving (`POST /admin/cms/save_block`), the new card is dynamically compiled and injected into the DOM adjacent to its anchor.
  - All custom cards persist in SQLite and are restored on subsequent page visits via server-side context processors and client-side initialization (`loadCustomCards()`).

### 6.8 Interactive JavaScript Tables & GFM Markdown Tables
- **GFM Table Support**:
  - Webmasters can compose tables directly in Markdown using standard GitHub Flavored Markdown (GFM) pipe syntax:
    ```markdown
    | Metric | Standard | MP-Weighted | WHR |
    | :--- | :--- | :--- | :--- |
    | Correlation ($\rho$) | 1.000 | 0.942 | 0.891 |
    | Calibration Loss | 0.082 | 0.071 | 0.064 |
    ```
- **Automatic Client-Side Enhancement (`enhanceCmsTables`)**:
  - Any rendered table (Markdown or HTML) within CMS cards is automatically wrapped in a responsive `.cms-table-wrapper` styled with the antique portal theme.
- **Click-to-Sort Headers**:
  - All column headers (`<th>`) receive interactive sort listeners.
  - Clicking a header toggles ascending (`▲`) and descending (`▼`) sort orders.
  - **Type-Aware Sorting**: The engine automatically strips formatting (currency, commas, percentage symbols `%`) to sort numbers numerically, while sorting text lexicographically.

### 6.9 Architectural Safeguard: Mathematical Integrity
- **Strict Separation of Concerns**:
  - **Editable**: Explanatory cards, section headers, guidelines, tour modals, rules explanations, footnotes, and webmaster player notes.
  - **Strictly Immutable / Non-Editable**: All algorithmic ratings, Rating Deviations ($\mathrm{RD}$), win percentages, table outcomes, Brier scores, log-loss metrics, and calibration curve calculations computed by the Glicko-2 and WHR engines.
- This guarantees that administrative convenience never compromises scientific and statistical integrity.


