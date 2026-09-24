"""Template Editor: Hardcode CMS card content directly into Jinja2 HTML templates."""
import re
from pathlib import Path
from typing import Optional, Dict, Any
from src.data.db import revert_cms_block

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / 'src' / 'web' / 'templates'

PAGE_TEMPLATE_MAP = {
    'faq': 'faq.html',
    'leaderboard': 'leaderboard.html',
    'analysis': 'analysis.html',
    'community': 'community_leaderboard.html',
    'hall_of_fame': 'tournaments/hub.html',
    'player': 'player.html',
    'movers': 'analysis_movers.html',
    'activity': 'analysis_activity.html',
}


def locate_template_for_block(page_id: str, block_key: str) -> Optional[Path]:
    """Locates the template file containing the specified block_key."""
    # 1. Try direct page_id mapping
    mapped_filename = PAGE_TEMPLATE_MAP.get(page_id)
    if mapped_filename:
        primary_path = TEMPLATES_DIR / mapped_filename
        if primary_path.exists():
            text = primary_path.read_text(encoding='utf-8')
            if f'data-block="{block_key}"' in text or f"data-block='{block_key}'" in text or block_key in text:
                return primary_path

    # 2. Search all templates
    for html_file in TEMPLATES_DIR.rglob('*.html'):
        try:
            text = html_file.read_text(encoding='utf-8')
            if f'data-block="{block_key}"' in text or f"data-block='{block_key}'" in text:
                return html_file
        except Exception:
            continue

    # Fallback to mapped file if it exists even if block_key not yet present (for custom dynamic cards)
    if mapped_filename:
        primary_path = TEMPLATES_DIR / mapped_filename
        if primary_path.exists():
            return primary_path

    return None


