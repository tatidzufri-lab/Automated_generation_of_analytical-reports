from __future__ import annotations

from datetime import datetime
from pathlib import Path


CHART_LABELS = {
    "time_series": "Динамика продаж",
    "top_items": "Топ позиций",
    "daily_count": "Количество по дням",
    "monthly_sales": "Продажи по месяцам",
    "cumulative": "Накопительный итог",
    "distribution": "Распределение сумм",
    "line": "Line chart",
    "bar": "Bar chart",
    "histogram": "Histogram",
}

ARTIFACT_KIND_LABELS = {
    "report": "DOCX-отчёт",
    "presentation": "PowerPoint презентация",
    "summary": "Markdown-сводка",
}

EXTENSION_LABELS = {
    ".pdf": "PDF-отчёт",
    ".docx": "DOCX-отчёт",
    ".pptx": "PowerPoint презентация",
    ".md": "Markdown-сводка",
    ".png": "График",
}


def humanize_artifact_name(file_name: str) -> str:
    """Turn `{file_id}__{type}__{timestamp}.{ext}` into a user-friendly label.

    Internal file names keep the file_id prefix for uniqueness, but the end user
    sees something like "Топ позиций · 22.04.2026 17:30".
    """
    stem = Path(file_name).stem
    suffix = Path(file_name).suffix.lower()
    parts = stem.split("__")

    artifact_type: str | None = None
    timestamp: str | None = None

    if len(parts) >= 3:
        artifact_type = parts[-2]
        timestamp = parts[-1]
    elif len(parts) == 2:
        artifact_type, timestamp = parts[0], parts[1]

    if suffix == ".png" and artifact_type in CHART_LABELS:
        label = CHART_LABELS[artifact_type]
    elif suffix in EXTENSION_LABELS:
        label = EXTENSION_LABELS[suffix]
    elif artifact_type in ARTIFACT_KIND_LABELS:
        label = ARTIFACT_KIND_LABELS[artifact_type]
    else:
        label = CHART_LABELS.get(artifact_type or "", artifact_type or stem)

    formatted_time = _format_timestamp(timestamp)
    if formatted_time:
        return f"{label} · {formatted_time}"
    return label


def _format_timestamp(raw: str | None) -> str:
    if not raw:
        return ""
    try:
        parsed = datetime.strptime(raw, "%Y%m%d%H%M%S")
    except ValueError:
        return ""
    return parsed.strftime("%d.%m.%Y %H:%M")
