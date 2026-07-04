# -*- coding: utf-8 -*-
"""Software uninstaller - registry scanner + executor + force uninstall"""
import os, subprocess, winreg, shutil, time
from PySide6.QtCore import QObject, Signal

SP_KWARGS = {"capture_output": True, "text": True, "encoding": "utf-8", "errors": "replace",
             "timeout": 180, "creationflags": subprocess.CREATE_NO_WINDOW}

class AppInfo:
    __slots__ = ("name","version","publisher","install_location",
                 "uninstall_string","display_icon","estimated_size",
                 "install_date","is_system","registry_key","hive","is_orphan","orphan_reason","orphan_level")
    def __init__(self):
        self.name = ""; self.version = ""; self.publisher = ""
        self.install_location = ""; self.uninstall_string = ""
        self.display_icon = ""; self.estimated_size = 0
        self.install_date = ""; self.is_system = False
        self.registry_key = ""; self.hive = ""
        self.is_orphan = False; self.orphan_reason = ""
        self.orphan_level = 0  # 0=safe, 1=possible, 2=confirmed

class UninstallWorker(QObject):
    finished = Signal(list)
    SYSTEM_DIRS = [
        os.environ.get("SystemRoot","C:\\Windows"),
        os.path.join(os.environ.get("SystemRoot","C:\\Windows"),"System32"),
    ]

    def _get_val(self, key, name):
        try:
            v = winreg.QueryValueEx(key, name)[0]
            return str(v) if v is not None else ""
        except: return ""

    def scan(self):
        apps = self.scan_all(); self.finished.emit(apps)

    def scan_all(self):
        apps = []; seen = set()
        regs = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall"),
        ]
        for hive, subkey in regs:
            try:
                key = winreg.OpenKey(hive, subkey)
                i = 0
                while True:
                    try:
                        skn = winreg.EnumKey(key, i)
                        full = subkey + "\\" + skn
                        sk = winreg.OpenKey(hive, full)
                        try:
                            name = self._get_val(sk, "DisplayName")
                            if name and name.strip() and name not in seen:
                                seen.add(name)
                                app = AppInfo()
                                app.name = name
                                app.version = self._get_val(sk, "DisplayVersion")
                                app.publisher = self._get_val(sk, "Publisher")
                                app.install_location = self._get_val(sk, "InstallLocation")
                                app.uninstall_string = self._get_val(sk, "UninstallString") or self._get_val(sk, "QuietUninstallString")
                                app.display_icon = self._get_val(sk, "DisplayIcon")
                                app.install_date = self._get_val(sk, "InstallDate")
                                try:
                                    sz = winreg.QueryValueEx(sk, "EstimatedSize")[0]
                                    app.estimated_size = sz * 1024
                                except: app.estimated_size = 0
                                app.registry_key = full
                                app.hive = "HKLM" if hive == winreg.HKEY_LOCAL_MACHINE else "HKCU"
                                # Smart system detection
                                is_ms = app.publisher in {"Microsoft Corporation", "Microsoft", "Windows"}
                                in_sys_dir = False
                                if app.install_location:
                                    ll = app.install_location.lower()
                                    for sd in self.SYSTEM_DIRS:
                                        if ll.startswith(sd.lower()):
                                            in_sys_dir = True; break
                                # System: in Windows dir OR is MS runtime/update/driver
                                if in_sys_dir:
                                    app.is_system = True
                                elif is_ms:
                                    nl = app.name.lower()
                                    sys_keywords = ["update", "runtime", "driver", "redistributable",
                                                    "sdk", ".net", "visual c++", "edge webview",
                                                    "windows", "service pack", "security",
                                                    "application verifier", "clickonce",
                                                    "windows sdk", "windows driver",
                                                    "c++", "desktop runtime", "asp.net",
                                                    ".net framework", "net framework",
                                                    "microsoft edge", "edge update",
                                                    "onedrive", "defender", "silverlight"]
                                    if any(kw in nl for kw in sys_keywords):
                                        app.is_system = True
                                # === SMART ORPHAN DETECTION ===
                                # Level 0: safe
                                # Level 1: suspected orphan (missing uninstaller but system/normal component)
                                # Level 2: confirmed orphan (install dir gone, user software)
                                app.is_orphan = False
                                app.orphan_level = 0

                                # NEVER mark system software as orphan
                                if app.is_system:
                                    apps.append(app)
                                    continue

                                # Check install directory
                                loc_exists = False
                                loc = ""
                                if app.install_location:
                                    loc = app.install_location.strip('"')
                                    loc_exists = os.path.exists(loc)

                                # Check uninstaller
                                uninstaller_exists = False
                                has_uninstall_string = False
                                if app.uninstall_string:
                                    has_uninstall_string = True
                                    us = app.uninstall_string.strip('"')
                                    exe_path = us.split('" ')[0] if '"' in us else us.split(' ')[0]
                                    uninstaller_exists = os.path.exists(exe_path.strip('"'))

                                # Level 2 (confirmed orphan): install dir AND uninstaller both gone, and it had both
                                if app.install_location and not loc_exists and has_uninstall_string and not uninstaller_exists:
                                    app.is_orphan = True
                                    app.orphan_level = 2
                                    app.orphan_reason = "安装目录和卸载程序均不存在"
                                # Level 1 (suspected): install dir gone, no uninstaller info
                                elif app.install_location and not loc_exists and not has_uninstall_string:
                                    app.is_orphan = True
                                    app.orphan_level = 1
                                    app.orphan_reason = "安装目录不存在(可能为组件)"
                                # Level 1: uninstaller gone but install dir exists (uninstaller was moved)
                                elif loc_exists and has_uninstall_string and not uninstaller_exists:
                                    app.is_orphan = True
                                    app.orphan_level = 1
                                    app.orphan_reason = "卸载程序缺失(目录仍存在)"
                                # Level 0: everything OK or only partial info
                                else:
                                    app.is_orphan = False
                                    app.orphan_level = 0
                                apps.append(app)
                        finally: winreg.CloseKey(sk)
                    except OSError: break
                    i += 1
                winreg.CloseKey(key)
            except OSError: pass
        apps.sort(key=lambda a: a.name.lower())
        return apps


