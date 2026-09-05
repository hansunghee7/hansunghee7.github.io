// Cloudflare Worker — SNS 확장 전용 GitHub 쓰기 프록시.
//
// 목적: SNS 확장이 GitHub PAT(Contents: Read and write)를 직접 들고
// 있으면, 확장을 새로 설치할 때마다 그 PAT를 다시 붙여넣어야 하고
// (크롬 확장은 설치본마다 저장 공간이 따로다), 확장 코드는 누구나 열어볼
// 수 있어 그 PAT가 그대로 노출된다. 그래서 진짜 GitHub PAT는 여기(Worker
// 환경변수, Cloudflare 대시보드에서만 보임)에만 두고, 확장은 이 Worker의
// 좁은 창구 두 개(get/put)만 호출한다.
//
// 좁게 만드는 방법: 병합 로직(오늘 날짜 항목을 덮어쓸지 새로 넣을지 등)은
// 여전히 확장(background.js) 쪽에 그대로 둔다 -- 이 Worker는 "GitHub
// Contents API의 GET/PUT을 대신 해주는 것"만 하고, 그마저도 ALLOWED_PATHS
// 목록에 있는 파일 3개(SNS 데이터 전용)에만 쓸 수 있다. APP_KEY가
// 새어나가도 사이트의 다른 파일(HTML/JS/CSS 등)은 절대 못 건드린다.
//
// 필요한 환경변수(Cloudflare 대시보드 > Workers > 이 Worker > Settings >
// Variables and Secrets에서 "Secret"으로 추가):
//   GITHUB_TOKEN -- fine-grained PAT, 이 저장소(hansunghee7.github.io) 하나,
//                   Contents: Read and write.
//   APP_KEY      -- 확장 코드에도 그대로 박아넣을 임의의 긴 문자열.

var REPO = "hansunghee7/hansunghee7.github.io";
var ALLOWED_PATHS = [
  "assets/data/sns-insight.json",
  "assets/data/naver-content.json",
  "assets/data/claude-usage.json",
];

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

    if (!body.path || ALLOWED_PATHS.indexOf(body.path) === -1) {
      return new Response("허용 안 된 경로", { status: 403 });
    }

    var ghHeaders = {
      Authorization: "token " + env.GITHUB_TOKEN,
      Accept: "application/vnd.github+json",
      "User-Agent": "simplifier-sns-writer",
    };
    var url = "https://api.github.com/repos/" + REPO + "/contents/" + body.path;

    if (body.op === "get") {
      var getRes = await fetch(url, { headers: ghHeaders });
      if (getRes.status === 404) {
        return new Response(JSON.stringify({ notFound: true }), {
          headers: { "Content-Type": "application/json" },
        });
      }
      if (!getRes.ok) {
        return new Response("GitHub GET 실패: " + getRes.status, { status: 502 });
      }
      var fileRes = await getRes.json();
      return new Response(JSON.stringify({ sha: fileRes.sha, content: fileRes.content }), {
        headers: { "Content-Type": "application/json" },
      });
    }

    if (body.op === "put") {
      if (typeof body.content !== "string") {
        return new Response("content 필요(base64)", { status: 400 });
      }
      var putBody = {
        message: body.message || "chore: 자동 기록 [skip ci]",
        content: body.content,
      };
      if (body.sha) putBody.sha = body.sha;

      var putRes = await fetch(url, {
        method: "PUT",
        headers: Object.assign({ "Content-Type": "application/json" }, ghHeaders),
        body: JSON.stringify(putBody),
      });

      if (putRes.status === 409) {
        return new Response(JSON.stringify({ conflict: true }), {
          status: 409,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (!putRes.ok) {
        var errText = await putRes.text();
        return new Response("GitHub PUT 실패: " + putRes.status + " " + errText, { status: 502 });
      }
      var putJson = await putRes.json();
      return new Response(
        JSON.stringify({ ok: true, sha: putJson.content && putJson.content.sha }),
        { headers: { "Content-Type": "application/json" } }
      );
    }

    return new Response("op 필요(get|put)", { status: 400 });
  },
};
