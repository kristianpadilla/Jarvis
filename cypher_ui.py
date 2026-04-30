from flask import Flask, send_from_directory, request as flask_request
from flask_socketio import SocketIO
import threading
import os
import json
import psutil
import subprocess
import re
import time as _time

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'cypher_secret_dev')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ui_state = {
    "status": "standby",
    "user_text": "",
    "cypher_text": "",
    "mode": "home",
}

def set_ui_state(status=None, user_text=None, cypher_text=None, mode=None):
    if status is not None:
        ui_state["status"] = status
    if user_text is not None:
        ui_state["user_text"] = user_text
    if cypher_text is not None:
        ui_state["cypher_text"] = cypher_text
    if mode is not None:
        ui_state["mode"] = mode
    socketio.emit('state_update', ui_state)

# ─── ROUTES ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "cypher.html")

@app.route("/model")
def model():
    return send_from_directory(BASE_DIR, "Cypher_.vrm")

@app.route("/<path:filename>.js")
def serve_js(filename):
    return send_from_directory(BASE_DIR, filename + ".js")

@app.route("/state")
def state():
    return ui_state

# ─── LEGACY STATS (kept for backward compat) ──────────────────────────────────
stats_cache = {"cpu": 0, "ram": 0, "gpu": 0}

def sample_stats():
    global stats_cache
    while True:
        try:
            cpu = round(psutil.cpu_percent(interval=1))
            ram = round(psutil.virtual_memory().percent)
            gpu = 0
            try:
                result = subprocess.run(
                    ['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'],
                    capture_output=True, text=True, timeout=2
                )
                gpu = round(float(result.stdout.strip()))
            except:
                pass
            stats_cache = {"cpu": cpu, "ram": ram, "gpu": gpu}
        except Exception as e:
            print(f"Stats sample error: {e}")
        _time.sleep(1)

@app.route("/stats")
def stats():
    return stats_cache

# ─── SYSINFO CACHE ────────────────────────────────────────────────────────────
# We cache sysinfo so multiple widget polls don't hammer nvidia-smi
_sysinfo_cache = {}
_sysinfo_ts = 0
_SYSINFO_TTL = 2.0

def _get_cpu_name():
    try:
        result = subprocess.run(
            ['wmic', 'cpu', 'get', 'name', '/value'],
            capture_output=True, text=True, timeout=3
        )
        for line in result.stdout.splitlines():
            if 'Name=' in line:
                name = line.split('=')[1].strip()
                name = name.replace('Intel(R) Core(TM) ', '').replace('AMD ', '')
                name = name.replace('(R)', '').replace('(TM)', '').replace('  ', ' ')
                return name.strip()
    except:
        pass
    return "CPU"

def _get_cpu_temp():
    """Try multiple methods to get CPU temp on Windows."""
    # Method 1: OpenHardwareMonitor WMI (if running)
    try:
        import wmi
        w = wmi.WMI(namespace="root\OpenHardwareMonitor")
        sensors = w.Sensor()
        for sensor in sensors:
            if sensor.SensorType == 'Temperature' and 'CPU' in sensor.Name:
                return round(float(sensor.Value))
    except:
        pass
    # Method 2: LibreHardwareMonitor WMI (if running)
    try:
        import wmi
        w = wmi.WMI(namespace="root\LibreHardwareMonitor")
        sensors = w.Sensor()
        for sensor in sensors:
            if sensor.SensorType == 'Temperature' and 'CPU' in sensor.Name:
                return round(float(sensor.Value))
    except:
        pass
    return None

