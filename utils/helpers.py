"""
Utility helpers for Disk Cleaner Pro
"""
import os, ctypes, sys, string
from datetime import datetime

def format_size(size_bytes) -> str:
    if size_bytes is None: size_bytes = 0
    if size_bytes == 0: return "0 B"
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    i = 0; fsize = float(size_bytes)
    while fsize >= 1024 and i < len(units) - 1:
        fsize /= 1024; i += 1
    if i == 0: return f"{int(fsize)} {units[i]}"
    return f"{fsize:.2f} {units[i]}"

def format_timestamp(ts: float) -> str:
    if ts == 0: return "-"
    try:
        dt = datetime.fromtimestamp(ts)
        return dt.strftime("%Y-%m-%d %H:%M")
    except (OSError, ValueError): return "-"

def get_file_access_time(filepath: str) -> float:
    try: return os.path.getatime(filepath)
    except OSError: return 0

def get_file_modify_time(filepath: str) -> float:
    try: return os.path.getmtime(filepath)
    except OSError: return 0

def days_since(timestamp: float) -> int:
    if timestamp == 0: return 9999
    return int((datetime.now().timestamp() - timestamp) / 86400)

def is_admin() -> bool:
    try: return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception: return False

def run_as_admin():
    if not is_admin():
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        sys.exit(0)

def get_drives() -> list:
    drives = []
    for letter in string.ascii_uppercase:
        path = f"{letter}:\\"
        if os.path.exists(path): drives.append(path)
    return drives

def get_drive_info(drive: str) -> dict:
    try:
        kernel32 = ctypes.windll.kernel32
        free_avail = ctypes.c_ulonglong(0)
        total = ctypes.c_ulonglong(0)
        total_free = ctypes.c_ulonglong(0)
        ret = kernel32.GetDiskFreeSpaceExW(
            ctypes.c_wchar_p(drive),
            ctypes.byref(free_avail),
            ctypes.byref(total),
            ctypes.byref(total_free)
        )
        if ret == 0: raise OSError("GetDiskFreeSpaceExW failed")
        total_val = total.value; free_val = total_free.value
        used_val = total_val - free_val
        percent = round(used_val / total_val * 100, 1) if total_val > 0 else 0
        return {"drive": drive, "total": total_val, "free": free_val,
                "used": used_val, "percent": percent}
    except Exception:
        return {"drive": drive, "total": 0, "free": 0, "used": 0, "percent": 0}

