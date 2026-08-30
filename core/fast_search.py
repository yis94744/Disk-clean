# -*- coding: utf-8 -*-
"""极速文件搜索：NTFS MFT(USN) 直读索引 + 大字符串 memchr 查询。

原理参考 voidtools Everything（MFT 直读 + 内存索引）：
- 构建：FSCTL_ENUM_USN_DATA 顺序枚举整卷 MFT 文件记录，O(文件总数)，
  只做一次顺序磁盘读；50 万文件约 3~6 秒（需要管理员权限）。
- 查询：全部文件名（小写副本）打包进一个大字符串，str.find 走 C 级
  memchr，单次扫描 O(索引字节数)——百万级索引毫秒级返回；命中偏移用
  bisect O(log n) 映射回文件记录，超限即提前停止。
- 空间：打包字符串(原始+小写副本) + FRN/偏移平行数组，约为
  "名字→全路径 dict"朴素方案的 1/5；路径按需从父链重建（Everything 同款省内存思路）。
"""
import ctypes
import struct
import time
from array import array
from bisect import bisect_right

from PySide6.QtCore import QThread, Signal

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

FSCTL_ENUM_USN_DATA = 0x000900B0  # CTL_CODE(FILE_DEVICE_FILE_SYSTEM, 44, METHOD_BUFFERED, FILE_ANY_ACCESS)
ERROR_HANDLE_EOF = 38
FILE_ATTRIBUTE_DIRECTORY = 0x10

_USN_HDR = struct.Struct("<IHQQQqIIIIHH")  # USN_RECORD_V2 头（60 字节）


class _MFT_ENUM_DATA_V0(ctypes.Structure):
    _fields_ = [("StartFileReferenceNumber", ctypes.c_ulonglong)]


def _open_volume(letter):
    h = _kernel32.CreateFileW(
        ctypes.c_wchar_p("\\\\.\\" + letter),
        0,                       # 仅元数据查询，无需读写权限
        1 | 2 | 4,               # 共享读/写/删除
        None, 3, 0, None)        # OPEN_EXISTING
    return h


def _close(h):
    if h not in (None, -1, 0):
        _kernel32.CloseHandle(h)


def enum_volume_usn(letter, should_cancel=None, on_count=None, probe=False):
    """枚举整卷 MFT 文件记录。返回 [(frn, pfrn, name, is_dir)]；失败返回 None。
    probe=True 时仅测试可用性（成功即返回 []，不做完整枚举）。"""
    handle = _open_volume(letter)
    if handle in (-1, 0, None):
        return None
    try:
        records = []
        med = 0  # StartFileReferenceNumber
        buf = ctypes.create_string_buffer(0x2000 if probe else 0x100000)  # 8KB / 1MB
        br = ctypes.c_ulonglong(0)
        while not (should_cancel and should_cancel()):
            med_struct = _MFT_ENUM_DATA_V0(med)
            ok = _kernel32.DeviceIoControl(
                handle, FSCTL_ENUM_USN_DATA,
                ctypes.byref(med_struct), ctypes.sizeof(med_struct),
                buf, len(buf), ctypes.byref(br), None)
            if not ok:
                err = ctypes.get_last_error()
                if err == ERROR_HANDLE_EOF:
                    break
                return None  # 权限不足/策略限制/非 NTFS 等
            n = br.value
            if n < 8:
                break
            med = struct.unpack_from("<Q", buf, 0)[0]  # 输出前 8 字节 = 下一起点
            if probe:
                return []
            off = 8
            end = n
            while off + _USN_HDR.size <= end:
                (reclen, _maj, _min, frn, pfrn, _usn, _ts,
                 _reason, _src, _sec, attr, namelen, nameoff) = _USN_HDR.unpack_from(buf, off)
                if reclen <= 0:
                    break
                off += reclen
                if not namelen:
                    continue
                name = buf[off - namelen * 2: off].decode("utf-16-le", "ignore")
                if name.startswith("$"):
                    continue  # NTFS 元文件
                records.append((frn & 0x0000FFFFFFFFFFFF, pfrn & 0x0000FFFFFFFFFFFF,
                                name, bool(attr & FILE_ATTRIBUTE_DIRECTORY)))
            if on_count and len(records) % 100000 < 500:
                on_count(len(records))
        return records
    finally:
        _close(handle)


