"""
Option pricing: Black-Scholes-Merton (BSM) and Merton Jump-Diffusion (MJD).

Performance-optimized:
  * scipy.special.ndtr instead of scipy.stats.norm.cdf (~15x faster)
  * Tight initial bracket for Brent's strike solver
  * Early termination of the MJD Poisson series
"""
from __future__ import annotations
from math import exp, log, sqrt
from typing import Optional

import numpy as np
from scipy.special import ndtr
from scipy.optimize import brentq


# -----------------------------------------------------------------------------
# Black-Scholes-Merton
# -----------------------------------------------------------------------------
def _d1_d2(S, K, T, r, q, sigma):
    if T <= 0:
        T = 1e-8
    if sigma <= 0:
        sigma = 1e-8
    vol_t = sigma * sqrt(T)
    d1 = (log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / vol_t
    d2 = d1 - vol_t
    return d1, d2


def bsm_price(S, K, T, r, q, sigma, option_type: str = "call") -> float:
    if T <= 0:
        return max(S - K, 0.0) if option_type == "call" else max(K - S, 0.0)
    d1, d2 = _d1_d2(S, K, T, r, q, sigma)
    if option_type == "call":
        return S * exp(-q * T) * ndtr(d1) - K * exp(-r * T) * ndtr(d2)
    return K * exp(-r * T) * ndtr(-d2) - S * exp(-q * T) * ndtr(-d1)


def bsm_delta(S, K, T, r, q, sigma, option_type: str = "call") -> float:
    if T <= 0:
        if option_type == "call":
            return 1.0 if S > K else 0.0
        return -1.0 if S < K else 0.0
    d1, _ = _d1_d2(S, K, T, r, q, sigma)
    if option_type == "call":
        return exp(-q * T) * ndtr(d1)
    return -exp(-q * T) * ndtr(-d1)


def bsm_price_delta(S, K, T, r, q, sigma, option_type: str = "call") -> tuple[float, float]:
    """Return (price, delta) together — reuses d1/d2."""
    if T <= 0:
        intrinsic = max(S - K, 0.0) if option_type == "call" else max(K - S, 0.0)
        if option_type == "call":
            d = 1.0 if S > K else 0.0
        else:
            d = -1.0 if S < K else 0.0
        return intrinsic, d
    d1, d2 = _d1_d2(S, K, T, r, q, sigma)
    if option_type == "call":
        disc_q = exp(-q * T)
        price = S * disc_q * ndtr(d1) - K * exp(-r * T) * ndtr(d2)
        delta = disc_q * ndtr(d1)
    else:
        disc_q = exp(-q * T)
        price = K * exp(-r * T) * ndtr(-d2) - S * disc_q * ndtr(-d1)
        delta = -disc_q * ndtr(-d1)
    return price, delta


# -----------------------------------------------------------------------------
# Merton Jump-Diffusion — optimized series
# -----------------------------------------------------------------------------
def _mjd_price_delta(
    S, K, T, r, q, sigma,
    lam: float, muJ: float, sigJ: float,
    option_type: str = "call",
    max_terms: int = 25,
    tol: float = 1e-10,
) -> tuple[float, float]:
    if T <= 0:
        intrinsic = max(S - K, 0.0) if option_type == "call" else max(K - S, 0.0)
        d = (1.0 if S > K else 0.0) if option_type == "call" else (-1.0 if S < K else 0.0)
        return intrinsic, d

    k = exp(muJ + 0.5 * sigJ * sigJ) - 1.0
    lamT = lam * T

    if lamT <= 0:
        return bsm_price_delta(S, K, T, r, q, sigma, option_type)

    price = 0.0
    delta = 0.0
    # Iterative Poisson weight: w_n = w_{n-1} * lamT / n
    w = exp(-lamT)   # w_0
    for n in range(max_terms):
        sig_n = sqrt(sigma * sigma + n * sigJ * sigJ / T)
        r_n = r - lam * k + n * (muJ + 0.5 * sigJ * sigJ) / T
        p_n, d_n = bsm_price_delta(S, K, T, r_n, q, sig_n, option_type)
        price += w * p_n
        delta += w * d_n

        # update Poisson weight for next iteration
        w = w * lamT / (n + 1)
        if w < tol and n > 5:
            break

    return price, delta


# -----------------------------------------------------------------------------
# Unified pricer
# -----------------------------------------------------------------------------
class OptionPricer:
    def __init__(self, model: str = "bsm",
                 lam: float = 1.2, muJ: float = -0.05, sigJ: float = 0.12):
        assert model in ("bsm", "mjd")
        self.model = model
        self.lam = lam
        self.muJ = muJ
        self.sigJ = sigJ

    def price(self, S, K, T, r, q, sigma, option_type="call"):
        if self.model == "bsm":
            return bsm_price(S, K, T, r, q, sigma, option_type)
        return _mjd_price_delta(S, K, T, r, q, sigma,
                                self.lam, self.muJ, self.sigJ, option_type)[0]

    def delta(self, S, K, T, r, q, sigma, option_type="call"):
        if self.model == "bsm":
            return bsm_delta(S, K, T, r, q, sigma, option_type)
        return _mjd_price_delta(S, K, T, r, q, sigma,
                                self.lam, self.muJ, self.sigJ, option_type)[1]

    def price_and_delta(self, S, K, T, r, q, sigma, option_type="call"):
        if self.model == "bsm":
            return bsm_price_delta(S, K, T, r, q, sigma, option_type)
        return _mjd_price_delta(S, K, T, r, q, sigma,
                                self.lam, self.muJ, self.sigJ, option_type)

    def strike_from_delta(self, S, T, r, q, sigma, target_delta: float,
                          option_type: str = "call") -> float:
        """Solve for K such that delta == target_delta (call)."""
        if option_type != "call":
            raise NotImplementedError
        # Try tight brackets first, widen if needed
        for lo_mult, hi_mult in ((0.5, 1.8), (0.2, 3.0), (0.05, 6.0)):
            lo, hi = S * lo_mult, S * hi_mult
            f_lo = self.delta(S, lo, T, r, q, sigma, option_type) - target_delta
            f_hi = self.delta(S, hi, T, r, q, sigma, option_type) - target_delta
            if f_lo * f_hi <= 0:
                return brentq(
                    lambda K: self.delta(S, K, T, r, q, sigma, option_type) - target_delta,
                    lo, hi, xtol=1e-3, rtol=1e-4, maxiter=50,
                )
        return lo if abs(f_lo) < abs(f_hi) else hi