def _get_gpu_data():
    """Get GPU stats via nvidia-smi."""
    try:
        result = subprocess.run(
            ['nvidia-smi',
             '--query-gpu=utilization.gpu,temperature.gpu,memory.used,memory.total,name,fan.speed,clocks.current.graphics',
             '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0:
            parts = [p.strip() for p in result.stdout.strip().split(',')]
            return {
                "gpu_percent":   int(parts[0]),
                "gpu_temp":      int(parts[1]),
                "gpu_vram_used": round(int(parts[2]) / 1024, 1),
                "gpu_vram_total":round(int(parts[3]) / 1024, 1),
                "gpu_name":      parts[4].replace('NVIDIA ', '').replace('GeForce ', '').strip(),
                "gpu_fan":       int(parts[5]) if parts[5] != '[N/A]' else 0,
                "gpu_clock_mhz": int(parts[6]) if parts[6] != '[N/A]' else 0,
            }
    except:
        pass
    return {
        "gpu_percent": 0, "gpu_temp": 0,
        "gpu_vram_used": 0, "gpu_vram_total": 0,
        "gpu_name": "GPU", "gpu_fan": 0, "gpu_clock_mhz": 0
    }

def _get_disk_data():
    """Disk usage for C: and D: plus live I/O rates."""
    disks = []
    for drive in ['C:\\', 'D:\\']:
        try:
            usage = psutil.disk_usage(drive)
            disks.append({
                "drive": drive[0],
                "percent": round(usage.percent),
                "used_gb": round(usage.used / (1024**3), 1),
                "total_gb": round(usage.total / (1024**3), 1),
            })
        except:
            pass
    # Disk I/O rates
    try:
        io1 = psutil.disk_io_counters()
        _time.sleep(0.3)
        io2 = psutil.disk_io_counters()
        read_mbs  = round((io2.read_bytes  - io1.read_bytes)  / 0.3 / (1024**2), 1)
        write_mbs = round((io2.write_bytes - io1.write_bytes) / 0.3 / (1024**2), 1)
    except:
        read_mbs = 0
        write_mbs = 0
    return {"disks": disks, "read_mbs": max(0, read_mbs), "write_mbs": max(0, write_mbs)}

# CPU name is static — cache it once at startup
_cpu_name_cache = None

@app.route("/sysinfo")
def sysinfo():
    global _sysinfo_cache, _sysinfo_ts, _cpu_name_cache
    now = _time.time()
    if now - _sysinfo_ts < _SYSINFO_TTL and _sysinfo_cache:
        return _sysinfo_cache

    if _cpu_name_cache is None:
        _cpu_name_cache = _get_cpu_name()

    cpu_percent = round(psutil.cpu_percent(interval=0.2))
    cpu_count   = psutil.cpu_count(logical=False) or 0
    cpu_threads = psutil.cpu_count(logical=True) or 0
    cpu_temp    = _get_cpu_temp()

    ram = psutil.virtual_memory()
    ram_percent  = round(ram.percent)
    ram_used_gb  = round(ram.used / (1024**3), 1)
    ram_total_gb = round(ram.total / (1024**3), 1)

    uptime_secs = int(_time.time() - psutil.boot_time())
    uptime_h = uptime_secs // 3600
    uptime_m = (uptime_secs % 3600) // 60
    uptime_str = f"{uptime_h}h {uptime_m}m"

    gpu = _get_gpu_data()
    disk = _get_disk_data()

    _sysinfo_cache = {
        "cpu_percent":   cpu_percent,
        "cpu_name":      _cpu_name_cache,
        "cpu_cores":     cpu_count,
        "cpu_threads":   cpu_threads,
        "cpu_temp":      cpu_temp,
        "ram_percent":   ram_percent,
        "ram_used_gb":   ram_used_gb,
        "ram_total_gb":  ram_total_gb,
        "uptime":        uptime_str,
        "gpu_percent":   gpu["gpu_percent"],
        "gpu_temp":      gpu["gpu_temp"],
        "gpu_vram_used": gpu["gpu_vram_used"],
        "gpu_vram_total":gpu["gpu_vram_total"],
        "gpu_name":      gpu["gpu_name"],
        "gpu_fan":       gpu["gpu_fan"],
        "gpu_clock_mhz": gpu["gpu_clock_mhz"],
        "disks":         disk["disks"],
        "disk_read_mbs": disk["read_mbs"],
        "disk_write_mbs":disk["write_mbs"],
    }
    _sysinfo_ts = now
    return _sysinfo_cache

# ─── NETWORK ─────────────────────────────────────────────────────────────────
_last_net = None
_last_net_time = None
_session_sent = 0
_session_recv = 0
_session_start_sent = None
_session_start_recv = None

@app.route("/network")
def network():
    global _last_net, _last_net_time, _session_sent, _session_recv
    global _session_start_sent, _session_start_recv
    try:
        now = _time.time()
        counters = psutil.net_io_counters()

        # Init session baseline on first call
        if _session_start_sent is None:
            _session_start_sent = counters.bytes_sent
            _session_start_recv = counters.bytes_recv

        # Live rates
        if _last_net and _last_net_time:
            elapsed  = now - _last_net_time
            upload   = round((counters.bytes_sent - _last_net.bytes_sent) / elapsed / (1024**2), 2)
            download = round((counters.bytes_recv - _last_net.bytes_recv) / elapsed / (1024**2), 2)
        else:
            upload = 0.0
            download = 0.0

        _last_net = counters
        _last_net_time = now

        # Session totals in MB
        session_up_mb   = round((counters.bytes_sent - _session_start_sent) / (1024**2), 1)
        session_down_mb = round((counters.bytes_recv - _session_start_recv) / (1024**2), 1)

        # Format session totals nicely (GB if over 1024MB)
        def fmt_total(mb):
            if mb >= 1024:
                return f"{round(mb/1024, 2)} GB"
            return f"{mb} MB"

        # Ping
        ping_ms = None
        try:
            result = subprocess.run(
                ['ping', '-n', '1', '8.8.8.8'],
                capture_output=True, text=True, timeout=3
            )
            for line in result.stdout.splitlines():
                m = re.search(r'time[<=](\d+)', line, re.IGNORECASE)
                if m:
                    ping_ms = int(m.group(1))
                    break
                if 'Average' in line:
                    parts = line.split('=')
                    ping_ms = int(parts[-1].replace('ms', '').strip())
                    break
        except:
            pass

        return {
            "upload":       max(0, upload),
            "download":     max(0, download),
            "ping":         ping_ms,
            "connected":    True,
            "session_up":   fmt_total(session_up_mb),
            "session_down": fmt_total(session_down_mb),
        }
    except Exception as e:
        print(f"Network error: {e}")
        return {"upload": 0, "download": 0, "ping": None, "connected": False,
                "session_up": "0 MB", "session_down": "0 MB"}

# ─── PROCESSES ───────────────────────────────────────────────────────────────
SKIP_PROCS = {'system idle process', 'idle', 'system', 'registry', 'smss.exe',
              'csrss.exe', 'wininit.exe', 'services.exe', 'lsass.exe',
              'svchost.exe', 'dwm.exe', 'winlogon.exe', 'fontdrvhost.exe',
              'secure system', 'memory compression', 'antimalware service executable',
              'windows defender', 'spoolsv.exe', 'taskhostw.exe', 'searchindexer.exe'}
# Also skip anything with 'idle' in the name (catches localized variants)
SKIP_PROC_KEYWORDS = ['idle', 'system idle']

@app.route("/processes")
def processes():
    try:
        procs = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
            try:
                info = proc.info
                name = info['name'] or ''
                name_lower = name.lower()
                if name_lower in SKIP_PROCS or any(k in name_lower for k in SKIP_PROC_KEYWORDS):
                    continue
                if info['cpu_percent'] is None or info['cpu_percent'] == 0.0:
                    continue
                mem_mb = round(info['memory_info'].rss / (1024**2)) if info['memory_info'] else 0
                procs.append({
                    "name": name,
                    "cpu":  round(info['cpu_percent'], 1),
                    "mem_mb": mem_mb,
                })
            except:
                continue
        procs.sort(key=lambda x: x['cpu'], reverse=True)
        return {"processes": procs[:6]}
    except Exception as e:
        print(f"Processes error: {e}")
        return {"processes": []}

# ─── MIC LEVEL ───────────────────────────────────────────────────────────────
_mic_level = 0
_mic_active = False

def _mic_monitor():
    """Background thread sampling microphone input level."""
    global _mic_level, _mic_active
    try:
        import pyaudio
        pa = pyaudio.PyAudio()
        # Find default input device
        dev_info = pa.get_default_input_device_info()
        sample_rate = int(dev_info['defaultSampleRate'])
        chunk = 1024
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=sample_rate,
            input=True,
            frames_per_buffer=chunk
        )
        import struct, math
        _mic_active = True
        while True:
            try:
                data = stream.read(chunk, exception_on_overflow=False)
                shorts = struct.unpack(f'{len(data)//2}h', data)
                rms = math.sqrt(sum(s*s for s in shorts) / len(shorts))
                # Normalize to 0-100 range (max int16 = 32768)
                level = min(100, round((rms / 32768) * 100 * 8))
                _mic_level = level
            except:
                _mic_level = 0
            _time.sleep(0.05)
    except Exception as e:
        print(f"Mic monitor error: {e} — mic widget will show unavailable")
        _mic_active = False
        _mic_level = -1

@app.route("/mic")
def mic_level():
    return {"level": _mic_level, "active": _mic_active}

# ─── FPS ─────────────────────────────────────────────────────────────────────
_fps_cache = {"fps": 0, "app": "", "source": "none"}
_fps_ts = 0

def _get_fps_from_nvidia():
    """Try to get FPS from nvidia-smi overlay stats."""
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=utilization.gpu,encoder.stats.sessionCount',
             '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=2
        )
        # nvidia-smi doesn't expose FPS directly — use this as a fallback signal
        return None
    except:
        return None

