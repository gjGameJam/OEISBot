"""Windows sandbox: a Job Object for resource limits plus an AppContainer for isolation.

Job Object (enforced by the kernel for the whole process tree):
  * commit-charge cap (allocations beyond it fail; we also kill on the limit notification)
  * optional CPU-time cap, one active process (no children), kill-on-close
    (if this harness dies, the job dies with it), below-normal priority, no UI access
AppContainer (a lowbox token with no capabilities):
  * no network at all, loopback included
  * filesystem: only objects whose ACL grants the container SID (or ALL APPLICATION
    PACKAGES, e.g. System32). `grant()` gives read access to the sandbox runtimes and
    modify access to the scratch root; user files stay unreadable and unwritable.

On top of that the harness polls: wall clock, free physical RAM (never let a job push
the machine into paging), and scratch-directory size.
"""
from __future__ import annotations

import ctypes
import msvcrt
import os
import shutil
import subprocess
import threading
import time
from collections import deque
from ctypes import wintypes as wt
from pathlib import Path

from .types import LineCallback, Limits, RunResult, Status, TickCallback

APPCONTAINER_NAME = "OEISBot.Sandbox"

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_adv = ctypes.WinDLL("advapi32", use_last_error=True)
_uenv = ctypes.WinDLL("userenv", use_last_error=True)
_ole = ctypes.WinDLL("ole32")


def _fn(dll, name, restype, *argtypes):
    f = getattr(dll, name)
    f.restype = restype
    f.argtypes = argtypes
    return f


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wt.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wt.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wt.DWORD),
        ("SchedulingClass", wt.DWORD),
    ]


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint64) for n in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class JOBOBJECT_BASIC_ACCOUNTING_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("TotalUserTime", ctypes.c_int64),
        ("TotalKernelTime", ctypes.c_int64),
        ("ThisPeriodTotalUserTime", ctypes.c_int64),
        ("ThisPeriodTotalKernelTime", ctypes.c_int64),
        ("TotalPageFaultCount", wt.DWORD),
        ("TotalProcesses", wt.DWORD),
        ("ActiveProcesses", wt.DWORD),
        ("TotalTerminatedProcesses", wt.DWORD),
    ]


class JOBOBJECT_ASSOCIATE_COMPLETION_PORT(ctypes.Structure):
    _fields_ = [("CompletionKey", ctypes.c_void_p), ("CompletionPort", wt.HANDLE)]


class JOBOBJECT_BASIC_UI_RESTRICTIONS(ctypes.Structure):
    _fields_ = [("UIRestrictionsClass", wt.DWORD)]


class SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("nLength", wt.DWORD), ("lpSecurityDescriptor", ctypes.c_void_p), ("bInheritHandle", wt.BOOL)]


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", wt.DWORD), ("lpReserved", wt.LPWSTR), ("lpDesktop", wt.LPWSTR), ("lpTitle", wt.LPWSTR),
        ("dwX", wt.DWORD), ("dwY", wt.DWORD), ("dwXSize", wt.DWORD), ("dwYSize", wt.DWORD),
        ("dwXCountChars", wt.DWORD), ("dwYCountChars", wt.DWORD), ("dwFillAttribute", wt.DWORD),
        ("dwFlags", wt.DWORD), ("wShowWindow", wt.WORD), ("cbReserved2", wt.WORD),
        ("lpReserved2", ctypes.c_void_p), ("hStdInput", wt.HANDLE), ("hStdOutput", wt.HANDLE),
        ("hStdError", wt.HANDLE),
    ]


class STARTUPINFOEXW(ctypes.Structure):
    _fields_ = [("StartupInfo", STARTUPINFOW), ("lpAttributeList", ctypes.c_void_p)]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [("hProcess", wt.HANDLE), ("hThread", wt.HANDLE), ("dwProcessId", wt.DWORD), ("dwThreadId", wt.DWORD)]


