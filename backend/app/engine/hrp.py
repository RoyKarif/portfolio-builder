import numpy as np
from scipy.cluster.hierarchy import linkage
from scipy.spatial.distance import squareform


def hrp_weights(cov_matrix: np.ndarray, tickers: list[str]) -> dict[str, float]:
    """Lopez de Prado 2016 Hierarchical Risk Parity.

    Returns weights summing to 1.0, all strictly positive, keyed by ticker
    in the original input order.

    Raises:
        ValueError: when fewer than 2 tickers are supplied, or when any asset
        has non-positive or near-zero variance (diag < 1e-12).
    """
    n = len(tickers)
    if n < 2:
        raise ValueError("HRP requires at least 2 assets")

    cov = np.asarray(cov_matrix, dtype=float)
    if cov.shape != (n, n):
        raise ValueError(f"cov_matrix shape {cov.shape} does not match {n} tickers")

    variances = np.diag(cov)
    if np.any(variances < 1e-12):
        raise ValueError("HRP cannot handle non-positive or near-zero variance assets")

    # 1. Covariance -> correlation
    std = np.sqrt(variances)
    corr = cov / np.outer(std, std)
    # Numerical guard: clamp into [-1, 1] before distance conversion
    corr = np.clip(corr, -1.0, 1.0)

    # 2. Distance metric and condensed form for scipy
    dist = np.sqrt(0.5 * (1.0 - corr))
    np.fill_diagonal(dist, 0.0)
    condensed = squareform(dist, checks=False)

    # 3. Hierarchical clustering (single linkage; deterministic for fixed input)
    link = linkage(condensed, method="single")

    # 4. Quasi-diagonalization: leaf order from the dendrogram
    sort_ix = _quasi_diag(link, n)

    # 5. Recursive bisection over the sorted index list
    raw = _recursive_bisection(cov, sort_ix)

    # 6. Return in caller's original ticker order
    return {tickers[i]: float(raw[i]) for i in range(n)}


def _quasi_diag(link: np.ndarray, n_leaves: int) -> list[int]:
    """Reorder leaves so that similar items sit next to each other.

    `link` is the (n-1) x 4 linkage matrix from scipy. Internal node ids
    are >= n_leaves; leaves are ids 0..n_leaves-1.
    """
    # Cast only columns 0 and 1 (the cluster IDs). Casting the whole
    # matrix would silently truncate the distance column (col 2) to 0.
    ids = link[:, :2].astype(int)
    ordered = [int(ids[-1, 0]), int(ids[-1, 1])]
    while max(ordered) >= n_leaves:
        new_ordered = []
        for cluster_id in ordered:
            if cluster_id < n_leaves:
                new_ordered.append(cluster_id)
            else:
                row = ids[cluster_id - n_leaves]
                new_ordered.append(int(row[0]))
                new_ordered.append(int(row[1]))
        ordered = new_ordered
    return ordered


def _inverse_variance_weights(cov_slice: np.ndarray) -> np.ndarray:
    """Inverse-variance weights (the HRP base case for a single cluster)."""
    inv = 1.0 / np.diag(cov_slice)
    return inv / inv.sum()


def _cluster_variance(cov: np.ndarray, indices: list[int]) -> float:
    """Variance of a cluster under inverse-variance weighting."""
    sub = cov[np.ix_(indices, indices)]
    w = _inverse_variance_weights(sub)
    return float(w @ sub @ w)


def _recursive_bisection(cov: np.ndarray, sort_ix: list[int]) -> np.ndarray:
    """Allocate weight across the quasi-diagonal-ordered list via top-down
    splits, sizing each side inversely to its cluster variance."""
    n = cov.shape[0]
    weights = np.ones(n)
    work = [list(sort_ix)]
    while work:
        clusters = []
        for cluster in work:
            if len(cluster) <= 1:
                continue
            mid = len(cluster) // 2
            left, right = cluster[:mid], cluster[mid:]
            var_left = _cluster_variance(cov, left)
            var_right = _cluster_variance(cov, right)
            alpha = 1.0 - var_left / (var_left + var_right)
            for i in left:
                weights[i] *= alpha
            for i in right:
                weights[i] *= 1.0 - alpha
            clusters.append(left)
            clusters.append(right)
        work = clusters
    return weights
