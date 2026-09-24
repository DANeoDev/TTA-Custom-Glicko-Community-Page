"""Community Leaderboard routes displaying the official standard tournament rankings across seasons."""
import json
import sqlite3
import math
from flask import Blueprint, render_template, request, current_app
from src.data.db import get_connection

bp = Blueprint('community', __name__)

AVAILABLE_EDITIONS = {
    '2026': {
        'id': '2026',
        'name': '2026 (Rolling Q2)',
        'title': 'Official Community Leaderboard &bull; Q2 2026 Cycle',
        'short': '2026 Q2',
        'badge': '⭐ Current Rolling',
        'year': 2026,
        'wc': 'a440',
        'wc_desc': 'Reigning World Champion (2025)'
    },
    '2025': {
        'id': '2025',
        'name': '2025 Final Archive',
        'title': 'Season 2025 Official Community Leaderboard Final Archive',
        'short': '2025 Final',
        'badge': '🏆 2025 Final',
        'year': 2025,
        'wc': 'a440',
        'wc_desc': 'World Champion 2025'
    },
    '2024': {
        'id': '2024',
        'name': '2024 Final Archive',
        'title': 'Season 2024 Official Community Leaderboard Final Archive',
        'short': '2024 Final',
        'badge': '📜 2024 Final',
        'year': 2024,
        'wc': 'Martin_Pecheur',
        'wc_desc': 'World Champion 2024'
    },
    'race26': {
        'id': 'race26',
        'name': '2026 Race Tracker',
        'title': 'Season 2026 Points Race Tracker (Race 26)',
        'short': 'Race 26',
        'badge': '🏁 2026 Race',
        'year': 2026,
        'wc': 'a440',
        'wc_desc': 'Reigning World Champion'
    }
}