class SECURITY_CAPABILITIES(ctypes.Structure):
    _fields_ = [("AppContainerSid", ctypes.c_void_p), ("Capabilities", ctypes.c_void_p),
                ("CapabilityCount", wt.DWORD), ("Reserved", wt.DWORD)]


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [("dwLength", wt.DWORD), ("dwMemoryLoad", wt.DWORD), ("ullTotalPhys", ctypes.c_uint64),
                ("ullAvailPhys", ctypes.c_uint64), ("ullTotalPageFile", ctypes.c_uint64),
                ("ullAvailPageFile", ctypes.c_uint64), ("ullTotalVirtual", ctypes.c_uint64),
                ("ullAvailVirtual", ctypes.c_uint64), ("ullAvailExtendedVirtual", ctypes.c_uint64)]


_CreateJobObjectW = _fn(_k32, "CreateJobObjectW", wt.HANDLE, ctypes.c_void_p, wt.LPCWSTR)
_SetInformationJobObject = _fn(_k32, "SetInformationJobObject", wt.BOOL, wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.DWORD)
_QueryInformationJobObject = _fn(_k32, "QueryInformationJobObject", wt.BOOL, wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD))
_TerminateJobObject = _fn(_k32, "TerminateJobObject", wt.BOOL, wt.HANDLE, wt.UINT)
_CreateIoCompletionPort = _fn(_k32, "CreateIoCompletionPort", wt.HANDLE, wt.HANDLE, wt.HANDLE, ctypes.c_size_t, wt.DWORD)
_GetQueuedCompletionStatus = _fn(_k32, "GetQueuedCompletionStatus", wt.BOOL, wt.HANDLE, ctypes.POINTER(wt.DWORD), ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_void_p), wt.DWORD)
_CreatePipe = _fn(_k32, "CreatePipe", wt.BOOL, ctypes.POINTER(wt.HANDLE), ctypes.POINTER(wt.HANDLE), ctypes.POINTER(SECURITY_ATTRIBUTES), wt.DWORD)
_SetHandleInformation = _fn(_k32, "SetHandleInformation", wt.BOOL, wt.HANDLE, wt.DWORD, wt.DWORD)
_InitializeProcThreadAttributeList = _fn(_k32, "InitializeProcThreadAttributeList", wt.BOOL, ctypes.c_void_p, wt.DWORD, wt.DWORD, ctypes.POINTER(ctypes.c_size_t))
_UpdateProcThreadAttribute = _fn(_k32, "UpdateProcThreadAttribute", wt.BOOL, ctypes.c_void_p, wt.DWORD, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p)
_DeleteProcThreadAttributeList = _fn(_k32, "DeleteProcThreadAttributeList", None, ctypes.c_void_p)
_CreateProcessW = _fn(_k32, "CreateProcessW", wt.BOOL, wt.LPCWSTR, wt.LPWSTR, ctypes.c_void_p, ctypes.c_void_p, wt.BOOL, wt.DWORD, ctypes.c_void_p, wt.LPCWSTR, ctypes.POINTER(STARTUPINFOEXW), ctypes.POINTER(PROCESS_INFORMATION))
_ResumeThread = _fn(_k32, "ResumeThread", wt.DWORD, wt.HANDLE)
_WaitForSingleObject = _fn(_k32, "WaitForSingleObject", wt.DWORD, wt.HANDLE, wt.DWORD)
_GetExitCodeProcess = _fn(_k32, "GetExitCodeProcess", wt.BOOL, wt.HANDLE, ctypes.POINTER(wt.DWORD))
_CloseHandle = _fn(_k32, "CloseHandle", wt.BOOL, wt.HANDLE)
_GlobalMemoryStatusEx = _fn(_k32, "GlobalMemoryStatusEx", wt.BOOL, ctypes.POINTER(MEMORYSTATUSEX))
_LocalFree = _fn(_k32, "LocalFree", ctypes.c_void_p, ctypes.c_void_p)
_CreateAppContainerProfile = _fn(_uenv, "CreateAppContainerProfile", ctypes.c_long, wt.LPCWSTR, wt.LPCWSTR, wt.LPCWSTR, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(ctypes.c_void_p))
_DeriveAppContainerSid = _fn(_uenv, "DeriveAppContainerSidFromAppContainerName", ctypes.c_long, wt.LPCWSTR, ctypes.POINTER(ctypes.c_void_p))
_GetAppContainerFolderPath = _fn(_uenv, "GetAppContainerFolderPath", ctypes.c_long, wt.LPCWSTR, ctypes.POINTER(wt.LPWSTR))
_ConvertSidToStringSidW = _fn(_adv, "ConvertSidToStringSidW", wt.BOOL, ctypes.c_void_p, ctypes.POINTER(wt.LPWSTR))
_CoTaskMemFree = _fn(_ole, "CoTaskMemFree", None, ctypes.c_void_p)

