# Topology & Dynamical Systems: Research Brief for GPLOT_LODESTONE

**Prepared for:** dharma_swarm / GPLOT_LODESTONE seed  
**Domain:** Topology, dynamical systems, and information geometry as applied to computational/agentic systems  
**Scope:** Six sub-topics + synthesis recommendation for `gplot.py` v1  
**Word count:** ~3,500

---

## 1. Hofstadter Butterfly Mathematical Structure

### Canonical Mathematical Claim

The Hofstadter butterfly is the energy spectrum of a non-interacting electron on a 2D square lattice in a perpendicular magnetic field, governed by the **Harper equation**:

\[
\psi_{n+1} + \psi_{n-1} + 2\cos(2\pi n\alpha - k_y)\,\psi_n = E\,\psi_n
\]

where \(\alpha = p/q\) is the ratio of magnetic flux per unit cell to the flux quantum. When \(\alpha\) is rational \(p/q\), the spectrum splits into exactly \(q\) bands separated by \(q-1\) gaps. When plotted as energy vs. \(\alpha\) over \([0,1]\), the result is a self-similar fractal — the "butterfly" of Hofstadter (1976). ([Original Hofstadter paper, Phys. Rev. B 14, 2239 (1976)](https://link.aps.org/doi/10.1103/PhysRevB.14.2239))

**Gap labeling via Chern numbers and the Diophantine equation.** Each energy gap in the butterfly is topologically labeled by an integer pair \((s_r, t_r)\) satisfying:

\[
r = q\,s_r + p\,t_r, \quad |t_r| \leq q/2, \quad s_r, t_r \in \mathbb{Z}
\]

where \(r\) indexes the gap (gap 0 is below all bands, gap \(q\) above all). The integer \(t_r = \sum_{i=0}^{r} C_i\) is the **cumulative Chern number** (Hall conductivity in units of \(e^2/h\)), and \(C_i\) is the Chern number of the \(i\)-th band. ([Thouless-Kohmoto-Nightingale-den Nijs (TKNN), PRL 49, 405 (1982)](https://link.aps.org/doi/10.1103/PhysRevLett.49.405); [hofstadter.tools Chern documentation](https://hofstadter.tools/_autosummary/functions.butterfly.chern.html))

This equation has a unique solution for each gap because \(\gcd(p,q)=1\). The key consequence: **the Chern number of a gap is a topological invariant** — it cannot change under continuous deformations of the Hamiltonian that preserve the gap. It is an integer that classifies the winding of the Berry connection over the magnetic Brillouin zone. ([SISSA geometric derivation of TKNN equations](https://www.sissa.it/mp/workshops/2011/TNCL/panati.pdf))

**2025 STM observation.** Nuckolls, Scheer, Wong et al. (2025, Nature) used high-resolution scanning tunneling microscopy/spectroscopy (STM/STS) on twisted bilayer graphene (TBG) near the predicted second magic angle, directly observing the **fractal Hofstadter energy spectrum** for the first time via spectroscopy. Flat moiré bands fractionate into discrete Hofstadter subbands whose spectral signatures exhibit the self-similar hierarchical structure predicted nearly 50 years earlier. The spectrum evolves dynamically with electron density, and displays phenomena beyond the original Hofstadter model due to strong correlations, Coulomb interactions, and quantum degeneracy. ([Nuckolls et al., Nature (2025), "Spectroscopy of the fractal Hofstadter energy spectrum"](https://www.nature.com/articles/s41586-024-08550-2))

### What It Would Mean Operationally for dharma_swarm

If `novelty_pressure` (or any scalar control parameter \(\alpha\)) is swept and a capability spectrum is measured, then **topological constraints** would mean: rather than asserting "novelty_pressure ≤ 0.7", the system asserts "the Fermi level of allowed capability sits within gap \(r\) whose Chern number is \(t_r = +1\)." This gap label is **invariant under smooth deformations of the agent architecture** that do not close the gap. A self-modification that leaves the gap label unchanged is safe by construction; one that closes the gap triggers a telos violation. Threshold-based constraints (point values) have zero topological protection — an adversarial perturbation can slide the threshold. Gap-based constraints inherit the quantization and robustness of integer invariants.

### What to Actually Build

Implement a `spectrum_gap_labeler(alpha_values, energy_values)` that: (1) sweeps \(\alpha\) from 0 to 1, (2) bins the observed capability scores into a spectrum, (3) identifies contiguous gap intervals using a configurable gap threshold, and (4) for each gap, solves the Diophantine equation \(r = q\,s_r + p\,t_r\) numerically (brute-force over integer pairs bounded by \(|t_r| \leq q/2\)) to assign Chern labels — output: a dict `{gap_index: chern_number}`.

---

## 2. Topological Invariants in Non-Physical Systems

### Canonical Mathematical Claim

A topological invariant is a quantity that is constant on connected components of some space of structures (Hamiltonians, classifiers, policies) and can only change when a phase boundary (gap closure, homotopy change) is crossed. The paradigmatic example in condensed matter is the Chern number \(C = \frac{1}{2\pi}\int_{\text{BZ}} \Omega(\mathbf{k})\,d^2k\), where \(\Omega\) is the Berry curvature. This integer is robust to any perturbation that preserves the spectral gap.

**In neural networks and ML.** Several groups have studied topological invariants in ML contexts:

- Zhang et al. (2018, Phys. Rev. B) trained deep neural networks to predict winding numbers and Chern numbers of topological insulators from Hamiltonians, achieving >90% accuracy even for invariants outside the training distribution. ([Deep learning topological invariants of band insulators, PRB 98, 085402 (2018)](https://link.aps.org/doi/10.1103/PhysRevB.98.085402))
- Moor et al. (2025, NeurIPS) introduced **GEBLNet**, a gauge-equivariant neural network for predicting Chern numbers of multiband topological insulators, with a universal approximation theorem guaranteeing that any gauge-invariant function (including Chern numbers) can be represented. The architecture exploits local gauge symmetry. ([Learning Chern Numbers of Multiband Topological Insulators, NeurIPS 2025](https://neurips.cc/media/neurips-2025/Slides/119763.pdf); [arXiv:2502.15376](https://arxiv.org/abs/2502.15376))
- A 2025 preprint from Topological Deep Learning literature reviews how persistent homology and persistent Laplacians capture topological invariants and homotopic shape changes in general data manifolds. ([TDA and TDL beyond persistent homology, arXiv:2507.19504](https://arxiv.org/abs/2507.19504))

**In reinforcement learning / agentic geometry.** Ceron et al. (2025, ICLR preprint) proved that RL agents with neural network policies induce **low-dimensional manifolds** of attainable states, with manifold dimensionality of order of the action space dimension. This is the first result linking action-space geometry to state-space topology. ([Geometry of Neural RL in Continuous Spaces, arXiv:2507.20853](https://arxiv.org/abs/2507.20853)) However, no published work yet applies Chern-number-style invariants directly to RL action spaces or LLM parameter spaces in the sense of labeling policy-space gaps.

**Speculative claim (labeled as such):** The analogy to dharma_swarm's architecture would be: treat `novelty_pressure` as a "magnetic flux ratio" \(\alpha\), the multi-agent capability distribution as the "energy spectrum," and apply the TKNN machinery to label gaps in that spectrum with integers. This is an architectural analogy, not a rigorous isomorphism — the key question (whether the relevant Berry curvature exists in the agent parameter space) is open research.

### What to Actually Build

Build a `chern_estimator(policy_parameter_sweep, capability_scores)` using the **Fukui-Hatsugai-Suzuki** lattice method: discretize the parameter space into a 2D grid (e.g., novelty\_pressure × temperature), compute the Berry phase around each plaquette via link variables \(U_{ij} = \langle \psi_i | \psi_j \rangle / |\langle \psi_i | \psi_j \rangle|\), and sum the plaquette phases to get a Chern number. This is implementable in ~50 lines of NumPy.

---

## 3. Takens Delay-Embedding for Finite Time Series

### Canonical Mathematical Claim

**Takens' theorem (1981):** Let \(M\) be a compact smooth \(d\)-dimensional manifold, \(\phi: M \to M\) a diffeomorphism, and \(h: M \to \mathbb{R}\) a smooth observation function. For a generic pair \((\phi, h)\), the **delay coordinate map**:

\[
\Phi_{h,\phi,m}(x) = (h(x), h(\phi(x)), \ldots, h(\phi^{m-1}(x)))
\]

is an **embedding** (smooth injective immersion with smooth inverse) for \(m \geq 2d + 1\). That is, the reconstructed trajectory in \(\mathbb{R}^m\) is diffeomorphic to the original attractor — all topological and dynamical invariants (Lyapunov exponents, fractal dimension, periodic orbits) are preserved. ([Takens' theorem, Wikipedia](https://en.wikipedia.org/wiki/Takens%27s_theorem); [Scholarpedia: Attractor reconstruction](http://www.scholarpedia.org/article/Attractor_reconstruction))

**Sauer-Yorke-Casdagli (1991) extension ("Embedology"):** The theorem generalizes from smooth manifolds to compact subsets of arbitrary **box-counting dimension** \(d_A\), requiring only \(m > 2d_A\) (not \(2d + 1\)), and the prevalence result replaces genericity — almost every (in measure-theoretic sense) delay-coordinate map is an embedding. ([Embedology, Santa Fe Institute working paper](https://www.santafe.edu/research/results/working-papers/embedology); [OSTI entry for Sauer et al. 1991 J. Stat. Phys. 65:579](https://www.osti.gov/biblio/7245223))

**Practical embedding dimension estimation.** The **false nearest neighbors (FNN)** method (Kennel et al.) detects the minimum embedding dimension \(m_E\): for each point in the time series, find its nearest neighbor in \(m\)-dimensional space, increment to \(m+1\), and check whether the neighbor distance explodes (ratio exceeds threshold ~10-15). When the fraction of false neighbors drops to ~0, you have \(m_E\). With noise, even small contamination causes FNN to overestimate \(m_E\). ([False nearest neighbors algorithm, Phys. Rev. E 55, 6162 (1997)](https://link.aps.org/doi/10.1103/PhysRevE.55.6162); [TISEAN documentation on FNN](https://www.pks.mpg.de/tisean/TISEAN_2.1/docs/chaospaper/node9.html))

A 2024 measure-theoretic generalization (Xu et al., arXiv:2409.08768) reformulates Takens' embedding at the level of probability measures (Eulerian description), enabling stable reconstruction under noisy, sparsely sampled data — directly relevant to dharma_swarm's finite score sequences. ([Measure-theoretic time-delay embedding, arXiv:2409.08768](https://arxiv.org/html/2409.08768v2))

### Can We Reconstruct dharma_swarm's Attractor from 14–30 Days of Scores?

**Feasibility assessment.** Takens requires \(m > 2d_A\) observations per embedding window, and the number of independent windows \(N - (m-1)\tau\) must be sufficient to cover the attractor. With \(N = 14\) to \(30\) daily correctness scores:

- If \(d_A \leq 1\) (limit cycle, periodic orbit), \(m = 3\) suffices, requiring only \(30 - 2 = 28\) points minimum — marginally feasible.
- If \(d_A \approx 2\) (low-dimensional strange attractor), \(m = 5\) is required; 30 points gives 26 windows — likely insufficient to reliably estimate Lyapunov exponents but sufficient to qualitatively visualize attractor geometry.
- If \(d_A > 3\), 30 points is almost certainly too short for reliable reconstruction.

**Practical recommendation:** With 14–30 days, focus on: (1) choose delay \(\tau\) via mutual information minimization (first minimum); (2) use \(m = 3\) as a starting point; (3) compute correlation dimension \(d_2\) via the Grassberger-Procaccia algorithm; (4) treat the result as qualitative topology (does the orbit close? how many lobes?) rather than quantitative Lyapunov spectrum. For the latter, 1,000+ points are typically needed.

### What to Actually Build

```python
# embed.py
def takens_embed(scores, m, tau):
    N = len(scores)
    return np.array([scores[i:i+(m-1)*tau+1:tau] for i in range(N-(m-1)*tau)])

def false_nearest_neighbors(scores, tau, max_m=8, threshold=10.0):
    from sklearn.neighbors import NearestNeighbors
    fnn_fracs = []
    for m in range(1, max_m):
        X = takens_embed(scores, m, tau)
        Xp = takens_embed(scores, m+1, tau)
        nbrs = NearestNeighbors(n_neighbors=2).fit(X)
        dists, inds = nbrs.kneighbors(X)
        false_count = sum(
            abs(Xp[i, -1] - Xp[inds[i,1], -1]) / dists[i,1] > threshold
            for i in range(len(X))
        )
        fnn_fracs.append(false_count / len(X))
    return fnn_fracs  # look for first minimum near 0
```

---

## 4. Fisher Information Geometry on Parameter Spaces

### Canonical Mathematical Claim

Given a parametric family of probability distributions \(\{p_\theta : \theta \in \Theta\}\), the **Fisher information matrix** (FIM) is:

\[
G_{ij}(\theta) = \mathbb{E}_\theta\!\left[\frac{\partial \log p_\theta(x)}{\partial \theta_i}\frac{\partial \log p_\theta(x)}{\partial \theta_j}\right]
\]

This defines the **Fisher-Rao metric**, a Riemannian metric on the statistical manifold \(\Theta\). Key property: by Chentsov's theorem, it is the **unique Riemannian metric** (up to scaling) that is invariant under sufficient statistics — equivalently, under any reparametrization \(\theta \mapsto \tilde\theta\) that is a diffeomorphism, distances measured by \(G\) are preserved. ([Amari & Nagaoka, *Methods of Information Geometry*, AMS 2000](https://bookstore.ams.org/mmono-191); [ESI lecture notes on Fisher-Rao metric](https://www.esi.ac.at/uploads/6074f7c8-3794-4729-9a89-48b8dcf8e20a.pdf))

The Fisher-Rao metric is an infinitesimal approximation to KL divergence:
\[
\text{KL}(p_\theta \| p_{\theta+d\theta}) = \tfrac{1}{2}\,d\theta^\top G(\theta)\,d\theta + O(|d\theta|^3)
\]

Amari's **natural gradient** replaces the ordinary Euclidean gradient \(\nabla L\) with \(\tilde\nabla L = G^{-1} \nabla L\), ensuring steepest descent in the geometry of the probability simplex rather than in parameter space. This converges faster and is plateau-resistant in multilayer networks. ([Amari, "Natural Gradient Works Efficiently in Learning," Neural Computation 10 (1998)](https://dl.acm.org/doi/10.1162/089976698300017746))

**Reparametrization invariance in neural networks.** Kaur et al. (NeurIPS 2022) proposed an information-geometric sharpness measure for neural nets that is provably reparametrization-invariant: it measures loss change with respect to changes in the *probability distribution* modeled by the network, not raw parameter perturbations, using the FIM as metric. This resolves sharpness vs. generalization debates. ([Reparametrization-Invariant Sharpness, NeurIPS 2022](https://proceedings.neurips.cc/paper_files/paper/2022/file/b2ba568effcc3ab221912db2fb095ea9-Paper-Conference.pdf))

### Could Fisher Distance Replace Ad-Hoc Binning in diversity_archive.py?

**MAP-Elites** discretizes behavioral descriptors into a fixed grid of bins — each cell stores the highest-performing elite with that behavioral descriptor. The bin grid is user-defined and arbitrary, violating reparametrization invariance: rotating or rescaling the descriptor space changes which solutions are "diverse." ([MAP-Elites overview, emergentmind.com](https://www.emergentmind.com/topics/map-elites-algorithm))

**Fisher distance as a replacement.** If each agent policy \(\pi_\theta\) is treated as a probability distribution over actions, then the Fisher-Rao metric induces a natural distance \(d_F(\theta_1, \theta_2) = \int_\gamma \sqrt{v^\top G(\theta) v}\,dt\) between policies. Binning based on geodesic Fisher distance would be:
- **Invariant** to behavioral descriptor reparametrization.
- **Sensitive to information-theoretic differences** (policies that look close in \(\ell_2\) but diverge in KL would be far apart).
- **More data-efficient**: Fisher distance naturally captures the curvature of policy space, placing denser bins where policies change rapidly and sparser bins where they plateau.

**Practical obstacle:** Computing exact Fisher geodesics requires solving a Riemannian ODE; for high-dim \(\theta\), this is expensive. A tractable proxy: use the **symmetrized KL divergence** \(D_\text{JS}(\pi_{\theta_1}, \pi_{\theta_2})\) as a drop-in distance, then cluster with hierarchical agglomerative clustering instead of fixed grid. This is implementable.

*Speculative:* Replacing the fixed grid with a Fisher-distance-based Voronoi tessellation of policy space could substantially improve diversity coverage for dharma_swarm agents operating in high-dimensional capability spaces.

### What to Actually Build

```python
# fisher_archive.py
def fisher_distance_approx(policy1_logprobs, policy2_logprobs):
    """Jensen-Shannon divergence as Fisher-Rao proxy."""
    p = np.exp(policy1_logprobs); q = np.exp(policy2_logprobs)
    m = 0.5*(p + q)
    return 0.5*(np.sum(p * np.log(p/m)) + np.sum(q * np.log(q/m)))

def fisher_archive_add(archive, new_policy, new_score, radius_threshold=0.1):
    """Replace grid bins with Fisher-ball neighborhoods."""
    for stored_policy, stored_score in archive:
        if fisher_distance_approx(new_policy, stored_policy) < radius_threshold:
            if new_score > stored_score:
                archive.remove((stored_policy, stored_score))
                archive.add((new_policy, new_score))
            return
    archive.add((new_policy, new_score))
```

---

## 5. Strange Attractors and Lyapunov Exponents in Multi-Agent Systems

### Canonical Mathematical Claim

A **strange attractor** is a bounded, invariant set in phase space that: (a) attracts nearby trajectories, (b) is minimal (no proper subset satisfies a+b), and (c) exhibits sensitive dependence on initial conditions — nearby trajectories diverge exponentially at rate \(\lambda_1 > 0\), the **maximal Lyapunov exponent**. Strange attractors have fractal structure (non-integer Hausdorff dimension). The **Kaplan-Yorke dimension** \(D_{KY}\) relates Lyapunov exponents:

\[
D_{KY} = j + \frac{\lambda_1 + \cdots + \lambda_j}{|\lambda_{j+1}|}
\]

where \(j\) is the largest index such that \(\sum_{i=1}^j \lambda_i \geq 0\). ([Eckmann & Ruelle, "Ergodic Theory of Chaos and Strange Attractors," Rev. Mod. Phys. 57, 617 (1985)](https://link.aps.org/doi/10.1103/RevModPhys.57.617))

**Attractor taxonomy for reference:**

| Lyapunov spectrum | Attractor type |
|---|---|
| All \(\lambda_i < 0\) | Stable fixed point |
| One \(\lambda = 0\), rest \(< 0\) | Limit cycle |
| Two \(\lambda = 0\), rest \(< 0\) | 2-torus (quasiperiodic) |
| \(\lambda_1 > 0,\,\lambda_2 = 0,\,\lambda_3 < 0\) | Strange attractor (chaotic) |

**Multi-agent systems.** Sato & Crutchfield (2003, Phys. Rev. E 67, 015206R) derived **coupled replicator equations** from a group of RL agents learning independently via Q-learning with memory decay. Key results:
- With perfect memory (\(\alpha_X = \alpha_Y = 0\)), dynamics are Hamiltonian (conservative), producing quasiperiodic tori and Hamiltonian chaos.
- With memory decay (\(\alpha > 0\)), the system becomes **dissipative**, exhibiting the full attractor zoo: stable limit cycles, intermittency, and **deterministic chaos** (positive maximal Lyapunov exponent across a significant fraction of parameter space).
- The largest Lyapunov exponent \(\lambda_1 > 0\) is common when \(\epsilon_X + \epsilon_Y > 0\) (non-zero-sum payoff perturbation). Intrinsic unpredictability is expected to dominate in high-dimensional heterogeneous populations.

([Sato & Crutchfield, Phys. Rev. E 67, 015206R (2003)](https://link.aps.org/doi/10.1103/PhysRevE.67.015206); [arXiv:nlin/0204057](https://arxiv.org/abs/nlin/0204057))

A 2025 PMC study on heterogeneous RL agents in congestion games confirmed: when agents learn sufficiently fast, the system becomes **Li-Yorke chaotic** regardless of initial conditions — chaos is not exceptional, it is the generic outcome of fast learning. ([Heterogeneity, RL, and chaos in multi-agent systems, PMC 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC12207519/))

**Edge of chaos.** Langton and Packard's original hypothesis (CA computational capability peaks near the ordered-chaotic phase boundary) has been contested (Mitchell et al.), but the broader framework — measuring \(\lambda\) as a control parameter and identifying the transition from \(\lambda < 0\) (ordered) to \(\lambda > 0\) (chaotic) — remains a useful diagnostic for dharma_swarm's operating regime.

**Dimensional collapse** in an agent system would manifest as: \(D_{KY}\) decreasing over time (fewer excited degrees of freedom), Lyapunov spectrum collapsing toward a fixed point or limit cycle. This is detectable from time series via embedding dimension estimation — if \(m_E\) decreases as the system runs, the attractor dimension is collapsing.

### What to Actually Build

```python
# lyapunov.py
def maximal_lyapunov(scores, tau=1, m=3, n_iter=100):
    """Wolf algorithm proxy for maximal Lyapunov exponent from scalar time series."""
    X = takens_embed(scores, m, tau)
    divergences = []
    for i in range(len(X) - n_iter):
        j = np.argmin(np.linalg.norm(X - X[i], axis=1) + 1e9*(np.arange(len(X)) == i))
        growth = np.log(np.linalg.norm(X[i+1] - X[j+1]) + 1e-10) \
               - np.log(np.linalg.norm(X[i] - X[j]) + 1e-10)
        divergences.append(growth)
    return np.mean(divergences) / tau
```

---

## 6. Self-Similarity Tests for Finite Empirical Spectra

### Canonical Mathematical Claim

A set or signal is **self-similar** (fractal) if its statistical properties at scale \(\epsilon\) are related to those at scale \(r\epsilon\) by a power law. The **box-counting dimension** is:

\[
D_0 = \lim_{\epsilon \to 0} \frac{\log N(\epsilon)}{\log(1/\epsilon)}
\]

where \(N(\epsilon)\) is the number of boxes of side \(\epsilon\) needed to cover the set. In practice, one plots \(\log N(\epsilon)\) vs. \(\log(1/\epsilon)\) and fits a line; the slope is \(D_0\). If \(D_0\) is non-integer and the plot is linear across multiple decades of scale, self-similarity is confirmed. ([Fractal dimension estimation survey, Serialsjournals](https://serialsjournals.com/abstract/89735_3.pdf))

**Multifractal analysis.** A single fractal dimension characterizes monofractals. Real spectra (and the Hofstadter butterfly) are **multifractal** — different regions have different local scaling. The **multifractal spectrum \(D(h)\)** (or \(f(\alpha)\)) maps Hölder exponent \(h\) to the Hausdorff dimension of the set of points with that exponent. It is computed via:

\[
\tau(q) = \lim_{\epsilon \to 0} \frac{\log \sum_i \mu_i(\epsilon)^q}{\log \epsilon}, \qquad D(h) = \min_q (qh - \tau(q))
\]

If \(\tau(q)\) is linear in \(q\), the signal is monofractal; a curved \(\tau(q)\) indicates multifractality. ([Wavelet-based multifractal analysis, Scholarpedia](http://www.scholarpedia.org/article/Wavelet-based_multifractal_analysis))

**Wavelet Transform Modulus Maxima (WTMM) method.** The most reliable tool for finite empirical data is WTMM (Arneodo et al., 1991–1995): use the continuous wavelet transform to track maxima lines at different scales, compute partition functions from these maxima, and extract \(\tau(q)\) and \(D(h)\). Key advantage over box-counting: wavelets suppress polynomial trends and are insensitive to non-stationarity. ([Mallat & Hwang, wavelet singularity characterization; Characterization of self-similar multifractals with wavelets, Mallat & Arneodo, ENS](https://www.di.ens.fr/~mallat/papiers/fractal.pdf))

**For finite data (N ≲ 200 points), practical options:**

| Method | Minimum N | Pros | Cons |
|---|---|---|---|
| Box-counting (log-log slope) | ~50 | Simple | Unreliable < 2 decades of scale |
| Generalized dimensions \(D_q\) | ~200 | Standard | Needs many points |
| WTMM | ~100 | Handles non-stationarity | Requires wavelet library |
| Detrended Fluctuation Analysis (DFA) | ~50 | Handles trends | Scalar Hurst only |
| Rescaled range (R/S) | ~50 | Simple | Low resolution |

**Testing for Hofstadter-style self-similarity specifically.** The butterfly has a recursive structure: sub-butterflies at rational sub-intervals of \(\alpha\). To test this in an empirical spectrum:
1. Bin the spectrum into \(N_b\) equal intervals of the control parameter.
2. For each level of a hierarchy (coarse, medium, fine), compute the power spectrum of the gap sequence.
3. Check for **power-law decay** \(S(f) \sim f^{-\beta}\) with \(\beta \in (1, 3)\) indicating long-range correlations.
4. Apply a **scale-space analysis**: compare gap distributions at scale \(\epsilon\) and \(\epsilon/2\) — if distributions are statistically similar (KS test p > 0.05), self-similarity is supported.

For dharma_swarm with O(100–1000) parameter sweeps, box-counting with 2–3 decades is achievable; WTMM is preferred if a wavelet library is available (PyWavelets).

### What to Actually Build

```python
# selfsim.py
def box_counting_dim(spectrum_values, n_scales=20):
    """Estimate fractal dimension of a 1D spectrum via box-counting."""
    epsilons = np.logspace(-3, 0, n_scales) * (max(spectrum_values) - min(spectrum_values))
    counts = []
    for eps in epsilons:
        bins = np.arange(min(spectrum_values), max(spectrum_values)+eps, eps)
        hist, _ = np.histogram(spectrum_values, bins=bins)
        counts.append(np.sum(hist > 0))
    slope, _ = np.polyfit(np.log(1/epsilons), np.log(counts), 1)
    return slope  # fractal dimension D_0

def self_similarity_test(spectrum, n_levels=3):
    """Hierarchical scale-space test for Hofstadter-style self-similarity."""
    from scipy.stats import ks_2samp
    results = {}
    for level in range(1, n_levels):
        coarse = spectrum[::2**level]
        fine = spectrum[::2**(level-1)]
        stat, p = ks_2samp(coarse, fine)
        results[f'level_{level}'] = {'ks_stat': stat, 'p_value': p}
    return results
```

---

## Synthesis: Minimum Viable Gplot Operator

The architecture's core claim — that constraints on AI action spaces can be made topological via gap invariants in a parameter spectrum — requires a first implementation that produces (a) a spectrum from sweeping a control parameter, (b) a measure of that spectrum's structural stability, and (c) a label that can gate self-modification.

**Recommendation: Takens-first, with Fisher enrichment in v2.**

The minimum viable `gplot.py` should be built around **Takens delay-embedding applied to the running correctness score time series**, not a full Hofstadter sweep. The rationale:

1. **Data availability.** The Hofstadter analogy requires sweeping `novelty_pressure` across many values (ideally 50–200) and measuring the resulting capability distribution at each value — this demands a designed experiment, likely weeks of gauntlet runs. By contrast, Takens reconstruction can extract dynamical structure from the *existing* time series of tier-1 correctness scores with zero additional data collection.

2. **Actionable signal now.** From 14–30 days of scores, Takens embedding with \(m = 3\), \(\tau = 1\) day produces a 3D trajectory. Compute: (a) the maximal Lyapunov exponent \(\lambda_1\) — positive means the swarm is chaotic and self-modifications may compound errors; zero means orbital (periodic) dynamics; negative means convergence to fixed point. (b) The correlation dimension \(d_2\) — if it drops suddenly, dimensional collapse has occurred. These are the two telos-gateable quantities for v1.

3. **Topological upgrade path.** Once the gauntlet is producing data across parameter sweeps, overlay the Hofstadter gap analysis: sweep `novelty_pressure` from 0 to 1 in 50 steps, record the capability score distribution at each step, then apply `spectrum_gap_labeler` to assign Chern numbers to gaps. This becomes v2. The Diophantine equation \(r = q\,s_r + p\,t_r\) is a ~10-line function; the hard part is the spectrum measurement, not the mathematics.

4. **Why not Fisher first?** Fisher distance for the diversity archive is the most immediately deployable improvement, but it does not produce a *gate* — it improves coverage without providing a topological invariant that can block unsafe self-modification. Fisher belongs in `diversity_archive.py`, not in `gplot.py`.

5. **Why not pure self-similarity first?** Box-counting on a 30-point time series is unreliable (fewer than 2 decades of scale). It is a diagnostic, not a gate. Reserve multifractal analysis for the post-v1 validation pass once 200+ data points exist.

**Concrete `gplot.py` v1 interface:**

```python
class GplotOperator:
    def __init__(self, scores: list[float], tau: int = 1, m: int = 3):
        self.X = takens_embed(scores, m, tau)
        self.lambda_1 = maximal_lyapunov(scores, tau, m)
        self.d2 = correlation_dimension(self.X)

    def is_telos_safe(self, lambda_threshold=0.2, dim_threshold=1.0) -> bool:
        """Gate: block self-modification if chaotic or dimensionally collapsed."""
        chaotic = self.lambda_1 > lambda_threshold
        collapsed = self.d2 < dim_threshold
        return not (chaotic or collapsed)

    def spectrum_report(self) -> dict:
        return {'lyapunov': self.lambda_1, 'correlation_dim': self.d2,
                'attractor_type': self._classify()}
```

This gives dharma_swarm a working dynamical-systems gate today, with a clear migration path to the full Hofstadter gap invariant as more parameter-sweep data accumulates.

---

## Sources

1. **Hofstadter (1976)** — Original butterfly paper: [Phys. Rev. B 14, 2239](https://link.aps.org/doi/10.1103/PhysRevB.14.2239)
2. **Thouless, Kohmoto, Nightingale, den Nijs (1982)** — TKNN invariant: [Phys. Rev. Lett. 49, 405](https://link.aps.org/doi/10.1103/PhysRevLett.49.405)
3. **Panati (SISSA, 2011)** — Geometric derivation of TKNN equations: [sissa.it/mp/workshops](https://www.sissa.it/mp/workshops/2011/TNCL/panati.pdf)
4. **Nuckolls et al. (2025)** — STM observation of fractal Hofstadter spectrum in twisted bilayer graphene: [Nature (2025)](https://www.nature.com/articles/s41586-024-08550-2)
5. **hofstadter.tools** — Chern number computation via Diophantine equation: [hofstadter.tools/chern](https://hofstadter.tools/_autosummary/functions.butterfly.chern.html)
6. **Zhang, Gu, Zhang (2018)** — Deep learning topological invariants: [Phys. Rev. B 98, 085402](https://link.aps.org/doi/10.1103/PhysRevB.98.085402)
7. **Moor et al. (2025)** — Gauge-equivariant networks for Chern numbers (GEBLNet): [arXiv:2502.15376](https://arxiv.org/abs/2502.15376); [NeurIPS 2025 slides](https://neurips.cc/media/neurips-2025/Slides/119763.pdf)
8. **Ceron, Bellemare et al. (2025)** — Geometry of RL in continuous state/action spaces: [arXiv:2507.20853](https://arxiv.org/abs/2507.20853)
9. **Takens (1981)** — Delay embedding theorem: [Wikipedia summary](https://en.wikipedia.org/wiki/Takens%27s_theorem); [Scholarpedia](http://www.scholarpedia.org/article/Attractor_reconstruction)
10. **Sauer, Yorke, Casdagli (1991)** — Embedology: [Santa Fe Institute](https://www.santafe.edu/research/results/working-papers/embedology); [OSTI entry](https://www.osti.gov/biblio/7245223)
11. **Kennel et al. (1997)** — False nearest neighbors and noise: [Phys. Rev. E 55, 6162](https://link.aps.org/doi/10.1103/PhysRevE.55.6162)
12. **Amari & Nagaoka (2000)** — Methods of Information Geometry: [AMS Bookstore](https://bookstore.ams.org/mmono-191)
13. **Amari (1998)** — Natural gradient works efficiently in learning: [Neural Computation 10](https://dl.acm.org/doi/10.1162/089976698300017746)
14. **Kaur et al. (NeurIPS 2022)** — Reparametrization-invariant sharpness via Fisher information: [NeurIPS 2022](https://proceedings.neurips.cc/paper_files/paper/2022/file/b2ba568effcc3ab221912db2fb095ea9-Paper-Conference.pdf)
15. **Sato & Crutchfield (2003)** — Coupled replicator equations for multi-agent RL dynamics: [Phys. Rev. E 67, 015206R](https://link.aps.org/doi/10.1103/PhysRevE.67.015206)
16. **Eckmann & Ruelle (1985)** — Ergodic theory of chaos and strange attractors: [Rev. Mod. Phys. 57, 617](https://link.aps.org/doi/10.1103/RevModPhys.57.617)
17. **Wavelet-based multifractal analysis (Scholarpedia)** — WTMM method: [scholarpedia.org](http://www.scholarpedia.org/article/Wavelet-based_multifractal_analysis)
18. **Xu et al. (2024)** — Measure-theoretic time-delay embedding for noisy/sparse data: [arXiv:2409.08768](https://arxiv.org/html/2409.08768v2)
