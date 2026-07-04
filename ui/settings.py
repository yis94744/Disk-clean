"""Settings - functional settings with live theme switching + real-time save"""
import json
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
    QComboBox, QCheckBox, QPushButton, QLineEdit, QMessageBox)
from PySide6.QtCore import Signal
from PySide6.QtGui import QFont, QIntValidator
from utils.themes import THEMES, load_settings, SETTINGS_FILE

DEFAULTS = {'scan_limit':50000,'theme':'deep','minimize_to_tray':False,'auto_start':False,'confirm_high_risk':True,'show_system_files':False,'expert_mode':False,'scan_min_size_mb':1,'max_results':500,'language':'zh'}

class SettingsPage(QWidget):
    status_message = Signal(str)
    theme_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings = self._load()
        self._setup_ui()

    def _load(self):
        s = load_settings()
        for k, v in DEFAULTS.items():
            if k not in s: s[k] = v
        return s

    def _save(self):
        try:
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, indent=2)
        except Exception: pass

    def _setup_ui(self):
        l = QVBoxLayout(self); l.setContentsMargins(20, 20, 20, 20); l.setSpacing(14)
        t = QLabel('\u8bbe\u7f6e')
        t.setFont(QFont('Microsoft YaHei', 18, QFont.Bold))
        t.setStyleSheet('color: #e0e0e0;'); l.addWidget(t)

        c1 = QFrame(); c1.setObjectName('card'); cl1 = QVBoxLayout(c1)
        cl1.setContentsMargins(14, 10, 14, 10); cl1.setSpacing(10)
        h1 = QLabel('\u5916\u89c2')
        h1.setFont(QFont('Microsoft YaHei', 13, QFont.Bold))
        h1.setStyleSheet('color: #58a6ff;background:transparent;'); cl1.addWidget(h1)

        r1 = QHBoxLayout(); r1.addWidget(QLabel('\u4e3b\u9898:'))
        self.tc = QComboBox()
        for k, t in THEMES.items():
            self.tc.addItem(t.get('name', k), k)
        cur = self._settings.get('theme', 'deep')
        self.tc.setCurrentText(THEMES.get(cur, {}).get('name', '\u6df1\u591c'))
        self.tc.currentIndexChanged.connect(self._on_theme_change)
        r1.addWidget(self.tc); r1.addStretch(); cl1.addLayout(r1)

        r2 = QHBoxLayout(); r2.addWidget(QLabel('\u8bed\u8a00:'))
        self.lc = QComboBox(); self.lc.addItems(['\u4e2d\u6587', 'English'])
        self.lc.setCurrentText('\u4e2d\u6587' if self._settings.get('language') == 'zh' else 'English')
        self.lc.currentTextChanged.connect(lambda t: self._on_setting_change('language', 'zh' if t == '\u4e2d\u6587' else 'en'))
        r2.addWidget(self.lc); r2.addStretch(); cl1.addLayout(r2)
        ln = QLabel('  \u26a0 \u8bed\u8a00\u5207\u6362\u9700\u91cd\u542f\u5e94\u7528')
        ln.setStyleSheet('color:#FF9800;font-size:10px;background:transparent;'); cl1.addWidget(ln); l.addWidget(c1)

        c2 = QFrame(); c2.setObjectName('card'); cl2 = QVBoxLayout(c2)
        cl2.setContentsMargins(14, 10, 14, 10); cl2.setSpacing(8)
        h2 = QLabel('\u626b\u63cf')
        h2.setFont(QFont('Microsoft YaHei', 13, QFont.Bold))
        h2.setStyleSheet('color: #58a6ff;background:transparent;'); cl2.addWidget(h2)

        self.cb_expert = QCheckBox('\u4e13\u5bb6\u6a21\u5f0f (\u663e\u793a\u6240\u6709\u6587\u4ef6)')
        self.cb_expert.setChecked(self._settings.get('expert_mode', False))
        self.cb_expert.toggled.connect(lambda v: self._on_setting_change('expert_mode', v)); cl2.addWidget(self.cb_expert)

        self.cb_sys = QCheckBox('\u663e\u793a\u7cfb\u7edf\u6587\u4ef6 (\u5305\u542bWindows\u76ee\u5f55)')
        self.cb_sys.setChecked(self._settings.get('show_system_files', False))
        self.cb_sys.toggled.connect(lambda v: self._on_setting_change('show_system_files', v)); cl2.addWidget(self.cb_sys)

        self.cb_confirm = QCheckBox('\u786e\u8ba4\u9ad8\u98ce\u9669\u64cd\u4f5c (\u9632\u6b62\u8bef\u5220)')
        self.cb_confirm.setChecked(self._settings.get('confirm_high_risk', True))
        self.cb_confirm.toggled.connect(lambda v: self._on_setting_change('confirm_high_risk', v)); cl2.addWidget(self.cb_confirm)

        r3 = QHBoxLayout(); r3.addWidget(QLabel('\u6700\u5c0f\u626b\u63cf\u6587\u4ef6(MB):'))
        self.sb1 = QLineEdit()
        self.sb1.setValidator(QIntValidator(1, 10000))
        self.sb1.setText(str(self._settings.get('scan_min_size_mb', 1)))
        self.sb1.setMaximumWidth(80)
        self.sb1.textChanged.connect(lambda t: self._on_text_change('scan_min_size_mb', t, 1))
        r3.addWidget(self.sb1); r3.addStretch(); cl2.addLayout(r3)

        r4 = QHBoxLayout(); r4.addWidget(QLabel('\u6700\u5927\u663e\u793a\u6587\u4ef6\u6570:'))
        self.sb2 = QLineEdit()
        self.sb2.setValidator(QIntValidator(50, 5000))
        self.sb2.setText(str(self._settings.get('max_results', 500)))
        self.sb2.setMaximumWidth(80)
        self.sb2.textChanged.connect(lambda t: self._on_text_change('max_results', t, 500))
        r4.addWidget(self.sb2); r4.addStretch(); cl2.addLayout(r4); l.addWidget(c2)

        c3 = QFrame(); c3.setObjectName('card'); cl3 = QVBoxLayout(c3)
        cl3.setContentsMargins(14, 10, 14, 10); cl3.setSpacing(6)
        h3 = QLabel('\u5173\u4e8e')
        h3.setFont(QFont('Microsoft YaHei', 13, QFont.Bold))
        h3.setStyleSheet('color: #58a6ff;background:transparent;'); cl3.addWidget(h3)
        cl3.addWidget(QLabel('Disk Cleaner Pro v2.0'))
        cl3.addWidget(QLabel('\u529f\u80fd\u5f3a\u5927\u7684\u78c1\u76d8\u6e05\u7406\u5de5\u5177'))
        cl3.addWidget(QLabel('\u6280\u672f: \u591a\u7ebf\u7a0b \u2022 \u5b89\u5168 \u2022 \u9ad8\u6027\u80fd \u2022 \u6613\u7528'))
        l.addWidget(c3)

        br = QHBoxLayout()
        rb = QPushButton('\u6062\u590d\u9ed8\u8ba4'); rb.clicked.connect(self._do_reset)
        br.addWidget(rb); br.addStretch(); l.addLayout(br); l.addStretch()

    def _on_setting_change(self, key, value):
        self._settings[key] = value
        self._save()
        self.status_message.emit(f'\u8bbe\u7f6e\u5df2\u4fdd\u5b58: {key}={value}')

    def _on_text_change(self, key, text, default_val):
        try:
            val = int(text) if text else default_val
            self._settings[key] = val
            self._save()
        except ValueError:
            pass

    def _on_theme_change(self, idx):
        key = self.tc.currentData()
        if key:
            self._settings['theme'] = key
            self.theme_changed.emit(key)
            self._save()
            self.status_message.emit(f'\u4e3b\u9898\u5df2\u5207\u6362: {THEMES.get(key,{}).get("name",key)}')

    def _do_reset(self):
        self._settings = dict(DEFAULTS)
        self._save()
        self.tc.setCurrentText(THEMES['deep']['name'])
        self.lc.setCurrentText('\u4e2d\u6587')
        self.cb_expert.setChecked(False)
        self.cb_sys.setChecked(False)
        self.cb_confirm.setChecked(True)
        self.sb1.setText('1'); self.sb2.setText('500'); self.sb_scan_limit.setText('50000')
        self.theme_changed.emit('deep')
        QMessageBox.information(self, '\u8bbe\u7f6e', '\u5df2\u6062\u590d\u9ed8\u8ba4\u8bbe\u7f6e')
        self.status_message.emit('\u8bbe\u7f6e\u5df2\u91cd\u7f6e')
