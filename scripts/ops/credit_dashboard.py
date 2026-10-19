# -*- coding: utf-8 -*-
"""크레딧 현황판 — 온디맨드 집계(2026-10-18 탐, 사장님 지시 "크레딧 현황판 보여줘 하면 바로 수치가 뜨게").

왜: 지금은 사장님이 물을 때마다 손으로 grants/quota를 긁어 표를 만든다. 이 도구 하나로 모든 소스를
한 번에 모아 markdown 표를 낸다. 판정('계획대로?')은 사람이 하므로 넣지 않는다 — 데이터만 모은다.

모으는 소스(정본에서 읽고, 모르면 '미확인'. 지어내지 않는다):
  1) 큰 클라우드/API 크레딧 프로그램: grants.py(운영 DB section='grant')의 AWS(G20)·Azure(G21)·
     GCP(G18)·Anthropic(G19)·NVIDIA(G22) 행 → 규모·상태·만료·다음 할 일.
  2) GCP 실사용/잔여: vertex_budget.json 기준 잔액 − 이후 API 실사용(gcp_usage.py)으로 추정.
     tam-vertex 서비스 계정으로 Cloud Billing API 읽기를 시도하되, 막히면 '권한 필요'로 표기(억지로 뚫지 않음).
  2b) GCP 전체 비용(인프라 포함·실측): Vertex뿐 아니라 saegim-mcp 서버 호스팅 등 모든 서비스 실비를
     BigQuery 결제 export에서 서비스별로 읽는다(tam-vertex SA). 중요: Cloud Billing API v1은 결제계정 메타·
     SKU 단가만 주고 '얼마 썼나'는 안 준다 — 실비는 export 경유가 유일. export 미설정·권한 없으면 '권한 필요'.
  3) 무료 모델 쿼터: quota.py status(비티·비티-sonnet·덱스) 파싱.
  4) Flow 영상 크레딧: 핏 영역 — flow_credits_local.jsonl의 계정별 최근 잔여 요약(상세는 핏 현황판).
  5) Claude Max 주간/5h: get_usage는 세션 전용 MCP라 스크립트가 못 부른다 → "세션에서만 실측"으로 명시,
     마지막 pace_log(pace/usage.csv) 값을 참고로 표시.
  6) Azure/AWS 실사용 $: Cost API 키가 아직 없어 '자동연동 대기(키 필요)' placeholder.
     키가 생기면 refresh가 Azure Cost Management / AWS Cost Explorer를 읽도록 함수 자리(스텁)만 둠.

사용:
    python scripts/ops/credit_dashboard.py show       # 현황판 표(markdown). 캐시 있으면 쓰고 없으면 그 자리서 소스 읽기
    python scripts/ops/credit_dashboard.py refresh     # 자동 연동 가능한 소스를 다시 읽어 캐시에 저장

캐시: C:/work/_ops/credit_state.json (레포 밖 런타임 STATE, 새 DB 표를 만들지 않는다 — DDL 승인 불필요).
"""
import csv
import json
import os
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

OPS = Path("C:/work/_ops")
CACHE = OPS / "credit_state.json"
CACHE_MAX_AGE = 3600  # show가 캐시를 그대로 쓰는 최대 나이(초). 넘으면 그 자리서 다시 읽는다.

# grants DB의 G번호 → 현황판에 보일 이름. GCP(G18)를 반드시 포함(지난 표 누락 지적).
GRANT_MAP = [
    ("G18", "GCP (Google for Startups)"),
    ("G19", "Anthropic (Claude Startups)"),
    ("G20", "AWS (Activate)"),
    ("G21", "Azure (MS for Startups)"),
    ("G22", "NVIDIA (Inception)"),
]


def _short(s, n=46):
    s = (s or "").replace("|", "/").replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


# ---------------------------------------------------------------- 소스별 수집(각 소스는 실패해도 전체를 막지 않는다)

