# -*- coding: utf-8 -*-
"""Disk scanner - tree-based, skips junk, signals progress."""
import os, time, threading, sys as _sys
from PySide6.QtCore import QThread, Signal

SKIP_NAMES = frozenset({
    "$Recycle.Bin", "$RECYCLE.BIN", "System Volume Information",
    "$Windows.~WS", "$WinREAgent", "Config.Msi", "MSOCache",
    "Recovery", "PerfLogs", "Documents and Settings",
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    "Temp", "tmp", "cache", ".cache", "logs", "Logs",
    "Windows", "WinSxS",
})

# Directories to skip entirely (won't even enter)
SKIP_ROOTS = frozenset({
    "C:\Windows",
    "C:\ProgramData\Packages",
})

# Priority scan paths - scanned first, results shown immediately
PRIORITY_PATHS = []  # Will be populated dynamically

SKIP_EXTS = frozenset({
    ".tmp", ".log", ".cache", ".etl", ".evtx", ".pf", ".dmp",
    ".dat", ".bin", ".db", ".sqlite", ".sqlite3",
    ".idx", ".index", ".lock", ".pid",
})

EMIT_INTERVAL_FILES = 8000
EMIT_INTERVAL_SECS = 1.2

class ScanNode:
    __slots__ = ("path", "name", "size", "file_count", "children", "large_files", "is_priority",
                 "is_dir", "mtime", "ext", "safety")
    def __init__(self, path, name, size=0, is_dir=False):
        self.path = path
        self.name = name
        self.size = size
        self.file_count = 0
        self.children = []
        self.is_dir = is_dir
        self.mtime = 0
        self.ext = ""
        self.safety = None
        self.large_files = []
        self.is_priority = False