def _get_fps_from_afterburner():
    """Read RivaTuner/Afterburner shared memory for FPS."""
    try:
        import mmap, struct
        mm = mmap.mmap(-1, 65536, "RTSSSharedMemoryV2")
        # RTSS header: signature at offset 0, version at 4, appEntrySize at 8, appArrOffset at 12, appArrSize at 16
        mm.seek(0)
        sig = mm.read(4)
        if sig != b'RTSS':
            mm.close()
            return None
        mm.seek(8)
        entry_size = struct.unpack('I', mm.read(4))[0]
        mm.seek(12)
        arr_offset = struct.unpack('I', mm.read(4))[0]
        arr_size   = struct.unpack('I', mm.read(4))[0]
        best_fps = 0
        best_app = ""
        for i in range(arr_size):
            offset = arr_offset + i * entry_size
            mm.seek(offset)
            entry = mm.read(entry_size)
            if len(entry) < 264:
                continue
            # App name: 260 bytes at offset 4, null-terminated
            app_name = entry[4:264].split(b'\x00')[0].decode('utf-8', errors='ignore')
            if not app_name or app_name == 'None':
                continue
            # FPS: at offset 264 (float)
            if len(entry) >= 268:
                fps_val = struct.unpack_from('f', entry, 264)[0]
                if fps_val > best_fps:
                    best_fps = fps_val
                    best_app = app_name
        mm.close()
        if best_fps > 0:
            return {"fps": round(best_fps), "app": best_app, "source": "rtss"}
    except:
        pass
    return None

@app.route("/fps")
def fps():
    global _fps_cache, _fps_ts
    now = _time.time()
    if now - _fps_ts < 1.0:
        return _fps_cache

    result = _get_fps_from_afterburner()
    if result:
        _fps_cache = result
    else:
        # No RTSS — check if a game process is running
        game_keywords = ['game', 'steam', 'epic', 'unity', 'unreal', 'dx11', 'dx12',
                         'opengl', 'vulkan', '.exe']
        gpu_pct = _sysinfo_cache.get('gpu_percent', 0)
        if gpu_pct > 20:
            _fps_cache = {"fps": 0, "app": "GPU active — install RivaTuner for FPS", "source": "hint"}
        else:
            _fps_cache = {"fps": 0, "app": "", "source": "none"}

    _fps_ts = now
    return _fps_cache

# ─── PERIPHERALS (Corsair iCUE SDK) ──────────────────────────────────────────
# Add future peripherals to PERIPHERAL_CONFIG — comment out inactive ones
PERIPHERAL_CONFIG = [
    {
        "id":    "void_elite",
        "label": "VOID ELITE",
        "type":  "headset",
        "brand": "corsair",
        # device_id populated at runtime by iCUE scan
    },
    {
        "id":    "m65_mouse",
        "label": "M65 RGB",
        "type":  "mouse",
        "brand": "corsair",
        # When wired: show wired icon instead of battery
    },
    # ── Add future devices below ──────────────────────────────────
    # {"id": "new_headset", "label": "HS80 RGB", "type": "headset", "brand": "corsair"},
    # {"id": "new_mouse",   "label": "M75",       "type": "mouse",   "brand": "corsair"},
]

_icue_sdk = None
_icue_devices = {}     # model_keyword -> device_id
_peripherals_cache = []
_peripherals_ts = 0
_PERIPHERALS_TTL = 30.0  # refresh every 30s

def _init_icue():
    global _icue_sdk, _icue_devices
    try:
        from cuesdk import CueSdk, CorsairDeviceFilter
        sdk = CueSdk()
        sdk.connect(lambda state: None)
        _time.sleep(1.5)
        device_filter = CorsairDeviceFilter(device_type_mask=0xFFFFFFFF)
        devices, err = sdk.get_devices(device_filter)
        if devices:
            for d in devices:
                _icue_devices[d.model.lower()] = d.device_id
                print(f"iCUE: found {d.model} → {d.device_id}", flush=True)
        _icue_sdk = sdk
        print(f"iCUE SDK initialized. Devices: {list(_icue_devices.keys())}", flush=True)
    except Exception as e:
        print(f"iCUE init error: {e}", flush=True)
        _icue_sdk = None

def _icue_read(device_id, prop_id):
    """Read a property from iCUE SDK. Returns value or None."""
    try:
        val, err = _icue_sdk.read_device_property(device_id, prop_id, 0)
        if 'Success' in str(err):
            return val.value
    except:
        pass
    return None

def _get_peripheral_data():
    results = []

    # ── VOID ELITE HEADSET ────────────────────────────────────────
    headset_data = {
        "id":        "void_elite",
        "label":     "VOID ELITE",
        "type":      "headset",
        "battery":   None,
        "charging":  False,
        "connected": False,
        "wired":     False,
    }
    if _icue_sdk:
        # Find headset device_id
        headset_id = None
        for key, did in _icue_devices.items():
            if 'void' in key:
                headset_id = did
                break
        if headset_id:
            headset_data["connected"] = _icue_read(headset_id, 4) or False
            headset_data["battery"]   = _icue_read(headset_id, 9)
            headset_data["charging"]  = _icue_read(headset_id, 2) or False
    results.append(headset_data)

    # ── M65 MOUSE ─────────────────────────────────────────────────
    mouse_data = {
        "id":        "m65_mouse",
        "label":     "M65 RGB",
        "type":      "mouse",
        "battery":   None,
        "charging":  False,
        "connected": False,
        "wired":     False,
    }
    if _icue_sdk:
        mouse_id = None
        for key, did in _icue_devices.items():
            if 'm65' in key or 'mouse' in key:
                mouse_id = did
                break
        if mouse_id:
            mouse_data["connected"] = _icue_read(mouse_id, 4) or False
            mouse_data["battery"]   = _icue_read(mouse_id, 9)
            mouse_data["charging"]  = _icue_read(mouse_id, 2) or False
        else:
            # Not found in iCUE = likely wired/cabled
            mouse_data["wired"]     = True
            mouse_data["connected"] = True
    results.append(mouse_data)

    return results

@app.route("/peripherals")
def peripherals():
    global _peripherals_cache, _peripherals_ts
    now = _time.time()
    if now - _peripherals_ts < _PERIPHERALS_TTL and _peripherals_cache:
        return {"devices": _peripherals_cache}
    _peripherals_cache = _get_peripheral_data()
    _peripherals_ts = now
    return {"devices": _peripherals_cache}

# ─── SUNRISE / SUNSET ────────────────────────────────────────────────────────
@app.route("/sunrise/<location>")
def sunrise(location):
    try:
        import requests as req
        r = req.get(f"https://wttr.in/{location}?format=%S+%s", timeout=5)
        if r.status_code == 200:
            text = r.text.strip()
            parts = text.split(' ')
            if len(parts) >= 2:
                # wttr.in returns times like "6:07 AM" — clean and return
                rise = parts[0].strip()
                sset = parts[1].strip()
                return {"sunrise": rise, "sunset": sset}
        return {"sunrise": "--:--", "sunset": "--:--"}
    except Exception as e:
        print(f"Sunrise error: {e}")
        return {"sunrise": "--:--", "sunset": "--:--"}

# ─── WEATHER ─────────────────────────────────────────────────────────────────
@app.route("/weather/<location>")
def weather(location):
    try:
        import requests as req
        r = req.get(f"https://wttr.in/{location}?format=%t+%C&u", timeout=5)
        text = r.text.strip().replace('+', '').replace('degF', 'F')
        return text
    except:
        return "--"

# ─── SPORTS ──────────────────────────────────────────────────────────────────
sports_cache = {"teams": [], "standings": [], "loading": True}

