# -*- coding: utf-8 -*-
"""C 盘专清分析引擎。

知识库列出 C 盘每个顶层/常见目标 → 后台线程统计大小 → 规则库给出
AI 建议（建议清理/可考虑/用户数据/系统勿动）+ 理由 + 预计可释放空间。
最终是否删除由用户勾选决定。
"""
import os, time
from PySide6.QtCore import QThread, Signal

# AI 建议等级
ADVICE_CLEAN = "clean"        # 建议清理（可再生缓存/临时文件），默认勾选
ADVICE_CONSIDER = "consider"  # 可考虑（有轻微代价或低风险数据），不默认勾选
ADVICE_USER = "user"          # 用户数据，AI 不代作决定
ADVICE_PROTECT = "protect"    # 系统核心，禁止删除

ADVICE_LABELS = {
    ADVICE_CLEAN: "✅ 建议清理",
    ADVICE_CONSIDER: "🟡 可以考虑",
    ADVICE_USER: "🔵 用户数据",
    ADVICE_PROTECT: "🔴 系统勿动",
}

# 执行动作类型
ACT_EMPTY = "empty"      # 清空文件夹内容（保留目录本身）
ACT_DELETE = "delete"    # 整项删除
ACT_RECYCLE = "recycle"  # 清空回收站（PowerShell）
ACT_FEATURE = "feature"  # 需系统功能处理（如 powercfg 关闭休眠）
ACT_SKIP = "skip"        # 仅展示，不可执行


