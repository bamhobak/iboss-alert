# -*- coding: utf-8 -*-
"""
아이보스 '대행의뢰' 게시판 새글 감시 → 텔레그램 알림

- 대상: https://www.i-boss.co.kr/ab-1957  (분류는 CATEGORIES 로 지정, 기본 BCV)
- 판정: 글번호(/ab-1958-<번호>)로 한다. 제목이나 순서는 바뀔 수 있지만 번호는 안 바뀐다.
- 상태: state.json 에 이미 알린 글번호를 남긴다. 레포에 커밋해 다음 실행이 이어받는다.
- 첫 실행: 알림을 보내지 않고 현재 목록만 기록한다(수십 개가 한꺼번에 날아가는 걸 막는다).
  일부러 과거분을 받고 싶으면 SEED=0 으로 돌린다.

환경변수
  TELEGRAM_TOKEN    (필수) 봇 토큰
  TELEGRAM_CHAT_ID  (필수) 보낼 대화방 id (채널이면 -100... 또는 @채널명)
  CATEGORIES        감시할 분류 코드, 쉼표 구분 (기본 BCV)
  SEED              1=상태파일 없으면 알림 없이 기록만 (기본 1)
  INCLUDE_CLOSED    1=[마감] 글도 알림 (기본 0)
  DRY_RUN           1=텔레그램 전송 없이 콘솔에만 (기본 0)
"""

APP_VERSION = "1.0.03"

import html
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

# 윈도우 콘솔(cp949)에서 한글·중점(·)이 터지지 않게
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE = "https://www.i-boss.co.kr"
LIST_URL = BASE + "/ab-1957"
STATE_PATH = Path(__file__).with_name("state.json")

# 이미 알린 글번호를 몇 개까지 들고 갈지. 게시판이 하루 몇 건이라 300 이면 몇 달치다.
KEEP_SEEN = 300

# 게시판 분류 코드 → 이름 (게시판 HTML 의 관심분야 선택기에서 그대로 가져왔다)
CATEGORY_NAMES = {
    "IMC": "통합광고대행", "BCV": "블로그·카페·바이럴", "SNS": "SNS마케팅",
    "YTB": "유튜브·영상·PPL", "SEO": "검색최적화·SEO", "CPA": "CPA·CPS",
    "KWD": "키워드광고", "SHP": "지식쇼핑·스토어", "LVC": "라이브커머스",
    "배너광고": "배너광고", "INF": "체험단", "NWS": "언론홍보",
    "APP": "앱·모바일", "OFF": "오프라인광고", "AI": "AI",
    "SIT": "웹사이트 제작", "LAD": "랜딩페이지", "DES": "디자인",
    "SAL": "상품 판매요청", "AGE": "대대행사", "ETC": "기타",
}

def load_dotenv():
    """옆에 .env 가 있으면 읽어 온다(로컬 테스트용). 이미 있는 환경변수는 덮지 않는다."""
    f = Path(__file__).with_name(".env")
    if not f.exists():
        return
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if v and not os.environ.get(k):
            os.environ[k] = v


load_dotenv()

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")


def env_flag(name, default="0"):
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "y")


def strip_tags(s):
    s = re.sub(r"<[^>]*>", "", s or "")
    return html.unescape(s).replace("\xa0", " ").strip()


def fetch_list(category):
    """분류 하나의 목록 HTML 을 받아 온다."""
    url = LIST_URL if not category else f"{LIST_URL}?category_1={category}"
    last_err = None
    for attempt in range(3):
        try:
            r = requests.get(url, headers={"User-Agent": UA,
                                           "Accept-Language": "ko-KR,ko;q=0.9"},
                             timeout=20)
            r.raise_for_status()
            r.encoding = r.apparent_encoding or "utf-8"
            return r.text
        except Exception as e:          # 일시적인 실패는 몇 초 쉬고 다시
            last_err = e
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"목록을 받지 못했다: {url} ({last_err})")


# 목록의 한 칸: <div class="cell"> ... </div> 안에 bd_open / bd_closed 가 들어 있다
CELL_RE = re.compile(r'<div class="cell">(.*?)(?=<div class="cell">|<div class="paging|</form>)',
                     re.S)
ID_RE = re.compile(r'href="/ab-1958-(\d+)"')
TITLE_RE = re.compile(r'<div class="subject">(.*?)</div>', re.S)
CAT_RE = re.compile(r'<a class="cat"[^>]*>(.*?)</a>', re.S)
BUDGET_RE = re.compile(r'<span class="budget">\s*예산\s*<em>(.*?)</em>', re.S)
TOB_RE = re.compile(r'<span class="BDU_tob">\s*업종\s*<em[^>]*>(.*?)</em>', re.S)
DATE_RE = re.compile(r'<span class="sign_date">\s*등록일\s*<em>(.*?)</em>', re.S)


def parse_list(page_html, fallback_category=""):
    """목록 HTML → 글 목록. 위(최신)에서 아래(과거) 순서 그대로 돌려준다."""
    items = []
    for chunk in CELL_RE.findall(page_html):
        m = ID_RE.search(chunk)
        if not m:                        # 광고·공지 칸은 글번호가 없다
            continue
        pid = int(m.group(1))
        raw_title = TITLE_RE.search(chunk)
        raw_title = raw_title.group(1) if raw_title else ""
        closed = 'class="bd_closed"' in chunk or 'class="closed"' in raw_title
        title = strip_tags(re.sub(r'<em class="closed">.*?</em>', "", raw_title, flags=re.S))
        cat = CAT_RE.search(chunk)
        items.append({
            "id": pid,
            "title": title or "(제목 없음)",
            "url": f"{BASE}/ab-1958-{pid}",
            "category": strip_tags(cat.group(1)) if cat else CATEGORY_NAMES.get(
                fallback_category, fallback_category),
            "budget": strip_tags(BUDGET_RE.search(chunk).group(1)) if BUDGET_RE.search(chunk) else "",
            "industry": strip_tags(TOB_RE.search(chunk).group(1)) if TOB_RE.search(chunk) else "",
            "date": strip_tags(DATE_RE.search(chunk).group(1)) if DATE_RE.search(chunk) else "",
            "closed": closed,
        })
    return items