TEAM_SLUGS = {
    "anaheim ducks":("nhl","ana"),"arizona coyotes":("nhl","ari"),"boston bruins":("nhl","bos"),
    "buffalo sabres":("nhl","buf"),"calgary flames":("nhl","cgy"),"carolina hurricanes":("nhl","car"),
    "chicago blackhawks":("nhl","chi"),"colorado avalanche":("nhl","col"),"columbus blue jackets":("nhl","cbj"),
    "dallas stars":("nhl","dal"),"detroit red wings":("nhl","det"),"edmonton oilers":("nhl","edm"),
    "florida panthers":("nhl","fla"),"los angeles kings":("nhl","la"),"minnesota wild":("nhl","min"),
    "montreal canadiens":("nhl","mtl"),"nashville predators":("nhl","nsh"),"new jersey devils":("nhl","nj"),
    "new york islanders":("nhl","nyi"),"new york rangers":("nhl","nyr"),"ottawa senators":("nhl","ott"),
    "philadelphia flyers":("nhl","phi"),"pittsburgh penguins":("nhl","pit"),"san jose sharks":("nhl","sj"),
    "seattle kraken":("nhl","sea"),"st. louis blues":("nhl","stl"),"tampa bay lightning":("nhl","tb"),
    "toronto maple leafs":("nhl","tor"),"utah hockey club":("nhl","utah"),"vancouver canucks":("nhl","van"),
    "vegas golden knights":("nhl","vgk"),"washington capitals":("nhl","wsh"),"winnipeg jets":("nhl","wpg"),
    "arizona diamondbacks":("mlb","ari"),"atlanta braves":("mlb","atl"),"baltimore orioles":("mlb","bal"),
    "boston red sox":("mlb","bos"),"chicago cubs":("mlb","chc"),"chicago white sox":("mlb","chw"),
    "cincinnati reds":("mlb","cin"),"cleveland guardians":("mlb","cle"),"colorado rockies":("mlb","col"),
    "detroit tigers":("mlb","det"),"houston astros":("mlb","hou"),"kansas city royals":("mlb","kc"),
    "los angeles angels":("mlb","laa"),"los angeles dodgers":("mlb","lad"),"miami marlins":("mlb","mia"),
    "milwaukee brewers":("mlb","mil"),"minnesota twins":("mlb","min"),"new york mets":("mlb","nym"),
    "new york yankees":("mlb","nyy"),"oakland athletics":("mlb","oak"),"philadelphia phillies":("mlb","phi"),
    "pittsburgh pirates":("mlb","pit"),"san diego padres":("mlb","sd"),"san francisco giants":("mlb","sf"),
    "seattle mariners":("mlb","sea"),"st. louis cardinals":("mlb","stl"),"tampa bay rays":("mlb","tb"),
    "texas rangers":("mlb","tex"),"toronto blue jays":("mlb","tor"),"washington nationals":("mlb","wsh"),
    "atlanta hawks":("nba","atl"),"boston celtics":("nba","bos"),"brooklyn nets":("nba","bkn"),
    "charlotte hornets":("nba","cha"),"chicago bulls":("nba","chi"),"cleveland cavaliers":("nba","cle"),
    "dallas mavericks":("nba","dal"),"denver nuggets":("nba","den"),"detroit pistons":("nba","det"),
    "golden state warriors":("nba","gs"),"houston rockets":("nba","hou"),"indiana pacers":("nba","ind"),
    "los angeles clippers":("nba","lac"),"los angeles lakers":("nba","lal"),"memphis grizzlies":("nba","mem"),
    "miami heat":("nba","mia"),"milwaukee bucks":("nba","mil"),"minnesota timberwolves":("nba","min"),
    "new orleans pelicans":("nba","no"),"new york knicks":("nba","ny"),"oklahoma city thunder":("nba","okc"),
    "orlando magic":("nba","orl"),"philadelphia 76ers":("nba","phi"),"phoenix suns":("nba","phx"),
    "portland trail blazers":("nba","por"),"sacramento kings":("nba","sac"),"san antonio spurs":("nba","sa"),
    "toronto raptors":("nba","tor"),"utah jazz":("nba","utah"),"washington wizards":("nba","wsh"),
    "arizona cardinals":("nfl","ari"),"atlanta falcons":("nfl","atl"),"baltimore ravens":("nfl","bal"),
    "buffalo bills":("nfl","buf"),"carolina panthers":("nfl","car"),"chicago bears":("nfl","chi"),
    "cincinnati bengals":("nfl","cin"),"cleveland browns":("nfl","cle"),"dallas cowboys":("nfl","dal"),
    "denver broncos":("nfl","den"),"detroit lions":("nfl","det"),"green bay packers":("nfl","gb"),
    "houston texans":("nfl","hou"),"indianapolis colts":("nfl","ind"),"jacksonville jaguars":("nfl","jax"),
    "kansas city chiefs":("nfl","kc"),"las vegas raiders":("nfl","lv"),"los angeles chargers":("nfl","lac"),
    "los angeles rams":("nfl","lar"),"miami dolphins":("nfl","mia"),"minnesota vikings":("nfl","min"),
    "new england patriots":("nfl","ne"),"new orleans saints":("nfl","no"),"new york giants":("nfl","nyg"),
    "new york jets":("nfl","nyj"),"philadelphia eagles":("nfl","phi"),"pittsburgh steelers":("nfl","pit"),
    "san francisco 49ers":("nfl","sf"),"seattle seahawks":("nfl","sea"),"tampa bay buccaneers":("nfl","tb"),
    "tennessee titans":("nfl","ten"),"washington commanders":("nfl","wsh"),
}

def get_logo_url(team_name, sport):
    key = team_name.lower().strip()
    ncaa_overrides = {"oregon ducks": "https://a.espncdn.com/i/teamlogos/ncaa/500/2483.png"}
    if key in ncaa_overrides:
        return ncaa_overrides[key]
    if key in TEAM_SLUGS:
        s, slug = TEAM_SLUGS[key]
        return f"https://a.espncdn.com/i/teamlogos/{s}/500/{slug}.png"
    return f"https://a.espncdn.com/i/teamlogos/{sport}/500/default.png"

