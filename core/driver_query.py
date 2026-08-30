# -*- coding: utf-8 -*-
"""驱动检测引擎：枚举系统驱动 → 按厂商/日期给出更新建议 → 映射官方下载页。

说明：各厂商没有公开统一的"最新版本"查询接口，因此"检测更新"采用两步：
1) 按驱动日期给出新旧建议（重要设备超过 2 年建议检查、超过 4 年强烈建议）；
2) 跳转到对应厂商的官方驱动下载页，用户比对版本后下载。
微软通用驱动一律引导到 Windows 更新的"可选更新"（驱动更新通常发布在那里）。
"""
import os
import subprocess
from datetime import datetime
from PySide6.QtCore import QThread, Signal

WINDOWS_UPDATE = "ms-settings:windowsupdate-optionalupdates"

# 厂商/设备名关键词 → 官方驱动页（顺序敏感：先专后泛）
VENDOR_SITES = [
    ("nvidia", "https://www.nvidia.cn/Download/index.aspx?lang=cn"),
    ("advanced micro devices", "https://www.amd.com/zh-hans/support"),
    ("radeon", "https://www.amd.com/zh-hans/support"),
    ("amd", "https://www.amd.com/zh-hans/support"),
    ("intel", "https://www.intel.cn/content/www/cn/zh/download-center/home.html"),
    ("realtek", "https://www.realtek.com/Download"),
    ("qualcomm", "https://www.qualcomm.com/support"),
    ("atheros", "https://www.qualcomm.com/support"),
    ("mediatek", "https://www.mediatek.com/downloads"),
    ("ralink", "https://www.mediatek.com/downloads"),
    ("broadcom", "https://www.broadcom.com/support/download-search"),
    ("synaptics", "https://www.synaptics.com/products/touchpad-driver"),
    ("conexant", "https://www.synaptics.com/products/touchpad-driver"),
    ("asus", "https://www.asus.com.cn/support/"),
    ("micro-star", "https://www.msi.cn/support/download"),
    ("gigabyte", "https://www.gigabyte.cn/Support"),
    ("lenovo", "https://support.lenovo.com.cn/"),
    ("dell", "https://www.dell.com/support/contents/zh-cn"),
    ("hewlett", "https://support.hp.com/cn-zh/drivers"),
    ("samsung", "https://www.samsung.com/cn/support/"),
    ("huawei", "https://consumer.huawei.com/cn/support/"),
]

CATEGORY_NAMES = {
    "DISPLAY": "显示设备",
    "NET": "网络设备",
    "MEDIA": "音频设备",
    "HDC": "存储控制器",
    "SCSIADAPTER": "存储适配器",
    "SYSTEM": "系统设备",
    "USB": "USB 设备",
}

# 参与"新旧建议"的重点类别（显卡/网卡/声卡驱动更新最频繁）
IMPORTANT_CLASSES = {"DISPLAY", "NET", "MEDIA"}

ADVICE_OK = "ok"      # 状态良好
ADVICE_CHECK = "check"   # 建议检查更新（>2 年）
ADVICE_OLD = "old"       # 驱动较旧（>4 年）
ADVICE_WU = "wu"         # 跟随 Windows 更新（微软提供）

ADVICE_LABELS = {
    ADVICE_OK: "状态良好",
    ADVICE_CHECK: "建议检查更新",
    ADVICE_OLD: "驱动较旧，建议更新",
    ADVICE_WU: "跟随 Windows 更新",
}


def site_for(manufacturer, device_name):
    """按厂商/设备名映射官方驱动页；未识别的厂商回退到 Windows 可选更新。"""
    text = f"{manufacturer} {device_name}".lower()
    for key, url in VENDOR_SITES:
        if key in text:
            return url
    return WINDOWS_UPDATE


def advice_for(device_class, provider, date_str):
    """按提供方和驱动日期给出建议。"""
    if "microsoft" in (provider or "").lower():
        return ADVICE_WU
    age_days = age_of(date_str)
    if device_class in IMPORTANT_CLASSES and age_days is not None:
        if age_days > 1460:
            return ADVICE_OLD
        if age_days > 730:
            return ADVICE_CHECK
    return ADVICE_OK


def age_of(date_str):
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return (datetime.now() - d).days
    except (TypeError, ValueError):
        return None



