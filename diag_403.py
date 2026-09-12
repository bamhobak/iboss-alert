# -*- coding: utf-8 -*-
"""
403 진단 — 어떤 요청 방식이 통하는지 러너에서 직접 재 본다.

집 IP 는 200, GitHub 러너는 403 이었다. 앞단이 Cloudflare 라서
(1) IP 자체가 막힌 것인지 (2) 헤더가 부실해서 봇으로 찍힌 것인지를 가른다.

한 판 돌리면 전략별 상태코드가 표로 나온다. 진단용이라 알림과는 무관하다.
"""

import time

import requests

URL = "https://www.i-boss.co.kr/ab-1957?category_1=BCV"
HOME = "https://www.i-boss.co.kr/ab-home"

CHROME = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
MOBILE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1")
GOOGLEBOT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"

FULL = {
    "User-Agent": CHROME,
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "image/avif,image/webp,image/apng,*/*;q=0.8"),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "max-age=0",
    "Sec-Ch-Ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "Connection": "keep-alive",
}


def show(name, r, extra=""):
    if r is None:
        print(f"{name:34s} | 예외 {extra}")
        return
    mit = r.headers.get("cf-mitigated", "-")
    print(f"{name:34s} | {r.status_code} | {len(r.content):>7d}B | "
          f"cf-mitigated={mit} | ray={r.headers.get('cf-ray','-')}")
    if r.status_code != 200:
        body = r.text[:200].replace("\n", " ")
        print(f"{'':34s} └ {body}")


def try_(name, fn):
    try:
        show(name, fn())
    except Exception as e:
        show(name, None, repr(e)[:120])
    time.sleep(4)          # 진단이라도 예의는 지킨다


def main():
    try:
        ip = requests.get("https://api.ipify.org", timeout=10).text
        print(f"러너 IP: {ip}\n")
    except Exception:
        print("러너 IP: 확인 실패\n")

    print(f"{'전략':34s} | 코드 | 크기 | 완화 | ray")
    print("-" * 100)

    # 1) 지금 쓰는 방식 — 최소 헤더
    try_("1. 최소 헤더(현재 방식)",
         lambda: requests.get(URL, headers={"User-Agent": CHROME,
                                            "Accept-Language": "ko-KR,ko;q=0.9"},
                              timeout=20))

    # 2) 브라우저 헤더 전부
    try_("2. 브라우저 헤더 전체",
         lambda: requests.get(URL, headers=FULL, timeout=20))

    # 3) 세션으로 홈 먼저 → 쿠키 받고 게시판 (사람이 들어오는 순서)
    def s3():
        s = requests.Session()
        s.headers.update(FULL)
        s.get(HOME, timeout=20)
        time.sleep(2)
        h = {"Referer": HOME, "Sec-Fetch-Site": "same-origin"}
        return s.get(URL, headers=h, timeout=20)
    try_("3. 세션(홈→게시판, 쿠키+Referer)", s3)

    # 4) 모바일 UA
    try_("4. 모바일 UA",
         lambda: requests.get(URL, headers={**FULL, "User-Agent": MOBILE,
                                            "Sec-Ch-Ua-Mobile": "?1"}, timeout=20))

    # 5) 검색봇 UA — 사이트가 색인은 허용하는 경우가 많다
    try_("5. Googlebot UA",
         lambda: requests.get(URL, headers={"User-Agent": GOOGLEBOT}, timeout=20))

    # 6) HTTP/2 로 (클플은 HTTP/1.1 고정을 의심 신호로 본다)
    def s6():
        import httpx
        with httpx.Client(http2=True, headers=FULL, timeout=20,
                          follow_redirects=True) as c:
            return c.get(URL)
    try_("6. HTTP/2 (httpx)", s6)

    # 7) 같은 IP 로 연속 요청 — 속도 제한인지 본다
    print("\n연속 3회(각 2초 간격) — 속도 제한 여부")
    for i in range(3):
        try_(f"7-{i+1}. 반복", lambda: requests.get(URL, headers=FULL, timeout=20))


if __name__ == "__main__":
    main()
