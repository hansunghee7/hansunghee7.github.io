#!/usr/bin/env bash
# hx_lite.sh - 신PC(헤르메스 PC)에 업무지시와 읽기만 하는 통로. 마야 등 탐 외 세션용.
# 사장님 결정(2026-09-20): 마야에게도 hx를 열되, 신PC에서 할 수 있는 일은 업무지시와 읽기로 제한.
#   hx_lite.sh cron | ls <경로> | read <경로> [줄수] | ask < 업무지시
# put(스크립트 교체)은 막혀 있다. 이 제한은 관례와 세션 권한 규칙으로 지키는 안전장치이며
# SSH 키 자체를 나눠 주는 것은 아니다(같은 PC의 세션이 ssh를 직접 부르는 것까지 기술적으로 막지는 못함).
# 그래서 마야 세션의 허용 규칙에는 `Bash(bash scripts/hx_lite.sh:*)`만 넣고 ssh 직접 호출은 허용하지 않는다.
HX_MODE=lite exec bash "$(dirname "$0")/hx.sh" "$@"
