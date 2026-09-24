"""Tests for Universal Webmaster In-Place Card & Header CMS."""
import pytest
from flask import session
from src.data.db import (
    get_connection,
    save_cms_block,
    get_cms_block,
    get_all_cms_blocks,
    revert_cms_block
)
from src.web.app import create_app
import src.data.db


@pytest.fixture(autouse=True)
def isolate_cms_test_db(tmp_path, monkeypatch):
    """Isolates all CMS tests to a temporary SQLite database, protecting production/dev data."""
    test_db = tmp_path / "cms_test.db"
    from src.data.db import init_db
    monkeypatch.setattr(src.data.db, 'DEFAULT_DB_PATH', test_db)
    init_db(test_db)
    yield test_db


@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    with app.test_client() as client:
        yield client


def test_cms_db_crud():
    """Test direct database CRUD operations for CMS content blocks."""
    page_id = 'test_page'
    block_key = 'test_block'
    title = 'Test Card Title'
    markdown = '### Heading\n\nThis is **bold** text and $x = 42$.'
    html = '<h3>Heading</h3><p>This is <strong>bold</strong> text and $x = 42$.</p>'

    # 1. Save block
    save_cms_block(page_id, block_key, title, html, markdown)

    # 2. Get block
    block = get_cms_block(page_id, block_key)
    assert block is not None
    assert block['page_id'] == page_id
    assert block['block_key'] == block_key
    assert block['title'] == title
    assert block['content_markdown'] == markdown
    assert block['content_html'] == html

    # 3. Check get_all_cms_blocks
    all_blocks = get_all_cms_blocks()
    assert (page_id, block_key) in all_blocks
    assert all_blocks[(page_id, block_key)]['title'] == title

    # 4. Revert block
    reverted = revert_cms_block(page_id, block_key)
    assert reverted is True
    assert get_cms_block(page_id, block_key) is None


def test_cms_security_guardrails(client):
    """Ensure non-admin users cannot access or alter CMS blocks."""
    # GET block without admin login
    res = client.get('/admin/cms/get_block?page_id=faq&block_key=philosophy_what_is_engine')
    assert res.status_code in [302, 401, 403]

    # POST save without admin login
    res = client.post('/admin/cms/save_block', json={
        'page_id': 'faq',
        'block_key': 'philosophy_what_is_engine',
        'title': 'Hacked Title',
        'content_markdown': 'Hacked content',
        'content_html': '<p>Hacked content</p>'
    })
    assert res.status_code in [302, 401, 403]

    # POST revert without admin login
    res = client.post('/admin/cms/revert_block', json={
        'page_id': 'faq',
        'block_key': 'philosophy_what_is_engine'
    })
    assert res.status_code in [302, 401, 403]


def test_cms_admin_workflow_and_rollback(client):
    """Test full cycle: admin save, page reflection, and revert to default."""
    # 1. Set admin session
    with client.session_transaction() as sess:
        sess['is_admin'] = True

    page_id = 'faq'
    block_key = 'glicko_std_overview'
    custom_title = 'Customized Webmaster CMS Title 2026'
    custom_md = '**Customized body** with math: $E = mc^2$'
    custom_html = '<p><strong>Customized body</strong> with math: $E = mc^2$</p>'

    try:
        # 2. Save custom block via API
        save_res = client.post('/admin/cms/save_block', json={
            'page_id': page_id,
            'block_key': block_key,
            'title': custom_title,
            'content_markdown': custom_md,
            'content_html': custom_html
        })
        assert save_res.status_code == 200
        save_data = save_res.get_json()
        assert save_data['status'] == 'success'

        # 3. Fetch block via API
        get_res = client.get(f'/admin/cms/get_block?page_id={page_id}&block_key={block_key}')
        assert get_res.status_code == 200
        get_data = get_res.get_json()
        assert get_data['status'] == 'success'
        assert get_data['block']['title'] == custom_title
        assert get_data['block']['content_markdown'] == custom_md

        # 4. View page and ensure customized title and content render
        faq_res = client.get('/faq')
        assert faq_res.status_code == 200
        html_text = faq_res.get_data(as_text=True)
        assert custom_title in html_text
        assert 'Customized body' in html_text

        # 5. Revert block back to default
        rev_res = client.post('/admin/cms/revert_block', json={
            'page_id': page_id,
            'block_key': block_key
        })
        assert rev_res.status_code == 200
        rev_data = rev_res.get_json()
        assert rev_data['status'] == 'success'

        # 6. Verify page now displays default template content
        faq_res2 = client.get('/faq')
        assert faq_res2.status_code == 200
        html_text2 = faq_res2.get_data(as_text=True)
        assert custom_title not in html_text2
        assert 'Glicko-2 Standard: Classical Sequential Bayesian Estimation' in html_text2

    finally:
        # Clean up database just in case
        revert_cms_block(page_id, block_key)