JobObjectBasicAccountingInformation = 1
JobObjectBasicUIRestrictions = 4
JobObjectAssociateCompletionPortInformation = 7
JobObjectExtendedLimitInformation = 9

JOB_OBJECT_LIMIT_JOB_TIME = 0x4
JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x8
JOB_OBJECT_LIMIT_PRIORITY_CLASS = 0x20
JOB_OBJECT_LIMIT_JOB_MEMORY = 0x200
JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION = 0x400
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
JOB_OBJECT_UILIMIT_ALL = 0xFF

JOB_OBJECT_MSG_END_OF_JOB_TIME = 1
JOB_OBJECT_MSG_END_OF_PROCESS_TIME = 2
JOB_OBJECT_MSG_ACTIVE_PROCESS_LIMIT = 3
JOB_OBJECT_MSG_ACTIVE_PROCESS_ZERO = 4
JOB_OBJECT_MSG_PROCESS_MEMORY_LIMIT = 9
JOB_OBJECT_MSG_JOB_MEMORY_LIMIT = 10

BELOW_NORMAL_PRIORITY_CLASS = 0x4000
CREATE_SUSPENDED = 0x4
DETACHED_PROCESS = 0x8          # no console, hence no conhost.exe to count against the process limit
CREATE_UNICODE_ENVIRONMENT = 0x400
EXTENDED_STARTUPINFO_PRESENT = 0x80000
STARTF_USESTDHANDLES = 0x100
HANDLE_FLAG_INHERIT = 0x1
INVALID_HANDLE_VALUE = wt.HANDLE(-1)
WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 258

PROC_THREAD_ATTRIBUTE_HANDLE_LIST = 0x20002
PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES = 0x20009
PROC_THREAD_ATTRIBUTE_JOB_LIST = 0x2000D
PROC_THREAD_ATTRIBUTE_CHILD_PROCESS_POLICY = 0x2000E
PROCESS_CREATION_CHILD_PROCESS_RESTRICTED = 0x1

E_ALREADY_EXISTS = ctypes.c_long(0x800700B7).value

MIN_JOB_MEM = 256 << 20
MAX_LINE = 1 << 20
DISK_CHECK_INTERVAL_S = 1.0


def _check(ok, what: str):
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error(), what)
    return ok


# ---------------------------------------------------------------- AppContainer identity

_sid_cache: tuple[ctypes.c_void_p, str] | None = None


def appcontainer_sid() -> tuple[ctypes.c_void_p, str]:
    """Create (once) or look up the AppContainer profile; returns (PSID, 'S-1-15-2-...')."""
    global _sid_cache
    if _sid_cache is None:
        psid = ctypes.c_void_p()
        hr = _CreateAppContainerProfile(APPCONTAINER_NAME, "OEISBot sandbox",
                                        "Runs untrusted OEIS sequence programs", None, 0, ctypes.byref(psid))
        if hr == E_ALREADY_EXISTS:
            hr = _DeriveAppContainerSid(APPCONTAINER_NAME, ctypes.byref(psid))
        if hr != 0:
            raise OSError(f"AppContainer profile failed: HRESULT 0x{hr & 0xFFFFFFFF:08X}")
        s = wt.LPWSTR()
        _check(_ConvertSidToStringSidW(psid, ctypes.byref(s)), "ConvertSidToStringSidW")
        text = s.value
        _LocalFree(ctypes.cast(s, ctypes.c_void_p))
        _sid_cache = (psid, text)  # the PSID lives for the whole process
    return _sid_cache


def appcontainer_folder() -> Path | None:
    """The container's own writable profile folder (it can always write there)."""
    _, sid = appcontainer_sid()
    p = wt.LPWSTR()
    if _GetAppContainerFolderPath(sid, ctypes.byref(p)) != 0:
        return None
    path = Path(p.value)
    _CoTaskMemFree(ctypes.cast(p, ctypes.c_void_p))
    return path


