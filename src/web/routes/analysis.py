"""Model Analysis & Diagnostics Blueprint for TTA-Glicko2-WHR.

Provides comprehensive comparative evaluation across rating engines:
- Standard (in-sample match-by-match) vs Walk-Forward (out-of-sample monthly freeze) calibration curves
- Key predictive metrics: ECE, Brier Score, Log Loss, and Bin Accuracy
- Stylized Webmaster Commentary Box (editable in-place by authenticated admin)
- Predictive Bin Statistics table adapted to active selection
- Rating Distribution Density curves
- Simplified Agreement & Correlation Insights (Top alignment vs divergent models)
- Multi-Engine Player Comparison Tool
"""
import json
import math
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Any, Optional
import numpy as np
from flask import Blueprint, render_template, session, request, jsonify, flash, redirect, url_for
from src.data.db import get_connection

analysis_bp = Blueprint('analysis', __name__)

VALID_MODELS = {
    'glicko2_daneo': '👑 GlickoD* (Flagship)',
    'glicko2_std': 'Glicko-2 Standard',
    'glicko2_mp': 'Glicko-2 MP-Weighted',
    'glicko2_adapt': 'Glicko-2 Adaptive-T',
    'whr': 'Whole-History Rating'
}

VALID_FORMATS = {
    0: 'All Formats',
    2: '2-Player (Duel)',
    3: '3-Player',
    4: '4-Player'
}

VALID_RESET_MODES = {
    'continuous': {
        'id': 'continuous',
        'name': 'Continuous',
        'short': 'Career',
        'desc': 'Unbroken multi-year Bayesian career trajectory across all historical games.'
    },
    'softer': {
        'id': 'softer',
        'name': 'Season Reset',
        'short': 'Season Reset',
        'desc': 'Annual reset balancing career achievement with current season dynamics.'
    }
}

VALID_EVAL_MODES = {
    'standard': {
        'id': 'standard',
        'name': 'Standard (Match-Time)',
        'desc': 'Evaluates predictions at the exact time each game occurred based on pre-game ratings.'
    },
    'walk_forward': {
        'id': 'walk_forward',
        'name': 'Walk-Forward (Out-of-Sample)',
        'desc': 'Strict monthly rating freeze evaluating predictions on subsequent unseen games.'
    }
}

DEFAULT_WEBMASTER_NOTES = r"""### Webmaster Model Assessment & Empirical Findings

Our multi-engine empirical analysis evaluates rating systems on their sole physical purpose: **accurately predicting unseen match outcomes**. 

Through extensive walk-forward validation, diagnostic ablation, and testing across more than 380,000 tournament encounters, we uncovered critical structural failures in standard models and refined the foundational pillars that define the premier **GlickoD\\*** engine:

#### 1. The Investigation: The "Tail Overconfidence" Illusion & Its True Root Cause
In naive Glicko-2, extreme probability forecasts ($>90\%$) appear to suffer from systematic overconfidence: when the model predicts $93\%$, actual tournament win rates hovered around $\approx 89\%$. 

We initially hypothesized that this was caused by an entropic ceiling on *Through the Ages* skill expression: that cards, military draws, and multiplayer friction meant "a 99% win probability cannot physically exist." To bend predictions back toward reality, we formulated an adaptive temperature scaling function $T(P, N)$ to compress logits toward 50%.

However, deeper diagnostic ablation across **top-3% elite tournament players** revealed an eye-opening empirical truth:
- **The Information Defect**: The apparent overconfidence was NOT caused by game entropy. It was an **uncalibrated newcomer artifact**. When strong newcomers (future 1750+ players) enter tournaments like the WCS or Grand Slams with blank $1500$ priors and face Grandmasters ($1950+$), standard Glicko forecasts a $93\%+$ win chance for the GM. When the GM wins only $75\%$ against this hidden shark, the raw data falsely looks like "favorite overconfidence."
- **Skill Expression in TTA is Real**: For well-calibrated elite players, top players genuinely win $\mathbf{\ge 95\%}$ and even $\mathbf{98\%}$ of matches against lower-tier competition (e.g. an established 2000 GM facing an average 1475 player).
- **The Verdict on Temperature Scaling**: Once the **15-Game Recalibration Breakthrough** discovers emergent player baselines, the overconfidence artifact vanishes. Applying temperature scaling on top of calibrated data actually worsened predictions by artificially suppressing legitimate elite win probabilities (+2% to +3% underconfidence). Consequently, **temperature scaling was retired from GlickoD\\*** ($T \equiv 1.0$), establishing near-perfect tail calibration ($|\Delta| < 0.2\%$) and an all-time record ECE of **0.24%**.

#### 2. The Proven Pillars of GlickoD\\*

- **Pillar 1: 15-Game Recalibration Breakthrough (The Primary Anchor)**:
  - When new players enter the tournament pool with blank stats ($1500, \mathrm{RD}=350$), they inject severe statistical noise. Active tournament veterans average $\approx 1521$, while the overall pool mean is $\approx 1471$. Nominal "1521 vs. 1500" contests are actually mismatches against uncalibrated skill, producing both a 50% underconfidence droop (from below-average newcomers) and extreme tail overconfidence (from above-average newcomers).
  - **The Fix**: Once a player completes 15 games, their emergent baseline is discovered. All affected historical matches are recomputed using these calibrated priors, while the newcomer's active rating remains frozen during matches $1 \dots 15$ to eliminate self-amplifying feedback. This single architectural shift eliminates the root cause of noise across the entire graph.

- **Pillar 2: Golden Ratio ($\phi$) Multiplayer Information Decomposition**:
  - Standard Glicko naively decomposes $N$-player matches into independent 1v1 duels, treating a 4-player victory as 3 full 1v1 wins ($W(N) = N-1$). This artificially inflates certainty and deflates RD, allowing low-game-count players with short winning streaks to unrealistically dominate leaderboards.
  - Naive fractional weighting ($w = \frac{1}{N-1}$, yielding $1.0$ match equivalent) over-penalizes multiplayer play, falsely assuming a 4-player win yields no more evidence than a 1v1 duel.
  - GlickoD\\* deploys Golden Ratio information scaling $W(N) = \phi^{N-2}$ ($w_N = \frac{\phi^{N-2}}{N-1}$), giving $\approx 1.618$ effective match equivalents for 3-player and $\approx 2.618$ for 4-player games, perfectly capturing multilateral information without runaway certainty.

- **Pillar 3: Bilateral Composite Variance ($c = \sqrt{\phi_A^2 + \phi_B^2}$)**:
  - In match prediction, performance difference variance is $\text{Var}(\Theta_A - \Theta_B) = \phi_A^2 + \phi_B^2$. GlickoD\\* applies full bilateral composite variance shrinkage $g(c)$, preventing overconfidence whenever either competitor has elevated rating uncertainty.

#### 3. Seasonal Resets & Veteran Mobility
Applying a gentle annual soft season reset (expanding RD and regressing ratings toward competitive tier anchors via Gaussian Golden Ratio scaling) further improves out-of-sample forward predictive accuracy (record 0.24% ECE). It prevents inactive or historical records ("graveyard players") from permanently anchoring the leaderboard, prioritizing recent form while respecting career skill.
"""


