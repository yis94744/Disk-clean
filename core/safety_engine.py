"""
File safety scoring engine
"""
import os
import json
import re
from typing import Optional
from datetime import datetime

from utils.constants import SAFE, SUGGESTED, CAUTION, PROTECTED, SAFETY_LABELS
from utils.helpers import days_since, get_file_access_time, get_file_modify_time

_rules_cache = None

def _load_rules():
    global _rules_cache
    if _rules_cache is not None:
        return _rules_cache
    rules_path = os.path.join(os.path.dirname(__file__), "safety_rules.json")
    try:
        with open(rules_path, "r", encoding="utf-8") as f:
            _rules_cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        _rules_cache = {"safe_patterns": {}, "protected_patterns": {}, "suggested_patterns": {}}
    return _rules_cache


def _expand_env(path):
    result = path
    for var in ["TEMP", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "SYSTEMROOT",
                "WINDIR", "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMDATA", "HOMEPATH"]:
        val = os.environ.get(var, "\\")
        if val:
            result = result.replace("%" + var + "%", val)
    return result


def _match_path_pattern(filepath, patterns):
    filepath_lower = filepath.lower().replace("\\", "/")
    for pattern in patterns:
        expanded = _expand_env(pattern).lower().replace("\\", "/")
        if "*" in expanded:
            regex = re.escape(expanded).replace("\*", ".*")
            if re.search(regex, filepath_lower):
                return True
        elif expanded in filepath_lower:
            return True
    return False


def _match_name_pattern(filename, patterns):
    filename_lower = filename.lower()
    for pattern in patterns:
        if pattern.startswith("~") and pattern.endswith("*"):
            prefix = pattern.replace("*", "\\")
            if filename_lower.startswith(prefix):
                return True
        elif pattern.lower() == filename_lower:
            return True
    return False


def _match_ext_pattern(ext, patterns):
    ext_lower = ext.lower()
    return ext_lower in [p.lower() for p in patterns]


def _check_digital_signature(filepath):
    """Stub - digital signature check disabled for performance"""
    return False, False



def evaluate_fast(filepath, size=0, ext=""):
    """Fast safety evaluation - no PowerShell, no digital signature checks"""
    rules = _load_rules()
    filename = os.path.basename(filepath)

    score = 50.0

    # Quick path checks
    safe_paths = rules.get("safe_patterns", {}).get("paths", [])
    protected_paths = rules.get("protected_patterns", {}).get("paths", [])
    suggested_paths = rules.get("suggested_patterns", {}).get("paths", [])

    if _match_path_pattern(filepath, safe_paths):
        score -= 30
    elif _match_path_pattern(filepath, protected_paths):
        score += 30
    elif _match_path_pattern(filepath, suggested_paths):
        score -= 15

    # Extension checks
    safe_exts = rules.get("safe_patterns", {}).get("extensions", [])
    protected_exts = rules.get("protected_patterns", {}).get("extensions", [])
    suggested_exts = rules.get("suggested_patterns", {}).get("extensions", [])

    if _match_ext_pattern(ext, safe_exts):
        score -= 20
    elif _match_ext_pattern(ext, protected_exts):
        score += 20
    elif _match_ext_pattern(ext, suggested_exts):
        score -= 10

    # Name checks
    safe_names = rules.get("safe_patterns", {}).get("names", [])
    protected_names = rules.get("protected_patterns", {}).get("names", [])

    if _match_name_pattern(filename, safe_names):
        score -= 15
    if _match_name_pattern(filename, protected_names):
        score += 25

    # Temp file check
    if filename.startswith("~$"):
        score -= 25

    # Recycle bin check
    if "RECYCLE.BIN" in filepath.upper():
        score = 0

    # Age-based scoring
    if size > 0:
        mtime = os.path.getmtime(filepath) if os.path.exists(filepath) else 0
        days = days_since(mtime)
        if days > 180:
            score -= 15
        elif days > 90:
            score -= 10
        elif days > 30:
            score -= 5

    if score <= 20:
        level = SAFE
    elif score <= 40:
        level = SUGGESTED
    elif score <= 65:
        level = CAUTION
    else:
        level = PROTECTED

    label, color, _ = SAFETY_LABELS[level]
    return {"level": level, "label": label, "color": color, "score": score, "is_safe_to_delete": level == SAFE}


