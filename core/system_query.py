"""Detailed system hardware query via WMI"""
import subprocess, json
from PySide6.QtCore import QObject, Signal
from utils.helpers import get_drives, get_drive_info

class SystemQuery(QObject):
    progress = Signal(str)
    progress_value = Signal(int)
    finished = Signal(dict)

    STEPS = 10  # total query phases, for progress bar reporting

    def __init__(self, parent=None):
        super().__init__(parent)
        self._step_idx = 0

    def _begin_step(self, msg):
        self._step_idx += 1
        self.progress.emit(msg)
        self.progress_value.emit(min(100, int(self._step_idx * 100 / self.STEPS)))

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

    def _query_disk_health(self):
        """Physical disk health & lifespan via Get-PhysicalDisk + StorageReliabilityCounter."""
        script = (
            "$out=Get-PhysicalDisk|ForEach-Object{$d=$_;$c=$null;"
            "try{$c=$d|Get-StorageReliabilityCounter -ErrorAction SilentlyContinue}catch{};"
            "[PSCustomObject]@{model=[string]$d.FriendlyName;serial=[string]$d.SerialNumber;"
            "media=[string]$d.MediaType;bus=[string]$d.BusType;health=[string]$d.HealthStatus;"
            "wear=$c.Wear;temp=$c.Temperature;hours=$c.PowerOnHours;read_errors=$c.ReadErrorsTotal}}"
            "|ConvertTo-Json -Compress;$out"
        )
        data = self._ps(script)
        if not data:
            return []
        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list):
            return []

        def _num(v):
            try:
                return int(v) if v is not None and str(v) != "" else None
            except (TypeError, ValueError):
                return None

        disks = []
        for d in data:
            if not isinstance(d, dict):
                continue
            disks.append({
                "model": d.get("model", "") or "",
                "media": d.get("media", "") or "Unspecified",
                "bus": d.get("bus", "") or "",
                "health": d.get("health", "") or "Unknown",
                "wear": _num(d.get("wear")),
                "temperature": _num(d.get("temp")),
                "power_on_hours": _num(d.get("hours")),
                "read_errors": _num(d.get("read_errors")),
            })
        return disks

    def _query_nvidia_temps(self):
        """NVIDIA GPU temperature/load/VRAM via nvidia-smi (if driver installed)."""
        out = []
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,temperature.gpu,utilization.gpu,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=8, creationflags=subprocess.CREATE_NO_WINDOW)
            if r.returncode == 0 and r.stdout.strip():
                for line in r.stdout.strip().splitlines():
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) < 2:
                        continue
                    try:
                        t = float(parts[1])
                    except ValueError:
                        continue
                    load = ""
                    if len(parts) > 2 and parts[2]:
                        load = parts[2].rstrip("%")
                    mem_bytes = 0
                    if len(parts) > 3 and parts[3].replace(".", "").isdigit():
                        try:
                            mem_bytes = int(float(parts[3]) * 1048576)  # MiB -> bytes
                        except ValueError:
                            mem_bytes = 0
                    out.append({"name": parts[0] or "NVIDIA GPU", "temp": t,
                                "load": load, "mem_bytes": mem_bytes})
        except Exception:
            pass
        return out

    def _query_monitor(self, gpu_names=None):
        """CPU/GPU temperatures, fans and CPU load.

        Priority: LibreHardwareMonitor/OpenHardwareMonitor WMI (best, needs the
        app running) -> nvidia-smi (NVIDIA GPUs) -> ACPI thermal zone (CPU only,
        often needs admin). Returns None fields gracefully when unavailable.
        """
        result = {
            "cpu_temp": None, "cpu_temp_source": "", "cpu_load": None,
            "gpus": [], "fans": [], "sensor_source": "",
        }
        try:
            import psutil
            result["cpu_load"] = int(psutil.cpu_percent(interval=0.3))
        except Exception:
            pass

        # 1) LibreHardwareMonitor / OpenHardwareMonitor sensors
        sensors = self._ps(
            "$s=Get-CimInstance -Namespace root/LibreHardwareMonitor -ClassName Sensor "
            "-ErrorAction SilentlyContinue;"
            "if(-not $s){$s=Get-CimInstance -Namespace root/OpenHardwareMonitor "
            "-ClassName Sensor -ErrorAction SilentlyContinue};"
            "if($s){$s|Select-Object Name,SensorType,Value|ConvertTo-Json -Compress}else{''}"
        )
        if isinstance(sensors, dict):
            sensors = [sensors]
        parsed = []
        if isinstance(sensors, list):
            for s in sensors:
                try:
                    parsed.append((str(s.get("Name", "")), str(s.get("SensorType", "")),
                                   float(s.get("Value"))))
                except (TypeError, ValueError):
                    continue

        temps = [(n, v) for n, st, v in parsed if st == "Temperature"]
        if temps:
            result["sensor_source"] = "LibreHardwareMonitor"
            for pref in ("cpu package", "tctl/tdie", "core (tctl", "cpu (tctl", "cpu"):
                for n, v in temps:
                    if n.lower().startswith(pref):
                        result["cpu_temp"] = v
                        result["cpu_temp_source"] = "LibreHardwareMonitor"
                        break
                if result["cpu_temp"] is not None:
                    break
        lhm_gpu_temps = [v for n, v in temps
                         if n.lower().startswith("gpu")
                         and ("core" in n.lower() or "chip" in n.lower() or n.lower() == "gpu")]

        # 2) GPU list from Win32_VideoController, temps from nvidia-smi then LHM
        gpus = [{"name": n or "GPU", "temp": None, "load": "", "source": "", "mem_bytes": 0}
                for n in (gpu_names or [])]
        for ng in self._query_nvidia_temps():
            target = None
            for g in gpus:
                if g["temp"] is None and "nvidia" in g["name"].lower():
                    target = g
                    break
            if target is None:
                target = {"name": ng["name"], "temp": None, "load": "", "source": "", "mem_bytes": 0}
                gpus.append(target)
            target["temp"] = ng["temp"]
            target["load"] = ng.get("load", "")
            target["mem_bytes"] = ng.get("mem_bytes", 0)
            target["source"] = "nvidia-smi"
        gi = 0
        for g in gpus:
            if g["temp"] is None and gi < len(lhm_gpu_temps):
                g["temp"] = lhm_gpu_temps[gi]
                g["source"] = result["sensor_source"]
                gi += 1
        if not gpus and lhm_gpu_temps:
            for t in lhm_gpu_temps:
                result["gpus"].append({"name": "GPU", "temp": t, "load": "",
                                       "source": result["sensor_source"]})
        result["gpus"] = gpus

        # 3) CPU fallback: ACPI thermal zone (K*10 units), often needs admin
        if result["cpu_temp"] is None:
            for src, cls in (("ACPI 热区", "MSAcpi_ThermalZoneTemperature"),
                             ("系统热区", "Win32_PerfFormattedData_Counters_ThermalZoneInformation")):
                prop = "CurrentTemperature" if cls == "MSAcpi_ThermalZoneTemperature" else "Temperature"
                ns = "-Namespace root/wmi " if cls == "MSAcpi_ThermalZoneTemperature" else ""
                raw = self._ps(
                    "$t=Get-CimInstance " + ns + "-ClassName " + cls + " "
                    "-ErrorAction SilentlyContinue|Where-Object{$_." + prop + " -gt 0};"
                    "if($t){[math]::Round((($t|Measure-Object -Property " + prop +
                    " -Average).Average)/10-273.15,1)|ConvertTo-Json -Compress}else{''}"
                )
                try:
                    c = float(raw)
                    if -50 < c < 120:
                        result["cpu_temp"] = c
                        result["cpu_temp_source"] = src
                        break
                except (TypeError, ValueError):
                    continue

        # Fans (only available from hardware monitor sensors)
        result["fans"] = [{"name": n, "rpm": int(v)}
                          for n, st, v in parsed if st == "Fan" and v > 0][:6]
        return result

    def query_all(self):
        info = {}

        # ── OS ──
        self._begin_step("正在获取操作系统信息...")
        info["os"] = self._ps(
            "$os=Get-CimInstance Win32_OperatingSystem;"
            "@{name=$os.Caption;version=$os.Version;build=$os.BuildNumber;"
            "arch=if([Environment]::Is64BitOperatingSystem){'x64'}else{'x86'};"
            "install_date=$os.InstallDate.ToString('yyyy-MM-dd');"
            "last_boot=$os.LastBootUpTime.ToString('yyyy-MM-dd HH:mm');"
            "registered_user=$os.RegisteredUser}|ConvertTo-Json -Compress"
        )

        # ── CPU ──
        self._begin_step("正在获取CPU信息...")
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
        self._begin_step("正在获取内存信息...")
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
        self._begin_step("正在获取显卡信息...")
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
        self._begin_step("正在获取主板信息...")
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
        self._begin_step("正在获取BIOS信息...")
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
        self._begin_step("正在获取磁盘信息...")
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

        # ── 硬盘健康 / 寿命 ──
        self._begin_step("正在获取硬盘健康信息...")
        info["disk_health"] = self._query_disk_health()

        # ── 温度监控 ──
        self._begin_step("正在读取温度传感器...")
        mon = self._query_monitor([g.get("name", "") for g in info.get("gpu", [])])
        info["monitor"] = mon
        # AdapterRAM 是 32 位，>4GB 显存读数错误，用 nvidia-smi 的显存修正
        for g in info.get("gpu", []):
            gl = (g.get("name") or "").lower()
            if g.get("vram", 0) >= 4 * 1024**3 or "nvidia" not in gl:
                continue
            for ng in mon.get("gpus", []):
                mb = ng.get("mem_bytes") or 0
                if mb and "nvidia" in (ng.get("name") or "").lower():
                    g["vram"] = mb
                    break

        # ── Network ──
        self._begin_step("正在获取网络信息...")
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
