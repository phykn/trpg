# 웹 클라이언트

고정 높이의 한 화면에서 장면을 읽고 문장으로 행동하는 모바일 웹 앱입니다(Expo, React Native Web, NativeWind). 그림을 쓰지 않고, 대화 영역 밖은 스크롤하지 않으며, PC에서도 같은 폭(412px)을 유지합니다. 화면 설계는 [docs/ui.md](../docs/ui.md), 설치와 플레이는 [루트 README](../README.md)를 따릅니다.

## 화면과 코드

`app/index.tsx` → `screens/` → `logic/useGame.ts` → `services/api.ts`

- `screens/Title.tsx`: 이야기 선반, 이어하기, 새로 시작. `screens/Start.tsx`: 이름, 능력치, 특성. `screens/Play.tsx`: 플레이 화면의 배치.
- `components/ui/`: 모든 화면이 함께 쓰는 부품. `Icon`(선 아이콘), `Button`과 `IconButton`, `Sheet`(아래에서 올라오는 판과 `Choice`), `motion.ts`(들어옴 움직임), `useDialog`(Escape, 포커스 가두기와 돌려주기).
- `components/game/`: 아이콘 줄(`Row`, `Item`, `Pill`), 머리줄과 주인공 판, 위험 시계, 장면, 칸, 대화, 입력줄, 굴림 카드와 주사위, 되묻기·확인·성장 카드, 메뉴, 결말.
- `logic/useGame.ts`: 시작, 복원, 명령의 생애, 서술 스트림, 실패 복구. 서버 응답만 게임 상태로 채택하고 규칙을 되풀이하지 않습니다. `logic/reveal.ts`는 단계 기록을 드러남의 시간표로 바꾸는 순수 함수, `logic/useLog.ts`는 이 기기에 남기는 대화 내역입니다.
- `services/api.ts`: 인증된 요청과 NDJSON 서술 스트림의 유일한 경계. `types.ts`는 응답 형식, `storage.ts`는 이어하기 ID(`trpg.game_id`)와 대화 내역 저장입니다.
- `design/tokens.js`: 색, 간격, 글꼴, 움직임 시간. `locale/ko.ts`: 화면이 만드는 문장. 이야기 문장은 모두 서버 응답에서 옵니다.

명령이 저장되면 화면이 먼저 바뀌고, 그 턴의 서술을 스트림으로 받습니다. 서술이 끝나거나 실패할 때까지 다음 명령은 잠깁니다. 30초 안에 응답이 없으면 같은 명령(같은 `request_id`)으로만 다시 보낼 수 있습니다. 409 응답의 `view`는 그대로 받아들입니다.

## 명령

`client/`에서 실행합니다.

```bash
npm run web              # 로컬 API(--local)로 접속, localhost:8090
npm run web -- --clear   # 토큰·Tailwind·Babel·Metro 설정 변경 후 캐시 초기화
npm run build:web        # 로컬 API를 쓰는 웹 빌드 → dist/ (라우팅·설정 변경 후)
npm run dev              # 웹+API, 같은 네트워크의 휴대폰 접속
npm run dev:public       # 웹+API+공용 HTTPS 주소
npm test -- --runInBand  # 하나만: npx jest path/to/file.test.ts
npx tsc --noEmit
npm run lint
node --test scripts/dev-proxy.test.cjs
```

## 외부 공개 (workers.dev)

```bash
npm run deploy           # 웹 빌드를 Cloudflare Worker(trpg)에 배포. 화면 코드를 바꿨을 때만
npm run serve            # 맥에서 API+터널을 올리고 터널 주소를 Worker KV에 기록. 플레이할 때마다
```

Worker는 정적 화면을 내보내고 `/api/*`를 KV의 현재 터널 주소로 넘깁니다. 터널이 끊기면 `serve`가 새로 열고 KV를 다시 씁니다. `server/`의 `.py`나 `scenarios/`의 `.yaml`이 바뀌면 API만 다시 시작하므로 주소는 바로 이어집니다. KV 반영에 1분쯤 걸립니다. 처음 한 번 `npx wrangler login`이 필요하고, 두 모델이 켜져 있어야 합니다. `serve`를 끄면 화면은 열리지만 API는 502를 돌려줍니다.

`dev` 명령은 `/api` 요청을 로컬 API에 전달하므로 휴대폰에서도 웹과 API가 같은 주소를 씁니다. 기존 로컬 API가 있으면 재사용합니다. `dev:public`의 주소는 실행마다 바뀌고, Windows에서는 검증된 공식 `cloudflared` 실행 파일을 `node_modules/.cache/`에 보관합니다.

## 다른 서버에 연결

로컬 웹 명령은 늘 고정된 로컬 설정을 씁니다. 다른 서버에 연결할 때는 세 환경변수를 지정하고 Expo를 직접 실행합니다. 서버의 `CORS_ORIGINS`에 브라우저 주소도 등록합니다. 포트는 8090으로 둡니다(Expo의 기본 8081은 결정 모델이 씀).

```bash
EXPO_NO_DOTENV=1 EXPO_PUBLIC_API_URL=http://127.0.0.1:8000 EXPO_PUBLIC_API_USER=local EXPO_PUBLIC_API_PASS=local npx expo start --web --host localhost --port 8090
```

이 값은 웹 번들에서 보이는 공용 접속 설정입니다. 같은 설정으로 `npx expo export --platform web`을 실행하면 그 서버에 연결되는 정적 빌드를 만듭니다. `npm start`, `npm run android`, `npm run ios`는 `.env.shared`와 `.env.dev`를 읽는 Expo 개발 명령이며, 검증 대상은 웹입니다.
