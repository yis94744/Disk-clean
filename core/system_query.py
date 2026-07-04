"""Detailed system hardware query via WMI"""
import subprocess, json
from PySide6.QtCore import QObject, Signal
from utils.helpers import get_drives, get_drive_info

class SystemQuery(QObject):
    progress = Signal(str)
    finished = Signal(dict)

    def _ps(self, script):
        try:
            r = subprocess.run(
                ["powershell","-NoProfile","-Command","[Console]::OutputEncoding=[Text.Encoding]::UTF8; " + script],
                capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=20,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if r.returncode == 0 and r.stdout.strip():
                return json.loads(r.stdout.strip())
        except Exception:
            pass
        return {}

    def _ps_text(self, script):
        """Run PowerShell, return raw text"""
        try:
            r = subprocess.run(
                ["powershell","-NoProfile","-Command","[Console]::OutputEncoding=[Text.Encoding]::UTF8; " + script],
                capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=20,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return (r.stdout or "").strip()
        except Exception:
            return ""

    def query_all(self):
        info = {}

        # ── OS ──
        self.progress.emit("正在获取操作系统信息...")
        info["os"] = self._ps(
            "$os=Get-CimInstance Win32_OperatingSystem;"
            "@{name=$os.Caption;version=$os.Version;build=$os.BuildNumber;"
            "arch=if([Environment]::Is64BitOperatingSystem){'x64'}else{'x86'};"
            "install_date=$os.InstallDate.ToString('yyyy-MM-dd');"
            "last_boot=$os.LastBootUpTime.ToString('yyyy-MM-dd HH:mm');"
            "registered_user=$os.RegisteredUser}|ConvertTo-Json -Compress"
        )

        # ── CPU ──
        self.progress.emit("正在获取CPU信息...")
        cpu_raw = self._ps_text(
            "$c=Get-CimInstance Win32_Processor|Select -First 1;"
            "$c.Name+'|'+$c.NumberOfCores+'|'+$c.NumberOfLogicalProcessors+'|'+"
            "$c.MaxClockSpeed+'|'+$c.L2CacheSize+'|'+$c.L3CacheSize+'|'+$c.SocketDesignation+'|'+"
            "$c.Manufacturer+'|'+$c.Architecture"
        )
        parts = cpu_raw.split("|") if cpu_raw else []
        info["cpu"] = {
            "name": parts[0].strip() if len(parts) > 0 else "Unknown",
            "cores": int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0,
            "threads": int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0,
            "max_speed": int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0,
            "l2_cache": int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 0,
            "l3_cache": int(parts[5]) if len(parts) > 5 and parts[5].isdigit() else 0,
            "socket": parts[6].strip() if len(parts) > 6 else "",
            "manufacturer": parts[7].strip() if len(parts) > 7 else "",
        }

        # ── Memory (detailed via WMI + psutil) ──
        self.progress.emit("正在获取内存信息...")
        mem = {}
        try:
            import psutil
            vm = psutil.virtual_memory()
            sm = psutil.swap_memory()
            mem = {
                "total": vm.total, "available": vm.available,
                "used": vm.used, "percent": int(vm.percent),
                "swap_total": sm.total, "swap_used": sm.used,
            }
        except ImportError:
            mem_info = self._ps(
                "$os=Get-CimInstance Win32_OperatingSystem;"
                "@{total=$os.TotalVisibleMemorySize*1024;"
                "free=$os.FreePhysicalMemory*1024;"
                "used=($os.TotalVisibleMemorySize-$os.FreePhysicalMemory)*1024;"
                "percent=[math]::Round(($os.TotalVisibleMemorySize-$os.FreePhysicalMemory)/$os.TotalVisibleMemorySize*100)}"
                "|ConvertTo-Json -Compress"
            )
            mem = mem_info if isinstance(mem_info, dict) else {"total": 0, "percent": 0}

        # Get physical memory stick details
        sticks_raw = self._ps_text(
            "$sticks=Get-CimInstance Win32_PhysicalMemory|ForEach-Object{"
            "$_.Capacity.ToString()+'|'+$_.Speed.ToString()+'|'+$_.Manufacturer+'|'+$_.PartNumber+'|'+$_.MemoryType+'|'+$_.DeviceLocator"
            "};$sticks -join ';;'"
        )
        sticks = []
        if sticks_raw:
            for s in sticks_raw.split(";;"):
                p = s.split("|")
                if len(p) >= 4:
                    sticks.append({
                        "capacity": int(p[0]) if p[0].isdigit() else 0,
                        "speed": int(p[1]) if p[1].isdigit() else 0,
                        "manufacturer": p[2].strip(),
                        "part": p[3].strip(),
                        "type": p[4].strip() if len(p) > 4 else "",
                        "slot": p[5].strip() if len(p) > 5 else "",
                    })
        mem["sticks"] = sticks
        info["memory"] = mem

        # ── GPU ──
        self.progress.emit("正在获取显卡信息...")
        gpu_raw = self._ps_text(
            "Get-CimInstance Win32_VideoController|ForEach-Object{"
            "$_.Name+'|'+$_.AdapterRAM+'|'+$_.DriverVersion+'|'+$_.VideoModeDescription+'|'+$_.CurrentRefreshRate"
            "}|Out-String"
        )
        gpus = []
        if gpu_raw:
            for line in gpu_raw.strip().splitlines():
                line = line.strip()
                if not line or line.startswith("---"):
                    continue
                p = line.split("|")
                if len(p) >= 1 and p[0].strip():
                    vram = int(p[1]) if len(p) > 1 and p[1].strip().isdigit() else 0
                    gpus.append({
                        "name": p[0].strip(),
                        "vram": vram,
                        "driver": p[2].strip() if len(p) > 2 else "",
                        "resolution": p[3].strip() if len(p) > 3 else "",
                        "refresh": p[4].strip() if len(p) > 4 else "",
                    })
        info["gpu"] = gpus

        # ── Motherboard ──
        self.progress.emit("正在获取主板信息...")
        mb_raw = self._ps_text(
            "$b=Get-CimInstance Win32_BaseBoard|Select -First 1;"
            "$b.Manufacturer+'|'+$b.Product+'|'+$b.Version"
        )
        mb_parts = mb_raw.split("|") if mb_raw else []
        info["motherboard"] = {
            "manufacturer": mb_parts[0].strip() if len(mb_parts) > 0 else "",
            "product": mb_parts[1].strip() if len(mb_parts) > 1 else "",
            "version": mb_parts[2].strip() if len(mb_parts) > 2 else "",
        }

        # ── BIOS ──
        self.progress.emit("正在获取BIOS信息...")
        bios = self._ps(
            "$b=Get-CimInstance Win32_BIOS;"
            "@{manufacturer=$b.Manufacturer;version=$b.SMBIOSBIOSVersion;"
            "date=$b.ReleaseDate.ToString('yyyy-MM-dd');serial=$b.SerialNumber}"
            "|ConvertTo-Json -Compress"
        )
        if isinstance(bios, dict):
            info["bios"] = bios
        else:
            info["bios"] = {"manufacturer": "", "version": "", "date": "", "serial": ""}

        # ── Disks (detailed) ──
        self.progress.emit("正在获取磁盘信息...")
        disks = []

        # Get physical disk info
        phys_raw = self._ps_text(
            "Get-CimInstance Win32_DiskDrive|ForEach-Object{"
            "$_.Model+'|'+$_.Size+'|'+$_.MediaType+'|'+$_.InterfaceType+'|'+$_.FirmwareRevision+'|'+$_.SerialNumber.Trim()"
            "}|Out-String"
        )
        phys_disks = {}
        if phys_raw:
            for line in phys_raw.strip().splitlines():
                line = line.strip()
                if not line:
                    continue
                p = line.split("|")
                if len(p) >= 3:
                    phys_disks[p[0].strip()] = {
                        "model": p[0].strip(),
                        "size": int(p[1]) if p[1].strip().isdigit() else 0,
                        "media": p[2].strip(),
                        "interface": p[3].strip() if len(p) > 3 else "",
                        "firmware": p[4].strip() if len(p) > 4 else "",
                    }

        # Get logical drive info
        for d in get_drives():
            di = get_drive_info(d)
            if di["total"] > 0:
                label = d.rstrip(":\\") + ":"
                # Try to match with physical disk
                disk_info = {
                    "mount": label,
                    "total": di["total"],
                    "used": di["used"],
                    "free": di["free"],
                    "percent": di["percent"],
                }
                disks.append(disk_info)

        info["disks"] = disks
        info["physical_disks"] = phys_disks

        # ── Network ──
        self.progress.emit("正在获取网络信息...")
        net_raw = self._ps_text(
            "Get-CimInstance Win32_NetworkAdapter|Where-Object{$_.NetEnabled -eq $true}|ForEach-Object{"
            "$_.Name+'|'+$_.AdapterType+'|'+$_.Speed"
            "}|Out-String"
        )
        adapters = []
        if net_raw:
            for line in net_raw.strip().splitlines():
                line = line.strip()
                if not line:
                    continue
                p = line.split("|")
                if len(p) >= 1:
                    speed = int(p[2]) if len(p) > 2 and p[2].strip().isdigit() else 0
                    speed_str = ""
                    if speed >= 1_000_000_000:
                        speed_str = f"{speed/1_000_000_000:.0f} Gbps"
                    elif speed >= 1_000_000:
                        speed_str = f"{speed/1_000_000:.0f} Mbps"
                    adapters.append({
                        "name": p[0].strip(),
                        "type": p[1].strip() if len(p) > 1 else "",
                        "speed": speed_str,
                    })
        info["network"] = adapters

        # ── Audio ──
        audio_raw = self._ps_text(
            "Get-CimInstance Win32_SoundDevice|Where-Object{$_.Status -eq 'OK'}|ForEach-Object{"
            "$_.Name"
            "}|Out-String"
        )
        audio = []
        if audio_raw:
            for line in audio_raw.strip().splitlines():
                line = line.strip()
                if line and not line.startswith("---"):
                    audio.append(line)
        info["audio"] = audio

        self.finished.emit(info)
