# AI Server

협업 여행 서비스용 무상태 FastAPI AI 서버다.

현재 구현 범위는 `API 기능 구현`까지다. 즉, Spring Boot BE 연결 전에도 아래 두 API를 단독으로 검증할 수 있다.

## 구현된 API

- `POST /v1/ai/context/summaries`
- `POST /v1/ai/chat/plan`

## 전체 구조

```text
app/
├─ main.py
├─ dependencies.py
├─ core/
│  └─ config.py
├─ schemas/
│  ├─ chat.py
│  └─ planner.py
├─ clients/
│  ├─ openai_travel.py
│  └─ google_places.py
└─ services/
   ├─ summary.py
   └─ orchestrator.py
```

## 현재 동작 방식

- 채팅 요약 API는 `previous_summary + messages_since_last_summary`를 받아 rolling structured summary를 만든다.
- 채팅 플랜 API는 `summary + delta + recent_messages + request_message`를 받아 intent를 분기한다.
- intent는 `place_recommendation`, `conversation_summary`, `travel_general_chat`, `unsupported` 4개로 고정했다.
- 장소 추천은 Google Places 어댑터를 통해 최대 3개 후보를 반환한다.
- OpenAI 호출은 summary 생성, intent 분기, 최종 답변 생성에 각각 간단한 structured-output 프롬프트로 나눠 넣었다.

## 실행

```bash
uvicorn app.main:app --reload
```

기본 주소는 `http://127.0.0.1:8000` 이고 Swagger는 `/docs` 에서 확인할 수 있다.

## 환경 변수

- `OPENAI_API_KEY`
- `GOOGLE_MAPS_API_KEY`
- `GOOGLE_PLACES_LANGUAGE_CODE` 기본값 `ko`
- `OPENAI_MODEL` 기본값 `gpt-5.4-mini`
- `AI_LOG_LEVEL` 기본값 `INFO`

현재는 `OPENAI_API_KEY`, `GOOGLE_MAPS_API_KEY` 둘 다 필수다.
