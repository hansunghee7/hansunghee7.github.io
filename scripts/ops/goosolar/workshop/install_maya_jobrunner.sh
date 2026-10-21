#!/bin/bash
# 마야 작업서 실행기 크론 설치(5분마다). 한 번만 실행한다. 다시 실행해도 한 줄만 남는다.
set -e
L="*/5 * * * * cd \$HOME/workshop && venv/bin/python maya_jobrunner.py >> out/maya/jobrunner.log 2>&1 # maya-jobrunner"
(crontab -l 2>/dev/null | grep -v "# maya-jobrunner"; echo "$L") | crontab -
crontab -l | grep maya-jobrunner
