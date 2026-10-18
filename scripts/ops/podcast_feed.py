#!/usr/bin/env python3
"""마야 운전 학습: 비공개 팟캐스트 RSS 관리 (안드로이드 오토용).

사용:
  python scripts/ops/podcast_feed.py init            # 최초 1회: 설정 파일 생성(버킷 이름은 설정에서 읽음)
  python scripts/ops/podcast_feed.py add <mp3> --title T --desc D [--date YYYY-MM-DD]
  python scripts/ops/podcast_feed.py list
  python scripts/ops/podcast_feed.py remove <id>
  python scripts/ops/podcast_feed.py url             # 앱에 등록할 주소를 feed_url.txt에 저장(화면 출력 안 함)

저장소: GCS 버킷(공개 읽기, 목록 불가). 경로는 추측 불가한 무작위 토큰.
상태 파일은 저장소 밖 C:/work/_ops/podcast/ 에 둔다(주소·버킷 이름은 비밀 취급, 커밋 금지).
gcloud 계정은 hansunghee7@gmail.com(크레딧 프로젝트). 키 값은 다루지 않는다.
"""
import argparse, json, secrets, subprocess, sys, datetime as dt
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

STATE = Path("C:/work/_ops/podcast")
CFG = STATE / "config.json"
EPS = STATE / "episodes.json"
FEED_LOCAL = STATE / "feed.xml"
URL_FILE = STATE / "feed_url.txt"
ACCOUNT = "hansunghee7@gmail.com"
PROJECT = "project-e59cbc25-e96a-44f5-ac6"
CHANNEL_TITLE = "마야 운전 학습"
CHANNEL_DESC = "운전 중에 귀로 배우는 AI 학습 음성. 개인 비공개 피드."
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def run(args, **kw):
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                          creationflags=NO_WINDOW, **kw)


def gcloud(*a):
    r = run(["gcloud", *a, f"--account={ACCOUNT}", f"--project={PROJECT}"], shell=(sys.platform == "win32"))
    if r.returncode != 0:
        sys.exit("gcloud 실패: " + (r.stderr or r.stdout)[-400:])
    return r.stdout


def load(p, default):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def cfg():
    c = load(CFG, None)
    if not c:
        sys.exit("설정 없음: C:/work/_ops/podcast/config.json (bucket, token)")
    return c


def base(c):
    return f"https://storage.googleapis.com/{c['bucket']}/{c['token']}"


def probe(mp3):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp3)])
    return int(float(r.stdout.strip()))


def hms(sec):
    return f"{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


def build_feed(c, eps):
    b = base(c)
    items = []
    for e in sorted(eps, key=lambda x: x["date"], reverse=True):
        pub = format_datetime(dt.datetime.fromisoformat(e["date"] + "T07:00:00+09:00"))
        url = f"{b}/{e['file']}"
        items.append(f"""  <item>
   <title>{escape(e['title'])}</title>
   <description>{escape(e['desc'])}</description>
   <itunes:summary>{escape(e['desc'])}</itunes:summary>
   <pubDate>{pub}</pubDate>
   <guid isPermaLink="false">{escape(e['id'])}</guid>
   <enclosure url="{url}" length="{e['bytes']}" type="audio/mpeg"/>
   <itunes:duration>{hms(e['seconds'])}</itunes:duration>
   <itunes:episode>{e['n']}</itunes:episode>
   <itunes:explicit>false</itunes:explicit>
  </item>""")
    now = format_datetime(dt.datetime.now(dt.timezone.utc))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
 <channel>
  <title>{CHANNEL_TITLE}</title>
  <link>{b}/feed.xml</link>
  <description>{CHANNEL_DESC}</description>
  <language>ko</language>
  <lastBuildDate>{now}</lastBuildDate>
  <itunes:author>마야</itunes:author>
  <itunes:summary>{CHANNEL_DESC}</itunes:summary>
  <itunes:explicit>false</itunes:explicit>
  <itunes:block>yes</itunes:block>
  <itunes:category text="Education"/>
{chr(10).join(items)}
 </channel>
</rss>
"""


def publish(c, eps):
    xml = build_feed(c, eps)
    FEED_LOCAL.write_text(xml, encoding="utf-8")
    gcloud("storage", "cp", str(FEED_LOCAL), f"gs://{c['bucket']}/{c['token']}/feed.xml",
           "--content-type=application/rss+xml; charset=utf-8", "--cache-control=public, max-age=300")
    URL_FILE.write_text(f"{base(c)}/feed.xml\n", encoding="utf-8")


def cmd_init(a):
    STATE.mkdir(parents=True, exist_ok=True)
    if CFG.exists():
        return print("이미 설정됨")
    bucket = a.bucket or sys.exit("--bucket 필요(비밀 취급)")
    CFG.write_text(json.dumps({"bucket": bucket, "token": secrets.token_urlsafe(24).replace("_", "x").replace("-", "y")}), encoding="utf-8")
    print("설정 생성")


def cmd_add(a):
    c = cfg(); eps = load(EPS, [])
    mp3 = Path(a.mp3)
    if not mp3.exists():
        sys.exit("mp3 없음")
    n = max([e["n"] for e in eps] + [0]) + 1
    eid = f"maya-drive-{n:03d}-{secrets.token_hex(4)}"
    fname = f"{eid}.mp3"
    gcloud("storage", "cp", str(mp3), f"gs://{c['bucket']}/{c['token']}/{fname}",
           "--content-type=audio/mpeg", "--cache-control=public, max-age=86400")
    eps.append({"n": n, "id": eid, "file": fname, "title": a.title, "desc": a.desc,
                "date": a.date or dt.date.today().isoformat(),
                "bytes": mp3.stat().st_size, "seconds": probe(mp3)})
    EPS.write_text(json.dumps(eps, ensure_ascii=False, indent=1), encoding="utf-8")
    publish(c, eps)
    print(f"추가: {n}회차 {a.title} ({hms(eps[-1]['seconds'])})")


def cmd_list(a):
    for e in sorted(load(EPS, []), key=lambda x: x["n"]):
        print(f"{e['n']}\t{e['date']}\t{hms(e['seconds'])}\t{e['title']}")


def cmd_remove(a):
    c = cfg(); eps = load(EPS, [])
    t = [e for e in eps if str(e["n"]) == a.n]
    if not t:
        sys.exit("해당 회차 없음")
    gcloud("storage", "rm", f"gs://{c['bucket']}/{c['token']}/{t[0]['file']}")
    eps = [e for e in eps if e is not t[0]]
    EPS.write_text(json.dumps(eps, ensure_ascii=False, indent=1), encoding="utf-8")
    publish(c, eps)
    print(f"삭제: {a.n}회차")


def cmd_url(a):
    publish(cfg(), load(EPS, []))
    print("주소를 feed_url.txt 에 저장함(값은 출력하지 않음)")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    s = p.add_subparsers(dest="cmd", required=True)
    x = s.add_parser("init"); x.add_argument("--bucket"); x.set_defaults(f=cmd_init)
    x = s.add_parser("add"); x.add_argument("mp3"); x.add_argument("--title", required=True)
    x.add_argument("--desc", required=True); x.add_argument("--date"); x.set_defaults(f=cmd_add)
    s.add_parser("list").set_defaults(f=cmd_list)
    x = s.add_parser("remove"); x.add_argument("n"); x.set_defaults(f=cmd_remove)
    s.add_parser("url").set_defaults(f=cmd_url)
    a = p.parse_args(); a.f(a)
