# 웹 클라이언트

스크롤 없이 한 화면에서 이야기를 읽고 선택하는 모바일 웹 앱입니다. 그림을 사용하지 않으며 PC에서도 같은 폭을 유지합니다. 설치와 플레이는 [루트 README](../README.md)를 따릅니다.

## 화면과 코드

`app/index.tsx` → `screens/GameScreen.tsx` → `logic/useGame.ts` → `services/api.ts`

- `screens/Arrival.tsx`: 소개→이름→성향 선택.
- `screens/Adventure.tsx`: 읽기→행동 선택, 이동과 수첩 열기.
- `components/game/`: 자원 상태, 전투 하트, 페이지로 보는 수첩.
- `components/ui/Reader.tsx`: 실제 글자 높이를 측정해 본문을 페이지로 나눕니다. 읽기 위치는 화면 크기가 바뀌거나 수첩을 열어도 유지합니다.
- `components/ui/PagedList.tsx`: 화면 높이에 맞는 개수로 행동과 기록을 넘깁니다. 항목을 열면 전체 내용을 확인합니다.
- `components/ui/MenuGrid.tsx`: 수첩과 행동 분류를 두 열로 배치합니다.
- `components/ui/ActionPreview.tsx`: 행동의 내용·비용·조건을 읽고 실행합니다.
- `logic/useGame.ts`: 시작·복원·선택·실패 복구. 서버 응답만 게임 상태로 채택합니다.
- `services/api.ts`: 인증된 `expo/fetch` 요청과 15초 제한. `types.ts`는 응답 형식입니다.
- `services/storage.ts`: 이어하기 ID만 저장합니다.
- `locale/ko.ts`: 클라이언트 문구. `design/tokens.js`: 색상·간격·글꼴·너비.

페이지 넘김은 화면 상태만 바꿉니다. 실제 행동을 확정할 때만 서버로 요청합니다. 화면 높이는 모바일 주소창과 가상 키보드의 가시 영역을 따릅니다. 본문 측정에는 웹 DOM을 사용하며 네이티브 앱은 현재 검증 대상이 아닙니다.

응답이 끊기면 다른 선택을 잠그고 동일 명령으로 재시도합니다. 409·422 응답 후에는 저장된 장면을 다시 불러옵니다. 서버 저장에 성공한 턴은 브라우저 저장소 오류가 나도 화면에 유지합니다.

## 명령

`client/`에서 실행합니다.

```powershell
npm run dev:public       # 웹+API+공용 HTTPS 주소, LTE 접속
npm run dev              # 웹+API, 같은 네트워크의 휴대폰 접속
npm run web              # 로컬 API로 접속, localhost:8081
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
