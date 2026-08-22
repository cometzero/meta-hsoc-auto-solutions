from __future__ import annotations

import math
import statistics
from collections.abc import Mapping, Sequence


REAL_MAX_SAMPLE_SPREAD_RATIO = 1.5
USER_MAX_SAMPLE_SPREAD_RATIO = 2.5
MIN_MEDIAN_IMPROVEMENT_RATIO = 1.25


def _metric_values(
    samples: Sequence[Mapping[str, float]],
    metric: str,
) -> list[float]:
    if len(samples) < 3:
        raise ValueError("crypto_insufficient_samples")
    values: list[float] = []
    for sample in samples:
        value = sample.get(metric)
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError(f"crypto_invalid_{metric}_sample")
        numeric = float(value)
        if not math.isfinite(numeric) or numeric <= 0:
            raise ValueError(f"crypto_invalid_{metric}_sample")
        values.append(numeric)
    maximum_spread = (
        REAL_MAX_SAMPLE_SPREAD_RATIO
        if metric == "real"
        else USER_MAX_SAMPLE_SPREAD_RATIO
    )
    if max(values) / min(values) > maximum_spread:
        raise ValueError(f"crypto_unstable_{metric}_samples")
    return values


def validate_crypto_samples(
    enabled: Sequence[Mapping[str, float]],
    disabled: Sequence[Mapping[str, float]],
) -> dict[str, tuple[float, float]]:
    medians: dict[str, tuple[float, float]] = {}
    for metric in ("real", "user"):
        enabled_median = statistics.median(_metric_values(enabled, metric))
        disabled_median = statistics.median(_metric_values(disabled, metric))
        if disabled_median < enabled_median * MIN_MEDIAN_IMPROVEMENT_RATIO:
            raise ValueError(f"crypto_insufficient_{metric}_improvement")
        medians[metric] = (enabled_median, disabled_median)
    return medians
