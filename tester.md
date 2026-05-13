# dev_test Tester

`scenarios/dev_test`는 로컬 QA용 시드다. 한 기능을 짧게 확인한 뒤 새 게임을 다시 시작하는 방식으로 쓰면 상태 오염을 피할 수 있다.

## 실행 원칙

이 문서에 따른 테스트는 **백그라운드 CLI 자동화**로 실행한다.

금지:

- Codex in-app browser로 클릭하며 진행
- Chrome 원격 조작으로 클릭하며 진행
- 사람이 화면을 보면서 수동 클릭
- Playwright spec 없이 임의 브라우저 세션에서 단계별 조작

반복 실행자는 아래 순서를 그대로 따른다.

1. PowerShell에서 시드 검증을 실행한다.
2. 서버와 클라이언트를 `Start-Process`로 백그라운드 실행한다.
3. `agency\qa\run_dev_test.ps1`를 실행해 기능 QA와 10-15개 플레이어 행동의 재미 플레이테스트를 한 번에 진행한다.
4. Playwright가 생성한 `output/tester/fun_playtest_transcript.json`을 읽어 재미 플레이테스트를 평가한다.
5. 결과는 로그 파일, Playwright 출력, 서버 저장 그래프 JSON, 재미 플레이테스트 transcript로 판정한다.
6. 기능 QA와 재미 플레이테스트가 모두 끝나면 repo 루트에 `report_{note}.md` 형식의 리포트를 작성한다.

완료 조건:

- 사용자가 `tester.md에 따라 테스트`, `테스트 진행`, `dev_test QA`처럼 말하면 기능 Playwright QA와 재미 플레이테스트를 모두 수행해야 한다.
- 기능 Playwright QA만 통과한 상태로 테스트가 끝났다고 말하거나 리포트를 마감하지 않는다.
- 재미 플레이테스트를 생략하려면 사용자가 먼저 명시적으로 제외해야 한다.

화면을 직접 조작해야 하는 예외는 "재현 영상이나 스크린샷이 필요한 시각 결함"뿐이다. 그 경우에도 먼저 CLI 자동화 실패 로그를 남긴 뒤 보조 확인으로만 화면을 연다.

## 고정 실행 명령

아래 명령은 repo 루트(`D:\code\trpg`)에서 실행한다. 포트가 이미 떠 있으면 기존 프로세스를 확인하고, 다른 테스트가 아닌 이전 QA 프로세스라고 판단될 때만 종료한다.

다음 명령 하나로 시드 검증, 서버/클라이언트 백그라운드 실행, readiness 대기, headless Playwright 기능 QA, 10-15개 플레이어 행동의 재미 플레이테스트, transcript 생성, 프로세스 정리까지 수행한다.

```powershell
.\agency\qa\run_dev_test.ps1
```

이 명령은 임시 자동화 파일을 새로 만들지 않는다. 고정 파일인 `agency/qa/dev_test.spec.ts`와 `agency/qa/run_dev_test.ps1`만 사용한다.

세부 실행이 필요할 때만 아래 개별 명령을 사용한다.

```powershell
.\.venv\Scripts\python.exe -m server.scripts.check_seed scenarios/dev_test
```

```powershell
$out = Join-Path (Get-Location) "output\tester"
New-Item -ItemType Directory -Force $out | Out-Null

$server = Start-Process `
  -FilePath "D:\code\trpg\.venv\Scripts\python.exe" `
  -ArgumentList "run_api.py" `
  -WorkingDirectory "D:\code\trpg\server" `
  -RedirectStandardOutput "$out\server.stdout.log" `
  -RedirectStandardError "$out\server.stderr.log" `
  -WindowStyle Hidden `
  -PassThru

$client = Start-Process `
  -FilePath "npm.cmd" `
  -ArgumentList "run","web" `
  -WorkingDirectory "D:\code\trpg\client" `
  -RedirectStandardOutput "$out\client.stdout.log" `
  -RedirectStandardError "$out\client.stderr.log" `
  -WindowStyle Hidden `
  -PassThru

$server.Id
$client.Id

$deadline = (Get-Date).AddSeconds(90)
do {
  Start-Sleep -Seconds 2
  $serverReady = $false
  $clientReady = $false
  try { $serverReady = (Invoke-WebRequest -Uri "http://127.0.0.1:8001/docs" -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200 } catch {}
  try { $clientReady = (Invoke-WebRequest -Uri "http://localhost:8081" -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200 } catch {}
} until (($serverReady -and $clientReady) -or (Get-Date) -gt $deadline)

if (-not ($serverReady -and $clientReady)) {
  throw "server/client did not become ready within 90 seconds"
}
```

