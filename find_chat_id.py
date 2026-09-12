# -*- coding: utf-8 -*-
"""
텔레그램 chat id 찾기 도우미

주소를 손으로 만들지 않아도 되게, 토큰만 붙여넣으면 getUpdates 를 대신 호출해
찾은 대화방을 보기 좋게 늘어놓는다. 채널은 따로 표시한다.

    python find_chat_id.py

토큰을 물어보면 BotFather 가 준 줄을 그대로 붙여넣고 엔터.
"""

APP_VERSION = "1.0.01"

import json
import re
import sys

import requests

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass


def clean_token(raw):
    """붙여넣을 때 흔히 끼는 것들을 털어낸다 (꺾쇠, 공백, 주소 전체를 붙인 경우)."""
    t = (raw or "").strip().strip("<>").strip()
    # 주소를 통째로 붙여넣었을 때: .../bot<토큰>/getUpdates 에서 토큰만 꺼낸다
    m = re.search(r"/bot([0-9]{5,}:[A-Za-z0-9_-]{20,})", t)
    if m:
        return m.group(1)
    t = t.replace(" ", "")
    if t.lower().startswith("bot"):
        t = t[3:]
    return t


def walk_chats(updates):
    """업데이트 묶음에서 나온 모든 대화방을 (id, type, 제목, 어디서 나왔나) 로 모은다."""
    found = {}

    def add(chat, where):
        if not isinstance(chat, dict) or "id" not in chat:
            return
        cid = chat["id"]
        name = chat.get("title") or " ".join(
            x for x in (chat.get("first_name"), chat.get("last_name")) if x
        ) or chat.get("username") or "(이름없음)"
        prev = found.get(cid)
        if prev is None:
            found[cid] = {"type": chat.get("type", "?"), "name": name, "where": {where}}
        else:
            prev["where"].add(where)

    for u in updates:
        for key in ("message", "edited_message", "channel_post", "edited_channel_post",
                    "my_chat_member", "chat_member"):
            ev = u.get(key)
            if not isinstance(ev, dict):
                continue
            add(ev.get("chat"), key)
            add(ev.get("forward_from_chat"), "전달된 채널")
            add(ev.get("sender_chat"), "보낸 채널")
    return found


def main():
    token = clean_token(sys.argv[1] if len(sys.argv) > 1 else "")
    if not token:
        print("BotFather 가 준 토큰을 붙여넣고 엔터를 눌러라.")
        print("(8123456789:AAF... 형태. 주소를 통째로 붙여도 알아서 자른다)")
        try:
            token = clean_token(input("토큰> "))
        except (EOFError, KeyboardInterrupt):
            return 1
    if not re.match(r"^[0-9]{5,}:[A-Za-z0-9_-]{20,}$", token):
        print(f"\n토큰 모양이 이상하다: {token[:12]}...")
        print("숫자 → 콜론(:) → 긴 문자열 형태여야 한다. BotFather 대화에서 다시 복사해라.")
        return 2

    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=20)
        data = r.json()
    except Exception as e:
        print(f"\n호출 실패: {e}")
        print("인터넷이나 방화벽 문제일 수 있다.")
        return 3

    if not data.get("ok"):
        code = data.get("error_code")
        print(f"\n텔레그램이 거절했다 ({code}): {data.get('description')}")
        if code == 404:
            print("→ 토큰이 틀렸다. BotFather 대화에서 토큰 줄을 통째로 다시 복사해라.")
        elif code == 409:
            print("→ 이 봇에 웹훅이 걸려 있다. 아래를 브라우저로 한 번 열어 지운 뒤 다시 해라:")
            print(f"   https://api.telegram.org/bot{token}/deleteWebhook")
        return 4

    updates = data.get("result", [])
    found = walk_chats(updates)

    if not found:
        print("\n아무 대화방도 못 찾았다. 업데이트가 비어 있다.")
        print("다음을 하고 다시 실행해라:")
        print("  1) 채널에 아무 글이나 하나 올린다")
        print("  2) 그 글을 길게 눌러 → 전달 → 네 봇에게 보낸다")
        print("     (봇과 1:1 대화에서 START 를 한 번 눌러둬야 전달 대상에 나온다)")
        print("  ※ 텔레그램은 업데이트를 24시간만 보관한다. 오래됐으면 새로 한 번 더 전달해라.")
        return 5

    channels = {k: v for k, v in found.items() if v["type"] == "channel"}
    others = {k: v for k, v in found.items() if v["type"] != "channel"}

    print(f"\n찾은 대화방 {len(found)}개\n")
    if channels:
        print("=== 채널 (이 중에서 골라라) ===")
        for cid, v in channels.items():
            print(f"  TELEGRAM_CHAT_ID = {cid}")
            print(f"    이름: {v['name']}")
        print()
    if others:
        print("=== 그 외 (개인 대화·그룹 — 채널로 받을 거면 쓰지 않는다) ===")
        for cid, v in others.items():
            print(f"  {cid}  [{v['type']}]  {v['name']}")
        print()

    if not channels:
        print("채널이 안 보인다. 채널 글을 봇에게 '전달' 했는지 확인해라.")
        print("(봇을 관리자로만 추가해도 채널이 안 나올 수 있다 — 전달이 확실한 방법이다)")

    if len(sys.argv) > 2 and sys.argv[2] == "--raw":
        print("--- 원본 ---")
        print(json.dumps(data, ensure_ascii=False, indent=1)[:4000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