def grant(path: Path, access: str) -> None:
    """Grant the container SID inheritable access to a directory. access: 'RX' or 'M'."""
    _, sid = appcontainer_sid()
    subprocess.run(["icacls", str(path), "/grant", f"*{sid}:(OI)(CI){access}", "/Q"],
                   check=True, capture_output=True)


def avail_phys_bytes() -> int:
    st = MEMORYSTATUSEX()
    st.dwLength = ctypes.sizeof(st)
    _check(_GlobalMemoryStatusEx(ctypes.byref(st)), "GlobalMemoryStatusEx")
    return st.ullAvailPhys


# ---------------------------------------------------------------- helpers

def _dir_size(root: Path | None) -> int:
    if root is None:
        return 0
    total = 0
    stack = [str(root)]
    while stack:
        try:
            with os.scandir(stack.pop()) as it:
                for e in it:
                    try:
                        if e.is_dir(follow_symlinks=False):
                            stack.append(e.path)
                        else:
                            # not e.stat(): directory entries report stale sizes for files still open for writing
                            total += os.stat(e.path, follow_symlinks=False).st_size
                    except OSError:
                        pass
        except OSError:
            pass
    return total


def _clear_dir(root: Path) -> None:
    if not root.is_dir():
        return
    for entry in root.iterdir():
        try:
            if entry.is_dir() and not entry.is_symlink():
                shutil.rmtree(entry, ignore_errors=True)
            else:
                entry.unlink()
        except OSError:
            pass


def _env_block(cwd: Path, argv0: str, extra: dict[str, str] | None) -> ctypes.Array:
    sysroot = os.environ.get("SystemRoot", r"C:\Windows")
    env = {
        "SystemRoot": sysroot,
        "windir": sysroot,
        "SystemDrive": os.environ.get("SystemDrive", "C:"),
        "PATH": f"{Path(argv0).parent};{sysroot}\\System32",
        "TEMP": str(cwd), "TMP": str(cwd), "HOME": str(cwd), "USERPROFILE": str(cwd),
        # Required when launching into an AppContainer (else CreateProcess fails with
        # ERROR_ENVVAR_NOT_FOUND); Windows rewrites it, TEMP and TMP to the container folder.
        "LOCALAPPDATA": os.environ.get("LOCALAPPDATA", str(cwd)),
    }
    env.update(extra or {})
    block = "".join(f"{k}={v}\0" for k, v in sorted(env.items(), key=lambda kv: kv[0].upper())) + "\0"
    return ctypes.create_unicode_buffer(block, len(block))


def _pipe(sa: SECURITY_ATTRIBUTES) -> tuple[wt.HANDLE, wt.HANDLE]:
    r, w = wt.HANDLE(), wt.HANDLE()
    _check(_CreatePipe(ctypes.byref(r), ctypes.byref(w), ctypes.byref(sa), 1 << 20), "CreatePipe")
    return r, w


class _Stop:
    def __init__(self):
        self.lock = threading.Lock()
        self.status: Status | None = None
        self.reason: str | None = None
        self.event = threading.Event()

    def request(self, status: Status, reason: str) -> None:
        with self.lock:
            if self.status is None:
                self.status, self.reason = status, reason
                self.event.set()


# ---------------------------------------------------------------- run

