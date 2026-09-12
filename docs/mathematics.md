# Mathematical Foundations & Rating Formulations

This document provides the formal mathematical derivations for the three rating models implemented in **Through the Ages (TTA) Rating Engine**:
1. **Glicko-2 Standard** (Naive Pairwise 1v1)
2. **Glicko-2 MP-Weighted** (Coulom-Weighted Fractional Pairwise)
3. **Whole-History Rating (WHR)** (Continuous Brownian Motion MAP)

---

## 1. Glicko-2 Standard Formulation

The standard Glicko-2 system (Glickman, 2012) models each player by three parameters:
- Rating $\mu$ (scaled such that $\mu = (r - 1500) / 173.7178$)
- Rating Deviation $\phi$ (scaled such that $\phi = RD / 173.7178$)
- Rating Volatility $\sigma$ (degree of expected rating fluctuations)

### 1.1 Match Likelihood & Expected Outcome
Against an opponent with rating $\mu_j$ and rating deviation $\phi_j$, the expected outcome $E$ is given by:

$$g(\phi_j) = \frac{1}{\sqrt{1 + 3\phi_j^2 / \pi^2}}$$

$$E(\mu, \mu_j, \phi_j) = \frac{1}{1 + \exp(-g(\phi_j)(\mu - \mu_j))}$$

### 1.2 Step Equations (Sequential Update)
For $m$ match encounters in a rating period with observed scores $s_j \in \{1.0, 0.5, 0.0\}$:

1. **Estimated Variance ($v$)**:
   $$v = \left[ \sum_{j=1}^{m} g(\phi_j)^2 E_j (1 - E_j) \right]^{-1}$$

2. **Estimated Improvement ($\Delta$)**:
   $$\Delta = v \sum_{j=1}^{m} g(\phi_j) (s_j - E_j)$$

3. **Volatility Update ($\sigma'$)**:
   Using the Illinois bracket root-finding algorithm, find $x = \ln(\sigma'^2)$ such that $f(x) = 0$, where $a = \ln(\sigma^2)$:
   $$f(x) = \frac{e^x (\Delta^2 - \phi^2 - v - e^x)}{2 (\phi^2 + v + e^x)^2} - \frac{x - a}{\tau^2}$$

4. **New Rating Deviation ($\phi'$) and Mean ($\mu'$)**:
   $$\phi^* = \sqrt{\phi^2 + \sigma'^2}$$
   $$\phi' = \frac{1}{\sqrt{\frac{1}{(\phi^*)^2} + \frac{1}{v}}}$$
   $$\mu' = \mu + (\phi')^2 \sum_{j=1}^{m} g(\phi_j)(s_j - E_j)$$

5. **Conservative Rating**:
   $$C = r - 3 \times RD$$
   This represents the lower 99.7% confidence bound of a player's true skill.

---

## 2. The Multiplayer Flaw & Glicko-2 MP-Weighted Formulation

### 2.1 The Problem with Naive Pairwise Decomposition
In an $N$-player game (e.g. 4-player TTA), a player simultaneously plays against 3 opponents. Naive decomposition treats this single match as $(N - 1) = 3$ independent 1v1 duels.

Because Fisher information $v^{-1} = \sum g^2 E(1-E)$ sums over all opponents, a 4-player match yields **$3\times$ the information of a 2-player match**. 

In the variance equation:
$$\frac{1}{(\phi')^2} = \frac{1}{(\phi^*)^2} + \frac{1}{v}$$
$\frac{1}{v}$ is 3 times larger, meaning the rating deviation $\phi$ shrinks up to $\sqrt{3} \approx 1.73$ times faster than warranted by real game entropy. This causes premature confidence, rating crystallization, and ranking instability when players participate predominantly in 4-player lobbies.

### 2.2 The Coulom Fractional Match Weight Solution
To preserve correct evidence accumulation, each pairwise encounter derived from an $N$-player match is assigned a fractional weight:
$$w_j = \frac{1}{N - 1}$$

- 2-player duel: $N=2 \implies w_j = 1.0$ (Standard Glicko-2)
- 3-player match: $N=3 \implies w_j = 0.5$ (2 opponents $\times 0.5 = 1.0$ effective match)
- 4-player match: $N=4 \implies w_j = \frac{1}{3}$ (3 opponents $\times \frac{1}{3} = 1.0$ effective match)

### 2.3 Mathematical Integration
1. **Weighted Inverted Variance ($v_w^{-1}$)**:
   $$v_w = \left[ \sum_{j=1}^{m} w_j \cdot g(\phi_j)^2 E_j (1 - E_j) \right]^{-1}$$

2. **Weighted Improvement ($\Delta_w$)**:
   $$\Delta_w = v_w \sum_{j=1}^{m} w_j \cdot g(\phi_j) (s_j - E_j)$$

3. **Invariance of Volatility Search**:
   Because $v_w$ scales by $(N - 1)$ and $\sum w_j \dots$ scales by $\frac{1}{N - 1}$, $\Delta_w$ maintains the exact physical magnitude of a standard 2-player duel. Thus, $f(x)$ remains strictly bounded, and Illinois root-finding converges with standard tolerances.

4. **Updated Parameters**:
   $$\frac{1}{(\phi')^2} = \frac{1}{(\phi^*)^2} + \frac{1}{v_w}$$
   $$\mu' = \mu + (\phi')^2 \sum_{j=1}^{m} w_j \cdot g(\phi_j)(s_j - E_j)$$

**Conclusion**: The effective sample size per match event is strictly 1.0. Ratings remain on the standard 1500 scale while rating deviation ($RD$) reliably reflects true information entropy.

---

## 3. Whole-History Rating (WHR)

Whole-History Rating (Coulom, 2008) is a global Bayesian model that simultaneously fits a player's entire career trajectory across time.

### 3.1 Prior: Wiener Process (Brownian Motion)
A player's skill $r(t)$ on day $t$ evolves as a continuous random walk:
$$r(t_2) \sim \mathcal{N}(r(t_1), w^2 |t_2 - t_1|)$$
where $w^2$ is the skill variance drift rate per day ($w^2 = 0.005$ in our implementation).

### 3.2 Likelihood & Objective Function
Under the Bradley-Terry model, the probability of player $i$ beating opponent $j$ on day $t$ is:
$$P(i > j) = \frac{\exp(r_i(t))}{1 + \exp(r_i(t) - r_j(t))}$$

The joint posterior log-density is the sum of game log-likelihoods and Brownian prior transition log-densities:
$$\ln P(R | \text{Games}) = \sum_{\text{games}} \ln P(\text{outcome}) - \sum_{\text{players}} \sum_{k} \frac{(r(t_{k+1}) - r(t_k))^2}{2 w^2 (t_{k+1} - t_k)} + \text{const}$$

### 3.3 Optimization via Thomas Algorithm
Maximization with respect to $r_i = [r_i(t_1), \dots, r_i(t_K)]^T$ yields a symmetric positive-definite **tridiagonal system**:
$$A_i \Delta r_i = \text{rhs}_i$$
where:
- $A_i = H_{\text{lik}} + \Sigma_{\text{prior}}^{-1}$
- $\text{rhs}_i = g_{\text{lik}} - \Sigma_{\text{prior}}^{-1} r_i$

This system is solved in linear time $O(K)$ per player using the **Thomas algorithm** (forward elimination and back substitution). By cycling through all players iteratively, the system converges in 5--7 Newton-Raphson iterations across all 9 years of history.
