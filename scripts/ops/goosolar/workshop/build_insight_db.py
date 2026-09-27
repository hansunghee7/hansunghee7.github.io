"""N70 PoC: 구PC(goosolar)가 수집한 SNS jsonl을 SQLite로 합쳐 구글드라이브에 올린다.

단일 writer 전제(구PC 크론에서만 실행). 다른 세션은 Drive에서 읽기만 한다.
스키마는 아직 followers_daily·content_items 2테이블뿐 — 크롬 확장 격차 항목
(유튜브·X·Claude 사용량 등)은 다음 라운드에서 추가할 것(탐_업무대장.md N70).
"""
import glob
import json
import os
import sqlite3
import subprocess

SRC = os.path.expanduser("~/workshop/out/sns")
DB = os.path.expanduser("~/workshop/insight.db")
DRIVE_DEST = "gdrive:인사이트-데이터/"
RCLONE = os.path.expanduser("~/.local/bin/rclone")


def build():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.executescript(
        """
        DROP TABLE IF EXISTS followers_daily;
        DROP TABLE IF EXISTS content_items;
        CREATE TABLE followers_daily(
          date TEXT, platform TEXT, followers INTEGER, following INTEGER,
          likes INTEGER, login_wall INTEGER, port INTEGER,
          PRIMARY KEY(date, platform)
        );
        CREATE TABLE content_items(
          date TEXT, platform TEXT, item_id TEXT, views INTEGER,
          likes INTEGER, comments INTEGER, url TEXT,
          PRIMARY KEY(date, platform, item_id)
        );
        """
    )

    n_follow = n_items = 0
    for path in sorted(glob.glob(os.path.join(SRC, "*.jsonl"))):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                cur.execute(
                    "INSERT OR REPLACE INTO followers_daily VALUES (?,?,?,?,?,?,?)",
                    (
                        row.get("date"),
                        row.get("key"),
                        row.get("followers"),
                        row.get("following"),
                        row.get("likes"),
                        int(bool(row.get("login_wall"))),
                        row.get("port"),
                    ),
                )
                n_follow += 1
                for item in row.get("items", []) or []:
                    cur.execute(
                        "INSERT OR REPLACE INTO content_items VALUES (?,?,?,?,?,?,?)",
                        (
                            row.get("date"),
                            row.get("key"),
                            item.get("id"),
                            item.get("views"),
                            item.get("likes"),
                            item.get("comments"),
                            item.get("url"),
                        ),
                    )
                    n_items += 1

    con.commit()
    cur.execute("SELECT COUNT(*) FROM followers_daily")
    fc = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM content_items")
    ic = cur.fetchone()[0]
    con.close()
    print(f"followers_daily rows={fc} (source lines={n_follow}), content_items rows={ic} (source items={n_items})")


def upload():
    subprocess.run([RCLONE, "copy", DB, DRIVE_DEST], check=True)


if __name__ == "__main__":
    build()
    upload()
