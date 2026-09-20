#!/usr/bin/env python3
"""Golden Test (정적 층): CLAUDE.md 구조 개편 전후로 "규칙이 사라지지 않았는지" 기계적으로 비교한다.

왜 만들었나: CLAUDE.md를 줄이면 줄 수는 쉽게 줄지만, 필요한 규칙이 어디에서도 안 읽히게 될 위험이 있다.
모델 행동 시험(동적 층, docs/claude_md_golden_test.md)은 비싸고 흔들리므로, 규칙의 존재와 도달 가능성은
이 스크립트가 값싸게 결정적으로 확인한다. 이 스크립트는 LLM을 쓰지 않는다(토큰 0).

두 가지 표면:
  ALWAYS = 모든 세션에 상시 로드되는 것 = CLAUDE.md + paths 없는 .claude/rules + 스킬 frontmatter(name, description)
  REACH  = 도달 가능한 것 = ALWAYS + 스킬·rule 본문 + 그것들이 링크한 문서(1홉, 상태·역사 문서는 제외)
사실(fact) 수준:
  A = 핵심 불변식·진입점. 개편 후에도 ALWAYS에 남아야 한다.
  R = 절차·세부. 개편 후 REACH 어디에든 있으면 된다(이동 허용).
  N = 있으면 안 되는 낡은 표현(REACH 전체에서 검색).
사용: python scripts/golden_test_claude_md.py [--json] [--verbose]   종료코드 1 = FAIL 있음
"""
import glob
import json
import os
import re
import sys

ROOT = os.environ.get("GOLDEN_ROOT") or os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
EXTERNAL = [r"C:\work\simplifier-cxo-db\standards\simplifier-way.md"]  # 있으면 REACH에 포함
# 상태·역사 문서는 "규칙이 거기 있다"로 세지 않는다(우연히 문구가 걸려 통과하는 것을 막는다)
REACH_EXCLUDE = re.compile(
    r"docs[\\/](진행상황|진행상황_아카이브|지시서|산출물_인덱스|CLAUDE_md_근거_이력|CLAUDE_md_구조최적화_Phase2_설계|claude_md_golden_test)"
)


def read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def frontmatter(text):
    m = re.match(r"---\r?\n(.*?)\r?\n---", text, re.S)
    return m.group(1) if m else ""


def has_paths(fm):
    return re.search(r"^paths\s*:", fm, re.M) is not None


def build_surfaces():
    claude = read(os.path.join(ROOT, "CLAUDE.md"))
    always = [claude]
    bodies = [claude]
    sources = ["CLAUDE.md"]
    for p in sorted(glob.glob(os.path.join(ROOT, ".claude", "skills", "**", "*.md"), recursive=True)):
        t = read(p)
        fm = frontmatter(t)
        if os.path.basename(p) == "SKILL.md":
            always.append(fm)
        bodies.append(t)
        sources.append(os.path.relpath(p, ROOT))
    for p in sorted(glob.glob(os.path.join(ROOT, ".claude", "rules", "**", "*.md"), recursive=True)):
        t = read(p)
        if not has_paths(frontmatter(t)):
            always.append(t)
        bodies.append(t)
        sources.append(os.path.relpath(p, ROOT))
    link_re = re.compile(r"(?:docs|insight-7b3e9f2c|scripts|\.github)[\\/][\w가-힣_\-./\\]+?\.(?:md|py|yml)")
    linked = set()
    for t in bodies:
        for m in link_re.findall(t):
            linked.add(m.replace("\\", "/"))
    for rel in sorted(linked):
        if REACH_EXCLUDE.search(rel):
            continue
        t = read(os.path.join(ROOT, rel))
        if t:
            bodies.append(t)
            sources.append(rel)
    for ext in EXTERNAL:
        t = read(ext)
        if t:
            bodies.append(t)
            sources.append(ext)
    # 줄바꿈 때문에 문구가 갈라져 불합격하는 것을 막기 위해 공백을 한 칸으로 합친다
    def norm(parts):
        return re.sub(r"\s+", " ", "\n".join(parts))

    return norm(always), norm(bodies), sources


