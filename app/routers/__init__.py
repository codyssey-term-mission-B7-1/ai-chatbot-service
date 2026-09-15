"""라우터 패키지 — 라우터 목록과 등록 순서를 한곳에서 관리한다(#172)."""

from fastapi import FastAPI

from app.routers import admin, auth, chat, health, logs, pages, threads


def register_routers(app: FastAPI) -> None:
    """main.py가 호출하는 유일한 진입점. pages·health는 API가 아니어도 앱 라우팅의 일부다."""
    app.include_router(auth.router)
    app.include_router(chat.router)
    app.include_router(threads.router)
    app.include_router(logs.router)
    app.include_router(admin.router)
    app.include_router(pages.router)
    app.include_router(health.router)