def collect_grants():
    """소스 1: 큰 클라우드/API 크레딧 프로그램(grants DB section='grant')."""
    rows = []
    try:
        import grants
        for no, label in GRANT_MAP:
            try:
                r = grants.find(no)
            except SystemExit:
                rows.append({"name": label, "scale": "미확인", "used": "—", "expiry": "미확인",
                             "state": f"{no} 행 없음", "note": "grants DB에서 못 찾음"})
                continue
            w = grants.raw_of(r)
            rows.append({
                "name": label,
                "scale": _short(w.get("amount") or r.get("result") or "미확인", 54),
                "used": "—",  # 프로그램 승인 전/직후라 실사용 잔액은 소스 2(GCP)·소스 6(Azure/AWS Cost API)에서 채운다
                "expiry": _short(w.get("window") or "미확인", 30),
                "state": r.get("status") or "미확인",
                "note": _short(r.get("next_action") or "", 40),
            })
    except Exception as e:  # noqa: BLE001
        rows.append({"name": "크레딧 프로그램", "scale": "", "used": "", "expiry": "",
                     "state": "읽기 실패", "note": f"grants DB 오류: {type(e).__name__}"})
    return rows


def gcp_billing_probe():
    """소스 2 보조: tam-vertex SA로 Cloud Billing API 읽기 가능 여부만 확인(실수치 경로). 막으면 사유 반환, 억지로 뚫지 않는다."""
    try:
        import urllib.error
        import urllib.request

        import ask_vertex as av
        t = av.sa_token()
        if not t:
            return False, "SA 토큰 없음(패스 envput 필요)"
        req = urllib.request.Request("https://cloudbilling.googleapis.com/v1/billingAccounts",
                                     headers={"Authorization": "Bearer " + t})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        accts = data.get("billingAccounts", [])
        return True, f"{len(accts)}개 결제계정 읽기 OK"
    except urllib.error.HTTPError as e:  # noqa: F821
        code = e.code
        if code == 403:
            return False, "billing 읽기 권한 필요(Cloud Billing API 비활성/권한 없음)"
        return False, f"billing API HTTP {code}"
    except Exception as e:  # noqa: BLE001
        return False, f"billing 읽기 권한 필요({type(e).__name__})"


def collect_gcp_actual():
    """소스 2: GCP 무료크레딧 실사용/잔여(vertex_budget.json 기준잔액 − 이후 실사용 추정). simon+hansunghee7 합산."""
    row = {"name": "GCP 무료크레딧(실사용)", "scale": "미확인", "used": "미확인",
           "expiry": "미확인", "state": "추정", "note": ""}
    billing_ok, billing_msg = gcp_billing_probe()
    try:
        b = json.loads((OPS / "vertex_budget.json").read_text(encoding="utf-8"))
        balance = b.get("balance")
        as_of = b.get("as_of", "")
        expiry = b.get("expiry", "미확인")
        # 기준일(as_of) 이후 API 실사용 합계(회사+개인 캐시)
        total_used = 0.0
        used_known = False
        try:
            import gcp_usage
            caches = ["gcp_usage_cache.json", "gcp_usage_cache_simplifier-vertex-credit.json"]
            for cf in caches:
                p = OPS / cf
                if not p.exists():
                    continue
                daily = json.loads(p.read_text(encoding="utf-8")).get("daily", {})
                for day, v in daily.items():
                    if day > as_of:
                        total_used += float(v.get("krw", 0) if isinstance(v, dict) else v or 0)
                        used_known = True
        except Exception:  # noqa: BLE001
            used_known = False
        remain = (balance - total_used) if (balance is not None and used_known) else None
        row["scale"] = f"₩{balance:,} 기준({as_of})" if balance is not None else "미확인"
        if remain is not None:
            row["used"] = f"사용 ₩{total_used:,.0f} / 잔여 약 ₩{remain:,.0f}(추정)"
        else:
            row["used"] = "미확인(실사용 캐시 없음)"
        row["expiry"] = expiry
        note = b.get("note", "")
        # 회사/개인 분해가 note에 있으면 요약
        row["note"] = _short("회사+개인 합산, 잔액은 추정. " + billing_msg, 60)
        row["_billing"] = {"ok": billing_ok, "msg": billing_msg}
    except Exception as e:  # noqa: BLE001
        row["note"] = f"vertex_budget.json 오류: {type(e).__name__}; {billing_msg}"
        row["_billing"] = {"ok": billing_ok, "msg": billing_msg}
    return [row]


# ---- 소스 2b: GCP 전체 비용(인프라 포함). Vertex뿐 아니라 saegim-mcp 서버 호스팅 등 모든 서비스 실비. ----
# 읽는 길은 BigQuery 결제 export 하나뿐이다. Cloud Billing API v1(billingAccounts/billingInfo/services)은
# "결제계정 메타·SKU 단가"만 주고 "실제 얼마 썼나"는 주지 않는다(2026-10-18 tam-vertex SA 실측 확인). 실비는
# 결제계정→BigQuery export를 켠 뒤 그 데이터셋을 질의해야 나온다. export가 없거나 권한이 없으면 사유만 돌려준다.

