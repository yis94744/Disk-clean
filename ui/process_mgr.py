"""Process Manager - QThread-based, non-blocking, with software attribution"""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTreeWidget, QTreeWidgetItem, QMessageBox, QApplication)
from PySide6.QtCore import Signal, QTimer, QThread, QObject
from PySide6.QtGui import QFont, QColor
from collections import defaultdict
from utils.helpers import format_size
from utils.themes import size_color
import subprocess as _sp, os as _os

# Process name -> Chinese software name mapping
SOFTWARE_MAP = {
    "chrome.exe": "Google Chrome \u6d4f\u89c8\u5668",
    "msedge.exe": "Microsoft Edge \u6d4f\u89c8\u5668",
    "firefox.exe": "Mozilla Firefox \u6d4f\u89c8\u5668",
    "brave.exe": "Brave \u6d4f\u89c8\u5668",
    "iexplore.exe": "Internet Explorer",
    "explorer.exe": "Windows \u8d44\u6e90\u7ba1\u7406\u5668",
    "dwm.exe": "Windows \u684c\u9762\u7a97\u53e3\u7ba1\u7406\u5668",
    "taskmgr.exe": "Windows \u4efb\u52a1\u7ba1\u7406\u5668",
    "cmd.exe": "Windows \u547d\u4ee4\u63d0\u793a\u7b26",
    "powershell.exe": "Windows PowerShell",
    "conhost.exe": "Windows \u63a7\u5236\u53f0\u4e3b\u673a",
    "svchost.exe": "Windows \u670d\u52a1\u4e3b\u673a\u8fdb\u7a0b",
    "csrss.exe": "Windows \u5ba2\u6237\u670d\u52a1\u5668\u8fdb\u7a0b",
    "winlogon.exe": "Windows \u767b\u5f55\u7ba1\u7406\u5668",
    "lsass.exe": "Windows \u5b89\u5168\u9a8c\u8bc1\u670d\u52a1",
    "services.exe": "Windows \u670d\u52a1\u63a7\u5236\u7ba1\u7406\u5668",
    "smss.exe": "Windows \u4f1a\u8bdd\u7ba1\u7406\u5668",
    "spoolsv.exe": "Windows \u6253\u5370\u5047\u8131\u673a",
    "wininit.exe": "Windows \u542f\u52a8\u521d\u59cb\u5316",
    "fontdrvhost.exe": "Windows \u5b57\u4f53\u9a71\u52a8\u4e3b\u673a",
    "ctfmon.exe": "Windows \u8bed\u8a00\u680f\u76d1\u63a7",
    "sihost.exe": "Windows Shell \u57fa\u7840\u8bbe\u65bd",
    "taskhostw.exe": "Windows \u4efb\u52a1\u4e3b\u673a",
    "rundll32.exe": "Windows \u52a8\u6001\u5e93\u8fd0\u884c\u5668",
    "regedit.exe": "Windows \u6ce8\u518c\u8868\u7f16\u8f91\u5668",
    "notepad.exe": "Windows \u8bb0\u4e8b\u672c",
    "mspaint.exe": "Microsoft \u753b\u56fe",
    "calc.exe": "Windows \u8ba1\u7b97\u5668",
    "snippingtool.exe": "Windows \u622a\u56fe\u5de5\u5177",
    "code.exe": "Visual Studio Code",
    "devenv.exe": "Visual Studio IDE",
    "msbuild.exe": "MSBuild \u6784\u5efa\u5de5\u5177",
    "python.exe": "Python \u89e3\u91ca\u5668",
    "pythonw.exe": "Python (\u65e0\u7a97\u53e3)",
    "java.exe": "Java \u8fd0\u884c\u65f6",
    "javaw.exe": "Java (\u65e0\u7a97\u53e3)",
    "node.exe": "Node.js \u8fd0\u884c\u65f6",
    "npm.exe": "npm \u5305\u7ba1\u7406\u5668",
    "git.exe": "Git \u7248\u672c\u63a7\u5236",
    "bash.exe": "Git Bash Shell",
    "wsl.exe": "WSL \u5b50\u7cfb\u7edf",
    "docker.exe": "Docker \u5bb9\u5668\u5f15\u64ce",
    "com.docker.backend.exe": "Docker Desktop \u540e\u7aef",
    "Discord.exe": "Discord \u901a\u8baf",
    "slack.exe": "Slack \u534f\u4f5c",
    "Teams.exe": "Microsoft Teams",
    "zoom.exe": "Zoom \u4f1a\u8bae",
    "WeChat.exe": "\u5fae\u4fe1",
    "Wechat.exe": "\u5fae\u4fe1",
    "QQ.exe": "QQ",
    "DingTalk.exe": "\u9489\u9489",
    "Telegram.exe": "Telegram \u901a\u8baf",
    "Spotify.exe": "Spotify \u97f3\u4e50",
    "iTunes.exe": "iTunes \u97f3\u4e50",
    "vlc.exe": "VLC \u5a92\u4f53\u64ad\u653e\u5668",
    "notepad++.exe": "Notepad++ \u7f16\u8f91\u5668",
    "sublime_text.exe": "Sublime Text",
    "WINWORD.EXE": "Microsoft Word",
    "EXCEL.EXE": "Microsoft Excel",
    "POWERPNT.EXE": "Microsoft PowerPoint",
    "OUTLOOK.EXE": "Microsoft Outlook",
    "onedrive.exe": "OneDrive \u4e91\u76d8",
    "dropbox.exe": "Dropbox \u4e91\u76d8",
    "steam.exe": "Steam \u6e38\u620f\u5e73\u53f0",
    "EpicGamesLauncher.exe": "Epic Games Launcher",
    "Adobe Desktop Service.exe": "Adobe Creative Cloud",
    "Photoshop.exe": "Adobe Photoshop",
    "AfterFX.exe": "Adobe After Effects",
    "obs64.exe": "OBS Studio \u76f4\u64ad",
    "thunderbird.exe": "Thunderbird \u90ae\u4ef6",
    "7zFM.exe": "7-Zip \u538b\u7f29\u7ba1\u7406\u5668",
    "7zG.exe": "7-Zip",
    "winrar.exe": "WinRAR \u538b\u7f29",
    "everything.exe": "Everything \u641c\u7d22",
    "utorrent.exe": "uTorrent \u4e0b\u8f7d",
    "qbittorrent.exe": "qBittorrent \u4e0b\u8f7d",
    "aria2c.exe": "aria2 \u4e0b\u8f7d\u5de5\u5177",
    "nginx.exe": "Nginx Web\u670d\u52a1\u5668",
    "httpd.exe": "Apache HTTP\u670d\u52a1\u5668",
    "mysqld.exe": "MySQL \u6570\u636e\u5e93\u670d\u52a1",
    "postgres.exe": "PostgreSQL \u6570\u636e\u5e93",
    "mongod.exe": "MongoDB \u6570\u636e\u5e93",
    "redis-server.exe": "Redis \u7f13\u5b58\u670d\u52a1",
    "Codex CLI.exe": "OpenAI Codex CLI",
    "Codex.exe": "OpenAI Codex",
    "Cursor.exe": "Cursor IDE",
    "idea64.exe": "IntelliJ IDEA",
    "pycharm64.exe": "PyCharm IDE",
    "webstorm64.exe": "WebStorm IDE",
    "goland64.exe": "GoLand IDE",
    "clion64.exe": "CLion IDE",
    "rider64.exe": "Rider IDE",
    "datagrip64.exe": "DataGrip",
}

