"""Registry scanner and cleaner"""
import os, re, winreg
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
    hive: str = "HKCU"

    @staticmethod
    def _extract_paths(d):
        """Extract candidate executable paths from a registry command string.

        Handles quoted paths with arguments, unquoted paths with spaces, and
        argument separators like ' /x', ' -x', ' %1'.
        """
        d = (d or "").strip()
        out = []
        if d.startswith('"'):
            end = d.find('"', 1)
            if end > 1:
                out.append(d[1:end])
        else:
            cand = d
            for marker in (" /", " -", " %"):
                i = cand.find(marker)
                if i > 0:
                    cand = cand[:i]
                    break
            cand = cand.strip().strip('"')
            if cand:
                out.append(cand)
            first = d.split(" ")[0].strip('"')
            if first and first not in out:
                out.append(first)
        return [p for p in out if p]

    @staticmethod
    def _is_broken_command(d):
        """True only when the value looks like an absolute path command and no
        candidate path exists on disk. Relative/system names can't be judged."""
        d = (d or "").strip()
        if d.startswith("@"):
            # MUI 间接字符串（@dll,-index 指向资源文本），不是文件路径
            return False, ""
        cands = RegistryIssue._extract_paths(d)
        if not cands:
            return False, ""
        for c in cands:
            # 结尾 ",-N" 是 DLL 资源索引（imageres.dll,-4），剥离资源库本体后再判定
            base = re.sub(r",\s*-?\d+$", "", c).strip()
            if not base:
                continue
            # %SystemRoot% 等环境变量先展开再判定，否则真实路径会被误判失效
            if os.path.exists(os.path.expandvars(base)):
                return False, base
        p = cands[0]
        # 只有盘符/UNC 绝对路径才可判定失效；相对命令（rundll32.exe、QT:MOV 等）无法校验
        probe = os.path.expandvars(p)
        if not (re.match(r"^[A-Za-z]:[\\/]", probe) or probe.startswith("\\\\")):
            return False, p
        return True, p

class RegistryScanner(QThread):
    progress = Signal(str)
    found_issue = Signal(object)
    finished = Signal(list)

    def run(self):
        issues = []
        try:
            self.progress.emit("正在扫描无效路径...")
            issues.extend(self._invalid_paths())
            self.progress.emit("正在扫描启动项...")
            issues.extend(self._startup_entries())
            self.progress.emit("正在扫描卸载残留...")
            issues.extend(self._uninstall_residue())
            self.progress.emit("扫描完成")
        except Exception as e:
            # 兜底：任何阶段异常都不能让线程静默死亡（否则 UI 永远停在"正在扫描"）
            try:
                self.progress.emit("注册表扫描出错: " + str(e)[:120])
            except Exception:
                pass
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
                        broken, p = RegistryIssue._is_broken_command(d)
                        if broken:
                            hive_name = "HKLM" if hkey == winreg.HKEY_LOCAL_MACHINE else \
                                        "HKCR" if hkey == winreg.HKEY_CLASSES_ROOT else "HKCU"
                            issues.append(RegistryIssue(
                                key_path=sub, value_name=n, value_data=str(d)[:200],
                                issue_type="invalid_path",
                                description="Invalid path: " + os.path.basename(p) if "\\" in p else p[:50],
                                safety_level=1, hive=hive_name))
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
                        if isinstance(d, str) and d.strip():
                            broken, p = RegistryIssue._is_broken_command(d)
                            if broken:
                                hive_name = "HKLM" if hkey == winreg.HKEY_LOCAL_MACHINE else "HKCU"
                                issues.append(RegistryIssue(
                                    key_path=sub, value_name=n, value_data=str(d)[:200],
                                    issue_type="broken_startup",
                                    description="Broken startup: " + (os.path.basename(p) if "\\" in p else p),
                                    safety_level=2, hive=hive_name))
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
                hive_name = "HKLM" if hkey_root == winreg.HKEY_LOCAL_MACHINE else "HKCU"
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
                                    description="Residue: " + (nm or sk), safety_level=1,
                                    hive=hive_name))
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
            hive_map = {
                "HKLM": winreg.HKEY_LOCAL_MACHINE,
                "HKCR": winreg.HKEY_CLASSES_ROOT,
                "HKCU": winreg.HKEY_CURRENT_USER,
            }
            hk = hive_map.get(getattr(issue, "hive", "") or "", winreg.HKEY_CURRENT_USER)
            sub = issue.key_path
            if sub.startswith(("HKEY_LOCAL_MACHINE\\", "HKEY_CLASSES_ROOT\\", "HKEY_CURRENT_USER\\")):
                sub = sub.split("\\", 1)[1]
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
