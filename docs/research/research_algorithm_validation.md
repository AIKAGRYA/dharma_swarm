# Algorithm Validation Brief: Chaos/Dynamical-Systems Invariants for Short AI Evaluation Time Series

**Prepared for:** Production implementation of a chaos/dynamical-systems observability module  
**Target signal:** Gauntlet correctness scores ∈ [0,1], N = 50–500 samples  
**Date:** 2025  
**Scope:** Takens delay-embedding, maximal Lyapunov exponent (MLE), correlation dimension (D₂)

---

## Executive Summary

The three classical algorithms — Rosenstein (1993) for MLE, Cao (1997) or Kennel FNN (1992) for embedding dimension, Fraser–Swinney (1986) AMI for delay τ, and Grassberger–Procaccia (1983) for D₂ — remain the most defensible choices for a v1 implementation on short, noisy time series. They are computationally tractable in pure NumPy/SciPy, well-understood in terms of failure modes, and still recommended in the 2020–2025 literature for practical applications. However, **the literature is unambiguous that N = 50–200 samples is at or below the reliable operating floor for all of these methods**, and claims must be hedged accordingly. Neural-network-based estimators and persistent-homology alternatives are improving rapidly but are not yet mature enough for production use without the equation of motion.

---

## 1. Maximal Lyapunov Exponent: Algorithm Choice in 2025

### 1.1 Status of Rosenstein 1993

**Rosenstein's algorithm remains the standard of practice for MLE estimation from scalar time series in 2025.** A 2024 systematic review of 31 biomechanics studies found Rosenstein applied in 19 of 31 cases, making it the dominant method in applied literature by a wide margin ([Winter et al., Journal of Sports Sciences, 2024](https://www.tandfonline.com/doi/full/10.1080/02640414.2024.2308441)). Its advantages — simple implementation, robustness to parameter choices, direct derivability from the definition of divergence rate — remain unmatched among equation-free methods for univariate series.

The algorithm reconstructs the attractor via delay embedding, locates each point's nearest neighbor (subject to a temporal exclusion window to avoid trivial neighbors), then tracks the average log-divergence of those neighbor pairs over short time horizons. The MLE λ₁ is the slope of the linear region of this average divergence curve.

