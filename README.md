# 안개 항구의 마지막 배

배가 떠나기 전에 사라진 선원을 찾아야 합니다. 사람을 만나고 단서를 모아 구출 방법을 선택하는 한국어 웹 TRPG입니다. 전투에서도 상대의 말을 듣고 화해할 수 있으며, 항구는 당신의 선택을 기억합니다.

인물·장소·소지품·지식·관계를 그래프로 보관하고, 작성된 조건과 결과로 이야기를 진행합니다. 첫 이야기는 장소 5곳, 인물 6명, 시작 성향 3개, 결말 5개로 구성됩니다. 전투는 하트와 주사위를 사용하는 턴제입니다.

## 로컬 실행

Python 3.13과 Node.js 24에서 검증합니다. 저장소 루트에서 한 번 설치합니다.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
cd client
npm i
```

두 터미널을 열어 실행합니다.

```powershell
# 터미널 1: 저장소 루트
.\.venv\Scripts\python.exe server/run_api.py --local
```

```powershell
# 터미널 2: client/
npm run web
```

브라우저에서 **http://localhost:8081**을 엽니다. API는 `127.0.0.1:8000`이며, 두 명령은 같은 로컬 접속 설정을 사용합니다. 개인 환경 파일을 수정할 필요가 없습니다. `npm run web:local`도 같은 명령입니다.

## 휴대폰에서 플레이

`client/`에서 실행하면 웹과 API를 함께 시작합니다.

```powershell
npm run dev:public
```

터미널에 표시되는 **https://…trycloudflare.com** 주소를 폰에서 엽니다. LTE와 다른 와이파이에서도 접속할 수 있습니다. 실행하는 동안 주소가 유지되고, 재실행하면 주소가 바뀝니다. Windows x64에서는 Cloudflare 공식 도구를 최초 실행 때 다운로드하고 배포 체크섬을 확인합니다. 다른 환경에서는 `cloudflared`를 먼저 설치합니다. [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)

같은 와이파이에서만 접속하려면 `npm run dev`를 실행하고 출력된 `http://서버IP:8081` 주소를 사용합니다. 웹과 API가 같은 주소를 사용합니다. 이미 실행 중인 로컬 모험 API가 있으면 재사용하며, 새로 시작한 프로세스는 Ctrl+C로 함께 종료합니다. 기존 저장 폴더와 인증은 그대로 사용합니다. 8081 포트에서 이전 웹 명령이 실행 중이면 먼저 종료합니다.

## 플레이

1. 이름과 성향을 고르고 항구에 도착합니다.
2. **이전·다음**으로 이야기를 읽고 **행동 선택**을 누릅니다. 행동을 열면 비용·성공률·필요 조건을 확인할 수 있으며, **이 선택을 합니다**를 눌러 실행합니다.
3. **이동**에서 비용을 확인하고 장소를 누르면 이동합니다. **수첩**에서 단서, 소지품·기술과 기록을 확인합니다. 긴 글과 목록은 페이지로 넘기며, 읽기와 수첩 탐색은 시간을 쓰지 않습니다.
4. 출항까지 24칸 안에 구출과 탈출을 준비합니다. 전투에서는 공격·방어·도주·기술·도구 또는 대화를 선택합니다.
5. 구출 후 기술을 배우고, 동료와 함께 선택의 후일담을 확인합니다.

선택마다 자동 저장됩니다. 같은 브라우저에서 새로고침하면 이어집니다. 연결이 끊기면 **다시 시도합니다**를 누릅니다. 같은 선택은 중복 적용되지 않습니다. 새 모험은 이어하기 위치를 바꾸며 이전 저장 파일은 남겨 둡니다.

## 어디를 고치나요?

| 목적 | 파일 |
|---|---|
| 대사·단서·선택·결말 | [scenarios/harbor/adventure.json](scenarios/harbor/adventure.json) |
| 행동 조건·비용·판정·성장 | [server/src/game/engine.py](server/src/game/engine.py) |
| API·저장·응답 흐름 | [server/README.md](server/README.md) |
| 장면·전투·수첩 화면 | [client/screens/GameScreen.tsx](client/screens/GameScreen.tsx) |
| 화면 상태·재시도 | [client/logic/useGame.ts](client/logic/useGame.ts) |
| 색상·간격·글자 크기 | [client/design/tokens.js](client/design/tokens.js) |
| 게임 설계와 다음 개선 | [plan.md](plan.md) |

서버가 게임 상태와 문장을 결정하고 클라이언트가 그대로 표시합니다. 클라이언트 소유 문구는 `client/locale/ko.ts`, 서버의 공통 문구는 `server/src/locale/ko.py`에 있습니다.

## 검증

저장소 루트에서 실행합니다.

```powershell
.\.venv\Scripts\python.exe server/validate_adventure.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check server/
# Git Bash
& 'C:/Program Files/Git/bin/bash.exe' server/scripts/check_relational_ssot.sh
```

`client/`에서 실행합니다.

```powershell
npm test -- --runInBand
npx tsc --noEmit
npm run lint
npm run build:web
```

웹 빌드는 로컬 API에 연결되는 `client/dist/`를 만듭니다. 웹 화면은 그림과 스크롤 없이 한 화면에서 진행하는 모바일 구성입니다. PC에서도 같은 폭으로 표시합니다. 화면 변경은 320×568, 412×915와 PC 폭에서 페이지 넘김·버튼·잘림을 확인합니다. 글자 크기나 Tailwind 설정을 바꾼 뒤에는 `npm run web -- --clear`로 다시 실행합니다.

## 저장과 실행 범위

저장은 `saves/adventure/adv_<id>.json`입니다. 그래프·전투·기록·난수 순서·요청 영수증을 한 파일로 교체하므로 한 턴이 함께 저장됩니다. 브라우저에는 `trpg.adventure_game_id`만 보관합니다. 저장 파일과 개인 환경 파일은 Git에서 제외합니다.

파일 저장은 **단일 서버 프로세스**용입니다. 서버를 재시작해도 같은 저장 폴더를 사용해야 합니다. 현재 엔진은 항구 이야기의 인물과 사건을 사용하므로 새 캠페인을 JSON만 바꿔 실행하는 범용 제작기는 아닙니다. 재미와 회차 길이의 균형은 실제 플레이 평가로 다듬을 과제입니다.

다른 API 주소나 저장 폴더를 사용하려면 [서버 설정](server/README.md)과 [클라이언트 설정](client/README.md)을 따릅니다.