def run(argv: list[str], *, cwd: Path, limits: Limits, env: dict[str, str] | None = None,
        on_line: LineCallback | None = None, on_tick: TickCallback | None = None,
        tick_s: float = 0.25) -> RunResult:
    cwd = Path(cwd).resolve()
    argv = [str(a) for a in argv]
    avail = avail_phys_bytes()
    mem_cap = min(limits.mem_bytes, avail - limits.reserve_phys_bytes)
    if mem_cap < MIN_JOB_MEM:
        return RunResult(Status.LAUNCH_ERROR, None, 0.0, 0.0, 0, max(mem_cap, 0),
                         f"only {avail / 2**30:.1f} GiB physical RAM free (reserve {limits.reserve_phys_bytes / 2**30:.1f} GiB)")

    handles: list[wt.HANDLE] = []

    def close(h):
        if h and h.value and h in handles:
            _CloseHandle(h)
            handles.remove(h)

    job = _CreateJobObjectW(None, None)
    _check(job, "CreateJobObjectW")
    job = wt.HANDLE(job)
    port = wt.HANDLE(_check(_CreateIoCompletionPort(INVALID_HANDLE_VALUE, None, 0, 1), "CreateIoCompletionPort"))
    handles += [job, port]
    try:
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        basic = info.BasicLimitInformation
        basic.LimitFlags = (JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION
                            | JOB_OBJECT_LIMIT_JOB_MEMORY | JOB_OBJECT_LIMIT_ACTIVE_PROCESS)
        basic.ActiveProcessLimit = 1
        info.JobMemoryLimit = mem_cap
        if limits.cpu_s:
            basic.LimitFlags |= JOB_OBJECT_LIMIT_JOB_TIME
            basic.PerJobUserTimeLimit = int(limits.cpu_s * 1e7)
        if limits.low_priority:
            basic.LimitFlags |= JOB_OBJECT_LIMIT_PRIORITY_CLASS
            basic.PriorityClass = BELOW_NORMAL_PRIORITY_CLASS
        _check(_SetInformationJobObject(job, JobObjectExtendedLimitInformation, ctypes.byref(info), ctypes.sizeof(info)), "job limits")
        ui = JOBOBJECT_BASIC_UI_RESTRICTIONS(JOB_OBJECT_UILIMIT_ALL)
        _check(_SetInformationJobObject(job, JobObjectBasicUIRestrictions, ctypes.byref(ui), ctypes.sizeof(ui)), "job UI limits")
        assoc = JOBOBJECT_ASSOCIATE_COMPLETION_PORT(1, port)
        _check(_SetInformationJobObject(job, JobObjectAssociateCompletionPortInformation, ctypes.byref(assoc), ctypes.sizeof(assoc)), "job completion port")

        sa = SECURITY_ATTRIBUTES(ctypes.sizeof(SECURITY_ATTRIBUTES), None, True)
        in_r, in_w = _pipe(sa)
        out_r, out_w = _pipe(sa)
        err_r, err_w = _pipe(sa)
        handles += [in_r, in_w, out_r, out_w, err_r, err_w]
        for h in (in_w, out_r, err_r):
            _check(_SetHandleInformation(h, HANDLE_FLAG_INHERIT, 0), "SetHandleInformation")

        inherit = (wt.HANDLE * 3)(in_r, out_w, err_w)
        job_list = (wt.HANDLE * 1)(job)
        child_policy = wt.DWORD(PROCESS_CREATION_CHILD_PROCESS_RESTRICTED)
        attrs: list[tuple[int, ctypes._CData]] = [
            (PROC_THREAD_ATTRIBUTE_HANDLE_LIST, inherit),
            (PROC_THREAD_ATTRIBUTE_JOB_LIST, job_list),
            (PROC_THREAD_ATTRIBUTE_CHILD_PROCESS_POLICY, child_policy),
        ]
        container_dir = None
        if limits.isolate:
            psid, _ = appcontainer_sid()
            caps = SECURITY_CAPABILITIES(psid, None, 0, 0)
            attrs.append((PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES, caps))
            container_dir = appcontainer_folder()
        container_baseline = _dir_size(container_dir)

        size = ctypes.c_size_t(0)
        _InitializeProcThreadAttributeList(None, len(attrs), 0, ctypes.byref(size))
        attr_buf = ctypes.create_string_buffer(size.value)
        _check(_InitializeProcThreadAttributeList(attr_buf, len(attrs), 0, ctypes.byref(size)), "InitializeProcThreadAttributeList")
        try:
            for attr_id, obj in attrs:
                _check(_UpdateProcThreadAttribute(attr_buf, 0, attr_id, ctypes.addressof(obj), ctypes.sizeof(obj), None, None),
                       f"UpdateProcThreadAttribute(0x{attr_id:X})")
            si = STARTUPINFOEXW()
            si.StartupInfo.cb = ctypes.sizeof(STARTUPINFOEXW)
            si.StartupInfo.dwFlags = STARTF_USESTDHANDLES
            si.StartupInfo.hStdInput, si.StartupInfo.hStdOutput, si.StartupInfo.hStdError = in_r, out_w, err_w
            si.lpAttributeList = ctypes.addressof(attr_buf)
            pi = PROCESS_INFORMATION()
            cmdline = ctypes.create_unicode_buffer(subprocess.list2cmdline(argv))
            env_buf = _env_block(cwd, argv[0], env)
            flags = CREATE_SUSPENDED | DETACHED_PROCESS | EXTENDED_STARTUPINFO_PRESENT | CREATE_UNICODE_ENVIRONMENT
            if not _CreateProcessW(argv[0], cmdline, None, None, True, flags, ctypes.addressof(env_buf), str(cwd),
                                   ctypes.byref(si), ctypes.byref(pi)):
                err = ctypes.WinError(ctypes.get_last_error())
                return RunResult(Status.LAUNCH_ERROR, None, 0.0, 0.0, 0, mem_cap, f"CreateProcess: {err}")
        finally:
            _DeleteProcThreadAttributeList(attr_buf)

        proc, thread = wt.HANDLE(pi.hProcess), wt.HANDLE(pi.hThread)
        handles += [proc, thread]
        for h in (in_r, out_w, err_w, in_w):   # child's ends, and stdin write end (child sees EOF)
            close(h)

        stop = _Stop()
        cb_lock = threading.Lock()
        stdout_tail: deque[str] = deque(maxlen=200)
        stderr_tail: deque[bytes] = deque()
        stderr_size = [0]
        t_start = [0.0]

        out_file = os.fdopen(msvcrt.open_osfhandle(out_r.value, os.O_RDONLY), "rb", buffering=1 << 16)
        handles.remove(out_r)
        err_file = os.fdopen(msvcrt.open_osfhandle(err_r.value, os.O_RDONLY), "rb", buffering=1 << 16)
        handles.remove(err_r)

        def read_stdout():
            total = 0
            skipping = False
            with out_file:
                while True:
                    chunk = out_file.readline(MAX_LINE)
                    if not chunk:
                        return
                    total += len(chunk)
                    if stop.event.is_set():
                        continue  # keep draining so the child never blocks on a full pipe
                    if total > limits.output_bytes:
                        stop.request(Status.OUTPUT_CAP, f"stdout exceeded {limits.output_bytes} bytes")
                        continue
                    complete = chunk.endswith(b"\n")
                    if skipping:
                        skipping = not complete
                        continue
                    if not complete and len(chunk) == MAX_LINE:
                        stop.request(Status.OUTPUT_CAP, f"stdout line longer than {MAX_LINE} bytes")
                        skipping = True
                        continue
                    line = chunk.decode("utf-8", "replace").rstrip("\r\n")
                    stdout_tail.append(line[:2000])
                    if on_line is not None:
                        t = time.perf_counter() - t_start[0]
                        with cb_lock:
                            reason = on_line(line, t)
                        if reason:
                            stop.request(Status.STOPPED, reason)

        def read_stderr():
            with err_file:
                while True:
                    chunk = err_file.read1(1 << 16)
                    if not chunk:
                        return
                    stderr_tail.append(chunk)
                    stderr_size[0] += len(chunk)
                    while stderr_size[0] > (64 << 10) and len(stderr_tail) > 1:
                        stderr_size[0] -= len(stderr_tail.popleft())

        readers = [threading.Thread(target=read_stdout, daemon=True), threading.Thread(target=read_stderr, daemon=True)]
        for r in readers:
            r.start()

        t_start[0] = time.perf_counter()
        if _ResumeThread(thread) == 0xFFFFFFFF:
            _TerminateJobObject(job, 1)
            raise ctypes.WinError(ctypes.get_last_error(), "ResumeThread")
        close(thread)

        msg, key, ov = wt.DWORD(), ctypes.c_size_t(), ctypes.c_void_p()
        job_msg_status: Status | None = None
        next_disk_check = 0.0
        wait_ms = max(10, int(min(tick_s, 0.1) * 1000))
        next_tick = 0.0

        def handle_msg(m: int) -> None:
            nonlocal job_msg_status
            if m in (JOB_OBJECT_MSG_JOB_MEMORY_LIMIT, JOB_OBJECT_MSG_PROCESS_MEMORY_LIMIT):
                job_msg_status = job_msg_status or Status.MEMORY_CAP
                stop.request(Status.MEMORY_CAP, f"job commit reached cap of {mem_cap} bytes")
            elif m in (JOB_OBJECT_MSG_END_OF_JOB_TIME, JOB_OBJECT_MSG_END_OF_PROCESS_TIME):
                job_msg_status = job_msg_status or Status.CPU_CAP
                stop.request(Status.CPU_CAP, f"CPU time reached {limits.cpu_s} s")
            elif m == JOB_OBJECT_MSG_ACTIVE_PROCESS_LIMIT:
                stop.request(Status.STOPPED, "tried to start a child process")

        while True:
            if _GetQueuedCompletionStatus(port, ctypes.byref(msg), ctypes.byref(key), ctypes.byref(ov), wait_ms):
                handle_msg(msg.value)
            if stop.event.is_set():
                _TerminateJobObject(job, 1)
                break
            if _WaitForSingleObject(proc, 0) == WAIT_OBJECT_0:
                break
            elapsed = time.perf_counter() - t_start[0]
            if elapsed >= limits.wall_s:
                stop.request(Status.TIMEOUT, f"wall clock reached {limits.wall_s:g} s")
                continue
            if elapsed >= next_disk_check:
                next_disk_check = elapsed + DISK_CHECK_INTERVAL_S
                used = _dir_size(cwd) + max(0, _dir_size(container_dir) - container_baseline)
                if used > limits.disk_bytes:
                    stop.request(Status.DISK_CAP, f"scratch usage {used} bytes > {limits.disk_bytes}")
                    continue
                if shutil.disk_usage(cwd).free < limits.reserve_disk_bytes:
                    stop.request(Status.DISK_CAP, f"free disk below {limits.reserve_disk_bytes} bytes")
                    continue
                if avail_phys_bytes() < limits.reserve_phys_bytes // 2:
                    stop.request(Status.MEMORY_CAP, "system physical RAM running low; stopping before paging")
                    continue
            if on_tick is not None and elapsed >= next_tick:
                next_tick = elapsed + tick_s
                with cb_lock:
                    reason = on_tick(elapsed)
                if reason:
                    stop.request(Status.STOPPED, reason)

        _WaitForSingleObject(proc, 10_000)
        wall = time.perf_counter() - t_start[0]
        for r in readers:
            r.join(timeout=10)
        # messages that raced with a natural exit (e.g. MemoryError caught and exited)
        while _GetQueuedCompletionStatus(port, ctypes.byref(msg), ctypes.byref(key), ctypes.byref(ov), 0):
            handle_msg(msg.value)

        if container_dir is not None:
            _clear_dir(container_dir / "Temp")

        code = wt.DWORD()
        exit_code = code.value if _GetExitCodeProcess(proc, ctypes.byref(code)) else None
        acct = JOBOBJECT_BASIC_ACCOUNTING_INFORMATION()
        _QueryInformationJobObject(job, JobObjectBasicAccountingInformation, ctypes.byref(acct), ctypes.sizeof(acct), None)
        ext = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        _QueryInformationJobObject(job, JobObjectExtendedLimitInformation, ctypes.byref(ext), ctypes.sizeof(ext), None)

        if stop.status is None:
            status, reason = (job_msg_status or Status.EXITED), None
        else:
            status, reason = stop.status, stop.reason
        if status is Status.EXITED and job_msg_status is not None:
            status = job_msg_status
        return RunResult(
            status=status,
            exit_code=exit_code,
            wall_s=wall,
            cpu_s=(acct.TotalUserTime + acct.TotalKernelTime) / 1e7,
            # Windows counts a *refused* commit (e.g. one 16 GiB allocation against a 6 GiB cap) in the
            # job's peak, so the raw value can exceed the cap without that memory ever being granted
            peak_mem_bytes=min(ext.PeakJobMemoryUsed, mem_cap),
            mem_cap_bytes=mem_cap,
            stop_reason=reason,
            stdout_tail=list(stdout_tail),
            stderr_tail=b"".join(stderr_tail).decode("utf-8", "replace")[-(64 << 10):],
        )
    finally:
        for h in list(reversed(handles)):   # job handle last: closing it kills anything left
            _CloseHandle(h)
