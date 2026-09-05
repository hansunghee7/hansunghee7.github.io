// Cloudflare Worker — 클로드 사용량 데이터 기록 전용 프록시.
//
// 목적: SNS 확장이 GitHub PAT(Contents: Read and write)를 직접 들고
// 있으면, 확장을 새로 설치할 때마다 그 PAT를 다시 붙여넣어야 하고
// (크롬 확장은 설치본마다 저장 공간이 따로다), 확장 코드는 누구나 열어볼
// 수 있어 그 PAT가 그대로 노출된다. 그래서 진짜 GitHub PAT는 여기(Worker
// 환경변수, Cloudflare 대시보드에서만 보임)에만 두고, 확장은 이 Worker의
// 좁은 창구 하나만 호출한다 -- 이 창구가 할 수 있는 일은 정확히
// "assets/data/claude-usage.json에 오늘 날짜로 값 3개 쓰기" 하나뿐이라,
// 이 Worker를 호출하는 APP_KEY가 새어나가도 사이트 전체를 고칠 수는 없다.
//
// 필요한 환경변수(Cloudflare 대시보드 > Workers > 이 Worker > Settings >
// Variables and Secrets에서 "Secret"으로 추가 -- Secret으로 넣으면 대시보드
// 재방문해도 값이 안 보인다):
//   GITHUB_TOKEN -- fine-grained PAT, 이 저장소(hansunghee7.github.io) 하나,
//                   Contents: Read and write. 이 Worker 전용으로 새로 발급
//                   권장(sns-extension-2와 별도 -- 하나가 새면 하나만 무효화).
//   APP_KEY      -- 확장 코드에도 그대로 박아넣을 임의의 긴 문자열(추측
//                   못 하게 32자 이상 랜덤 문자열 권장).

var REPO = "hansunghee7/hansunghee7.github.io";
var DATA_PATH = "assets/data/claude-usage.json";
var FIELD_KEYS = ["session_5h", "weekly_all", "weekly_fable"];

function b64EncodeUtf8(str) {
  var bytes = new TextEncoder().encode(str);
  var binary = "";
  bytes.forEach(function (b) { binary += String.fromCharCode(b); });
  return btoa(binary);
}

function b64DecodeUtf8(b64) {
  var binary = atob(b64.replace(/\n/g, ""));
  var bytes = new Uint8Array(binary.length);
  for (var i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return new TextDecoder().decode(bytes);
}

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("Method not allowed", { status: 405 });
    }

    var body;
    try {
      body = await request.json();
    } catch (e) {
      return new Response("Bad JSON", { status: 400 });
    }

    if (!env.APP_KEY || body.key !== env.APP_KEY) {
      return new Response("Unauthorized", { status: 401 });
    }

    var fields = body.fields;
    var capturedAt = body.capturedAt || new Date().toISOString();
    if (!fields || typeof fields !== "object") {
      return new Response("fields 필요", { status: 400 });
    }

    var ghHeaders = {
      Authorization: "token " + env.GITHUB_TOKEN,
      Accept: "application/vnd.github+json",
      "User-Agent": "simplifier-claude-usage-writer",
    };
    var url = "https://api.github.com/repos/" + REPO + "/contents/" + DATA_PATH;

    var getRes = await fetch(url, { headers: ghHeaders });
    var sha = null;
    var data = {};
    if (getRes.status === 200) {
      var fileRes = await getRes.json();
      sha = fileRes.sha;
      try {
        data = JSON.parse(b64DecodeUtf8(fileRes.content));
      } catch (e) {
        data = {};
      }
    } else if (getRes.status !== 404) {
      return new Response("GitHub GET 실패: " + getRes.status, { status: 502 });
    }

    var day = todayStr();
    FIELD_KEYS.forEach(function (key) {
      if (fields[key] == null) return;
      if (!data[key]) data[key] = [];
      var series = data[key];
      var todayEntry = series.filter(function (e) { return e.date === day; })[0];
      if (todayEntry) {
        todayEntry.pct = fields[key];
        todayEntry.capturedAt = capturedAt;
      } else {
        series.push({ date: day, pct: fields[key], capturedAt: capturedAt });
      }
      series.sort(function (a, b) { return a.date < b.date ? -1 : 1; });
    });

    var putBody = {
      message: "chore: 클로드 사용량 자동 기록 (" + day + ") [skip ci]",
      content: b64EncodeUtf8(JSON.stringify(data, null, 2)),
    };
    if (sha) putBody.sha = sha;

    var putRes = await fetch(url, {
      method: "PUT",
      headers: Object.assign({ "Content-Type": "application/json" }, ghHeaders),
      body: JSON.stringify(putBody),
    });

    if (!putRes.ok) {
      var errText = await putRes.text();
      return new Response("GitHub PUT 실패: " + putRes.status + " " + errText, { status: 502 });
    }

    return new Response(JSON.stringify({ ok: true }), {
      headers: { "Content-Type": "application/json" },
    });
  },
};
