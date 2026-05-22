"""
Windows COM IDropTarget for multi-file Outlook drag-drop.

Qt's QMimeData.data("FileContents") hardcodes lindex=0, so only the first
dragged Outlook email is accessible through Qt's normal drop machinery.
This module registers a native IDropTarget on the widget's HWND and calls
IDataObject::GetData() with each lindex, extracting every dragged email.

Falls back gracefully (no-op) on non-Windows platforms or if OLE
registration fails, so Qt's built-in drag-drop remains active.

No external dependencies beyond ctypes (stdlib).
"""
import ctypes
import ctypes.wintypes as wintypes
import hashlib
import struct
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Non-Windows shim
# ---------------------------------------------------------------------------
if sys.platform != "win32":
    class OutlookDropTarget:  # noqa: F811
        def __init__(self, drop_zone):
            pass

        def revoke(self):
            pass

else:
    # -----------------------------------------------------------------------
    # Windows OLE types and constants
    # -----------------------------------------------------------------------
    _ole32    = ctypes.windll.ole32
    _kernel32 = ctypes.windll.kernel32
    _user32   = ctypes.windll.user32

    HRESULT = ctypes.c_long
    ULONG   = ctypes.c_ulong
    DWORD   = wintypes.DWORD
    LONG    = ctypes.c_long

    S_OK            = 0
    DROPEFFECT_COPY = 1
    TYMED_HGLOBAL   = 1
    TYMED_ISTREAM   = 4
    TYMED_ISTORAGE  = 8
    DVASPECT_CONTENT = 1
    CF_HDROP        = 15
    STGM_READWRITE  = 0x00000002
    STGM_SHARE_EXCLUSIVE = 0x00000010
    STGM_CREATE     = 0x00001000
    STGC_DEFAULT    = 0

    # Explicit argtypes/restype so ctypes uses pointer-sized (64-bit) args on x64.
    # Without these, ctypes defaults to c_int (32-bit) and overflows on large handles.
    _kernel32.GlobalSize.argtypes  = [ctypes.c_void_p]
    _kernel32.GlobalSize.restype   = ctypes.c_size_t
    _kernel32.GlobalLock.argtypes  = [ctypes.c_void_p]
    _kernel32.GlobalLock.restype   = ctypes.c_void_p
    _kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    _kernel32.GlobalUnlock.restype  = ctypes.c_bool
    _ole32.ReleaseStgMedium.argtypes = [ctypes.c_void_p]
    _ole32.ReleaseStgMedium.restype  = None
    _ole32.RevokeDragDrop.argtypes   = [ctypes.c_void_p]
    _ole32.RevokeDragDrop.restype    = HRESULT
    _ole32.RegisterDragDrop.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    _ole32.RegisterDragDrop.restype  = HRESULT
    _ole32.CreateILockBytesOnHGlobal.argtypes = [
        ctypes.c_void_p, wintypes.BOOL, ctypes.POINTER(ctypes.c_void_p),
    ]
    _ole32.CreateILockBytesOnHGlobal.restype = HRESULT
    _ole32.StgCreateDocfileOnILockBytes.argtypes = [
        ctypes.c_void_p, DWORD, DWORD, ctypes.POINTER(ctypes.c_void_p),
    ]
    _ole32.StgCreateDocfileOnILockBytes.restype = HRESULT
    _ole32.GetHGlobalFromILockBytes.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p),
    ]
    _ole32.GetHGlobalFromILockBytes.restype = HRESULT

    # Outlook virtual-file clipboard formats
    _CF_FGDW = _user32.RegisterClipboardFormatW("FileGroupDescriptorW")
    _CF_FC   = _user32.RegisterClipboardFormatW("FileContents")

    # FILEDESCRIPTORW constants (Windows SDK)
    _FD_SIZE     = 592
    _FD_NAME_OFF = 72

    # -----------------------------------------------------------------------
    # COM structures
    # -----------------------------------------------------------------------
    class _FORMATETC(ctypes.Structure):
        _fields_ = [
            ("cfFormat", ctypes.c_ushort),
            ("ptd",      ctypes.c_void_p),
            ("dwAspect", DWORD),
            ("lindex",   LONG),
            ("tymed",    DWORD),
        ]

    class _STGMEDIUM(ctypes.Structure):
        _fields_ = [
            ("tymed",          DWORD),
            ("hGlobal",        wintypes.HANDLE),
            ("pUnkForRelease", ctypes.c_void_p),
        ]

    # -----------------------------------------------------------------------
    # IDropTarget vtable function prototypes.
    # POINTL pt is passed by value (8 bytes on x64 = one register slot).
    # Using c_longlong avoids struct-by-value ABI ambiguity in ctypes callbacks.
    # -----------------------------------------------------------------------
    _PT  = ctypes.c_longlong  # stands in for POINTL by-value

    _FnQI   = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
    _FnAR   = ctypes.WINFUNCTYPE(ULONG,   ctypes.c_void_p)
    _FnRel  = ctypes.WINFUNCTYPE(ULONG,   ctypes.c_void_p)
    _FnDE   = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.c_void_p, DWORD, _PT, ctypes.POINTER(DWORD))
    _FnDO   = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, DWORD, _PT, ctypes.POINTER(DWORD))
    _FnDL   = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p)
    _FnDrop = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.c_void_p, DWORD, _PT, ctypes.POINTER(DWORD))

    class _Vtable(ctypes.Structure):
        _fields_ = [
            ("QueryInterface", _FnQI),
            ("AddRef",         _FnAR),
            ("Release",        _FnRel),
            ("DragEnter",      _FnDE),
            ("DragOver",       _FnDO),
            ("DragLeave",      _FnDL),
            ("Drop",           _FnDrop),
        ]

    class _COMObj(ctypes.Structure):
        _fields_ = [
            ("lpVtbl", ctypes.POINTER(_Vtable)),
            ("ref",    ctypes.c_long),
        ]

    # -----------------------------------------------------------------------
    # Low-level helpers
    # -----------------------------------------------------------------------
    def _call_getdata(idata_ptr, cfformat: int, lindex: int,
                      tymed: int = TYMED_HGLOBAL | TYMED_ISTREAM | TYMED_ISTORAGE):
        """
        Call IDataObject::GetData via vtable index 3.
        idata_ptr is a Python integer holding the IDataObject* address.
        """
        fe          = _FORMATETC()
        fe.cfFormat = cfformat
        fe.ptd      = None
        fe.dwAspect = DVASPECT_CONTENT
        fe.lindex   = lindex
        fe.tymed    = tymed
        sm = _STGMEDIUM()

        # Dereference IDataObject* to reach the vtable pointer array
        obj_ptr = ctypes.c_void_p(idata_ptr)
        vtbl_addr = ctypes.cast(obj_ptr, ctypes.POINTER(ctypes.c_void_p))[0]
        vtbl = ctypes.cast(ctypes.c_void_p(vtbl_addr), ctypes.POINTER(ctypes.c_void_p))

        # vtable[3] = IDataObject::GetData
        fn = ctypes.WINFUNCTYPE(
            HRESULT, ctypes.c_void_p,
            ctypes.POINTER(_FORMATETC), ctypes.POINTER(_STGMEDIUM),
        )(vtbl[3])

        hr = fn(idata_ptr, ctypes.byref(fe), ctypes.byref(sm))
        return hr, sm

    def _release_com_ptr(ptr):
        addr = _to_int_ptr(ptr)
        if not addr:
            return
        try:
            vtbl_addr = ctypes.cast(ctypes.c_void_p(addr), ctypes.POINTER(ctypes.c_void_p))[0]
            vtbl = ctypes.cast(ctypes.c_void_p(vtbl_addr), ctypes.POINTER(ctypes.c_void_p))
            fn = ctypes.WINFUNCTYPE(ULONG, ctypes.c_void_p)(vtbl[2])
            fn(addr)
        except Exception:
            pass

    def _to_int_ptr(handle) -> int:
        """Normalise any handle representation to an integer pointer value."""
        if handle is None:
            return 0
        # ctypes instance (c_void_p, c_uint64, etc.) — read .value
        val = getattr(handle, "value", None)
        if val is not None:
            return int(val) if val else 0
        # Plain int already
        if isinstance(handle, int):
            return handle
        # Bytes representation (8-byte LE pointer from buffer protocol)
        if isinstance(handle, (bytes, bytearray)):
            return struct.unpack("<Q", bytes(handle)[:8].ljust(8, b"\x00"))[0]
        return 0

    def _hglobal_to_bytes(handle) -> bytes | None:
        """Copy data out of an HGLOBAL and return it as bytes."""
        addr = _to_int_ptr(handle)
        if not addr:
            return None
        h = ctypes.c_void_p(addr)
        size = _kernel32.GlobalSize(h)
        if not size:
            return None
        ptr = _kernel32.GlobalLock(h)
        if not ptr:
            return None
        try:
            return ctypes.string_at(ptr, size)
        finally:
            _kernel32.GlobalUnlock(h)

    def _istream_to_bytes(punk) -> bytes | None:
        """Read data out of an IStream COM pointer."""
        addr = _to_int_ptr(punk)
        if not addr:
            return None
        try:
            # IStream vtable: QI(0) AddRef(1) Release(2) Read(3) Write(4) ...
            vtbl_addr = ctypes.cast(ctypes.c_void_p(addr), ctypes.POINTER(ctypes.c_void_p))[0]
            vtbl = ctypes.cast(ctypes.c_void_p(vtbl_addr), ctypes.POINTER(ctypes.c_void_p))
            Read = ctypes.WINFUNCTYPE(
                HRESULT, ctypes.c_void_p,
                ctypes.c_void_p, DWORD, ctypes.POINTER(DWORD),
            )(vtbl[3])
            chunks = []
            buf_size = 65536
            buf = (ctypes.c_char * buf_size)()
            read = DWORD(0)
            while True:
                hr = Read(addr, buf, buf_size, ctypes.byref(read))
                if read.value == 0:
                    break
                chunks.append(bytes(buf[:read.value]))
                if hr != S_OK:
                    break
            return b"".join(chunks) if chunks else None
        except Exception:
            return None

    def _istorage_to_bytes(pstorage) -> bytes | None:
        """
        Copy an IStorage-backed Outlook virtual file into an in-memory compound
        storage, then extract the resulting HGLOBAL as bytes.
        """
        src_addr = _to_int_ptr(pstorage)
        if not src_addr:
            return None

        lockbytes = ctypes.c_void_p()
        dest_storage = ctypes.c_void_p()
        hglobal = ctypes.c_void_p()
        try:
            hr = _ole32.CreateILockBytesOnHGlobal(None, True, ctypes.byref(lockbytes))
            if hr != S_OK or not lockbytes.value:
                print(f"[OutlookDrop]     CreateILockBytesOnHGlobal failed hr=0x{hr & 0xFFFFFFFF:08X}",
                      flush=True)
                return None

            hr = _ole32.StgCreateDocfileOnILockBytes(
                lockbytes,
                STGM_CREATE | STGM_READWRITE | STGM_SHARE_EXCLUSIVE,
                0,
                ctypes.byref(dest_storage),
            )
            if hr != S_OK or not dest_storage.value:
                print(f"[OutlookDrop]     StgCreateDocfileOnILockBytes failed hr=0x{hr & 0xFFFFFFFF:08X}",
                      flush=True)
                return None

            src_vtbl_addr = ctypes.cast(ctypes.c_void_p(src_addr), ctypes.POINTER(ctypes.c_void_p))[0]
            src_vtbl = ctypes.cast(ctypes.c_void_p(src_vtbl_addr), ctypes.POINTER(ctypes.c_void_p))

            # IStorage::CopyTo is at vtable index 7
            copy_to = ctypes.WINFUNCTYPE(
                HRESULT, ctypes.c_void_p, DWORD, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
            )(src_vtbl[7])

            hr = copy_to(src_addr, 0, None, None, dest_storage.value)
            if hr != S_OK:
                print(f"[OutlookDrop]     IStorage::CopyTo failed hr=0x{hr & 0xFFFFFFFF:08X}",
                      flush=True)
                return None

            # Commit the destination so all data is flushed into the lockbytes
            try:
                dest_vtbl_addr = ctypes.cast(dest_storage, ctypes.POINTER(ctypes.c_void_p))[0]
                dest_vtbl = ctypes.cast(ctypes.c_void_p(dest_vtbl_addr), ctypes.POINTER(ctypes.c_void_p))
                dest_commit = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, DWORD)(dest_vtbl[9])
                dest_commit(dest_storage.value, STGC_DEFAULT)
            except Exception as exc:
                print(f"[OutlookDrop]     dest commit warning: {exc}", flush=True)

            hr = _ole32.GetHGlobalFromILockBytes(lockbytes, ctypes.byref(hglobal))
            if hr != S_OK or not hglobal.value:
                print(f"[OutlookDrop]     GetHGlobalFromILockBytes failed hr=0x{hr & 0xFFFFFFFF:08X}",
                      flush=True)
                return None
            return _hglobal_to_bytes(hglobal.value)
        finally:
            if dest_storage.value:
                _release_com_ptr(dest_storage.value)
            if lockbytes.value:
                _release_com_ptr(lockbytes.value)

    def _read_and_release(sm: _STGMEDIUM) -> bytes | None:
        """Extract bytes from a STGMEDIUM (hGlobal or IStream) then release it."""
        data = None
        if sm.tymed == TYMED_HGLOBAL and sm.hGlobal:
            data = _hglobal_to_bytes(sm.hGlobal)
        elif sm.tymed == TYMED_ISTREAM and sm.hGlobal:
            data = _istream_to_bytes(sm.hGlobal)
        elif sm.tymed == TYMED_ISTORAGE and sm.hGlobal:
            data = _istorage_to_bytes(sm.hGlobal)
        # ReleaseStgMedium argtypes expects c_void_p; cast byref to satisfy it
        _ole32.ReleaseStgMedium(ctypes.cast(ctypes.byref(sm), ctypes.c_void_p))
        return data

    # -----------------------------------------------------------------------
    # Extraction logic
    # -----------------------------------------------------------------------
    def _cache_path_for_msg(cache_dir: Path, original_name: str, content: bytes) -> Path:
        """
        Outlook often uses the subject line as the virtual filename, so
        different emails can arrive with the same name. Keep the visible
        subject, but add a short content hash so each distinct email gets a
        stable cached path.
        """
        original = Path(original_name)
        stem = original.stem.strip() or "outlook_email"
        suffix = original.suffix or ".msg"
        digest = hashlib.sha1(content).hexdigest()[:10]
        candidate = cache_dir / f"{stem}__{digest}{suffix}"

        if not candidate.exists():
            return candidate

        try:
            if candidate.read_bytes() == content:
                return candidate
        except Exception:
            pass

        for idx in range(2, 1000):
            fallback = cache_dir / f"{stem}__{digest}_{idx}{suffix}"
            if not fallback.exists():
                return fallback
            try:
                if fallback.read_bytes() == content:
                    return fallback
            except Exception:
                pass

        return cache_dir / f"{stem}__{digest}_overflow{suffix}"

    def _extract_outlook(idata_ptr, cache_dir: Path) -> list[str]:
        """
        Extract ALL virtual .msg files from an Outlook IDataObject.
        Uses lindex = 0 … num_items-1 to retrieve each file independently.
        """
        hr, sm = _call_getdata(idata_ptr, _CF_FGDW, -1)
        if hr != S_OK:
            print(f"[OutlookDrop] FileGroupDescriptorW GetData failed hr=0x{hr & 0xFFFFFFFF:08X}",
                  flush=True)
            return []

        raw = _read_and_release(sm)
        if not raw or len(raw) < 4:
            print("[OutlookDrop] FileGroupDescriptorW data empty", flush=True)
            return []

        num = struct.unpack_from("<I", raw, 0)[0]
        print(f"[OutlookDrop] {num} email(s) detected in drag", flush=True)
        if num == 0:
            return []

        names: list[str] = []
        for i in range(num):
            base = 4 + i * _FD_SIZE
            try:
                blob = raw[base + _FD_NAME_OFF: base + _FD_NAME_OFF + 520]
                name = blob.decode("utf-16-le").rstrip("\x00")
            except Exception:
                name = ""
            if not name:
                name = f"outlook_email_{i + 1}.msg"
            elif not name.lower().endswith(".msg"):
                name += ".msg"
            # Sanitise filename (strip path separators that Outlook sometimes includes)
            name = Path(name).name or name
            names.append(name)
            print(f"[OutlookDrop]   [{i}] {name}", flush=True)

        # Attempt order for FileContents:
        # 1. lindex=i  with ISTORAGE only    (common for Outlook .msg virtual files)
        # 2. lindex=i  with ISTREAM only
        # 3. lindex=i  with HGLOBAL only
        # 4. lindex=i  with all three media  (some impls need a combined request)
        # 5. lindex=-1 with ISTORAGE only    (fallback for some Outlook variants)
        # 6. lindex=-1 with ISTREAM only
        # 7. lindex=-1 with HGLOBAL only
        # 8. lindex=-1 with all three media
        # Combinations 4-6 are only attempted for i==0 because lindex=-1 always
        # returns the "first" file, so using it for i>0 would give duplicate data.
        def _attempt_fc(lindex, tymed):
            hr, sm = _call_getdata(idata_ptr, _CF_FC, lindex, tymed)
            if hr != S_OK:
                print(f"[OutlookDrop]     lindex={lindex} tymed={tymed} → "
                      f"hr=0x{hr & 0xFFFFFFFF:08X}", flush=True)
                return None
            data = _read_and_release(sm)
            if data:
                print(f"[OutlookDrop]     lindex={lindex} tymed={tymed} → OK "
                      f"({len(data)} bytes)", flush=True)
            return data

        saved: list[str] = []
        for i in range(num):
            print(f"[OutlookDrop]   fetching FileContents[{i}]:", flush=True)
            content = None
            candidates = [
                (i,  TYMED_ISTORAGE),
                (i,  TYMED_ISTREAM),
                (i,  TYMED_HGLOBAL),
                (i,  TYMED_HGLOBAL | TYMED_ISTREAM | TYMED_ISTORAGE),
            ]
            if i == 0:
                candidates += [
                    (-1, TYMED_ISTORAGE),
                    (-1, TYMED_ISTREAM),
                    (-1, TYMED_HGLOBAL),
                    (-1, TYMED_HGLOBAL | TYMED_ISTREAM | TYMED_ISTORAGE),
                ]
            for lx, ty in candidates:
                content = _attempt_fc(lx, ty)
                if content:
                    break

            if not content:
                print(f"[OutlookDrop]   all attempts failed for [{i}]", flush=True)
                continue
            p = _cache_path_for_msg(cache_dir, names[i], content)
            try:
                p.write_bytes(content)
                saved.append(str(p))
                print(f"[OutlookDrop]   saved {p}", flush=True)
            except Exception as exc:
                print(f"[OutlookDrop]   write failed: {exc}", flush=True)

        return saved

    def _extract_hdrop(idata_ptr) -> list[str]:
        """Extract file paths from a standard Explorer CF_HDROP."""
        hr, sm = _call_getdata(idata_ptr, CF_HDROP, -1)
        if hr != S_OK:
            return []
        raw = _read_and_release(sm)
        if not raw or len(raw) < 20:
            return []

        # DROPFILES: pFiles(4) pt.x(4) pt.y(4) fNC(4) fWide(4)
        p_files = struct.unpack_from("<I", raw,  0)[0]
        f_wide  = struct.unpack_from("<I", raw, 16)[0]
        blob    = raw[p_files:]
        paths: list[str] = []

        if f_wide:
            text = blob.decode("utf-16-le", errors="replace")
            for name in text.split("\x00"):
                if not name:
                    break
                paths.append(name)
        else:
            for chunk in blob.split(b"\x00"):
                if not chunk:
                    break
                paths.append(chunk.decode("mbcs", errors="replace"))

        return [p for p in paths if p.lower().endswith((".pdf", ".msg"))]

    # -----------------------------------------------------------------------
    # COM IDropTarget class
    # -----------------------------------------------------------------------
    class OutlookDropTarget:
        """
        COM IDropTarget registered on a DropZone widget's HWND.

        Handles both Outlook virtual-file drops (all emails in one drag)
        and standard Explorer drops, bypassing Qt's lindex=0 limitation.

        Must be registered AFTER Qt finishes its own RegisterDragDrop call
        (which happens during show). Use DropZone.showEvent + QTimer for this.
        """

        def __init__(self, drop_zone):
            self._zone = drop_zone
            self._hwnd = int(drop_zone.winId())

            # Persistent dropcache so session source_file paths survive restarts
            self._cache = Path(tempfile.gettempdir()) / "nagarkot_dropcache"
            self._cache.mkdir(exist_ok=True)

            self._obj    = _COMObj()
            self._vtable = _Vtable()

            # Hold references so Python GC doesn't collect the ctypes callbacks
            self._cb_qi   = _FnQI  (self._qi)
            self._cb_ar   = _FnAR  (self._ar)
            self._cb_rel  = _FnRel (self._rel)
            self._cb_de   = _FnDE  (self._de)
            self._cb_do   = _FnDO  (self._do)
            self._cb_dl   = _FnDL  (self._dl)
            self._cb_drop = _FnDrop(self._drop)

            self._vtable.QueryInterface = self._cb_qi
            self._vtable.AddRef         = self._cb_ar
            self._vtable.Release        = self._cb_rel
            self._vtable.DragEnter      = self._cb_de
            self._vtable.DragOver       = self._cb_do
            self._vtable.DragLeave      = self._cb_dl
            self._vtable.Drop           = self._cb_drop

            self._obj.lpVtbl = ctypes.pointer(self._vtable)
            self._obj.ref    = 1

            com_ptr = ctypes.cast(ctypes.pointer(self._obj), ctypes.c_void_p)

            # Revoke whatever is registered (Qt's target) then register ours
            _ole32.RevokeDragDrop(self._hwnd)
            hr = _ole32.RegisterDragDrop(self._hwnd, com_ptr)
            if hr == S_OK:
                print(f"[OutlookDrop] registered on hwnd=0x{self._hwnd:X}", flush=True)
            else:
                print(f"[OutlookDrop] RegisterDragDrop failed hr=0x{hr & 0xFFFFFFFF:08X}", flush=True)

        def revoke(self):
            if self._hwnd:
                _ole32.RevokeDragDrop(self._hwnd)
                self._hwnd = 0

        def __del__(self):
            self.revoke()

        # --- IUnknown ---
        def _qi(self, this, riid, ppv):
            ppv[0] = this
            return S_OK

        def _ar(self, this):
            self._obj.ref += 1
            return self._obj.ref

        def _rel(self, this):
            self._obj.ref = max(0, self._obj.ref - 1)
            return self._obj.ref

        # --- IDropTarget ---
        def _de(self, this, pDataObj, grfKeyState, pt, pdwEffect):
            self._zone._active_style()
            pdwEffect[0] = DROPEFFECT_COPY
            return S_OK

        def _do(self, this, grfKeyState, pt, pdwEffect):
            pdwEffect[0] = DROPEFFECT_COPY
            return S_OK

        def _dl(self, this):
            self._zone._idle_style()
            return S_OK

        def _drop(self, this, pDataObj, grfKeyState, pt, pdwEffect):
            self._zone._idle_style()
            pdwEffect[0] = DROPEFFECT_COPY
            try:
                saved = _extract_outlook(pDataObj, self._cache)
                if not saved:
                    saved = _extract_hdrop(pDataObj)
                if saved:
                    self._zone.files_dropped.emit(saved)
                else:
                    print("[OutlookDrop] drop produced no files", flush=True)
            except Exception as exc:
                print(f"[OutlookDrop] _drop error: {exc}", flush=True)
                import traceback
                traceback.print_exc()
            return S_OK
