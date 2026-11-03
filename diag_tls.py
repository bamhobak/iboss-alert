# -*- coding: utf-8 -*-
"""
TLS 지문 진단 (2026-11-03) — 데이터센터 IP 에서 Cloudflare 챌린지를 지문으로 넘을 수 있나.

배경: 러너도 Supabase 서울 엣지도 403 cf-mitigated=challenge 가 됐다. 집 IP 는 200 이다.
가설: IP 평판뿐 아니라 **TLS/JA3 지문**도 본다. requests(OpenSSL) 는 봇 티가 난다.
      네이버 PC 검색이 같은 식으로 막았을 때 curl_cffi 크롬 지문으로 뚫은 전례가 있다.

이게 통하면 인프라를 안 옮기고 fetch 방식만 바꾸면 된다.
"""

import time

URL = "https://www.i-boss.co.kr/ab-1957?category_1=BCV"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")


def show(name, status, size, mitigated, note=""):
    mark = "통과" if status == 200 and size > 50000 else "막힘"
    print(f"{name:28s} | {str(status):>5} | {size:>7} | {mitigated:<10} | {mark} {note}")


def main():
    try:
        import requests
        ip = requests.get("https://api.ipify.org", timeout=10).text
    except Exception:
        ip = "?"
    print(f"러너 IP: {ip}\n")
    print(f"{'방식':28s} | {'코드':>5} | {'크기':>7} | {'완화':<10} | 판정")
    print("-" * 78)

    # 기준선 — 지금 쓰는 방식
    try:
        import requests
        r = requests.get(URL, timeout=25, headers={
            "User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"})
        show("requests (지금 방식)", r.status_code, len(r.content),
             r.headers.get("cf-mitigated", "-"))
    except Exception as e:
        show("requests (지금 방식)", "예외", 0, "-", repr(e)[:60])
    time.sleep(4)

    # curl_cffi — 크롬 TLS 지문 흉내
    try:
        from curl_cffi import requests as creq
    except Exception as e:
        print(f"curl_cffi 를 못 불러왔다: {e}")
        return

    for target in ("chrome", "chrome124", "chrome120", "chrome110",
                   "safari17_0", "edge101"):
        try:
            r = creq.get(URL, impersonate=target, timeout=30,
                         headers={"Accept-Language": "ko-KR,ko;q=0.9"})
            show(f"curl_cffi {target}", r.status_code, len(r.content),
                 r.headers.get("cf-mitigated", "-"))
        except Exception as e:
            show(f"curl_cffi {target}", "예외", 0, "-", repr(e)[:60])
        time.sleep(4)

    # 통과한 지문으로 연속 3회 — 한 번 운이 아니라 꾸준한지
    print("\n같은 지문으로 연속 3회 (꾸준한지 확인)")
    for i in range(3):
        try:
            r = creq.get(URL, impersonate="chrome", timeout=30,
                         headers={"Accept-Language": "ko-KR,ko;q=0.9"})
            show(f"  반복 {i+1} (chrome)", r.status_code, len(r.content),
                 r.headers.get("cf-mitigated", "-"))
        except Exception as e:
            show(f"  반복 {i+1} (chrome)", "예외", 0, "-", repr(e)[:60])
        time.sleep(4)


if __name__ == "__main__":
    main()
