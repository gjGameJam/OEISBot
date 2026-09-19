"""Sandbox-side driver for Python candidates. Copied into the scratch dir; runs under the sandbox interpreter.

Contract for a candidate module (what the executed program must provide; a model program for a list of
numbers defines `members(work)` instead, and strategies/codegen.py appends a driver that defines `terms`):

    def terms(work):
        '''Yield (n, a(n)) pairs for n = offset, offset+1, ... in order, forever or until done.
        Call work(k) to report k units of instrumented work (nodes visited, states expanded,
        candidates tested...). Counts should reflect effort, not wall time.'''

Output, one line per term (cumulative cpu/work; memory = peak private bytes since the previous term):
    @T <n> <value> <cpu_us> <work> <mem_bytes>
then @DONE, or @ERR <message> with a traceback on stderr and exit code 3.
"""
import importlib.util
import operator
import sys
import threading
import time
import traceback


def _memory_probe():
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes as wt

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t), ("PrivateUsage", ctypes.c_size_t)]

        k32 = ctypes.WinDLL("kernel32")
        k32.GetCurrentProcess.restype = wt.HANDLE
        k32.K32GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(PMC), wt.DWORD]
        handle, pmc = k32.GetCurrentProcess(), PMC()
        pmc.cb = ctypes.sizeof(PMC)

        def probe():
            k32.K32GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb)
            return pmc.PrivateUsage
        return probe

    import os
    page = os.sysconf("SC_PAGE_SIZE")

    def probe():
        with open("/proc/self/statm") as f:
            return int(f.read().split()[1]) * page
    return probe


class _PeakSampler(threading.Thread):
    def __init__(self, probe, interval=0.02):
        super().__init__(daemon=True)
        self.probe, self.interval = probe, interval
        self.peak = probe()

    def run(self):
        while True:
            m = self.probe()
            if m > self.peak:
                self.peak = m
            time.sleep(self.interval)

    def take(self):
        current = self.probe()
        peak = max(self.peak, current)
        self.peak = current
        return peak


class Work:
    __slots__ = ("count",)

    def __init__(self):
        self.count = 0

    def __call__(self, k=1):
        self.count += k


def _fail(out, message):
    traceback.print_exc()
    out.write("@ERR " + " ".join(str(message).split())[:500] + "\n")
    out.flush()
    sys.exit(3)


def main(argv):
    sys.set_int_max_str_digits(0)
    out = sys.stdout
    try:
        spec = importlib.util.spec_from_file_location("candidate", argv[1])
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        generate = module.terms
    except Exception as e:
        _fail(out, f"loading candidate: {type(e).__name__}: {e}")
    sampler = _PeakSampler(_memory_probe())
    sampler.start()
    work = Work()
    try:
        for item in generate(work):
            n, value = item
            n, value = operator.index(n), operator.index(value)
            out.write(f"@T {n} {value} {time.process_time_ns() // 1000} {work.count} {sampler.take()}\n")
            out.flush()
    except Exception as e:
        _fail(out, f"{type(e).__name__}: {e}")
    out.write("@DONE\n")
    out.flush()


if __name__ == "__main__":
    main(sys.argv)
