"""Restore user's custom card edits into SQLite database."""
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.db import save_cms_block, get_cms_block

# 1. philosophy_what_is_engine
what_is_engine_md = '''A rating engines main purpose is to answer one central question: "When two opponents meet in a match, given the results we have seen these opponents achieve in the past, what is the expected outcome of the match?"

A rating engine does **not provide information which reflects tournament achievements**
Using it as a community leaderboard is, at least in some sense, missing its point. 
A player going 40 - 2 within his first 42 ranked games will earn a spot in the top 20 (or higher - depending on the engine). In no way has this player already proven that he can, over an extended period of time, consistently beat top lvl opponents. 
But his place there is also not "unearned" - it is the engines current best guess about predicting matches involving that player given the current data. 

This sites engine 'leaderboards' provide a minimum game count filter (among several other filters) which is set to 30 per default. Feel free to provide feedback if another number might be more fitting.

$$
P(\\text{Player A defeats Player B}) = \\frac{1}{1 + 10^{-(r_A - r_B)/400}}
$$

A player's rating ($\\mu$ or $r$) and rating deviation ($\\mathrm{RD}$ or $\\sigma$) have no independent physical existence outside of this formula. They are latent parameters chosen to maximize the likelihood of observed game outcomes. The number $1850$ is not a \u201cbadge of honor\u201d; it is a statistical claim that against a $1750$ opponent, the player has an expected probability of victory of exactly $64.0\\%$.'''

what_is_engine_html = '''<p>A rating engines main purpose is to answer one central question: &quot;When two opponents meet in a match, given the results we have seen these opponents achieve in the past, what is the expected outcome of the match?&quot;</p>
<p>A rating engine does <strong>not provide information which reflects tournament achievements</strong>
Using it as a community leaderboard is, at least in some sense, missing its point. 
A player going 40 - 2 within his first 42 ranked games will earn a spot in the top 20 (or higher - depending on the engine). In no way has this player already proven that he can, over an extended period of time, consistently beat top lvl opponents. 
But his place there is also not &quot;unearned&quot; - it is the engines current best guess about predicting matches involving that player given the current data. </p>
<p>This sites engine &#39;leaderboards&#39; provide a minimum game count filter (among several other filters) which is set to 30 per default. Feel free to provide feedback if another number might be more fitting.</p>
<div class="faq-formula">
$$
P(\\text{Player A defeats Player B}) = \\frac{1}{1 + 10^{-(r_A - r_B)/400}}
$$
</div>
<p>A player&#39;s rating ($\\mu$ or $r$) and rating deviation ($\\mathrm{RD}$ or $\\sigma$) have no independent physical existence outside of this formula. They are latent parameters chosen to maximize the likelihood of observed game outcomes. The number $1850$ is not a \u201cbadge of honor\u201d; it is a statistical claim that against a $1750$ opponent, the player has an expected probability of victory of exactly $64.0\\%$.</p>'''

save_cms_block(
    page_id='faq',
    block_key='philosophy_what_is_engine',
    title='What is a Rating Engine and What Does It Try to Achieve?',
    content_html=what_is_engine_html,
    content_markdown=what_is_engine_md
)

# 2. philosophy_accuracy_goals
accuracy_goals_md = '''Since rating systems exist to predict match outcomes, the question *“Which rating model is best?”* is not a matter of aesthetic taste or community politics. It is a strictly empirical question answered by evaluating how accurately the model predicts unseen future matches:

- **Brier Score (Mean Squared Error ↓):**
  Measures the mean squared difference between predicted win probabilities $P_k$ and actual binary match outcomes $s_k \\in \\{0, 1\\}$:

$$
\\mathrm{Brier} = \\frac{1}{M} \\sum_{k=1}^{M} (P_k - s_k)^2
$$

- **What do the numbers actually mean?**:
Well, i think it is somewhat impossible to compare the number to out of context brier scores. We can first of all observe: The coin flip engine baseline is $0.2500$; Meaning: If we were to allways just guess the winner by coinflip, it would achieve a score of $0.2500$. Evaluating the quality of our engines should be done in a comperative matter: If model A yields Brier of $0.2138$ and model B $0.2314$, that is one indicator for model A performing better at fulfilling its purpose.
        
- **Expected Calibration Error (ECE ↓):**
  Tests whether the model's confidence corresponds to physical reality. If we aggregate all matches where the model predicted a $75\\%$ win chance, did the favorites actually win $75\\%$ of those games? If they only won $68\\%$, the model is systematically overconfident. ECE integrates this calibration gap across all probability bins.
        
- **Walk-Forward Out-of-Sample Validation:**
  Evaluating a model on matches it already saw during parameter fitting produces a false illusion of precision. True predictive validity requires a strict **expanding-window walk-forward test**: ratings are frozen at month $M-1$ to forecast month $M$ matches before any results were observed, spanning over 308,000 out-of-sample predictions across 2022–2026.'''

accuracy_goals_html = '''<p>Since rating systems exist to predict match outcomes, the question <em>\u201cWhich rating model is best?\u201d</em> is not a matter of aesthetic taste or community politics. It is a strictly empirical question answered by evaluating how accurately the model predicts unseen future matches:</p>
<ul>
<li><strong>Brier Score (Mean Squared Error \u2193):</strong>
    Measures the mean squared difference between predicted win probabilities $P_k$ and actual binary match outcomes $s_k \\in \\{0, 1\\}$:</li>
</ul>
<div class="faq-formula">
$$
\\mathrm{Brier} = \\frac{1}{M} \\sum_{k=1}^{M} (P_k - s_k)^2
$$
</div>
<ul>
<li><p><strong>What do the numbers actually mean?</strong>:
Well, i think it is somewhat impossible to compare the number to out of context brier scores. We can first of all observe: The coin flip engine baseline is $0.2500$; Meaning: If we were to allways just guess the winner by coinflip, it would achieve a score of $0.2500$. Evaluating the quality of our engines should be done in a comperative matter: If model A yields Brier of $0.2138$ and model B $0.2314$, that is one indicator for model A performing better at fulfilling its purpose.</p>
</li>
<li><p><strong>Expected Calibration Error (ECE \u2193):</strong>
    Tests whether the model&#39;s confidence corresponds to physical reality. If we aggregate all matches where the model predicted a $75\\%$ win chance, did the favorites actually win $75\\%$ of those games? If they only won $68\\%$, the model is systematically overconfident. ECE integrates this calibration gap across all probability bins.
  </p>
</li>
<li><p><strong>Walk-Forward Out-of-Sample Validation:</strong>
    Evaluating a model on matches it already saw during parameter fitting produces a false illusion of precision. True predictive validity requires a strict <strong>expanding-window walk-forward test</strong>: ratings are frozen at month $M-1$ to forecast month $M$ matches before any results were observed, spanning over 308,000 out-of-sample predictions across 2022\u20132026.</p>
</li>
</ul>'''

save_cms_block(
    page_id='faq',
    block_key='philosophy_accuracy_goals',
    title='Attempts at evalution of an engines predictive capabilities (Brier Score & ECE)',
    content_html=accuracy_goals_html,
    content_markdown=accuracy_goals_md
)

print('Restored philosophy_what_is_engine:', get_cms_block('faq', 'philosophy_what_is_engine') is not None)
print('Restored philosophy_accuracy_goals:', get_cms_block('faq', 'philosophy_accuracy_goals') is not None)