```powershell
playwright --version
Test-Path .\agency\qa\dev_test.spec.ts
Test-Path .\agency\qa\run_dev_test.ps1
.\agency\qa\run_dev_test.ps1
```

`Test-Path`가 `False`를 출력하면 테스트를 중단한다. spec이나 runner를 `output/tester/`에 새로 만들지 않는다.

QA가 끝나면 이 실행에서 받은 `$server.Id`, `$client.Id`만 종료한다.

```powershell
Stop-Process -Id $server.Id,$client.Id
```

테스트 스크립트는 repo 루트에 `package.json`, `package-lock.json`, `node_modules`를 만들지 않는다. dev_test 자동화는 `agency/qa/dev_test.spec.ts`와 `agency/qa/run_dev_test.ps1`만 표준으로 사용한다.

## 리포트 작성

QA가 끝나면 성공/실패와 관계없이 repo 루트에 `report_{note}.md`를 작성한다. `{note}`는 짧은 영문 소문자/숫자/밑줄 이름으로 쓰고, 예시는 `report_dev_test.md`, `report_item_guard.md`다.

리포트는 기능 QA와 재미 플레이테스트를 모두 포함해야 한다. 기능 QA만 적은 리포트는 완료 리포트가 아니다.

리포트에는 아래 항목을 포함한다.

- 실행 일시와 실행 명령
- 시드 검증 결과
- Playwright 요약: 통과/실패 개수
- 실패 항목: 테스트명, 기대값, 실제값, 관련 로그 또는 error-context 경로
- 생성된 `game_id`가 확인되면 해당 ID
- 재미 플레이테스트 실행 방식과 `game_id`
- 재미 플레이테스트 transcript 요약: 턴 번호, 입력 또는 action payload, 핵심 GM 반응, 상태 변화
- 재미 플레이테스트 점수표: 다음 행동 욕구, 세계 반응성, 실패의 맛, 나레이션 다양성, 상태 변화 체감, 다시 하고 싶은 정도
- 다음 수정으로 이어질 원인 메모. 기능 실패와 재미/몰입 개선 메모가 있으면 분리해서 쓴다.

## 준비

시드 무결성을 먼저 확인한다.

```powershell
.\.venv\Scripts\python.exe -m server.scripts.check_seed scenarios/dev_test
```

현재 머신에는 전역 Playwright가 설치되어 있다. 평소 QA에서는 설치 명령을 다시 실행하지 않고 `playwright` CLI를 바로 사용한다.

새 머신이거나 `playwright --version`이 실패할 때만 아래 명령을 한 번 실행한다.

```powershell
npm install -g playwright
playwright install chromium
playwright --version
```

QA 자동화는 `playwright` CLI를 기준으로 실행한다. 일반 `node` 스크립트에서 `require('playwright')`를 직접 쓰려면 로컬 의존성이 필요하므로, repo 루트에 임시 `node_modules`를 만들지 않는 운영에서는 CLI 방식으로 작성한다. repo 루트의 `package.json`, `package-lock.json`, `node_modules`는 Playwright 실행용으로 만들지 않는다. 생기면 QA 임시 파일로 보고 정리한다.

로컬 시드를 서버에서 읽으려면 `server/.env.dev`에 아래 값이 필요하다.

```env
SCENARIO_REPO=local
SCENARIO_DIR=../scenarios
GRAPH_REPO=local
GRAPH_SAVE_DIR=../qa_test/local_graph
```

현재 repo의 `server/.env.dev`가 다른 `GRAPH_SAVE_DIR`을 쓰면 그 값을 따른다. 판정용 JSON 경로도 같은 디렉터리 아래의 `games/<game_id>/`를 읽는다.

개발 중 사람이 직접 띄울 때만 아래 명령을 쓴다. 자동 QA에서는 위의 `Start-Process` 고정 명령을 사용한다.

```powershell
cd server
..\.venv\Scripts\python.exe run_api.py
```

```powershell
cd client
npm start
```

새 게임은 `dev_test` 프로필, `human` 종족으로 시작한다. 이름은 자유롭게 넣고, 성별은 UI에서 제공하는 값 중 하나를 고른다.

## CLI 체크리스트

