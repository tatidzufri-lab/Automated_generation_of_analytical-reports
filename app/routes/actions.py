from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates

from app.core.config import get_settings
from app.routes.pages import (
    analysis_service,
    chart_service,
    chat_service,
    file_service,
    pdf_service,
    pptx_service,
    report_service,
)
from app.services.file_service import FileReadError
from app.services.pdf_service import PdfServiceError
from app.services.pptx_service import PptxServiceError


settings = get_settings()
templates = Jinja2Templates(directory=str(settings.templates_dir))

router = APIRouter()


def _panel_context(
    request: Request,
    file_id: str,
    success_message: str | None = None,
    error_message: str | None = None,
):
    stored_file = file_service.get_file(file_id)
    preview_context = file_service.build_preview_context(stored_file)
    analysis = analysis_service.analyze(stored_file)
    artifacts = file_service.get_output_artifacts(file_id)
    business = chat_service._safe_business_metrics(stored_file)
    return {
        "request": request,
        "preview": preview_context,
        "analysis": analysis,
        "artifacts": artifacts,
        "business": business,
        "success_message": success_message,
        "error_message": error_message,
    }


@router.post("/actions/analyze/{file_id}")
async def analyze_action(request: Request, file_id: str):
    stored_file = file_service.get_file(file_id)
    artifacts = file_service.get_output_artifacts(file_id)
    charts_generated = 0
    if not artifacts["charts"]:
        business_charts = chart_service.generate_business_charts(stored_file)
        if business_charts:
            charts_generated = len(business_charts)
        else:
            fallback = chart_service.generate_default_charts(stored_file)
            charts_generated = len(fallback) if fallback else 0

    message = (
        f"Анализ выполнен. Построено {charts_generated} графиков."
        if charts_generated
        else "Анализ выполнен."
    )
    context = _panel_context(request, file_id, success_message=message)
    return templates.TemplateResponse("partials/preview_content.html", context)


@router.post("/actions/chart/{file_id}")
async def chart_action(
    request: Request,
    file_id: str,
    chart_type: str = Form(...),
    x_column: str | None = Form(default=None),
    y_column: str | None = Form(default=None),
):
    try:
        stored_file = file_service.get_file(file_id)
        chart_service.generate_chart(stored_file, chart_type, x_column=x_column or None, y_column=y_column or None)
        context = _panel_context(request, file_id, success_message=f"График «{chart_type}» построен и сохранён.")
    except FileReadError as exc:
        context = _panel_context(request, file_id, error_message=str(exc))
    return templates.TemplateResponse("partials/result_panel.html", context)


@router.post("/actions/charts_business/{file_id}")
async def business_charts_action(request: Request, file_id: str):
    stored_file = file_service.get_file(file_id)
    charts = chart_service.generate_business_charts(stored_file)
    message = (
        f"Собран пакет бизнес-графиков ({len(charts)} шт.)."
        if charts
        else "Не нашёл подходящих бизнес-колонок (дата/сумма). Проверьте файл."
    )
    context = _panel_context(request, file_id, success_message=message if charts else None, error_message=None if charts else message)
    return templates.TemplateResponse("partials/result_panel.html", context)


@router.post("/actions/report/{file_id}")
async def report_action(request: Request, file_id: str):
    stored_file = file_service.get_file(file_id)
    preview_context = file_service.build_preview_context(stored_file)
    analysis = analysis_service.analyze(stored_file)
    business = chat_service._safe_business_metrics(stored_file)
    chart_records = chat_service._ensure_business_charts(stored_file, business)
    report_service.generate_report(
        stored_file, analysis, chart_records[:3], preview_context, business_metrics=business
    )
    context = _panel_context(request, file_id, success_message="DOCX-отчёт сформирован и готов к скачиванию.")
    return templates.TemplateResponse("partials/result_panel.html", context)


@router.post("/actions/pdf/{file_id}")
async def pdf_action(request: Request, file_id: str):
    stored_file = file_service.get_file(file_id)
    analysis = analysis_service.analyze(stored_file)
    business = chat_service._safe_business_metrics(stored_file)
    chart_records = chat_service._ensure_business_charts(stored_file, business)
    try:
        pdf_service.generate_report(stored_file, analysis, business, chart_records[:6])
        context = _panel_context(request, file_id, success_message="PDF-отчёт с графиками и таблицами готов.")
    except PdfServiceError as exc:
        context = _panel_context(request, file_id, error_message=str(exc))
    return templates.TemplateResponse("partials/result_panel.html", context)


@router.post("/actions/pptx/{file_id}")
async def pptx_action(request: Request, file_id: str):
    stored_file = file_service.get_file(file_id)
    analysis = analysis_service.analyze(stored_file)
    business = chat_service._safe_business_metrics(stored_file)
    chart_records = chat_service._ensure_business_charts(stored_file, business)
    try:
        pptx_service.generate_report(stored_file, analysis, business, chart_records[:6])
        context = _panel_context(request, file_id, success_message="PowerPoint презентация сформирована.")
    except PptxServiceError as exc:
        context = _panel_context(request, file_id, error_message=str(exc))
    return templates.TemplateResponse("partials/result_panel.html", context)


@router.post("/actions/business/{file_id}")
async def business_report_action(request: Request, file_id: str):
    stored_file = file_service.get_file(file_id)
    analysis = analysis_service.analyze(stored_file)
    business = chat_service._safe_business_metrics(stored_file)
    chart_records = chart_service.generate_business_charts(stored_file)
    if not chart_records:
        chart_records = chat_service._ensure_business_charts(stored_file, business)

    errors: list[str] = []
    try:
        pdf_service.generate_report(stored_file, analysis, business, chart_records[:6])
    except PdfServiceError as exc:
        errors.append(f"PDF: {exc}")
    try:
        pptx_service.generate_report(stored_file, analysis, business, chart_records[:6])
    except PptxServiceError as exc:
        errors.append(f"PPTX: {exc}")

    success_message = (
        f"Бизнес-пакет готов: {len(chart_records)} графиков, PDF и PPTX."
        if not errors
        else None
    )
    error_message = "; ".join(errors) if errors else None
    context = _panel_context(request, file_id, success_message=success_message, error_message=error_message)
    return templates.TemplateResponse("partials/preview_content.html", context)


@router.get("/download/{artifact_name}")
async def download_artifact(artifact_name: str):
    candidate = settings.output_dir / artifact_name
    if not candidate.exists() or candidate.parent != settings.output_dir:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Файл не найден.")
    return FileResponse(path=candidate, filename=candidate.name)