def ntfs_fixed_drives():
    """返回本地 NTFS 固定盘符列表，如 ['C:', 'D:']。"""
    import string
    drives = []
    for letter in string.ascii_uppercase:
        root = letter + ":\\"
        if not os_path_exists(root):
            continue
        type_name = ctypes.create_unicode_buffer(64)
        fs_name = ctypes.create_unicode_buffer(64)
        ok = _kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(root), type_name, 64, None, None, None, fs_name, 64)
        if ok and "NTFS" in fs_name.value.upper():
            drives.append(letter + ":")
    return drives


def os_path_exists(path):
    import os
    return os.path.exists(path)


class FastSearchIndex:
    """跨卷文件名索引。build 一次，query 若干次。"""

    def __init__(self):
        self.mode = ""             # "mft"（MFT 直读）或 "walk"（多线程目录扫描回退）
        self._orig = ""            # 原始大小写大字符串
        self._lower = ""           # 小写副本（查询用）
        self._offs = array("Q")    # 每个名字的起始偏移（升序），末尾补总长
        self._frns = array("Q")
        self._pfrns = array("Q")
        self._isdir = array("B")
        self._segs = []            # [(start_idx, end_idx, vol_letter)]（mft 模式）
        self._frn2idx = []         # 每段 {frn: idx} 用于路径重建
        self._dirs = []            # walk 模式：dir_id -> 目录完整路径
        self._dir_ids = array("I") # walk 模式：每条结果的目录 id
        self._path_cache = {}
        self.count = 0
        self.drives = []
        self.build_seconds = 0.0

    # ---------- 构建 ----------
    def build(self, drives, progress=None, should_cancel=None):
        """优先尝试 NTFS MFT 直读（秒级）；不可用则回退多线程目录扫描（兼容模式）。"""
        self.clear()
        t0 = time.time()
        for letter in drives:
            if should_cancel and should_cancel():
                return False
            probe = enum_volume_usn(letter, should_cancel, None, probe=True)
            if probe is not None:
                self.mode = "mft"
                return self._build_mft(drives, progress, should_cancel)
        if should_cancel and should_cancel():
            return False
        self.mode = "walk"
        return self._build_walk(drives, progress, should_cancel)

    def _build_walk(self, drives, progress=None, should_cancel=None, workers=6):
        """兼容模式：多线程 os.scandir 全盘扫描（枚举系统调用释放 GIL，可并行）。

        流式写入省内存：目录路径只存一次（文件记录目录 id）；
        MAX_ENTRIES 封顶，防止异常巨型数据集耗尽内存。"""
        import io
        import os as _os
        from threading import Thread, Lock
        t0 = time.time()
        self.clear()
        self.mode = "walk"
        MAX_ENTRIES = 2000000

        low_buf = io.StringIO()
        orig_buf = io.StringIO()
        offs = self._offs
        isdir_arr = self._isdir
        dirs = []                        # dir_id -> 完整目录路径（含盘符）
        dir_ids = array("I")             # 每条结果所属目录 id
        lock = Lock()
        queue = [d + "\\" for d in drives]   # 根目录必须带尾反斜杠，否则 e.path 是相对式路径
        dirid_of = {d: i for i, d in enumerate(queue)}
        qlock = Lock()
        qpos = [0]
        counters = {"n": 0}
        state = {"pos": 0, "truncated": False}

        def worker():
            _dbg_done = 0
            while True:
                if should_cancel and should_cancel():
                    return
                with qlock:
                    if state["truncated"] or qpos[0] >= len(queue):
                        print(f"    [dbg w] exit: truncated={state['truncated']} qpos={qpos[0]} qlen={len(queue)} n={counters['n']} done={_dbg_done}")
                        return
                    d = queue[qpos[0]]
                    qpos[0] += 1
                try:
                    entries = list(_os.scandir(d))
                except OSError as _e:
                    print(f"    [dbg w] scandir {d!r} FAILED: {_e!r}")
                    continue
                _dbg_done += 1
                if _dbg_done <= 12:
                    print(f"    [dbg w] scan {d!r}: {len(entries)} entries")
                did = dirid_of.get(d)
                for e in entries:
                    try:
                        isdir = e.is_dir(follow_symlinks=False)
                        if isdir:
                            # junction/symlink（reparse point）不递归：
                            # "Documents and Settings\Application Data\..." 等历史
                            # 兼容 junction 会无限循环引用自身，直到内存耗尽
                            if e.stat(follow_symlinks=False).st_file_attributes & 0x400:
                                isdir = False
                        full = e.path
                        low = full.lower()
                        if len(low) != len(full):
                            full = low  # 罕见 Unicode 大小写变换，保证双副本等长对齐
                    except OSError:
                        continue
                    with lock:
                        if counters["n"] >= MAX_ENTRIES:
                            state["truncated"] = True
                            return
                        dir_ids.append(did)
                        offs.append(state["pos"])
                        state["pos"] += len(full)
                        low_buf.write(full.lower())
                        orig_buf.write(full)
                        isdir_arr.append(1 if isdir else 0)
                        counters["n"] += 1
                        c = counters["n"]
                    if isdir:
                        with qlock:
                            queue.append(full)
                            dirid_of[full] = len(dirs)
                            dirs.append(full)
                    if progress and c % 200000 == 0:
                        progress(f"已扫描 {c} 条路径...")

        ths = [Thread(target=worker, daemon=True) for _ in range(workers)]
        for t in ths:
            t.start()
        for t in ths:
            t.join()
        if should_cancel and should_cancel():
            return False

        self._dirs = dirs
        self._dir_ids = dir_ids
        self._orig = orig_buf.getvalue()
        self._lower = low_buf.getvalue()
        offs.append(len(self._lower))
        self.count = counters["n"]
        self.drives = list(drives)
        self.build_seconds = time.time() - t0
        if progress:
            tail = "（已达上限，结果截断）" if state["truncated"] else ""
            progress(f"索引完成（兼容模式）：{self.count} 条{tail}，耗时 {self.build_seconds:.1f}s")
        return True

    def _build_mft(self, drives, progress=None, should_cancel=None):
        t0 = time.time()
        vol_list = []
        all_records = []
        for letter in drives:
            if should_cancel and should_cancel():
                return False
            recs = enum_volume_usn(letter, should_cancel,
                                   (lambda n: progress(f"已索引 {n} 条记录...")) if progress else None)
            if recs is None:
                if progress:
                    progress(f"{letter} 卷枚举失败，已跳过")
                continue
            vol_list.append(letter)
            all_records.append(recs)

        # 打包：名字直接 concat（无分隔符，靠偏移数组切分），空间最省
        orig_parts = []
        lower_parts = []
        pos = 0
        for letter, recs in zip(vol_list, all_records):
            seg_start = len(self._frns)
            for frn, pfrn, name, isdir in recs:
                self._frns.append(frn)
                self._pfrns.append(pfrn)
                self._isdir.append(1 if isdir else 0)
                low = name.lower()
                if len(low) != len(name):
                    # 罕见 Unicode 大小写变换（如 İ），统一用小写副本保证偏移一致
                    name = low
                orig_parts.append(name)
                lower_parts.append(low)
                self._offs.append(pos)
                pos += len(low)
            seg_end = len(self._frns)
            self._segs.append((seg_start, seg_end, letter))
            fmap = {}
            for j in range(seg_start, seg_end):
                fmap[self._frns[j]] = j
            self._frn2idx.append(fmap)
        self._orig = "".join(orig_parts)
        self._lower = "".join(lower_parts)
        self._offs.append(len(self._lower))  # 哨兵：最后一个名字的结束位置
        self.count = len(self._frns)
        self.drives = list(vol_list)
        self.build_seconds = time.time() - t0
        self._path_cache.clear()
        if progress:
            progress(f"索引完成：{self.count} 条记录，耗时 {self.build_seconds:.1f}s")
        return True

    def clear(self):
        self.mode = ""
        self._orig = ""
        self._lower = ""
        self._offs = array("Q")
        self._frns = array("Q")
        self._pfrns = array("Q")
        self._isdir = array("B")
        self._segs = []
        self._frn2idx = []
        self._dirs = []
        self._dir_ids = array("I")
        self._path_cache = {}
        self.count = 0
        self.drives = []
        self.build_seconds = 0.0

    # ---------- 查询 ----------
    def query(self, keyword, limit=1000):
        """子串查询（大小写不敏感）。返回 [{name, path, is_dir}]，最多 limit 条。"""
        kw = (keyword or "").strip().lower()
        if not kw or not self._lower:
            return []
        hay = self._lower
        res = []
        find = hay.find
        pos = find(kw)
        while pos != -1 and len(res) < limit:
            idx = bisect_right(self._offs, pos) - 1
            res.append(idx)
            pos = find(kw, pos + 1)
        out = []
        if self.mode == "walk":
            # 兼容模式：打包字符串里存的就是完整路径，切片即得
            for idx in res:
                p = self._orig[self._offs[idx]: self._offs[idx + 1]]
                out.append({"name": p.rsplit("\\", 1)[-1], "path": p,
                            "is_dir": bool(self._isdir[idx])})
            return out
        for idx in res:
            name = self._orig[self._offs[idx]: self._offs[idx + 1]]
            out.append({"name": name, "path": self._path_of(idx), "is_dir": bool(self._isdir[idx])})
        return out

    # ---------- 路径重建 ----------
    def _seg_of(self, idx):
        for si, (start, end, letter) in enumerate(self._segs):
            if start <= idx < end:
                return si
        return None

    def _path_of(self, idx):
        cached = self._path_cache.get(idx)
        if cached:
            return cached
        si = self._seg_of(idx)
        if si is None:
            return "?"
        letter = self._segs[si][2]
        fmap = self._frn2idx[si]
        parts = []
        cur = idx
        seen = 0
        while True:
            parts.append(self._orig[self._offs[cur]: self._offs[cur + 1]])
            pfrn = self._pfrns[cur]
            if pfrn == 5 or pfrn == 0:
                break
            nxt = fmap.get(pfrn)
            if nxt is None:
                parts.append("...")  # 父链断裂（索引过期）
                break
            cur = nxt
            seen += 1
            if seen > 120:
                break
        path = letter + "\\" + "\\".join(reversed(parts))
        if len(self._path_cache) > 60000:
            self._path_cache.clear()
        self._path_cache[idx] = path
        return path


class IndexBuildWorker(QThread):
    progress = Signal(str)
    done = Signal(bool, str)

    def __init__(self, index, drives):
        super().__init__()
        self.index = index
        self.drives = drives
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def should_cancel(self):
        return self._cancel

    def run(self):
        try:
            ok = self.index.build(self.drives, self.progress.emit, self.should_cancel)
            self.done.emit(ok, "")
        except Exception as e:
            self.done.emit(False, str(e))


class SearchWorker(QThread):
    done = Signal(int, str, float, int)  # gen, keyword, elapsed_ms, results(list 存 self)

    def __init__(self, gen, index, keyword, limit=1000):
        super().__init__()
        self.gen = gen
        self.index = index
        self.keyword = keyword
        self.limit = limit
        self.results = []

    def run(self):
        t0 = time.time()
        try:
            self.results = self.index.query(self.keyword, self.limit)
        except Exception:
            self.results = []
        ms = (time.time() - t0) * 1000
        self.done.emit(self.gen, self.keyword, ms, len(self.results))
