# Concept: Player Case Studies & Model Dynamics in Practice

> **Archival Note**: Extracted from `src/web/templates/faq.html` on 2026-09-17 to declutter the core FAQ & Model Guide.
> Preserved for recycling into future dedicated analysis subpages, documentation deep-dives, or interactive player profiles.

---

## Overview
This concept document preserves the 10 empirical player case studies illustrating how **Glicko-2 Standard**, **Glicko-2 MP-Weighted**, **Glicko-2 Adaptive-T**, and **Whole-History Rating (WHR)** respond to real-world competitive phenomena:
1. **SandHippo**: Multi-year hiatus (790 days), burst-play temporal decoupling, Brownian bridge recovery.
2. **Weidenbaum**: Massive sample asymptotic convergence (1,488+ games), Grandmaster stability.
3. **Martin_Pecheur**: Inactivity variance expansion ($\sigma 	o 350$), multiplayer fractional weighting.
4. **Ender_Wiggin**: Fractional evidence vs explosive certainty in high-stakes 4-player lobbies.
5. **Dan_eo**: Multi-model career trajectory across competitive tournament play.
6. **Tianren**: Historical retrospection vs forward chronological stamping.
7. **PV4**: Rating volatility damping and calibration stability.
8. **Lemmingsplayer**: Early career exploration vs high-volume parameter settling.
9. **LCFYX**: Multi-format transition dynamics (2-player duel vs 4-player multiplayer).
10. **Megumi**: Active ladder forward drift, Brownian motion expansion, objective title defense.

---

## Original Template Markup & Content