def test_faq_preserves_user_manual_copy(client):
    """Verify that the user's manual copy on the FAQ frontpage remains intact."""
    res = client.get('/faq')
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    expected_phrase = 'When two opponents meet in a match, given the results we have seen these opponents achieve in the past, what is the expected outcome of the match?'
    assert expected_phrase in html


def test_cms_list_and_revert_all(client):
    """Verify listing all CMS blocks and the bulk revert_all endpoint."""
    with client.session_transaction() as sess:
        sess['is_admin'] = True

    # 1. Save two test blocks
    client.post('/admin/cms/save_block', json={
        'page_id': 'faq',
        'block_key': 'test_bulk_1',
        'title': 'Bulk 1',
        'content_markdown': 'Formula: $$\\mu = 1500$$',
        'content_html': '<div class="faq-formula">$$\\mu = 1500$$</div>'
    })
    client.post('/admin/cms/save_block', json={
        'page_id': 'faq',
        'block_key': 'test_bulk_2',
        'title': 'Bulk 2',
        'content_markdown': 'Formula: $P(A > B)$',
        'content_html': '<p>Formula: $P(A > B)$</p>'
    })

    # 2. List blocks
    list_res = client.get('/admin/cms/list')
    assert list_res.status_code == 200
    list_data = list_res.get_json()
    assert list_data['status'] == 'success'
    assert list_data['count'] >= 2

    # 3. Bulk revert all
    rev_all_res = client.post('/admin/cms/revert_all', json={})
    assert rev_all_res.status_code == 200
    rev_all_data = rev_all_res.get_json()
    assert rev_all_data['status'] == 'success'
    assert rev_all_data['reverted_count'] >= 2

    # 4. List again to ensure empty
    list_res2 = client.get('/admin/cms/list')
    assert list_res2.get_json()['count'] == 0


def test_faq_templates_contain_content_and_formulas(client):
    """Verify all FAQ cards contain populated default templates with intact formulas."""
    res = client.get('/faq')
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    # Check that default source templates exist for cards
    assert 'class="cms-default-source"' in html
    
    # Check that key formulas exist within default source templates
    assert r'P(\text{Player A defeats Player B})' in html
    assert r'\frac{1}{1 + 10^{-(r_A - r_B)/400}}' in html
    assert r'\mu' in html or r'\sigma' in html


