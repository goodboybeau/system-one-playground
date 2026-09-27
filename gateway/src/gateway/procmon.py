"""Process and system measurements on macOS.

Memory is the process's physical footprint (what Activity Monitor calls "Memory"), read
with proc_pid_rusage. On Apple Silicon that includes Metal buffers in unified memory,
which RSS does not, so MPS and MLX models are measured honestly. RSS is kept alongside.

CPU is psutil's per-process CPU time; 100% means one core busy. GPU utilisation comes
from the IOAccelerator's performance statistics (ioreg, no sudo) and is system-wide:
macOS does not attribute GPU time to processes without root.
"""

from __future__ import annotations

import ctypes
import re
import subprocess
import time
from dataclasses import dataclass

import psutil

_libproc = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
_RUSAGE_INFO_V2 = 2


class _RusageInfoV2(ctypes.Structure):
    _fields_ = [
        ("ri_uuid", ctypes.c_uint8 * 16),
        ("ri_user_time", ctypes.c_uint64),
        ("ri_system_time", ctypes.c_uint64),
        ("ri_pkg_idle_wkups", ctypes.c_uint64),
        ("ri_interrupt_wkups", ctypes.c_uint64),
        ("ri_pageins", ctypes.c_uint64),
        ("ri_wired_size", ctypes.c_uint64),
        ("ri_resident_size", ctypes.c_uint64),
        ("ri_phys_footprint", ctypes.c_uint64),
        ("ri_proc_start_abstime", ctypes.c_uint64),
        ("ri_proc_exit_abstime", ctypes.c_uint64),
        ("ri_child_user_time", ctypes.c_uint64),
        ("ri_child_system_time", ctypes.c_uint64),
        ("ri_child_pkg_idle_wkups", ctypes.c_uint64),
        ("ri_child_interrupt_wkups", ctypes.c_uint64),
        ("ri_child_pageins", ctypes.c_uint64),
        ("ri_child_elapsed_abstime", ctypes.c_uint64),
        ("ri_diskio_bytesread", ctypes.c_uint64),
        ("ri_diskio_byteswritten", ctypes.c_uint64),
    ]


def phys_footprint(pid: int) -> int | None:
    info = _RusageInfoV2()
    if _libproc.proc_pid_rusage(pid, _RUSAGE_INFO_V2, ctypes.byref(info)) != 0:
        return None
    return int(info.ri_phys_footprint)


@dataclass
class ProcSample:
    t: float
    cpu_percent: float
    cpu_seconds: float
    footprint: int
    rss: int
    threads: int


class ProcessMeter:
    """Samples one process. cpu_percent is measured between consecutive samples."""

    def __init__(self, pid: int):
        self.proc = psutil.Process(pid)
        self._last: tuple[float, float] | None = None

    def cpu_seconds(self) -> float:
        t = self.proc.cpu_times()
        return t.user + t.system

    def sample(self) -> ProcSample | None:
        try:
            with self.proc.oneshot():
                now = time.monotonic()
                cpu = self.cpu_seconds()
                mem = self.proc.memory_info()
                threads = self.proc.num_threads()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return None
        percent = 0.0
        if self._last is not None and now > self._last[0]:
            percent = 100 * (cpu - self._last[1]) / (now - self._last[0])
        self._last = (now, cpu)
        footprint = phys_footprint(self.proc.pid)
        return ProcSample(t=time.time(), cpu_percent=max(0.0, percent), cpu_seconds=cpu,
                          footprint=footprint if footprint is not None else mem.rss, rss=mem.rss, threads=threads)


_GPU_UTIL = re.compile(rb'"Device Utilization %"=(\d+)')
_GPU_MEM = re.compile(rb'"In use system memory"=(\d+)')


def gpu_stats() -> tuple[float | None, int | None]:
    """(utilisation %, bytes of GPU-allocated system memory), system-wide, or Nones."""
    try:
        out = subprocess.run(["ioreg", "-r", "-d", "1", "-w", "0", "-c", "IOAccelerator"],
                             capture_output=True, timeout=2, check=False).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None, None
    util = _GPU_UTIL.search(out)
    mem = _GPU_MEM.search(out)
    return (float(util.group(1)) if util else None, int(mem.group(1)) if mem else None)


@dataclass
class SystemSample:
    t: float
    cpu_percent: float
    memory_used: int
    memory_total: int
    gpu_percent: float | None
    gpu_memory: int | None


def system_sample() -> SystemSample:
    vm = psutil.virtual_memory()
    gpu, gpu_mem = gpu_stats()
    return SystemSample(t=time.time(), cpu_percent=psutil.cpu_percent(interval=None),
                        memory_used=vm.total - vm.available, memory_total=vm.total,
                        gpu_percent=gpu, gpu_memory=gpu_mem)