# 2026-10-20 실측: 결제 export는 이미 켜져 있고 위치는 프로젝트 saegim-mcp, 데이터셋 billing_export(결제계정 0138DC)다. 예전 기본값(simplifier-vertex-credit)에는 데이터셋이 없어 "export 미설정"으로 잘못 나왔다.
GCP_BILLING_PROJECT = os.environ.get("GCP_BILLING_PROJECT", "saegim-mcp")
GCP_BILLING_BQ_DATASET = os.environ.get("GCP_BILLING_BQ_DATASET", "billing_export")  # 기본은 실제 위치를 못 박음(자동 탐색은 다른 'billing' 데이터셋을 집을 수 있음). 환경변수를 빈 문자열로 주면 자동 탐색(비티 리뷰 반영)


def _bq_call(path, body=None, token=None, method="GET"):
    import urllib.error
    import urllib.request
    url = "https://bigquery.googleapis.com/bigquery/v2/" + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Authorization": "Bearer " + token,
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def read_gcp_total_cost(days=30):
    """GCP 결제계정의 최근 N일 실비를 서비스별로 읽는다(BigQuery 결제 export 경유). tam-vertex SA 토큰.

    돌려주는 값: (data, reason).
      - data: {"total": 원화아닌원통화합, "currency": "KRW"/"USD", "by_service": [(서비스, 금액), ...],
               "days": N, "project": 질의프로젝트} — 읽기 성공 시.
      - data=None, reason="…": export 미설정·권한 없음·API 막힘 등. 억지로 뚫지 않고 사유만 전한다.
    export 표준 테이블명은 gcp_billing_export_v1_<결제계정ID>. 데이터셋은 환경변수 또는 'billing' 포함 자동탐색.
    """
    import urllib.error
    try:
        import ask_vertex as av
        token = av.sa_token()
    except Exception as e:  # noqa: BLE001
        return None, f"SA 토큰 로드 실패({type(e).__name__})"
    if not token:
        return None, "SA 토큰 없음(패스 envput 필요)"
    proj = GCP_BILLING_PROJECT
    try:
        # 1) 데이터셋 찾기(환경변수 우선, 없으면 'billing' 포함 자동탐색)
        ds = GCP_BILLING_BQ_DATASET
        if not ds:
            lst = _bq_call(f"projects/{proj}/datasets", token=token)
            datasets = [d["datasetReference"]["datasetId"] for d in lst.get("datasets", [])]
            if not datasets:
                return None, "BigQuery 결제 export 미설정(데이터셋 없음) — 콘솔에서 export 켜야 함"
            cand = [d for d in datasets if "billing" in d.lower()]
            if not cand:
                return None, f"결제 export 데이터셋 못 찾음(있는 데이터셋: {', '.join(datasets[:3])}…) — GCP_BILLING_BQ_DATASET 지정 필요"
            ds = cand[0]
        # 2) 서비스별 실비 질의(비용 + 크레딧 = 순비용). 표준 export 테이블 와일드카드.
        sql = (
            "SELECT service.description AS svc, currency AS cur, "
            "SUM(cost) + SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)) AS net "
            f"FROM `{proj}.{ds}.gcp_billing_export_v1_*` "
            f"WHERE usage_start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {int(days)} DAY) "
            "GROUP BY svc, cur ORDER BY net DESC"
        )
        res = _bq_call(f"projects/{proj}/queries", body={"query": sql, "useLegacySql": False, "timeoutMs": 55000},
                       token=token, method="POST")
        rows = res.get("rows", [])
        by_service = []
        total = 0.0
        currency = ""
        for r in rows:
            f = r.get("f", [])
            svc = f[0].get("v") if len(f) > 0 else "?"
            cur = f[1].get("v") if len(f) > 1 else ""
            net = float(f[2].get("v") or 0) if len(f) > 2 else 0.0
            currency = currency or cur
            by_service.append((svc or "(미분류)", net))
            total += net
        return {"total": total, "currency": currency or "?", "by_service": by_service,
                "days": days, "project": proj}, "OK"
    except urllib.error.HTTPError as e:
        code = e.code
        try:
            msg = json.loads(e.read().decode("utf-8", "replace")).get("error", {}).get("message", "")
        except Exception:  # noqa: BLE001
            msg = ""
        if code == 403:
            if "gcp_billing_export" in msg or "Not found: Table" in msg:
                return None, "결제 export 테이블 없음 — 콘솔에서 export 켜야 함"
            return None, "BigQuery/결제 export 읽기 권한 필요(SA에 bigquery.dataViewer+jobUser 부여 필요)"
        if code == 404:
            return None, "export 테이블 없음(gcp_billing_export_v1_*) — 콘솔에서 export 켜야 함"
        return None, f"BigQuery HTTP {code}"
    except Exception as e:  # noqa: BLE001
        return None, f"GCP 전체비용 읽기 실패({type(e).__name__})"