def test_cms_preserves_latex_subscripts_and_symbols(client):
    """Ensure complex LaTeX math with subscripts and greek letters is saved and served without corruption."""
    with client.session_transaction() as sess:
        sess['is_admin'] = True

    page_id = 'faq'
    block_key = 'test_math_integrity'
    raw_markdown = r"""### Calibration Metric

Expected win probability for player with rating $r_A$ against $r_B$:

$$
P(A > B) = \frac{1}{1 + 10^{-(r_A - r_B)/400}}
$$

Where $\mu \in \mathbb{R}$ and $\sigma^2$ is the variance."""

    raw_html = r"""<h3>Calibration Metric</h3>
<p>Expected win probability for player with rating $r_A$ against $r_B$:</p>
<div class="faq-formula">
$$
P(A > B) = \frac{1}{1 + 10^{-(r_A - r_B)/400}}
$$
</div>
<p>Where $\mu \in \mathbb{R}$ and $\sigma^2$ is the variance.</p>"""

    try:
        # Save
        save_res = client.post('/admin/cms/save_block', json={
            'page_id': page_id,
            'block_key': block_key,
            'title': 'Calibration Metric',
            'content_markdown': raw_markdown,
            'content_html': raw_html
        })
        assert save_res.status_code == 200

        # Retrieve
        get_res = client.get(f'/admin/cms/get_block?page_id={page_id}&block_key={block_key}')
        assert get_res.status_code == 200
        block = get_res.get_json()['block']

        # Verify LaTeX is 100% intact (no italics conversion from underscores)
        assert r'r_A - r_B' in block['content_markdown']
        assert r'\frac{1}{1 + 10^{-(r_A - r_B)/400}}' in block['content_markdown']
        assert r'\sigma^2' in block['content_markdown']
        assert r'<em>' not in block['content_html']  # subscripts should not become <em>
    finally:
        revert_cms_block(page_id, block_key)


def test_cms_card_deletion_and_restore(client):
    """Test deleting a card (marking is_deleted) and restoring it."""
    with client.session_transaction() as sess:
        sess['is_admin'] = True

    page_id = 'faq'
    block_key = 'test_delete_card'

    try:
        # 1. Delete block
        del_res = client.post('/admin/cms/delete_block', json={
            'page_id': page_id,
            'block_key': block_key
        })
        assert del_res.status_code == 200
        assert del_res.get_json()['status'] == 'success'

        # 2. Check block status
        block = get_cms_block(page_id, block_key)
        assert block is not None
        assert block['is_deleted'] == 1

        # 3. Restore block
        rest_res = client.post('/admin/cms/restore_block', json={
            'page_id': page_id,
            'block_key': block_key
        })
        assert rest_res.status_code == 200
        assert rest_res.get_json()['status'] == 'success'

        # 4. Verify restored
        block2 = get_cms_block(page_id, block_key)
        assert block2 is None or block2['is_deleted'] == 0
    finally:
        revert_cms_block(page_id, block_key)


def test_cms_card_creation_above_below(client):
    """Test creating dynamic custom cards anchored above or below an existing card."""
    with client.session_transaction() as sess:
        sess['is_admin'] = True

    page_id = 'faq'
    anchor_key = 'philosophy_what_is_engine'
    new_card_key = 'custom_card_test_99'

    try:
        # 1. Create card below anchor
        save_res = client.post('/admin/cms/save_block', json={
            'page_id': page_id,
            'block_key': new_card_key,
            'title': 'New Dynamic Custom Card',
            'content_markdown': '### Custom Note\n\n| Param | Value |\n|---|---|\n| Rating | 1850 |',
            'content_html': '<h3>Custom Note</h3><table><thead><tr><th>Param</th><th>Value</th></tr></thead><tbody><tr><td>Rating</td><td>1850</td></tr></tbody></table>',
            'relative_to': anchor_key,
            'placement': 'below',
            'is_custom_card': 1
        })
        assert save_res.status_code == 200
        assert save_res.get_json()['status'] == 'success'

        # 2. Query custom cards endpoint
        cards_res = client.get(f'/admin/cms/custom_cards?page_id={page_id}')
        assert cards_res.status_code == 200
        data = cards_res.get_json()
        assert data['status'] == 'success'
        found = [c for c in data['cards'] if c['block_key'] == new_card_key]
        assert len(found) == 1
        assert found[0]['relative_to'] == anchor_key
        assert found[0]['placement'] == 'below'
        assert found[0]['title'] == 'New Dynamic Custom Card'
    finally:
        revert_cms_block(page_id, new_card_key)


