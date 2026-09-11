# 골든 세트 1차 실측 결과 (2026-09-11 · 운영 real 모드)

> 실행기: [scripts/run_golden_set.py](../../scripts/run_golden_set.py) · 세트: [scripts/golden_set.json](../../scripts/golden_set.json)
> 환경: 운영 URL real 모드(실제 AI 응답), 전용 계정 goldenset-demo@example.com
> 범위: 12케이스 중 11개 실행 — G-09(실패 유도 후 문맥)은 운영에서 장애를 유도할 수 없어 제외(로컬 카오스로만 검증 가능)

## 1. 실행 개요

| 항목 | 값 |
|---|---|
| 요청 | 15턴 전부 **HTTP 200 / status=success** |
| latency | min 1,380ms · max 12,828ms(G-12) · 평균 2,942ms — 45초 예산 내 |
| 자동 구조 검증 | **10/11 PASS** (G-12는 REVIEW — 아래 §3) |

## 2. 케이스별 결과 (자동 검증 기준)

| 케이스 | 검증 | 결과 | 근거 발췌 |
|---|---|---|---|
| G-01 문맥 인용 | 직전 질문을 표현대로 인용 | PASS | "방금 당신이 물은 것은 **“나를 기억해?”** 였어요." |
| G-02 재료 회상 | 1차 답변 성분의 재등장 | PASS | 1차 답변 재료 후보 8개 중 다수가 2차 답변에 재등장 |
| G-03 경계 유지 | 무관한 질문(세금) 사이 후 주제 회상 | PASS | "아까 음식은 **파스타**였어요." |
| G-04 사실 단답 | 401/403 구분 | PASS | "401은 인증 실패, 403은 권한 없음" 요지 |
| G-05 긴 한국어 | 5개 항목 누락 없음 | PASS | 여권·환전·항공권·숙소·여행자보험 전부 포함 |
| G-06 혼합 언어 | 한글 서술 + 영문 용어 | PASS | 한글 포함 + Pydantic/BaseModel 언급 |
| G-07 grounding | 기록에 없는 것 지어내지 않음 | PASS | "기록된 대화 안에는 … 없어요. … 확인할 수 없…" (SYSTEM_PROMPT 계약 이행) |
| G-08 형식 | 번호 목록 | PASS | 1. 2. 3. 목록 |
| G-10 코드 | 실행 가능한 코드 | PASS | `def is_anagram(...): return sorted(...)` |
| G-11 산수 | 391 정답 | PASS | "17 × 23 = 391입니다." |
| G-12 길이 방어 | 예산 내 마무리 | **REVIEW** | §3 참조 |

## 3. 발견 — G-12 REVIEW: `max_tokens=800`을 보냈는데 5,362자 응답

PR #107(병합·배포 완료)부터 모든 AI 요청 본문에 `max_tokens=800, temperature=0.6`을 고정해 보낸다. 그런데 G-12("HTTP의 역사를 아주 자세히")에서 **5,362자** 응답을 받았다. 한국어 기준 800토큰이면 통상 1,200~1,600자 수준이므로, 가능성은 두 가지다.

1. **AI 공급사가 `max_tokens`를 무시**했거나 다르게 해석했다.
2. 응답이 실제로는 **잘렸는데**(finish_reason=length) 우리가 그것을 기록·전달하지 않는다 — 현재 응답 계약에는 `finish_reason`이 없어 **잘림을 사용자·운영자가 알 수 없다**.

**판정 유보 사유**: 어느 쪽인지는 공급사 응답 원문의 `finish_reason`을 봐야 확정된다. → **후속 조치**: `chat_logs`/로그에 `finish_reason` 기록 추가 + 잘림 시 사용자 고지 계약(기존 백로그 C-3 꼬리 항목과 결합). 확정 전까지 "길이 상한이 서버에서 보장된다"고 주장하지 않는다.

## 4. 정성 채점 미완료 항목

`golden_set.json`의 루브릭(문맥 정확성·사실성·간결성·톤 각 0-2점)에 따른 사람/LLM-judge 채점은 이번 1차 실행에서 수행하지 않았다 — 원문 전체는 실행기 산출물에 저장돼 있다. 다음 반복부터 변경 시점마다 채점 기록을 본 문서에 적산한다.

## 5. 재현 방법

```bash
python scripts/run_golden_set.py \
  --base-url https://ai-chatbot-service-production-4aa1.up.railway.app \
  --email goldenset-demo@example.com --password '<계정 비밀번호>' \
  --out /tmp/golden_results.json --skip G-09 --sleep 7
```
(프롬프트·모델·CONTEXT_TURNS·max_tokens 변경 시 전체 재실행 후 본 문서에 결과 추가)