def collect_gcp_total(days=30):
    """소스 2b 행: GCP 전체 비용(인프라 포함, 실측). 읽히면 서비스별 합, 안 되면 '권한 필요'."""
    row = {"name": "GCP 전체 비용(인프라 포함·실측)", "scale": f"최근 {days}일", "used": "권한 필요",
           "expiry": "—", "state": "권한 필요", "note": ""}
    data, reason = read_gcp_total_cost(days)
    if data is None:
        row["note"] = _short(reason, 72)
        row["_gcp_total"] = {"ok": False, "reason": reason}
        return [row]
    cur = data["currency"]
    sym = "₩" if cur == "KRW" else ("$" if cur == "USD" else "")
    top = ", ".join(f"{s} {sym}{v:,.0f}" for s, v in data["by_service"][:3]) or "내역 없음"
    row["scale"] = f"최근 {days}일 · {data['project']}"
    row["used"] = f"합계 {sym}{data['total']:,.0f} ({cur})"
    row["state"] = "실측"
    row["note"] = _short("상위: " + top, 72)
    row["_gcp_total"] = {"ok": True, "total": data["total"], "currency": cur,
                         "by_service": data["by_service"], "days": days}
    return [row]


def collect_vertex_agents(days=7):
    """소스 2 상세: GCP/Vertex 실소비의 에이전트(who)별 내역(vertex_usage.csv, 최근 N일).

    위 'GCP 무료크레딧(실사용)' 총 소비를 '누가 얼마나 썼나'로 쪼갠다(사장님 지적: 비티가 GCP를
    연결해 쓰는데 quota.py 안티그래비티 풀 수치만 보여 Vertex 사용이 표에 안 드러났다).
    CSV는 utf-8(한글 who). est_krw 합을 추정비용(원)으로, 행 수를 호출수로 집계하고 많은 순 정렬."""
    p = OPS / "vertex_usage.csv"
    agg = {}  # who → [호출수, est_krw 합]
    err = None
    cutoff = datetime.now() - timedelta(days=days)
    try:
        with p.open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                ts = (r.get("time") or "").strip()
                try:
                    t = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    continue
                if t < cutoff:
                    continue
                who = (r.get("who") or "?").strip() or "?"
                try:
                    krw = float(r.get("est_krw") or 0)
                except ValueError:
                    krw = 0.0
                a = agg.setdefault(who, [0, 0.0])
                a[0] += 1
                a[1] += krw
    except FileNotFoundError:
        err = "vertex_usage.csv 없음"
    except OSError as e:  # noqa: BLE001
        err = f"vertex_usage.csv 오류: {type(e).__name__}"
    rows = [{"who": w, "calls": c, "krw": k} for w, (c, k) in agg.items()]
    rows.sort(key=lambda x: (-x["calls"], -x["krw"]))
    return {"days": days, "rows": rows, "err": err}


