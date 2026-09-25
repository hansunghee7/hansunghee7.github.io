#!/usr/bin/env python3
r"""드라이버 업데이트 뒤 GPU 점검 3종(2026-09-25 탐, 핏→탐 이관·사장님 지시).

평소: nvidia-smi 드라이버 버전만 보고, 기록값(C:\work\_ops\gpu_baseline.json)과 같으면 아무것도 출력하지 않고 끝난다.
버전이 바뀌었거나 --force: 아래 3종을 돌린다.
  ① 계산: shorts-lab tts-env 파이썬으로 torch.cuda.is_available() + 2048x2048 행렬곱
  ② 인코더: ffmpeg h264_nvenc·hevc_nvenc·av1_nvenc로 1초 시험 영상을 실제로 인코딩(상태 기록만, 통과 조건 아님:
     9/25 실측 ffmpeg 9.0.1은 NVENC API 13.1 = 드라이버 610 이상 필요, 591.86에서는 셋 다 불가. 우리 파이프라인은 libx264라 영향 없음)
  ③ 음성: 우리 목소리 챔피언 설정(알파 0.35, our_voice_v1.json, tempo 1.0)으로 한 문장 생성
통과: 기록값을 새 버전으로 바꾸고 탐·핏에게 우편 한 줄. 실패: 사장님께 --ask 우편(텔레그램 신솔라 방) + exit 1.
헤르메스 no-agent 크론으로 돈다(사본: 헤르메스 scripts/). 기준값 9/25: RTX 4090, 드라이버 591.86, CUDA 13.1.
사용: python scripts/ops/gpu_check.py [--force] [--dry]   (--dry: 알림·기록 갱신 없이 결과만 출력)
"""
from __future__ import annotations
import json, os, re, subprocess, sys, time
from datetime import datetime
from pathlib import Path

OPS = Path(r"C:\work\_ops")
BASE = OPS / "gpu_baseline.json"
WORK = OPS / "gpu_check"
TTS_PY = Path(r"C:\work\shorts-lab\pilot-shorts2\tts-env\Scripts\python.exe")
PILOT = Path(r"C:\work\shorts-lab\pilot-shorts2")
MAILBOX = Path(r"C:\work\solar-bible\mailbox\mailbox.py")
SENTENCE = "드라이버를 바꾼 뒤에도 목소리가 잘 나오는지 한 문장으로 확인합니다."


def run(cmd, timeout, cwd=None):
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    env["PYTHONIOENCODING"] = "utf-8"
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, cwd=cwd, env=env)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def smi():
    code, out = run(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"], 30)
    name, drv = [x.strip() for x in out.strip().splitlines()[0].split(",")]
    _, full = run(["nvidia-smi"], 30)
    m = re.search(r"CUDA Version:\s*([\d.]+)", full)
    return {"gpu": name, "driver": drv, "cuda": m.group(1) if m else "?"}


def check_compute():
    code = ("import torch,time;assert torch.cuda.is_available(),'cuda false';"
            "a=torch.randn(2048,2048,device='cuda');t=time.time();b=(a@a).sum().item();torch.cuda.synchronize();"
            "print('ok',torch.cuda.get_device_name(0),torch.__version__,round((time.time()-t)*1000),'ms')")
    rc, out = run([str(TTS_PY), "-c", code], 180)
    return rc == 0 and out.strip().splitlines()[-1].startswith("ok"), out.strip().splitlines()[-1][:160] if out.strip() else "no output"


def check_nvenc():
    res = {}
    for enc in ("h264_nvenc", "hevc_nvenc", "av1_nvenc"):
        rc, out = run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=duration=1:size=1280x720:rate=30",
                       "-c:v", enc, "-f", "null", "-"], 120)
        m = re.search(r"Required: ([\d.]+) Found: ([\d.]+)", out)
        res[enc] = "ok" if rc == 0 else (f"불가(API 필요 {m.group(1)}, 드라이버 제공 {m.group(2)})" if m else (out.strip().splitlines() or [f"exit {rc}"])[0][:120])
    return all(v == "ok" for v in res.values()), res


def check_voice():
    ep = WORK / "ep"; (ep / "03-align").mkdir(parents=True, exist_ok=True)
    tags = [{"i": 0, "tone": "explain", "speed": 1.0, "pause": 0.3, "why": "GPU 점검", "text": SENTENCE}]
    (ep / "03-align" / "tone_tags.json").write_text(json.dumps(tags, ensure_ascii=False), encoding="utf-8")
    out = WORK / "voice_check.mp3"
    if out.exists():
        out.unlink()
    t0 = time.time()
    rc, log = run([str(TTS_PY), "voice_tone.py", "say", str(ep), "0.35", str(out), "--ref=voice_ref/our_voice_v1.json", "--tempo=1.0"], 900, cwd=str(PILOT))
    sec = round(time.time() - t0)
    if rc != 0 or not out.exists() or out.stat().st_size < 10_000:
        return False, f"exit {rc}, {sec}s, " + (log.strip().splitlines()[-1][:160] if log.strip() else "no log")
    _, dur = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)], 30)
    return True, f"{out.stat().st_size // 1024}KB, {float(dur.strip() or 0):.1f}s 음성, 생성 {sec}s"


def mail(to, title, body, ask=None):
    cmd = [sys.executable, str(MAILBOX), "send", to, title, "--from", "헤르메스", "--body", body]
    if ask:
        cmd += ["--ask", ask]
    subprocess.run(cmd, capture_output=True, timeout=60)


def main():
    force, dry = "--force" in sys.argv, "--dry" in sys.argv
    now = smi()
    base = json.loads(BASE.read_text(encoding="utf-8")) if BASE.exists() else {}
    if not force and base.get("driver") == now["driver"]:
        return 0  # 버전 그대로: 조용히 끝
    results = {}
    for name, fn in (("compute", check_compute), ("nvenc", check_nvenc), ("voice", check_voice)):
        try:
            ok, detail = fn()
        except Exception as e:  # 점검 자체가 죽어도 실패로 보고
            ok, detail = False, f"{type(e).__name__}: {str(e)[:150]}"
        results[name] = {"ok": ok, "detail": detail}
    REQUIRED = ("compute", "voice")  # nvenc는 상태 기록만(파이프라인이 쓰지 않음)
    passed = all(results[k]["ok"] for k in REQUIRED)
    summary = f"드라이버 {base.get('driver', '기록 없음')} → {now['driver']} (CUDA {now['cuda']}): " + ", ".join(
        f"{k} {'통과' if v['ok'] else ('불가(기록만)' if k == 'nvenc' else '실패')}" for k, v in results.items())
    print(summary)
    for k, v in results.items():
        print(f"  {k}: {v['detail']}")
    if dry:
        return 0 if passed else 1
    if passed:
        BASE.write_text(json.dumps({**now, "checked_at": datetime.now().isoformat(timespec="seconds"), "results": results}, ensure_ascii=False, indent=1), encoding="utf-8")
        for to in ("탐", "핏"):
            mail(to, "[GPU 점검] 드라이버 변경 뒤 3종 통과", summary)
        return 0
    fails = "; ".join(f"{k}: {v['detail']}" for k, v in results.items() if not v["ok"] and k in REQUIRED)
    mail("사장님", "GPU 점검 실패: 드라이버 업데이트 뒤", f"{summary}. 실패 내용: {fails}",
         ask="영상·음성 작업 전에 탐에게 '이전 드라이버로 되돌릴지' 알려 주세요")
    mail("탐", "[GPU 점검] 실패", f"{summary}. {fails}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