# ---- 噪音设备过滤与硬件分组 ----

# 这些"驱动"不是真实硬件，逐条展示只会产生噪音（默认折叠进"其它驱动"）
def is_noise_device(name, maker):
    n = (name or "").lower()
    m = (maker or "").lower()
    if n.startswith("wan miniport"):
        return True
    if "virtual" in n:
        return True
    if "kernel debug" in n:
        return True
    if "idd" in n and "oray" in m:
        return True
    if "(standard system devices)" in m:
        return True
    return False


# 硬件大类分组定义：(类别码列表, 组名, 图标)
DRIVER_GROUPS = [
    (("DISPLAY",), "显卡驱动", "🖥️"),
    (("MEDIA",), "声卡驱动", "🎵"),
    (("NET",), "网卡驱动", "🌐"),
    (("HDC", "SCSIADAPTER"), "存储控制器驱动", "💾"),
    (("SYSTEM",), "芯片组 / 系统设备", "🧩"),
    (("USB",), "USB 设备", "🔌"),
]

# 组建议聚合优先级：越大的代表组
_ADVICE_RANK = {ADVICE_OK: 0, ADVICE_WU: 1, ADVICE_CHECK: 2, ADVICE_OLD: 3}


def group_advice(advices):
    """组建议 = 组内最需要关注的那条。"""
    if not advices:
        return ADVICE_OK
    return max(advices, key=lambda a: _ADVICE_RANK.get(a, 0))

class DriverScanWorker(QThread):
    """后台枚举 Win32_PnPSignedDriver 中的重点类别驱动。"""
    progress = Signal(str)
    finished_all = Signal(list)

    QUERY_CLASSES = ("DISPLAY", "NET", "MEDIA", "HDC", "SCSIADAPTER", "SYSTEM", "USB")

    def __init__(self):
        super().__init__()
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        self.progress.emit("正在枚举驱动（Win32_PnPSignedDevice），约需 10~30 秒...")
        script = (
            "$cls=@('" + "','".join(self.QUERY_CLASSES) + "');"
            "Get-CimInstance -ClassName Win32_PnPSignedDriver -ErrorAction SilentlyContinue"
            "|Where-Object{$_.DeviceClass -in $cls -and $_.DeviceName}"
            "|Select-Object DeviceName,DeviceClass,DriverVersion,DriverProviderName,Manufacturer,"
            "@{n='Date';e={if($_.DriverDate){$_.DriverDate.ToString('yyyy-MM-dd')}else{''}}},DeviceID"
            "|ConvertTo-Json -Compress"
        )
        data = self._ps_json(script)
        if self._cancel:
            self.finished_all.emit([])
            return
        if isinstance(data, dict):
            data = [data]
        drivers = []
        if isinstance(data, list):
            seen = set()
            for d in data:
                if not isinstance(d, dict):
                    continue
                name = (d.get("DeviceName") or "").strip()
                cls = (d.get("DeviceClass") or "").upper()
                version = (d.get("DriverVersion") or "").strip()
                date = (d.get("Date") or "").strip()
                key = (name, version, date)
                if not name or key in seen:
                    continue
                seen.add(key)
                provider = d.get("DriverProviderName") or ""
                maker = d.get("Manufacturer") or provider
                drivers.append({
                    "name": name,
                    "cls": cls,
                    "version": version or "—",
                    "date": date or "—",
                    "maker": maker,
                    "provider": provider,
                    "site": site_for(maker, name),
                    "advice": advice_for(cls, provider, date),
                })
        # 重要类别在前，其后按日期旧→新
        drivers.sort(key=lambda x: (x["cls"] not in IMPORTANT_CLASSES, x["date"]))
        self.progress.emit("扫描完成")
        self.finished_all.emit(drivers)

    @staticmethod
    def _ps_json(script):
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "[Console]::OutputEncoding=[Text.Encoding]::UTF8; " + script],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=120, creationflags=subprocess.CREATE_NO_WINDOW)
            import json
            out = (r.stdout or "").strip()
            if r.returncode == 0 and out:
                return json.loads(out)
        except Exception:
            pass
        return None


def open_site(url):
    """打开官网/系统页面。"""
    if not url:
        return False
    try:
        os.startfile(url)  # http(s) 走默认浏览器，ms-settings: 走系统设置
        return True
    except Exception:
        return False