```html
<!-- ========================================================================= -->
  <!-- TAB 7: PLAYER CASE STUDIES                                                -->
  <!-- ========================================================================= -->

<div id="faq-casestudies" class="faq-section">
    {% set block_casestudies_intro = get_cms('faq', 'casestudies_intro', 'Player Case Studies: Model Dynamics in Practice') %}
    <div class="faq-card cms-card" data-page="faq" data-block="casestudies_intro" data-is-custom="{{ 'true' if block_casestudies_intro.is_custom else 'false' }}" style="border-left: 4px solid var(--accent-gold); background: linear-gradient(135deg, rgba(35, 20, 10, 0.95), rgba(20, 12, 6, 0.95)); margin-bottom: 1.5rem;">
      <h3 class="cms-title"  style="color: #ffde8a; font-size: 1.35rem; margin-top: 0;">{{ block_casestudies_intro.title }}</h3>
      <div class="cms-content">
        {% if block_casestudies_intro.is_custom %}
          {{ block_casestudies_intro.content }}
        {% else %}
          <p>
        Comparing rating trajectories across <strong>Glicko-2 Standard</strong>, <strong>Glicko-2 MP-Weighted</strong>, and <strong>Whole-History Rating (WHR)</strong> provides deep insight into how different rating algorithms behave under real-world competitive conditions.
      </p>
      <p style="margin-bottom: 0.85rem;">
        Below are 10 in-depth case studies of prominent players and community figures, examining foundational phenomena such as <em>burst-play hiatus plateaus and graph cliffs</em>, <em>asymptotic convergence across massive samples</em>, <em>multiplayer fractional variance weighting</em>, <em>global network transitivity</em>, and <em>inactivity variance expansion</em>.
      </p>
      <div style="background: rgba(14, 9, 6, 0.85); border: 1px solid rgba(229, 169, 60, 0.35); border-left: 3px solid var(--accent-gold); padding: 0.75rem 1rem; border-radius: 4px; margin-top: 0.85rem;">
        <strong style="color: #ffd700; font-family: var(--font-subheading); font-size: 0.95rem; display: block; margin-bottom: 0.25rem;">
          📜 Note from the Webmaster
        </strong>
        <p style="margin: 0; font-size: 0.92rem; font-style: italic; color: #cfbeab; line-height: 1.6;">
          &ldquo;Beware &ndash; this has been written by AI. I am not certain the explanations are overall coherent, but i thought it's still fun to leave this in. If you want a Casestudy made for yourself, just let me know.&rdquo;
        </p>
      </div>
        {% endif %}
      </div>
      <template class="cms-default-source" style="display:none;">
        <p>
        Comparing rating trajectories across <strong>Glicko-2 Standard</strong>, <strong>Glicko-2 MP-Weighted</strong>, and <strong>Whole-History Rating (WHR)</strong> provides deep insight into how different rating algorithms behave under real-world competitive conditions.
      </p>
      <p style="margin-bottom: 0.85rem;">
        Below are 10 in-depth case studies of prominent players and community figures, examining foundational phenomena such as <em>burst-play hiatus plateaus and graph cliffs</em>, <em>asymptotic convergence across massive samples</em>, <em>multiplayer fractional variance weighting</em>, <em>global network transitivity</em>, and <em>inactivity variance expansion</em>.
      </p>
      <div style="background: rgba(14, 9, 6, 0.85); border: 1px solid rgba(229, 169, 60, 0.35); border-left: 3px solid var(--accent-gold); padding: 0.75rem 1rem; border-radius: 4px; margin-top: 0.85rem;">
        <strong style="color: #ffd700; font-family: var(--font-subheading); font-size: 0.95rem; display: block; margin-bottom: 0.25rem;">
          📜 Note from the Webmaster
        </strong>
        <p style="margin: 0; font-size: 0.92rem; font-style: italic; color: #cfbeab; line-height: 1.6;">
          &ldquo;Beware &ndash; this has been written by AI. I am not certain the explanations are overall coherent, but i thought it's still fun to leave this in. If you want a Casestudy made for yourself, just let me know.&rdquo;
        </p>
      </div>
      </template>
    </div>

    <!-- 1. SandHippo -->
    {% set block_casestudies_sandhippo = get_cms('faq', 'casestudies_sandhippo', 'SandHippo Case Study') %}
    <div class="faq-card cms-card" data-page="faq" data-block="casestudies_sandhippo" data-is-custom="{{ 'true' if block_casestudies_sandhippo.is_custom else 'false' }}">
      <h4  class="cms-title case-study-title">{{ block_casestudies_sandhippo.title }}</h4>
      <div class="cms-content">
        {% if block_casestudies_sandhippo.is_custom %}
          {{ block_casestudies_sandhippo.content }}
        {% else %}
          <a href="/player/SandHippo" class="btn btn-sm btn-outline-warning" style="padding: 0.25rem 0.75rem; font-size: 0.85rem; border-color: rgba(218, 165, 32, 0.5); color: #f7dfa5;">
          View Full Profile &raquo;
        </a>
      </div>
      <div class="case-study-stats-grid">
        <div class="case-stat-box">
          <span class="case-stat-label">Career Record</span>
          <span class="case-stat-val">61 Matches</span>
          <span class="case-stat-sub">77.1% Win Rate</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 Standard</span>
          <span class="case-stat-val">2034.64 &plusmn; 51.04</span>
          <span class="case-stat-sub">C: 1881.52 &bull; Rank #13</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 MP-Weighted</span>
          <span class="case-stat-val">2021.62 &plusmn; 54.19</span>
          <span class="case-stat-sub">C: 1859.05 &bull; Rank #9</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Whole-History Rating</span>
          <span class="case-stat-val" style="color: #ffe082;">1965.19 &plusmn; 45.96</span>
          <span class="case-stat-sub" style="color: #81c784;">C: 1827.30 &bull; Rank #8</span>
        </div>
      </div>
      <div class="case-analysis-block">
        <strong>Key Phenomenon: Burst-Play Temporal Decoupling, Hiatus Plateaus &amp; The "Wild Swings" Interpretation</strong>
        <p>
          SandHippo is one of the strongest competitors on the portal, boasting a phenomenal 77.1% win rate over 61 matches and ranking in the global elite (#8 active WHR, with a historical peak C-Rating of 1928.30). However, their WHR rating graph appears to feature steep steps and abrupt plateaus. How should this be interpreted?
        </p>
        <ul class="faq-list">
          <li>
            <strong>Burst-Play Cadence:</strong> SandHippo did not play an even, week-in week-out schedule. Instead, they competed in intensive, high-stakes tournament bursts separated by massive hiatuses (including an extended <strong>790-day hiatus</strong> and a 340-day hiatus).
          </li>
          <li>
            <strong>Natural Uncertainty Growth (<a href="https://en.wikipedia.org/wiki/Wiener_process" class="faq-link" target="_blank" rel="noopener noreferrer">Brownian Motion</a>):</strong> WHR models skill drift via continuous Brownian motion:
            <div class="faq-formula">
              $$\mathrm{Var}(r_{t + \Delta t} - r_t) = w^2 \cdot \Delta t$$
            </div>
            Across 790 days of absence, skill uncertainty expands smoothly ($790 \times w^2$). With our Golden Attenuation Kernel, multi-year absences decouple earlier tournament eras from later ones. This allows WHR to evaluate their skill in each era independently, rather than forcing artificial inertia between them.
          </li>
          <li>
            <strong>The Visual "Cliff" Artifact:</strong> Rating charts plot points on the specific dates games were played. When a player takes a 2-year break, the charting library draws a straight connecting line between the final match before the hiatus and the first match upon returning. What looks like a sudden "jump" or wild swing is simply the visual connection across 2+ years of unrecorded time where the player returned at world-class strength.
          </li>
          <li>
            <strong>Sequential Lag vs. Retrospective Precision:</strong> In Glicko-2, post-hiatus uncertainty causes ratings to update cautiously, taking many games to catch up. WHR evaluates the whole career simultaneously: because SandHippo defeated top-tier rivals immediately upon returning, WHR rapidly confirms their world-class ability in that era.
          </li>
        </ul>
      </div>
        {% endif %}
      </div>
      <template class="cms-default-source" style="display:none;">
        <a href="/player/SandHippo" class="btn btn-sm btn-outline-warning" style="padding: 0.25rem 0.75rem; font-size: 0.85rem; border-color: rgba(218, 165, 32, 0.5); color: #f7dfa5;">
          View Full Profile &raquo;
        </a>
      </div>
      <div class="case-study-stats-grid">
        <div class="case-stat-box">
          <span class="case-stat-label">Career Record</span>
          <span class="case-stat-val">61 Matches</span>
          <span class="case-stat-sub">77.1% Win Rate</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 Standard</span>
          <span class="case-stat-val">2034.64 &plusmn; 51.04</span>
          <span class="case-stat-sub">C: 1881.52 &bull; Rank #13</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 MP-Weighted</span>
          <span class="case-stat-val">2021.62 &plusmn; 54.19</span>
          <span class="case-stat-sub">C: 1859.05 &bull; Rank #9</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Whole-History Rating</span>
          <span class="case-stat-val" style="color: #ffe082;">1965.19 &plusmn; 45.96</span>
          <span class="case-stat-sub" style="color: #81c784;">C: 1827.30 &bull; Rank #8</span>
        </div>
      </div>
      <div class="case-analysis-block">
        <strong>Key Phenomenon: Burst-Play Temporal Decoupling, Hiatus Plateaus &amp; The "Wild Swings" Interpretation</strong>
        <p>
          SandHippo is one of the strongest competitors on the portal, boasting a phenomenal 77.1% win rate over 61 matches and ranking in the global elite (#8 active WHR, with a historical peak C-Rating of 1928.30). However, their WHR rating graph appears to feature steep steps and abrupt plateaus. How should this be interpreted?
        </p>
        <ul class="faq-list">
          <li>
            <strong>Burst-Play Cadence:</strong> SandHippo did not play an even, week-in week-out schedule. Instead, they competed in intensive, high-stakes tournament bursts separated by massive hiatuses (including an extended <strong>790-day hiatus</strong> and a 340-day hiatus).
          </li>
          <li>
            <strong>Natural Uncertainty Growth (<a href="https://en.wikipedia.org/wiki/Wiener_process" class="faq-link" target="_blank" rel="noopener noreferrer">Brownian Motion</a>):</strong> WHR models skill drift via continuous Brownian motion:
            <div class="faq-formula">
              $$\mathrm{Var}(r_{t + \Delta t} - r_t) = w^2 \cdot \Delta t$$
            </div>
            Across 790 days of absence, skill uncertainty expands smoothly ($790 \times w^2$). With our Golden Attenuation Kernel, multi-year absences decouple earlier tournament eras from later ones. This allows WHR to evaluate their skill in each era independently, rather than forcing artificial inertia between them.
          </li>
          <li>
            <strong>The Visual "Cliff" Artifact:</strong> Rating charts plot points on the specific dates games were played. When a player takes a 2-year break, the charting library draws a straight connecting line between the final match before the hiatus and the first match upon returning. What looks like a sudden "jump" or wild swing is simply the visual connection across 2+ years of unrecorded time where the player returned at world-class strength.
          </li>
          <li>
            <strong>Sequential Lag vs. Retrospective Precision:</strong> In Glicko-2, post-hiatus uncertainty causes ratings to update cautiously, taking many games to catch up. WHR evaluates the whole career simultaneously: because SandHippo defeated top-tier rivals immediately upon returning, WHR rapidly confirms their world-class ability in that era.
          </li>
        </ul>
      </div>
      </template>
    </div>

    <!-- 2. Weidenbaum -->
    {% set block_casestudies_weidenbaum = get_cms('faq', 'casestudies_weidenbaum', 'Weidenbaum GM Case Study') %}
    <div class="faq-card cms-card" data-page="faq" data-block="casestudies_weidenbaum" data-is-custom="{{ 'true' if block_casestudies_weidenbaum.is_custom else 'false' }}">
      <h4  class="cms-title case-study-title">{{ block_casestudies_weidenbaum.title }}</h4>
      <div class="cms-content">
        {% if block_casestudies_weidenbaum.is_custom %}
          {{ block_casestudies_weidenbaum.content }}
        {% else %}
          <a href="/player/Weidenbaum" class="btn btn-sm btn-outline-warning" style="padding: 0.25rem 0.75rem; font-size: 0.85rem; border-color: rgba(218, 165, 32, 0.5); color: #f7dfa5;">
          View Full Profile &raquo;
        </a>
      </div>
      <div class="case-study-stats-grid">
        <div class="case-stat-box">
          <span class="case-stat-label">Career Record</span>
          <span class="case-stat-val">1,315 Matches</span>
          <span class="case-stat-sub">67.0% Win Rate</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 Standard</span>
          <span class="case-stat-val">1966.57 &plusmn; 20.00</span>
          <span class="case-stat-sub">C: 1906.57 &bull; Rank #5</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 MP-Weighted</span>
          <span class="case-stat-val">1968.34 &plusmn; 23.51</span>
          <span class="case-stat-sub">C: 1897.82 &bull; Rank #2</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Whole-History Rating</span>
          <span class="case-stat-val">1929.78 &plusmn; 21.21</span>
          <span class="case-stat-sub">C: 1866.15 &bull; Rank #3</span>
        </div>
      </div>
      <div class="case-analysis-block">
        <strong>Key Phenomenon: Large-Sample Asymptotic Convergence (The Law of Large Numbers in Rating Theory)</strong>
        <p>
          Weidenbaum provides empirical proof of rating system consistency. Across a staggering 1,315 opponent encounters with a 67.0% win rate and steady competitive activity:
        </p>
        <ul class="faq-list">
          <li>
            <strong>Model Agreement Across Paradigms:</strong> All three mathematical algorithms converge within a tight band:
            <div class="faq-formula">
              $$1966.57 \text{ (Glicko Std)} \;\approx\; 1968.34 \text{ (Glicko MP)} \;\approx\; 1929.78 \text{ (WHR)}$$
            </div>
          </li>
          <li>
            <strong>The Law of Large Numbers:</strong> Under the <a href="https://en.wikipedia.org/wiki/Law_of_large_numbers" class="faq-link" target="_blank" rel="noopener noreferrer">Law of Large Numbers</a>, when match volume is high and activity is consistent, sequential estimation (Glicko) and global retrospective smoothing (WHR) arrive at the exact same physical truth.
          </li>
          <li>
            <strong>Uncertainty Floor:</strong> For all three models, Rating Deviation has reached its theoretical minimum floor ($\mathrm{RD} \approx 20.00$), confirming statistical certainty in Weidenbaum's standing as one of the greatest TTA players of all time.
          </li>
        </ul>
      </div>
        {% endif %}
      </div>
      <template class="cms-default-source" style="display:none;">
        <a href="/player/Weidenbaum" class="btn btn-sm btn-outline-warning" style="padding: 0.25rem 0.75rem; font-size: 0.85rem; border-color: rgba(218, 165, 32, 0.5); color: #f7dfa5;">
          View Full Profile &raquo;
        </a>
      </div>
      <div class="case-study-stats-grid">
        <div class="case-stat-box">
          <span class="case-stat-label">Career Record</span>
          <span class="case-stat-val">1,315 Matches</span>
          <span class="case-stat-sub">67.0% Win Rate</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 Standard</span>
          <span class="case-stat-val">1966.57 &plusmn; 20.00</span>
          <span class="case-stat-sub">C: 1906.57 &bull; Rank #5</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 MP-Weighted</span>
          <span class="case-stat-val">1968.34 &plusmn; 23.51</span>
          <span class="case-stat-sub">C: 1897.82 &bull; Rank #2</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Whole-History Rating</span>
          <span class="case-stat-val">1929.78 &plusmn; 21.21</span>
          <span class="case-stat-sub">C: 1866.15 &bull; Rank #3</span>
        </div>
      </div>
      <div class="case-analysis-block">
        <strong>Key Phenomenon: Large-Sample Asymptotic Convergence (The Law of Large Numbers in Rating Theory)</strong>
        <p>
          Weidenbaum provides empirical proof of rating system consistency. Across a staggering 1,315 opponent encounters with a 67.0% win rate and steady competitive activity:
        </p>
        <ul class="faq-list">
          <li>
            <strong>Model Agreement Across Paradigms:</strong> All three mathematical algorithms converge within a tight band:
            <div class="faq-formula">
              $$1966.57 \text{ (Glicko Std)} \;\approx\; 1968.34 \text{ (Glicko MP)} \;\approx\; 1929.78 \text{ (WHR)}$$
            </div>
          </li>
          <li>
            <strong>The Law of Large Numbers:</strong> Under the <a href="https://en.wikipedia.org/wiki/Law_of_large_numbers" class="faq-link" target="_blank" rel="noopener noreferrer">Law of Large Numbers</a>, when match volume is high and activity is consistent, sequential estimation (Glicko) and global retrospective smoothing (WHR) arrive at the exact same physical truth.
          </li>
          <li>
            <strong>Uncertainty Floor:</strong> For all three models, Rating Deviation has reached its theoretical minimum floor ($\mathrm{RD} \approx 20.00$), confirming statistical certainty in Weidenbaum's standing as one of the greatest TTA players of all time.
          </li>
        </ul>
      </div>
      </template>
    </div>

    <!-- 3. Martin_Pecheur -->
    {% set block_casestudies_martin_pecheur = get_cms('faq', 'casestudies_martin_pecheur', 'Martin_Pecheur GM Case Study') %}
    <div class="faq-card cms-card" data-page="faq" data-block="casestudies_martin_pecheur" data-is-custom="{{ 'true' if block_casestudies_martin_pecheur.is_custom else 'false' }}">
      <h4  class="cms-title case-study-title">{{ block_casestudies_martin_pecheur.title }}</h4>
      <div class="cms-content">
        {% if block_casestudies_martin_pecheur.is_custom %}
          {{ block_casestudies_martin_pecheur.content }}
        {% else %}
          <a href="/player/Martin_Pecheur" class="btn btn-sm btn-outline-warning" style="padding: 0.25rem 0.75rem; font-size: 0.85rem; border-color: rgba(218, 165, 32, 0.5); color: #f7dfa5;">
          View Full Profile &raquo;
        </a>
      </div>
      <div class="case-study-stats-grid">
        <div class="case-stat-box">
          <span class="case-stat-label">Career Record</span>
          <span class="case-stat-val">1,420 Matches</span>
          <span class="case-stat-sub">65.7% Win Rate</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 Standard</span>
          <span class="case-stat-val">1963.24 &plusmn; 20.00</span>
          <span class="case-stat-sub">C: 1903.24 &bull; Rank #7</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 MP-Weighted</span>
          <span class="case-stat-val">1955.47 &plusmn; 22.94</span>
          <span class="case-stat-sub">C: 1886.66 &bull; Rank #5</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Whole-History Rating</span>
          <span class="case-stat-val" style="color: #ffe082;">1971.22 &plusmn; 12.29</span>
          <span class="case-stat-sub" style="color: #81c784;">C: 1934.35 &bull; Rank #1</span>
        </div>
      </div>
      <div class="case-analysis-block">
        <strong>Key Phenomenon: Championship Playoff Density &amp; Global Skill Transitivity</strong>
        <p>
          Martin_Pecheur has 1,420 recorded matches with a 65.7% win rate. While their Glicko-2 ratings are virtually indistinguishable from Weidenbaum's (~1963 vs ~1966), WHR awards Martin_Pecheur <strong>1971.22 (#1 in the world in WHR)</strong>. Why does WHR give Martin_Pecheur the top crown?
        </p>
        <ul class="faq-list">
          <li>
            <strong>Evaluating Opponents of Opponents:</strong> Glicko-2 evaluates games period-by-period based solely on an opponent's rating at that moment. WHR constructs a global interconnected graph of all 131,000 matches.
          </li>
          <li>
            <strong>Diamond Playoff Density:</strong> Martin_Pecheur's tournament history was concentrated against players in elite Diamond playoff brackets who themselves achieved dominant records against the rest of the world.
          </li>
          <li>
            <strong>Strength of Schedule:</strong> When those playoff opponents went on to win other leagues, WHR retroactively confirmed their exceptional strength, recognizing that Martin_Pecheur faced the most demanding schedule of opponents in competitive TTA history.
          </li>
        </ul>
      </div>
        {% endif %}
      </div>
      <template class="cms-default-source" style="display:none;">
        <a href="/player/Martin_Pecheur" class="btn btn-sm btn-outline-warning" style="padding: 0.25rem 0.75rem; font-size: 0.85rem; border-color: rgba(218, 165, 32, 0.5); color: #f7dfa5;">
          View Full Profile &raquo;
        </a>
      </div>
      <div class="case-study-stats-grid">
        <div class="case-stat-box">
          <span class="case-stat-label">Career Record</span>
          <span class="case-stat-val">1,420 Matches</span>
          <span class="case-stat-sub">65.7% Win Rate</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 Standard</span>
          <span class="case-stat-val">1963.24 &plusmn; 20.00</span>
          <span class="case-stat-sub">C: 1903.24 &bull; Rank #7</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 MP-Weighted</span>
          <span class="case-stat-val">1955.47 &plusmn; 22.94</span>
          <span class="case-stat-sub">C: 1886.66 &bull; Rank #5</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Whole-History Rating</span>
          <span class="case-stat-val" style="color: #ffe082;">1971.22 &plusmn; 12.29</span>
          <span class="case-stat-sub" style="color: #81c784;">C: 1934.35 &bull; Rank #1</span>
        </div>
      </div>
      <div class="case-analysis-block">
        <strong>Key Phenomenon: Championship Playoff Density &amp; Global Skill Transitivity</strong>
        <p>
          Martin_Pecheur has 1,420 recorded matches with a 65.7% win rate. While their Glicko-2 ratings are virtually indistinguishable from Weidenbaum's (~1963 vs ~1966), WHR awards Martin_Pecheur <strong>1971.22 (#1 in the world in WHR)</strong>. Why does WHR give Martin_Pecheur the top crown?
        </p>
        <ul class="faq-list">
          <li>
            <strong>Evaluating Opponents of Opponents:</strong> Glicko-2 evaluates games period-by-period based solely on an opponent's rating at that moment. WHR constructs a global interconnected graph of all 131,000 matches.
          </li>
          <li>
            <strong>Diamond Playoff Density:</strong> Martin_Pecheur's tournament history was concentrated against players in elite Diamond playoff brackets who themselves achieved dominant records against the rest of the world.
          </li>
          <li>
            <strong>Strength of Schedule:</strong> When those playoff opponents went on to win other leagues, WHR retroactively confirmed their exceptional strength, recognizing that Martin_Pecheur faced the most demanding schedule of opponents in competitive TTA history.
          </li>
        </ul>
      </div>
      </template>
    </div>

    <!-- 4. Ender_Wiggin -->
    {% set block_casestudies_ender_wiggin = get_cms('faq', 'casestudies_ender_wiggin', 'Ender_Wiggin Case Study') %}
    <div class="faq-card cms-card" data-page="faq" data-block="casestudies_ender_wiggin" data-is-custom="{{ 'true' if block_casestudies_ender_wiggin.is_custom else 'false' }}">
      <h4  class="cms-title case-study-title">{{ block_casestudies_ender_wiggin.title }}</h4>
      <div class="cms-content">
        {% if block_casestudies_ender_wiggin.is_custom %}
          {{ block_casestudies_ender_wiggin.content }}
        {% else %}
          <a href="/player/Ender_Wiggin" class="btn btn-sm btn-outline-warning" style="padding: 0.25rem 0.75rem; font-size: 0.85rem; border-color: rgba(218, 165, 32, 0.5); color: #f7dfa5;">
          View Full Profile &raquo;
        </a>
      </div>
      <div class="case-study-stats-grid">
        <div class="case-stat-box">
          <span class="case-stat-label">Career Record</span>
          <span class="case-stat-val">66 Matches</span>
          <span class="case-stat-sub">62.1% Win Rate</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 Standard</span>
          <span class="case-stat-val">1778.92 &plusmn; 51.47</span>
          <span class="case-stat-sub">C: 1624.51 &bull; Rank #421</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 MP-Weighted</span>
          <span class="case-stat-val">1919.03 &plusmn; 59.80</span>
          <span class="case-stat-sub">C: 1739.64 &bull; Rank #94</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Whole-History Rating</span>
          <span class="case-stat-val" style="color: #ffe082;">2076.74 &plusmn; 67.71</span>
          <span class="case-stat-sub" style="color: #81c784;">Peak C: 1873.62 &bull; Active: #1074</span>
        </div>
      </div>
      <div class="case-analysis-block">
        <strong>Key Phenomenon: Historical Era Anchoring, The Time Machine Problem &amp; Golden Retrospective Decay ($1/\phi$)</strong>
        <p>
          Ender_Wiggin competed in 2022 and subsequently retired, providing the prime demonstration of why modern rating systems need <strong>retrospective lookahead attenuation</strong> and <strong>active leaderboard forward projection</strong>:
        </p>
        <ul class="faq-list">
          <li>
            <strong>The Naive WHR Time Machine Trap:</strong> In 2022, Ender defeated developing talents (including SandHippo and vanishadow). When those opponents became 2100-rated titans years later in 2025–2026, standard unbounded WHR allowed that future mastery to leak backward into 2022, artificially boosting Ender's peak rating to 2164 as if Ender had beaten peak 2100 grandmasters.
          </li>
          <li>
            <strong>The Golden Retrospective Solution:</strong> Using our <a href="https://en.wikipedia.org/wiki/Golden_ratio" class="faq-link" target="_blank" rel="noopener noreferrer">Golden Ratio</a> decay kernel $W(\Delta t) = \phi^{-2 \Delta t / 365.25}$, future lookahead leakage drops below $2.1\%$ after 4 years. This prevents distant modern results from distorting historical tournaments, accurately setting Ender's peak at <strong>2076.74 (Peak C: 1873.62)</strong>.
          </li>
          <li>
            <strong>Automated Leaderboard Defense:</strong> Through $t_{\mathrm{now}}$ forward Brownian projection, Ender's active uncertainty naturally expands during retirement ($\mathrm{RD} \le 350.0$), placing their active standing at rank #1074 while permanently preserving their 2022 peak in their profile timeline.
          </li>
        </ul>
      </div>
        {% endif %}
      </div>
      <template class="cms-default-source" style="display:none;">
        <a href="/player/Ender_Wiggin" class="btn btn-sm btn-outline-warning" style="padding: 0.25rem 0.75rem; font-size: 0.85rem; border-color: rgba(218, 165, 32, 0.5); color: #f7dfa5;">
          View Full Profile &raquo;
        </a>
      </div>
      <div class="case-study-stats-grid">
        <div class="case-stat-box">
          <span class="case-stat-label">Career Record</span>
          <span class="case-stat-val">66 Matches</span>
          <span class="case-stat-sub">62.1% Win Rate</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 Standard</span>
          <span class="case-stat-val">1778.92 &plusmn; 51.47</span>
          <span class="case-stat-sub">C: 1624.51 &bull; Rank #421</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 MP-Weighted</span>
          <span class="case-stat-val">1919.03 &plusmn; 59.80</span>
          <span class="case-stat-sub">C: 1739.64 &bull; Rank #94</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Whole-History Rating</span>
          <span class="case-stat-val" style="color: #ffe082;">2076.74 &plusmn; 67.71</span>
          <span class="case-stat-sub" style="color: #81c784;">Peak C: 1873.62 &bull; Active: #1074</span>
        </div>
      </div>
      <div class="case-analysis-block">
        <strong>Key Phenomenon: Historical Era Anchoring, The Time Machine Problem &amp; Golden Retrospective Decay ($1/\phi$)</strong>
        <p>
          Ender_Wiggin competed in 2022 and subsequently retired, providing the prime demonstration of why modern rating systems need <strong>retrospective lookahead attenuation</strong> and <strong>active leaderboard forward projection</strong>:
        </p>
        <ul class="faq-list">
          <li>
            <strong>The Naive WHR Time Machine Trap:</strong> In 2022, Ender defeated developing talents (including SandHippo and vanishadow). When those opponents became 2100-rated titans years later in 2025–2026, standard unbounded WHR allowed that future mastery to leak backward into 2022, artificially boosting Ender's peak rating to 2164 as if Ender had beaten peak 2100 grandmasters.
          </li>
          <li>
            <strong>The Golden Retrospective Solution:</strong> Using our <a href="https://en.wikipedia.org/wiki/Golden_ratio" class="faq-link" target="_blank" rel="noopener noreferrer">Golden Ratio</a> decay kernel $W(\Delta t) = \phi^{-2 \Delta t / 365.25}$, future lookahead leakage drops below $2.1\%$ after 4 years. This prevents distant modern results from distorting historical tournaments, accurately setting Ender's peak at <strong>2076.74 (Peak C: 1873.62)</strong>.
          </li>
          <li>
            <strong>Automated Leaderboard Defense:</strong> Through $t_{\mathrm{now}}$ forward Brownian projection, Ender's active uncertainty naturally expands during retirement ($\mathrm{RD} \le 350.0$), placing their active standing at rank #1074 while permanently preserving their 2022 peak in their profile timeline.
          </li>
        </ul>
      </div>
      </template>
    </div>

    <!-- 5. DANeo -->
    {% set block_casestudies_daneo = get_cms('faq', 'casestudies_daneo', 'DANeo GM Case Study') %}
    <div class="faq-card cms-card" data-page="faq" data-block="casestudies_daneo" data-is-custom="{{ 'true' if block_casestudies_daneo.is_custom else 'false' }}">
      <h4  class="cms-title case-study-title">{{ block_casestudies_daneo.title }}</h4>
      <div class="cms-content">
        {% if block_casestudies_daneo.is_custom %}
          {{ block_casestudies_daneo.content }}
        {% else %}
          <a href="/player/DANeo" class="btn btn-sm btn-outline-warning" style="padding: 0.25rem 0.75rem; font-size: 0.85rem; border-color: rgba(218, 165, 32, 0.5); color: #f7dfa5;">
          View Full Profile &raquo;
        </a>
      </div>
      <div class="case-study-stats-grid">
        <div class="case-stat-box">
          <span class="case-stat-label">Career Record</span>
          <span class="case-stat-val">716 Matches</span>
          <span class="case-stat-sub">61.9% Win Rate</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 Standard</span>
          <span class="case-stat-val">1898.34 &plusmn; 21.65</span>
          <span class="case-stat-sub">C: 1833.39 &bull; Rank #30</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 MP-Weighted</span>
          <span class="case-stat-val">1904.23 &plusmn; 25.80</span>
          <span class="case-stat-sub">C: 1826.82 &bull; Rank #20</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Whole-History Rating</span>
          <span class="case-stat-val">1790.78 &plusmn; 53.57</span>
          <span class="case-stat-sub">C: 1630.05 &bull; Rank #121</span>
        </div>
      </div>
      <div class="case-analysis-block">
        <strong>Key Phenomenon: High-Volume Championship Play &amp; Retrospective Margin Recalibration</strong>
        <p>
          DANeo is an active competitive Through the Ages player, logging over 700 recorded opponent encounters across major leagues and International Championships with an impressive 61.9% win rate (440 wins, 270 losses).
        </p>
        <ul class="faq-list">
          <li>
            <strong>Sequential Momentum in Glicko-2:</strong> In sequential Glicko-2, deep tournament runs and sustained winning streaks compound forward in time. With low rating deviation ($\mathrm{RD} \approx 21.65$), DANeo holds elite global rankings of <strong>#20 (MP-Weighted)</strong> and <strong>#30 (Standard)</strong>.
          </li>
          <li>
            <strong>Retrospective Global Balancing in WHR:</strong> WHR solves for every player's skill globally using a joint <a href="https://en.wikipedia.org/wiki/Hessian_matrix" class="faq-link" target="_blank" rel="noopener noreferrer">Hessian matrix</a>. Because DANeo regularly competes in large open championship fields against a broad range of opponent skill levels, WHR averages out short-term hot streaks to establish a conservative long-term baseline (#121 active ladder, with an all-time peak rating of 1858).
          </li>
          <li>
            <strong>Distinct Model Roles:</strong> This contrast illustrates the different missions of the systems: Glicko-2 captures current tournament form and in-season momentum, while WHR establishes a conservative, retrospective career foundation.
          </li>
        </ul>
      </div>
        {% endif %}
      </div>
      <template class="cms-default-source" style="display:none;">
        <a href="/player/DANeo" class="btn btn-sm btn-outline-warning" style="padding: 0.25rem 0.75rem; font-size: 0.85rem; border-color: rgba(218, 165, 32, 0.5); color: #f7dfa5;">
          View Full Profile &raquo;
        </a>
      </div>
      <div class="case-study-stats-grid">
        <div class="case-stat-box">
          <span class="case-stat-label">Career Record</span>
          <span class="case-stat-val">716 Matches</span>
          <span class="case-stat-sub">61.9% Win Rate</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 Standard</span>
          <span class="case-stat-val">1898.34 &plusmn; 21.65</span>
          <span class="case-stat-sub">C: 1833.39 &bull; Rank #30</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 MP-Weighted</span>
          <span class="case-stat-val">1904.23 &plusmn; 25.80</span>
          <span class="case-stat-sub">C: 1826.82 &bull; Rank #20</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Whole-History Rating</span>
          <span class="case-stat-val">1790.78 &plusmn; 53.57</span>
          <span class="case-stat-sub">C: 1630.05 &bull; Rank #121</span>
        </div>
      </div>
      <div class="case-analysis-block">
        <strong>Key Phenomenon: High-Volume Championship Play &amp; Retrospective Margin Recalibration</strong>
        <p>
          DANeo is an active competitive Through the Ages player, logging over 700 recorded opponent encounters across major leagues and International Championships with an impressive 61.9% win rate (440 wins, 270 losses).
        </p>
        <ul class="faq-list">
          <li>
            <strong>Sequential Momentum in Glicko-2:</strong> In sequential Glicko-2, deep tournament runs and sustained winning streaks compound forward in time. With low rating deviation ($\mathrm{RD} \approx 21.65$), DANeo holds elite global rankings of <strong>#20 (MP-Weighted)</strong> and <strong>#30 (Standard)</strong>.
          </li>
          <li>
            <strong>Retrospective Global Balancing in WHR:</strong> WHR solves for every player's skill globally using a joint <a href="https://en.wikipedia.org/wiki/Hessian_matrix" class="faq-link" target="_blank" rel="noopener noreferrer">Hessian matrix</a>. Because DANeo regularly competes in large open championship fields against a broad range of opponent skill levels, WHR averages out short-term hot streaks to establish a conservative long-term baseline (#121 active ladder, with an all-time peak rating of 1858).
          </li>
          <li>
            <strong>Distinct Model Roles:</strong> This contrast illustrates the different missions of the systems: Glicko-2 captures current tournament form and in-season momentum, while WHR establishes a conservative, retrospective career foundation.
          </li>
        </ul>
      </div>
      </template>
    </div>

    <!-- 6. tianren4561367 (Tinaren) -->
    {% set block_casestudies_tianren = get_cms('faq', 'casestudies_tianren', 'tianren4561367 (Tinaren) Case Study') %}
    <div class="faq-card cms-card" data-page="faq" data-block="casestudies_tianren" data-is-custom="{{ 'true' if block_casestudies_tianren.is_custom else 'false' }}">
      <h4  class="cms-title case-study-title">{{ block_casestudies_tianren.title }}</h4>
      <div class="cms-content">
        {% if block_casestudies_tianren.is_custom %}
          {{ block_casestudies_tianren.content }}
        {% else %}
          <a href="/player/tianren4561367" class="btn btn-sm btn-outline-warning" style="padding: 0.25rem 0.75rem; font-size: 0.85rem; border-color: rgba(218, 165, 32, 0.5); color: #f7dfa5;">
          View Full Profile &raquo;
        </a>
      </div>
      <div class="case-study-stats-grid">
        <div class="case-stat-box">
          <span class="case-stat-label">Career Record</span>
          <span class="case-stat-val">110 Matches</span>
          <span class="case-stat-sub" style="color: #ffe082;">90.0% Win Rate (99-11)</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 Standard</span>
          <span class="case-stat-val">1940.45 &plusmn; 41.20</span>
          <span class="case-stat-sub">C: 1816.84 &bull; Rank #41</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 MP-Weighted</span>
          <span class="case-stat-val">1935.88 &plusmn; 55.89</span>
          <span class="case-stat-sub">C: 1768.20 &bull; Rank #67</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Whole-History Rating</span>
          <span class="case-stat-val" style="color: #ffe082;">1923.89 &plusmn; 44.30</span>
          <span class="case-stat-sub" style="color: #81c784;">C: 1790.98 &bull; Rank #17</span>
        </div>
      </div>
      <div class="case-analysis-block">
        <strong>Key Phenomenon: Extreme Win-Rate Bayesian Acceleration</strong>
        <p>
          Achieving a <strong>90.0% win rate across 110 tournament matches</strong> (99 wins, only 11 losses) is an extraordinary statistical anomaly in Through the Ages.
        </p>
        <ul class="faq-list">
          <li>
            <strong>Glicko Period Limits:</strong> Glicko-2 uses a volatility limiter $\tau$ to prevent ratings from shooting up too quickly during short hot streaks. Because Tinaren played in concentrated bursts, Glicko-2's step limiter slowed down their climb, resulting in $\mathrm{RD} \approx 41.20$ and a Conservative rank of #41.
          </li>
          <li>
            <strong>WHR Full-Dataset Recognition:</strong> Because WHR evaluates the entire dataset simultaneously, it recognizes that 99 wins in 110 games against competitive tournament fields cannot possibly be luck. WHR rapidly collapses uncertainty down to a peak $\mathrm{RD} = 17.41$, propelling their Conservative Rating to <strong>1871.68 (#17 on the active ladder)</strong>.
          </li>
        </ul>
      </div>
        {% endif %}
      </div>
      <template class="cms-default-source" style="display:none;">
        <a href="/player/tianren4561367" class="btn btn-sm btn-outline-warning" style="padding: 0.25rem 0.75rem; font-size: 0.85rem; border-color: rgba(218, 165, 32, 0.5); color: #f7dfa5;">
          View Full Profile &raquo;
        </a>
      </div>
      <div class="case-study-stats-grid">
        <div class="case-stat-box">
          <span class="case-stat-label">Career Record</span>
          <span class="case-stat-val">110 Matches</span>
          <span class="case-stat-sub" style="color: #ffe082;">90.0% Win Rate (99-11)</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 Standard</span>
          <span class="case-stat-val">1940.45 &plusmn; 41.20</span>
          <span class="case-stat-sub">C: 1816.84 &bull; Rank #41</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 MP-Weighted</span>
          <span class="case-stat-val">1935.88 &plusmn; 55.89</span>
          <span class="case-stat-sub">C: 1768.20 &bull; Rank #67</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Whole-History Rating</span>
          <span class="case-stat-val" style="color: #ffe082;">1923.89 &plusmn; 44.30</span>
          <span class="case-stat-sub" style="color: #81c784;">C: 1790.98 &bull; Rank #17</span>
        </div>
      </div>
      <div class="case-analysis-block">
        <strong>Key Phenomenon: Extreme Win-Rate Bayesian Acceleration</strong>
        <p>
          Achieving a <strong>90.0% win rate across 110 tournament matches</strong> (99 wins, only 11 losses) is an extraordinary statistical anomaly in Through the Ages.
        </p>
        <ul class="faq-list">
          <li>
            <strong>Glicko Period Limits:</strong> Glicko-2 uses a volatility limiter $\tau$ to prevent ratings from shooting up too quickly during short hot streaks. Because Tinaren played in concentrated bursts, Glicko-2's step limiter slowed down their climb, resulting in $\mathrm{RD} \approx 41.20$ and a Conservative rank of #41.
          </li>
          <li>
            <strong>WHR Full-Dataset Recognition:</strong> Because WHR evaluates the entire dataset simultaneously, it recognizes that 99 wins in 110 games against competitive tournament fields cannot possibly be luck. WHR rapidly collapses uncertainty down to a peak $\mathrm{RD} = 17.41$, propelling their Conservative Rating to <strong>1871.68 (#17 on the active ladder)</strong>.
          </li>
        </ul>
      </div>
      </template>
    </div>

    <!-- 7. pv4 -->
    {% set block_casestudies_pv4 = get_cms('faq', 'casestudies_pv4', 'pv4 GM Case Study') %}
    <div class="faq-card cms-card" data-page="faq" data-block="casestudies_pv4" data-is-custom="{{ 'true' if block_casestudies_pv4.is_custom else 'false' }}">
      <h4  class="cms-title case-study-title">{{ block_casestudies_pv4.title }}</h4>
      <div class="cms-content">
        {% if block_casestudies_pv4.is_custom %}
          {{ block_casestudies_pv4.content }}
        {% else %}
          <a href="/player/pv4" class="btn btn-sm btn-outline-warning" style="padding: 0.25rem 0.75rem; font-size: 0.85rem; border-color: rgba(218, 165, 32, 0.5); color: #f7dfa5;">
          View Full Profile &raquo;
        </a>
      </div>
      <div class="case-study-stats-grid">
        <div class="case-stat-box">
          <span class="case-stat-label">Career Record</span>
          <span class="case-stat-val">1,025 Matches</span>
          <span class="case-stat-sub">60.0% Win Rate</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 Standard</span>
          <span class="case-stat-val">1913.53 &plusmn; 20.78</span>
          <span class="case-stat-sub">C: 1851.18 &bull; Rank #22</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 MP-Weighted</span>
          <span class="case-stat-val" style="color: #ffe082;">1920.02 &plusmn; 24.30</span>
          <span class="case-stat-sub" style="color: #81c784;">C: 1847.13 &bull; Rank #14</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Whole-History Rating</span>
          <span class="case-stat-val">1778.83 &plusmn; 21.28</span>
          <span class="case-stat-sub">C: 1715.00 &bull; Rank #48</span>
        </div>
      </div>
      <div class="case-analysis-block">
        <strong>Key Phenomenon: Multiplayer Pairwise Over-Counting vs. Fractional Variance Correction</strong>
        <p>
          pv4 is an elite competitor with over 1,000 matches, specializing heavily in 3-player and 4-player competitive formats.
        </p>
        <ul class="faq-list">
          <li>
            <strong>The Fractional Weighting Advantage:</strong> In Standard Glicko-2, every 4-player match is split into 3 independent duels with full weight ($w=1.0$), artificially compressing rating deviation. When <a href="https://www.remi-coulom.fr/WHR/" class="faq-link" target="_blank" rel="noopener noreferrer">Coulom's fractional weighting</a> ($w = \frac{1}{N-1}$) is applied, pv4's ranking jumps from <strong>#22 up to #14</strong> globally.
          </li>
          <li>
            <strong>Joint Multinomial Modeling in WHR:</strong> WHR applies joint multinomial <a href="https://en.wikipedia.org/wiki/Bradley%E2%80%93Terry_model" class="faq-link" target="_blank" rel="noopener noreferrer">Bradley-Terry models</a> for multiplayer games rather than synthetic pairwise decomposition, properly accounting for multiplayer variance without over-counting outcomes.
          </li>
        </ul>
      </div>
        {% endif %}
      </div>
      <template class="cms-default-source" style="display:none;">
        <a href="/player/pv4" class="btn btn-sm btn-outline-warning" style="padding: 0.25rem 0.75rem; font-size: 0.85rem; border-color: rgba(218, 165, 32, 0.5); color: #f7dfa5;">
          View Full Profile &raquo;
        </a>
      </div>
      <div class="case-study-stats-grid">
        <div class="case-stat-box">
          <span class="case-stat-label">Career Record</span>
          <span class="case-stat-val">1,025 Matches</span>
          <span class="case-stat-sub">60.0% Win Rate</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 Standard</span>
          <span class="case-stat-val">1913.53 &plusmn; 20.78</span>
          <span class="case-stat-sub">C: 1851.18 &bull; Rank #22</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 MP-Weighted</span>
          <span class="case-stat-val" style="color: #ffe082;">1920.02 &plusmn; 24.30</span>
          <span class="case-stat-sub" style="color: #81c784;">C: 1847.13 &bull; Rank #14</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Whole-History Rating</span>
          <span class="case-stat-val">1778.83 &plusmn; 21.28</span>
          <span class="case-stat-sub">C: 1715.00 &bull; Rank #48</span>
        </div>
      </div>
      <div class="case-analysis-block">
        <strong>Key Phenomenon: Multiplayer Pairwise Over-Counting vs. Fractional Variance Correction</strong>
        <p>
          pv4 is an elite competitor with over 1,000 matches, specializing heavily in 3-player and 4-player competitive formats.
        </p>
        <ul class="faq-list">
          <li>
            <strong>The Fractional Weighting Advantage:</strong> In Standard Glicko-2, every 4-player match is split into 3 independent duels with full weight ($w=1.0$), artificially compressing rating deviation. When <a href="https://www.remi-coulom.fr/WHR/" class="faq-link" target="_blank" rel="noopener noreferrer">Coulom's fractional weighting</a> ($w = \frac{1}{N-1}$) is applied, pv4's ranking jumps from <strong>#22 up to #14</strong> globally.
          </li>
          <li>
            <strong>Joint Multinomial Modeling in WHR:</strong> WHR applies joint multinomial <a href="https://en.wikipedia.org/wiki/Bradley%E2%80%93Terry_model" class="faq-link" target="_blank" rel="noopener noreferrer">Bradley-Terry models</a> for multiplayer games rather than synthetic pairwise decomposition, properly accounting for multiplayer variance without over-counting outcomes.
          </li>
        </ul>
      </div>
      </template>
    </div>

    <!-- 8. Lemmingsplayer -->
    {% set block_casestudies_lemmingsplayer = get_cms('faq', 'casestudies_lemmingsplayer', 'Lemmingsplayer GM Case Study') %}
    <div class="faq-card cms-card" data-page="faq" data-block="casestudies_lemmingsplayer" data-is-custom="{{ 'true' if block_casestudies_lemmingsplayer.is_custom else 'false' }}">
      <h4  class="cms-title case-study-title">{{ block_casestudies_lemmingsplayer.title }}</h4>
      <div class="cms-content">
        {% if block_casestudies_lemmingsplayer.is_custom %}
          {{ block_casestudies_lemmingsplayer.content }}
        {% else %}
          <a href="/player/Lemmingsplayer" class="btn btn-sm btn-outline-warning" style="padding: 0.25rem 0.75rem; font-size: 0.85rem; border-color: rgba(218, 165, 32, 0.5); color: #f7dfa5;">
          View Full Profile &raquo;
        </a>
      </div>
      <div class="case-study-stats-grid">
        <div class="case-stat-box">
          <span class="case-stat-label">Career Record</span>
          <span class="case-stat-val">229 Matches</span>
          <span class="case-stat-sub">76.0% Win Rate</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 Standard</span>
          <span class="case-stat-val">1921.05 &plusmn; 31.10</span>
          <span class="case-stat-sub">C: 1827.75 &bull; Rank #32</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 MP-Weighted</span>
          <span class="case-stat-val">1922.35 &plusmn; 40.96</span>
          <span class="case-stat-sub">C: 1799.47 &bull; Rank #32</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Whole-History Rating</span>
          <span class="case-stat-val">1578.15 &plusmn; 240.26</span>
          <span class="case-stat-sub" style="color: #ef5350;">Peak C: 1296.11 &bull; Active: #1309</span>
        </div>
      </div>
      <div class="case-analysis-block">
        <strong>Key Phenomenon: Extended Inactivity Variance Expansion &amp; C-Rating Leaderboard Protection</strong>
        <p>
          Lemmingsplayer is a celebrated Grandmaster with a stellar 76.0% win rate across 229 matches. Yet while they sit at #32 in Glicko-2, their WHR Conservative Rating is at rank #1309 on the active ladder. Why?
        </p>
        <ul class="faq-list">
          <li>
            <strong>Daily Uncertainty Expansion:</strong> During a tournament hiatus, WHR expands uncertainty for every day elapsed without a game:
            <div class="faq-formula">
              $$\sigma^2(t_{\text{now}}) = \sigma^2(t_{\text{last}}) + w^2 \cdot \Delta t$$
            </div>
            At the present day ($t_{\mathrm{now}}$), this causes Lemmingsplayer's uncertainty to expand to $\mathrm{RD} \approx 240.26$.
          </li>
          <li>
            <strong>Conservative Rating Penalty ($3 \times \mathrm{RD}$):</strong> Because Conservative Rating subtracts $3 \times \mathrm{RD}$, this uncertainty expansion deducts $720.8$ points ($1578.15 - 720.8 = 857.36$).
          </li>
          <li>
            <strong>Leaderboard Defense vs. Historical Preservation:</strong> This demonstrates how WHR protects active competitive leaderboards from retired accounts "squatting" on top spots, while permanently preserving their peak historical ratings (Peak C: 1296.11) in their profile history.
          </li>
        </ul>
      </div>
        {% endif %}
      </div>
      <template class="cms-default-source" style="display:none;">
        <a href="/player/Lemmingsplayer" class="btn btn-sm btn-outline-warning" style="padding: 0.25rem 0.75rem; font-size: 0.85rem; border-color: rgba(218, 165, 32, 0.5); color: #f7dfa5;">
          View Full Profile &raquo;
        </a>
      </div>
      <div class="case-study-stats-grid">
        <div class="case-stat-box">
          <span class="case-stat-label">Career Record</span>
          <span class="case-stat-val">229 Matches</span>
          <span class="case-stat-sub">76.0% Win Rate</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 Standard</span>
          <span class="case-stat-val">1921.05 &plusmn; 31.10</span>
          <span class="case-stat-sub">C: 1827.75 &bull; Rank #32</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 MP-Weighted</span>
          <span class="case-stat-val">1922.35 &plusmn; 40.96</span>
          <span class="case-stat-sub">C: 1799.47 &bull; Rank #32</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Whole-History Rating</span>
          <span class="case-stat-val">1578.15 &plusmn; 240.26</span>
          <span class="case-stat-sub" style="color: #ef5350;">Peak C: 1296.11 &bull; Active: #1309</span>
        </div>
      </div>
      <div class="case-analysis-block">
        <strong>Key Phenomenon: Extended Inactivity Variance Expansion &amp; C-Rating Leaderboard Protection</strong>
        <p>
          Lemmingsplayer is a celebrated Grandmaster with a stellar 76.0% win rate across 229 matches. Yet while they sit at #32 in Glicko-2, their WHR Conservative Rating is at rank #1309 on the active ladder. Why?
        </p>
        <ul class="faq-list">
          <li>
            <strong>Daily Uncertainty Expansion:</strong> During a tournament hiatus, WHR expands uncertainty for every day elapsed without a game:
            <div class="faq-formula">
              $$\sigma^2(t_{\text{now}}) = \sigma^2(t_{\text{last}}) + w^2 \cdot \Delta t$$
            </div>
            At the present day ($t_{\mathrm{now}}$), this causes Lemmingsplayer's uncertainty to expand to $\mathrm{RD} \approx 240.26$.
          </li>
          <li>
            <strong>Conservative Rating Penalty ($3 \times \mathrm{RD}$):</strong> Because Conservative Rating subtracts $3 \times \mathrm{RD}$, this uncertainty expansion deducts $720.8$ points ($1578.15 - 720.8 = 857.36$).
          </li>
          <li>
            <strong>Leaderboard Defense vs. Historical Preservation:</strong> This demonstrates how WHR protects active competitive leaderboards from retired accounts "squatting" on top spots, while permanently preserving their peak historical ratings (Peak C: 1296.11) in their profile history.
          </li>
        </ul>
      </div>
      </template>
    </div>

    <!-- 9. Lcfyx -->
    {% set block_casestudies_lcfyx = get_cms('faq', 'casestudies_lcfyx', 'Lcfyx M Case Study') %}
    <div class="faq-card cms-card" data-page="faq" data-block="casestudies_lcfyx" data-is-custom="{{ 'true' if block_casestudies_lcfyx.is_custom else 'false' }}">
      <h4  class="cms-title case-study-title">{{ block_casestudies_lcfyx.title }}</h4>
      <div class="cms-content">
        {% if block_casestudies_lcfyx.is_custom %}
          {{ block_casestudies_lcfyx.content }}
        {% else %}
          <a href="/player/Lcfyx" class="btn btn-sm btn-outline-warning" style="padding: 0.25rem 0.75rem; font-size: 0.85rem; border-color: rgba(218, 165, 32, 0.5); color: #f7dfa5;">
          View Full Profile &raquo;
        </a>
      </div>
      <div class="case-study-stats-grid">
        <div class="case-stat-box">
          <span class="case-stat-label">Career Record</span>
          <span class="case-stat-val">801 Matches</span>
          <span class="case-stat-sub">61.5% Win Rate</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 Standard</span>
          <span class="case-stat-val">1877.34 &plusmn; 22.01</span>
          <span class="case-stat-sub">C: 1811.32 &bull; Rank #42</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 MP-Weighted</span>
          <span class="case-stat-val">1875.24 &plusmn; 26.26</span>
          <span class="case-stat-sub">C: 1796.46 &bull; Rank #36</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Whole-History Rating</span>
          <span class="case-stat-val">1796.46 &plusmn; 30.12</span>
          <span class="case-stat-sub">C: 1706.10 &bull; Rank #53</span>
        </div>
      </div>
      <div class="case-analysis-block">
        <strong>Key Phenomenon: The Community Calibration Anchor (Robust Graph Connectivity)</strong>
        <p>
          With 801 recorded encounters and an exemplary 61.5% win rate, Master Lcfyx is an essential calibration anchor for the entire competitive rating ecosystem.
        </p>
        <ul class="faq-list">
          <li>
            <strong>Bridging Tournament Communities:</strong> In rating systems, players who actively compete across diverse tournaments, seasons, and tiers provide the connective tissue that stabilizes comparisons between different player groups.
          </li>
          <li>
            <strong>Cross-Model Alignment:</strong> Because Lcfyx plays against a broad cross-section of the player base, their ratings across Glicko-2 Standard (1877), Glicko-2 MP-Weighted (1875), and WHR (1796) remain closely aligned, demonstrating how high-connectivity competitors ground the entire system.
          </li>
        </ul>
      </div>
        {% endif %}
      </div>
      <template class="cms-default-source" style="display:none;">
        <a href="/player/Lcfyx" class="btn btn-sm btn-outline-warning" style="padding: 0.25rem 0.75rem; font-size: 0.85rem; border-color: rgba(218, 165, 32, 0.5); color: #f7dfa5;">
          View Full Profile &raquo;
        </a>
      </div>
      <div class="case-study-stats-grid">
        <div class="case-stat-box">
          <span class="case-stat-label">Career Record</span>
          <span class="case-stat-val">801 Matches</span>
          <span class="case-stat-sub">61.5% Win Rate</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 Standard</span>
          <span class="case-stat-val">1877.34 &plusmn; 22.01</span>
          <span class="case-stat-sub">C: 1811.32 &bull; Rank #42</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 MP-Weighted</span>
          <span class="case-stat-val">1875.24 &plusmn; 26.26</span>
          <span class="case-stat-sub">C: 1796.46 &bull; Rank #36</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Whole-History Rating</span>
          <span class="case-stat-val">1796.46 &plusmn; 30.12</span>
          <span class="case-stat-sub">C: 1706.10 &bull; Rank #53</span>
        </div>
      </div>
      <div class="case-analysis-block">
        <strong>Key Phenomenon: The Community Calibration Anchor (Robust Graph Connectivity)</strong>
        <p>
          With 801 recorded encounters and an exemplary 61.5% win rate, Master Lcfyx is an essential calibration anchor for the entire competitive rating ecosystem.
        </p>
        <ul class="faq-list">
          <li>
            <strong>Bridging Tournament Communities:</strong> In rating systems, players who actively compete across diverse tournaments, seasons, and tiers provide the connective tissue that stabilizes comparisons between different player groups.
          </li>
          <li>
            <strong>Cross-Model Alignment:</strong> Because Lcfyx plays against a broad cross-section of the player base, their ratings across Glicko-2 Standard (1877), Glicko-2 MP-Weighted (1875), and WHR (1796) remain closely aligned, demonstrating how high-connectivity competitors ground the entire system.
          </li>
        </ul>
      </div>
      </template>
    </div>

    <!-- 10. megumi -->
    {% set block_casestudies_megumi = get_cms('faq', 'casestudies_megumi', 'megumi Case Study') %}
    <div class="faq-card cms-card" data-page="faq" data-block="casestudies_megumi" data-is-custom="{{ 'true' if block_casestudies_megumi.is_custom else 'false' }}">
      <h4  class="cms-title case-study-title">{{ block_casestudies_megumi.title }}</h4>
      <div class="cms-content">
        {% if block_casestudies_megumi.is_custom %}
          {{ block_casestudies_megumi.content }}
        {% else %}
          <a href="/player/megumi" class="btn btn-sm btn-outline-warning" style="padding: 0.25rem 0.75rem; font-size: 0.85rem; border-color: rgba(218, 165, 32, 0.5); color: #f7dfa5;">
          View Full Profile &raquo;
        </a>
      </div>
      <div class="case-study-stats-grid">
        <div class="case-stat-box">
          <span class="case-stat-label">Career Record</span>
          <span class="case-stat-val">48 Matches</span>
          <span class="case-stat-sub">68.8% Win Rate</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 Standard</span>
          <span class="case-stat-val">1964.64 &plusmn; 55.94</span>
          <span class="case-stat-sub">C: 1796.83 &bull; Rank #55</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 MP-Weighted</span>
          <span class="case-stat-val">1964.54 &plusmn; 56.02</span>
          <span class="case-stat-sub">C: 1796.49 &bull; Rank #35</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Whole-History Rating</span>
          <span class="case-stat-val">1778.54 &plusmn; 240.71</span>
          <span class="case-stat-sub">Peak C: 1726.35 &bull; Active: #1025</span>
        </div>
      </div>
      <div class="case-analysis-block">
        <strong>Key Phenomenon: Sample Scarcity vs. Prior Information Propagation</strong>
        <p>
          megumi played a compact slate of 48 elite matches with an outstanding 68.8% win rate, illustrating how different models handle small samples against high-tier competition.
        </p>
        <ul class="faq-list">
          <li>
            <strong>High Uncertainty in Sequential Systems:</strong> With relatively few games, Glicko-2 retains a wide confidence margin ($\mathrm{RD} = 55.94$). As a result, although megumi's raw rating reaches 1964.64, their Conservative Rating is 1796.83.
          </li>
          <li>
            <strong>Borrowing Certainty in WHR:</strong> WHR takes into account that megumi's opponents had hundreds of other matches defining their skills. By leveraging their established strength, WHR narrowed megumi's peak historical uncertainty to $\mathrm{RD} = 17.40$ (Peak C: 1726.35).
          </li>
          <li>
            <strong>Active Ladder Forward Drift:</strong> Because megumi has not competed recently, forward Brownian motion naturally expands their live uncertainty to $\mathrm{RD} \approx 240.71$, illustrating objective leaderboard defense without erasing historical achievement.
          </li>
        </ul>
      </div>
        {% endif %}
      </div>
      <template class="cms-default-source" style="display:none;">
        <a href="/player/megumi" class="btn btn-sm btn-outline-warning" style="padding: 0.25rem 0.75rem; font-size: 0.85rem; border-color: rgba(218, 165, 32, 0.5); color: #f7dfa5;">
          View Full Profile &raquo;
        </a>
      </div>
      <div class="case-study-stats-grid">
        <div class="case-stat-box">
          <span class="case-stat-label">Career Record</span>
          <span class="case-stat-val">48 Matches</span>
          <span class="case-stat-sub">68.8% Win Rate</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 Standard</span>
          <span class="case-stat-val">1964.64 &plusmn; 55.94</span>
          <span class="case-stat-sub">C: 1796.83 &bull; Rank #55</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Glicko-2 MP-Weighted</span>
          <span class="case-stat-val">1964.54 &plusmn; 56.02</span>
          <span class="case-stat-sub">C: 1796.49 &bull; Rank #35</span>
        </div>
        <div class="case-stat-box">
          <span class="case-stat-label">Whole-History Rating</span>
          <span class="case-stat-val">1778.54 &plusmn; 240.71</span>
          <span class="case-stat-sub">Peak C: 1726.35 &bull; Active: #1025</span>
        </div>
      </div>
      <div class="case-analysis-block">
        <strong>Key Phenomenon: Sample Scarcity vs. Prior Information Propagation</strong>
        <p>
          megumi played a compact slate of 48 elite matches with an outstanding 68.8% win rate, illustrating how different models handle small samples against high-tier competition.
        </p>
        <ul class="faq-list">
          <li>
            <strong>High Uncertainty in Sequential Systems:</strong> With relatively few games, Glicko-2 retains a wide confidence margin ($\mathrm{RD} = 55.94$). As a result, although megumi's raw rating reaches 1964.64, their Conservative Rating is 1796.83.
          </li>
          <li>
            <strong>Borrowing Certainty in WHR:</strong> WHR takes into account that megumi's opponents had hundreds of other matches defining their skills. By leveraging their established strength, WHR narrowed megumi's peak historical uncertainty to $\mathrm{RD} = 17.40$ (Peak C: 1726.35).
          </li>
          <li>
            <strong>Active Ladder Forward Drift:</strong> Because megumi has not competed recently, forward Brownian motion naturally expands their live uncertainty to $\mathrm{RD} \approx 240.71$, illustrating objective leaderboard defense without erasing historical achievement.
          </li>
        </ul>
      </div>
      </template>
    </div>
  </div>
```