def hardcode_card_to_template(
    page_id: str,
    block_key: str,
    title: str,
    content_html: str,
    content_markdown: Optional[str] = None,
    relative_to: Optional[str] = None,
    placement: Optional[str] = None,
    is_custom_card: bool = False
) -> Dict[str, Any]:
    """Permanently bakes card title, HTML content, and pristine Markdown source directly into the template file on disk."""
    target_search_key = relative_to if (is_custom_card and relative_to) else block_key
    template_path = locate_template_for_block(page_id, target_search_key)
    if not template_path:
        raise FileNotFoundError(f"Could not locate template for page '{page_id}' and block '{target_search_key}'")

    raw_html = template_path.read_text(encoding='utf-8')

    if is_custom_card and relative_to:
        # Insert a new card above or below the anchor
        anchor_match = re.search(r'([ \t]*<div[^>]*data-block=[\'"]' + re.escape(relative_to) + r'[\'"][^>]*>)', raw_html)
        if not anchor_match:
            raise ValueError(f"Anchor card '{relative_to}' not found in template {template_path.name}")

        clean_var_name = f"block_{re.sub(r'[^a-zA-Z0-9_]', '_', block_key)}"
        new_card_markup = f"""
    {{% set {clean_var_name} = get_cms('{page_id}', '{block_key}', '{title}') %}}
    <div class="faq-card cms-card" data-page="{page_id}" data-block="{block_key}" data-is-custom="{{{{ 'true' if {clean_var_name}.is_custom else 'false' }}}}" style="border-left: 4px solid var(--accent-gold);">
      <h3 class="cms-title">{{{{ {clean_var_name}.title }}}}</h3>
      <div class="cms-content">
        {{% if {clean_var_name}.is_custom %}}
          {{{{ {clean_var_name}.content }}}}
        {{% else %}}
          {content_html}
        {{% endif %}}
      </div>
      <template class="cms-default-source" style="display:none;">
        {content_html}
      </template>
      <script type="text/markdown" class="cms-markdown-source" style="display:none;">
{content_markdown or ''}
      </script>
    </div>
"""
        if placement == 'above':
            pos = anchor_match.start()
            set_pat = re.search(r'([ \t]*\{%\s*set\s+[a-zA-Z0-9_]+\s*=\s*get_cms\([^)]*[\'"]' + re.escape(relative_to) + r'[\'"][^)]*\)\s*%\}\s*\n)', raw_html[:pos])
            if set_pat and pos - set_pat.end() < 50:
                pos = set_pat.start()
            raw_html = raw_html[:pos] + new_card_markup + "\n" + raw_html[pos:]
        else:
            anchor_end = re.search(
                r'(<div[^>]*data-block=[\'"]' + re.escape(relative_to) + r'[\'"][^>]*>[\s\S]*?)(</template>\s*</div>|</div>\s*</div>)',
                raw_html
            )
            if anchor_end:
                pos = anchor_end.end()
            else:
                pos = anchor_match.end()
            raw_html = raw_html[:pos] + "\n" + new_card_markup + raw_html[pos:]

    else:
        # Modifying an existing template card
        # 1. Update default title in get_cms
        title_pat = re.compile(
            r"({%-?\s*set\s+[a-zA-Z0-9_]+\s*=\s*get_cms\(\s*['\"]" + re.escape(page_id) + r"['\"]\s*,\s*['\"]" + re.escape(block_key) + r"['\"]\s*,\s*['\"])(.*?)(['\"]\s*\)\s*-?%})"
        )
        raw_html = title_pat.sub(lambda m: m.group(1) + title + m.group(3), raw_html)

        # 2. Update {% else %} ... {% endif %} block inside the card container
        else_pat = re.compile(
            r'(<div[^>]*data-block=[\'"]' + re.escape(block_key) + r'[\'"][^>]*>[\s\S]*?\{%-?\s*else\s*-?%\})([\s\S]*?)(\{%-?\s*endif\s*-?%\})'
        )
        if else_pat.search(raw_html):
            raw_html = else_pat.sub(lambda m: m.group(1) + '\n          ' + content_html + '\n        ' + m.group(3), raw_html)
        else:
            # If no {% else %} block, update inside cms-content
            cms_content_pat = re.compile(
                r'(<div[^>]*data-block=[\'"]' + re.escape(block_key) + r'[\'"][^>]*>[\s\S]*?<div class="cms-content">)([\s\S]*?)(</div>)'
            )
            if cms_content_pat.search(raw_html):
                clean_var_name = f"block_{re.sub(r'[^a-zA-Z0-9_]', '_', block_key)}"
                replacement = f"""
        {{% if {clean_var_name}.is_custom %}}
          {{{{ {clean_var_name}.content }}}}
        {{% else %}}
          {content_html}
        {{% endif %}}
      """
                raw_html = cms_content_pat.sub(lambda m: m.group(1) + replacement + m.group(3), raw_html)

        # 3. Update <template class="cms-default-source"> if present
        tpl_pat = re.compile(
            r'(<div[^>]*data-block=[\'"]' + re.escape(block_key) + r'[\'"][^>]*>[\s\S]*?<template class="cms-default-source"[^>]*>)([\s\S]*?)(</template>)'
        )
        if tpl_pat.search(raw_html):
            raw_html = tpl_pat.sub(lambda m: m.group(1) + '\n        ' + content_html + '\n      ' + m.group(3), raw_html)

        # 4. Update or insert <script type="text/markdown" class="cms-markdown-source"> if markdown provided
        if content_markdown:
            md_pat = re.compile(
                r'(<div[^>]*data-block=[\'"]' + re.escape(block_key) + r'[\'"][^>]*>[\s\S]*?<script type="text/markdown" class="cms-markdown-source"[^>]*>)([\s\S]*?)(</script>)'
            )
            if md_pat.search(raw_html):
                raw_html = md_pat.sub(lambda m: m.group(1) + '\n' + content_markdown + '\n      ' + m.group(3), raw_html)
            else:
                tpl_after = re.compile(
                    r'(<div[^>]*data-block=[\'"]' + re.escape(block_key) + r'[\'"][^>]*>[\s\S]*?</template>)'
                )
                if tpl_after.search(raw_html):
                    md_tag = f'\n      <script type="text/markdown" class="cms-markdown-source" style="display:none;">\n{content_markdown}\n      </script>'
                    raw_html = tpl_after.sub(lambda m: m.group(1) + md_tag, raw_html)

    # Write changes directly to template file
    template_path.write_text(raw_html, encoding='utf-8')

    # Remove dynamic override from SQLite so the template is now the source of truth
    revert_cms_block(page_id, block_key)

    return {
        'status': 'success',
        'file': str(template_path.relative_to(TEMPLATES_DIR.parent)),
        'block_key': block_key,
        'page_id': page_id
    }
