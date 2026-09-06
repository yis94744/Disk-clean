# -*- coding: utf-8 -*-
"""Software uninstaller - registry scanner + executor + force uninstall"""
import os, subprocess, winreg, shutil, time
from PySide6.QtCore import QObject, Signal
from utils.helpers import recycle_path

# 注意：timeout 由 _run() 的参数统一传入，不能写死在这里，
# 否则 subprocess.run 收到重复的 timeout 关键字参数直接 TypeError。
SP_KWARGS = {"capture_output": True, "text": True, "encoding": "utf-8", "errors": "replace",
             "creationflags": subprocess.CREATE_NO_WINDOW}

# 进程名 -> 永不允许强制卸载器结束的系统关键进程
PROTECTED_PROCESSES = {
    "system", "registry", "idle", "explorer.exe", "svchost.exe", "csrss.exe",
    "winlogon.exe", "services.exe", "lsass.exe", "smss.exe", "wininit.exe",
    "dwm.exe", "fontdrvhost.exe", "taskhostw.exe", "sihost.exe", "ctfmon.exe",
    "conhost.exe", "spoolsv.exe", "msmpeng.exe", "securityhealthservice.exe",
}

def _name_token(text):
    """Lowercase alphanumeric token of an app/publisher name for matching."""
    return "".join(ch for ch in (text or "").lower() if ch.isalnum())


def parse_command_line(s):
    """把 Windows 命令行字符串切分为 argv，正确处理双引号。

    注册表 UninstallString 形如 '"C:\\...\\Uninstall App.exe" /currentuser'，
    之前用 .strip('"') 只去掉首尾引号，中间引号仍在，shell=True 时 cmd 解析失败。
    """
    toks, cur, in_q = [], [], False
    for ch in (s or ""):
        if ch == '"':
            in_q = not in_q
        elif ch in " \t" and not in_q:
            if cur:
                toks.append("".join(cur))
                cur = []
        else:
            cur.append(ch)
    if cur:
        toks.append("".join(cur))
    return toks