아래 체크리스트는 사람이 화면을 보며 클릭하라는 뜻이 아니다. Playwright spec에서 각 단계를 함수로 만들고, 액션 전후의 UI 텍스트와 `/session/{game_id}/graph/state` 응답 또는 `GRAPH_SAVE_DIR/games/<game_id>/` JSON을 함께 검증한다.

각 기능 묶음은 가능한 한 새 게임과 독립 test 또는 독립 블록으로 나눈다. 한 체크가 실패해도 뒤 체크가 가려지지 않도록 상태 검증에는 `expect.soft`를 우선 사용하고, 다음 블록을 계속 실행한다. 단, 서버 시작 실패, spec 파일 없음, HTTP 5xx처럼 테스트 환경 자체가 무너진 경우만 즉시 중단한다.

권장 spec 구조:

```ts
import { test, expect } from "playwright/test";

test.describe("dev_test QA", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("http://localhost:8081");
    await page.setViewportSize({ width: 412, height: 915 });
    await page.evaluate(() => localStorage.clear());
  });

  test("시작과 대화", async ({ page }) => {
    // 새 게임 생성, 인트로 스트리밍, 대화/이동 검증
  });
});
```

텍스트 액션은 가능하면 UI 입력창을 통해 보내서 실제 클라이언트 경로를 검증한다. LLM 분류가 흔들려 기능 검증이 막힐 때만 이 문서의 "정확한 Action Payload"를 API에 직접 보낸다.

각 묶음은 새 게임에서 시작하는 것을 권장한다.
실패하거나 거부된 행동도 조용히 끝나지 않고, 실패 이유나 장면 반응을 담은 GM 나레이션 로그가 따라와야 한다.

### 시작과 대화

1. 새 게임을 시작한다.
2. 인트로 GM 로그가 한 번에 붙지 않고 스트리밍으로 누적되는지 본다.
3. `테스트 가이드에게 말을 건다`
4. `마을 주민에게 말을 건다`
5. `보급 구역으로 이동한다`
6. `보급 담당자에게 회복 아이템을 묻는다`

기대값: 시작 위치에는 가이드, 마을 주민, 허수아비, 들쥐, 보급 표식이 보인다. 보급 구역 이동 뒤 보급 담당자가 대상 목록에 보여야 한다.

### 이동과 획득

1. `준비실로 이동한다`
2. `테스트 허브로 이동한다`
3. 시작 장소의 `보급 표식`을 획득한다.

기대값: 위치 카드가 준비실과 테스트 허브로 바뀌고, 보급 표식이 인벤토리로 들어간다.

### 장비

1. `훈련 조끼를 장비한다`
2. `구리 반지를 장비한다`
3. `훈련 단검을 해제한다`

기대값: armor, accessory 슬롯이 채워지고, weapon 슬롯은 비며 훈련 단검은 인벤토리로 돌아온다.

### 퀘스트 확인

1. 퀘스트 제안 카드에서 `훈련 전투`를 수락한다.
2. 퀘스트 패널에서 포기를 누른다.

기대값: 수락과 포기 모두 확인창을 거친다. 포기 후 active quest가 비어야 한다.

### 보급품 누락 관계 분기

각 루트는 새 게임에서 시작한다.

고발 루트:

1. `마을 주민을 보급 담당자에게 고발한다`

기대값: `보급품 누락` 퀘스트가 완료되고, 보급 담당자와의 관계는 좋아지며 주민과의 관계는 나빠진다. 로그는 고발로 해결했다는 장면 반응을 보여야 한다.

중재 루트:

1. `마을 주민에게 누락된 보급품을 가져간 이유를 묻는다`
2. `보급 구역으로 이동한다`
3. `보급 담당자에게 주민의 사정을 봐 달라고 설득한다`

기대값: 먼저 주민의 사정이 확인되고, 이후 설득으로 퀘스트가 완료된다. 주민과 가이드 관계가 좋아지고 보급 담당자 관계도 조금 좋아진다.

조용한 반납 루트:

1. `보급품을 조용히 돌려놓는다`

기대값: 퀘스트가 조용한 반납으로 완료된다. 주민과의 관계가 좋아지고 `helped_quietly` 성격의 플래그가 저장된다.

### 하트 전투와 스킬/아이템 보조

1. `훈련 일격으로 훈련용 허수아비를 공격한다`
2. 공격 시작 확인창을 승인한다.

기대값: 전투 패널은 HP 피해가 아니라 내 하트 3/3, 적 하트 3/3에서 시작한다. `훈련 일격`은 MP 2를 소모하고 공격 판정 DC를 낮춘다. 성공하면 적 하트가 줄고, 승리해도 실제 HP는 줄지 않는다.

