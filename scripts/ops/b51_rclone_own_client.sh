#!/usr/bin/env bash
# B51: 구PC rclone 구글드라이브 연결을 공용 client_id에서 우리 것으로 바꾼다(2026-10-03 탐, 사장님 승인 1번: 탐이 값 미출력으로 옮김 + 사장님 동의 클릭).
# 왜: rclone 공용 client_id가 2026년 중 중단된다는 경고("shared Google Drive client_id ... being retired"). 구PC의 인사이트 DB·비공개 저장소 백업·Pass 폴더 마운트가 전부 이 연결을 쓴다.
# 무엇으로: 10/1 유튜브 수집용으로 만든 구글 클라우드 프로젝트(Default Gemini Project, 동의 화면 "Carvit Insight" 프로덕션 게시)의 데스크톱 OAuth 클라이언트를 재사용. 드라이브 API는 10/3 켬.
# 비밀값: 클라이언트 ID·비밀번호는 C:/work/_ops/yt_oauth/token.json에서 읽어 ssh 표준입력으로만 넘긴다. 화면·로그·명령줄에 찍지 않는다.
#
# 사용:
#   bash scripts/ops/b51_rclone_own_client.sh check     # 사전 점검만(아무것도 안 바꿈)
#   bash scripts/ops/b51_rclone_own_client.sh start     # 백업 → 키 교체 → 동의 주소 출력(사장님이 브라우저에서 허용할 때까지 대기)
#   bash scripts/ops/b51_rclone_own_client.sh consent   # 동의 주소만 다시 받기(키 교체는 건드리지 않음)
#   bash scripts/ops/b51_rclone_own_client.sh verify    # 경고 없이 목록이 읽히는지, 마운트 다시 걸기
#   bash scripts/ops/b51_rclone_own_client.sh rollback  # 백업본으로 되돌림(공용 client_id가 살아 있는 동안은 그대로 다시 동작)
set -u
TOKEN_JSON="C:/work/_ops/yt_oauth/token.json"
H=goosolar; R='$HOME/.local/bin/rclone'; CONF='$HOME/.config/rclone/rclone.conf'; BAK='$HOME/.config/rclone/rclone.conf.bak_b51'
PORT=53682  # rclone 동의 받는 기본 통로. ssh로 신PC 127.0.0.1:53682 → 구PC로 이어 준다.

case "${1:-check}" in
check)
  python -c "import json;d=json.load(open('$TOKEN_JSON',encoding='utf-8'));assert d.get('client_id') and d.get('client_secret');print('키 파일 OK(값 미출력)')" || exit 1
  ssh -o BatchMode=yes $H "$R version | head -1; test -f $CONF && echo conf OK; $R listremotes; (ss -ltn 2>/dev/null | grep -q ':$PORT ' && echo '구PC 통로 $PORT 사용 중(다른 프로그램)' || echo '구PC 통로 $PORT 비어 있음')" || exit 1
  (netstat -ano 2>/dev/null | grep -q "127.0.0.1:$PORT .*LISTENING" && echo "신PC 통로 $PORT 사용 중" || echo "신PC 통로 $PORT 비어 있음")
  ;;
start)
  # 백업은 한 번만: 다시 실행해도 원래 설정 백업을 덮어쓰지 않는다(10/3 실측: 재실행하면 되돌릴 원본이 사라질 뻔함).
  ssh -o BatchMode=yes $H "test -f $BAK && echo '백업 이미 있음(덮어쓰지 않음)' || (cp $CONF $BAK && echo 백업 완료)" || exit 1
  # 키 교체: 값은 표준입력으로만. rclone.conf의 [gdrive]에 client_id·client_secret을 넣는다.
  python -c "import json;d=json.load(open('$TOKEN_JSON',encoding='utf-8'));print(json.dumps({'i':d['client_id'],'s':d['client_secret']}))" | ssh -o BatchMode=yes $H 'python3 -c "
import json,sys,configparser,os
k=json.load(sys.stdin); p=os.path.expanduser(\"~/.config/rclone/rclone.conf\")
c=configparser.RawConfigParser(); c.optionxform=str; c.read(p)
c.set(\"gdrive\",\"client_id\",k[\"i\"]); c.set(\"gdrive\",\"client_secret\",k[\"s\"])
c.write(open(p,\"w\")); print(\"키 교체 완료(값 미출력)\")
"' || { echo "키 교체 실패 → rollback 하세요"; exit 1; }
  exec bash "$0" consent
  ;;
consent)
  # 동의만 다시 받는다(키 교체는 건드리지 않음). 출력은 줄 단위로 바로 내보낸다:
  # 10/3 실측에서 grep이 출력을 모아 두는 바람에 동의 주소가 화면에 안 나왔다.
  echo "아래에 'http://127.0.0.1:$PORT/auth?state=...' 주소가 나옵니다. Ctrl을 누른 채 클릭하고 구글에서 허용하면 이 명령이 스스로 끝납니다."
  ssh -o BatchMode=yes $H "pkill -f '[r]clone config reconnect' 2>/dev/null; sleep 1; true"
  # -L: 신PC의 53682를 구PC 53682로. 구PC에는 화면이 없어 브라우저 자동 열기는 실패하고 주소만 찍힌다(정상).
  ssh -o BatchMode=yes -L $PORT:127.0.0.1:$PORT $H "$R config reconnect gdrive: --auto-confirm 2>&1 | grep --line-buffered -o -E 'http://127\.0\.0\.1:$PORT/auth[^ ]*|Success|Error.*|Failed.*|[Cc]ouldn.t.*'"
  ;;
verify)
  ssh -o BatchMode=yes $H "$R lsd gdrive: --max-depth 1 2>&1 | head -5; echo ---; $R lsd gdrive: 2>&1 | grep -c 'being retired' | sed 's/^/경고 줄 수: /'; (fusermount -u \$HOME/carvit-pass/ag-test 2>/dev/null; $R mount gdrive:'새김Pass/ag-test' \$HOME/carvit-pass/ag-test --vfs-cache-mode writes --vfs-cache-max-age 24h --dir-cache-time 1m --daemon && ls \$HOME/carvit-pass/ag-test | head -3)"
  ;;
rollback)
  ssh -o BatchMode=yes $H "cp $BAK $CONF && echo 되돌림 완료 && $R lsd gdrive: --max-depth 1 2>&1 | head -3"
  ;;
*) echo "check | start | consent | verify | rollback"; exit 64;;
esac