def _resolve_software(proc_name, proc_pid):
    lname = proc_name.lower()
    if lname in SOFTWARE_MAP:
        return SOFTWARE_MAP[lname]
    if proc_name in SOFTWARE_MAP:
        return SOFTWARE_MAP[proc_name]
    # Try to get exe path and extract folder name
    try:
        import psutil
        p = psutil.Process(proc_pid)
        exe = p.exe()
        if exe:
            dirname = _os.path.basename(_os.path.dirname(exe))
            # Check if dirname looks like a software name
            if dirname and len(dirname) > 2 and not dirname.lower() in ('bin','app','apps','lib','usr','opt','program','files','windows','system32','syswow64'):
                return dirname
            # Check parent's parent
            pp = _os.path.dirname(_os.path.dirname(exe))
            ppn = _os.path.basename(pp)
            if ppn and len(ppn) > 2 and ppn.lower() not in ('program files','program files (x86)','windows','users'):
                return ppn
    except:
        pass
    return ""

class _ProcessWorker(QObject):
    progress = Signal(str)
    finished = Signal(list)

    def run(self):
        import psutil, time
        try:
            self.progress.emit("正在读取进程列表...")
            # Get all processes ONCE, keep references for cpu_percent baseline
            procs = list(psutil.process_iter(['pid', 'name', 'memory_info', 'status', 'username']))
            # First call to establish baseline
            for p in procs:
                try: p.cpu_percent()
                except: pass
            # Wait for measurement
            time.sleep(0.5)
            # Second call to get actual CPU%
            processes = []
            for p in procs:
                try:
                    info = p.as_dict()
                    cpu = p.cpu_percent() or 0.0
                    mem = info.get('memory_info')
                    processes.append({
                        'pid': p.pid,
                        'name': info.get('name', ''),
                        'cpu': cpu,
                        'mem_rss': mem.rss if mem else 0,
                        'status': info.get('status', ''),
                        'user': (info.get('username', '') or '')[:25]
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            # Filter: skip processes with < 0.05% CPU (noise)
            processes = [p for p in processes if p['cpu'] >= 0.05 or p['mem_rss'] > 1048576]
            self.finished.emit(processes)
        except Exception as e:
            self.progress.emit(f"进程读取失败: {e}")
            self.finished.emit([])



class ProcessManagerPage(QWidget):
    status_message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread = None
        self._worker = None
        self._setup_ui()
        QTimer.singleShot(100, self._refresh)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 6)
        layout.setSpacing(6)

        tb = QHBoxLayout()
        self.rf_btn = QPushButton("刷新进程列表")
        self.rf_btn.setObjectName("greenBtn")
        self.rf_btn.clicked.connect(self._refresh)
        tb.addWidget(self.rf_btn)
        kill_btn = QPushButton("结束进程")
        kill_btn.setObjectName("redBtn")
        kill_btn.clicked.connect(self._kill)
        tb.addWidget(kill_btn)
        tb.addStretch()
        layout.addLayout(tb)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["进程名称", "CPU", "内存", "PID", "状态", "用户", "程序归属"])
        self.tree.setColumnWidth(0, 200); self.tree.setColumnWidth(1, 65)
        self.tree.setColumnWidth(2, 85); self.tree.setColumnWidth(3, 60)
        self.tree.setColumnWidth(4, 85); self.tree.setColumnWidth(5, 110)
        self.tree.setColumnWidth(6, 150)
        self.tree.setSortingEnabled(True); self.tree.setIndentation(20)
        self.tree.setAnimated(True); self.tree.setExpandsOnDoubleClick(True)
        layout.addWidget(self.tree)
        self.sl = QLabel(""); self.sl.setStyleSheet("color:#aaa;font-size:11px;"); layout.addWidget(self.sl)

    def _refresh(self):
        self.rf_btn.setEnabled(False); self.sl.setText("加载中...")
        if self._thread and self._thread.isRunning():
            self._thread.quit(); self._thread.wait(2000)
        self._thread = QThread()
        self._worker = _ProcessWorker()
        self._worker.moveToThread(self._thread)
        self._worker.progress.connect(self.sl.setText)
        self._worker.finished.connect(self._on_data)
        self._thread.started.connect(self._worker.run)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_data(self, processes):
        self.tree.clear()
        groups = defaultdict(list)
        for proc in processes: groups[proc['name'].lower()].append(proc)
        sorted_groups = sorted(groups.items(), key=lambda x: sum(p['mem_rss'] for p in x[1]), reverse=True)
        visible = 0; total_p = len(processes)
        for _, procs in sorted_groups:
            t_cpu = sum(p['cpu'] for p in procs); t_mem = sum(p['mem_rss'] for p in procs)
            sw_name = _resolve_software(procs[0]['name'], procs[0]['pid'])
            if len(procs) == 1:
                p = procs[0]
                it = QTreeWidgetItem()
                it.setText(0, p['name']); it.setText(1, f"{p['cpu']:.1f}%")
                it.setText(2, format_size(p['mem_rss'])); it.setText(3, str(p['pid']))
                it.setText(4, p['status'] or "-"); it.setText(5, p['user'])
                it.setText(6, sw_name or _resolve_software(p['name'], p['pid']))
                cpu_c = size_color(p['cpu']); it.setForeground(1, QColor(cpu_c))
                it.setData(0, 256, p['pid']); self.tree.addTopLevelItem(it); visible += 1
            else:
                par = QTreeWidgetItem()
                par.setText(0, f"{procs[0]['name']} ({len(procs)})")
                par.setText(1, f"{t_cpu:.1f}%"); par.setText(2, format_size(t_mem))
                par.setText(3, "-"); par.setText(4, f"{len(procs)} 个进程"); par.setText(5, "")
                par.setText(6, sw_name)
                cpu_c = size_color(t_cpu); par.setForeground(1, QColor(cpu_c))
                self.tree.addTopLevelItem(par); visible += 1
                for p in sorted(procs, key=lambda x: x['mem_rss'], reverse=True):
                    child = QTreeWidgetItem()
                    child.setText(0, p['name']); child.setText(1, f"{p['cpu']:.1f}%")
                    child.setText(2, format_size(p['mem_rss'])); child.setText(3, str(p['pid']))
                    child.setText(4, p['status'] or "-"); child.setText(5, p['user'])
                    child.setText(6, "")
                    cpu_c = size_color(p['cpu']); child.setForeground(1, QColor(cpu_c))
                    child.setData(0, 256, p['pid']); par.addChild(child)
        self.rf_btn.setEnabled(True)
        self.sl.setText(f"共 {total_p} 个进程，显示 {visible} 个组")
        self.status_message.emit(f"进程管理: {total_p} 个进程")

    def _kill(self):
        sel = self.tree.currentItem()
        if not sel:
            QMessageBox.information(self, "提示", "请先选择要结束的进程")
            return
        pid = sel.data(0, 256)
        if not pid:
            QMessageBox.information(self, "提示", "请选择具体的子进程而非进程组")
            return
        import psutil
        try:
            p = psutil.Process(pid)
            name = p.name()
            r = QMessageBox.warning(self, "确认结束",
                f"确定要结束进程 {name} (PID: {pid}) 吗？",
                QMessageBox.Yes|QMessageBox.No, QMessageBox.No)
            if r != QMessageBox.Yes: return
            p.terminate()
            p.wait(3)
            self.status_message.emit(f"已结束: {name}")
            QTimer.singleShot(800, self._refresh)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法结束进程: {e}")