class ScanWorker(QThread):
    progress = Signal(int, str)
    scan_finished = Signal(object)
    status_update = Signal(str)

    def __init__(self, root_path, scan_limit=50000, min_size_mb=1):
        super().__init__()
        self.root_path = root_path
        self.scan_limit = scan_limit
        self.min_size = min_size_mb * 1048576
        self._cancel = threading.Event()
        self._file_count = 0
        self._byte_count = 0
        self._last_emit = 0.0
        self._emit_count = 0

    def cancel(self):
        self._cancel.set()

    def _maybe_emit(self, force=False):
        self._emit_count += 1
        if force or self._emit_count >= EMIT_INTERVAL_FILES:
            now = time.time()
            if force or now - self._last_emit >= EMIT_INTERVAL_SECS:
                self.progress.emit(self._file_count, _fmt(self._byte_count))
                self._last_emit = now
                self._emit_count = 0

    def run(self):
        import os as _os
        _sys.setrecursionlimit(20000)
        t0 = time.time()
        self._file_count = 0
        self._byte_count = 0
        self._last_emit = t0
        self._emit_count = 0
        self._results_sent = False

        # Build priority paths
        userprofile = _os.environ.get("USERPROFILE", "C:\\Users")
        homedrive = _os.environ.get("HOMEDRIVE", "C:")
        priority = []
        for sub in ["Desktop", "Downloads", "Documents", "Pictures", "Videos", "Music"]:
            p = _os.path.join(userprofile, sub)
            if _os.path.isdir(p):
                priority.append(p)

        self.status_update.emit("Phase 1/2: 扫描用户目录...")
        root_children = []

        # Phase 1: Scan priority paths
        for pp in priority:
            if self._cancel.is_set(): break
            try:
                sub = self._scan_dir(pp, _os.path.basename(pp))
                sub.is_priority = True
                root_children.append(sub)
            except Exception:
                pass

        # Phase 2: Scan remaining drive (skip Windows, skip already-scanned dirs)
        if not self._cancel.is_set():
            self.status_update.emit("Phase 2/2: 扫描其它目录...")
            scanned_paths = {_os.path.normpath(p) for p in priority}
            try:
                entries = _os.scandir(self.root_path)
            except Exception:
                entries = []
            for entry in entries:
                if self._cancel.is_set(): break
                try:
                    if not entry.is_dir(follow_symlinks=False):
                        continue
                    ename = entry.name
                    epath = _os.path.normpath(entry.path)
                    if ename == "Windows":
                        continue
                    if ename in SKIP_NAMES or ename[:1] in (".", "$"):
                        continue
                    if epath == _os.path.normpath(userprofile):
                        continue
                    if any(epath.startswith(sp) for sp in scanned_paths):
                        continue
                    sub = self._scan_dir(epath, ename)
                    if sub.file_count > 0 or sub.size > 0:
                        root_children.append(sub)
                except Exception:
                    continue
            try:
                entries.close()
            except Exception:
                pass

        # Build fake root
        total_size = sum(c.size for c in root_children)
        total_files = sum(c.file_count for c in root_children)
        root_children.sort(key=lambda x: x.size, reverse=True)

        root = ScanNode(self.root_path, self.root_path, size=total_size, is_dir=True)
        root.children = root_children
        root.file_count = total_files

        elapsed = time.time() - t0
        self._maybe_emit(force=True)
        root.large_files = self._collect_large_files(root)
        self.status_update.emit(
            "完成: " + str(total_files) + " 文件, " + _fmt(total_size) +
            " (" + str(round(elapsed, 1)) + "s), " + str(len(root.large_files)) + " 个大文件"
        )
        self.scan_finished.emit(root)

    _LARGE_EXTS = frozenset({'.py','.pyd','.js','.ts','.java','.c','.cpp','.h','.hpp','.json','.xml','.yaml','.yml','.toml','.ini','.cfg','.conf','.css','.html','.htm','.php','.rb','.go','.rs','.swift','.kt','.lua','.sql','.sh','.bat','.ps1','.cs','.vb','.r','.m','.mm','.pl','.pm','.tcl','.dart','.ex','.exs','.erl','.hs','.nim','.zig','.v','.sv','.scala','.clj','.rkt','.fs','.fsx','.psm1','.psd1','.ipynb','.md','.txt','.csv','.log'})

    def _collect_large_files(self, root):
        result = []
        stack = [root]
        min_size = getattr(self, 'min_size', 1048576)
        limit = getattr(self, 'scan_limit', 50000)
        while stack and len(result) < limit:
            n = stack.pop()
            for child in getattr(n, 'children', []):
                if getattr(child, 'is_dir', False):
                    stack.append(child)
                elif getattr(child, 'size', 0) >= min_size or getattr(child, 'ext', '') in self._LARGE_EXTS:
                    result.append(child)
        return result

    def _scan_dir(self, dirpath, relname, depth=0):
        if self._cancel.is_set() or depth > 150:
            return ScanNode(dirpath, relname or os.path.basename(dirpath) or dirpath, is_dir=True)
        name = relname or os.path.basename(dirpath) or dirpath
        node = ScanNode(dirpath, name, is_dir=True)
        try:
            entries = os.scandir(dirpath)
        except (PermissionError, OSError, NotADirectoryError):
            return node

        total_size = 0; total_files = 0
        children = []; subdirs = []

        for entry in entries:
            if self._cancel.is_set(): break
            try:
                if entry.is_dir(follow_symlinks=False):
                    ename = entry.name
                    if ename in SKIP_NAMES or ename[:1] in (".", "$"):
                        continue
                    subdirs.append((entry.path, ename))
                else:
                    try:
                        st = entry.stat()
                        fsize = st.st_size
                    except OSError:
                        continue
                    if fsize < 512:
                        ext = os.path.splitext(entry.name)[1].lower()
                        if ext in SKIP_EXTS:
                            continue
                    fn_node = ScanNode(entry.path, entry.name, size=fsize)
                    fn_node.mtime = st.st_mtime
                    fn_node.ext = os.path.splitext(entry.name)[1].lower()
                    total_size += fsize; total_files += 1
                    children.append(fn_node)
                    self._file_count += 1
                    self._byte_count += fsize
                    self._maybe_emit()
            except OSError:
                continue

        try:
            entries.close()
        except Exception:
            pass

        for sub_path, sub_name in subdirs:
            if self._cancel.is_set(): break
            try:
                sub = self._scan_dir(sub_path, sub_name, depth + 1)
            except Exception:
                sub = ScanNode(sub_path, sub_name, is_dir=True)
            children.append(sub)
            total_size += sub.size
            total_files += sub.file_count

        children.sort(key=lambda x: x.size, reverse=True)
        node.children = children
        node.size = total_size
        node.file_count = total_files
        return node
def _fmt(s):
    if s < 1024: return str(s) + " B"
    if s < 1048576: return str(round(s / 1024, 1)) + " KB"
    if s < 1073741824: return str(round(s / 1048576, 1)) + " MB"
    if s < 1099511627776: return str(round(s / 1073741824, 2)) + " GB"
    return str(round(s / 1099511627776, 2)) + " TB"
