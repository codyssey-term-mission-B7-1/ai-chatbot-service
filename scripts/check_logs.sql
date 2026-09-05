-- DB 확인 가이드 — 최근 대화 로그 조회
-- 사용법: sqlite3 app.db < scripts/check_logs.sql

.mode column
.headers on

PRINT '── 최근 대화 로그 20건 ──';
SELECT id,
       user_id,
       status,
       latency_ms || 'ms'          AS latency,
       substr(question, 1, 40)     AS question,
       substr(answer, 1, 40)       AS answer,
       created_at
FROM chat_logs
ORDER BY id DESC
LIMIT 20;

PRINT '── 사용자별 대화 통계 ──';
SELECT u.id,
       u.email,
       u.nickname,
       COUNT(c.id)                              AS total_chats,
       SUM(CASE WHEN c.status='ai_error' THEN 1 ELSE 0 END) AS errors
FROM users u
LEFT JOIN chat_logs c ON c.user_id = u.id
GROUP BY u.id
ORDER BY total_chats DESC;

PRINT '── 특정 사용자 추적 예시 (user_id=1) ──';
SELECT id, question, answer, created_at
FROM chat_logs
WHERE user_id = 1
ORDER BY id DESC
LIMIT 10;
