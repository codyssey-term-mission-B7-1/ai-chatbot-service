"""열거형 상수 — 흩어지기 쉬운 문자열 리터럴의 단일 위치(#175).

StrEnum(str 상속)이라 기존 문자열 비교·DB 저장·JSON 직렬화와 그대로 호환된다.
불변 수치·헤더 정책은 policies.py, 로그 이벤트 이름은 audit.E를 사용한다.
"""

import enum


class SessionKey(enum.StrEnum):
    """서명 세션 쿠키에 저장하는 키 — auth가 기록하고 deps·미들웨어가 읽는다."""

    USER_ID = "user_id"
    EMAIL_FP = "email_fp"
    IAT = "iat"


class ChatStatus(enum.StrEnum):
    """대화 기록 상태 — DB 컬럼 기본값·API 응답·성공 문맥 필터가 공유하는 값."""

    SUCCESS = "success"
    AI_ERROR = "ai_error"


class DeliveryResult(enum.StrEnum):
    """비밀번호 재설정 메일 발송 결과 — 발송 서비스가 반환하고 라우터가 분기한다."""

    SENT = "sent"
    DEV_CONSOLE = "dev_console"


class SchemaSyncStatus(enum.StrEnum):
    """기동 시 스키마 동기화 상태 — database가 기록하고 health가 읽는다."""

    PENDING = "pending"
    OK = "ok"
    ERROR = "error"