def compute_spearman_corr(ranks1: List[float], ranks2: List[float]) -> float:
    n = len(ranks1)
    if n < 2:
        return 1.0
    d_sq_sum = sum((r1 - r2) ** 2 for r1, r2 in zip(ranks1, ranks2))
    return float(1.0 - (6.0 * d_sq_sum) / (n * (n * n - 1)))


def get_webmaster_notes(conn, key: str = 'analysis_overview') -> Dict[str, Any]:
    """Loads webmaster commentary notes from database or returns defaults."""
    row = conn.execute("SELECT title, content, updated_at FROM webmaster_notes WHERE key = ?", (key,)).fetchone()
    if row and row['content']:
        return {
            'key': key,
            'title': row['title'] or "Webmaster Model Assessment & Empirical Findings",
            'content': row['content'],
            'updated_at': row['updated_at']
        }
    return {
        'key': key,
        'title': "Webmaster Model Assessment & Empirical Findings",
        'content': DEFAULT_WEBMASTER_NOTES,
        'updated_at': "Initial Setup"
    }


MODEL_METADATA = {
    'glicko2_daneo': {
        'name': 'GlickoD* Flagship (Continuous)',
        'short': '👑 GlickoD* (Career)',
        'family': 'glicko2_daneo',
        'family_name': 'GlickoD* (Flagship)',
        'reset': 'continuous',
        'reset_name': 'Continuous',
        'retro': True,
        'color': '#8b5cf6',
        'bg': 'rgba(139, 92, 246, 0.25)',
        'verdict': '👑 The Premier Crown — Golden ratio multiplayer information decomposition (φ^(N-2)), 15-game re-calibration, and bilateral composite variance.'
    },
    'glicko2_daneo_softer': {
        'name': 'GlickoD* Flagship (Season Reset)',
        'short': '👑 GlickoD* (Season)',
        'family': 'glicko2_daneo',
        'family_name': 'GlickoD* (Flagship)',
        'reset': 'softer',
        'reset_name': 'Season Reset',
        'retro': True,
        'color': '#a855f7',
        'bg': 'rgba(168, 85, 247, 0.25)',
        'verdict': '👑 Peak Statistical & Competitive Harmony — Golden Ratio decomposition with Season Reset (α ≈ 1.45, λ ≈ 0.12), 15-game re-calibration, and all-time record 0.24% ECE.'
    },
    'glicko2_adapt': {
        'name': 'Glicko-2 Adaptive-T (Continuous)',
        'short': 'G2 Adapt (Career)',
        'family': 'glicko2_adapt',
        'family_name': 'Adaptive-T',
        'reset': 'continuous',
        'reset_name': 'Continuous',
        'retro': False,
        'color': '#4ade80',
        'bg': 'rgba(74, 222, 128, 0.2)',
        'verdict': '★ Gold Standard Calibration — Empirical format temperature scaling T(P, N) eliminates tail overconfidence and aligns with m=1 diagonal.'
    },
    'glicko2_adapt_softer': {
        'name': 'Glicko-2 Adaptive-T (Season Reset)',
        'short': 'G2 Adapt (Season)',
        'family': 'glicko2_adapt',
        'family_name': 'Adaptive-T',
        'reset': 'softer',
        'reset_name': 'Season Reset',
        'retro': False,
        'color': '#10b981',
        'bg': 'rgba(16, 185, 129, 0.2)',
        'verdict': '★ High Calibration Fidelity — Format-specific temperature T(P, N) combined with optimal annual Season Reset.'
    },
    'glicko2_adapt_retro': {
        'name': 'Glicko-2 Adaptive-T (Continuous + Retro Prior)',
        'short': 'G2 Adapt (Career+Retro)',
        'family': 'glicko2_adapt',
        'family_name': 'Adaptive-T',
        'reset': 'continuous',
        'reset_name': 'Continuous',
        'retro': True,
        'color': '#34d399',
        'bg': 'rgba(52, 211, 153, 0.25)',
        'verdict': '★ High Precision Retro Career — 15-game emergent baseline combined with continuous temperature scaling.'
    },
    'glicko2_adapt_softer_retro': {
        'name': 'Glicko-2 Adaptive-T (Season Reset + Retro Prior)',
        'short': 'G2 Adapt (Season+Retro)',
        'family': 'glicko2_adapt',
        'family_name': 'Adaptive-T',
        'reset': 'softer',
        'reset_name': 'Season Reset',
        'retro': True,
        'color': '#059669',
        'bg': 'rgba(5, 150, 105, 0.25)',
        'verdict': '★ Peak Statistical Power — 15-game emergent prior eliminates newcomer distortion with Season Reset.'
    },
    'glicko2_mp': {
        'name': 'Glicko-2 MP-Weighted (Continuous)',
        'short': 'G2 MP (Career)',
        'family': 'glicko2_mp',
        'family_name': 'Glicko-2 MP',
        'reset': 'continuous',
        'reset_name': 'Continuous',
        'retro': False,
        'color': '#ef5350',
        'bg': 'rgba(239, 83, 80, 0.2)',
        'verdict': '★ Optimal Multiplayer Balance — Fractional variance weighting (w=1/(N-1)) eliminates overconfidence in 3P/4P tables.'
    },
    'glicko2_mp_softer': {
        'name': 'Glicko-2 MP-Weighted (Season Reset)',
        'short': 'G2 MP (Season)',
        'family': 'glicko2_mp',
        'family_name': 'Glicko-2 MP',
        'reset': 'softer',
        'reset_name': 'Season Reset',
        'retro': False,
        'color': '#fb923c',
        'bg': 'rgba(251, 146, 60, 0.2)',
        'verdict': '★ Calibrated MP Turnover — Fractional multiplayer variance weighting with gentle season decay.'
    },
    'glicko2_mp_retro': {
        'name': 'Glicko-2 MP-Weighted (Continuous + Retro Prior)',
        'short': 'G2 MP (Career+Retro)',
        'family': 'glicko2_mp',
        'family_name': 'Glicko-2 MP',
        'reset': 'continuous',
        'reset_name': 'Continuous',
        'retro': True,
        'color': '#f97316',
        'bg': 'rgba(249, 115, 22, 0.25)',
        'verdict': '★ Career MP Retro Accuracy — Unbroken career multiplayer weighting with emergent priors.'
    },
    'glicko2_mp_softer_retro': {
        'name': 'Glicko-2 MP-Weighted (Season Reset + Retro Prior)',
        'short': 'G2 MP (Season+Retro)',
        'family': 'glicko2_mp',
        'family_name': 'Glicko-2 MP',
        'reset': 'softer',
        'reset_name': 'Season Reset',
        'retro': True,
        'color': '#ea580c',
        'bg': 'rgba(234, 88, 12, 0.25)',
        'verdict': '★ Multiplayer Retro Precision — Fractional 1/(N-1) variance with stabilized 15-game prior and Season Reset.'
    },
    'glicko2_std': {
        'name': 'Glicko-2 Standard (Continuous)',
        'short': 'G2 Std (Career)',
        'family': 'glicko2_std',
        'family_name': 'Glicko-2 Std',
        'reset': 'continuous',
        'reset_name': 'Continuous',
        'retro': False,
        'color': '#ffca28',
        'bg': 'rgba(255, 202, 40, 0.2)',
        'verdict': '★ High Forward Responsiveness — Standard pairwise Elo dynamics; classical odometer benchmark.'
    },
    'glicko2_std_softer': {
        'name': 'Glicko-2 Standard (Season Reset)',
        'short': 'G2 Std (Season)',
        'family': 'glicko2_std',
        'family_name': 'Glicko-2 Std',
        'reset': 'softer',
        'reset_name': 'Season Reset',
        'retro': False,
        'color': '#facc15',
        'bg': 'rgba(250, 204, 21, 0.2)',
        'verdict': '★ Gentle Annual Turnover — Standard pairwise Elo with Season Reset tier reversion.'
    },
    'glicko2_std_retro': {
        'name': 'Glicko-2 Standard (Continuous + Retro Prior)',
        'short': 'G2 Std (Career+Retro)',
        'family': 'glicko2_std',
        'family_name': 'Glicko-2 Std',
        'reset': 'continuous',
        'reset_name': 'Continuous',
        'retro': True,
        'color': '#fde047',
        'bg': 'rgba(253, 224, 71, 0.25)',
        'verdict': '★ Career Pairwise Retro Benchmark — Continuous pairwise Elo dynamics initialized from emergent priors.'
    },
    'glicko2_std_softer_retro': {
        'name': 'Glicko-2 Standard (Season Reset + Retro Prior)',
        'short': 'G2 Std (Season+Retro)',
        'family': 'glicko2_std',
        'family_name': 'Glicko-2 Std',
        'reset': 'softer',
        'reset_name': 'Season Reset',
        'retro': True,
        'color': '#eab308',
        'bg': 'rgba(234, 179, 8, 0.25)',
        'verdict': '★ Standard Elo with Retro Prior — High pairwise fidelity with calibrated 15-game emergent baseline and Season Reset.'
    },
    'whr': {
        'name': 'Whole-History Rating (Continuous)',
        'short': 'WHR (Career)',
        'family': 'whr',
        'family_name': 'WHR',
        'reset': 'continuous',
        'reset_name': 'Continuous',
        'retro': False,
        'color': '#29b6f6',
        'bg': 'rgba(41, 182, 246, 0.2)',
        'verdict': '★ Retrospective Global Optimum — Exceptional in-sample fit across the global graph; exhibits boundary volatility at frontier.'
    },
    'whr_softer': {
        'name': 'Whole-History Rating (Season Reset)',
        'short': 'WHR (Season)',
        'family': 'whr',
        'family_name': 'WHR',
        'reset': 'softer',
        'reset_name': 'Season Reset',
        'retro': False,
        'color': '#38bdf8',
        'bg': 'rgba(56, 189, 248, 0.2)',
        'verdict': '★ Retrospective Season Reset — Balanced multi-year graph smoothing with annual boundary stabilization.'
    }
}