def collect_quota():
    """소스 3: 무료 모델 쿼터(quota.py status: 비티·비티-sonnet·덱스)."""
    rows = []
    try:
        out = subprocess.run([sys.executable, str(HERE / "quota.py"), "status"],
                             capture_output=True, text=True, encoding="utf-8", timeout=30,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        for line in out.splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            pool, rest = line.split(":", 1)
            rest = rest.strip()
            blocked = "막힘" in rest
            rows.append({
                "name": f"무료모델 {pool.strip()}",
                "scale": "주간(한도 미공개, 세기만)",
                "used": _short(rest.split("/")[0].strip(), 40),
                "expiry": "주 단위 리셋",
                "state": "막힘" if blocked else "통과",
                "note": _short(rest, 50) if blocked else "",
            })
    except Exception as e:  # noqa: BLE001
        rows.append({"name": "무료모델 쿼터", "scale": "", "used": "", "expiry": "",
                     "state": "읽기 실패", "note": f"quota.py 오류: {type(e).__name__}"})
    return rows


def collect_flow():
    """소스 4: Flow 영상 크레딧(핏 영역). flow_credits_local.jsonl의 계정별 최근 잔여 요약. 상세는 핏 현황판."""
    row = {"name": "Flow 영상 크레딧(핏 영역)", "scale": "계정별", "used": "미확인",
           "expiry": "일 단위 충전", "state": "핏 영역", "note": "상세는 핏 현황판"}
    try:
        p = OPS / "flow_credits_local.jsonl"
        if not p.exists():
            row["used"] = "로그 없음"
            return [row]
        latest = {}  # acct/u → (ts, credits)
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            key = d.get("u") or d.get("acct") or "?"
            ts = d.get("ts", "")
            if key not in latest or ts >= latest[key][0]:
                latest[key] = (ts, d.get("credits"))
        if latest:
            parts = [f"{k} {v[1]}" for k, v in sorted(latest.items())]
            row["used"] = _short("잔여 " + ", ".join(parts), 56)
            row["note"] = _short("최근 로그 기준, 상세는 핏 현황판", 40)
    except Exception as e:  # noqa: BLE001
        row["note"] = f"flow 로그 오류: {type(e).__name__}"
    return [row]


def collect_claude_max():
    """소스 5: Claude Max 주간/5h. get_usage는 세션 전용 MCP라 스크립트가 못 부른다 → 명시 + 마지막 pace_log 참고."""
    row = {"name": "Claude Max (주간/5h)", "scale": "구독 한도", "used": "세션에서만 실측(파이프라인 자동 불가)",
           "expiry": "토 18시 리셋", "state": "세션 전용", "note": "get_usage MCP 필요"}
    try:
        p = OPS / "pace" / "usage.csv"
        if p.exists():
            lines = [l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
            if len(lines) >= 2:
                last = lines[-1].split(",")
                # 열: 기록시각_UTC,주간%,5시간%,컨텍스트%,...
                ts, wk, h5 = last[0], last[1], last[2]
                row["used"] = f"세션 실측값만. 마지막 pace_log({ts[:16]}): 주간 {wk}% · 5h {h5}%"
    except Exception as e:  # noqa: BLE001
        row["note"] = f"pace 로그 오류: {type(e).__name__}"
    return [row]


# ---- 소스 6 스텁: Azure/AWS 실사용 $. 키가 생기면 여기서 Cost API를 읽는다(지금은 호출하지 않는다). ----

def read_azure_cost():
    """[스텁] Azure Cost Management(Query Usage) 읽기. 키가 생기면 구현.
    구현 시: AZURE_* 자격증명으로 /subscriptions/{id}/providers/Microsoft.CostManagement/query 호출,
    실제 사용 $를 돌려준다. 지금은 호출하지 않는다(키 없음)."""
    return None


def read_aws_cost():
    """[스텁] AWS Cost Explorer(GetCostAndUsage) 읽기. 키가 생기면 구현.
    구현 시: AWS_* 자격증명으로 ce:GetCostAndUsage 호출, 실제 사용 $를 돌려준다. 지금은 호출하지 않는다(키 없음)."""
    return None


def collect_cloud_cost_stub():
    """소스 6: Azure/AWS 실사용 $ — Cost API 키가 아직 없어 placeholder."""
    rows = []
    for name, fn in (("Azure 실사용 $", read_azure_cost), ("AWS 실사용 $", read_aws_cost)):
        val = fn()
        if val is None:
            rows.append({"name": name, "scale": "—", "used": "자동연동 대기(키 필요)", "expiry": "—",
                         "state": "미연동", "note": "Cost API 키 생기면 refresh가 자동 집계"})
        else:
            rows.append(val)
    return rows


# ---------------------------------------------------------------- 집계·캐시·출력

def gather():
    """모든 소스를 한 번에 모아 행 목록과 메타를 돌려준다."""
    rows = []
    rows += collect_grants()
    rows += collect_gcp_actual()
    rows += collect_gcp_total()
    rows += collect_quota()
    rows += collect_flow()
    rows += collect_claude_max()
    rows += collect_cloud_cost_stub()
    return {"at": time.time(), "generated": datetime.now().strftime("%Y-%m-%d %H:%M"), "rows": rows,
            "vertex_agents": collect_vertex_agents()}


def save_cache(state):
    try:
        OPS.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
        return True
    except OSError:
        return False


def load_cache():
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def render(state):
    rows = state.get("rows", [])
    out = [f"## 크레딧 현황판 ({state.get('generated', '')} 기준)", ""]
    out.append("| 크레딧/한도 | 규모 | 사용(잔여) | 만료 | 상태 | 비고 |")
    out.append("|---|---|---|---|---|---|")
    for r in rows:
        out.append("| {name} | {scale} | {used} | {expiry} | {state} | {note} |".format(
            name=r.get("name", ""), scale=r.get("scale", "") or "—", used=r.get("used", "") or "—",
            expiry=r.get("expiry", "") or "—", state=r.get("state", "") or "—", note=r.get("note", "") or ""))
    out.append("")
    out.append("데이터만 모읍니다(계획대로인지 판정은 사람이). 잔액·추정 표기는 소스 한계를 그대로 둡니다. "
               "GCP 프로그램(G18)·무료크레딧 둘 다 포함, Azure/AWS 실사용 $는 Cost API 키가 생기면 자동연동.")
    out.append("")
    out += render_vertex_agents(state.get("vertex_agents"))
    return "\n".join(out)


def render_vertex_agents(va):
    """위 'GCP 무료크레딧(실사용)' 총 소비를 에이전트(who)별로 쪼갠 섹션. 비티의 Vertex 사용이 여기서 드러난다."""
    if not va:
        return []
    days = va.get("days", 7)
    out = [f"## GCP/Vertex 에이전트별 사용(최근 {days}일)", ""]
    if va.get("err"):
        out.append(f"(집계 불가: {va['err']})")
        return out
    agent_rows = va.get("rows", [])
    if not agent_rows:
        out.append("(최근 기록 없음)")
        return out
    out.append("| 에이전트(who) | 호출수 | 추정비용(원) |")
    out.append("|---|---:|---:|")
    tot_c = tot_k = 0
    for r in agent_rows:
        out.append("| {who} | {calls} | {krw:,.0f} |".format(
            who=r.get("who", "?"), calls=r.get("calls", 0), krw=r.get("krw", 0.0)))
        tot_c += r.get("calls", 0)
        tot_k += r.get("krw", 0.0)
    out.append("| **합계** | **{c}** | **{k:,.0f}** |".format(c=tot_c, k=tot_k))
    out.append("")
    out.append("위 'GCP 무료크레딧(실사용)' 소비를 주체별로 쪼갠 내역입니다(vertex_usage.csv 실측, 많은 순). "
               "비티 등 에이전트가 GCP 연결로 쓰는 Vertex가 여기 잡힙니다.")
    return out


def cmd_show():
    state = load_cache()
    fresh = state and (time.time() - state.get("at", 0) < CACHE_MAX_AGE)
    if not fresh:
        state = gather()  # 캐시가 없거나 오래됐으면 그 자리서 소스 읽기(저장은 refresh의 몫, show는 읽기만)
    elif "vertex_agents" not in state:
        state["vertex_agents"] = collect_vertex_agents()  # 옛 캐시엔 이 키가 없다 — 그 자리서 집계
    print(render(state))
    return 0


def cmd_refresh():
    state = gather()
    ok = save_cache(state)
    print(render(state))
    print("")
    print(f"[refresh] 캐시 {'저장' if ok else '저장 실패'}: {CACHE}")
    b = next((r.get("_billing") for r in state["rows"] if r.get("_billing")), None)
    if b:
        print(f"[refresh] GCP billing 읽기: {'가능' if b['ok'] else '불가'} — {b['msg']}")
    g = next((r.get("_gcp_total") for r in state["rows"] if r.get("_gcp_total")), None)
    if g:
        print(f"[refresh] GCP 전체비용(실측): {'가능' if g['ok'] else '권한 필요'} — "
              f"{g.get('reason') if not g['ok'] else format(g.get('total', 0), ',.0f') + ' ' + g.get('currency', '')}")
    return 0


def main(argv):
    cmd = argv[0] if argv else "show"
    if cmd == "show":
        return cmd_show()
    if cmd == "refresh":
        return cmd_refresh()
    print(__doc__)
    return 64


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
