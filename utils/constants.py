"""
Shared constants for Disk Cleaner Pro
"""
import os

APP_NAME = "Disk Cleaner Pro"
APP_VERSION = "1.0.0"
ORG_NAME = "DiskCleaner"

SAFE = 0
SUGGESTED = 1
CAUTION = 2
PROTECTED = 3

SAFETY_LABELS = {
    SAFE: ("安全", "#4CAF50", "green"),
    SUGGESTED: ("建议清理", "#FF9800", "yellow"),
    CAUTION: ("谨慎", "#FF5722", "orange"),
    PROTECTED: ("受保护", "#F44336", "red"),
}

SAFETY_STYLESHEET = {
    SAFE: "background-color: #4CAF50; color: white; border-radius: 4px; padding: 2px 8px;",
    SUGGESTED: "background-color: #FF9800; color: white; border-radius: 4px; padding: 2px 8px;",
    CAUTION: "background-color: #FF5722; color: white; border-radius: 4px; padding: 2px 8px;",
    PROTECTED: "background-color: #F44336; color: white; border-radius: 4px; padding: 2px 8px;",
}

SYSTEM_PATHS = [
    os.environ.get("SystemRoot", "C:/Windows") + "/System32",
    os.environ.get("SystemRoot", "C:/Windows") + "/SysWOW64",
    os.environ.get("SystemRoot", "C:/Windows") + "/Boot",
    os.environ.get("SystemRoot", "C:/Windows") + "/WinSxS",
]

TEMP_PATHS = [
    os.environ.get("TEMP", ""),
    os.environ.get("SystemRoot", "C:/Windows") + "/Temp",
    os.environ.get("SystemRoot", "C:/Windows") + "/Prefetch",
    os.environ.get("SystemRoot", "C:/Windows") + "/SoftwareDistribution/Download",
]

SCAN_CACHE_DB = "scan_cache.db"
CACHE_TTL_SECONDS = 3600
PROCESS_REFRESH_MS = 3000
THEME_LIGHT = "light"
THEME_DARK = "dark"