def refresh_sports_cache():
    import requests as req
    import pytz
    from datetime import datetime
    global sports_cache

    FAVORITE_TEAMS = [
        {"name":"Tampa Bay Lightning","sport":"nhl","search_name":"Tampa Bay Lightning","espn_slug":"tb","active":True},
        {"name":"Tampa Bay Rays","sport":"mlb","search_name":"Tampa Bay Rays","espn_slug":"tb","active":True},
        {"name":"Orlando Magic","sport":"nba","search_name":"Orlando Magic","espn_slug":"orl","active":True},
        {"name":"Tampa Bay Buccaneers","sport":"nfl","search_name":"Tampa Bay Buccaneers","espn_slug":"tb","active":False},
        {"name":"Oregon Ducks","sport":"ncaaf","search_name":"Oregon","espn_slug":"2483","active":False},
    ]
    SPORT_ENDPOINTS = {
        "mlb":"https://site.api.espn.com/apis/site/v2/sports/baseball/mlb",
        "nfl":"https://site.api.espn.com/apis/site/v2/sports/football/nfl",
        "nba":"https://site.api.espn.com/apis/site/v2/sports/basketball/nba",
        "nhl":"https://site.api.espn.com/apis/site/v2/sports/hockey/nhl",
        "ncaaf":"https://site.api.espn.com/apis/site/v2/sports/football/college-football",
    }
    SPORT_LEAGUE = {
        "nhl":"hockey/nhl","mlb":"baseball/mlb","nba":"basketball/nba","nfl":"football/nfl","ncaaf":None
    }
    est = pytz.timezone('America/New_York')
    today = datetime.now(est).strftime("%Y%m%d")
    teams_data = []

    from concurrent.futures import ThreadPoolExecutor, as_completed

    def fetch_team(team):
        team_info = {
            "name":team["name"],"record":"0-0","game_today":False,"state":"pre",
            "opponent":"","opponent_logo":"",
            "our_logo":get_logo_url(team["name"],team["sport"]),
            "game_time":"","our_score":"","opp_score":"","sport":team["sport"],
            "status_detail":"","opp_record":"","situation":{},"news":[],
            "player_stats":[],"pitcher":{},"batter":{},"balls":0,"strikes":0,"outs":0,
            "on_first":False,"on_second":False,"on_third":False,"last_play":"",
            "active":team.get("active",True),"our_team_id":"",
        }
        try:
            r = req.get(f"{SPORT_ENDPOINTS[team['sport']]}/teams/{team['espn_slug']}",timeout=5)
            if r.status_code==200:
                t_info=r.json().get("team",{})
                rec=t_info.get("record",{}).get("items",[])
                if rec: team_info["record"]=rec[0].get("summary","0-0")
        except: pass

        if team["active"]:
            try:
                r=req.get(f"{SPORT_ENDPOINTS[team['sport']]}/scoreboard?dates={today}",timeout=5)
                if r.status_code==200:
                    for event in r.json().get("events",[]):
                        competitors=event.get("competitions",[{}])[0].get("competitors",[])
                        names=[c.get("team",{}).get("displayName","") for c in competitors]
                        if any(team["search_name"].lower() in n.lower() for n in names):
                            team_info["game_today"]=True
                            status=event.get("status",{})
                            team_info["state"]=status.get("type",{}).get("state","pre")
                            team_info["status_detail"]=status.get("type",{}).get("shortDetail","")
                            for c in competitors:
                                c_name=c.get("team",{}).get("displayName","")
                                if team["search_name"].lower() not in c_name.lower():
                                    team_info["opponent"]=c_name
                                    team_info["opp_score"]=c.get("score","")
                                    team_info["opponent_logo"]=get_logo_url(c_name,team["sport"])
                                    opp_rec=c.get("records",[])
                                    team_info["opp_record"]=opp_rec[0].get("summary","") if opp_rec else c.get("record","")
                                else:
                                    team_info["our_score"]=c.get("score","")
                                    team_info["our_team_id"]=c.get("team",{}).get("id","")
                            raw_time=event.get("date","")
                            if raw_time:
                                try:
                                    from datetime import datetime as dt
                                    utc=dt.strptime(raw_time,"%Y-%m-%dT%H:%MZ")
                                    utc=pytz.utc.localize(utc)
                                    est_t=utc.astimezone(est)
                                    team_info["game_time"]=est_t.strftime("%I:%M %p").lstrip("0")
                                except: pass
                            sit=event.get("competitions",[{}])[0].get("situation",{})
                            event_id=event.get("id","")
                            if team["sport"]=="mlb" and sit:
                                pitcher_a=sit.get("pitcher",{}).get("athlete",{})
                                batter_a=sit.get("batter",{}).get("athlete",{})
                                team_info["situation"]={
                                    "balls":sit.get("balls",0),"strikes":sit.get("strikes",0),
                                    "outs":sit.get("outs",0),"onFirst":sit.get("onFirst",False),
                                    "onSecond":sit.get("onSecond",False),"onThird":sit.get("onThird",False),
                                    "lastPlay":sit.get("lastPlay",{}).get("text",""),
                                    "pitcher":{"name":pitcher_a.get("shortName",""),"headshot":pitcher_a.get("headshot",""),"summary":sit.get("pitcher",{}).get("summary","")},
                                    "batter":{"name":batter_a.get("shortName",""),"headshot":batter_a.get("headshot",""),"summary":sit.get("batter",{}).get("summary","")},
                                }
                            elif team["sport"]=="nhl" and event_id:
                                try:
                                    sr=req.get(f"https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/summary?event={event_id}",timeout=5)
                                    if sr.status_code==200:
                                        sd=sr.json()
                                        plays=sd.get("plays",[])
                                        goals=[p for p in plays if p.get("scoringPlay")]
                                        last_goal={}
                                        if goals:
                                            g=goals[-1]
                                            scorer=next((p for p in g.get("participants",[]) if p.get("type")=="scorer"),{})
                                            assisters=[p for p in g.get("participants",[]) if p.get("type")=="assister"]
                                            last_goal={
                                                "text":g.get("text",""),"period":g.get("period",{}).get("displayValue",""),
                                                "clock":g.get("clock",{}).get("displayValue",""),
                                                "strength":g.get("strength",{}).get("text",""),
                                                "shot_type":g.get("shotInfo",{}).get("text","") if g.get("shotInfo") else "",
                                                "scorer_name":scorer.get("athlete",{}).get("shortName",""),
                                                "scorer_headshot":scorer.get("athlete",{}).get("headshot",{}).get("href","") if isinstance(scorer.get("athlete",{}).get("headshot",{}),dict) else scorer.get("athlete",{}).get("headshot",""),
                                                "scorer_goals":scorer.get("ytdGoals",""),
                                                "assists":[{"name":a.get("athlete",{}).get("shortName",""),"headshot":a.get("athlete",{}).get("headshot",{}).get("href","") if isinstance(a.get("athlete",{}).get("headshot",{}),dict) else ""} for a in assisters],
                                            }
                                        goalies=[]
                                        for team_box in sd.get("boxscore",{}).get("players",[]):
                                            for stat_group in team_box.get("statistics",[]):
                                                if stat_group.get("name","").lower()=="goalies":
                                                    for athlete in stat_group.get("athletes",[]):
                                                        a=athlete.get("athlete",{});stats=athlete.get("stats",[]);hs=a.get("headshot",{})
                                                        goalies.append({"name":a.get("shortName",""),"headshot":hs.get("href","") if isinstance(hs,dict) else hs,"saves":stats[0] if len(stats)>0 else "","shots":stats[1] if len(stats)>1 else "","team_id":team_box.get("team",{}).get("id","")})
                                        series_summary=""
                                        comp=event.get("competitions",[{}])[0]
                                        series=comp.get("series",{})
                                        if series: series_summary=series.get("summary","")
                                        status=event.get("status",{})
                                        # Pull team stats from boxscore
                                        our_stats={}; opp_stats={}
                                        for team_box in sd.get("boxscore",{}).get("teams",[]):
                                            tid=team_box.get("team",{}).get("id","")
                                            stat_map={s.get("name"):s.get("displayValue","--") for s in team_box.get("statistics",[])}
                                            if tid==team_info.get("our_team_id",""):
                                                our_stats=stat_map
                                            else:
                                                opp_stats=stat_map
                                        def pp_str(s):
                                            g=s.get("powerPlayGoals",""); o=s.get("powerPlayOpportunities","")
                                            return f"{g}/{o}" if g and o else "--"
                                        # Faceoff % — try boxscore first, fallback to competitors
                                        def get_faceoff(stat_map, competitors, is_our):
                                            fo = stat_map.get("faceOffWinPercentage","--")
                                            if fo and fo not in ("--","0","0.0","0.00"):
                                                return fo
                                            # Fallback: competitors from scoreboard
                                            for c in competitors:
                                                c_is_us = c.get("team",{}).get("id","") == team_info.get("our_team_id","")
                                                if c_is_us == is_our:
                                                    for stat in c.get("statistics",[]):
                                                        if stat.get("name","").lower() in ("faceoffwinpct","faceoffwinpercentage","faceoffpct"):
                                                            return stat.get("displayValue","--")
                                            return "--"
                                        competitors = comp.get("competitors",[])
                                        our_fo = get_faceoff(our_stats, competitors, True)
                                        opp_fo = get_faceoff(opp_stats, competitors, False)
                                        team_info["situation"]={
                                            "sport":"nhl","last_goal":last_goal,"goalies":goalies,
                                            "series":series_summary,"period":status.get("period",1),
                                            "clock":status.get("displayClock",""),
                                            "lastPlay":sit.get("lastPlay",{}).get("text","") if sit else "",
                                            "our_shots":our_stats.get("shotsongoal","--"),
                                            "opp_shots":opp_stats.get("shotsongoal","--"),
                                            "our_hits":our_stats.get("hits","--"),
                                            "opp_hits":opp_stats.get("hits","--"),
                                            "our_faceoff":our_fo,
                                            "opp_faceoff":opp_fo,
                                            "our_pp":pp_str(our_stats),
                                            "opp_pp":pp_str(opp_stats),
                                            "our_blocked":our_stats.get("blockedShots","--"),
                                            "our_giveaways":our_stats.get("giveaways","--"),
                                        }
                                except Exception as e:
                                    print(f"NHL summary error: {e}",flush=True)
                            elif team["sport"]=="nba" and event_id:
                                try:
                                    sr=req.get(f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={event_id}",timeout=5)
                                    if sr.status_code==200:
                                        sd=sr.json()
                                        leaders_data=[]
                                        for team_leaders in sd.get("leaders",[]):
                                            team_id=team_leaders.get("team",{}).get("id","")
                                            for cat in team_leaders.get("leaders",[]):
                                                cat_name=cat.get("name","")
                                                top_list=cat.get("leaders",[])
                                                if not top_list: continue
                                                top=top_list[0];athlete=top.get("athlete",{});hs=athlete.get("headshot",{})
                                                raw_val=top.get("value",0)
                                                try: display_val=str(round(float(raw_val)))
                                                except: display_val=str(raw_val)
                                                leaders_data.append({"team_id":team_id,"category":cat_name,"label":cat.get("abbreviation",cat_name.upper()[:3]),"name":athlete.get("shortName",""),"headshot":hs.get("href","") if isinstance(hs,dict) else hs,"value":raw_val,"display_value":display_val,"summary":top.get("summary","")})
                                        series_summary=""
                                        comp=event.get("competitions",[{}])[0]
                                        series=comp.get("series",{})
                                        if series: series_summary=series.get("summary","")
                                        status=event.get("status",{})
                                        # Build quarter scores — key = quarter number, value = {our_team_id: score, opp_id: score}
                                        scoring_by_period = {}
                                        linescores = sd.get("boxscore",{}).get("teams",[])
                                        comp_linescore = comp.get("linescores",[])
                                        if comp_linescore:
                                            # ESPN linescores are per-team per-period
                                            for i, period_score in enumerate(comp_linescore):
                                                q = str(i+1)
                                                scoring_by_period[q] = {}
                                            for comp_team in comp.get("competitors",[]):
                                                tid = comp_team.get("team",{}).get("id","")
                                                is_us = tid == team_info.get("our_team_id","")
                                                for i, ls in enumerate(comp_team.get("linescores",[])):
                                                    q = str(i+1)
                                                    if q not in scoring_by_period: scoring_by_period[q] = {}
                                                    scoring_by_period[q]["our" if is_us else "opp"] = ls.get("value",0)
                                        team_info["situation"]={"sport":"nba","leaders":leaders_data,"series":series_summary,"period":status.get("period",1),"clock":status.get("displayClock",""),"scoring_by_period":scoring_by_period}
                                except Exception as e:
                                    print(f"NBA summary error: {e}",flush=True)
                            break
            except: pass

        try:
            league=SPORT_LEAGUE.get(team["sport"])
            if league:
                r=req.get(f"https://site.api.espn.com/apis/site/v2/sports/{league}/news?team={team['espn_slug']}&limit=2",timeout=5)
                if r.status_code==200:
                    articles=r.json().get("articles",[])
                    keywords=team["search_name"].lower().split()+[team["name"].lower()]
                    filtered=[a.get("headline","") for a in articles[:5] if a.get("headline","") and any(k in a.get("headline","").lower() for k in keywords)]
                    limit=4 if not team.get("active") else 2
                    team_info["news"]=filtered[:limit] if filtered else [a.get("headline","") for a in articles[:limit] if a.get("headline")]
        except Exception as e:
            print(f"News error {team['name']}: {e}",flush=True)

        try:
            league=SPORT_LEAGUE.get(team["sport"])
            if league and team.get("active"):
                r=req.get(f"https://site.api.espn.com/apis/site/v2/sports/{league}/teams/{team['espn_slug']}/statistics",timeout=5)
                if r.status_code==200:
                    cats=r.json().get("results",{}).get("stats",{}).get("categories",[])
                    stats=[]
                    WANT={"nhl":["goals","assists","savePct","plusMinus"],"mlb":["teamGamesPlayed","homeRuns","winPct"],"nba":["points","assists","rebounds","fieldGoalPct"],"nfl":["passingYards","rushingYards","sacks","interceptions"]}
                    seen_labels=set()
                    want=WANT.get(team["sport"],[])
                    for cat in cats:
                        for stat in cat.get("stats",[]):
                            if stat.get("name") in want:
                                label=stat.get("abbreviation",stat.get("name",""))
                                if label not in seen_labels:
                                    seen_labels.add(label)
                                    stats.append({"label":label,"value":stat.get("displayValue",str(stat.get("value","")))})
                    team_info["player_stats"]=stats[:6]
        except Exception as e:
            print(f"Stats error {team['name']}: {e}",flush=True)

        return team_info

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures={executor.submit(fetch_team,team):team for team in FAVORITE_TEAMS}
        for future in as_completed(futures):
            try: teams_data.append(future.result())
            except Exception as e: print(f"Team fetch error: {e}",flush=True)

    order={t["name"]:i for i,t in enumerate(FAVORITE_TEAMS)}
    teams_data.sort(key=lambda t:order.get(t["name"],99))

    standings_data=[]
    try:
        r=req.get("https://site.api.espn.com/apis/v2/sports/hockey/nhl/standings",timeout=5)
        if r.status_code==200:
            for group in r.json().get("children",[]):
                entries=group.get("standings",{}).get("entries",[])
                if any("Tampa Bay" in e.get("team",{}).get("displayName","") for e in entries):
                    for entry in entries:
                        t_name=entry.get("team",{}).get("displayName","")
                        record=""
                        for stat in entry.get("stats",[]):
                            if stat.get("name")=="overall":
                                record=stat.get("displayValue","")
                                break
                        standings_data.append({"name":t_name.replace("Tampa Bay ","TB "),"record":record,"is_my_team":"Tampa Bay Lightning" in t_name})
                    break
    except Exception as e:
        print(f"Standings error: {e}",flush=True)

    sports_cache={"teams":teams_data,"standings":standings_data[:8],"loading":False}
    print(f"Sports cache updated: {len(teams_data)} teams",flush=True)

def sports_background_loop():
    import traceback, sys
    print("Sports background loop started",flush=True)
    while True:
        try: refresh_sports_cache()
        except Exception as e:
            print(f"Sports cache CRASHED: {e}",flush=True)
            traceback.print_exc(file=sys.stdout)
            sys.stdout.flush()
        _time.sleep(120)

threading.Thread(target=sports_background_loop,daemon=True).start()

@app.route("/sports")
def sports():
    return sports_cache

@app.route("/headshot")
def headshot():
    import requests as req
    url=flask_request.args.get("url","")
    if not url or "espncdn.com" not in url:
        return "",404
    try:
        r=req.get(url,timeout=5,headers={"User-Agent":"Mozilla/5.0"})
        return r.content,200,{"Content-Type":r.headers.get("Content-Type","image/png"),"Cache-Control":"max-age=3600"}
    except:
        return "",404

# ─── NEWS ─────────────────────────────────────────────────────────────────────
import xml.etree.ElementTree as ET
news_cache = {}
NEWS_CACHE_TTL = 1800

COUNTRY_RSS = {
    "united states of america":["https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml","https://feeds.npr.org/1004/rss.xml"],
    "united kingdom":["https://feeds.bbci.co.uk/news/uk/rss.xml"],
    "russia":["https://www.themoscowtimes.com/rss/news"],
    "china":["https://www.scmp.com/rss/91/feed"],
    "japan":["https://www.japantimes.co.jp/feed"],
    "india":["https://feeds.bbci.co.uk/news/world/south_asia/rss.xml"],
    "germany":["https://rss.dw.com/rdf/rss-en-ger"],
    "france":["https://www.france24.com/en/france/rss"],
    "australia":["https://feeds.bbci.co.uk/news/world/australia/rss.xml"],
    "brazil":["https://feeds.bbci.co.uk/news/world/latin_america/rss.xml"],
    "canada":["https://www.cbc.ca/cmlink/rss-topstories"],
    "south africa":["https://feeds.bbci.co.uk/news/world/africa/rss.xml"],
    "saudi arabia":["https://www.aljazeera.com/xml/rss/all.xml"],
    "israel":["https://www.aljazeera.com/xml/rss/all.xml"],
    "iran":["https://www.aljazeera.com/xml/rss/all.xml"],
    "ukraine":["https://feeds.bbci.co.uk/news/world/europe/rss.xml"],
    "thailand":["https://www.bangkokpost.com/rss/data/topstories.xml","https://www.chiangmaicitylife.com/feed/"],
    "indonesia":["https://feeds.bbci.co.uk/news/world/asia/rss.xml"],
    "south korea":["https://feeds.bbci.co.uk/news/world/asia/rss.xml"],
    "nigeria":["https://feeds.bbci.co.uk/news/world/africa/rss.xml"],
    "egypt":["https://www.aljazeera.com/xml/rss/all.xml"],
    "mexico":["https://feeds.bbci.co.uk/news/world/latin_america/rss.xml"],
    "argentina":["https://feeds.bbci.co.uk/news/world/latin_america/rss.xml"],
    "turkey":["https://feeds.bbci.co.uk/news/world/europe/rss.xml"],
    "pakistan":["https://feeds.bbci.co.uk/news/world/south_asia/rss.xml"],
}
RSS_FALLBACK = "https://feeds.bbci.co.uk/news/world/rss.xml"

def parse_rss(url):
    import requests as req
    headers={"User-Agent":"Mozilla/5.0 (compatible; CypherHUD/1.0)"}
    r=req.get(url,timeout=8,headers=headers); r.raise_for_status()
    root=ET.fromstring(r.content)
    items=root.findall(".//item"); articles=[]
    for item in items[:5]:
        title=(item.findtext("title") or "").strip()
        desc=re.sub(r'<[^>]+>','',(item.findtext("description") or "").strip())[:140]
        source_el=item.find("source"); source=source_el.text if source_el is not None else ""
        if title: articles.append({"title":title,"desc":desc,"source":source})
    return articles

def tag_article(title,desc):
    text=(title+" "+desc).lower()
    if any(w in text for w in ["artificial intelligence"," ai ","software","cybersecurity","semiconductor","robotics","spacecraft","tech"]): return "TECH"
    if any(w in text for w in ["war","military","troops","airstrike","missile","combat","nato","invasion","weapon","armed"]): return "MIL"
    if any(w in text for w in ["economy","stock market","trade","inflation","gdp","central bank","interest rate","recession","tariff","currency"]): return "ECO"
    if any(w in text for w in ["climate","flood","wildfire","earthquake","hurricane","tsunami","drought","emissions","storm"]): return "ENV"
    if any(w in text for w in ["election","president","prime minister","parliament","congress","senate","vote","government","political","sanctions"]): return "POL"
    if any(w in text for w in ["world cup","olympics","championship","nba","nfl","premier league","formula 1","tournament"]): return "SPT"
    return "NEWS"

@app.route("/news")
def get_news():
    country=flask_request.args.get("country","").lower().strip()
    if not country: return {"articles":[],"error":"No country specified"}
    cached=news_cache.get(country)
    if cached and (_time.time()-cached["ts"])<NEWS_CACHE_TTL:
        return {"articles":cached["articles"],"cached":True}
    try:
        feed_urls=COUNTRY_RSS.get(country,[RSS_FALLBACK])
        all_articles=[]; seen_titles=set()
        for url in feed_urls:
            try:
                items=parse_rss(url)
                source_name=url.split("/")[2].replace("www.","").replace("feeds.","")
                for item in items:
                    if item["title"] not in seen_titles:
                        seen_titles.add(item["title"])
                        all_articles.append({"tag":tag_article(item["title"],item["desc"]),"title":item["title"],"desc":item["desc"],"source":item.get("source") or source_name})
            except Exception as e:
                print(f"RSS fetch error {url}: {e}",flush=True)
        all_articles=all_articles[:6]
        news_cache[country]={"ts":_time.time(),"articles":all_articles}
        return {"articles":all_articles,"cached":False}
    except Exception as e:
        return {"articles":[],"error":str(e)}

# ─── CALENDAR ─────────────────────────────────────────────────────────────────
CALENDAR_FILE = os.path.join(BASE_DIR, "calendar.json")

def load_calendar():
    if os.path.exists(CALENDAR_FILE):
        try:
            with open(CALENDAR_FILE,"r") as f: return json.load(f)
        except: pass
    return {"events":[]}

def save_calendar(data):
    with open(CALENDAR_FILE,"w") as f: json.dump(data,f,indent=2)

@app.route("/calendar")
def get_calendar(): return load_calendar()

@app.route("/calendar/add",methods=["POST"])
def add_calendar_event():
    data=flask_request.get_json()
    cal=load_calendar()
    cal["events"].append({"date":data.get("date",""),"time":data.get("time",""),"title":data.get("title","")})
    save_calendar(cal); return {"status":"ok"}

@app.route("/calendar/delete",methods=["POST"])
def delete_calendar_event():
    data=flask_request.get_json(); idx=data.get("index",-1)
    cal=load_calendar()
    if 0<=idx<len(cal["events"]):
        cal["events"].pop(idx); save_calendar(cal); return {"status":"ok"}
    return {"status":"error","message":"Invalid index"}

@app.route("/calendar/today")
def get_today_events():
    import pytz; from datetime import datetime
    est=pytz.timezone('America/New_York')
    today_dt=datetime.now(est)
    today=f"{today_dt.month}/{today_dt.day}/{today_dt.year}"
    cal=load_calendar()
    events=[e for e in cal.get("events",[]) if e.get("date")==today]
    events.sort(key=lambda e:e.get("time",""))
    return {"events":events,"today":today}

# ─── TIMER ────────────────────────────────────────────────────────────────────
@app.route("/timer/set",methods=["POST"])
def timer_set():
    data=flask_request.get_json()
    ui_state["timer_seconds"]=data.get("seconds",0)
    ui_state["timer_label"]=data.get("label","TIMER")
    ui_state["timer_ts"]=_time.time()
    return {"status":"ok"}

@app.route("/timer/reset",methods=["POST"])
def timer_reset():
    ui_state["timer_seconds"]=0
    ui_state["timer_label"]=""
    ui_state["timer_ts"]=_time.time()
    return {"status":"ok"}

@app.route("/timer/state")
def timer_state():
    return {"seconds":ui_state.get("timer_seconds",0),"label":ui_state.get("timer_label",""),"ts":ui_state.get("timer_ts",0)}

# ─── GOALS ────────────────────────────────────────────────────────────────────
GOALS_FILE = os.path.join(BASE_DIR, "goals.json")

def load_goals():
    import pytz; from datetime import datetime
    est=pytz.timezone('America/New_York')
    today=datetime.now(est).strftime("%Y-%m-%d")
    if os.path.exists(GOALS_FILE):
        try:
            with open(GOALS_FILE,"r") as f: data=json.load(f)
            if data.get("date")==today: return data
        except: pass
    return {"date":today,"goals":[]}

def save_goals(data):
    with open(GOALS_FILE,"w") as f: json.dump(data,f,indent=2)

@app.route("/goals")
def get_goals(): return load_goals()

@app.route("/goals/add",methods=["POST"])
def add_goal():
    data=flask_request.get_json(); goals=load_goals()
    if len(goals["goals"])<3:
        goals["goals"].append({"text":data.get("text",""),"done":False})
        save_goals(goals); return {"status":"ok"}
    return {"status":"error","message":"Max 3 goals per day"}

@app.route("/goals/toggle",methods=["POST"])
def toggle_goal():
    data=flask_request.get_json(); idx=data.get("index",-1); goals=load_goals()
    if 0<=idx<len(goals["goals"]):
        goals["goals"][idx]["done"]=not goals["goals"][idx]["done"]
        save_goals(goals); return {"status":"ok"}
    return {"status":"error"}

@app.route("/goals/clear",methods=["POST"])
def clear_goals():
    import pytz; from datetime import datetime
    est=pytz.timezone('America/New_York')
    today=datetime.now(est).strftime("%Y-%m-%d")
    save_goals({"date":today,"goals":[]}); return {"status":"ok"}

# ─── COUNTDOWN ────────────────────────────────────────────────────────────────
COUNTDOWN_FILE = os.path.join(BASE_DIR, "countdown.json")

def load_countdowns():
    if os.path.exists(COUNTDOWN_FILE):
        try:
            with open(COUNTDOWN_FILE,"r") as f: return json.load(f)
        except: pass
    return {"countdowns":[]}

def save_countdowns(data):
    with open(COUNTDOWN_FILE,"w") as f: json.dump(data,f,indent=2)

@app.route("/countdown")
def get_countdown(): return load_countdowns()

@app.route("/countdown/add",methods=["POST"])
def add_countdown():
    data=flask_request.get_json(); cd=load_countdowns()
    cd["countdowns"].append({"label":data.get("label","Event"),"date":data.get("date","")})
    save_countdowns(cd); return {"status":"ok"}

@app.route("/countdown/delete",methods=["POST"])
def delete_countdown():
    data=flask_request.get_json(); idx=data.get("index",-1); cd=load_countdowns()
    if 0<=idx<len(cd["countdowns"]):
        cd["countdowns"].pop(idx); save_countdowns(cd); return {"status":"ok"}
    return {"status":"error"}

# ─── SESSION LOG ──────────────────────────────────────────────────────────────
session_log = []

def add_session_log(entry):
    import pytz; from datetime import datetime
    est=pytz.timezone('America/New_York')
    now=datetime.now(est)
    time_str=now.strftime("%I:%M%p").lstrip("0").lower()
    session_log.append({"time":time_str,"text":entry})
    if len(session_log)>20: session_log.pop(0)

@app.route("/session-log")
def get_session_log(): return {"log":list(reversed(session_log))}

@app.route("/session-log/add",methods=["POST"])
def post_session_log():
    data=flask_request.get_json(); add_session_log(data.get("text","")); return {"status":"ok"}

# ─── STARTUP ──────────────────────────────────────────────────────────────────
def _startup_background():
    """Run non-critical startup tasks in background so server starts fast."""
    _time.sleep(2)
    # Start stats sampler
    threading.Thread(target=sample_stats, daemon=True).start()
    # Init iCUE SDK
    threading.Thread(target=_init_icue, daemon=True).start()
    # Start mic monitor (requires pyaudio — optional)
    threading.Thread(target=_mic_monitor, daemon=True).start()
    print("Background services started.", flush=True)

def run_ui():
    socketio.run(app, host='0.0.0.0', port=5000, debug=False,
                 use_reloader=False, allow_unsafe_werkzeug=True)

def start_ui():
    t = threading.Thread(target=run_ui, daemon=True)
    t.start()
    _time.sleep(1)
    threading.Thread(target=sample_stats, daemon=True).start()
    threading.Thread(target=_init_icue, daemon=True).start()
    threading.Thread(target=_mic_monitor, daemon=True).start()
    print("Cypher UI running at http://localhost:5000")

if __name__ == "__main__":
    threading.Thread(target=_startup_background, daemon=True).start()
    print("Cypher UI running at http://localhost:5000")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
