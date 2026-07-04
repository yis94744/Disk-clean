"""Duplicate file finder - blake2b + mmap + optimized"""
import os, hashlib, mmap
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from PySide6.QtCore import QThread, Signal

WORKERS = 12; READ_SIZE = 262144; MIN_SIZE = 1024; PARTIAL_SIZE = 16384
SKIP_DIRS = {".Bin",".BIN","System Volume Information",".~WS","","Config.Msi","MSOCache","Recovery","PerfLogs","Windows","node_modules",".git","__pycache__",".venv","venv","ProgramData\\Packages","ProgramData\\Microsoft","ProgramData\\Package Cache","WinSxS","assembly","Microsoft.NET"}
SKIP_EXTS = {".tmp",".log",".cache",".etl",".evtx",".pf",".dmp",".dat",".bin"}

class DupFinder(QThread):
    progress = Signal(str, int, int); found_group = Signal(list); finished = Signal(list)
    def __init__(self):
        super().__init__(); self._cancel_flag=False; self._root_paths=[]; self._min_size=MIN_SIZE
    def setup(self, root_paths, min_size=MIN_SIZE):
        self._root_paths=root_paths; self._min_size=max(min_size,512)
    def cancel(self): self._cancel_flag=True

    def run(self):
        self._cancel_flag=False
        self.progress.emit("正在收集文件列表...",0,0)
        all_files=[]
        for root in self._root_paths:
            if self._cancel_flag: self.finished.emit([]); return
            self._walk_fast(root, all_files)
        total=len(all_files)
        if total==0: self.progress.emit("未找到文件",0,0); self.finished.emit([]); return
        self.progress.emit(f"共{total} 个文件, 按大小分组...",0,total)
        by_key=defaultdict(list)
        for fp,sz,mt in all_files: by_key[(sz,mt)].append(fp)
        candidates=[]
        for (sz,mt),group in by_key.items():
            if len(group)>1: candidates.append((sz,group))
        cf=sum(len(g) for _,g in candidates)
        if cf==0: self.progress.emit("无候选重复文件",0,0); self.finished.emit([]); return
        self.progress.emit(f"{len(candidates)} 组相同大小, {cf} 个候选文件",0,cf)
        all_groups=[]; processed=0; rs=max(1,cf//50)
        for sz,group in candidates:
            if self._cancel_flag: break
            existing=[f for f in group if os.path.exists(f)]
            if len(existing)<2: processed+=len(group); continue
            if len(existing)==2:
                if self._quick_compare(existing[0],existing[1]): all_groups.append(existing); self.found_group.emit(existing)
                processed+=2
            else:
                bh=self._hash_parallel(existing)
                for dups in bh.values():
                    if len(dups)>1: all_groups.append(dups); self.found_group.emit(dups)
                processed+=len(existing)
            if processed>=rs:
                pct=min(100,processed*100//cf)
                self.progress.emit(f"分析 {pct}% ({processed}/{cf})",processed,cf)
                rs=processed+max(1,cf//50)
        if not self._cancel_flag: self.progress.emit(f"完成! {len(all_groups)} 组重复",cf,cf)
        self.finished.emit(all_groups)

    def _walk_fast(self, root, result):
        try:
            for entry in os.scandir(root):
                if self._cancel_flag: return
                try:
                    if entry.is_dir(follow_symlinks=False):
                        name=entry.name
                        if name in SKIP_DIRS or name[:1] in ('.','$'): continue
                        self._walk_fast(entry.path,result)
                    elif entry.is_file(follow_symlinks=False):
                        st=entry.stat(); sz=st.st_size
                        if sz<self._min_size: continue
                        ext=os.path.splitext(entry.name)[1].lower()
                        if ext in SKIP_EXTS: continue
                        result.append((entry.path,sz,int(st.st_mtime)))
                except (OSError,FileNotFoundError): continue
        except (PermissionError,OSError): pass

    def _quick_compare(self, fp1, fp2):
        try:
            s1=os.path.getsize(fp1); s2=os.path.getsize(fp2)
            if s1!=s2: return False
            with open(fp1,"rb") as f1, open(fp2,"rb") as f2:
                if f1.read(PARTIAL_SIZE)!=f2.read(PARTIAL_SIZE): return False
                if s1>PARTIAL_SIZE*2:
                    f1.seek(-PARTIAL_SIZE,2); f2.seek(-PARTIAL_SIZE,2)
                    if f1.read(PARTIAL_SIZE)!=f2.read(PARTIAL_SIZE): return False
            return True
        except (OSError,PermissionError,FileNotFoundError): return False

    def _hash_parallel(self, files):
        bh=defaultdict(list)
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futures={}
            for fp in files:
                if self._cancel_flag: break
                futures[ex.submit(self._full_hash,fp)]=fp
            for future in as_completed(futures):
                fp=futures[future]
                try:
                    h=future.result(timeout=30)
                    if h: bh[h].append(fp)
                except: pass
        return bh

    @staticmethod
    def _full_hash(fp):
        try:
            sz=os.path.getsize(fp)
            if sz<512: return None
            with open(fp,"rb") as f:
                try:
                    with mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as m:
                        h=hashlib.blake2b()
                        for offset in range(0,sz,READ_SIZE): h.update(m[offset:offset+READ_SIZE])
                        return h.digest()
                except (ValueError,OSError):
                    h=hashlib.blake2b()
                    while True:
                        chunk=f.read(READ_SIZE)
                        if not chunk: break
                        h.update(chunk)
                    return h.digest()
        except (OSError,PermissionError,FileNotFoundError): return None