def get_edition_structure(edition: str):
    """Returns tournament categories and tournament summaries calibrated to the specific leaderboard edition."""
    if edition == '2025':
        categories = [
            {
                'category': 'World Championship',
                'badge_class': 'badge-wc',
                'columns': [
                    {'id': 'wrld', 'name': 'World Championship', 'short': 'Worlds', 'max_pts': 2500, 'desc': 'World Championship (won by a440)'}
                ]
            },
            {
                'category': 'International Championship (4-Player League)',
                'badge_class': 'badge-gm',
                'columns': [
                    {'id': 'ic_28', 'name': 'International Season 28', 'short': 'IC 28', 'max_pts': 1000},
                    {'id': 'ic_29', 'name': 'International Season 29', 'short': 'IC 29', 'max_pts': 1000},
                    {'id': 'ic_30', 'name': 'International Season 30', 'short': 'IC 30', 'max_pts': 1000},
                    {'id': 'ic_31', 'name': 'International Season 31', 'short': 'IC 31', 'max_pts': 1000},
                ]
            },
            {
                'category': 'Intermezzo Championship (3-Player League)',
                'badge_class': 'badge-m',
                'columns': [
                    {'id': 'im_25', 'name': 'Intermezzo Season 25', 'short': 'IM 25', 'max_pts': 1000},
                    {'id': 'im_26', 'name': 'Intermezzo Season 26', 'short': 'IM 26', 'max_pts': 1000},
                    {'id': 'im_27', 'name': 'Intermezzo Season 27', 'short': 'IM 27', 'max_pts': 1000},
                    {'id': 'im_28', 'name': 'Intermezzo Season 28', 'short': 'IM 28', 'max_pts': 1000},
                ]
            },
            {
                'category': 'Royal League',
                'badge_class': 'badge-p',
                'columns': [
                    {'id': 'rl_03', 'name': 'Royal League Season 3', 'short': 'RL 03', 'max_pts': 1000},
                    {'id': 'rl_04', 'name': 'Royal League Season 4', 'short': 'RL 04', 'max_pts': 1000},
                    {'id': 'rl_05', 'name': 'Royal League Season 5', 'short': 'RL 05', 'max_pts': 1000},
                    {'id': 'rl_06', 'name': 'Royal League Season 6', 'short': 'RL 06', 'max_pts': 1000},
                ]
            },
            {
                'category': 'Grand Slams & Major Opens',
                'badge_class': 'badge-g',
                'columns': [
                    {'id': 'wmbl', 'name': 'Wimbledon Open', 'short': 'Wimbledon', 'max_pts': 1000},
                    {'id': 'aus', 'name': 'Australian Open', 'short': 'Aussie Open', 'max_pts': 1000},
                ]
            },
            {
                'category': 'Competitive Ladders',
                'badge_class': 'badge-rank',
                'columns': [
                    {'id': 'sl', 'name': 'Sodium Ladder', 'short': 'Sodium', 'max_pts': 1000},
                    {'id': 'ml', 'name': 'Mercurial Ladder', 'short': 'Mercurial', 'max_pts': 1000},
                ]
            },
            {
                'category': 'Invitational & Gala Cups',
                'badge_class': 'badge-rank',
                'columns': [
                    {'id': 'eif', 'name': 'Eiffel Tower Cup', 'short': 'Eiffel', 'max_pts': 1000},
                    {'id': 'qd', 'name': 'Quick & Dirty (Swiss)', 'short': 'Q&D', 'max_pts': 600},
                    {'id': 'ldrb', 'name': 'Leaderboard Trophy', 'short': 'Trophy', 'max_pts': 1000},
                ]
            }
        ]
        tournaments_summary = [
            {'id': 'wrld', 'name': 'World Championship', 'short': 'Worlds', 'cols': ['wrld'], 'max_pts': 2500, 'badge_class': 'badge-wc', 'desc': 'World Championship'},
            {'id': 'ic', 'name': 'International (4P)', 'short': 'International (4P)', 'cols': ['ic_28', 'ic_29', 'ic_30', 'ic_31'], 'max_pts': 4000, 'badge_class': 'badge-gm', 'desc': 'Sum of S28–S31'},
            {'id': 'im', 'name': 'Intermezzo (3P)', 'short': 'Intermezzo (3P)', 'cols': ['im_25', 'im_26', 'im_27', 'im_28'], 'max_pts': 4000, 'badge_class': 'badge-m', 'desc': 'Sum of S25–S28'},
            {'id': 'rl', 'name': 'Royal League', 'short': 'Royal League', 'cols': ['rl_03', 'rl_04', 'rl_05', 'rl_06'], 'max_pts': 4000, 'badge_class': 'badge-p', 'desc': 'Sum of S03–S06'},
            {'id': 'wmbl', 'name': 'Wimbledon Open', 'short': 'Wimbledon', 'cols': ['wmbl'], 'max_pts': 1000, 'badge_class': 'badge-g', 'desc': 'Premier Grand Slam'},
            {'id': 'aus', 'name': 'Australian Open', 'short': 'Aussie Open', 'cols': ['aus'], 'max_pts': 1000, 'badge_class': 'badge-g', 'desc': 'Premier Grand Slam'},
            {'id': 'sl', 'name': 'Sodium Ladder', 'short': 'Sodium', 'cols': ['sl'], 'max_pts': 1000, 'badge_class': 'badge-rank', 'desc': 'Annual competitive ladder'},
            {'id': 'ml', 'name': 'Mercurial Ladder', 'short': 'Mercurial', 'cols': ['ml'], 'max_pts': 1000, 'badge_class': 'badge-rank', 'desc': 'Annual competitive ladder'},
            {'id': 'eif', 'name': 'Eiffel Tower Cup', 'short': 'Eiffel', 'cols': ['eif'], 'max_pts': 1000, 'badge_class': 'badge-rank', 'desc': 'Invitational cup'},
            {'id': 'qd', 'name': 'Quick & Dirty (Swiss)', 'short': 'Q&D', 'cols': ['qd'], 'max_pts': 600, 'badge_class': 'badge-rank', 'desc': 'Swiss tournament'},
            {'id': 'ldrb', 'name': 'Leaderboard Trophy', 'short': 'Trophy', 'cols': ['ldrb'], 'max_pts': 1000, 'badge_class': 'badge-wc', 'desc': 'Year-closing gala trophy'}
        ]

    elif edition == '2024':
        categories = [
            {
                'category': 'World Championship',
                'badge_class': 'badge-wc',
                'columns': [
                    {'id': 'wrld', 'name': 'World Championship', 'short': 'Worlds', 'max_pts': 2500, 'desc': 'World Championship (won by Martin_Pecheur)'}
                ]
            },
            {
                'category': 'International Championship (4-Player League)',
                'badge_class': 'badge-gm',
                'columns': [
                    {'id': 'ic_24', 'name': 'International Season 24', 'short': 'IC 24', 'max_pts': 1000},
                    {'id': 'ic_25', 'name': 'International Season 25', 'short': 'IC 25', 'max_pts': 1000},
                    {'id': 'ic_26', 'name': 'International Season 26', 'short': 'IC 26', 'max_pts': 1000},
                    {'id': 'ic_27', 'name': 'International Season 27', 'short': 'IC 27', 'max_pts': 1000},
                ]
            },
            {
                'category': 'Intermezzo Championship (3-Player League)',
                'badge_class': 'badge-m',
                'columns': [
                    {'id': 'im_21', 'name': 'Intermezzo Season 21', 'short': 'IM 21', 'max_pts': 1000},
                    {'id': 'im_22', 'name': 'Intermezzo Season 22', 'short': 'IM 22', 'max_pts': 1000},
                    {'id': 'im_23', 'name': 'Intermezzo Season 23', 'short': 'IM 23', 'max_pts': 1000},
                    {'id': 'im_24', 'name': 'Intermezzo Season 24', 'short': 'IM 24', 'max_pts': 1000},
                ]
            },
            {
                'category': 'Royal League',
                'badge_class': 'badge-p',
                'columns': [
                    {'id': 'rl_01', 'name': 'Royal League Season 1', 'short': 'RL 01', 'max_pts': 1000},
                    {'id': 'rl_02', 'name': 'Royal League Season 2', 'short': 'RL 02', 'max_pts': 1000},
                ]
            },
            {
                'category': 'Grand Slams & Annual Cups',
                'badge_class': 'badge-g',
                'columns': [
                    {'id': 'snail', 'name': 'Snail Cup', 'short': 'Snail Cup', 'max_pts': 1000},
                    {'id': 'wmbl', 'name': 'Wimbledon Open', 'short': 'Wimbledon', 'max_pts': 1000},
                    {'id': 'aus', 'name': 'Australian Open', 'short': 'Aussie Open', 'max_pts': 1000},
                ]
            },
            {
                'category': 'Competitive Ladders',
                'badge_class': 'badge-rank',
                'columns': [
                    {'id': 'ml', 'name': 'Mercurial Ladder', 'short': 'Mercurial', 'max_pts': 1000},
                ]
            },
            {
                'category': 'Invitational Cups',
                'badge_class': 'badge-rank',
                'columns': [
                    {'id': 'eif', 'name': 'Eiffel Tower Cup', 'short': 'Eiffel', 'max_pts': 1000},
                    {'id': 'qd', 'name': 'Quick & Dirty (Swiss)', 'short': 'Q&D', 'max_pts': 600},
                ]
            }
        ]
        tournaments_summary = [
            {'id': 'wrld', 'name': 'World Championship', 'short': 'Worlds', 'cols': ['wrld'], 'max_pts': 2500, 'badge_class': 'badge-wc', 'desc': 'World Championship'},
            {'id': 'ic', 'name': 'International (4P)', 'short': 'International (4P)', 'cols': ['ic_24', 'ic_25', 'ic_26', 'ic_27'], 'max_pts': 4000, 'badge_class': 'badge-gm', 'desc': 'Sum of S24–S27'},
            {'id': 'im', 'name': 'Intermezzo (3P)', 'short': 'Intermezzo (3P)', 'cols': ['im_21', 'im_22', 'im_23', 'im_24'], 'max_pts': 4000, 'badge_class': 'badge-m', 'desc': 'Sum of S21–S24'},
            {'id': 'rl', 'name': 'Royal League', 'short': 'Royal League', 'cols': ['rl_01', 'rl_02'], 'max_pts': 2000, 'badge_class': 'badge-p', 'desc': 'Sum of S01–S02'},
            {'id': 'snail', 'name': 'Snail Cup', 'short': 'Snail Cup', 'cols': ['snail'], 'max_pts': 1000, 'badge_class': 'badge-g', 'desc': 'Annual championship cup'},
            {'id': 'wmbl', 'name': 'Wimbledon Open', 'short': 'Wimbledon', 'cols': ['wmbl'], 'max_pts': 1000, 'badge_class': 'badge-g', 'desc': 'Premier Grand Slam'},
            {'id': 'aus', 'name': 'Australian Open', 'short': 'Aussie Open', 'cols': ['aus'], 'max_pts': 1000, 'badge_class': 'badge-g', 'desc': 'Premier Grand Slam'},
            {'id': 'ml', 'name': 'Mercurial Ladder', 'short': 'Mercurial', 'cols': ['ml'], 'max_pts': 1000, 'badge_class': 'badge-rank', 'desc': 'Annual competitive ladder'},
            {'id': 'eif', 'name': 'Eiffel Tower Cup', 'short': 'Eiffel', 'cols': ['eif'], 'max_pts': 1000, 'badge_class': 'badge-rank', 'desc': 'Invitational cup'},
            {'id': 'qd', 'name': 'Quick & Dirty (Swiss)', 'short': 'Q&D', 'cols': ['qd'], 'max_pts': 600, 'badge_class': 'badge-rank', 'desc': 'Swiss tournament'}
        ]

    elif edition == 'race26':
        categories = [
            {
                'category': 'World Championship',
                'badge_class': 'badge-wc',
                'columns': [
                    {'id': 'wrld', 'name': 'World Championship', 'short': 'Worlds', 'max_pts': 2500, 'desc': 'World Championship stage points'}
                ]
            },
            {
                'category': 'International Championship (4-Player)',
                'badge_class': 'badge-gm',
                'columns': [
                    {'id': 'ic_32', 'name': 'International Season 32', 'short': 'IC 32', 'max_pts': 1000},
                    {'id': 'ic_33', 'name': 'International Season 33', 'short': 'IC 33', 'max_pts': 1000},
                ]
            },
            {
                'category': 'Intermezzo Championship (3-Player)',
                'badge_class': 'badge-m',
                'columns': [
                    {'id': 'im_29', 'name': 'Intermezzo Season 29', 'short': 'IM 29', 'max_pts': 1000},
                    {'id': 'im_30', 'name': 'Intermezzo Season 30', 'short': 'IM 30', 'max_pts': 1000},
                ]
            },
            {
                'category': 'Royal League',
                'badge_class': 'badge-p',
                'columns': [
                    {'id': 'rl_07', 'name': 'Royal League Season 7', 'short': 'RL 07', 'max_pts': 1000},
                    {'id': 'rl_08', 'name': 'Royal League Season 8', 'short': 'RL 08', 'max_pts': 1000},
                ]
            },
            {
                'category': 'Grand Slams & Major Opens',
                'badge_class': 'badge-g',
                'columns': [
                    {'id': 'wmbl', 'name': 'Wimbledon Open', 'short': 'Wimbledon', 'max_pts': 1000},
                    {'id': 'aus', 'name': 'Australian Open', 'short': 'Aussie Open', 'max_pts': 1000},
                ]
            },
            {
                'category': 'Competitive Cups & Ladders',
                'badge_class': 'badge-rank',
                'columns': [
                    {'id': 'surv', 'name': 'Survivors Cup', 'short': 'Survivors', 'max_pts': 1000},
                    {'id': 'ml', 'name': 'Mercurial Ladder', 'short': 'Mercurial', 'max_pts': 1000},
                    {'id': 'sl', 'name': 'Sodium Ladder', 'short': 'Sodium', 'max_pts': 1000},
                    {'id': 'qd', 'name': 'Quick & Dirty (Swiss)', 'short': 'Q&D', 'max_pts': 600},
                ]
            }
        ]
        tournaments_summary = [
            {'id': 'wrld', 'name': 'World Championship', 'short': 'Worlds', 'cols': ['wrld'], 'max_pts': 2500, 'badge_class': 'badge-wc', 'desc': 'World Championship stage points'},
            {'id': 'ic', 'name': 'International (4P)', 'short': 'International (4P)', 'cols': ['ic_32', 'ic_33'], 'max_pts': 2000, 'badge_class': 'badge-gm', 'desc': '2026 seasons S32–S33'},
            {'id': 'im', 'name': 'Intermezzo (3P)', 'short': 'Intermezzo (3P)', 'cols': ['im_29', 'im_30'], 'max_pts': 2000, 'badge_class': 'badge-m', 'desc': '2026 seasons S29–S30'},
            {'id': 'rl', 'name': 'Royal League', 'short': 'Royal League', 'cols': ['rl_07', 'rl_08'], 'max_pts': 2000, 'badge_class': 'badge-p', 'desc': '2026 seasons S07–S08'},
            {'id': 'wmbl', 'name': 'Wimbledon Open', 'short': 'Wimbledon', 'cols': ['wmbl'], 'max_pts': 1000, 'badge_class': 'badge-g', 'desc': 'Premier Grand Slam'},
            {'id': 'aus', 'name': 'Australian Open', 'short': 'Aussie Open', 'cols': ['aus'], 'max_pts': 1000, 'badge_class': 'badge-g', 'desc': 'Premier Grand Slam'},
            {'id': 'surv', 'name': 'Survivors Cup', 'short': 'Survivors', 'cols': ['surv'], 'max_pts': 1000, 'badge_class': 'badge-rank', 'desc': 'Special championship cup'},
            {'id': 'ml', 'name': 'Mercurial Ladder', 'short': 'Mercurial', 'cols': ['ml'], 'max_pts': 1000, 'badge_class': 'badge-rank', 'desc': '2026 ladder rounds'},
            {'id': 'sl', 'name': 'Sodium Ladder', 'short': 'Sodium', 'cols': ['sl'], 'max_pts': 1000, 'badge_class': 'badge-rank', 'desc': '2026 ladder rounds'},
            {'id': 'qd', 'name': 'Quick & Dirty (Swiss)', 'short': 'Q&D', 'cols': ['qd'], 'max_pts': 600, 'badge_class': 'badge-rank', 'desc': 'Swiss tournament'}
        ]

    else:
        # Default 2026 Rolling Q2
        categories = [
            {
                'category': 'World Championship',
                'badge_class': 'badge-wc',
                'columns': [
                    {'id': 'wrld', 'name': 'World Championship', 'short': 'Worlds', 'max_pts': 2500, 'desc': 'Biennial World Championship (won by a440 in 2025)'}
                ]
            },
            {
                'category': 'International Championship (4-Player League)',
                'badge_class': 'badge-gm',
                'columns': [
                    {'id': 'ic_30', 'name': 'International Season 30', 'short': 'IC 30', 'max_pts': 1000},
                    {'id': 'ic_31', 'name': 'International Season 31', 'short': 'IC 31', 'max_pts': 1000},
                    {'id': 'ic_32', 'name': 'International Season 32', 'short': 'IC 32', 'max_pts': 1000},
                    {'id': 'ic_33', 'name': 'International Season 33', 'short': 'IC 33', 'max_pts': 1000},
                ]
            },
            {
                'category': 'Intermezzo Championship (3-Player League)',
                'badge_class': 'badge-m',
                'columns': [
                    {'id': 'im_27', 'name': 'Intermezzo Season 27', 'short': 'IM 27', 'max_pts': 1000},
                    {'id': 'im_28', 'name': 'Intermezzo Season 28', 'short': 'IM 28', 'max_pts': 1000},
                    {'id': 'im_29', 'name': 'Intermezzo Season 29', 'short': 'IM 29', 'max_pts': 1000},
                    {'id': 'im_30', 'name': 'Intermezzo Season 30', 'short': 'IM 30', 'max_pts': 1000},
                ]
            },
            {
                'category': 'Royal League',
                'badge_class': 'badge-p',
                'columns': [
                    {'id': 'rl_05', 'name': 'Royal League Season 5', 'short': 'RL 05', 'max_pts': 1000},
                    {'id': 'rl_06', 'name': 'Royal League Season 6', 'short': 'RL 06', 'max_pts': 1000},
                    {'id': 'rl_07', 'name': 'Royal League Season 7', 'short': 'RL 07', 'max_pts': 1000},
                    {'id': 'rl_08', 'name': 'Royal League Season 8', 'short': 'RL 08', 'max_pts': 1000},
                ]
            },
            {
                'category': 'Grand Slams & Major Opens',
                'badge_class': 'badge-g',
                'columns': [
                    {'id': 'wmbl', 'name': 'Wimbledon Open', 'short': 'Wimbledon', 'max_pts': 1000},
                    {'id': 'aus', 'name': 'Australian Open', 'short': 'Aussie Open', 'max_pts': 1000},
                ]
            },
            {
                'category': 'Competitive Ladders',
                'badge_class': 'badge-rank',
                'columns': [
                    {'id': 'sl', 'name': 'Sodium Ladder', 'short': 'Sodium', 'max_pts': 1000},
                    {'id': 'ml', 'name': 'Mercurial Ladder', 'short': 'Mercurial', 'max_pts': 1000},
                ]
            },
            {
                'category': 'Invitational & Rapid Cups',
                'badge_class': 'badge-rank',
                'columns': [
                    {'id': 'eif', 'name': 'Eiffel Tower Cup', 'short': 'Eiffel', 'max_pts': 1000},
                    {'id': 'qd', 'name': 'Quick & Dirty (Swiss)', 'short': 'Q&D', 'max_pts': 600},
                ]
            }
        ]
        tournaments_summary = [
            {'id': 'wrld', 'name': 'World Championship', 'short': 'Worlds', 'cols': ['wrld'], 'max_pts': 2500, 'badge_class': 'badge-wc', 'desc': 'Biennial World Championship (won by a440 in 2025)'},
            {'id': 'ic', 'name': 'International (4P)', 'short': 'International (4P)', 'cols': ['ic_30', 'ic_31', 'ic_32', 'ic_33'], 'max_pts': 4000, 'badge_class': 'badge-gm', 'desc': 'Sum of 4 rolling seasons (S30–S33)'},
            {'id': 'im', 'name': 'Intermezzo (3P)', 'short': 'Intermezzo (3P)', 'cols': ['im_27', 'im_28', 'im_29', 'im_30'], 'max_pts': 4000, 'badge_class': 'badge-m', 'desc': 'Sum of 4 rolling seasons (S27–S30)'},
            {'id': 'rl', 'name': 'Royal League', 'short': 'Royal League', 'cols': ['rl_05', 'rl_06', 'rl_07', 'rl_08'], 'max_pts': 4000, 'badge_class': 'badge-p', 'desc': 'Sum of 4 rolling seasons (S05–S08)'},
            {'id': 'wmbl', 'name': 'Wimbledon Open', 'short': 'Wimbledon', 'cols': ['wmbl'], 'max_pts': 1000, 'badge_class': 'badge-g', 'desc': 'Premier Grand Slam open event'},
            {'id': 'aus', 'name': 'Australian Open', 'short': 'Aussie Open', 'cols': ['aus'], 'max_pts': 1000, 'badge_class': 'badge-g', 'desc': 'Premier Grand Slam open event'},
            {'id': 'sl', 'name': 'Sodium Ladder', 'short': 'Sodium', 'cols': ['sl'], 'max_pts': 1000, 'badge_class': 'badge-rank', 'desc': 'Tiered annual competitive ladder'},
            {'id': 'ml', 'name': 'Mercurial Ladder', 'short': 'Mercurial', 'cols': ['ml'], 'max_pts': 1000, 'badge_class': 'badge-rank', 'desc': 'Tiered annual competitive ladder'},
            {'id': 'eif', 'name': 'Eiffel Tower Cup', 'short': 'Eiffel', 'cols': ['eif'], 'max_pts': 1000, 'badge_class': 'badge-rank', 'desc': 'Invitational championship cup'},
            {'id': 'qd', 'name': 'Quick & Dirty (Swiss)', 'short': 'Q&D', 'cols': ['qd'], 'max_pts': 600, 'badge_class': 'badge-rank', 'desc': 'Fast-paced Swiss trophy tournament'}
        ]

    all_columns = []
    for cat in categories:
        all_columns.extend(cat['columns'])

    return categories, all_columns, tournaments_summary


