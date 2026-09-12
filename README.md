# iboss-alert

아이보스 [대행의뢰 게시판](https://www.i-boss.co.kr/ab-1957?category_1=BCV)의 **블로그·카페·바이럴(BCV)**
분류에 새 의뢰가 올라오면 텔레그램으로 알린다. 10분 주기.

알림 형태(사진과 동일):

```
블로그·카페·바이럴
[정기 물량 / 공식 대행사 Direct] 블로그 배포 및 카페 작업 전문 실행사 모집합니다
https://www.i-boss.co.kr/ab-1958-88422
```

세 번째 줄의 주소를 텔레그램이 스스로 펼쳐서 제목·요약·이미지 미리보기 카드를 붙인다.
따로 만들어 보내는 게 아니다.

## 동작

| 항목 | 방식 |
|---|---|
| 새글 판정 | 글번호(`/ab-1958-<번호>`). 제목·순서는 바뀌어도 번호는 안 바뀐다 |
| 상태 | `state.json` 에 이미 알린 글번호(최근 300개). 매 실행 후 레포에 커밋 |
| 첫 실행 | 알림을 **보내지 않고** 현재 목록만 기록(20건이 한꺼번에 날아가는 것 방지) |
| 마감글 | 기본 제외. `INCLUDE_CLOSED=1` 이면 포함 |
| 전송 실패 | 그 글은 기록하지 않는다 → 다음 실행에 다시 시도 |
| 목록 0건 | 차단·화면변경으로 보고 **종료코드 3 으로 실패**(빨간불). 조용히 죽지 않게 |

## 설정

### 1. 텔레그램 봇 만들기

1. 텔레그램에서 [@BotFather](https://t.me/BotFather) 에게 `/newbot` → 이름·아이디 입력 → **토큰**을 받는다.
2. 알림을 받을 곳을 정한다.
   - **개인 대화**: 만든 봇과 대화를 열고 아무 말이나 한 번 보낸다.
   - **채널**: 채널을 만들고 봇을 관리자로 추가한다.
3. **chat id** 확인:
   ```
   https://api.telegram.org/bot<토큰>/getUpdates
   ```
   를 브라우저로 열어 `"chat":{"id":123456789` 값을 쓴다.
   채널은 `-100...` 으로 시작한다. 공개 채널이면 `@채널명` 도 된다.

### 2. GitHub 레포

```powershell
cd g:\vscode\iboss-alert
git init -b main
git add -A
git commit -m "아이보스 대행의뢰 BCV 새글 텔레그램 알림"
gh repo create iboss-alert --public --source=. --push
```

> **공개(`--public`)로 만드는 게 좋다.** 10분 주기면 하루 144회 · 월 약 4,500분이다.
> 비공개 레포는 월 무료 2,000분이라 초과분이 과금된다. 공개 레포는 Actions 가 무제한 무료다.
> 이 레포에 비밀은 없다(토큰은 Secrets 에 들어간다).

### 3. Secrets 넣기

레포 → Settings → Secrets and variables → Actions:

| 종류 | 이름 | 값 |
|---|---|---|
| Secret | `TELEGRAM_TOKEN` | BotFather 토큰 |
| Secret | `TELEGRAM_CHAT_ID` | 위에서 찾은 chat id |
| Variable (선택) | `CATEGORIES` | 기본 `BCV`. 늘리려면 `BCV,SEO,INF` 처럼 |

```powershell
gh secret set TELEGRAM_TOKEN
gh secret set TELEGRAM_CHAT_ID
```

### 4. 첫 실행

Actions → `iboss-alert` → **Run workflow** (seed 체크 유지).
알림 없이 현재 20건만 기록하고 `state.json` 을 커밋한다. 다음 실행부터 새글만 온다.

## 정시를 소유하기 — 외부 스케줄러 (권장)

GitHub 예약은 밀리거나 통째로 유실된다(kospi-volume 에서 실측: 5일간 기대 10회 중 4회만 발화,
지연 중앙값 3시간). **간격이 짧을수록 더 밀린다.** GitHub 예약만 믿으면 새글을 한참 늦게 받는다.

[cron-job.org](https://cron-job.org) 에 무료 계정을 만들어 10분마다 아래를 때리게 해두면
시각을 우리가 갖는다(워크플로의 `repository_dispatch: [check]` 입구).

- URL: `https://api.github.com/repos/<계정>/iboss-alert/dispatches`
- Method: `POST`
- Headers:
  - `Authorization: Bearer <레포 contents:write 권한 PAT>`
  - `Accept: application/vnd.github+json`
- Body: `{"event_type":"check"}`

또 하나: 레포가 60일간 조용하면 GitHub 이 예약 워크플로를 자동으로 끈다.
`state.json` 커밋이 매번 일어나니 보통은 걸리지 않지만, 경고 메일이 오면 커밋 한 번 밀면 된다.

## 로컬에서 확인

```powershell
$env:DRY_RUN="1"; $env:SEED="0"; python iboss_alert.py
```

전송도 상태 저장도 하지 않고, 보낼 내용만 찍는다.

실제로 한 번 보내 보려면:

```powershell
$env:TELEGRAM_TOKEN="..."; $env:TELEGRAM_CHAT_ID="..."; python iboss_alert.py
```

## 알아둘 것

- 게시판은 로그인·쿠키 없이 열린다(실측 200). 대신 **GitHub Actions 의 데이터센터 IP 를
  아이보스가 막는지는 첫 실행 로그로 확인해야 한다.** 막히면 목록 0건 → 빨간불로 드러난다.
  그때는 내 PC 상주(작업 스케줄러) 또는 Cloudflare Workers cron 으로 옮기면 된다.
- 목록 첫 페이지(20건)만 본다. 10분 주기라 그 사이 21건이 올라올 일은 없다.