def build_targets():
    """C 盘清理目标知识库：(路径, 类别, 用途说明, AI建议, 执行动作, AI理由)"""
    u = os.environ.get("USERPROFILE", r"C:\Users\Unknown")
    local = os.environ.get("LOCALAPPDATA", os.path.join(u, "AppData", "Local"))
    sysroot = os.environ.get("SystemRoot", r"C:\Windows")
    return [
        (os.environ.get("TEMP", os.path.join(local, "Temp")),
         "临时文件", "用户与应用的临时文件，可再生", ADVICE_CLEAN, ACT_EMPTY,
         "临时目录内容 100% 可再生，清空无风险（占用中的文件会自动跳过）"),
        (os.path.join(sysroot, "Temp"),
         "系统临时", "Windows 系统临时文件", ADVICE_CLEAN, ACT_EMPTY,
         "系统临时目录，安装包解压残留等，可安全清空"),
        (os.path.join(sysroot, "SoftwareDistribution", "Download"),
         "更新缓存", "Windows 更新已下载的安装包", ADVICE_CLEAN, ACT_EMPTY,
         "更新安装完成后即为死数据，删除后需要时会重新下载"),
        (os.path.join(local, "Microsoft", "Windows", "Explorer"),
         "缩略图缓存", "资源管理器缩略图/图标缓存", ADVICE_CLEAN, ACT_EMPTY,
         "缓存被删后系统自动重建，首次打开文件夹会稍慢"),
        (os.path.join(local, "Google", "Chrome", "User Data", "Default", "Cache"),
         "浏览器缓存", "Chrome 网页缓存", ADVICE_CLEAN, ACT_EMPTY,
         "网页缓存，删除后浏览历史/密码/书签不受影响"),
        (os.path.join(local, "Microsoft", "Edge", "User Data", "Default", "Cache"),
         "浏览器缓存", "Edge 网页缓存", ADVICE_CLEAN, ACT_EMPTY,
         "网页缓存，删除后浏览历史/密码/收藏不受影响"),
        (os.path.join(local, "CrashDumps"),
         "崩溃转储", "应用崩溃时的内存转储", ADVICE_CLEAN, ACT_EMPTY,
         "仅用于排查崩溃原因，普通用户无需保留"),
        (os.path.join(local, "NVIDIA", "DXCache"),
         "着色器缓存", "NVIDIA DirectX 着色器缓存", ADVICE_CLEAN, ACT_EMPTY,
         "游戏着色器缓存，删除后首次进游戏编译稍慢，空间可翻倍回收"),
        (os.path.join(local, "AMD", "DxCache"),
         "着色器缓存", "AMD DirectX 着色器缓存", ADVICE_CLEAN, ACT_EMPTY,
         "同 NVIDIA DXCache，可安全清空"),
        ("C:\\$Recycle.Bin",
         "回收站", "已删除文件的暂存区", ADVICE_CLEAN, ACT_RECYCLE,
         "清空回收站即彻底释放这些空间"),
        (os.path.join(sysroot, "Prefetch"),
         "预读取", "应用启动预读取数据", ADVICE_CONSIDER, ACT_EMPTY,
         "可清约数十 MB；清除后各程序首次启动会略慢，系统会自动重建"),
        (os.path.join(sysroot, "Logs"),
         "系统日志", "Windows 组件日志", ADVICE_CONSIDER, ACT_EMPTY,
         "占用通常不大；排查系统问题时有用，删除不影响运行"),
        (os.path.join(sysroot, "LiveKernelReports"),
         "内核转储", "系统级内核报告(常为GB级大文件)", ADVICE_CONSIDER, ACT_EMPTY,
         "如曾出现 LIVEKERNEL 事件则有用，否则可清"),
        ("C:\\Windows.old",
         "旧系统备份", "升级/重装前的旧 Windows", ADVICE_CONSIDER, ACT_DELETE,
         "回滚窗口(通常10天)过后系统会自动删；确认不需回滚可手动删，通常数 GB~数十 GB"),
        ("C:\\hiberfil.sys",
         "休眠文件", "休眠功能的内存镜像", ADVICE_CONSIDER, ACT_FEATURE,
         "不可直接删除；以管理员运行 powercfg /h off 关闭休眠即可释放(约等于内存大小的 40%~100%)"),
        (os.path.join(u, "Downloads"),
         "下载数据", "下载的安装包/文件", ADVICE_USER, ACT_SKIP,
         "AI 不代作决定：安装包通常可删，请按需自行筛选（可用「大文件」页辅助）"),
        (os.path.join(u, "Desktop"),
         "用户数据", "桌面文件", ADVICE_USER, ACT_SKIP,
         "AI 不代作决定：请自行整理"),
        (os.path.join(u, "Documents"),
         "用户数据", "个人文档", ADVICE_USER, ACT_SKIP,
         "AI 不代作决定：请自行整理"),
        (os.environ.get("ProgramFiles", r"C:\Program Files"),
         "已安装程序", "64 位应用程序", ADVICE_PROTECT, ACT_SKIP,
         "请勿手动删除；卸载请使用「软件管理」页"),
        (os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
         "已安装程序", "32 位应用程序", ADVICE_PROTECT, ACT_SKIP,
         "请勿手动删除；卸载请使用「软件管理」页"),
        (os.environ.get("ProgramData", r"C:\ProgramData"),
         "共享数据", "应用共享配置/数据", ADVICE_PROTECT, ACT_SKIP,
         "删除会导致已装软件损坏"),
        (sysroot,
         "系统核心", "Windows 操作系统本体", ADVICE_PROTECT, ACT_SKIP,
         "系统核心，禁止整体删除；内部可清项已单列（Temp/更新缓存等）"),
        (r"C:\Users",
         "用户数据", "所有用户的文件", ADVICE_PROTECT, ACT_SKIP,
         "包含你的文档/桌面/下载，禁止整体删除"),
        (r"C:\pagefile.sys",
         "虚拟内存", "页面文件(系统管理)", ADVICE_PROTECT, ACT_SKIP,
         "由系统管理大小，不可手动删除；可在「系统属性→性能→虚拟内存」调整"),
        (r"C:\swapfile.sys",
         "UWP 交换", "UWP 应用交换文件", ADVICE_PROTECT, ACT_SKIP,
         "系统管理，保持现状"),
    ]


class CScanTarget:
    __slots__ = ("path", "category", "desc", "advice", "reason", "action",
                 "size", "file_count", "scanned", "approximate")

    def __init__(self, path, category, desc, advice, action, reason):
        self.path = path
        self.category = category
        self.desc = desc
        self.advice = advice
        self.reason = reason
        self.action = action
        self.size = 0
        self.file_count = 0
        self.scanned = False
        self.approximate = False


