# trpg-frontend

한국어 TRPG 클라이언트. 한 화면짜리 Expo (React Native) 앱. 백엔드는 `../backend/`, Claude Code 가이드는 [CLAUDE.md](./CLAUDE.md).

## 스택

- Expo SDK 54 / React Native 0.81 / React 19 (New Architecture + React Compiler)
- expo-router (파일 기반 라우팅, `typedRoutes`)
- NativeWind v4 (RN 용 Tailwind), `design/tokens.js` 가 단일 토큰 소스
- TypeScript strict
- 백엔드 호출: `expo/fetch` 로 SSE 스트리밍 (`services/llm.ts`)

## 셋업

```bash
npm install
```

`frontend/.env` 작성:

```
EXPO_PUBLIC_API_URL=<backend URL>
EXPO_PUBLIC_API_USER=<basic auth user>
EXPO_PUBLIC_API_PASS=<basic auth pass>
```

`<backend URL>` 은 LAN 주소 (`http://<windows-lan-ip>:8001`) 또는 Tailscale Funnel 도메인 (`https://<machine>.<tailnet>.ts.net`). 아래 테스트 모드와 짝.

## 폰 테스트

폰에 **Expo Go** 설치 (Play Store / App Store).

### LAN (같은 Wi-Fi)

1. 백엔드가 `0.0.0.0:8001` 에 바인딩, Windows 방화벽이 8001 inbound 허용.
2. 폰이 노트북과 같은 Wi-Fi.
3. `frontend/` 에서:
   ```bash
   npx expo start
   ```
4. Android: Expo Go → "Scan QR code". iOS: 카메라 앱으로 QR 찍고 "Open in Expo Go" notification.

### 외부망 (Tailscale Funnel)

1. 백엔드는 `127.0.0.1:8001` 에 바인딩.
2. Funnel 이 8001 프록시 중인지 확인:
   ```bash
   tailscale funnel status
   ```
   꺼져 있으면:
   ```bash
   sudo tailscale funnel --bg 8001
   ```
3. `EXPO_PUBLIC_API_URL` 이 funnel 도메인과 일치.
4. `frontend/` 에서:
   ```bash
   npx expo start --host=tunnel -c
   ```
5. Expo Go 로 QR 스캔 (LAN 4 단계와 동일).

## 기타 명령

```bash
npx expo start -c   # Metro 캐시 비우기 (tokens / tailwind / babel / metro config 수정 후)
npm run lint
```

## 구조

```
frontend/
  app/                # expo-router 라우트 셸 (단일 화면 — index.tsx 가 Shell 마운트)
  components/         # 화면 구성 요소 (header / log / hero / composer / ui + Shell + NewGame)
  hooks/use-game.ts   # 게임 상태 훅 (서버 호출 + SSE 이벤트 적용)
  services/           # 백엔드 경계 (llm.ts: REST + SSE 클라이언트)
  transformers/       # domain → UI 사영 (panels.ts)
  types/              # domain (백엔드 모델), ui (렌더 계약), wire (SSE/REST 페이로드)
  design/tokens.js    # 단일 디자인 토큰 (Tailwind config + 코드 양쪽이 import)
```