def get_file_extension_category(ext: str) -> str:
    if not ext: return "Other"
    ext = ext.lower()
    cats = {
        "Video": {".mp4",".mkv",".avi",".mov",".wmv",".flv",".webm",".ts",".vdm",".body",".m4v",".3gp",".rmvb",".vob",".m2ts",".f4v",".mpeg",".mpg",".divx",".xvid",".ogv",".asf",".mts",".m2t"},
        "Image": {".jpg",".jpeg",".png",".gif",".bmp",".webp",".svg",".psd",".heic",".ico",".tiff",".tif",".raw",".jfif",".avif",".nef",".cr2",".ai",".eps",".xcf",".pcx",".tga",".exr",".hdr",".icns",".cur",".dds",".ktx"},
        "Audio": {".mp3",".wav",".flac",".aac",".ogg",".ape",".mid",".wma",".midi",".aiff",".alac",".ac3",".dts",".amr",".opus",".m4a",".m4b",".m4r",".mka",".ra",".rm",".spx",".voc",".wv",".m3u",".m3u8",".pls",".cue",".asx",".wpl",".xspf"},
        "Archive": {".zip",".7z",".rar",".pak",".cab",".asar",".tar",".gz",".iso",".tgz",".wxvpkg",".wxapkg",".bz2",".xz",".lz",".lz4",".zst",".arj",".dmg",".deb",".rpm",".snap",".flatpak",".flatpakref",".flatpakrepo",".gem",".par2",".xpi",".crx",".war",".ear",".nupkg",".whl",".egg",".zipx",".lzh",".lha",".zoo",".arc",".squashfs"},
        "Document": {".pdf",".docx",".xlsx",".pptx",".txt",".md",".csv",".epub",".xml",".log",".doc",".xls",".ppt",".rtf",".odt",".ods",".odp",".chm",".tex",".srt",".vtt",".sub",".ass",".ssa",".nfo",".diz",".hlp",".cnt",".djvu",".mobi",".azw",".azw3",".kf8",".cbr",".cbz",".lit",".lrf",".fb2",".prc",".oxps",".xps",".msg"},
        "Code": {".py",".pyd",".js",".ts",".java",".jar",".c",".cpp",".h",".lex",".pri",".ipch",".json",".ress",".pyc",".cs",".go",".rs",".rb",".swift",".kt",".lua",".sql",".sh",".bash",".ps1",".yaml",".yml",".toml",".ini",".cfg",".conf",".env",".lock",".class",".gitignore",".dockerfile",".makefile",".gradle",".properties",".podspec",".gemspec",".rake",".entitlements",".mobileprovision",".xcworkspace",".pbxproj",".map",".tsbuildinfo",".d.ts",".nib",".xib",".storyboard",".playground",".rproj",".sln",".csproj",".vcxproj",".fsproj",".sqlproj",".rkt",".clj",".cljs",".edn",".dart",".elm",".hs",".lhs",".ml",".mli",".nim",".pl",".pm",".ex",".exs",".erl",".hrl",".zig",".odin",".vala",".vapi",".sfv",".sha1",".sha256",".md5",".crc32",".xsd",".xsl",".plist",".props",".targets",".qml",".ps1xml",".cdxml",".tcl",".adoc",".globalconfig",".strings",".config",".qmltypes"},
        "Program": {".exe",".msi",".msp",".appx",".cmd",".scr",".com",".bat",".msix",".pkg",".appimage",".gadget",".msixbundle",".appxbundle",".vbs",".wsf",".psm1",".psd1",".run",},
        "System": {".sys",".dll",".lib",".mui",".cat",".dmp",".drv",".ocx",".bin",".db",".dat",".ax",".cpl",".efi",".so",".dylib",".ko",".reg",".inf",".manifest",".man",".tmp",".cache",".bak",".old",".etl",".pf",".theme",".msc",".diagcab",".pol",".mof",".vdi",".vmdk",".vhd",".vhdx",".qcow2",".ova",".ovf",".pdb",".kext",".node",".nib",".part",".crdownload",".download",".opdownload",".aria2",".partial",".wim",".swm",".esd",".ffs",".gho",".evtx",".tlb",".nls",".winmd",".inf_loc",".pnf",".mfl",".ctb",".lang",".enc",".xrm-ms",".blf",".regtrans-ms",".catalogitem"},
        "Font": {".ttf",".ttc",".otf",".woff",".woff2",".eot",".fon",".pfa",".pfb",".sfd",".bdf",".pcf",".afm",".pfm",".ttc",".dfont",".ttf",".fea",".otb",".otc"},
        "Mobile App": {".apk",".a",".aab",".xapk",".apks",".apkm",".ipa",".dex",".aar",".so"},
        "Web/Net": {".html",".htm",".css",".php",".onnx",".usha1",".usha256",".jsx",".tsx",".vue",".svelte",".scss",".less",".wasm",".pem",".crt",".cer",".key",".pfx",".der",".p12",".p7b",".p7c",".torrent",".nzb",".magnet",".htaccess",".htpasswd",".shtml",".shtm",".asp",".aspx",".jsp",".do",".action",".rss",".atom",".wSDL",".xaml",".cshtml",".vbhtml",".twig",".blade.php",".ejs",".pug",".hbs",".njk"},
        "Shortcut": {".lnk",".url",".desktop",".webloc",".website"},
    }
    for cat, exts in cats.items():
        if ext in exts: return cat
    return "Other"