class CScanWorker(QThread):
    """逐目标统计大小（后台线程）。

    「系统勿动」的大目录（Windows/Program Files 等）不参与全量遍历——
    用限时+限量预算快速估算并标记近似值，避免用户等待数分钟。
    """
    item_updated = Signal(object)   # CScanTarget
    progress = Signal(str)
    finished_all = Signal(list)

    QUICK_FILE_LIMIT = 15000
    QUICK_TIME_BUDGET = 8.0

    def __init__(self, targets):
        super().__init__()
        self.targets = targets
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        for t in self.targets:
            if self._cancel:
                break
            self.progress.emit("正在分析: " + t.path)
            self._measure(t)
            self.item_updated.emit(t)
        self.progress.emit("分析完成")
        self.finished_all.emit(self.targets)

    def _measure(self, t):
        quick = (t.advice == ADVICE_PROTECT)
        if os.path.isfile(t.path):
            try:
                t.size = os.path.getsize(t.path)
                t.file_count = 1
            except OSError:
                t.size = 0
            t.scanned = True
            return
        if not os.path.isdir(t.path):
            t.size = 0
            t.scanned = True
            return
        total = 0
        count = 0
        truncated = False
        t0 = time.time()
        stack = [(t.path, 0)]
        while stack:
            if self._cancel:
                break
            root, depth = stack.pop()
            try:
                entries = list(os.scandir(root))
            except OSError:
                continue
            for e in entries:
                try:
                    if e.is_dir(follow_symlinks=False):
                        stack.append((e.path, depth + 1))
                    else:
                        total += e.stat().st_size
                        count += 1
                except OSError:
                    continue
            if quick and (count >= self.QUICK_FILE_LIMIT
                          or time.time() - t0 > self.QUICK_TIME_BUDGET):
                truncated = True
                break
        t.size = total
        t.file_count = count
        t.scanned = True
        t.approximate = truncated


class CCleanWorker(QThread):
    """执行清理：empty=清空内容(永久删除，不进回收站)，delete=整项删除，recycle=清空回收站。"""
    item_done = Signal(object, bool, int, int)  # target, ok, freed_bytes, skipped
    progress = Signal(str)
    finished_all = Signal(int, int)             # total_freed, total_skipped

    def __init__(self, jobs):
        super().__init__()
        self.jobs = jobs  # [(CScanTarget, action)]

    def run(self):
        total_freed = 0
        total_skipped = 0
        for target, action in self.jobs:
            if action == ACT_RECYCLE:
                self.progress.emit("正在清空回收站...")
                ok, freed, skipped = self._empty_recycle_bin()
            elif action == ACT_EMPTY:
                self.progress.emit("正在清理: " + target.path)
                ok, freed, skipped = self._empty_dir(target.path)
            elif action == ACT_DELETE:
                self.progress.emit("正在删除: " + target.path)
                ok, freed, skipped = self._delete_tree(target.path)
            else:
                ok, freed, skipped = False, 0, 0
            total_freed += freed
            total_skipped += skipped
            self.item_done.emit(target, ok, freed, skipped)
        self.finished_all.emit(total_freed, total_skipped)

    @staticmethod
    def _empty_dir(path):
        freed = 0
        skipped = 0
        if not os.path.isdir(path):
            return True, 0, 0
        for root, dirs, files in os.walk(path, topdown=False, onerror=lambda e: None):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    sz = os.path.getsize(fp)
                    os.remove(fp)
                    freed += sz
                except OSError:
                    skipped += 1
            for dn in dirs:
                try:
                    os.rmdir(os.path.join(root, dn))
                except OSError:
                    skipped += 1
        return True, freed, skipped

    @staticmethod
    def _delete_tree(path):
        import shutil
        if os.path.isfile(path):
            try:
                sz = os.path.getsize(path)
                os.remove(path)
                return True, sz, 0
            except OSError:
                return False, 0, 1
        if not os.path.isdir(path):
            return False, 0, 0
        freed = 0
        for root, dirs, files in os.walk(path, onerror=lambda e: None):
            for f in files:
                try:
                    freed += os.path.getsize(os.path.join(root, f))
                except OSError:
                    continue
        shutil.rmtree(path, ignore_errors=True)
        gone = not os.path.exists(path)
        return gone, freed if gone else 0, 0 if gone else 1

    @staticmethod
    def _empty_recycle_bin():
        import subprocess
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"],
                capture_output=True, timeout=60,
                creationflags=subprocess.CREATE_NO_WINDOW)
            return r.returncode == 0, 0, 0
        except Exception:
            return False, 0, 0