# (시나리오, 수준, 정규식, 설명)
FACTS = [
    ("S01 일반 코드 수정", "A", r"main에 직접 push", "main 직접 push 금지"),
    ("S01 일반 코드 수정", "A", r"auto-merge", "PR + auto-merge 경로"),
    ("S01 일반 코드 수정", "R", r"git fetch origin --prune", "세션 시작 시 원격 확인"),
    ("S01 일반 코드 수정", "R", r"병합된 브랜치는 삭제", "병합 후 브랜치 삭제"),
    ("S02 문서 수정", "A", r"공개 저장소", "공개 저장소 인식"),
    ("S02 문서 수정", "A", r"simplifier-cxo-db", "비공개 저장소 구분"),
    ("S02 문서 수정", "A", r"공개 커밋.{0,20}왜|\"왜\"를 쓰지", "공개 커밋에 '왜' 금지"),
    ("S02 문서 수정", "R", r"긴 줄표", "긴 줄표 금지"),
    ("S03 파일 생성·수정", "A", r"산출물_인덱스", "합의 산출물 인덱스 등록"),
    ("S03 파일 생성·수정", "R", r"새 세션이 찾을 수 있는가", "산출물 회수 판정 기준"),
    ("S03 파일 생성·수정", "R", r"폴더 이름이 공개 저장소에 그대로 보이므로", "insight 폴더 자물쇠 경고"),
    ("S04 테스트·빌드", "A", r"DONE = VERIFIED", "완료 = 증거"),
    ("S04 테스트·빌드", "A", r"EVIDENCE", "증거 단계"),
    ("S04 테스트·빌드", "R", r"build-check", "빌드 검사"),
    ("S05 글쓰기", "A", r"ink-desk", "글 작업 진입 스킬"),
    ("S05 글쓰기", "R", r"퍼스널_브랜딩_가이드", "화법 가이드"),
    ("S05 글쓰기", "R", r"WRITING_GUIDE", "장문 문체 가이드"),
    ("S05 글쓰기", "R", r"컨펌 ①②③", "컨펌 3회 구조"),
    ("S06 Studio 작업", "A", r"insight-7b3e9f2c", "Studio 폴더 진입점"),
    ("S06 Studio 작업", "R", r"check_studio_style\.py", "작업 후 검사 스크립트"),
    ("S06 Studio 작업", "R", r"shorts-studio\.html", "파이프라인이 덮어쓰는 파일 경고"),
    ("S07 Shorts 작업", "A", r"shorts-lab", "숏폼 저장소 진입점"),
    ("S07 Shorts 작업", "R", r"add_repo", "작업 전 저장소 부착"),
    ("S07 Shorts 작업", "R", r"다크 런칭", "채널명 대외 노출 금지"),
    ("S08 Hermes 위임", "A", r"헤르메스|Hermes", "Hermes 위임 원칙"),
    ("S08 Hermes 위임", "A", r"EXECUTE.{0,6}OBSERVE.{0,6}VERIFY.{0,6}RETRY", "Hermes 역할 분리"),
    ("S08 Hermes 위임", "R", r"계정 생성/최초 인증", "위임 금지: 계정 생성"),
    ("S08 Hermes 위임", "R", r"비밀값의 직접 입력", "위임 금지: 비밀값"),
    ("S08 Hermes 위임", "R", r"최대 3회", "재시도 상한"),
    ("S08 Hermes 위임", "R", r"헤르메스를 호출할 채널이 없습니다", "원격 세션 한계 보고 규칙"),
    ("S09 배포 사고", "A", r"deploy-incident", "배포 사고 진입 스킬"),
    ("S09 배포 사고", "R", r"revert", "revert 복구"),
    ("S10 노출 변경", "A", r"exposure-change", "노출 변경 진입 스킬"),
    ("S10 노출 변경", "R", r"노출-승인", "승인 태그"),
    ("S10 노출 변경", "R", r"noindex", "노출 판정 대상"),
    ("S11 세션 시작", "A", r"하이~", "아침 의식 개시어"),
    ("S11 세션 시작", "R", r"새 세션으로 시작", "어제 세션 이어받기 금지"),
    ("S11 세션 시작", "R", r"요약하지 말고 그대로 출력", "인수인계 블록 원문 출력"),
    ("S11 세션 시작", "R", r"전체 공지", "공지 확인"),
    ("S11 세션 시작", "R", r"우편함", "우편함 확인"),
    ("S12 세션 종료", "A", r"바이~", "저녁 의식 개시어"),
    ("S12 세션 종료", "R", r"push까지 끝나야", "push까지 마감"),
    ("S12 세션 종료", "R", r"산출물 회수", "산출물 회수"),
    ("S12 세션 종료", "R", r"손대지 말 것", "인수인계 템플릿 항목"),
    ("S12 세션 종료", "R", r"아카이브", "세션 종료 후 닫기"),
    ("S13 독립 검수", "A", r"서브에이전트", "검토 단계 서브에이전트"),
    ("S13 독립 검수", "R", r"페이블을 생각 없이", "페이블 서브에이전트 금지"),
    ("S13 독립 검수", "R", r"사장님 컨펌을 받은 뒤에만", "상위 모델 사전 컨펌"),
    ("S13 독립 검수", "R", r"하이쿠가\s*기본", "리서치는 하이쿠"),
    ("S13 독립 검수", "A", r"무료 엔진.{0,60}판정.{0,40}쓰지 않는다", "무료·로컬 엔진은 판정에 쓰지 않는다(2026-09-20 확정)"),
    ("S14 승인·확정", "A", r"마야 형식", "결정 요청 형식"),
    ("S14 승인·확정", "R", r"--ask", "결정 알림 명령"),
    ("S14 승인·확정", "A", r"직접 내리게", "핵심 결정은 사장님이"),
    ("S14 승인·확정", "A", r"검증 자체가 되돌리기 어려운 리스크", "위험한 실험 금지"),
    ("X 공통 불변식", "A", r"튜터 원칙", "튜터 원칙"),
    ("X 공통 불변식", "A", r"컴맹 기준", "사장님 손 절차는 컴맹 기준"),
    ("X 공통 불변식", "A", r"20줄 한 장", "설명 형식"),
    ("X 공통 불변식", "A", r"인박스", "경험DB 인박스 기록"),
    ("X 공통 불변식", "A", r"Artifact|아티팩트", "읽을 문서는 링크/아티팩트로"),
    ("X 공통 불변식", "A", r"카카오톡.{0,20}사용하지 않", "카카오톡 사용 중지(외부 발신 정책)"),
    ("X 공통 불변식", "A", r"개시어 없이 세션을 닫더라도", "바이~ 없이 끝나는 세션도 산출물 회수·push"),
    ("X 공통 불변식", "A", r"push까지", "push까지 마감"),
    ("X 공통 불변식", "A", r"system-map\.html", "인프라 변경 시 시스템 구조 페이지 갱신"),
    ("X 공통 불변식", "A", r"작업 완료를 보고하기 전에", "경험DB 기록 트리거 원문"),
    ("X 공통 불변식", "A", r"CLAUDE#<id>", "커밋 인용 태그(새김 측정 데이터원)"),
    ("X 공통 불변식", "A", r"위임 가능 여부부터 판단", "로컬 실행은 위임 가능 여부부터"),
    ("X 공통 불변식", "A", r"내부 에이전트.{0,40}교체 예외", "내부 에이전트 노출은 자격증명 교체 예외(2026-09-20 지시)"),
    ("X 공통 불변식", "A", r"주기 작업.{0,80}감시 대장", "주기 작업은 1회 실행 증거 후 감시 대장에 등록"),
    ("X 공통 불변식", "A", r"사장님께 드리는 보고.{0,60}새김 `?lookup`?을 먼저", "사장님 보고는 새김 조회가 먼저(2026-09-20 지시)"),
    # 마야 실사 실패 케이스 A~F (ink 스킬 흐름)
    ("M-A 글 관련 요청 진입", "A", r"블로그·SNS 글 작업", "ink-desk 설명이 상시 로드에 있음"),
    ("M-B ink-desk 진입", "R", r"세션당 한 번, 가장 먼저 연다", "ink-desk 먼저 열기"),
    ("M-C ink-homepage 진입", "R", r"용도별 스킬 파일을 열어 1단계부터 실제로 진행", "위임 시 스킬 열고 진행"),
    ("M-C ink-homepage 진입", "R", r"홈페이지용:\s*`?ink-homepage", "홈페이지용 분기"),
    ("M-D 최신 단계 사용", "R", r"사장님이 보시는 단계는 넷", "현재 4단계"),
    ("M-D 최신 단계 사용", "R", r"컨펌 ①.*②.*③|컨펌 ①②③", "컨펌 3회"),
    ("M-E 승인 전 확정 금지", "R", r"명시적으로 승인한 메시지", "확정 조건"),
    ("M-F 한 글 끝나기 전 다음 글 금지", "R", r"한 글이 끝난 뒤에 다음 글 작업을 시작한다", "글 하나씩"),
]
# 낡은 표현(N): REACH 전체에 있으면 안 됨. 개편 중 옛 단계 번호가 되살아나는 사고 방지.
NEGATIVE = [
    ("M-D 최신 단계 사용", r"ink-homepage[^\n]{0,40}(?:[5-9]|1[0-9])단계", "ink-homepage 옛 단계 번호"),
    ("M-D 최신 단계 사용", r"(?:홈페이지용|유입형)[^\n]{0,20}(?:5|6|7)단계", "홈페이지용 옛 단계 수"),
]


