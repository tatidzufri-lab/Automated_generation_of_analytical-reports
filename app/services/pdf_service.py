from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import Settings, get_settings
from app.services.artifact_naming import humanize_artifact_name
from app.services.file_service import FileService, StoredFile
from app.services.time_utils import filename_timestamp, format_local


logger = logging.getLogger(__name__)


class PdfServiceError(RuntimeError):
    """Raised when PDF generation fails."""


class PdfService:
    """WeasyPrint-based PDF generator with a branded HTML template."""

    def __init__(self, file_service: FileService, settings: Settings | None = None) -> None:
        self.file_service = file_service
        self.settings = settings or get_settings()
        self.template_dir = self.settings.templates_dir / "reports"
        self._env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def generate_report(
        self,
        stored_file: StoredFile,
        analysis: dict[str, Any],
        business_metrics: dict[str, Any] | None,
        charts: list[dict[str, Any]],
        title: str | None = None,
    ) -> dict[str, str]:
        self.file_service.ensure_storage()
        report_name = self._build_report_name(stored_file.file_id)
        output_path = self.settings.output_dir / report_name

        chart_entries = [
            {
                "title": chart.get("display_name")
                or chart.get("title")
                or humanize_artifact_name(chart.get("file_name", "Chart")),
                "description": chart.get("description", ""),
                "absolute_path": (self.settings.output_dir / chart["file_name"]).resolve().as_uri(),
            }
            for chart in charts
            if (self.settings.output_dir / chart.get("file_name", "")).exists()
        ]

        has_business_metrics = bool(
            business_metrics
            and (business_metrics.get("total_sales") or business_metrics.get("total_orders") or business_metrics.get("top_items"))
        )

        context = {
            "title": title or f"Аналитический отчёт · {stored_file.original_name}",
            "generated_at": format_local("%d.%m.%Y %H:%M"),
            "source_file": stored_file.original_name,
            "summary": analysis.get("summary"),
            "insights": analysis.get("insights", []),
            "stats": analysis.get("stats", []),
            "sample_rows": (business_metrics or {}).get("sample_rows", []),
            "has_business_metrics": has_business_metrics,
            "total_sales": (business_metrics or {}).get("total_sales", 0.0),
            "avg_ticket": (business_metrics or {}).get("avg_ticket", 0.0),
            "total_orders": (business_metrics or {}).get("total_orders", 0),
            "top_items": (business_metrics or {}).get("top_items", []),
            "charts": chart_entries,
        }

        try:
            from weasyprint import CSS, HTML  # lazy import to avoid import cost at module load
        except ImportError as exc:  # pragma: no cover - depends on system libraries
            raise PdfServiceError(
                "WeasyPrint не установлен. Установите системные библиотеки (pango, cairo) и выполните pip install weasyprint."
            ) from exc

        template = self._env.get_template("pdf_report.html")
        html_content = template.render(**context)

        css_files = [
            self.template_dir / "pdf_styles.css",
            self.template_dir / "pdf_weasyprint.css",
        ]
        try:
            stylesheets = [CSS(filename=str(path)) for path in css_files if path.exists()]
            HTML(string=html_content, base_url=str(self.template_dir)).write_pdf(
                target=str(output_path),
                stylesheets=stylesheets,
            )
        except Exception as exc:  # pragma: no cover - external tool
            logger.exception("Failed to generate PDF for %s", stored_file.file_id)
            raise PdfServiceError(f"Не удалось сгенерировать PDF: {exc}") from exc

        logger.info("Generated PDF %s for %s", report_name, stored_file.file_id)
        return {
            "title": "PDF report",
            "kind": "pdf",
            "file_name": report_name,
            "display_name": humanize_artifact_name(report_name),
            "description": "Аналитический отчёт в PDF с графиками и таблицами.",
            "storage_url": f"/storage/outputs/{report_name}",
            "download_url": f"/download/{report_name}",
        }

    def _build_report_name(self, file_id: str) -> str:
        return f"{file_id}__report__{filename_timestamp()}.pdf"
