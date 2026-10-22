---
name: console-flash-hunt
description: 사장님 모니터에 콘솔(CMD) 창이 떴다 사라진다고 하거나 "ㄱㄱ"·"창"만 보낼 때 사용. 상시 기록기 로그에서 최근 창의 범인(부모→자식)을 찾아 고친다.
---

# 콘솔 창 깜빡임 범인 색출

사장님은 창이 뜨는 동안 타이핑이 안 되므로, PC가 상시 기록기(`scripts/ops/console_flash_logger.py`, 예약 작업 `핏_창기록`)로 스스로 기록한다. 사장님 신고는 "ㄱㄱ"이나 "창" 한 단어면 된다(늦게 보내도 기록에 시각이 남는다).

## 신고를 받으면
- 먼저 `python scripts/ops/console_flash_logger.py --report 10`으로 최근 10분 기록을 본다.
- 창이 1개 이상이면 신고로 읽는다. 범인 후보(부모→자식)를 보고 그 부모 스크립트에서 `subprocess` 호출에 `creationflags=CREATE_NO_WINDOW`를 넣는다(DETACHED_PROCESS는 쓰지 않는다).
- 기록에 창이 0개인데 "ㄱㄱ"이면 "진행하라"는 뜻으로 읽고 하던 일을 잇는다.
- 기록기가 죽어 있으면(`C:/work/_ops/flash_logger.alive`가 10분 넘게 안 갱신) 먼저 예약 작업을 다시 시작한다.

## 고친 뒤
- 같은 작업을 다시 돌리며 `--report 2`로 새 창이 0개인지 확인한다.
- 원인과 고친 파일을 공정 카드 `핏-영상생성`에 남긴다. 상세 절차는 [docs/콘솔창_범인색출_절차.md](../../../docs/콘솔창_범인색출_절차.md).