def main():
    verbose = "--verbose" in sys.argv
    always, reach, sources = build_surfaces()
    results = []
    for scen, lvl, rx, desc in FACTS:
        pat = re.compile(rx, re.S)
        surface = always if lvl == "A" else reach
        ok = pat.search(surface) is not None
        # A인데 REACH에는 있으면 "상시 로드에서 빠졌다"는 뜻이라 별도 표기
        note = ""
        if not ok and lvl == "A" and pat.search(reach):
            note = "REACH에는 있음(상시 로드에서 빠짐)"
        results.append((scen, lvl, desc, ok, note))
    for scen, rx, desc in NEGATIVE:
        hit = re.search(rx, reach, re.S)
        results.append((scen, "N", "없어야 함: " + desc, hit is None, "" if hit is None else "발견: " + hit.group(0)[:60]))

    # rule 구조 검사: .claude/rules/*.md는 모두 paths: 를 가져야 한다(없으면 상시 로드되어 절감이 사라짐)
    for rp in sorted(glob.glob(os.path.join(ROOT, ".claude", "rules", "**", "*.md"), recursive=True)):
        ok = has_paths(frontmatter(read(rp)))
        results.append(("R rule 구조", "N", "paths 보유: " + os.path.basename(rp), ok, "" if ok else "paths 없음(상시 로드됨)"))
    by = {}
    for scen, lvl, desc, ok, note in results:
        by.setdefault(scen, []).append((lvl, desc, ok, note))
    total_pass = sum(1 for s in by.values() if all(o for _, _, o, _ in s))
    stats = {
        "always_chars": len(always),
        "reach_chars": len(reach),
        "claude_md_lines": len(read(os.path.join(ROOT, "CLAUDE.md")).splitlines()),
        "sources": len(sources),
        "facts": len(results),
        "facts_pass": sum(1 for r in results if r[3]),
        "scenarios": len(by),
        "scenarios_pass": total_pass,
    }
    if "--json" in sys.argv:
        print(json.dumps({"stats": stats, "results": [
            {"scenario": s, "level": l, "fact": d, "pass": o, "note": n} for s, l, d, o, n in results]},
            ensure_ascii=False, indent=1))
    else:
        for scen, items in by.items():
            fails = [(l, d, n) for l, d, o, n in items if not o]
            print(("PASS " if not fails else "FAIL ") + scen + f"  ({len(items) - len(fails)}/{len(items)})")
            for l, d, n in fails:
                print(f"     - [{l}] {d} {n}")
            if verbose and not fails:
                for l, d, _, _ in items:
                    print(f"     ok [{l}] {d}")
        print()
        print("상시 로드(ALWAYS): {always_chars:,}자 / 도달 가능(REACH): {reach_chars:,}자 / CLAUDE.md {claude_md_lines}줄".format(**stats))
        print("사실 {facts_pass}/{facts}, 시나리오 {scenarios_pass}/{scenarios} PASS".format(**stats))
    sys.exit(0 if stats["scenarios_pass"] == stats["scenarios"] else 1)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
