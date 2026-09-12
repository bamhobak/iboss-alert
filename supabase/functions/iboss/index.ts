// 아이보스 게시판 대리 수신(fetcher)
//
// 왜 있나: GitHub 러너(Azure IP)는 Cloudflare 에 403 으로 막힌다(실측 러너 6대 6/6).
// 그래서 "가져오는 일"만 여기서 하고, 일정·상태·텔레그램 전송은 그대로 Actions 가 한다.
// Actions → Supabase, Actions → 텔레그램 은 둘 다 막히지 않는다.
//
// 호출: GET /functions/v1/iboss?cat=BCV      → { ok, status, bytes, html }
//       GET /functions/v1/iboss?probe=1      → 본문 없이 상태만
// 인증: Supabase anon 키 필요(기본 JWT 검증). 아무나 프록시로 쓰지 못하게 둔다.

const BASE = "https://www.i-boss.co.kr";

const UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
  "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36";

const HEADERS: Record<string, string> = {
  "User-Agent": UA,
  "Accept":
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
  "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
  "Sec-Ch-Ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
  "Sec-Ch-Ua-Mobile": "?0",
  "Sec-Ch-Ua-Platform": '"Windows"',
  "Sec-Fetch-Dest": "document",
  "Sec-Fetch-Mode": "navigate",
  "Sec-Fetch-Site": "none",
  "Sec-Fetch-User": "?1",
  "Upgrade-Insecure-Requests": "1",
};

Deno.serve(async (req) => {
  const u = new URL(req.url);
  const cat = (u.searchParams.get("cat") || "BCV").replace(/[^A-Za-z가-힣]/g, "");
  const probeOnly = u.searchParams.get("probe") === "1";
  const target = `${BASE}/ab-1957?category_1=${encodeURIComponent(cat)}`;

  const json = (body: unknown, code = 200) =>
    new Response(JSON.stringify(body), {
      status: code,
      headers: { "content-type": "application/json; charset=utf-8" },
    });

  try {
    const r = await fetch(target, { headers: HEADERS, redirect: "follow" });
    const body = await r.text();
    const meta = {
      ok: r.status === 200,
      status: r.status,
      bytes: body.length,
      mitigated: r.headers.get("cf-mitigated") ?? "-",
      ray: r.headers.get("cf-ray") ?? "-",
      cat,
    };
    if (probeOnly || r.status !== 200) {
      return json({ ...meta, head: body.slice(0, 200) });
    }
    return json({ ...meta, html: body });
  } catch (e) {
    return json({ ok: false, status: 0, error: String(e).slice(0, 300), cat }, 200);
  }
});
