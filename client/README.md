# 웹 클라이언트

스크롤 없이 한 화면에서 장면을 읽고 문장이나 버튼으로 행동하는 모바일 웹 앱입니다. 그림을 사용하지 않으며 PC에서도 같은 폭을 유지합니다. 설치와 플레이는 [루트 README](../README.md)를 따릅니다.

## 화면과 코드

`app/index.tsx` → `screens/GameScreen.tsx` → `logic/useGame.ts` → `services/api.ts`

- `screens/Start.tsx`: 이야기 고르기, 원고가 허용하면 방식(+2와 0)과 특성 2개 고르기.
- `screens/Play.tsx`: 장애물·태그, 서술, 그리고 아래 칸 하나(추천 버튼과 입력창, 위험 확인 카드, 되묻기, 성장 선택, 결말 중 하나).
- `components/game/`: 장소·위험 머리글, 진행도 칸, 서술 스트림, 확인 카드, 당신(시트)과 기록 대화상자.
- `components/ui/Reader.tsx`: 실제 글자 높이를 측정해 본문을 페이지로 나눕니다. 서술 뒤에 이번 턴에 바뀐 것을 붙여 보여 줍니다.
- `logic/useGame.ts`: 시작·복원·행동·서술 스트림·실패 복구. 서버 응답만 게임 상태로 채택합니다.
- `services/api.ts`: 인증된 `expo/fetch` 요청(15초 제한)과 NDJSON 서술 스트림. `types.ts`는 응답 형식입니다.
- `services/storage.ts`: 이어하기 ID(`trpg.game_id`)만 저장합니다.
- `locale/ko.ts`: 클라이언트 문구. 이야기 문구는 모두 서버 응답에서 옵니다.

행동이 저장되면 화면이 먼저 바뀌고, 그 턴의 서술을 스트림으로 받습니다. 서술이 끝나거나 실패할 때까지 다음 행동은 잠깁니다. 검사에 실패한 서술은 지워지고 다시 쓰입니다. 서술이 실패하면 상태는 이미 저장되어 있으므로 다시 쓰기만 요청합니다.

응답이 끊기면 다른 행동을 잠그고 같은 명령(같은 `request_id`)으로 재시도합니다. 409·422 응답 후에는 저장된 장면을 다시 불러옵니다.

## 명령

`client/`에서 실행합니다.

```bash
npm run dev:public       # 웹+API+공용 HTTPS 주소, LTE 접속
npm run dev              # 웹+API, 같은 네트워크의 휴대폰 접속
npm run web              # 로컬 API로 접속, localhost:8090
npm run web -- --clear   # 디자인·Metro 설정 변경 후 캐시 초기화
npm run build:web        # 로컬 API를 사용하는 웹 빌드 → dist/
npm test -- --runInBand
npx tsc --noEmit
npm run lint
node --test scripts/dev-proxy.test.cjs
```

`dev` 명령은 `/api` 요청을 로컬 API에 전달하므로 휴대폰에서도 웹과 API가 같은 주소를 사용합니다. 기존 로컬 API가 있으면 재사용합니다. `dev:public`의 주소는 실행마다 바뀌며 Windows에서는 검증된 공식 `cloudflared` 실행 파일을 `node_modules/.cache/`에 보관합니다. 세부 접속 방법은 [루트 README](../README.md#휴대폰에서-플레이)를 따릅니다.

## 다른 서버에 연결

로컬 웹 명령은 항상 고정된 로컬 설정을 사용합니다. 다른 서버에 연결할 때는 세 환경변수를 지정한 뒤 Expo를 직접 실행합니다. 서버의 `CORS_ORIGINS`에 브라우저 주소도 등록합니다.

```powershell
$env:EXPO_NO_DOTENV = '1'
$env:EXPO_PUBLIC_API_URL = 'http://127.0.0.1:8000'
$env:EXPO_PUBLIC_API_USER = 'local'
$env:EXPO_PUBLIC_API_PASS = 'local'
npx expo start --web --host localhost
```

이 값은 웹 번들에서 볼 수 있는 공용 접속 설정입니다. 같은 설정으로 `npx expo export --platform web`을 실행하면 해당 서버에 연결되는 정적 빌드를 만듭니다. `npm start`, `npm run android`, `npm run ios`는 `.env.shared`와 `.env.dev`를 읽는 Expo 개발 명령입니다. 이번 검증 대상은 웹이며 네이티브 앱은 별도로 확인해야 합니다.
