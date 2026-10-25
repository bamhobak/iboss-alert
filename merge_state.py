# -*- coding: utf-8 -*-
"""
state.json 합치기 — 깃 충돌로 기록을 잃지 않게 한다.

쓰임: 워크플로의 '상태 저장' 단계에서, 작업트리를 원격 최신으로 되돌린 뒤
      내 실행이 만든 state 를 그 위에 얹을 때 쓴다.

    python merge_state.py <내_state.json>

현재 폴더의 state.json(= 원격 최신)에 인자로 준 파일(= 내 실행 결과)을 합쳐
state.json 에 다시 쓴다. 몇 번을 돌려도 결과가 같다(여러 번 재시도해도 안전).

합치는 규칙
  seen          : 양쪽 합집합. 알림을 두 번 보내지 않으려면 하나도 버리면 안 된다.
  seeded        : 한쪽이라도 True 면 True
  fail_streak   : 내 값(내 실행이 방금 본 결과가 최신이다)
  fail_notified : 내 값
  last_run      : 내 값
"""

import json
import sys
from pathlib import Path

KEEP_SEEN = 300          # iboss_alert.py 와 같은 값


def load(p):
    try:
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def main():
    if len(sys.argv) < 2:
        print("쓰임: python merge_state.py <내_state.json>", file=sys.stderr)
        return 2

    mine = load(sys.argv[1])          # 내 실행 결과
    theirs = load("state.json")       # 원격 최신

    if not mine:
        print("내 state 를 읽지 못했다 — 합치지 않는다", file=sys.stderr)
        return 1

    seen = {int(x) for x in theirs.get("seen", [])} | {int(x) for x in mine.get("seen", [])}
    out = {
        "seen": sorted(seen, reverse=True)[:KEEP_SEEN],
        "seeded": bool(theirs.get("seeded")) or bool(mine.get("seeded")),
        "last_run": mine.get("last_run", ""),
        "fail_streak": int(mine.get("fail_streak", 0)),
        "fail_notified": bool(mine.get("fail_notified", False)),
    }
    Path("state.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    only_mine = len(seen) - len({int(x) for x in theirs.get("seen", [])})
    print(f"합침: 원격 {len(theirs.get('seen', []))}건 + 내 것 {len(mine.get('seen', []))}건 "
          f"→ {len(out['seen'])}건 (새로 들어간 글 {only_mine}건)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
