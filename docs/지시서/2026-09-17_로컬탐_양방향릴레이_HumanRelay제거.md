# TASK: 양방향 Agent Relay 구조 개선 및 Human Relay 제거

발신: 탐(클라우드) / 수신: 탐(로컬) — 2026-09-17 야간, 사장님 전달

> 이 지시서를 받은 세션 컨텍스트가 69%(70% 자체 기준선)에 도달해
> 즉시 착수하지 않고 저장만 해뒀다(CLAUDE.md §d78e "70% 넘으면
> 저녁 의식으로" 원칙 적용). **다음 새 세션이 여기서부터 시작할 것.**
> 아래 원문은 사장님이 붙여넣은 내용을 그대로 옮긴 것이며, 마지막
> 코드 블록이 닫히지 않은 채로 끝난 것으로 보아 원문이 더 있었을
> 수 있다 — 착수 전에 사장님께 이어지는 내용이 더 있는지 확인할 것.

## Objective

현재 Claude Cloud ↔ 로컬 Hermes Agent 간 통신에서
성희님이 메시지를 복사/전달하는 Human Relay가 발생하지 않도록
자동화 구조를 개선한다.

현재 확인된 상태:

- Cloud → Local 방향:
  Git commit → relay-watcher → Telegram → 신솔라
  현재 약 1분 이내로 전달되는 실측 사례가 존재함.
- Local → Cloud 방향:
  로컬 탐/마야의 결과를 Cloud Claude 세션이 직접 읽을 수 없어
  현재 성희님이 중간 전달자 역할을 하고 있음.

최종 목표:

Human Relay = 0

단, "실시간 자동 전달"과 "다음 세션에서 자동 수신"을
구분하여 실제 가능한 수준까지만 구현한다.

---

## 1. 절대 원칙

구현 전에 현재 Hermes/Claude Code/GitHub/relay-watcher 구조를 조사한다.

다음 순서를 반드시 지킨다.

INSPECT
→ REUSE
→ EXTEND
→ CUSTOM

이미 Hermes에 존재하는 기능을 새 시스템으로 중복 구현하지 않는다.

특히 먼저 확인할 것:

- Hermes Telegram inbound
- Gateway Hooks
- Plugin Hooks
- `agent:start`
- `on_stream_end`
- Outbound Webhooks
- Webhook adapter
- `ctx.inject_message`
- GitHub integration
- 현재 relay-watcher

공식적으로 지원되는 기능이 있다면 그것을 우선 사용한다.

---

## 2. 현재 구조 진단

현재 relay-watcher를 분석한다.

확인할 것:

1. 정확히 어떤 이벤트를 감지하는가?
2. Git commit → Telegram latency를 어떻게 측정하는가?
3. 중복 이벤트 방지 방식은 무엇인가?
4. 실패 시 재시도하는가?
5. 현재 Telegram 메시지의 source/destination을 식별할 수 있는가?
6. Local Agent의 결과가 생성되는 최초 지점은 어디인가?

현재 확인된 사례의 latency는 약 1분이지만
이를 시스템의 평균 성능으로 가정하지 않는다.

최소 20건의 이벤트를 측정할 수 있는 구조를 만든다.

측정값:

- source timestamp
- relay timestamp
- Telegram delivery timestamp
- latency
- success/failure

그리고:

- average
- median
- p95

를 산출한다.

---

## 3. 중요한 설계 원칙

### Telegram을 Agent-to-Agent 작업 원장으로 사용하지 않는다.

권장 canonical flow:

#### Cloud → Local

GitHub
→ relay-watcher
→ Telegram notification
→ 신솔라

#### Local → Cloud

Local Agent
→ GitHub / Shared Inbox
→ Cloud Claude

즉:

GitHub = durable state / artifact / handoff

Telegram = notification / human interface

로 역할을 분리한다.

---

## 4. Local → Cloud 경로 구현

먼저 Telegram을 경유할 필요가 없는지 조사한다.

Local Hermes Agent에서 결과가 생성되는 지점을 확인한다.

가능하면 Hermes의 기존 hook을 사용한다.

후보:

- `on_stream_end`
- Gateway hook
- `agent:end`
- 기타 공식 hook

Local Agent의 최종 결과를:

`reports/incoming/`
또는
기존 프로젝트에서 이미 정한 canonical inbox

에 구조화된 형태로 기록한다.

예:

```markdown
# Relay Event

event_id:
timestamp:
source:
destination:
task_id:
status:

## Summary

...

## Required Action

...

## Evidence

...

## Source Session

...
```

(※ 사장님 원문이 여기서 끝남 — 이어지는 내용이 더 있었을 가능성 있음,
착수 전 확인 필요)

---

## 이 세션(로컬 탐, 2026-09-17 야간)이 이미 확보해둔 관련 사실

재조사 방지용으로 오늘 밤 이미 확인된 것들을 남긴다:

- **relay-watcher 현재 구현**: `AppData/Local/hermes/scripts/relay_watcher.py`.
  정규식으로 `docs/진행상황.md`의 `📥 탐(클라우드) → ... 로컬 ...` 추가된
  라인만 감지(git diff 기반, LLM 호출 없음). 상태는
  `relay_watcher_state.json`(마지막 처리 SHA)만 기록 — **latency
  타임스탬프·성공/실패 로그는 현재 안 남김**(2절이 요구하는 측정
  인프라가 없다는 뜻, 처음부터 만들어야 함). 크론 주기는 10분이지만
  실측 latency는 1~8분으로 관측됨(정확한 배포 매커니즘 불명 - 왜
  10분 미만으로도 오는지는 조사 안 됨, 2절 진단 대상).
- **카카오톡 직접 알림**: relay-watcher와 별개로, 탐(클라우드)이
  `📥` 작성 시점에 카카오톡 "나에게 보내기"를 병행 발송하는 것도
  오늘 밤 검증 완료(1~3분 지연). 이것도 "Telegram을 원장으로 안 쓴다"
  원칙과 같은 방향 — 사람 알림 채널이지 agent-to-agent 채널 아님.
- **텔레그램 Claude Code 커넥터는 없음**: MCP 레지스트리에 Telegram
  connector가 없어, 클라우드 세션이 텔레그램을 "읽는" 것은 지금
  구조로 불가능(카카오톡은 커넥터가 있어 "보내기"만 가능). 4절의
  "Local → Cloud, Telegram 경유 안 함" 방향과 일치 — 애초에 클라우드가
  텔레그램을 못 읽으니 잘된 설계 판단이다.
- **git worktree 격리 적용 완료**: 워킹 디렉토리 공유 충돌 문제는
  오늘 밤 별도로 해결됨(`docs/로컬_에이전트_작업영역.md`,
  Claude Code 내장 `EnterWorktree` 사용). 이 지시서 작업할 때도
  이 방식으로 격리된 워크트리에서 진행할 것을 권장.
- **cxo-db #106/#113/#115**: 오늘 3번째 재발 사례가 이 지시서를
  촉발한 배경.
