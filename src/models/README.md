# Rating Engines & Calibration Framework (`src/models`)

This directory contains the mathematical rating models, Bayesian updating algorithms, and empirical evaluation suites powering the **Through the Ages (TTA) Rating Portal**.

---

## 1. Architecture Overview

Five distinct rating engines are implemented and evaluated against 388,493 competitive pairwise encounters:

```
[Raw Match Logs] ──> [Format Filtering (Duel / 3P / 4P)]
                            │
       ┌────────────────────┼────────────────────┬────────────────────┐
       ▼                    ▼                    ▼                    ▼
[Glicko-2 Standard]  [Glicko-2 MP]      [Glicko-2 Adapt-T]    [Whole-History (WHR)]
                            │
                            ▼
              [👑 GlickoD (Gold Standard)]
              - Bilateral Composite Variance g(c)
              - Golden Ratio (phi) Weighting
              - 15-Game Emergent Prior Recalibration
              - Gaussian Tail Season Reset
```

---

## 2. Model Directory Structure

- `glicko2/` &mdash; Glicko-2 based engines:
  - `glicko2_daneo.py`: The gold-standard production engine developed by DANeo.
  - `glicko2_base.py`: Mark Glickman's baseline Glicko-2 specification.
  - `glicko2_mp.py`: Multiplayer rank-weighted Glicko-2 variant.
  - `glicko2_adapt.py`: Adaptive temperature scaling variant.
- `whr/` &mdash; Whole-History Rating:
  - `whr_engine.py`: Dynamic Bradley-Terry model with backward-forward Gibbs and Newton-Raphson smoothing across historical game networks.
- `evaluation/` &mdash; Empirical validation suite:
  - `walk_forward.py`: Out-of-sample monthly walk-forward backtesting (56 windows, 2022&ndash;2026).
  - `metrics.py`: Calculation of Brier score, Log Loss, and Expected Calibration Error (ECE).
  - `calibration_bins.py`: Evaluation of 10 confidence bins ($B_1, \dots, B_{10}$) for Soll vs. Ist reliability analysis.

---

## 3. Mathematical Formulations

### GlickoD Bilateral Composite Variance $g(c)$

In standard Glicko-2, variance impact $g(RD)$ depends only on the opponent's rating deviation. In GlickoD, bilateral composite variance is evaluated across both competitors:

$$
c = \sqrt{RD_i^2 + RD_j^2}
$$

$$
g(c) = \frac{1}{\sqrt{1 + \frac{3 q^2 c^2}{\pi^2}}}, \quad q = \frac{\ln 10}{400}
$$

### Golden Ratio ($\phi$) Multiplayer Weighting

For $N$-player board games ($N \in \{3, 4\}$), pairwise outcomes are weighted by finishing position differentials damped by powers of the Golden Ratio $\phi \approx 1.618$:

$$
w_{jk} = \phi^{-(k - j)} = \left(\frac{\sqrt{5}-1}{2}\right)^{k - j}
$$

### Conservative Rating ($C$)

To prevent provisional inflation and rank-camping, the primary competitive leaderboard ranks competitors by their $95\%$ lower-bound confidence rating:

$$
C = R - 2 \cdot RD
$$

### Gaussian Tail Season Reset

Annual seasonal resets preserve median competitors ($\mu \approx 1500$) while gently deflating extreme outlier inertia:

$$
z = \frac{\mu - \mu_0}{\sigma_{\mathrm{pop}}} = \frac{\mu - 1500.0}{175.0}
$$

$$
\tau(z) = 1.0 - \exp\left(-\frac{z^2}{2\phi}\right) \in [0.0, 1.0]
$$

$$
\alpha(z) = 1.0 + (\phi - 1) \cdot \tau(z) \cdot 0.5
$$

$$
\lambda(z) = 1.0 + \phi^{-1} \cdot \tau(z) \cdot 0.5
$$

---

## 4. Empirical Benchmark Results

Out-of-sample walk-forward validation across 308,000+ match predictions:

| Model Configuration | Brier Score ($\downarrow$) | Log Loss ($\downarrow$) | ECE ($\downarrow$) | Accuracy ($\uparrow$) |
|---|---|---|---|---|
| **👑 GlickoD (Continuous)** | **0.2081** | **0.6066** | **0.34%** | **66.12%** |
| **👑 GlickoD (Season Reset)** | **0.2081** | **0.6065** | **0.24%** | **66.13%** |
| Glicko-2 Adaptive-T | 0.2088 | 0.6083 | 0.82% | 65.84% |
| Whole-History Rating (WHR) | 0.2091 | 0.6092 | 1.15% | 65.70% |
| Glicko-2 Standard | 0.2104 | 0.6128 | 3.80% | 65.25% |

---

## 5. Usage

To run full walk-forward calibration across all models:

```bash
python -m src.models.evaluation.walk_forward
```