def _split_first_token(raw):
    """返回 (第一个token, 其余原文)，其余部分保持原始引号不做改写。"""
    s = raw.lstrip()
    if s.startswith('"'):
        end = s.find('"', 1)
        if end > 0:
            return s[1:end], s[end + 1:].lstrip()
    for i, ch in enumerate(s):
        if ch in " \t":
            return s[:i], s[i:].lstrip()
    return s, ""

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
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]
        for hive, subkey in regs:
            try:
                key = winreg.OpenKey(hive, subkey)
                i = 0
                while True:
                    try:
                        skn = winreg.EnumKey(key, i)
                    except OSError:
                        break
                    i += 1
                    try:
                        sk = winreg.OpenKey(hive, subkey + "\\" + skn)
                    except OSError:
                        continue
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
                            app.registry_key = subkey + "\\" + skn
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

    # 视为成功的卸载器返回码：
    #   0=成功  1605=软件未安装  3010/1641=成功但需重启
    SUCCESS_EXIT_CODES = {0, 1605, 3010, 1641}
    # 用户主动取消的返回码：1=常见取消码(NSIS/Inno)  1602=MSI 用户取消
    CANCEL_EXIT_CODES = {1, 1602}

    def _launch_uninstaller(self, app, timeout=600):
        """以正确的方式启动原生卸载程序。返回 (返回码, 错误信息)。

        - 注册表里的 '"exe 路径 带空格" 参数' 必须按引号解析后用 argv 启动，
          否则 cmd 解析失败返回 1，被误判为“用户取消”。
        - requireAdministrator 的卸载器在 CreateProcess 下报 WinError 740，
          此时用 ShellExecuteW(runas) 走 UAC 提权。
        """
        raw = (app.uninstall_string or "").strip()
        if not raw:
            return None, "没有卸载程序信息"
        self.output.emit("运行原生卸载程序: " + raw[:160])
        argv = parse_command_line(raw)
        exe = argv[0] if argv else ""
        exe_file = exe
        if exe and not os.path.isabs(exe):
            exe_file = shutil.which(exe) or exe
        use_argv = bool(exe) and os.path.isabs(exe_file) and os.path.isfile(exe_file)
        try:
            if use_argv:
                proc = subprocess.Popen(argv)
            else:
                # 畸形注册表项（未加引号的带空格路径等），退回 shell 让 cmd 解释
                proc = subprocess.Popen(raw, shell=True)
        except OSError as e:
            if getattr(e, "winerror", 0) == 740:
                return self._launch_elevated(raw, timeout)
            return None, str(e)
        try:
            proc.wait(timeout=timeout)
            return proc.returncode, ""
        except subprocess.TimeoutExpired:
            raise

    def _launch_elevated(self, raw, timeout, verb="runas"):
        """通过 ShellExecuteW 启动（支持 UAC 提权），返回 (返回码, 错误信息)。"""
        import ctypes
        from ctypes import wintypes

        file_tok, params = _split_first_token(raw)

        class SHELLEXECUTEINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD), ("fMask", wintypes.ULONG),
                ("hwnd", wintypes.HWND), ("lpVerb", wintypes.LPCWSTR),
                ("lpFile", wintypes.LPCWSTR), ("lpParameters", wintypes.LPCWSTR),
                ("lpDirectory", wintypes.LPCWSTR), ("nShow", ctypes.c_int),
                ("hInstApp", wintypes.HINSTANCE), ("lpIDList", ctypes.c_void_p),
                ("lpClass", wintypes.LPCWSTR), ("hkeyClass", wintypes.HKEY),
                ("dwHotKey", wintypes.DWORD), ("hIconOrMonitor", wintypes.HANDLE),
                ("hProcess", wintypes.HANDLE),
            ]

        SEE_MASK_NOCLOSEPROCESS = 0x00000040
        SEE_MASK_NOASYNC = 0x00000100
        sei = SHELLEXECUTEINFO()
        sei.cbSize = ctypes.sizeof(SHELLEXECUTEINFO)
        sei.fMask = SEE_MASK_NOCLOSEPROCESS | SEE_MASK_NOASYNC
        sei.lpVerb = verb
        sei.lpFile = file_tok or raw
        sei.lpParameters = params or None
        sei.nShow = 1  # SW_SHOWNORMAL：卸载窗口要显示给用户
        if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(sei)) or not sei.hProcess:
            # 用户在 UAC 弹窗点了“否”等场景
            return 1602, "用户拒绝了管理员权限请求 (UAC)"
        WAIT_OBJECT_0 = 0
        WAIT_TIMEOUT = 0x00000102
        res = ctypes.windll.kernel32.WaitForSingleObject(
            sei.hProcess, int(timeout * 1000))
        if res == WAIT_TIMEOUT:
            raise subprocess.TimeoutExpired(raw, timeout)
        exit_code = wintypes.DWORD()
        ctypes.windll.kernel32.GetExitCodeProcess(sei.hProcess, ctypes.byref(exit_code))
        ctypes.windll.kernel32.CloseHandle(sei.hProcess)
        return exit_code.value, ""

    def _wait_uninstalled(self, app, seconds):
        """轮询等待软件从注册表消失。

        NSIS 类卸载器会把自己复制到 %TEMP% 再重启，原进程立即退出而卸载仍在
        进行，wait() 返回时注册表往往还没删，需要轮询等待。
        """
        interval = 2
        waited = 0
        while waited < seconds:
            if not self._check_installed(app):
                return True
            time.sleep(interval)
            waited += interval
            if waited % 10 == 0:
                self.output.emit("  等待卸载完成... (" + str(waited) + "s)")
        return not self._check_installed(app)

    def uninstall(self, app):
        """直接调用软件原生卸载程序"""
        if app.uninstall_string and app.uninstall_string.strip():
            timed_out = False
            try:
                code, err = self._launch_uninstaller(app, timeout=600)
            except subprocess.TimeoutExpired:
                code, timed_out = None, True
            if timed_out:
                self.output.emit("原生卸载超时，等待其自行结束...")
                if self._wait_uninstalled(app, 15):
                    self.finished.emit(True, "卸载成功")
                else:
                    self.finished.emit(False, "原生卸载超时 - 请重试或使用强制卸载")
                return
            if code is None:
                self.output.emit("无法启动卸载程序: " + err)
            elif code in self.SUCCESS_EXIT_CODES:
                if self._wait_uninstalled(app, 60):
                    self.finished.emit(True, "卸载成功")
                    return
                self.output.emit("卸载程序已运行，但注册表仍存在，尝试 winget...")
            else:
                # 非零返回码：短暂等待，防止卸载器返回码不可靠
                if self._wait_uninstalled(app, 6):
                    self.finished.emit(True, "卸载成功")
                    return
                if code in self.CANCEL_EXIT_CODES:
                    self.output.emit("用户取消或原生卸载失败（返回码 " + str(code) + "）")
                    self.finished.emit(False, "用户取消卸载")
                    return
                self.output.emit("原生卸载失败（返回码 " + str(code) + "），尝试 winget...")
        else:
            self.output.emit("没有卸载程序信息，尝试 winget...")

        # Fallback: winget
        self.output.emit("尝试 winget...")
        try:
            code, out, err = self._run(
                ["winget", "uninstall", "--name", app.name, "--silent", "--accept-source-agreements"],
                timeout=120)
            if code == 0:
                if self._wait_uninstalled(app, 30):
                    self.finished.emit(True, "已通过 winget 卸载")
                    return
            else:
                detail = (err or out or "").strip()
                self.output.emit("winget 退出码 " + str(code) + (": " + detail[:120] if detail else ""))
        except Exception as e:
            self.output.emit("winget 不可用: " + str(e))

        if not self._check_installed(app):
            self.finished.emit(True, "已移除")
            return

        self.finished.emit(False, "卸载失败 - 请尝试强制卸载")

    def force_uninstall(self, app):
        """Geek-style force uninstall: kill processes, delete files, clean registry."""
        self.output.emit("=== 强制卸载: " + app.name + " ===")

        # Step 1: Try normal uninstall first (interactive)
        if app.uninstall_string:
            # Run interactive so user sees the uninstall dialog
            self.output.emit("步骤1: 运行官方卸载程序...")
            try:
                code, err = self._launch_uninstaller(app, timeout=600)
                if code is None:
                    self.output.emit("无法启动官方卸载程序: " + err)
                elif code in self.SUCCESS_EXIT_CODES:
                    self._wait_uninstalled(app, 30)
                    self.output.emit("官方卸载程序完成")
                else:
                    self.output.emit("卸载程序返回: " + str(code))
            except subprocess.TimeoutExpired:
                self.output.emit("卸载程序超时，继续强制清理...")
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
        """以注册表为准判断软件是否仍处于已安装状态。

        遗留的安装目录/文件不再算“仍安装”——很多卸载器会留下空目录或日志，
        之前因此把卸载成功的软件误判为失败。
        """
        # 1) 本应用的注册表卸载键（最权威）
        if app.registry_key:
            try:
                hive = winreg.HKEY_LOCAL_MACHINE if app.hive == "HKLM" else winreg.HKEY_CURRENT_USER
                key = winreg.OpenKey(hive, app.registry_key)
                winreg.CloseKey(key)
                return True
            except OSError:
                pass
        # 2) 三个卸载键里按名称查找：精确匹配优先，长名称(>=5字符)包含匹配兜底
        nl = (app.name or "").lower()
        if not nl:
            return False
        reg_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]
        for root_key, subpath in reg_paths:
            try:
                key = winreg.OpenKey(root_key, subpath)
            except OSError:
                continue
            i = 0
            found = False
            while True:
                try:
                    skn = winreg.EnumKey(key, i)
                except OSError:
                    break
                i += 1
                try:
                    sk = winreg.OpenKey(root_key, subpath + "\\" + skn)
                except OSError:
                    continue
                try:
                    dn = str(winreg.QueryValueEx(sk, "DisplayName")[0]).lower()
                except OSError:
                    dn = ""
                try:
                    winreg.CloseKey(sk)
                except OSError:
                    pass
                if dn == nl or (len(nl) >= 5 and nl in dn):
                    found = True
                    break
            try:
                winreg.CloseKey(key)
            except OSError:
                pass
            if found:
                return True
        return False

    def _kill_related(self, app):
        """Kill processes related to the app (conservative matching)."""
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
        # 按名称匹配时要求词首命中且名字足够长，避免误杀包含名的无关进程(如 edge 误杀 msedge)
        name_token = _name_token(app.name)
        name_match = len(name_token) >= 5
        killed = 0
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                pname = (proc.info['name'] or '').lower()
                if not pname or pname in PROTECTED_PROCESSES:
                    continue
                stem = pname[:-4] if pname.endswith('.exe') else pname
                hit = pname in exe_names or (
                    name_match and (stem == name_token or stem.replace(' ', '').startswith(name_token)))
                if hit:
                    proc.kill()
                    self.output.emit("  已终止: " + proc.info['name'] + " (PID: " + str(proc.info['pid']) + ")")
                    killed += 1
            except: pass
        if killed == 0:
            self.output.emit("  未发现运行中的进程")

    def _deep_delete(self, app):
        """Delete installation directory and all related files (Recycle Bin first)."""
        deleted = 0
        dirs_to_check = []
        if app.install_location:
            dirs_to_check.append(app.install_location.strip('"'))
        # Also check common install paths (name-token containment, length-guarded)
        name_token = _name_token(app.name)
        if len(name_token) >= 4:
            for base in [r"C:\Program Files", r"C:\Program Files (x86)",
                         os.environ.get("LOCALAPPDATA", ""), os.environ.get("PROGRAMDATA", "")]:
                if not base:
                    continue
                try:
                    for entry in os.scandir(base):
                        if name_token in _name_token(entry.name):
                            dirs_to_check.append(entry.path)
                except: pass
        for d in set(dirs_to_check):
            if os.path.exists(d):
                try:
                    if recycle_path(d):
                        self.output.emit("  已移入回收站: " + d)
                        deleted += 1
                    else:
                        # 回收站失败(路径过长/权限等)时回退为永久删除
                        if os.path.isdir(d):
                            shutil.rmtree(d, ignore_errors=True)
                        else:
                            os.remove(d)
                        if not os.path.exists(d):
                            self.output.emit("  已删除: " + d)
                            deleted += 1
                        else:
                            self.output.emit("  删除失败: " + d)
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

        # 只扫描三个卸载键，仅按软件名匹配键名，绝不按发布者匹配——
        # 否则发布者为 Microsoft 的软件会波及 SOFTWARE 下海量无关键
        reg_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]
        name_token = _name_token(app.name)
        if len(name_token) < 3:
            return cleaned
        for root_key, subpath in reg_paths:
            try:
                key = winreg.OpenKey(root_key, subpath, 0, winreg.KEY_READ | winreg.KEY_WRITE)
                to_delete = []
                i = 0
                while True:
                    try:
                        skn = winreg.EnumKey(key, i)
                        if name_token in _name_token(skn):
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
        """Clean user AppData directories (Recycle Bin first, name-token match)."""
        cleaned = 0
        name_token = _name_token(app.name)
        if len(name_token) < 3:
            return cleaned
        bases = [
            os.environ.get("APPDATA", ""),
            os.environ.get("LOCALAPPDATA", ""),
        ]
        for base in bases:
            if not base:
                continue
            try:
                for entry in os.scandir(base):
                    if name_token in _name_token(entry.name):
                        if recycle_path(entry.path):
                            self.output.emit("  已移入回收站(用户数据): " + entry.name)
                            cleaned += 1
                        else:
                            self.output.emit("  清理失败: " + entry.name)
            except: pass
        return cleaned

    def _clean_shortcuts(self, app):
        """Clean Start Menu and Desktop shortcuts (Recycle Bin)."""
        cleaned = 0
        name_token = _name_token(app.name)
        if len(name_token) < 3:
            return cleaned
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
                    if name_token in _name_token(f) and f.lower().endswith(('.lnk', '.url')):
                        fp = os.path.join(root, f)
                        if recycle_path(fp):
                            self.output.emit("  已移入回收站(快捷方式): " + f)
                            cleaned += 1
                # Also delete matching directories
                for d in list(dirs):
                    if name_token in _name_token(d):
                        dp = os.path.join(root, d)
                        if recycle_path(dp):
                            self.output.emit("  已移入回收站(快捷方式目录): " + d)
                            cleaned += 1
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