def test_cms_hardcode_to_template(client, tmp_path, monkeypatch):
    """Test hardcoding a CMS block directly into a template file on disk."""
    with client.session_transaction() as sess:
        sess['is_admin'] = True

    # Create a mock template in a temporary directory
    mock_templates_dir = tmp_path / "templates"
    mock_templates_dir.mkdir()
    mock_faq = mock_templates_dir / "faq.html"
    mock_faq.write_text("""
    {% set block_sample = get_cms('faq', 'sample_block', 'Original Title') %}
    <div class="faq-card cms-card" data-page="faq" data-block="sample_block">
      <h3 class="cms-title">{{ block_sample.title }}</h3>
      <div class="cms-content">
        {% if block_sample.is_custom %}
          {{ block_sample.content }}
        {% else %}
          <p>Original default content</p>
        {% endif %}
      </div>
      <template class="cms-default-source" style="display:none;">
        <p>Original default content</p>
      </template>
    </div>
    """, encoding='utf-8')

    import src.data.template_editor as te
    monkeypatch.setattr(te, 'TEMPLATES_DIR', mock_templates_dir)

    hardcode_res = client.post('/admin/cms/hardcode_block', json={
        'page_id': 'faq',
        'block_key': 'sample_block',
        'title': 'Hardcoded Brand New Title',
        'content_markdown': '### Baked in content\n\nHardcoded forever with math: $\\mu = 1500$, $\\sigma = 350$, $\\frac{1}{1 + 10^{-(r_A - r_B)/400}}$ and $\\mathrm{Brier}$',
        'content_html': '<h3>Baked in content</h3><p>Hardcoded forever with math: $\\mu = 1500$, $\\sigma = 350$, $\\frac{1}{1 + 10^{-(r_A - r_B)/400}}$ and $\\mathrm{Brier}$</p>'
    })
    assert hardcode_res.status_code == 200
    data = hardcode_res.get_json()
    assert data['status'] == 'success'

    # Check that template was modified directly
    updated_text = mock_faq.read_text(encoding='utf-8')
    assert 'Hardcoded Brand New Title' in updated_text
    assert 'Baked in content' in updated_text
    assert r'\mu = 1500' in updated_text
    assert r'\sigma = 350' in updated_text
    assert r'\mathrm{Brier}' in updated_text
    assert 'class="cms-markdown-source"' in updated_text
    assert r'$\mu = 1500$' in updated_text

    # Check that database override was cleared because template is now source of truth
    db_block = get_cms_block('faq', 'sample_block')
    assert db_block is None


def test_faq_mp_vs_std_calibration_table_and_sync(client):
    """Verify that the FAQ multiplayer card compares only authentic Glicko-2 Standard vs MP models."""
    res = client.get('/faq')
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    # 1. Ensure fabricated entries are eliminated
    assert 'Golden Geometric' not in html
    assert '<td>Coulom Fractional</td>' not in html
    assert 'Across 131,000+ Matches' not in html

    # 2. Ensure authentic title and models are displayed
    assert 'Comparing Glicko-2 Standard vs. MP-Weighted Models' in html
    assert 'Glicko-2 MP-Weighted' in html
    assert 'Glicko-2 Standard' in html

    # 3. Ensure live dynamic calibration metrics from analysis are present
    assert '0.2141' in html
    assert '1.15%' in html
    assert '0.2143' in html
    assert '1.47%' in html
    assert '4-Player Match Impact (Strict Walk-Forward)' in html

    # 4. Ensure user manual copy in philosophy cards remains 100% intact
    assert 'When two opponents meet in a match, given the results we have seen these opponents achieve in the past, what is the expected outcome of the match?' in html
    assert 'Well, i think it is somewhat impossible to compare the number to out of context brier scores.' in html


