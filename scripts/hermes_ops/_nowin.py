"""헤르메스 스크립트 공용: 자식 프로세스 콘솔 창이 사장님 화면에 뜨지 않게 한다 (탐, 2026-09-30).
스크립트 맨 위에서 `import _nowin`만 하면 subprocess.Popen 전부에 CREATE_NO_WINDOW가 붙는다.
DETACHED_PROCESS는 콘솔 앱(hermes.exe)에 새 창을 만들어 주므로 NO_WINDOW로 바꾼다."""
import subprocess, sys
if sys.platform == "win32" and not getattr(subprocess.Popen, "_nowin", False):
    _NW, _DET = 0x08000000, 0x00000008
    _orig = subprocess.Popen.__init__
    def _init(self, *a, **kw):
        f = kw.get("creationflags", 0) or 0
        kw["creationflags"] = (f & ~_DET) | _NW
        _orig(self, *a, **kw)
    subprocess.Popen.__init__ = _init
    subprocess.Popen._nowin = True
