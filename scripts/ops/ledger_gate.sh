#!/usr/bin/env bash
# 비티·덱스 호출 관문(2026-10-19 사장님 "비티와 덱스가 업무대장을 관리하도록 관문을 넣으세요", 공정 카드 탐#162 연속성 5종).
# 왜: 두 모델은 호출형이라 문서는 부르는 쪽이 만들어야 하는데, 업무대장이 10/03 이후 서 있었다. 문서 규칙은 세션이 바뀌면 빠지므로 호출 입구에서 막는다(CLAUDE#4e7b).
# 규칙: 호출 카드 맨 위쪽에 "업무대장: BT<번호>"(비티) 또는 "업무대장: DX<번호>"(덱스) 한 줄이 있어야 하고,
#       그 번호가 해당 대장 문서의 제목줄(### [상태] BT12: ...)로 실재해야 한다.
# 행 만들기: python scripts/ops/ledger_row.py add bt|dex "제목" --next "다음 행동"  (번호가 출력된다, 워크트리에서 만들고 PR로 병합)
# 우회: LEDGER_GATE=off (긴급용, ledger_gate_bypass.log에 기록). 기존 시험은 LEDGER_GATE=off로 돈다.
# 사용: source "$(dirname "$0")/ledger_gate.sh"; ledger_gate bt|dex <카드파일>
ledger_gate() {  # ledger_gate <bt|dex> <카드>
  local agent="$1" card="$2" pfx doc id root
  case "$agent" in
    bt) pfx=BT; doc="비티_$(printf '\xec\x97\x85\xeb\xac\xb4')대장.md" ;;
    dex) pfx=DX; doc="덱스_$(printf '\xec\x97\x85\xeb\xac\xb4')대장.md" ;;
    *) echo "ledger_gate: 알 수 없는 에이전트 $agent" >&2; return 2 ;;
  esac
  if [ "${LEDGER_GATE:-on}" = off ]; then
    echo "$(date '+%F %T') $agent $card" >> "${LEDGER_GATE_LOG:-/c/work/_ops/ledger_gate_bypass.log}" 2>/dev/null || true
    return 0
  fi
  root="${LEDGER_DOCS_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../docs" && pwd)}"
  id="$(head -40 "$card" 2>/dev/null | grep -Eo "업무대장[[:space:]]*:[[:space:]]*${pfx}[0-9]+" | head -1 | grep -Eo "${pfx}[0-9]+" || true)"
  if [ -z "$id" ]; then
    echo "업무대장 관문: 카드 맨 위쪽에 '업무대장: ${pfx}<번호>' 한 줄이 없습니다. 먼저 행을 만드세요: python scripts/ops/ledger_row.py add $agent \"제목\" --next \"다음 행동\"" >&2
    return 4
  fi
  if ! grep -Eq "^###[[:space:]]*\[[^]]*\][[:space:]]*${id}:" "$root/$doc"; then
    echo "업무대장 관문: $id 행이 $doc 에 없습니다. ledger_row.py add 로 만든 뒤 다시 부르세요." >&2
    return 4
  fi
  return 0
}