def load_state():
    if not STATE_PATH.exists():
        return {"seen": [], "seeded": False, "last_run": ""}
    try:
        st = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        # 상태파일이 깨졌으면 새로 시작한다. 알림이 한 번 몰리는 것보다 낫다.
        return {"seen": [], "seeded": False, "last_run": ""}
    st.setdefault("seen", [])
    st.setdefault("seeded", bool(st["seen"]))
    return st


def save_state(st, dry=False):
    if dry:
        print("(드라이런: state.json 을 쓰지 않는다)")
        return
    st["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    st["seen"] = sorted(set(int(x) for x in st["seen"]), reverse=True)[:KEEP_SEEN]
    STATE_PATH.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def send_telegram(token, chat_id, text):
    """전송 성공 여부를 돌려준다. 실패한 글은 seen 에 넣지 않아 다음 실행에 다시 시도된다."""
    api = f"https://api.telegram.org/bot{token}/sendMessage"
    for attempt in range(3):
        try:
            r = requests.post(api, timeout=20, data={
                "chat_id": chat_id,
                "text": text,
                # 미리보기 카드(제목·요약·이미지)를 살린다 — 사진처럼 보이게 하는 게 이거다
                "disable_web_page_preview": "false",
            })
            if r.status_code == 200 and r.json().get("ok"):
                return True
            body = r.text[:300]
            # 429 는 잠깐 쉬면 풀린다. 그 외 4xx 는 설정 문제라 재시도해도 같다.
            if r.status_code == 429:
                wait = 0
                try:
                    wait = int(r.json()["parameters"]["retry_after"])
                except Exception:
                    wait = 5
                time.sleep(wait + 1)
                continue
            print(f"  [텔레그램 실패 {r.status_code}] {body}", flush=True)
            if 400 <= r.status_code < 500:
                return False
        except Exception as e:
            print(f"  [텔레그램 오류] {e}", flush=True)
        time.sleep(3 * (attempt + 1))
    return False


def main():
    token = os.environ.get("TELEGRAM_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    dry = env_flag("DRY_RUN")
    if not dry and not (token and chat_id):
        print("TELEGRAM_TOKEN / TELEGRAM_CHAT_ID 가 없다.", file=sys.stderr)
        return 2

    categories = [c.strip() for c in os.environ.get("CATEGORIES", "BCV").split(",") if c.strip()]
    seed_mode = env_flag("SEED", "1")
    include_closed = env_flag("INCLUDE_CLOSED")

    st = load_state()
    seen = set(int(x) for x in st["seen"])

    found = []
    for cat in categories:
        items = parse_list(fetch_list(cat), cat)
        if not items:
            # 한 건도 못 뽑았으면 차단이거나 화면이 바뀐 것이다. 조용히 넘기면 알림이 죽는다.
            print(f"[경고] {cat} 목록에서 글을 하나도 못 뽑았다 "
                  f"(차단 또는 HTML 변경 의심)", file=sys.stderr)
            return 3
        print(f"[{cat}] {len(items)}건 파싱 (최신 {items[0]['id']})")
        found.extend(items)

    # 글번호 중복 제거 후, 오래된 글부터 보낸다 → 최신 글이 맨 아래(가장 최근 메시지)에 온다
    uniq = {}
    for it in found:
        uniq.setdefault(it["id"], it)
    new_items = [it for pid, it in sorted(uniq.items())
                 if pid not in seen and (include_closed or not it["closed"])]

    # 알림은 건너뛰지만 목록에 있던 모든 글(마감 포함)은 기록해 둔다
    all_ids = list(uniq.keys())

    if not st["seeded"] and seed_mode:
        st["seen"] = list(seen | set(all_ids))
        st["seeded"] = True
        save_state(st, dry)
        print(f"첫 실행: 알림 없이 {len(all_ids)}건 기록. 다음 실행부터 새글만 알린다.")
        return 0

    if not new_items:
        st["seen"] = list(seen | set(all_ids))
        st["seeded"] = True
        save_state(st, dry)
        print("새글 없음")
        return 0

    sent = 0
    for it in new_items:
        text = f"{it['category']}\n{it['title']}\n{it['url']}"
        if dry:
            print("--- 보낼 내용 ---\n" + text)
            ok = True
        else:
            ok = send_telegram(token, chat_id, text)
        if ok:
            seen.add(it["id"])
            sent += 1
            print(f"알림: {it['id']} {it['title'][:40]}")
            time.sleep(1.2)          # 텔레그램 속도 제한(초당 여러 건) 여유
        else:
            print(f"보류: {it['id']} — 다음 실행에 다시 시도한다")

    # 마감된 글 등 알림 대상이 아니었던 것도 이제 기록한다(다음에 열려도 다시 안 보내게)
    st["seen"] = list(seen | {pid for pid, it in uniq.items()
                              if not (include_closed or not it["closed"])})
    st["seeded"] = True
    save_state(st, dry)
    print(f"완료: {sent}/{len(new_items)}건 전송 (v{APP_VERSION})")
    return 0 if sent == len(new_items) else 1


if __name__ == "__main__":
    sys.exit(main())
