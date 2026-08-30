"""Disk Cleaner Pro - Main Window with robust deferred page loading"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget,
    QHBoxLayout, QVBoxLayout, QStackedWidget, QStatusBar,
    QLabel, QFrame, QPushButton, QSystemTrayIcon, QMenu, QGraphicsOpacityEffect)
from PySide6.QtCore import Qt, QTimer, QEvent, QObject, QPropertyAnimation, QEasingCurve, QAbstractAnimation
from PySide6.QtGui import QFont, QAction
from ui.widgets.sidebar import Sidebar
from ui.dashboard import DashboardPage
from ui.file_visualizer import FileVisualizerPage
from ui.disk_analyzer import DiskAnalyzerPage
from ui.safe_cleaner import SafeCleanerPage
from ui.c_disk_cleaner import CDiskCleanerPage
from ui.software_mgr import SoftwareManagerPage
from ui.dup_finder import DupFinderPage
from ui.large_files import LargeFilesPage
from ui.startup_mgr import StartupManagerPage
from ui.process_mgr import ProcessManagerPage
from ui.driver_mgr import DriverMgrPage
from ui.quick_search import QuickSearchPage
from ui.system_info import SystemInfoPage
from ui.settings import SettingsPage
from utils.helpers import is_admin, get_drive_info
from utils.themes import build_stylesheet, build_sidebar_style, load_settings, get_theme
from utils.constants import APP_NAME

def _load_theme():
    s = load_settings()
    return build_stylesheet(s.get('theme', 'green'))

THEME = _load_theme()

PAGE_CLASSES = {
    "dashboard": DashboardPage, "file_visualizer": FileVisualizerPage,
    "quick_search": QuickSearchPage,
    "disk_analyzer": DiskAnalyzerPage, "safe_cleaner": SafeCleanerPage,
    "c_cleaner": CDiskCleanerPage, "software_mgr": SoftwareManagerPage,
    "dup_finder": DupFinderPage,
    "large_files": LargeFilesPage, "startup_mgr": StartupManagerPage,
    "process_mgr": ProcessManagerPage, "driver_mgr": DriverMgrPage,
    "system_info": SystemInfoPage,
    "settings": SettingsPage,
}

PAGE_TITLES = {
    "dashboard": "仪表盘", "file_visualizer": "文件可视化", "quick_search": "极速搜索", "disk_analyzer": "磁盘分析",
    "safe_cleaner": "安全清理", "c_cleaner": "C盘专清", "software_mgr": "软件管理", "dup_finder": "重复文件",
    "large_files": "大文件", "startup_mgr": "启动管理",
    "process_mgr": "进程管理", "driver_mgr": "驱动检测", "system_info": "系统信息",
    "settings": "设置",
}


def _repolish(w):
    st = w.style()
    st.unpolish(w)
    st.polish(w)


class _ButtonGlow(QObject):
    """全局按钮点击动效：按下发光描边，松开恢复（配合 QSS :pressed 下沉）。"""

    def eventFilter(self, obj, event):
        et = event.type()
        if isinstance(obj, QPushButton) and obj.isEnabled():
            if et == QEvent.MouseButtonPress:
                obj.setProperty("pressGlow", True)
                _repolish(obj)
            elif et in (QEvent.MouseButtonRelease, QEvent.Hide):
                if obj.property("pressGlow"):
                    obj.setProperty("pressGlow", False)
                    _repolish(obj)
        return False
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
        self._pending_nav_key = ""
        self._nav_timer = QTimer(self)
        self._nav_timer.setSingleShot(True)
        self._nav_timer.timeout.connect(self._do_navigate)
        self._setup_ui()
        self._setup_statusbar()
        self.setStyleSheet(THEME)
        self._apply_background()
        self._setup_tray()

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
        theme_name = load_settings().get("theme", "green")
        sbs = build_sidebar_style(theme_name)
        self.sidebar.setStyleSheet(sbs)
        self.sidebar.set_accent(get_theme(theme_name)["accent"])
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
        """合并连续导航点击：只记录最新请求，事件循环空闲时执行最后一次。

        首次进入某页会在 UI 线程同步构造页面（数十至数百毫秒），连点期间
        被阻塞的点击会排队并在解除阻塞后逐个补执行，造成长时间卡顿；
        合并后无论点多少下都只切换到最后一页。"""
        if key == self._current_key:
            return
        self._pending_nav_key = key
        self._nav_timer.start(0)

    def _do_navigate(self):
        key = self._pending_nav_key
        self._pending_nav_key = ""
        if not key or key == self._current_key:
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
                        if hasattr(page, "action_requested"):
                            page.action_requested.connect(self._on_page_action)
                    except Exception as e:
                        print(f"Error creating page {key}: {e}")
                        return

            if key in self._pages:
                w = self._pages[key]
                if self.stack.indexOf(w) >= 0:
                    self.stack.setCurrentWidget(w)
                    self._current_key = key
                    self.sidebar.set_active(key)
                    self._fade_in(w)

                    # Deferred activation: short settle wait (50ms) keeps first paint snappy
                    self._pending_timer = QTimer()
                    self._pending_timer.setSingleShot(True)
                    self._pending_timer.timeout.connect(
                        lambda k=key: self._activate_page(k)
                    )
                    self._pending_timer.start(50)
        finally:
            self._navigating = False

    def _fade_in(self, w):
        """页面切换淡入动效。"""
        try:
            if w.graphicsEffect():
                w.setGraphicsEffect(None)
            eff = QGraphicsOpacityEffect(w)
            eff.setOpacity(0.35)
            w.setGraphicsEffect(eff)
            anim = QPropertyAnimation(eff, b"opacity", self)
            anim.setDuration(180)
            anim.setStartValue(0.35)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            anim.finished.connect(lambda ww=w: ww.setGraphicsEffect(None))
            anim.start(QAbstractAnimation.DeleteWhenStopped)
            self._fade_anim = anim
        except Exception:
            pass


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
        from utils.themes import build_stylesheet, build_sidebar_style, get_theme
        ss = build_stylesheet(theme_name)
        self.setStyleSheet(ss)
        sbs = build_sidebar_style(theme_name)
        self.sidebar.setStyleSheet(sbs)
        self.sidebar.set_accent(get_theme(theme_name)["accent"])
        # 页面级主题色（面板底色等）同步刷新
        for page in self._pages.values():
            if hasattr(page, "update_theme_styles"):
                try:
                    page.update_theme_styles()
                except Exception:
                    pass

    def _activate_page(self, key):
        if key in self._pages and key == self._current_key:
            page = self._pages[key]
            if hasattr(page, "_set_visible"):
                page._set_visible(True)

    def _on_page_action(self, action):
        """Quick-action buttons from the dashboard."""
        if action == "scan_all":
            self._navigate("file_visualizer")
            page = self._pages.get("file_visualizer")
            if page: QTimer.singleShot(400, page._scan_all)
        elif action == "smart_clean":
            self._navigate("safe_cleaner")
            page = self._pages.get("safe_cleaner")
            if page: QTimer.singleShot(400, page._analyze)

    def _setup_tray(self):
        self._tray = None
        self._force_quit = False
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        icon = self.windowIcon()
        if icon.isNull():
            return
        tray = QSystemTrayIcon(icon, self)
        menu = QMenu()
        act_show = QAction("显示主窗口", self)
        act_show.triggered.connect(self._restore_from_tray)
        act_exit = QAction("退出", self)
        act_exit.triggered.connect(self._really_quit)
        menu.addAction(act_show)
        menu.addSeparator()
        menu.addAction(act_exit)
        tray.setContextMenu(menu)
        tray.activated.connect(
            lambda reason: self._restore_from_tray()
            if reason == QSystemTrayIcon.DoubleClick else None)
        tray.setToolTip(APP_NAME)
        tray.show()
        self._tray = tray

    def _restore_from_tray(self):
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.activateWindow()

    def _really_quit(self):
        self._force_quit = True
        if self._tray:
            self._tray.hide()
        QApplication.quit()

    def closeEvent(self, event):
        if (self._tray and not self._force_quit
                and load_settings().get("minimize_to_tray", False)):
            event.ignore()
            self.hide()
            self._tray.showMessage(APP_NAME, "已最小化到托盘，双击图标恢复",
                                   QSystemTrayIcon.Information, 2000)

def main():
    app = QApplication(sys.argv)
    font = QFont("Microsoft YaHei", 9)
    app.setFont(font)
    import warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    w = MainWindow(); w.show()
    app.installEventFilter(_ButtonGlow(app))
    QTimer.singleShot(100, lambda: w._navigate("dashboard"))
    sys.exit(app.exec())

if __name__ == "__main__": main()