"""Disk Cleaner Pro - Main Window with robust deferred page loading"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget,
    QHBoxLayout, QVBoxLayout, QStackedWidget, QStatusBar,
    QLabel, QFrame, QPushButton)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from ui.widgets.sidebar import Sidebar
from ui.dashboard import DashboardPage
from ui.file_visualizer import FileVisualizerPage
from ui.safe_cleaner import SafeCleanerPage
from ui.software_mgr import SoftwareManagerPage
from ui.dup_finder import DupFinderPage
from ui.large_files import LargeFilesPage
from ui.startup_mgr import StartupManagerPage
from ui.process_mgr import ProcessManagerPage
from ui.system_info import SystemInfoPage
from ui.settings import SettingsPage
from utils.helpers import is_admin, get_drive_info
from utils.themes import build_stylesheet, build_sidebar_style, load_settings
from utils.constants import APP_NAME

def _load_theme():
    s = load_settings()
    return build_stylesheet(s.get('theme', 'deep'))

THEME = _load_theme()

PAGE_CLASSES = {
    "dashboard": DashboardPage, "file_visualizer": FileVisualizerPage, "safe_cleaner": SafeCleanerPage,
    "software_mgr": SoftwareManagerPage, "dup_finder": DupFinderPage,
    "large_files": LargeFilesPage, "startup_mgr": StartupManagerPage,
    "process_mgr": ProcessManagerPage, "system_info": SystemInfoPage,
    "settings": SettingsPage,
}

PAGE_TITLES = {
    "dashboard": "仪表盘", "file_visualizer": "文件可视化", "safe_cleaner": "安全清理",
    "software_mgr": "软件管理", "dup_finder": "重复文件",
    "large_files": "大文件", "startup_mgr": "启动管理",
    "process_mgr": "进程管理", "system_info": "系统信息",
    "settings": "设置",
}
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1100, 720)
        self._set_app_icon()
        self.resize(1280, 820)
        self._pages = {}
        self._current_key = ""
        self._pending_timer = None
        self._navigating = False
        self._setup_ui()
        self._setup_statusbar()
        self.setStyleSheet(THEME)
        self._apply_background()

    def _set_app_icon(self):
        import os, sys
        from PySide6.QtGui import QIcon
        # Try to find icon next to exe or in source
        base = os.path.dirname(os.path.abspath(sys.argv[0]))
        icon_paths = [
            os.path.join(base, "app.ico"),
            os.path.join(os.path.dirname(__file__), "app.ico"),
        ]
        for p in icon_paths:
            if os.path.exists(p):
                self.setWindowIcon(QIcon(p))
                return

    def _setup_ui(self):
        cw = QWidget(); self.setCentralWidget(cw)
        hl = QHBoxLayout(cw)
        hl.setContentsMargins(0, 0, 0, 0); hl.setSpacing(0)
        self.sidebar = Sidebar()
        sbs = build_sidebar_style(load_settings().get("theme", "deep"))
        self.sidebar.setStyleSheet(sbs)
        self.sidebar.nav_clicked.connect(self._navigate)
        hl.addWidget(self.sidebar)
        rp = QFrame(); rp.setObjectName("rightPanel")
        self._rp = rp  # save ref for bg setting later
        rl = QVBoxLayout(rp)
        rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(0)
        hdr = QFrame(); hdr.setObjectName("header"); hdr.setFixedHeight(42)
        hb = QHBoxLayout(hdr)
        hb.setContentsMargins(14, 5, 14, 5)
        self._title_lbl = QLabel(APP_NAME)
        self._title_lbl.setFont(QFont("Microsoft YaHei", 13, QFont.Bold))
        self._title_lbl.setStyleSheet("color:#f0f6fc;background:transparent;")
        hb.addWidget(self._title_lbl); hb.addStretch()
        admin_btn = QPushButton("管理员模式")
        admin_btn.setVisible(not is_admin())
        admin_btn.setStyleSheet("background:#da3633;color:#fff;border:none;border-radius:4px;padding:4px 10px;")
        admin_btn.clicked.connect(lambda: __import__("utils.helpers").helpers.run_as_admin())
        hb.addWidget(admin_btn)
        rl.addWidget(hdr)
        self.stack = QStackedWidget(); self.stack.setObjectName("mainStack"); self.stack.setStyleSheet("QStackedWidget{background:transparent;}")
        rl.addWidget(self.stack); hl.addWidget(rp)

    def _setup_statusbar(self):
        self.status = QStatusBar(); self.setStatusBar(self.status)
        self.status.setStyleSheet(
            "background:rgba(10,10,25,0.50);color:#8b949e;border-top:1px solid rgba(255,255,255,0.08);font-size:11px;"
        )
        self._disk_lbl = QLabel("  C: --")
        self._mem_lbl = QLabel("  RAM: --")
        self._status_lbl = QLabel("  就绪  ")
        self.status.addWidget(self._disk_lbl)
        self.status.addWidget(self._mem_lbl)
        self.status.addPermanentWidget(self._status_lbl)
        self._update_sb()
        self._sb_timer = QTimer()
        self._sb_timer.timeout.connect(self._update_sb)
        self._sb_timer.start(20000)

    def _update_sb(self):
        try:
            info = get_drive_info("C:")
            if info["total"] > 0:
                ug = info["used"] // (1024**3)
                tg = info["total"] // (1024**3)
                self._disk_lbl.setText("  C: " + str(info["percent"]) + "% (" + str(ug) + "G/" + str(tg) + "G)")
        except Exception: pass
        try:
            import psutil
            m = psutil.virtual_memory()
            self._mem_lbl.setText(f"  RAM: {int(m.percent)}%")
        except Exception: pass

    def _navigate(self, key):
        # Ignore if already navigating or same page
        if self._navigating:
            return
        if key == self._current_key:
            return
        
        self._navigating = True
        try:
            # Cancel any pending deferred load
            if self._pending_timer and self._pending_timer.isActive():
                self._pending_timer.stop()
                self._pending_timer = None
            
            # Hide old page
            if self._current_key and self._current_key in self._pages:
                old = self._pages[self._current_key]
                if hasattr(old, "_set_visible"):
                    old._set_visible(False)

            self._title_lbl.setText(PAGE_TITLES.get(key, key))

            # Create page lazily
            if key not in self._pages:
                cls = PAGE_CLASSES.get(key)
                if cls:
                    try:
                        page = cls()
                        self.stack.addWidget(page)
                        self._pages[key] = page
                        if hasattr(page, "status_message"):
                            page.status_message.connect(self._status_lbl.setText)
                        if hasattr(page, "theme_changed"):
                            page.theme_changed.connect(self._apply_theme)
                    except Exception as e:
                        print(f"Error creating page {key}: {e}")
                        return

            if key in self._pages:
                w = self._pages[key]
                if self.stack.indexOf(w) >= 0:
                    self.stack.setCurrentWidget(w)
                    self._current_key = key
                    self.sidebar.set_active(key)
                    
                    # Deferred activation: wait for UI to settle
                    self._pending_timer = QTimer()
                    self._pending_timer.setSingleShot(True)
                    self._pending_timer.timeout.connect(
                        lambda k=key: self._activate_page(k)
                    )
                    self._pending_timer.start(200)
        finally:
            self._navigating = False


    def _apply_background(self):
        # Apply background image AFTER theme stylesheet (themes override #rightPanel bg)
        if getattr(sys, 'frozen', False):
            bg_path = os.path.join(sys._MEIPASS, "bg.jpg")
        else:
            bg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bg.jpg")
        if os.path.exists(bg_path):
            bg_url = bg_path.replace("\\", "/")
            self._rp.setStyleSheet(
                f"QFrame#rightPanel {{ border-image: url({bg_url}) 0 0 0 0 stretch stretch; }}"
            )

    def _apply_theme(self, theme_name):
        """Apply theme live when settings change"""
        from utils.themes import build_stylesheet, build_sidebar_style
        ss = build_stylesheet(theme_name)
        self.setStyleSheet(ss)
        sbs = build_sidebar_style(theme_name)
        self.sidebar.setStyleSheet(sbs)

    def _activate_page(self, key):
        if key in self._pages and key == self._current_key:
            page = self._pages[key]
            if hasattr(page, "_set_visible"):
                page._set_visible(True)

def main():
    app = QApplication(sys.argv)
    font = QFont("Microsoft YaHei", 9)
    app.setFont(font)
    import warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    w = MainWindow(); w.show()
    QTimer.singleShot(100, lambda: w._navigate("dashboard"))
    sys.exit(app.exec())

if __name__ == "__main__": main()