def evaluate_file(filepath, size=0, file_count=0):
    rules = _load_rules()
    filename = os.path.basename(filepath)
    ext = os.path.splitext(filename)[1]
    is_dir = os.path.isdir(filepath)

    score = 50.0
    reasons = []

    safe_paths = rules.get("safe_patterns", {}).get("paths", [])
    protected_paths = rules.get("protected_patterns", {}).get("paths", [])
    suggested_paths = rules.get("suggested_patterns", {}).get("paths", [])

    if _match_path_pattern(filepath, safe_paths):
        score -= 30
        reasons.append("safe path")
    elif _match_path_pattern(filepath, protected_paths):
        score += 30
        reasons.append("protected path")
    elif _match_path_pattern(filepath, suggested_paths):
        score -= 15
        reasons.append("suggested path")

    safe_exts = rules.get("safe_patterns", {}).get("extensions", [])
    protected_exts = rules.get("protected_patterns", {}).get("extensions", [])
    suggested_exts = rules.get("suggested_patterns", {}).get("extensions", [])

    if _match_ext_pattern(ext, safe_exts):
        score -= 20
        reasons.append(f"safe ext ({ext})")
    elif _match_ext_pattern(ext, protected_exts):
        score += 20
        reasons.append(f"protected ext ({ext})")
    elif _match_ext_pattern(ext, suggested_exts):
        score -= 10
        reasons.append(f"suggested ext ({ext})")

    safe_names = rules.get("safe_patterns", {}).get("names", [])
    protected_names = rules.get("protected_patterns", {}).get("names", [])

    if _match_name_pattern(filename, safe_names):
        score -= 15
        reasons.append("safe name")
    if _match_name_pattern(filename, protected_names):
        score += 25
        reasons.append("protected name")

    if ext in [".exe", ".dll", ".sys"]:
        has_sig, is_ms = _check_digital_signature(filepath)
        if is_ms:
            score += 20
            reasons.append("Microsoft signed")
        elif has_sig:
            score += 5
            reasons.append("digitally signed")
        elif not is_dir:
            score -= 5
            reasons.append("unsigned executable")

    if not is_dir:
        access_time = get_file_access_time(filepath)
        days = days_since(access_time)
        if days > 180:
            score -= 15
            reasons.append(f"unused {days}d")
        elif days > 90:
            score -= 10
            reasons.append(f"unused {days}d")
        elif days > 30:
            score -= 5
            reasons.append(f"unused {days}d")

    if size > 100 * 1024 * 1024:
        modify_time = get_file_modify_time(filepath)
        days_mod = days_since(modify_time)
        if days_mod > 90:
            score -= 10
            reasons.append(f"large old file ({size // (1024*1024)}MB)")

    if os.path.exists(filepath + ".bak") or os.path.exists(filepath + ".old"):
        score -= 5
        reasons.append("has backup")

    if filename.startswith("~$"):
        score -= 25
        reasons.append("temp file (~$)")

    if "RECYCLE.BIN" in filepath.upper():
        score = 0
        reasons = ["recycle bin"]

    if score <= 20:
        level = SAFE
    elif score <= 40:
        level = SUGGESTED
    elif score <= 65:
        level = CAUTION
    else:
        level = PROTECTED

    label, color, _ = SAFETY_LABELS[level]

    return {
        "level": level,
        "label": label,
        "color": color,
        "score": score,
        "reasons": reasons,
        "is_safe_to_delete": level == SAFE,
    }


def evaluate_directory(dirpath):
    return evaluate_file(dirpath, 0, 0)


_eval_cache = {}

def evaluate_with_cache(filepath, size=0):
    mtime = get_file_modify_time(filepath)
    cache_key = filepath + ":" + str(mtime) + ":" + str(size)
    if cache_key in _eval_cache:
        return _eval_cache[cache_key]
    result = evaluate_fast(filepath, size, os.path.splitext(os.path.basename(filepath))[1])
    if len(_eval_cache) > 10000:
        _eval_cache.clear()
    _eval_cache[cache_key] = result
    return result


def clear_eval_cache():
    _eval_cache.clear()