아이템 보조:

1. 새 게임을 다시 시작한다.
2. `투척 단검으로 훈련용 허수아비를 공격한다`
3. 공격 시작 확인창을 승인한다.

기대값: 투척 단검은 공격 보조로 쓰이고, 사용 뒤 인벤토리에서 사라진다. 스킬과 아이템을 한 턴에 동시에 붙일 수 없어야 한다.

방어 보조:

1. `위험 훈련장으로 이동한다`
2. `중장 훈련 골렘을 공격한다`
3. 공격 시작 확인창을 승인한다.
4. 전투 중 `집중 부적으로 방어한다`

기대값: 집중 부적은 실패 후 하트 손실 방지 효과를 테스트한다. 사용 뒤 소모된다.

도주 보조:

1. `위험 훈련장으로 이동한다`
2. `중장 훈련 골렘을 공격한다`
3. 공격 시작 확인창을 승인한다.
4. `연막탄으로 도주한다`

기대값: 연막탄은 도주 DC를 크게 낮추고 사용 뒤 소모된다. 도주 성공 시 combat 상태가 해제되고 실제 HP 손실은 없다.

### 강한 전투와 도주

1. `위험 훈련장으로 이동한다`
2. `중장 훈련 골렘을 공격한다`
3. 공격 시작 확인창을 승인한다.
4. 전투 패널의 `도주` 버튼을 누른다.

기대값: 골렘 전투는 즉시 끝나지 않고 진행 중 상태가 된다. 맨몸 도주는 판정형이므로 성공하면 combat 상태가 해제되고, 실패하면 combat 상태가 유지되며 player heart가 줄어든다. 전체 자동 QA에서는 둘 중 하나를 정상 결과로 인정하고, 도주 성공 자체를 고정 검증해야 할 때는 `연막탄으로 도주한다` 보조 흐름을 사용한다.

### 휴식

안전 휴식:

1. `보급 구역으로 이동한다`
2. `잠을 잔다`

기대값: 골드를 지불하고 HP/MP가 회복되며 다음 아침 턴으로 이동한다.

위험 휴식:

1. `위험 훈련장으로 이동한다`
2. `잠을 잔다`

기대값: 회복 대신 `중장 훈련 골렘` 전투 encounter가 시작된다.

### 거래

구매:

1. `보급 구역으로 이동한다`
2. `보급 담당자에게 상점 회복 약초를 산다`

판매:

1. 새 게임을 다시 시작한다.
2. `보급 구역으로 이동한다`
3. `보급 담당자에게 회복 약초를 판다`

기대값: 구매는 player gold가 3 줄고 `상점 회복 약초`가 인벤토리로 들어온다. 판매는 player gold가 1 늘고 `회복 약초`가 보급 담당자에게 넘어간다.

### 아이템 사용

가드 확인:

1. 새 게임 시작 직후 `회복 약초를 사용한다`
2. 새 게임 시작 직후 `마나 시약을 사용한다`

기대값: HP/MP가 가득 차 있어서 사용이 거부된다.
거부 뒤에는 실패 이유를 설명하는 GM 나레이션 로그가 남아야 한다.

HP 회복 성공:

1. `위험 훈련장으로 이동한다`
2. `중장 훈련 골렘을 공격한다`
3. 공격 시작 확인창을 승인한다.
4. 전투 패널의 `도주` 버튼을 누른다.
5. `회복 약초를 사용한다`

MP 회복 성공:

1. 새 게임을 다시 시작한다.
2. `훈련 일격으로 훈련용 허수아비를 공격한다`
3. 공격 시작 확인창을 승인한다.
4. `마나 시약을 사용한다`

기대값: HP 회복은 골렘에게 맞은 뒤 성공한다. MP 회복은 `훈련 일격`으로 MP를 소모한 뒤 성공한다.

### 판정과 레벨업

1. `주변을 자세히 살핀다`
2. 판정 패널에서 주사위를 굴린다.
3. 새 게임 시작 직후 레벨업 UI를 연다.
4. 성장 선택지에 최대 HP +1, 최대 MP +1, 새 스킬 습득 후보가 함께 뜨는지 본다.
5. 새 스킬 습득 후보를 선택한다.

