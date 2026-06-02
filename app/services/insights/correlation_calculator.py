"""
correlation_calculator — iki zaman serisi arası Pearson korelasyonu.

Saf Python (numpy yok). Detector'lar iki entegrasyonun günlük kayıt
serisini buradan hizalayıp korelasyona sokar.
"""

from __future__ import annotations

import math

from app.services.insights import metric_calculator as mc


def pearson(xs: list[float], ys: list[float]) -> float | None:
    """
    İki eşit uzunluktaki serinin Pearson korelasyon katsayısı (-1..1).
    Tanımsızsa (varyans 0, n<3) None döner.
    """
    n = len(xs)
    if n < 3 or n != len(ys):
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x == 0 or var_y == 0:
        return None
    return cov / math.sqrt(var_x * var_y)


def aligned_daily_series(table_a: str, table_b: str,
                         start: str, end: str) -> tuple[list[float], list[float], list[str]]:
    """
    İki tablonun günlük sayımlarını ortak takvim üzerinde hizalar.
    Eksik günler 0 ile doldurulur.

    Döner: (seri_a, seri_b, gun_etiketleri)
    """
    days   = mc.date_series(start, end)
    map_a  = mc.daily_counts(table_a, start, end)
    map_b  = mc.daily_counts(table_b, start, end)
    xs = [float(map_a.get(d, 0)) for d in days]
    ys = [float(map_b.get(d, 0)) for d in days]
    return xs, ys, days


def best_lagged_correlation(xs: list[float], ys: list[float],
                            max_lag: int = 3) -> tuple[float | None, int]:
    """
    ys'yi -max_lag..+max_lag arası kaydırarak en güçlü |korelasyonu| bulur.
    Pozitif lag = B serisi A'dan SONRA hareket ediyor (A → B öncül ilişki).

    Döner: (en_iyi_korelasyon, lag).  Korelasyon yoksa (None, 0).
    """
    best_r   : float | None = None
    best_lag : int = 0

    for lag in range(-max_lag, max_lag + 1):
        if lag == 0:
            a, b = xs, ys
        elif lag > 0:
            # ys'yi geriye kaydır: a[t] ~ b[t+lag]
            a, b = xs[:-lag], ys[lag:]
        else:
            a, b = xs[-lag:], ys[:lag]

        r = pearson(a, b)
        if r is None:
            continue
        if best_r is None or abs(r) > abs(best_r):
            best_r, best_lag = r, lag

    return best_r, best_lag
