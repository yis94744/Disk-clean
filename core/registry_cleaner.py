"""Registry scanner and cleaner"""
import os, winreg
from dataclasses import dataclass
from PySide6.QtCore import QThread, Signal

@dataclass
class RegistryIssue:
    key_path: str = ""
    value_name: str = ""
    value_data: str = ""
    issue_type: str = ""
    description: str = ""
    safety_level: int = 1
    checked: bool = False

class RegistryScanner(QThread):
    progress = Signal(str)
    found_issue = Signal(object)
    finished = Signal(list)

    def run(self):
        issues = []
        self.progress.emit("正在扫描无效路径...")
        issues.extend(self._invalid_paths())
        self.progress.emit("正在扫描启动项...")
        issues.extend(self._startup_entries())
        self.progress.emit("正在扫描卸载残留...")
        issues.extend(self._uninstall_residue())
        self.progress.emit("扫描完成")
        self.finished.emit(issues)

    def _invalid_paths(self):
        issues = []
        paths = [
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts"),
            (winreg.HKEY_CLASSES_ROOT, r"Applications"),
        ]
        for hkey, sub in paths:
            try:
                key = winreg.OpenKey(hkey, sub)
                for i in range(min(winreg.QueryInfoKey(key)[0], 500)):
                    try:
                        sk = winreg.EnumKey(key, i)
                        full_sub = sub + "\\" + sk
                        self._check_vals(hkey, full_sub, issues)
                    except OSError:
                        continue
                winreg.CloseKey(key)
            except OSError:
                continue
        return issues

    def _check_vals(self, hkey, sub, issues):
        try:
            key = winreg.OpenKey(hkey, sub)
            for i in range(winreg.QueryInfoKey(key)[1]):
                try:
                    n, d, _ = winreg.EnumValue(key, i)
                    if isinstance(d, str) and len(d) > 3:
                        if ":" in d or "\\" in d or d.endswith(".exe") or d.endswith(".dll"):
                            p = d.strip().strip('"').split(" ")[0] if " " in d else d.strip().strip('"')
                            if not os.path.exists(p):
                                issues.append(RegistryIssue(
                                    key_path=sub, value_name=n, value_data=str(d)[:200],
                                    issue_type="invalid_path",
                                    description="Invalid path: " + os.path.basename(p) if "\\" in p else p[:50],
                                    safety_level=1))
                except OSError:
                    continue
            winreg.CloseKey(key)
        except OSError:
            pass

    def _startup_entries(self):
        issues = []
        paths = [
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
        ]
        for hkey, sub in paths:
            try:
                key = winreg.OpenKey(hkey, sub)
                for i in range(winreg.QueryInfoKey(key)[1]):
                    try:
                        n, d, _ = winreg.EnumValue(key, i)
                        if isinstance(d, str):
                            p = d.strip().strip('"').split(" ")[0] if " " in d else d.strip().strip('"')
                            if not os.path.exists(p):
                                issues.append(RegistryIssue(
                                    key_path=sub, value_name=n, value_data=str(d)[:200],
                                    issue_type="broken_startup",
                                    description="Broken startup: " + (os.path.basename(p) if "\\" in p else p),
                                    safety_level=2))
                    except OSError:
                        continue
                winreg.CloseKey(key)
            except OSError:
                continue
        return issues

    def _uninstall_residue(self):
        issues = []
        scan_targets = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]
        for hkey_root, sub in scan_targets:
            try:
                key = winreg.OpenKey(hkey_root, sub)
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        sk = winreg.EnumKey(key, i)
                        full_sub = sub + "\\" + sk
                        skk = winreg.OpenKey(hkey_root, full_sub)
                        try:
                            loc, _ = winreg.QueryValueEx(skk, "InstallLocation")
                            if loc and isinstance(loc, str) and not os.path.exists(loc):
                                nm = ""
                                try:
                                    nm, _ = winreg.QueryValueEx(skk, "DisplayName")
                                except:
                                    pass
                                issues.append(RegistryIssue(
                                    key_path=full_sub, value_name="InstallLocation",
                                    value_data=loc, issue_type="uninstall_residue",
                                    description="Residue: " + (nm or sk), safety_level=1))
                        except OSError:
                            pass
                        winreg.CloseKey(skk)
                    except OSError:
                        continue
                winreg.CloseKey(key)
            except OSError:
                continue
        return issues

    @staticmethod
    def clean_issue(issue):
        try:
            if issue.key_path.startswith("HKEY_LOCAL_MACHINE"):
                hk = winreg.HKEY_LOCAL_MACHINE
                sub = issue.key_path.replace("HKEY_LOCAL_MACHINE\\", "", 1)
            elif issue.key_path.startswith("HKEY_CLASSES_ROOT"):
                hk = winreg.HKEY_CLASSES_ROOT
                sub = issue.key_path.replace("HKEY_CLASSES_ROOT\\", "", 1)
            else:
                hk = winreg.HKEY_CURRENT_USER
                sub = issue.key_path
            try:
                key = winreg.OpenKey(hk, sub, 0, winreg.KEY_READ | winreg.KEY_WRITE | winreg.KEY_WOW64_64KEY)
                try:
                    winreg.DeleteValue(key, issue.value_name)
                except OSError as e:
                    if e.winerror != 2:
                        raise
                winreg.CloseKey(key)
                return (True, "")
            except PermissionError:
                return (False, "permission denied")
            except OSError as e:
                if e.winerror == 2:
                    return (True, "already gone")
                return (False, "error " + str(e.winerror))
        except PermissionError:
            return (False, "permission denied")
        except Exception as e:
            return (False, str(e))