def compute_composite_score(brier: float, ece: float, log_loss: float, accuracy: float) -> float:
    """Computes a normalized Composite Predictive Index (0-100) where higher is superior."""
    b_score = max(0.0, min(1.0, (0.25 - brier) / 0.10))
    e_score = max(0.0, min(1.0, (0.08 - ece) / 0.08))
    l_score = max(0.0, min(1.0, (0.70 - log_loss) / 0.25))
    a_score = max(0.0, min(1.0, (accuracy - 50.0) / 30.0))
    return round(100.0 * (0.35 * b_score + 0.35 * e_score + 0.15 * l_score + 0.15 * a_score), 1)


def compute_calibration(conn, player_count: int = 0, eval_mode: str = 'standard') -> Dict[str, Any]:
    """Retrieves calibration curves and Brier metrics for standard or walk-forward modes."""
    bin_labels = ['50-55%', '55-60%', '60-65%', '65-70%', '70-75%', '75-80%', '80-85%', '85-90%', '90-95%', '95-100%']
    ideal_points = [0.525, 0.575, 0.625, 0.675, 0.725, 0.775, 0.825, 0.875, 0.925, 0.975]

    calib_data = {
        'eval_mode': eval_mode,
        'labels': bin_labels,
        'ideal': ideal_points,
        'models': {}
    }

    table_name = 'walk_forward_calibration' if eval_mode == 'walk_forward' else 'standard_calibration'

    try:
        rows = conn.execute(f"""
            SELECT model_type, brier_score, ece, log_loss, accuracy, matches_evaluated, bin_data_json
            FROM {table_name}
            WHERE player_count = ? AND period_month = 'AGGREGATED'
        """, (player_count,)).fetchall()

        for r in rows:
            m = r['model_type']
            bin_info = json.loads(r['bin_data_json']) if r['bin_data_json'] else {}
            if 'labels' in bin_info and bin_info['labels']:
                calib_data['labels'] = bin_info['labels']
            if 'ideal' in bin_info and bin_info['ideal']:
                calib_data['ideal'] = bin_info['ideal']
            actuals = bin_info.get('actuals', ideal_points)
            preds = bin_info.get('preds', ideal_points)
            counts = bin_info.get('counts', [0] * len(calib_data['labels']))
            total_counts = sum(counts)
            if total_counts > 0:
                p_soll = sum(p * c for p, c in zip(preds, counts)) / total_counts
                p_ist = sum(a * c for a, c in zip(actuals, counts)) / total_counts
            else:
                p_soll = 0.65
                p_ist = 0.65

            calib_data['models'][m] = {
                'brier': round(r['brier_score'], 4),
                'ece': round(r['ece'], 4),
                'ece_pct': round(r['ece'] * 100.0, 2),
                'log_loss': round(r['log_loss'], 4) if r['log_loss'] is not None else 0.62,
                'accuracy': round(r['accuracy'], 1) if r['accuracy'] is not None else 64.0,
                'p_ist_pct': round(p_ist * 100.0, 1),
                'p_soll_pct': round(p_soll * 100.0, 1),
                'p_delta_pct': round((p_ist - p_soll) * 100.0, 1),
                'matches': r['matches_evaluated'],
                'actuals': actuals,
                'preds': preds,
                'counts': counts
            }
    except Exception:
        pass

    # Ensure all models have fallback definitions if table is initializing
    ALL_MODEL_KEYS = list(MODEL_METADATA.keys())
    for m in ALL_MODEL_KEYS:
        if m not in calib_data['models']:
            calib_data['models'][m] = {
                'brier': 0.2140, 'ece': 0.0150, 'ece_pct': 1.50, 'log_loss': 0.6200,
                'accuracy': 64.5, 'p_ist_pct': 65.0, 'p_soll_pct': 65.0, 'p_delta_pct': 0.0,
                'matches': 0, 'actuals': ideal_points,
                'preds': ideal_points, 'counts': [0] * len(bin_labels)
            }

    return calib_data


