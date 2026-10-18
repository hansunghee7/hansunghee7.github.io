#!/usr/bin/env python3
"""마야 운전 학습: 비공개 팟캐스트 RSS 관리 (안드로이드 오토용).

사용:
  python scripts/ops/podcast_feed.py init            # 최초 1회: 설정 파일 생성(버킷 이름은 설정에서 읽음)
  python scripts/ops/podcast_feed.py add <mp3> --title T --desc D [--date YYYY-MM-DD]
  python scripts/ops/podcast_feed.py list
  python scripts/ops/podcast_feed.py covers          # 썸네일(thumbs/)을 올려 피드에 연결(새 회차 추가 뒤 make_thumbs.py → covers)
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
SHOWS = {  # 시리즈(재생목록)별 피드. 새 시리즈는 여기 한 줄을 더하고 --show 로 고른다(마야 2026-10-18)
    "drive": ("마야 운전 학습", "운전 중에 귀로 배우는 AI 학습 음성. 개인 비공개 피드."),
    "briefing": ("마야 브리핑", "마야가 정리해 보내는 음성 브리핑. 개인 비공개 피드."),
}
SHOW = "drive"
CHANNEL_TITLE, CHANNEL_DESC = SHOWS[SHOW]


def use_show(show):
    """--show 값에 따라 상태 파일·주소·제목을 바꾼다. 기본(drive)은 옛 경로 그대로."""
    global SHOW, CHANNEL_TITLE, CHANNEL_DESC, EPS, FEED_LOCAL, URL_FILE
    if show not in SHOWS:
        sys.exit("모르는 시리즈: " + show + " (" + ", ".join(SHOWS) + ")")
    SHOW = show
    CHANNEL_TITLE, CHANNEL_DESC = SHOWS[show]
    if show != "drive":
        EPS = STATE / f"episodes_{show}.json"
        FEED_LOCAL = STATE / f"feed_{show}.xml"
        URL_FILE = STATE / f"feed_url_{show}.txt"


def sub():
    return "" if SHOW == "drive" else SHOW + "/"


def chan_key():
    return "channel_image" if SHOW == "drive" else "channel_image_" + SHOW
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
    return f"https://storage.googleapis.com/{c['bucket']}/{c['token']}" + ("" if SHOW == "drive" else "/" + SHOW)


def probe(mp3):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp3)])
    return int(float(r.stdout.strip()))


def hms(sec):
    return f"{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


def build_feed(c, eps):
    b = base(c)
    items = []
    for e in sorted(eps, key=lambda x: x["date"], reverse=True):
        # 같은 날짜 안에서는 회차 번호 순으로 시각을 1분씩 밀어, 앱에서 늦게 올린 회차가 위에 오게 한다
        pub = format_datetime(dt.datetime.fromisoformat(e["date"] + "T07:00:00+09:00") + dt.timedelta(minutes=e["n"]))
        url = f"{b}/{e['file']}"
        img = (chr(10) + '   <itunes:image href="' + b + "/" + e["image"] + '"/>') if e.get("image") else ""
        items.append(f"""  <item>
   <title>{escape(e['title'])}</title>
   <description>{escape(e['desc'])}</description>
   <itunes:summary>{escape(e['desc'])}</itunes:summary>
   <pubDate>{pub}</pubDate>
   <guid isPermaLink="false">{escape(e['id'])}</guid>
   <enclosure url="{url}" length="{e['bytes']}" type="audio/mpeg"/>
   <itunes:duration>{hms(e['seconds'])}</itunes:duration>
   <itunes:episode>{e['n']}</itunes:episode>
   <itunes:explicit>false</itunes:explicit>{img}
  </item>""")
    now = format_datetime(dt.datetime.now(dt.timezone.utc))
    chan_img = ""
    if c.get(chan_key()):
        u = b + "/" + c[chan_key()]
        chan_img = chr(10) + '  <itunes:image href="' + u + '"/>' + chr(10) + "  <image><url>" + u + "</url><title>" + CHANNEL_TITLE + "</title><link>" + b + "/feed.xml</link></image>"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
 <channel>
  <title>{CHANNEL_TITLE}</title>
  <link>{b}/feed.xml</link>
  <description>{CHANNEL_DESC}</description>
  <language>ko</language>
  <lastBuildDate>{now}</lastBuildDate>
  <itunes:author>마야</itunes:author>{chan_img}
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
    gcloud("storage", "cp", str(FEED_LOCAL), f"gs://{c['bucket']}/{c['token']}/{sub()}feed.xml",
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
    gcloud("storage", "cp", str(mp3), f"gs://{c['bucket']}/{c['token']}/{sub()}{fname}",
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
    gcloud("storage", "rm", f"gs://{c['bucket']}/{c['token']}/{sub()}{t[0]['file']}")
    eps = [e for e in eps if e is not t[0]]
    EPS.write_text(json.dumps(eps, ensure_ascii=False, indent=1), encoding="utf-8")
    publish(c, eps)
    print(f"삭제: {a.n}회차")


def cmd_covers(a):
    """C:/work/_ops/podcast/thumbs 의 channel.jpg, ep<n>.jpg 를 올리고 피드에 연결한다(마야 2026-10-18)."""
    c = cfg(); eps = load(EPS, [])
    th = STATE / ("thumbs" if SHOW == "drive" else "thumbs_" + SHOW)
    up = lambda f, name: gcloud("storage", "cp", str(f), f"gs://{c['bucket']}/{c['token']}/{sub()}{name}",
                                "--content-type=image/jpeg", "--cache-control=public, max-age=300")
    if (th / "channel.jpg").exists():
        name = f"cover-channel-{secrets.token_hex(3)}.jpg"; up(th / "channel.jpg", name); c[chan_key()] = name
        CFG.write_text(json.dumps(c), encoding="utf-8")
    n_up = 0
    for e in eps:
        f = th / f"ep{e['n']}.jpg"
        if f.exists():
            name = f"cover-{e['id']}-{secrets.token_hex(3)}.jpg"; up(f, name); e["image"] = name; n_up += 1
    EPS.write_text(json.dumps(eps, ensure_ascii=False, indent=1), encoding="utf-8")
    publish(c, eps)
    print(f"표지 연결: 채널 1 + 회차 {n_up}")


def cmd_url(a):
    publish(cfg(), load(EPS, []))
    print("주소를 feed_url.txt 에 저장함(값은 출력하지 않음)")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--show", default="drive", help="시리즈: " + ", ".join(SHOWS))
    s = p.add_subparsers(dest="cmd", required=True)
    x = s.add_parser("init"); x.add_argument("--bucket"); x.set_defaults(f=cmd_init)
    x = s.add_parser("add"); x.add_argument("mp3"); x.add_argument("--title", required=True)
    x.add_argument("--desc", required=True); x.add_argument("--date"); x.set_defaults(f=cmd_add)
    s.add_parser("list").set_defaults(f=cmd_list)
    s.add_parser("covers").set_defaults(f=cmd_covers)
    x = s.add_parser("remove"); x.add_argument("n"); x.set_defaults(f=cmd_remove)
    s.add_parser("url").set_defaults(f=cmd_url)
    a = p.parse_args(); use_show(a.show); a.f(a)