기대값: 살피기는 pending roll을 만들고, 주사위 처리 뒤 로그가 남는다. 레벨업은 시작 경험치 `1`로 바로 가능하다. 성장 선택지는 LLM 후보가 실패해도 fallback 스킬 후보를 보여준다. 새 스킬을 고르면 레벨은 2가 되고, 배운 기술 목록에 새 스킬이 추가되며, 스킬 tier는 1로 저장된다.

## 재미 플레이테스트

기능 체크리스트와 별도로, 한 캐릭터로 10-15개 플레이어 행동을 이어서 플레이한다. 이 단계는 기본 테스트 완료 조건에 포함된다. 목표는 기능 성공 여부보다 플레이어가 계속 행동하고 싶어지는지 확인하는 것이다.

진행 방식:

- 사람이 화면을 보며 클릭하지 않는다.
- 백그라운드 서버에서 CLI/API/Playwright 자동화로 입력을 보낸다.
- 각 플레이어 행동의 입력 또는 정확한 action payload, 핵심 GM 로그, HP/MP/골드/장비/퀘스트/combat 변화 중 의미 있는 것을 transcript로 남긴다.
- 인트로, 공격 확인 승인, 판정 굴림, pending 상태 정리처럼 플레이어 행동을 보조하는 행은 transcript에 남겨도 된다. 이 보조 행 때문에 전체 transcript row 수가 15를 넘었다는 이유만으로 실패 처리하지 않는다.
- LLM 분류가 흔들려 진행이 막히면 "정확한 Action Payload"를 사용하되, 리포트에 어느 턴에서 API payload로 전환했는지 적는다.
- 10개 플레이어 행동 이전에 캐릭터가 진행 불능 상태가 되면 그 자체를 재미/진행성 이슈로 기록하고, 새 게임을 시작해 남은 행동 수를 채운다.

플레이 중에는 아래를 메모한다.

- 다음 행동이 자연스럽게 떠올랐는가.
- 성공, 실패, 거절이 단순 판정문이 아니라 장면 반응처럼 읽혔는가.
- 실패 뒤에도 다시 시도하거나 우회하고 싶은 마음이 들었는가.
- NPC, 장소, 아이템이 서로 다른 성격으로 느껴졌는가.
- HP, MP, 골드, 장비, 퀘스트 같은 상태 변화가 플레이 판단에 영향을 줬는가.
- 같은 행동을 반복했을 때 나레이션이 기계적으로 반복되지 않았는가.

권장 플레이 흐름:

1. 새 게임을 시작하고 인트로를 읽은 뒤, 가장 먼저 하고 싶은 행동을 입력한다.
2. NPC 한 명과 대화하고, 그 반응을 바탕으로 다음 행동을 정한다.
3. 전투, 거래, 휴식, 아이템 사용 중 최소 2가지를 직접 시도한다.
4. 일부러 한 번은 불리하거나 거절될 만한 행동을 한다.
5. 10턴 이후에도 다음에 해보고 싶은 행동이 남아 있는지 확인한다.

마지막에 1-5점으로 기록한다. 1점은 플레이를 멈추고 싶은 상태, 3점은 기능은 되지만 감흥이 약한 상태, 5점은 다음 행동이 바로 떠오르는 상태다.

| 항목 | 점수 | 메모 |
| --- | --- | --- |
| 다음 행동 욕구 |  |  |
| 세계 반응성 |  |  |
| 실패의 맛 |  |  |
| 나레이션 다양성 |  |  |
| 상태 변화 체감 |  |  |
| 다시 하고 싶은 정도 |  |  |

낮은 점수는 실패가 아니라 개선 단서다. 예를 들어 "거래 거절은 맞지만 NPC 성격이 드러나지 않는다", "전투 승리는 됐지만 왜 이겼는지 장면으로 느껴지지 않는다"처럼 다음 수정으로 이어질 수 있게 쓴다.

## 정확한 Action Payload

LLM 분류가 흔들릴 때는 아래 payload를 `/session/{game_id}/graph/turn/stream`에 보낸다. 공격은 먼저 `confirmation_required`가 오므로, 반환된 `confirmation_id`를 `/session/{game_id}/graph/confirm/stream`에 보내 승인해야 실제 전투가 진행된다.

```json
{"action":{"verb":"transfer","what":"shop_healing_herb","from":"quartermaster_npc","to":"player_01","how":"trade"}}
```

```json
{"action":{"verb":"transfer","what":"healing_herb","from":"player_01","to":"quartermaster_npc","how":"trade"}}
```

```json
{"action":{"verb":"attack","what":"training_dummy","with":"training_strike"}}
```

```json
{"action":{"verb":"rest"}}
```