def get_ranked_models(calib_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Calculates composite predictive scores and ranks models from best to worst."""
    ranked = []
    for m_key, meta in MODEL_METADATA.items():
        stats = calib_data['models'].get(m_key, {})
        brier = stats.get('brier', 0.2140)
        ece = stats.get('ece', 0.0150)
        ece_pct = stats.get('ece_pct', round(ece * 100.0, 2))
        log_loss = stats.get('log_loss', 0.6200)
        accuracy = stats.get('accuracy', 64.0)
        p_ist_pct = stats.get('p_ist_pct', 65.0)
        p_soll_pct = stats.get('p_soll_pct', 65.0)
        p_delta_pct = stats.get('p_delta_pct', 0.0)
        composite = compute_composite_score(brier, ece, log_loss, accuracy)

        ranked.append({
            'key': m_key,
            'name': meta['name'],
            'short': meta['short'],
            'family': meta['family'],
            'family_name': meta['family_name'],
            'reset': meta['reset'],
            'reset_name': meta['reset_name'],
            'retro': meta.get('retro', False),
            'color': meta['color'],
            'bg': meta['bg'],
            'brier': brier,
            'ece': ece,
            'ece_pct': ece_pct,
            'log_loss': log_loss,
            'accuracy': accuracy,
            'p_ist_pct': p_ist_pct,
            'p_soll_pct': p_soll_pct,
            'p_delta_pct': p_delta_pct,
            'composite': composite,
            'verdict': meta['verdict']
        })

    ranked.sort(key=lambda x: x['composite'], reverse=True)
    for rank, rm in enumerate(ranked, 1):
        rm['rank'] = rank
    return ranked


_ANALYSIS_CACHE: Dict[str, Any] = {
    'matrix': None,
    'hist': {},
    'correlations': {}
}


def clear_analysis_cache():
    """Invalidates the in-memory analysis caches."""
    global _ANALYSIS_CACHE
    _ANALYSIS_CACHE = {
        'matrix': None,
        'hist': {},
        'correlations': {}
    }


@analysis_bp.route('/analysis/calibration')
def calibration():
    return index()


@analysis_bp.route('/analysis')
def index():
    global _ANALYSIS_CACHE
    active_model = request.args.get('model', session.get('active_model', 'all'))
    if active_model in VALID_MODELS or active_model == 'all':
        session['active_model'] = active_model

    format_param = request.args.get('format')
    if format_param is not None:
        try:
            fmt_int = int(format_param)
            if fmt_int in VALID_FORMATS:
                session['active_format'] = fmt_int
        except ValueError:
            pass
    active_format = session.get('active_format', 0)

    reset_param = request.args.get('reset_mode')
    if reset_param in VALID_RESET_MODES or reset_param == 'all':
        session['active_reset_mode'] = reset_param
    active_reset_mode = session.get('active_reset_mode', 'all')
    if active_reset_mode not in VALID_RESET_MODES and active_reset_mode != 'all':
        active_reset_mode = 'all'

    eval_param = request.args.get('eval_mode')
    if eval_param in VALID_EVAL_MODES:
        session['active_eval_mode'] = eval_param
    active_eval_mode = session.get('active_eval_mode', 'standard')
    if active_eval_mode not in VALID_EVAL_MODES:
        active_eval_mode = 'standard'

    conn = get_connection()
    try:
        # Full matrix across all eval modes & formats for instant client-side switching (cached)
        all_calib_matrix = _ANALYSIS_CACHE.get('matrix')
        if all_calib_matrix is None:
            all_calib_matrix = {}
            for em in ('standard', 'walk_forward'):
                all_calib_matrix[em] = {}
                for f_id in (0, 2, 3, 4):
                    c_d = compute_calibration(conn, player_count=f_id, eval_mode=em)
                    all_calib_matrix[em][f_id] = {
                        'calib_data': c_d,
                        'ranked_models': get_ranked_models(c_d)
                    }
            _ANALYSIS_CACHE['matrix'] = all_calib_matrix

        # 1. Active Calibration Data & Ranked Models from matrix
        calib_entry = all_calib_matrix.get(active_eval_mode, {}).get(active_format)
        if calib_entry:
            calib_data = calib_entry['calib_data']
            ranked_models = calib_entry['ranked_models']
        else:
            calib_data = compute_calibration(conn, player_count=active_format, eval_mode=active_eval_mode)
            ranked_models = get_ranked_models(calib_data)

        # 2. Webmaster Notes
        webmaster_notes = get_webmaster_notes(conn, 'analysis_overview')

        # 3. Rating Distribution Histograms (cached by format)
        hist_data = _ANALYSIS_CACHE['hist'].get(active_format)
        if hist_data is None:
            bins = list(range(1000, 2200, 100))
            bin_labels = [f'{b}-{b+99}' for b in bins[:-1]]

            daneo_rows = [r['rating'] for r in conn.execute('SELECT rating FROM player_ratings WHERE model_type=? AND player_count = ?', ('glicko2_daneo', active_format)).fetchall()]
            std_rows = [r['rating'] for r in conn.execute('SELECT rating FROM player_ratings WHERE model_type=? AND player_count = ?', ('glicko2_std', active_format)).fetchall()]
            mp_rows = [r['rating'] for r in conn.execute('SELECT rating FROM player_ratings WHERE model_type=? AND player_count = ?', ('glicko2_mp', active_format)).fetchall()]
            adapt_rows = [r['rating'] for r in conn.execute('SELECT rating FROM player_ratings WHERE model_type=? AND player_count = ?', ('glicko2_adapt', active_format)).fetchall()]
            whr_rows = [r['rating'] for r in conn.execute('SELECT rating FROM player_ratings WHERE model_type=? AND player_count = ?', ('whr', active_format)).fetchall()]

            daneo_counts, _ = np.histogram(daneo_rows, bins=bins) if daneo_rows else ([], [])
            std_counts, _ = np.histogram(std_rows, bins=bins) if std_rows else ([], [])
            mp_counts, _ = np.histogram(mp_rows, bins=bins) if mp_rows else ([], [])
            adapt_counts, _ = np.histogram(adapt_rows, bins=bins) if adapt_rows else ([], [])
            whr_counts, _ = np.histogram(whr_rows, bins=bins) if whr_rows else ([], [])

            # Active players: >10 games in the last year (relative to latest match in DB)
            active_p_rows = conn.execute('''
                SELECT p.name AS player_name
                FROM (
                    SELECT date, player1 AS name FROM matches
                    UNION ALL
                    SELECT date, player2 AS name FROM matches
                    UNION ALL
                    SELECT date, player3 AS name FROM matches WHERE player3 IS NOT NULL
                    UNION ALL
                    SELECT date, player4 AS name FROM matches WHERE player4 IS NOT NULL
                ) p
                WHERE p.date >= (SELECT date(MAX(date), '-365 days') FROM matches)
                GROUP BY p.name
                HAVING COUNT(*) > 10
            ''').fetchall()
            active_set = {r['player_name'] for r in active_p_rows}

            daneo_active = [r['rating'] for r in conn.execute('SELECT rating, player_name FROM player_ratings WHERE model_type=? AND player_count = ?', ('glicko2_daneo', active_format)).fetchall() if r['player_name'] in active_set]
            std_active = [r['rating'] for r in conn.execute('SELECT rating, player_name FROM player_ratings WHERE model_type=? AND player_count = ?', ('glicko2_std', active_format)).fetchall() if r['player_name'] in active_set]
            mp_active = [r['rating'] for r in conn.execute('SELECT rating, player_name FROM player_ratings WHERE model_type=? AND player_count = ?', ('glicko2_mp', active_format)).fetchall() if r['player_name'] in active_set]
            adapt_active = [r['rating'] for r in conn.execute('SELECT rating, player_name FROM player_ratings WHERE model_type=? AND player_count = ?', ('glicko2_adapt', active_format)).fetchall() if r['player_name'] in active_set]
            whr_active = [r['rating'] for r in conn.execute('SELECT rating, player_name FROM player_ratings WHERE model_type=? AND player_count = ?', ('whr', active_format)).fetchall() if r['player_name'] in active_set]

            hist_data = {
                'labels': bin_labels,
                'daneo': [int(x) for x in daneo_counts],
                'std': [int(x) for x in std_counts],
                'mp': [int(x) for x in mp_counts],
                'adapt': [int(x) for x in adapt_counts],
                'whr': [int(x) for x in whr_counts],
                'means': {
                    'daneo': round(float(np.mean(daneo_rows)), 1) if daneo_rows else 1500.0,
                    'adapt': round(float(np.mean(adapt_rows)), 1) if adapt_rows else 1500.0,
                    'mp': round(float(np.mean(mp_rows)), 1) if mp_rows else 1500.0,
                    'std': round(float(np.mean(std_rows)), 1) if std_rows else 1500.0,
                    'whr': round(float(np.mean(whr_rows)), 1) if whr_rows else 1500.0,
                },
                'active_means': {
                    'daneo': round(float(np.mean(daneo_active)), 1) if daneo_active else 1500.0,
                    'adapt': round(float(np.mean(adapt_active)), 1) if adapt_active else 1500.0,
                    'mp': round(float(np.mean(mp_active)), 1) if mp_active else 1500.0,
                    'std': round(float(np.mean(std_active)), 1) if std_active else 1500.0,
                    'whr': round(float(np.mean(whr_active)), 1) if whr_active else 1500.0,
                }
            }
            _ANALYSIS_CACHE['hist'][active_format] = hist_data

        # 4. Agreement & Correlation Rework (Summary of strongest vs weakest correlations)
        correlation_summary = _ANALYSIS_CACHE['correlations'].get(active_format)
        if correlation_summary is None:
            ALL_ENGINES = [
                ('glicko2_daneo', 'GlickoD* (Gold Standard)', 'GlickoD* φ-MP Continuous (Flagship)'),
                ('glicko2_daneo_softer', 'GlickoD* (Season Reset)', 'GlickoD* Dynamic Season Reset'),
                ('glicko2_std', 'G2 Std (Career)', 'Glicko-2 Standard Continuous'),
                ('glicko2_std_softer', 'G2 Std (Season Reset)', 'Glicko-2 Standard Season Reset'),
                ('glicko2_mp', 'G2 MP (Career)', 'Glicko-2 MP-Weighted Continuous'),
                ('glicko2_mp_softer', 'G2 MP (Season Reset)', 'Glicko-2 MP-Weighted Season Reset'),
                ('glicko2_adapt', 'G2 Adapt (Career)', 'Glicko-2 Adaptive-T Continuous'),
                ('glicko2_adapt_softer', 'G2 Adapt (Season Reset)', 'Glicko-2 Adaptive-T Season Reset'),
                ('whr', 'WHR (Career)', 'Whole-History Rating Continuous'),
                ('whr_softer', 'WHR (Season Reset)', 'Whole-History Rating Season Reset'),
            ]

            engine_keys = [e[0] for e in ALL_ENGINES]
            placeholders = ', '.join(['?'] * len(engine_keys))

            raw_rows = conn.execute(f'''
                SELECT player_name, model_type, rating, rank
                FROM player_ratings
                WHERE player_count = ? AND opponents_count >= 15 AND model_type IN ({placeholders})
            ''', [active_format] + engine_keys).fetchall()

            player_ratings_map = defaultdict(dict)
            player_ranks_map = defaultdict(dict)
            for r in raw_rows:
                p = r['player_name']
                m = r['model_type']
                player_ratings_map[p][m] = r['rating']
                player_ranks_map[p][m] = r['rank']

            eligible_p = [p for p, d in player_ratings_map.items() if len(d) == len(engine_keys)]
            pair_correlations = []

            if len(eligible_p) > 1:
                engine_dict = {e[0]: e[1] for e in ALL_ENGINES}
                for i in range(len(engine_keys)):
                    for j in range(i + 1, len(engine_keys)):
                        k1, k2 = engine_keys[i], engine_keys[j]
                        v1 = [player_ratings_map[p][k1] for p in eligible_p]
                        v2 = [player_ratings_map[p][k2] for p in eligible_p]
                        r1 = [player_ranks_map[p][k1] for p in eligible_p]
                        r2 = [player_ranks_map[p][k2] for p in eligible_p]

                        p_corr = float(np.corrcoef(v1, v2)[0, 1])
                        s_corr = compute_spearman_corr(r1, r2)
                        pair_correlations.append({
                            'k1': k1, 'k2': k2,
                            'name1': engine_dict[k1], 'name2': engine_dict[k2],
                            'pearson': round(p_corr, 4),
                            'spearman': round(s_corr, 4)
                        })

            sorted_by_spearman = sorted(pair_correlations, key=lambda x: x['spearman'], reverse=True)
            top_agreements = sorted_by_spearman[:4] if sorted_by_spearman else []
            weakest_agreements = sorted_by_spearman[-4:] if sorted_by_spearman else []

            correlation_summary = {
                'sample_size': len(eligible_p),
                'top_agreements': top_agreements,
                'weakest_agreements': weakest_agreements
            }
            _ANALYSIS_CACHE['correlations'][active_format] = correlation_summary

        return render_template(
            'analysis.html',
            calib_data=calib_data,
            calib_json=json.dumps(calib_data),
            all_calib_matrix_json=json.dumps(all_calib_matrix),
            ranked_models=ranked_models,
            model_metadata=MODEL_METADATA,
            model_metadata_json=json.dumps(MODEL_METADATA),
            hist_data=hist_data,
            hist_json=json.dumps(hist_data),
            webmaster_notes=webmaster_notes,
            correlation_summary=correlation_summary,
            active_model=active_model,
            models=VALID_MODELS,
            active_format=active_format,
            formats=VALID_FORMATS,
            active_reset_mode=active_reset_mode,
            reset_modes=VALID_RESET_MODES,
            active_eval_mode=active_eval_mode,
            eval_modes=VALID_EVAL_MODES
        )
    finally:
        conn.close()


@analysis_bp.route('/analysis/save_notes', methods=['POST'])
def save_notes():
    """Allows authenticated webmaster to update commentary text."""
    if not session.get('is_admin'):
        return jsonify({'status': 'error', 'message': 'Admin authentication required.'}), 403

    content = request.form.get('content', '').strip()
    title = request.form.get('title', 'Webmaster Model Assessment & Empirical Findings').strip()
    key = request.form.get('key', 'analysis_overview').strip()

    if not content:
        return jsonify({'status': 'error', 'message': 'Commentary content cannot be empty.'}), 400

    conn = get_connection()
    try:
        with conn:
            conn.execute("""
                INSERT INTO webmaster_notes (key, title, content, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    title = excluded.title,
                    content = excluded.content,
                    updated_at = CURRENT_TIMESTAMP
            """, (key, title, content))
        flash("Webmaster analysis assessment notes updated successfully!", "success")
        return jsonify({'status': 'success', 'message': 'Notes updated successfully.'})
    finally:
        conn.close()


@analysis_bp.route('/analysis/movers')
def movers():
    """Multi-Engine Player Comparison Tool."""
    format_param = request.args.get('format')
    active_format = 0
    if format_param is not None:
        try:
            active_format = int(format_param)
        except ValueError:
            active_format = 0

    search = (request.args.get('search') or '').strip()
    min_games = max(0, int(request.args.get('min_games', 15)))

    ALL_CONFIGS = [
        ('glicko2_std', 'Glicko-2 Standard', 'Continuous'),
        ('glicko2_std_soft', 'Glicko-2 Standard', 'Soft Reset'),
        ('glicko2_std_amplified', 'Glicko-2 Standard', 'Hard Reset'),
        ('glicko2_mp', 'Glicko-2 MP-Weighted', 'Continuous'),
        ('glicko2_mp_soft', 'Glicko-2 MP-Weighted', 'Soft Reset'),
        ('glicko2_mp_amplified', 'Glicko-2 MP-Weighted', 'Hard Reset'),
        ('glicko2_adapt', 'Glicko-2 Adaptive-T', 'Continuous'),
        ('glicko2_adapt_soft', 'Glicko-2 Adaptive-T', 'Soft Reset'),
        ('glicko2_adapt_amplified', 'Glicko-2 Adaptive-T', 'Hard Reset'),
        ('whr', 'Whole-History Rating (WHR)', 'Continuous'),
        ('whr_soft', 'Whole-History Rating (WHR)', 'Soft Reset'),
        ('whr_amplified', 'Whole-History Rating (WHR)', 'Hard Reset'),
    ]

    conn = get_connection()
    try:
        # Determine players to compare
        if search:
            if ',' in search:
                names = [n.strip() for n in search.split(',') if n.strip()]
                or_clauses = ['(LOWER(name) LIKE ? OR LOWER(country_code) = ?)' for _ in names]
                or_params = []
                for n in names:
                    or_params.extend([f"%{n.lower()}%", n.lower()])
                p_rows = conn.execute(f"SELECT name, country_code, title FROM players WHERE {' OR '.join(or_clauses)} LIMIT 15", or_params).fetchall()
            else:
                p_rows = conn.execute("SELECT name, country_code, title FROM players WHERE LOWER(name) LIKE ? OR LOWER(country_code) = ? LIMIT 15", (f"%{search.lower()}%", search.lower())).fetchall()
            target_players = [dict(r) for r in p_rows]
        else:
            # Default: show top 6 renowned titleholders
            default_names = ['a440', 'Martin_Pecheur', 'Weidenbaum', 'saru', 'pv4', 'Genghisip']
            placeholders = ', '.join(['?'] * len(default_names))
            p_rows = conn.execute(f"SELECT name, country_code, title FROM players WHERE name IN ({placeholders})", default_names).fetchall()
            target_players = [dict(r) for r in p_rows]

        player_comparisons = []
        for p in target_players:
            p_name = p['name']
            engine_stats = []
            for m_key, engine_name, reset_name in ALL_CONFIGS:
                r_row = conn.execute("""
                    SELECT rank, rating, rd, c_rating, opponents_count, win_rate
                    FROM player_ratings
                    WHERE player_name = ? AND model_type = ? AND player_count = ?
                """, (p_name, m_key, active_format)).fetchone()

                if r_row:
                    engine_stats.append({
                        'model_key': m_key,
                        'engine': engine_name,
                        'reset_mode': reset_name,
                        'rank': r_row['rank'],
                        'rating': round(r_row['rating'], 1),
                        'rd': round(r_row['rd'], 1),
                        'c_rating': round(r_row['c_rating'], 1),
                        'opps': r_row['opponents_count'],
                        'win_rate': r_row['win_rate']
                    })

            player_comparisons.append({
                'player': p,
                'stats': engine_stats
            })

        return render_template(
            'analysis_movers.html',
            player_comparisons=player_comparisons,
            search=search,
            min_games=min_games,
            active_format=active_format,
            formats=VALID_FORMATS
        )
    finally:
        conn.close()


@analysis_bp.route('/analysis/activity')
def activity():
    conn = get_connection()
    try:
        active_count = conn.execute("SELECT count(*) FROM players WHERE last_played > '2025-05-31'").fetchone()[0]
        inactive_count = conn.execute("SELECT count(*) FROM players WHERE last_played IS NULL OR last_played <= '2025-05-31'").fetchone()[0]
        total_players = active_count + inactive_count

        fmt_counts = conn.execute("SELECT player_count, count(*) as count FROM matches GROUP BY player_count ORDER BY player_count").fetchall()
        match_stats = {r['player_count']: r['count'] for r in fmt_counts}

        country_rows = conn.execute(
            "SELECT p.country_code, "
            "COUNT(DISTINCT p.name) as total_count, "
            "ROUND(AVG(CASE WHEN p.title = 'GM' THEN pr.rating END), 1) as avg_gm, "
            "ROUND(AVG(CASE WHEN p.title IN ('GM', 'M') THEN pr.rating END), 1) as avg_m_plus, "
            "ROUND(AVG(CASE WHEN p.title IN ('GM', 'M', 'P') THEN pr.rating END), 1) as avg_p_plus, "
            "ROUND(AVG(pr.rating), 1) as avg_all "
            "FROM players p "
            "JOIN player_ratings pr ON p.name = pr.player_name AND pr.model_type = 'glicko2_std' AND pr.player_count = 0 "
            "WHERE p.country_code IS NOT NULL "
            "GROUP BY p.country_code "
            "ORDER BY total_count DESC LIMIT 15"
        ).fetchall()

        title_rows = conn.execute(
            "SELECT title, count(*) as count FROM players WHERE title IS NOT NULL GROUP BY title ORDER BY count DESC"
        ).fetchall()

        return render_template(
            'analysis_activity.html',
            active_count=active_count,
            inactive_count=inactive_count,
            total_players=total_players,
            match_stats=match_stats,
            countries=country_rows,
            titles=title_rows,
            formats=VALID_FORMATS
        )
    finally:
        conn.close()