@bp.route('/community-leaderboard')
@bp.route('/community-leaderboard/<edition_param>')
@bp.route('/community')
@bp.route('/community/<edition_param>')
def index(edition_param=None):
    # Determine edition / year
    raw_ed = edition_param or request.args.get('year') or request.args.get('edition') or '2026'
    raw_ed = str(raw_ed).strip().lower()
    if raw_ed in ('2026', 'q2_2026', 'current'):
        active_edition = '2026'
    elif raw_ed in ('2025', 'y2025'):
        active_edition = '2025'
    elif raw_ed in ('2024', 'y2024'):
        active_edition = '2024'
    elif raw_ed in ('race26', 'race', 'race2026', '2026race'):
        active_edition = 'race26'
    else:
        active_edition = '2026'

    edition_info = AVAILABLE_EDITIONS.get(active_edition, AVAILABLE_EDITIONS['2026'])
    categories, all_columns, tournaments_summary = get_edition_structure(active_edition)

    search_query = request.args.get('q', '').strip()
    page_str = request.args.get('page', '1').strip()
    per_page_str = request.args.get('per_page', '50').strip()
    view_mode = request.args.get('view', 'standard').lower()
    if view_mode not in ('standard', 'expanded'):
        view_mode = 'standard'

    try:
        page = max(1, int(page_str))
    except ValueError:
        page = 1

    if per_page_str == 'all':
        per_page = 2000
    else:
        try:
            per_page = max(10, min(200, int(per_page_str)))
        except ValueError:
            per_page = 50

    conn = get_connection()
    
    # Check if community_leaderboard_entries table exists
    has_entries_table = conn.execute("""
        SELECT name FROM sqlite_master WHERE type='table' AND name='community_leaderboard_entries'
    """).fetchone()

    if has_entries_table:
        count_sql = "SELECT COUNT(*) as cnt FROM community_leaderboard_entries cle WHERE cle.edition = ?"
        count_params = [active_edition]
        if search_query:
            count_sql += " AND cle.player_name LIKE ? "
            count_params.append(f"%{search_query}%")

        total_count = conn.execute(count_sql, count_params).fetchone()['cnt']
        total_pages = max(1, math.ceil(total_count / per_page)) if per_page > 0 else 1

        if page > total_pages:
            page = total_pages

        offset = (page - 1) * per_page
        query_sql = """
            SELECT cle.edition, cle.rank, cle.player_name, cle.points, cle.tourneys_played,
                   cle.scores_json, cle.counting_cols_json,
                   p.country_code, p.title
            FROM community_leaderboard_entries cle
            LEFT JOIN players p ON cle.player_name = p.name COLLATE NOCASE
            WHERE cle.edition = ?
        """
        query_params = [active_edition]
        if search_query:
            query_sql += " AND cle.player_name LIKE ? "
            query_params.append(f"%{search_query}%")

        query_sql += " ORDER BY cle.rank ASC, cle.points DESC LIMIT ? OFFSET ?"
        query_params.extend([per_page, offset])
        rows = conn.execute(query_sql, query_params).fetchall()

        players_data = []
        for r in rows:
            row_dict = dict(r)
            scores = {}
            if row_dict.get('scores_json'):
                try:
                    scores = json.loads(row_dict['scores_json'])
                except Exception:
                    scores = {}
            row_dict.update(scores)

            counting_cols = set()
            if row_dict.get('counting_cols_json'):
                try:
                    counting_cols = set(json.loads(row_dict['counting_cols_json']))
                except Exception:
                    pass
            row_dict['counting_cols'] = counting_cols
            row_dict['is_reigning_wc'] = (row_dict['player_name'].lower() == edition_info['wc'].lower())

            # Calculate tournament sums for Standard View
            summary_scores = {}
            summary_has_counting = {}
            for t in tournaments_summary:
                t_sum = 0.0
                has_any = False
                has_counting = False
                for col in t['cols']:
                    v = row_dict.get(col)
                    if v is not None and v > 0:
                        t_sum += v
                        has_any = True
                        if col in counting_cols:
                            has_counting = True
                summary_scores[t['id']] = t_sum if has_any else None
                summary_has_counting[t['id']] = has_counting

            row_dict['summary_scores'] = summary_scores
            row_dict['summary_has_counting'] = summary_has_counting
            players_data.append(row_dict)

        top_row = conn.execute(
            "SELECT player_name, points FROM community_leaderboard_entries WHERE edition = ? ORDER BY rank ASC LIMIT 1",
            (active_edition,)
        ).fetchone()
        top_player = top_row['player_name'] if top_row else "wolvs"
        top_points = top_row['points'] if top_row else 6320.0
        total_competitors = conn.execute(
            "SELECT COUNT(*) as c FROM community_leaderboard_entries WHERE edition = ?",
            (active_edition,)
        ).fetchone()['c']

    else:
        # Fallback to legacy single community_leaderboard table
        base_sql = """
            SELECT cl.*, p.country_code, p.title
            FROM community_leaderboard cl
            LEFT JOIN players p ON LOWER(cl.player_name) = LOWER(p.name)
        """
        params = []
        if search_query:
            base_sql += " WHERE cl.player_name LIKE ? "
            params.append(f"%{search_query}%")

        count_sql = f"SELECT COUNT(*) as cnt FROM ({base_sql})"
        total_count = conn.execute(count_sql, params).fetchone()['cnt']
        total_pages = max(1, math.ceil(total_count / per_page)) if per_page > 0 else 1

        if page > total_pages:
            page = total_pages

        offset = (page - 1) * per_page
        query_sql = f"{base_sql} ORDER BY cl.rank ASC, cl.points DESC LIMIT ? OFFSET ?"
        params.extend([per_page, offset])
        rows = conn.execute(query_sql, params).fetchall()

        players_data = []
        for r in rows:
            row_dict = dict(r)
            counting_cols = set()
            if row_dict.get('counting_cols_json'):
                try:
                    counting_cols = set(json.loads(row_dict['counting_cols_json']))
                except Exception:
                    pass
            row_dict['counting_cols'] = counting_cols
            row_dict['is_reigning_wc'] = (row_dict['player_name'].lower() == 'a440')

            summary_scores = {}
            summary_has_counting = {}
            for t in tournaments_summary:
                t_sum = 0.0
                has_any = False
                has_counting = False
                for col in t['cols']:
                    v = row_dict.get(col)
                    if v is not None and v > 0:
                        t_sum += v
                        has_any = True
                        if col in counting_cols:
                            has_counting = True
                summary_scores[t['id']] = t_sum if has_any else None
                summary_has_counting[t['id']] = has_counting

            row_dict['summary_scores'] = summary_scores
            row_dict['summary_has_counting'] = summary_has_counting
            players_data.append(row_dict)

        top_row = conn.execute("SELECT player_name, points FROM community_leaderboard ORDER BY rank ASC LIMIT 1").fetchone()
        top_player = top_row['player_name'] if top_row else "wolvs"
        top_points = top_row['points'] if top_row else 6320.0
        total_competitors = conn.execute("SELECT COUNT(*) as c FROM community_leaderboard").fetchone()['c']

    stats = {
        'total_competitors': total_competitors,
        'active_tournaments': len(all_columns),
        'top_player': top_player,
        'top_points': top_points,
        'reigning_wc': edition_info['wc'],
        'wc_desc': edition_info['wc_desc'],
        'wc_points': 2500
    }
    conn.close()

    return render_template(
        'community_leaderboard.html',
        players=players_data,
        categories=categories,
        all_columns=all_columns,
        tournaments_summary=tournaments_summary,
        view_mode=view_mode,
        stats=stats,
        search_query=search_query,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        total_count=total_count,
        active_edition=active_edition,
        edition_info=edition_info,
        available_editions=AVAILABLE_EDITIONS
    )
