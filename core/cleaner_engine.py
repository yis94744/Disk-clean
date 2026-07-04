"""Cleaner engine - scans and cleans system junk, browser cache, temp files"""
import os, shutil, subprocess
from PySide6.QtCore import QObject, Signal
from utils.constants import SAFE, SUGGESTED, CAUTION, PROTECTED

class CleanItem:
    __slots__ = ("name", "category", "description", "safety_level", "size", "file_count", "paths", "enabled")
    def __init__(self, name, category, description, safety_level, paths=None):
        self.name = name; self.category = category; self.description = description
        self.safety_level = safety_level; self.size = 0; self.file_count = 0
        self.paths = paths or []
        self.enabled = (safety_level == SAFE)

class CleanerEngine(QObject):
    progress = Signal(str)
    item_updated = Signal(object)
    finished = Signal(list)

    def get_clean_items(self):
        items = []
        root = os.environ.get("SystemRoot", "C:\Windows")
        local = os.environ.get("LOCALAPPDATA", "\\")
        appdata = os.environ.get("APPDATA", "\\")

        items.append(CleanItem("Windows 临时文件", "系统", "%%TEMP%% and Windows\\Temp", SAFE,
            [os.environ.get("TEMP","\\"), os.path.join(root, "Temp")]))
        items.append(CleanItem("Windows 更新缓存", "系统", "Windows Update downloads", SUGGESTED,
            [os.path.join(root, "SoftwareDistribution", "Download")]))
        items.append(CleanItem("缩略图缓存", "系统", "Explorer thumbnail cache", SAFE,
            [os.path.join(local, "Microsoft", "Windows", "Explorer")]))
        items.append(CleanItem("系统错误转储", "系统", ".dmp / .mdmp files", SUGGESTED,
            [os.path.join(root, "Minidump"), os.path.join(root, "MEMORY.DMP")]))
        items.append(CleanItem("预读取缓存", "系统", "Prefetch files", SUGGESTED,
            [os.path.join(root, "预读取缓存")]))
        items.append(CleanItem("系统日志文件", "系统", "Event logs and log files", CAUTION,
            [os.path.join(root, "Logs"), os.path.join(root, "System32", "LogFiles")]))
        items.append(CleanItem("字体缓存", "系统", "Font cache, auto-rebuilt", SAFE,
            [os.path.join(local, "Microsoft", "Windows", "Fonts")]))
        items.append(CleanItem("Chrome 缓存", "浏览器", "Chrome browser cache", SAFE,
            [os.path.join(local, "Google", "Chrome", "User Data", "Default", "Cache")]))
        items.append(CleanItem("Edge 缓存", "浏览器", "Edge browser cache", SAFE,
            [os.path.join(local, "Microsoft", "Edge", "User Data", "Default", "Cache")]))
        items.append(CleanItem("Firefox 缓存", "浏览器", "Firefox browser cache", SAFE,
            [os.path.join(appdata, "Mozilla", "Firefox", "Profiles")]))
        items.append(CleanItem("回收站", "用户", "All drives recycle bin", SAFE))
        items.append(CleanItem("最近文档", "用户", "Recent documents list", SAFE,
            [os.path.join(appdata, "Microsoft", "Windows", "Recent")]))
        items.append(CleanItem("剪贴板历史", "用户", "Clipboard history", SAFE,
            [os.path.join(local, "Microsoft", "Windows", "剪贴板历史")]))
        items.append(CleanItem("休眠文件", "高级", "hiberfil.sys (needs powercfg)", PROTECTED,
            [os.path.join(os.environ.get("SystemDrive","C:"), "hiberfil.sys")]))
        items.append(CleanItem("DNS 缓存", "高级", "DNS resolver cache", SAFE))
        items.append(CleanItem("DirectX 缓存", "高级", "DirectX shader cache", SAFE,
            [os.path.join(local, "NVIDIA", "DXCache"), os.path.join(local, "AMD", "DxCache")]))
        return items

    def analyze(self, items):
        for item in items:
            self.progress.emit(f"Analyzing: {item.name}")
            total_size = 0; total_files = 0
            for path in item.paths:
                if not path or not os.path.exists(path): continue
                if os.path.isfile(path):
                    try: total_size += os.path.getsize(path); total_files += 1
                    except OSError: pass
                elif os.path.isdir(path):
                    for dp, _, fns in os.walk(path):
                        for f in fns:
                            try: total_size += os.path.getsize(os.path.join(dp,f)); total_files += 1
                            except OSError: pass
            item.size = total_size; item.file_count = total_files
            self.item_updated.emit(item)
        self.finished.emit(items)

    def clean(self, items):
        results = []
        for item in items:
            if item.name == "回收站":
                self._empty_recycle()
                results.append({"name": item.name, "freed_size": 0, "errors": [], "success": True})
                continue
            if item.name == "DNS 缓存":
                self._flush_dns()
                results.append({"name": item.name, "freed_size": 0, "errors": [], "success": True})
                continue
            self.progress.emit(f"Cleaning: {item.name}")
            freed = 0; errors = []
            for path in item.paths:
                if not path or not os.path.exists(path): continue
                try:
                    if os.path.isfile(path):
                        sz = os.path.getsize(path); os.remove(path); freed += sz
                    elif os.path.isdir(path):
                        for rp, ds, fns in os.walk(path, topdown=False):
                            for fn in fns:
                                fp = os.path.join(rp, fn)
                                try: sz = os.path.getsize(fp); os.remove(fp); freed += sz
                                except OSError as e: errors.append(str(e))
                            for d in ds:
                                try: os.rmdir(os.path.join(rp, d))
                                except OSError: pass
                except OSError as e: errors.append(str(e))
            results.append({"name": item.name, "freed_size": freed, "errors": errors, "success": not errors})
        return results

    def _empty_recycle(self):
        try: subprocess.run(["powershell","-Command","Clear-RecycleBin -Force -ErrorAction SilentlyContinue"], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=30)
        except: pass

    def _flush_dns(self):
        try: subprocess.run(["ipconfig","/flushdns"], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
        except: pass
