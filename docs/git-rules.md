# Git / 형상관리 규칙 — 적용 증빙 (#2)

> 과제 요구사항(7. 협업 및 형상관리) 대응 문서 · 최종 확인: 2026-09-07
> 규칙 원문은 `CONTRIBUTING.md`. 이 문서는 **실제 저장소에 적용된 설정의 증빙**이다.
> 설정 작업은 커밋 이력이 남지 않으므로 API 조회 결과를 그대로 기록한다.

## 1. 과제 요구사항 ↔ 적용 상태

| 요구사항 (PDF 7절) | 적용 방식 | 상태 |
|---|---|---|
| 브랜치 전략 (main/develop 분리) | `main` ← `develop` ← `feature/*` 운영 | ✅ |
| 기능 단위 작업 브랜치 흔적 | `feature/#N-설명` 네이밍 규칙 | ✅ |
| PR 기반 Merge 기록 존재 | 룰셋으로 직접 push 차단, PR 필수 | ✅ |
| 팀원별 유의미한 커밋 10회+ | 주간 감사 → `docs/commit-audit.md` | ⚠️ 진행 중 |
| 문서와 Git 이력 불일치 없음 | 개인별 작업 요약을 커밋 이력 기준으로 작성 | 진행 중 |

## 2. 적용된 룰셋 — `team-collaboration-rules`

대상 브랜치: `refs/heads/main`, `refs/heads/develop` · 상태: **active**

```bash
# 재확인 명령
gh api repos/codyssey-term-mission-B7-1/ai-chatbot-service/rulesets
```

| 규칙 | 설정값 | 무엇을 막는가 |
|---|---|---|
| `pull_request` → `required_approving_review_count` | `1` | 리뷰 없는 머지 |
| `pull_request` → **`allowed_merge_methods`** | **`["merge"]`** | **Squash / Rebase 머지** |
| `pull_request` → `require_last_push_approval` | `true` | 마지막 push 당사자의 셀프 승인 (이슈 #16) |
| `pull_request` → `dismiss_stale_reviews_on_push` | `true` | 승인 후 몰래 커밋 추가 |
| `pull_request` → `required_review_thread_resolution` | `true` | 리뷰 코멘트 미해결 머지 |
| `non_fast_forward` | 활성 | `main`/`develop` 강제 push |
| `deletion` | 활성 | 보호 브랜치 삭제 |
| `bypass_actors` | `null` | **관리자 포함 전원 우회 불가** |

## 3. Squash 금지가 채점에 직결되는 이유

PDF 요구사항은 **"팀원별 유의미한 커밋 10회 이상"**이다.
Squash and merge는 PR 안의 커밋 N개를 **1개로 합쳐** develop에 올린다.
하루를 2~3개 논리 단위로 나눠 커밋해도 머지 시점에 1개로 소멸하므로,
**개인별 커밋 수 증빙 자체가 사라진다.**

→ 룰셋의 `allowed_merge_methods: ["merge"]`로 main/develop에서 Squash를 차단했다.

### 남은 조치 (관리자 권한 필요)

저장소 설정의 `allow_squash_merge`가 아직 `true`다.

```bash
$ gh api repos/codyssey-term-mission-B7-1/ai-chatbot-service \
    --jq '{squash:.allow_squash_merge, merge:.allow_merge_commit, rebase:.allow_rebase_merge}'
{"squash":true,"merge":true,"rebase":true}
```

룰셋이 main/develop에서 이미 차단하므로 **실질적 위험은 없으나**, PR 화면에 Squash 버튼이
남아 있어 다른 브랜치 대상 머지나 향후 룰셋 변경 시 실수 여지가 있다.
저장소 설정에서도 끄는 것이 이중 안전장치다.

- 필요 권한: `admin` (현재 담당자 이종석은 `maintain`)
- **@giyeop-cody 에게 요청** — Settings → General → Pull Requests → `Allow squash merging` 해제

## 3-1. 작업 브랜치 보존 정책 (증빙 보조)

머지된 `feature/*` 브랜치를 **삭제하지 않고 남긴다.** 저장소 설정도 이미 자동 삭제가 꺼져 있다.

```bash
$ gh api repos/codyssey-term-mission-B7-1/ai-chatbot-service --jq '.delete_branch_on_merge'
false
```

기능 단위 작업 브랜치의 흔적(PDF 7절 요구사항)이 그대로 남고,
머지 방식에 문제가 생기더라도 각 브랜치에 원본 커밋이 보존된다.

> **단, 이것이 커밋 수 증빙을 대체하지는 않는다.**
> `git shortlog origin/develop`과 GitHub Contributors 통계는 기본 브랜치 기준으로 집계하므로,
> 커밋이 합쳐지면 브랜치가 남아 있어도 수치에는 잡히지 않는다.
> 커밋 수 요구사항은 **Squash 금지(위 3절) + 주간 감사(`docs/commit-audit.md`)** 로 관리한다.

## 4. 민감정보 차단 검증

```bash
$ git check-ignore -v .env demo.db
.gitignore:2:.env    .env
.gitignore:16:*.db   demo.db

$ git log --all --diff-filter=A --name-only --pretty=format: | grep -E '(^|/)\.env$|\.db$' | sort -u
(출력 없음 — 저장소 이력에 .env / *.db 가 추가된 적 없음)
```

- `.gitignore`에 `.env`, `*.db`, `.venv/` 포함
- `.env.example`은 **키 이름과 설명만** 포함, 값 없음 (PDF 제약사항 대응)

## 5. 브랜치·커밋·PR 규칙 요약

```
main ← develop ← feature/* | fix/* | docs/* | chore/* | hotfix/*
```

- 브랜치: `종류/#이슈번호-짧은설명` (kebab-case) — 사람 이름 금지
- 커밋: `type(scope): 제목 (#이슈번호)` — 50자 이내, 1 커밋 = 1 논리 단위
- PR: 1 PR = 1 이슈, 변경 400줄 이내, 리뷰어 1명 승인 후 머지
- 머지 방식: **Merge commit만** (Squash 금지)

상세는 `CONTRIBUTING.md` 참고.