class UninstallExecutor(QObject):
    """Normal + Force uninstall executor with Geek Uninstaller-style deep scan."""
    output = Signal(str)
    finished = Signal(bool, str)  # (success, message)

    def _run(self, cmd, shell=False, timeout=180):
        try:
            r = subprocess.run(cmd, shell=shell, timeout=timeout, **SP_KWARGS)
            return r.returncode, r.stdout, r.stderr
        except subprocess.TimeoutExpired:
            return -2, "", "Timeout expired"
        except Exception as e:
            return -1, "", str(e)

    def uninstall(self, app):
        """直接调用软件原生卸载程序"""
        self.output.emit("正在卸载: " + app.name)

        if app.uninstall_string:
            cmd = app.uninstall_string.strip().strip('"')
            self.output.emit("运行原生卸载程序: " + cmd[:120])
            try:
                # 不使用 capture_output 和 CREATE_NO_WINDOW，让原生卸载窗口正常显示
                proc = subprocess.Popen(cmd, shell=True)
                proc.wait(timeout=300)
                code = proc.returncode
                time.sleep(2)
                if not self._check_installed(app):
                    self.finished.emit(True, "卸载成功"); return
                elif code != 0:
                    self.output.emit("用户取消或原生卸载失败（返回码 " + str(code) + "）")
                    self.finished.emit(False, "用户取消卸载" if code == 1 else "原生卸载失败"); return
                else:
                    self.output.emit("卸载程序已运行，但注册表仍存在，尝试 winget...")
            except subprocess.TimeoutExpired:
                self.output.emit("原生卸载超时，尝试 winget...")
            except Exception as e:
                self.output.emit("运行原生卸载程序失败: " + str(e))

        # Fallback: winget (only when uninstall_string was None)
        self.output.emit("尝试 winget...")
        try:
            code, out, err = self._run(
                ["winget", "uninstall", "--name", app.name, "--silent", "--accept-source-agreements"],
                timeout=120)
            if code == 0:
                time.sleep(1)
                if not self._check_installed(app):
                    self.finished.emit(True, "已通过 winget 卸载"); return
        except: pass

        if not self._check_installed(app):
            self.finished.emit(True, "已移除"); return

        self.finished.emit(False, "卸载失败 - 请尝试强制卸载")

    def force_uninstall(self, app):
        """Geek-style force uninstall: kill processes, delete files, clean registry."""
        self.output.emit("=== 强制卸载: " + app.name + " ===")

        # Step 1: Try normal uninstall first (interactive)
        if app.uninstall_string:
            cmd = app.uninstall_string.strip().strip('"')
            # Try interactive first so user can cancel if they want
            self.output.emit("步骤1: 运行官方卸载程序...")
            try:
                # Run without /quiet so user sees the uninstall dialog
                code, out, err = self._run(cmd, shell=True, timeout=300)
                if code == 0:
                    self.output.emit("官方卸载程序完成")
                elif code == -2:
                    self.output.emit("卸载程序超时")
                else:
                    self.output.emit("卸载程序返回: " + str(code))
            except Exception as e:
                self.output.emit("运行卸载程序出错: " + str(e))

        time.sleep(1)

        # Step 2: Kill related processes
        self.output.emit("步骤2: 终止相关进程...")
        self._kill_related(app)

        # Step 3: Delete installation directory
        self.output.emit("步骤3: 删除安装文件...")
        files_deleted = self._deep_delete(app)

        # Step 4: Clean registry
        self.output.emit("步骤4: 清理注册表...")
        reg_cleaned = self._clean_registry(app)

        # Step 5: Clean AppData
        self.output.emit("步骤5: 清理用户数据...")
        appdata_cleaned = self._clean_appdata(app)

        # Step 6: Clean start menu shortcuts
        self.output.emit("步骤6: 清理快捷方式...")
        self._clean_shortcuts(app)

        total = files_deleted + reg_cleaned + appdata_cleaned
        if self._check_installed(app):
            self.output.emit("警告: 软件可能未完全清除")
            self.finished.emit(False, "强制卸载完成（" + str(total) + " 项已清理，但注册表可能仍有残留）")
        else:
            self.finished.emit(True, "强制卸载成功（" + str(total) + " 项已清理）")

    def _check_installed(self, app):
        """Check if app still appears in registry or files exist."""
        # Check if install dir still exists
        if app.install_location:
            loc = app.install_location.strip('"')
            if os.path.exists(loc):
                return True
        # Check registry
        try:
            if app.hive == "HKLM":
                hive = winreg.HKEY_LOCAL_MACHINE
            else:
                hive = winreg.HKEY_CURRENT_USER
            key = winreg.OpenKey(hive, app.registry_key)
            winreg.CloseKey(key)
            return True
        except:
            pass
        # Also check alternate registry locations
        reg_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall"),
        ]
        for root_key, subpath in reg_paths:
            try:
                key = winreg.OpenKey(root_key, subpath)
                i = 0
                while True:
                    try:
                        skn = winreg.EnumKey(key, i)
                        sk = winreg.OpenKey(root_key, subpath + "\\" + skn)
                        try:
                            dn = str(winreg.QueryValueEx(sk, "DisplayName")[0])
                            if app.name.lower() in dn.lower():
                                winreg.CloseKey(sk)
                                return True
                        except: pass
                        winreg.CloseKey(sk)
                    except OSError: break
                    i += 1
                winreg.CloseKey(key)
            except: pass
        return False

    def _kill_related(self, app):
        """Kill processes related to the app."""
        import psutil
        exe_names = set()
        if app.install_location:
            loc = app.install_location.strip('"')
            if os.path.exists(loc):
                for root, dirs, files in os.walk(loc):
                    for f in files:
                        if f.lower().endswith('.exe'):
                            exe_names.add(f.lower())
                    if len(exe_names) > 50:
                        break
        killed = 0
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                pname = (proc.info['name'] or '').lower()
                if pname in exe_names or app.name.lower().replace(' ', '') in pname:
                    proc.kill()
                    self.output.emit("  已终止: " + proc.info['name'] + " (PID: " + str(proc.info['pid']) + ")")
                    killed += 1
            except: pass
        if killed == 0:
            self.output.emit("  未发现运行中的进程")

    def _deep_delete(self, app):
        """Delete installation directory and all related files."""
        deleted = 0
        dirs_to_check = []
        if app.install_location:
            dirs_to_check.append(app.install_location.strip('"'))
        # Also check common install paths
        name_clean = app.name.replace(' ', '').replace('-', '').lower()
        for base in [r"C:\\Program Files", r"C:\\Program Files (x86)", os.environ.get("LOCALAPPDATA", ""), os.environ.get("PROGRAMDATA", "")]:
            if not base:
                continue
            try:
                for entry in os.scandir(base):
                    if name_clean in entry.name.lower().replace(' ', ''):
                        dirs_to_check.append(entry.path)
            except: pass
        for d in set(dirs_to_check):
            if os.path.exists(d):
                try:
                    if os.path.isdir(d):
                        shutil.rmtree(d, ignore_errors=True)
                        self.output.emit("  已删除目录: " + d)
                        deleted += len(list(os.walk(d))) if os.path.exists(d) else 1
                    else:
                        os.remove(d)
                        self.output.emit("  已删除文件: " + d)
                        deleted += 1
                except Exception as e:
                    self.output.emit("  删除失败: " + d + " - " + str(e))
        return deleted

    def _clean_registry(self, app):
        """Deep clean registry entries related to the app."""
        cleaned = 0

        # Step 0: Directly delete the app's known registry key FIRST
        if app.registry_key:
            try:
                hive_map = {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER}
                rk = hive_map.get(app.hive, winreg.HKEY_LOCAL_MACHINE)
                ok, err = _delete_registry_tree(rk, app.registry_key)
                if ok:
                    self.output.emit("  已删除注册表项: " + app.registry_key)
                    cleaned += 1
                else:
                    self.output.emit("  注册表项删除失败: " + app.registry_key + " - " + err)
            except Exception as e:
                self.output.emit("  注册表项删除异常: " + app.registry_key + " - " + str(e))

        reg_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\\WOW6432Node"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE"),
        ]
        name_lower = app.name.lower()
        publisher_lower = (app.publisher or "").lower()
        for root_key, subpath in reg_paths:
            try:
                key = winreg.OpenKey(root_key, subpath, 0, winreg.KEY_READ | winreg.KEY_WRITE)
                to_delete = []
                i = 0
                while True:
                    try:
                        skn = winreg.EnumKey(key, i)
                        sk_lower = skn.lower()
                        if name_lower in sk_lower or (publisher_lower and publisher_lower in sk_lower):
                            to_delete.append(skn)
                    except OSError: break
                    i += 1
                for skn in to_delete:
                    try:
                        ok, err = _delete_registry_tree(root_key, subpath + "\\" + skn)
                        if ok:
                            self.output.emit("  已删除注册表: " + skn)
                            cleaned += 1
                        else:
                            self.output.emit("  注册表删除失败: " + skn + " - " + err)
                    except Exception as e:
                        self.output.emit("  注册表删除失败: " + skn + " - " + str(e))
                winreg.CloseKey(key)
            except Exception as e:
                pass
        return cleaned

    def _clean_appdata(self, app):
        """Clean user AppData directories."""
        cleaned = 0
        name_clean = app.name.replace(' ', '').replace('-', '').lower()
        publisher_clean = (app.publisher or "").replace(' ', '').replace('-', '').lower()
        bases = [
            os.environ.get("APPDATA", ""),
            os.environ.get("LOCALAPPDATA", ""),
        ]
        for base in bases:
            if not base:
                continue
            try:
                for entry in os.scandir(base):
                    ename = entry.name.lower().replace(' ', '').replace('-', '')
                    if name_clean in ename or (publisher_clean and publisher_clean in ename):
                        try:
                            if entry.is_dir():
                                shutil.rmtree(entry.path, ignore_errors=True)
                            else:
                                os.remove(entry.path)
                            self.output.emit("  已清理用户数据: " + entry.name)
                            cleaned += 1
                        except Exception as e:
                            self.output.emit("  清理失败: " + entry.name + " - " + str(e))
            except: pass
        return cleaned

    def _clean_shortcuts(self, app):
        """Clean Start Menu and Desktop shortcuts."""
        cleaned = 0
        name_clean = app.name.replace(' ', '').replace('-', '').lower()
        shortcut_dirs = [
            os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs"),
            os.path.join(os.environ.get("PROGRAMDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs"),
            os.path.join(os.environ.get("USERPROFILE", ""), "Desktop"),
            os.path.join(os.environ.get("PUBLIC", ""), "Desktop"),
        ]
        for sdir in shortcut_dirs:
            if not os.path.exists(sdir):
                continue
            for root, dirs, files in os.walk(sdir):
                for f in files:
                    if name_clean in f.lower().replace(' ', '').replace('-', '') and f.lower().endswith(('.lnk', '.url')):
                        fp = os.path.join(root, f)
                        try:
                            os.remove(fp)
                            self.output.emit("  已删除快捷方式: " + f)
                            cleaned += 1
                        except: pass
                # Also delete matching directories
                for d in list(dirs):
                    if name_clean in d.lower().replace(' ', '').replace('-', ''):
                        dp = os.path.join(root, d)
                        try:
                            shutil.rmtree(dp, ignore_errors=True)
                            self.output.emit("  已删除快捷方式目录: " + d)
                            cleaned += 1
                        except: pass
        return cleaned


def _delete_registry_tree(root_key, subpath):
    """Recursively delete a registry key and all its subkeys. Returns (success, error_msg)."""
    try:
        key = winreg.OpenKey(root_key, subpath, 0, winreg.KEY_READ | winreg.KEY_WRITE | winreg.KEY_WOW64_64KEY)
        i = 0
        while True:
            try:
                skn = winreg.EnumKey(key, i)
                _delete_registry_tree(root_key, subpath + "\\" + skn)
            except OSError:
                break
            i += 1
        winreg.CloseKey(key)
        winreg.DeleteKey(root_key, subpath)
        return (True, "")
    except PermissionError:
        return (False, "权限不足，请以管理员身份运行")
    except OSError as e:
        if e.winerror == 2:  # File not found
            return (True, "已不存在")
        return (False, str(e))
    except Exception as e:
        return (False, str(e))
