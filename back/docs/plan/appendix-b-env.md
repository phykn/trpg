# 부록 B: 환경 변수

> 상위: [plan.md](../plan.md)

`run_api.py` 기동 시 fail-fast (누락 시 throw, `??` fallback 금지).

| 변수 | 용도 | 예시 |
|---|---|---|
| `HOST` | FastAPI 바인드 | `0.0.0.0` |
| `PORT` | 서비스 포트 | `8000` |
| `BASE_URL` | llama.cpp OpenAI-compat URL | `http://127.0.0.1:8080/v1` |
| `DATA_DIR` | 게임 저장 루트 | `./data` |
| `PROFILE_DIR` | 프로필 루트 | `./config/profiles` |
| `DEFAULT_PROFILE` | `/session/init` 기본 profile 이름 | `default` |

프론트 측 `EXPO_PUBLIC_API_URL` 은 `http://{HOST}:{PORT}` 를 가리키며, 폰 테스트 시 LAN 내부 IP 를 사용 (터널·외부 노출은 인증 붙을 때까지 보류).
