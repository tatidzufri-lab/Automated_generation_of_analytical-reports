from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings, get_settings
from app.services.file_service import StoredFile

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - handled at runtime when dependency is absent
    OpenAI = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)


class AIServiceError(RuntimeError):
    """Base AI service error."""


class AIServiceConfigurationError(AIServiceError):
    """Raised when OpenAI is not configured."""


class AIServiceRequestError(AIServiceError):
    """Raised when the OpenAI API request fails."""


@dataclass
class AIPlan:
    assistant_message: str
    actions: list[dict[str, Any]]


class AIService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = None

    @property
    def enabled(self) -> bool:
        return bool(self.settings.openai_api_key) and OpenAI is not None

    @property
    def model_name(self) -> str:
        return self.settings.openai_model

    def plan_response(
        self,
        *,
        conversation_messages: list[dict[str, Any]],
        user_text: str,
        active_file: StoredFile | None,
        active_file_context: dict[str, Any] | None,
    ) -> AIPlan:
        if OpenAI is None:
            raise AIServiceConfigurationError(
                "Python-пакет `openai` не установлен. Выполните `pip install -r requirements.txt`."
            )
        if not self.settings.openai_api_key:
            raise AIServiceConfigurationError(
                "Не задан `OPENAI_API_KEY` в `.env`."
            )

        client = self._get_client()
        try:
            response = client.responses.create(
                model=self.settings.openai_model,
                instructions=self._system_prompt(),
                input=self._build_input(
                    conversation_messages=conversation_messages,
                    user_text=user_text,
                    active_file=active_file,
                    active_file_context=active_file_context,
                ),
            )
        except Exception as exc:  # pragma: no cover - depends on external API/network
            logger.exception("OpenAI request failed")
            raise AIServiceRequestError(str(exc)) from exc

        payload = self._parse_response_text(getattr(response, "output_text", ""))
        logger.info("OpenAI plan received with %s actions", len(payload.actions))
        return payload

    def _get_client(self):
        if self._client is None:
            self._client = OpenAI(api_key=self.settings.openai_api_key)
        return self._client

    def _build_input(
        self,
        *,
        conversation_messages: list[dict[str, Any]],
        user_text: str,
        active_file: StoredFile | None,
        active_file_context: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        history = []
        for message in conversation_messages[-self.settings.openai_max_history_messages :]:
            history.append(
                {
                    "role": message.get("role", "assistant"),
                    "text": message.get("text", ""),
                }
            )

        current_request = user_text.strip() or "Пользователь загрузил файл без дополнительного текста."
        prompt_payload = {
            "current_user_message": current_request,
            "recent_messages": history,
            "active_file": active_file_context,
            "available_actions": [
                {"type": "preview"},
                {"type": "analyze"},
                {
                    "type": "generate_chart",
                    "chart_type": "histogram | bar | line | time_series | top_items | daily_count | monthly_sales | cumulative | distribution",
                    "x_column": "string | null",
                    "y_column": "string | null",
                },
                {"type": "generate_report", "description": "DOCX отчёт"},
                {"type": "generate_pdf", "description": "PDF отчёт с графиками и таблицами"},
                {"type": "generate_pptx", "description": "PowerPoint презентация"},
                {"type": "generate_business_report", "description": "Полный бизнес-пакет: набор графиков + PDF + PPTX"},
                {"type": "save_summary"},
            ],
            "response_contract": {
                "assistant_message": "string",
                "actions": "array",
            },
        }

        content: list[dict[str, Any]] = [
            {
                "type": "input_text",
                "text": (
                    "Верни только JSON без markdown-обёртки. "
                    "Строго следуй схеме из `response_contract`.\n\n"
                    + json.dumps(prompt_payload, ensure_ascii=False, indent=2)
                ),
            },
        ]

        if active_file and active_file.kind == "image":
            content.append(
                {
                    "type": "input_image",
                    "image_url": self._image_data_url(active_file),
                }
            )

        return [{"role": "user", "content": content}]

    def _system_prompt(self) -> str:
        return (
            "Ты — AI Analytics Assistant для веб-приложения на русском языке. "
            "Ты отвечаешь как реальный ИИ от OpenAI, помогаешь анализировать таблицы и изображения, "
            "объясняешь выводы простым языком и при необходимости выбираешь действия для приложения. "
            "Не придумывай действия вне разрешённого списка. "
            "Если пользователь просит график, отчёт или сохранение — добавь действие в `actions`. "
            "Для продаж и табличных данных предпочитай бизнес-типы графиков: "
            "`time_series`, `top_items`, `daily_count`, `monthly_sales`, `cumulative`, `distribution`. "
            "Для произвольных числовых — `histogram`, `bar`, `line`. "
            "Если просят полный отчёт/презентацию по продажам — используй `generate_business_report` "
            "(он автоматически построит набор графиков и сформирует PDF и PPTX). "
            "Отдельно доступны `generate_pdf`, `generate_pptx`, `generate_report` (DOCX). "
            "Если активный файл — изображение, используй визуальное содержимое изображения в ответе. "
            "Если активный файл — таблица, опирайся на переданные поля, preview, summary и признаки колонок. "
            "Если действий не требуется, верни пустой список `actions`."
        )

    def _parse_response_text(self, raw_text: str) -> AIPlan:
        text = (raw_text or "").strip()
        if text.startswith("```"):
            parts = text.split("```")
            text = parts[1] if len(parts) > 1 else text
            text = text.removeprefix("json").strip()

        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("OpenAI returned non-JSON output; falling back to plain text")
            return AIPlan(assistant_message=text or "Не удалось разобрать ответ модели.", actions=[])

        assistant_message = str(payload.get("assistant_message", "")).strip()
        if not assistant_message:
            assistant_message = "Готово. Я обработал запрос."

        allowed_actions = {
            "preview",
            "analyze",
            "generate_chart",
            "generate_report",
            "generate_pdf",
            "generate_pptx",
            "generate_business_report",
            "save_summary",
        }
        allowed_chart_types = {
            "histogram",
            "bar",
            "line",
            "time_series",
            "top_items",
            "daily_count",
            "monthly_sales",
            "cumulative",
            "distribution",
        }

        actions: list[dict[str, Any]] = []
        for item in payload.get("actions", []):
            if not isinstance(item, dict):
                continue
            action_type = str(item.get("type", "")).strip()
            if action_type not in allowed_actions:
                continue
            normalized: dict[str, Any] = {"type": action_type}
            if action_type == "generate_chart":
                chart_type = str(item.get("chart_type", "bar")).strip().lower()
                normalized["chart_type"] = chart_type if chart_type in allowed_chart_types else "bar"
                normalized["x_column"] = self._clean_optional_text(item.get("x_column"))
                normalized["y_column"] = self._clean_optional_text(item.get("y_column"))
            actions.append(normalized)

        return AIPlan(assistant_message=assistant_message, actions=actions[:6])

    def _clean_optional_text(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _image_data_url(self, stored_file: StoredFile) -> str:
        mime_type = stored_file.content_type or "image/png"
        encoded = base64.b64encode(stored_file.path.read_bytes()).decode("utf-8")
        return f"data:{mime_type};base64,{encoded}"
