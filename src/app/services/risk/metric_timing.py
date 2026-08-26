from collections.abc import Callable
from contextlib import AbstractContextManager

MetricDurationObserver = Callable[[str], AbstractContextManager[None]]


__all__ = ["MetricDurationObserver"]