**Key references:**
- Rosenstein, M.T., Collins, J.J., De Luca, C.J. (1993). "A practical method for calculating largest Lyapunov exponents from small data sets." *Physica D*, 65(1–2), 117–134. [[link](https://dl.acm.org/doi/10.1016/0167-2789(93)90009-P)]

### 1.2 Comparison with Wolf, Kantz, and Neural-Network Methods

A systematic comparison of Wolf (1985), Rosenstein (1993), Kantz (1994), and neural-network-based methods across multiple systems (logistic map, Hénon, Rössler, Lorenz) found the following ([Krysko et al., *Entropy*, 2018](https://pmc.ncbi.nlm.nih.gov/articles/PMC7512692/)):

| Method | Small Data | Noise Robustness | Accuracy (Lorenz LLE) | Notes |
|---|---|---|---|---|
| **Wolf (1985)** | Poor | Poor | 0.817 vs ref 0.906 | Marginal on small data; breaks on noise |
| **Rosenstein (1993)** | Good | Moderate | 0.836 vs ref 0.906 | Simple, fast, recommended for small N |
| **Kantz (1994)** | Moderate | Moderate | 0.807 vs ref 0.906 | Parameter choices are arbitrary; underestimates on Rössler/Lorenz |
| **Neural network (modified)** | Best | Best | 0.949 vs ref 0.906 | Requires training; only method computing full LE spectrum |

**Kantz (1994)** is conceptually similar to Rosenstein but averages over neighborhoods at multiple scales rather than tracking individual pairs. Its parameter sensitivity (choice of neighborhood radius ε, scale range) is well documented as a weakness when ground truth is unknown. On multiple test systems, Kantz underestimated the LLE relative to Rosenstein.

**Wolf (1985)** is widely considered obsolete for short, noisy series and should not be used.

**Neural-network estimators** (modified Benettin-style networks) are the only methods capable of recovering the full LE spectrum without system equations. A 2025 arxiv paper ([Boikov et al., 2025](https://www.arxiv.org/pdf/2507.04868v2)) demonstrates a machine-learning GMAE-based estimator achieving R²_pos > 0.99 on M = 450-sample clean series. At M = 50, performance collapses to R²_pos ≈ 0.75 for KNN-R and further degrades below SNR ≈ 27 dB. These estimators require validation data (known systems) for calibration and are not yet suitable as plug-in estimators for production code without ground truth.

**Automatic-differentiation (AD)-based methods** (Chaos, 2025) can compute the full LE spectrum via linearized variational equations and offer competitive accuracy for higher-dimensional systems but require an explicit or learned model.

### 1.3 Recommended Modification: Multi-Neighbor Rosenstein

A 2019 study in *Journal of Biomechanics* ([Mehdizadeh, 2019](https://pubmed.ncbi.nlm.nih.gov/30670330/)) proposed using k ≥ 15 initial neighboring points instead of Rosenstein's original k = 1, achieving plateau stability and more consistent values on noisy signals. This is a low-cost enhancement compatible with the original algorithm and **is recommended for v1**.

### 1.4 Sample-Size Minimums and Confidence Intervals

- Bradley & Kantz (2015 review, *Chaos*) state explicitly: "A computation of a Lyapunov exponent for a five-dimensional system from N = 100 points should probably not be trusted." Estimates are "unstable and extremely sensitive to data length." ([Bradley & Kantz, *Chaos* 25, 097610, 2015](https://ar5iv.labs.arxiv.org/html/1503.07493))
- The Winter et al. (2024) systematic review found no consensus on minimum data length in the biomechanics literature; sample sizes for sporting movement LyE ranged from 30 to 287 cycles.
- **No closed-form confidence interval for MLE from Rosenstein's method exists** in standard practice. Bootstrap resampling of sub-segments is the only defensible approach; report variance across bootstrap trials as uncertainty bounds. The test-retest reliability of MLE is rarely characterized in the literature, and the 2024 review recommended this as a priority research gap.
- **Defensible threshold**: For signals in [0,1] with unknown dynamics, N ≥ 200 is a practical floor for reporting MLE as indicative rather than quantitative; N < 100 should be reported only as a trend indicator, never as a precise value.

---

## 2. Embedding Dimension Selection: Cao vs. FNN in 2025

### 2.1 Cao (1997) vs. Kennel FNN (1992)

Both methods estimate the minimum embedding dimension m at which the reconstructed attractor is "unfolded" — i.e., no more false neighbors exist due to projection artifacts.

**Kennel FNN (1992)** uses a threshold ratio to decide whether a neighbor is "false": the neighbor distance jumps more than a set factor when dimension increases by one. The method requires setting two thresholds (R_tol and A_tol), and its performance degrades with noise because noise drives the false-neighbor fraction artificially low, suggesting spuriously low embedding dimensions. A 2005 study ([Lim & Puthusserypady, *Phys. Rev. E* 72, 027204, 2005](https://link.aps.org/doi/10.1103/PhysRevE.72.027204)) demonstrated that both FNN and Cao's method are significantly affected by SNR and proposed systematic postprocessing corrections.

**Cao (1997)** uses two functions, E1(m) and E2(m), derived from the ratio of nearest-neighbor distances in successive embedding dimensions, and requires no threshold parameters. E1 saturating near 1 indicates the minimum m; E2 ≠ 1 confirms the series is deterministic (not random). For moderately noisy data, Cao is generally preferred because it reduces the threshold-sensitivity problem.

**Current consensus (2025):**
- Neither method is universally preferred; both are in active use.
- A 2022 paper proposing **automated scaling-region selection with confidence intervals** ([Deshmukh, Meikle, Bradley et al., *Physica D*, 2023](https://linkinghub.elsevier.com/retrieve/pii/S0167278923000283)) provides formal statistical tests for convergence, removing the subjectivity of visually identifying saturation in E1(m) or FNN% curves. This is the closest thing to a recent methodological advance and is recommended for automated pipelines.
- **For N = 50–500**: Both methods lose reliability because noise inflates the perceived fraction of false neighbors (FNN) or biases the E1 plateau (Cao). At these sample sizes, **fix embedding dimension by theory or literature precedent** where possible, and test sensitivity by varying m ± 1.

**Recommendation:** Use Cao (1997) as primary (no threshold parameters), compute for m = 1..10, look for E1 saturation. Supplement with E2 to screen out stochastic series. At N < 200, treat the result as a heuristic, not a firm estimate.

### 2.2 Recent Critiques (2023–2026)

The Deshmukh et al. (2023) *Physica D* paper identifies the core problem with both methods: **the scaling-region selection is subjective, performed "by eye," and lacks confidence intervals**. Their automated method computes confidence intervals on the scaling region and provides a statistical test for convergence — an important improvement that should guide v1 design even if the full method is not initially implemented. The Tan et al. (2023) *Chaos* paper similarly notes that FNN and mutual information methods "fail in the presence of finite data length, finite precision, and noise."

---

## 3. Delay τ Selection: Fraser–Swinney AMI in 2025

### 3.1 Status of Fraser–Swinney (1986)

**The first minimum of average mutual information (AMI) remains the dominant standard for τ selection in 2025.** The 2024 systematic review by Winter et al. found AMI used in 25 of 31 biomechanics studies. No single successor method has displaced it in applied practice.

Fraser, A.M. & Swinney, H.L. (1986). "Independent coordinates for strange attractors from mutual information." *Physical Review A*, 33(2), 1134. This paper established that AMI, unlike autocorrelation, captures nonlinear dependencies — a critical property for chaotic systems where the goal is to choose τ so that x(t) and x(t+τ) are "as independent as possible" while still linked by the same dynamics.

### 3.2 Autocorrelation First-Zero-Crossing as Alternative

The first zero-crossing of the autocorrelation function is computationally simpler but captures only linear dependence. For bounded signals (scores ∈ [0,1]) with possible nonlinear dynamics, autocorrelation-based τ can be significantly too long or too short. Morales et al. (2021, *Entropy*, [link](https://pmc.ncbi.nlm.nih.gov/articles/PMC7916852/)) showed explicitly that for Lorenz, Rössler, Duffing, Mackey–Glass, and Chen systems, AMI and autocorrelation give τ values that agree at ~2 decimal places in some cases (Lorenz: AMI = 11, FAC = 11) but diverge dramatically in others (Rossler: AMI = 20, FAC = 20; Chen: AMI = 10, FAC = 10 — agreement here — but FAC leads to LLE errors 30–40% greater than AMI when fed into the reconstruction). **Autocorrelation is acceptable only as a fallback when N is too small to estimate AMI reliably.**

### 3.3 Newer Alternatives (2022–2026)

The 2023 *Chaos* paper by Tan et al. ([DOI: 10.1063/5.0137223](https://pubs.aip.org/aip/cha/article/33/3/032101/2881154/Selecting-embedding-delays-An-overview-of)) provides the most comprehensive recent review of τ-selection methods. Key findings:

- **SToPS (Significant Times on Persistent Strands)**: A 2023 persistent-homology-based method that identifies "characteristic time scales" as local maxima of a significance score S(τ). It outperforms AMI for multi-timescale signals (fast-slow dynamics, sum of sines). However, computational scaling is polynomial in simplicial complex size, with reported execution times of ~2400 seconds for a Lorenz series at τ_max = 200 — making it impractical for production real-time use.
- **PECUZAL / MDOP**: Joint embedding methods that simultaneously optimize τ and m using continuity statistics or L-statistics. Prediction error on Lorenz: SToPS = 0.106, PECUZAL = 0.122, MDOP = 0.112. These require more code complexity.
- **C-C method** (Kim et al.): Simultaneously selects τ and m via correlation integral. Computationally simple but shown to produce wrong τ_w estimates in multiple studies.
- **Gao–Zheng method**: Based on false nearest neighbors; minimizes both redundancy and irrelevancy. Extension of FNN philosophy to joint (τ, m) selection.

**Summary table of τ selection methods:**

| Method | Theoretical Basis | Noise Robustness | Computational Cost | Recommended for N=50–500? |
|---|---|---|---|---|
| AMI first minimum (Fraser–Swinney) | Nonlinear information | Moderate | O(N²) for histogram | Yes (primary) |
| Autocorrelation first-zero | Linear only | High | O(N log N) | Fallback only |
| SToPS (TDA) | Topological | High | Very high (~hours) | No (v1) |
| PECUZAL | Continuity statistic + L-stat | High | Moderate-high | Consider for v2 |
| C-C method | Correlation integral | Moderate | Low | Not recommended |

**Recommendation:** Use AMI first-minimum (Fraser–Swinney) with a binned histogram estimator (10–20 bins for N = 50–500). For extremely short series (N < 80), fall back to autocorrelation first-zero. Report τ and sensitivity tests (τ ± 1, τ ± 2).

---

## 4. Correlation Dimension: Grassberger–Procaccia vs. Persistent Homology

### 4.1 Status of Grassberger–Procaccia (1983)

The Grassberger–Procaccia (GP) algorithm remains **the standard method for correlation dimension estimation from time series** in 2025. It computes the correlation sum C(r) — the fraction of point pairs within distance r — and estimates D₂ as the power-law exponent of C(r) ∝ r^D₂ in the scaling region.

Grassberger, P. & Procaccia, I. (1983). "Characterization of strange attractors." *Physical Review Letters*, 50(5), 346–349.

The TISEAN documentation (Schreiber & Schmitz) notes that "typically 1000 pairs will suffice for a stable estimation of D₂," implying N ~ 32 for low-dimensional attractors but far more for D₂ > 3 ([TISEAN docs](https://www.pks.mpg.de/tisean/TISEAN_2.1/docs/chaospaper/node30.html)). The **Theiler window** — excluding temporally adjacent pairs from the correlation sum — is mandatory and should be set at the first minimum of the autocorrelation function or estimated from a space-time-separation plot.

**Critical error sources in GP:**
- Failure to apply Theiler window (leads to systematic overestimation)
- Fitting the linear region by eye without confidence intervals (subjective)
- Finite sample effects: For small N, the correlation sum is dominated by large-r behavior, biasing D₂ downward at small r and upward at large r

### 4.2 Data-Size Requirements for GP

Multiple empirical and theoretical analyses establish these bounds:

| Authority | Minimum N formula | N for D₂ ≈ 2 | N for D₂ ≈ 5 |
|---|---|---|---|
| Smith (1988) | N > 42^D₂ | ~1,764 | ~130 million |
| Theiler (1990) | N > 5^D₂ | ~25 | ~3,125 |
| Ruelle (1990) | N ≥ 10^(D₂/2) | ~10 | ~316 |
| Eckmann & Ruelle (1992) | exponential in D₂ | — | — |

The Eckmann–Ruelle limit is often cited as the most pessimistic: N must grow exponentially with D₂. The 2025 *Nonlinear Processes in Geophysics* paper ([Caby et al., 2025](https://npg.copernicus.org/articles/32/139/2025/npg-32-139-2025.pdf)) confirms that for 95.5% confidence and 10% relative error: **N > 427 analogues within radius R are required**, with total trajectory length N_tot needing 10⁴–10⁷ points for well-characterized systems. For N = 50–500 total points, this is essentially impossible to achieve for D₂ > 1.5.

A comparison study by Diks (1999) ([*Physica D*](https://www.sciencedirect.com/science/article/pii/S0167278998001687)) found that for a D₂ ≈ 6 attractor, reliable estimates require N ≈ 100,000 points, with the analytical approximation N_min(d) ≈ 10^((d+3.7)/1.9) providing a useful rule of thumb.

### 4.3 Persistent-Homology-Based Alternatives (2019–2025)

Jaquette & Schweinhart (2019, *Nonlinear Science*; [PMC link](https://pmc.ncbi.nlm.nih.gov/articles/PMC7117095/)) compared PH₀-based fractal dimension estimation to GP correlation dimension across Hénon, Ikeda, Rulkov, Lorenz, and Mackey–Glass attractors (using 10⁶ samples per trial). Key findings:

- **PH₀ and correlation dimension perform comparably** on well-behaved fractals; both converge toward the same values (Lorenz: correlation = 2.04, PH₀ = 2.05–2.06).
- On irregular attractors (Rulkov), estimates **disagreed by up to 2.1× between methods**, indicating genuine definitional differences, not just noise.
- PH₁ and PH₂ dimensions are "slow for point clouds in ℝ³" and "impractical for higher ambient dimensions."
- **PH₀ requires no example-specific parameters**, whereas GP requires fitting a linear region.
- Correlation dimension is still noted as providing "reasonable answers even for relatively small sample sizes."

Recent COVID-19 time-series analysis ([Phang et al., *Scientific Reports*, 2024](https://www.nature.com/articles/s41598-024-79002-0)) and 2024 *Chaos* papers use **persistent homology for topology-based clustering** of delay-embedded trajectories — a different use case (topological classification, not scalar dimension estimation). This is a growing area but not yet competitive with GP for single scalar estimates.

**Assessment:** PH₀ as a dimension estimator is mathematically rigorous and parameter-free, but (1) computational cost scales poorly with N, (2) the method requires a large point cloud (same order as GP or larger), (3) software maturity is lower, and (4) interpretability is harder for practitioners. **For v1, use GP with Theiler window correction; flag PH-based estimation as a v2 research item.**

---

## 5. Short Time Series Caveats: N = 50–500

### 5.1 What the 2020–2026 Literature Says

The most authoritative summary remains Bradley & Kantz (2015, *Chaos*) — still heavily cited through 2025 ([arxiv version](https://ar5iv.labs.arxiv.org/html/1503.07493)):

> "A computation of a Lyapunov exponent for a five-dimensional system from a data set containing N = 100 points should probably not be trusted."

Specific quantitative bounds from the literature:

| Quantity | Sample bound | Reference |
|---|---|---|
| Correlation dimension (D₂ ≈ 2) | N_min ≈ 1,764 (Smith); ≈ 25 (Theiler) | Diks (1999), *Physica D* |
| Correlation dimension D₂ (general) | N_min(d) ≈ 10^((d+3.7)/1.9) | Diks (1999) |
| MLE (Lyapunov) | N = 100 for d = 5 is "not trustworthy" | Bradley & Kantz (2015) |
| MLE (ML-based) | R²_pos ≈ 0.75 at M = 50; R²_pos > 0.96 at M ≥ 200 | Boikov et al. (arXiv, 2025) |
| Correlation sum pairs | ≥ 1000 pairs within radius for stable D₂ | TISEAN docs; Diks (1999) |
| EVT local dimension | N > 427 analogues within radius for 10% accuracy | Caby et al. (2025) |
| Embedding parameter estimation | "Break down if one has a short or noisy time series" | Bradley & Kantz (2015) |

### 5.2 Systematic Biases at Small N

- **Correlation dimension**: At N < 1000, systematic underestimation at small r (insufficient pairs) and potential overestimation at large r (global shape effects). The Theiler window further reduces the effective number of pairs.
- **Lyapunov exponent**: At short N, the divergence curve may not show a clear linear region; fitting is unreliable. The 2021 Matilla-García et al. study (*Entropy*, [link](https://pmc.ncbi.nlm.nih.gov/articles/PMC7916852/)) showed that at T = 3,000 points, FAC-based τ selection caused LLE errors of 50–90% (Lorenz: reference 1.500, FAC estimate 0.771), while AMI-based selection was accurate to within 1–2%.
- **Embedding dimension**: FNN and Cao both degrade with noise, underestimating m when SNR is low, potentially leading to under-embedded attractors.
- **In-sample noise amplification**: In an m-dimensional embedding, a single noisy observation affects m separate embedding vectors — a unique amplification effect absent in the original state space.

### 5.3 Defensible Claims at N = 50–500

For production code targeting N = 50–500:

| N range | Defensible claim |
|---|---|
| N < 100 | Qualitative trend only; all invariant estimates are exploratory |
| N = 100–200 | λ₁ sign (positive vs. negative/zero) if linear divergence region is visible; D₂ lower bound only |
| N = 200–500 | λ₁ as approximate magnitude ± 30–50% (bootstrap over sub-segments); D₂ as indicative estimate for D₂ < 2 only; τ and m estimates are heuristic |

**Mandatory practices for claims:**
1. Apply surrogate data testing (Theiler et al. 1992 AAFT surrogates) to confirm the series is non-random before reporting any invariant. At N < 200, this is the most informative test.
2. Report all invariants with explicit confidence caveats proportional to N.
3. Sweep embedding parameters (m ± 1, τ ± 2) and report sensitivity.
4. Apply Theiler window in GP correlation sum.

---

## 6. Python Library Assessment

### 6.1 `nolds` (CSchoel)

**Most directly relevant for v1.** Implements exactly the three required algorithms in pure NumPy: `lyap_r` (Rosenstein 1993), `corr_dim` (GP with optional Theiler window), and `sampen`/`hurst_rs`/`dfa`. Documentation ([nolds.readthedocs.io](https://nolds.readthedocs.io/en/latest/nolds.html)) explicitly cites original papers and explains each implementation decision. The Lyapunov implementation uses RANSAC for robust line fitting in the linear divergence region — an important default.

- **Strengths:** Minimal dependencies (NumPy only); clear, annotated source; active maintenance (PyPI version 2025); direct correspondence to reference papers.
- **Weaknesses:** No built-in parameter selection (τ, m must be supplied); no confidence intervals; no Cao/FNN embedding dimension estimator.
- **Trust level:** High. The cleanest reference implementation available for pure NumPy/SciPy use. Zenodo-archived ([Zenodo](https://zenodo.org/records/3814723)).

### 6.2 `neurokit2` (neuropsychology)

Implements 112+ complexity indices including `fractal_correlation` (GP D₂) and delay/dimension selection via `delay_optimal`. A 2022 *Entropy* study ([Makowski et al., 2022](https://pmc.ncbi.nlm.nih.gov/articles/PMC9407071/)) benchmarked these measures systematically across signal types, lengths, and noise levels — the most comprehensive empirical comparison in the Python ecosystem.

- **Strengths:** Comprehensive; actively maintained; peer-reviewed methodology paper; AMI-based delay selection built in.
- **Weaknesses:** Large dependency footprint; primarily oriented toward physiological signals; does not implement Rosenstein's Lyapunov; GP correlation dimension uses simplified defaults.
- **Trust level:** High for entropy/fractal complexity; moderate for Lyapunov.

### 6.3 `pyunicorn` (PIK Potsdam)

Implements recurrence quantification analysis (RQA), recurrence networks, visibility graphs, and surrogate time series construction ([Donges et al., *Chaos*, 2015](https://pubs.aip.org/aip/cha/article/25/11/113101/134592/Unified-functional-network-and-nonlinear-time)). Does **not** natively implement Rosenstein MLE or GP correlation dimension as primary algorithms; its strength is complex-network representations of time series.

- **Strengths:** Rigorous recurrence analysis; climate science pedigree; good parallelization.
- **Weaknesses:** Not focused on the three target invariants; heavier installation; primary use case is network analysis, not scalar invariants.
- **Trust level:** High for recurrence analysis; not the right tool for MLE/D₂/embedding.

### 6.4 `teaspoon` (TeaspoonTDA)

Topological signal processing toolkit focused on persistent homology, delay-coordinate Takens embeddings, and TDA-based feature extraction ([GitHub](https://github.com/TeaspoonTDA/teaspoon)). Implements FNN and AMI for parameter selection. Includes `DynSysLib` for benchmark dynamical systems.

- **Strengths:** Modern TDA perspective; good for topological signatures of attractors; useful for v2 PH dimension.
- **Weaknesses:** Not production-mature for scalar MLE or GP D₂; academic/research codebase; smaller user community.
- **Trust level:** Moderate; appropriate for TDA research, not yet for production scalar invariants.

### 6.5 Library Recommendation Summary

| Library | Rosenstein MLE | GP D₂ | AMI/FNN | Confidence | Use in v1? |
|---|---|---|---|---|---|
| `nolds` | ✓ (`lyap_r`) | ✓ (`corr_dim`) | Partial | High | Yes — primary reference |
| `neurokit2` | ✗ | ✓ | ✓ | High | Partial — delay/dim selection |
| `pyunicorn` | ✗ | ✗ | Partial | High | No — different use case |
| `teaspoon` | ✗ | ✗ | ✓ | Moderate | No for v1 |

**Recommended approach for pure NumPy/SciPy implementation:** Use `nolds` source as the reference implementation to port and adapt. Its `lyap_r` and `corr_dim` routines are well-commented, paper-accurate, and minimal. For AMI, implement Fraser–Swinney using `scipy.stats` histograms (8–16 bins for N = 50–500).

---

## 7. Final Recommendation: What to Implement in v1

**Implement the following three-algorithm core, hedged to the actual sample-size regime:**

Implement **Rosenstein (1993)** ([*Physica D*, 65, 117–134](https://dl.acm.org/doi/10.1016/0167-2789(93)90009-P)) for the maximal Lyapunov exponent — it remains the consensus standard for univariate scalar time series in 2025, is robust to parameter choices relative to Kantz and Wolf, and is straightforwardly implementable in pure NumPy; use ≥ 15 initial neighbors following Mehdizadeh (2019) ([*J Biomech*, 85, 84–91](https://pubmed.ncbi.nlm.nih.gov/30670330/)) to improve noise robustness, report the slope of the linear divergence region only where a clear scaling region exists, and note confidence as *indicative (±30–50%)* for N < 500 and *exploratory only* for N < 100. Implement **Cao (1997)** ([*Physica D*, 110, 43–50](https://www.sciencedirect.com/science/article/abs/pii/S0167278997001188)) for embedding dimension selection — computing E1(m) and E2(m) for m = 1..12, accepting the first m where E1 saturates near 1.0 and E2 ≠ 1.0 confirms determinism; note confidence as *heuristic* for N < 300 and sweep m ± 1 to assess sensitivity per Deshmukh et al. (2023) ([*Physica D*, 133674](https://www.sciencedirect.com/science/article/pii/S0167278923000283)). Implement **Fraser–Swinney (1986) AMI first minimum** ([*Phys. Rev. A*, 33, 1134](https://journals.aps.org/pra/abstract/10.1103/PhysRevA.33.1134)) for delay τ using a histogram-based mutual information estimator — still the dominant standard in 2025 per Winter et al. ([*J Sports Sci.*, 2024](https://www.tandfonline.com/doi/full/10.1080/02640414.2024.2308441)) with AMI used in 25/31 reviewed applied studies, robust to nonlinear signal structure unlike autocorrelation; note that for N < 80, fall back to autocorrelation first-zero-crossing with an explicit warning. Implement **Grassberger–Procaccia (1983)** ([*Phys. Rev. Lett.*, 50, 346](https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.50.346)) for correlation dimension with mandatory Theiler window — it provides "reasonable answers even for relatively small sample sizes" per Jaquette & Schweinhart (2019) ([*Nonlinear Science*, 2020](https://pmc.ncbi.nlm.nih.gov/articles/PMC7117095/)), outperforms box-counting at small N, and ties to nolds reference implementation; apply the Theiler window at the AMI-selected τ, require ≥ 1000 pairwise distance evaluations before reporting, and caveat all D₂ estimates at N < 500 as *lower-bound approximations* given Eckmann–Ruelle limits. **Mandatory across all four algorithms:** run AAFT surrogate tests ([Theiler et al., 1992](https://www.sciencedirect.com/science/article/pii/0167278992900652)) before reporting any invariant, explicitly flag series where N < 100 as outside the defensible operating range, and emit structured uncertainty metadata (sweep results over ±1 embedding parameter) with every output.

---

## References

1. Rosenstein, M.T., Collins, J.J., De Luca, C.J. (1993). A practical method for calculating largest Lyapunov exponents from small data sets. *Physica D*, 65(1–2), 117–134. https://dl.acm.org/doi/10.1016/0167-2789(93)90009-P
2. Kantz, H. (1994). A robust method to estimate the maximal Lyapunov exponent of a time series. *Physics Letters A*, 185(1), 77–87.
3. Wolf, A., Swift, J.B., Swinney, H.L., Vastano, J.A. (1985). Determining Lyapunov exponents from a time series. *Physica D*, 16, 285–317.
4. Cao, L. (1997). Practical method for determining the minimum embedding dimension of a scalar time series. *Physica D*, 110(1–2), 43–50.
5. Kennel, M.B., Brown, R., Abarbanel, H.D.I. (1992). Determining embedding dimension for phase-space reconstruction using a geometrical construction. *Physical Review A*, 45(6), 3403–3411.
6. Fraser, A.M., Swinney, H.L. (1986). Independent coordinates for strange attractors from mutual information. *Physical Review A*, 33(2), 1134–1140. https://journals.aps.org/pra/abstract/10.1103/PhysRevA.33.1134
7. Grassberger, P., Procaccia, I. (1983). Characterization of strange attractors. *Physical Review Letters*, 50(5), 346–349. https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.50.346
8. Krysko, A.V., Awrejcewicz, J., Barulina, M.A., Erofeev, N.P., Dobriyan, V., Krysko, V.A. (2018). Quantifying Chaos by Various Computational Methods. Part 1: Simple Systems. *Entropy*, 20(3), 175. https://pmc.ncbi.nlm.nih.gov/articles/PMC7512692/
9. Bradley, E., Kantz, H. (2015). Nonlinear time-series analysis revisited. *Chaos*, 25, 097610. https://ar5iv.labs.arxiv.org/html/1503.07493
10. Diks, C. (1999). Estimating invariants of noisy attractors. *Physica D*, 120(1–2), 209–224. https://www.sciencedirect.com/science/article/pii/S0167278998001687
11. Mehdizadeh, S. (2019). A robust method to estimate the largest Lyapunov exponent of noisy signals: A revision to the Rosenstein's algorithm. *Journal of Biomechanics*, 85, 84–91. https://pubmed.ncbi.nlm.nih.gov/30670330/
12. Tan, E., Algar, S., Corrêa, D., Small, M., Stemler, T., Walker, D. (2023). Selecting embedding delays: An overview of embedding techniques and a new method using persistent homology. *Chaos*, 33(3), 032101. https://pubs.aip.org/aip/cha/article/33/3/032101/
13. Deshmukh, V., Meikle, R., Bradley, E., Meiss, J., Garland, J. (2023). Using scaling-region distributions to select embedding parameters. *Physica D*, 133674. https://linkinghub.elsevier.com/retrieve/pii/S0167278923000283
14. Matilla-García, M., Morales, I., Rodríguez, J., Marín, M.R. (2021). Selection of embedding dimension and delay time in phase space reconstruction via symbolic dynamics. *Entropy*, 23(2), 221. https://pmc.ncbi.nlm.nih.gov/articles/PMC7916852/
15. Jaquette, J., Schweinhart, B. (2019/2020). Fractal dimension estimation with persistent homology: A comparative study. *Nonlinear Science*. https://pmc.ncbi.nlm.nih.gov/articles/PMC7117095/
16. Winter, L., Taylor, P., Bellenger, C., Grimshaw, P., Crowther, R.G. (2024). The application of the Lyapunov Exponent to analyse human performance: A systematic review. *Journal of Sports Sciences*. https://www.tandfonline.com/doi/full/10.1080/02640414.2024.2308441
17. Makowski, D., Te, A.S., Pham, T., Lau, Z.J., Chen, S.H.A. (2022). The structure of chaos: An empirical comparison of fractal physiology complexity indices using NeuroKit2. *Entropy*, 24(8), 1036. https://pmc.ncbi.nlm.nih.gov/articles/PMC9407071/
18. Caby, T., et al. (2025). Finite-size local dimension as a tool for extracting dynamical information. *Nonlinear Processes in Geophysics*, 32, 139–155. https://npg.copernicus.org/articles/32/139/2025/npg-32-139-2025.pdf
19. Theiler, J., Eubank, S., Longtin, A., Galdrikian, B., Farmer, J.D. (1992). Testing for nonlinearity in time series: the method of surrogate data. *Physica D*, 58(1–4), 77–94.
20. Lim, T.P., Puthusserypady, S. (2005). Postprocessing methods for finding the embedding dimension of chaotic time series. *Physical Review E*, 72, 027204. https://link.aps.org/doi/10.1103/PhysRevE.72.027204
21. Donges, J.F., et al. (2015). Unified functional network and nonlinear time series analysis for complex systems science: The pyunicorn package. *Chaos*, 25, 113101. https://pubs.aip.org/aip/cha/article/25/11/113101/
22. Boikov, A., et al. (2025). A novel approach for estimating largest Lyapunov exponents from one-dimensional chaotic time series. arXiv:2507.04868. https://www.arxiv.org/pdf/2507.04868v2
23. Phang, P., Ling, C.Y.F., Liew, S.H., Razak, F., Wiwatanapataphee, B. (2024). Nonlinear time series analysis of state-wise COVID-19 in Malaysia using wavelet and persistent homology. *Scientific Reports*, 14, 26700. https://www.nature.com/articles/s41598-024-79002-0
24. Schoel, C. (2016–2025). nolds: NOnLinear measures for Dynamical Systems. GitHub/PyPI. https://github.com/CSchoel/nolds
25. Eckmann, J.P., Ruelle, D. (1992). Fundamental limitations for estimating dimensions and Lyapunov exponents in dynamical systems. *Physica D*, 56, 185–187.

---

*This brief was prepared for production engineering use. All algorithm recommendations are conditioned on the N = 50–500 constraint and should be reviewed if the sample size regime changes significantly. The authors recommend reassessing persistent-homology-based dimension estimation (teaspoon + giotto-tda) for a v2 roadmap if signal lengths reliably reach N > 1,000.*
