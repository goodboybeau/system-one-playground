import time
from collections import deque
from types import SimpleNamespace

from gateway.jobs import resources
from gateway.procmon import ProcSample


def s(t, fp, cpu=50.0):
    return ProcSample(t=t, cpu_percent=cpu, cpu_seconds=0, footprint=fp, rss=fp, threads=1)


def test_resources_inside_window():
    run = SimpleNamespace(samples=deque([s(1, 10), s(2, 30), s(3, 20), s(9, 99)]))
    r = resources(run, 1.5, 3.5)
    assert r == {"samples": 2, "cpu_avg": 50.0, "cpu_peak": 50.0, "footprint_peak": 30, "footprint_start": 30}


def test_short_window_uses_neighbouring_samples():
    run = SimpleNamespace(samples=deque([s(1, 10), s(2, 30)]))
    assert resources(run, 1.2, 1.3)["footprint_peak"] == 30
    assert resources(run, 5, 6)["footprint_peak"] == 30


def test_no_samples():
    assert resources(SimpleNamespace(samples=deque()), time.time(), time.time()) == {"samples": 0}
