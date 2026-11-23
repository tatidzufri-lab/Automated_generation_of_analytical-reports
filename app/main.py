from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.i18n import LANGS, lang_from_accept_language, reset_lang, set_lang
from app.core.logging import configure_logging
from app.routes.actions import router as actions_router
from app.routes.chat import router as chat_router
from app.routes.pages import router as pages_router
from app.routes.upload import router as upload_router
from app.services.file_service import FileService


settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    FileService(settings).ensure_storage()
    (settings.storage_dir / "chats").mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)


@app.middleware("http")
async def language_middleware(request: Request, call_next):
    """?lang=en|ru → cookie `lang` → Accept-Language → ru. Выбор из адреса запоминается в cookie."""
    from_query = request.query_params.get("lang")
    if from_query in LANGS:
        lang = from_query
    elif request.cookies.get("lang") in LANGS:
        lang = request.cookies["lang"]
    else:
        lang = lang_from_accept_language(request.headers.get("accept-language"))
    token = set_lang(lang)
    try:
        response = await call_next(request)
    finally:
        reset_lang(token)
    if from_query in LANGS:
        response.set_cookie("lang", from_query, max_age=60 * 60 * 24 * 365, samesite="lax")
    return response


app.include_router(pages_router)
app.include_router(chat_router)
app.include_router(upload_router)
app.include_router(actions_router)
app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")
app.mount("/storage", StaticFiles(directory=str(settings.storage_dir)), name="storage")
