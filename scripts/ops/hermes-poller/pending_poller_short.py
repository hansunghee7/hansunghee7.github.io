#!/usr/bin/env python3
"""solar-bible-tasks-poller(dbec1e96eff3)용 얇은 래퍼. 실제 로직은 pending_poller.py --lane pending.
hermes cron --script는 인자를 넘기지 않으므로 줄(lane)마다 래퍼 파일을 따로 둔다.

⚠️ 버전 관리용 사본. 실행본은 헤르메스 홈(C:/Users/PC/AppData/Local/hermes/scripts/)에 있다."""
import runpy
import sys

sys.argv = [sys.argv[0], "--lane", "pending"]
runpy.run_path(str(__import__("pathlib").Path(__file__).with_name("pending_poller.py")), run_name="__main__")
