from __future__ import annotations

import logging
from typing import Any, Optional

import numpy as np
import pandas as pd

from app.services.file_service import FileService, StoredFile


logger = logging.getLogger(__name__)


DATE_KEYWORDS = (
    "date",
    "time",
    "dt",
    "день",
    "дата",
    "период",
    "month",
    "year",
    "timestamp",
    "created",
    "order_date",
    "sale_date",
)
AMOUNT_KEYWORDS = (
    "amount",
    "sum",
    "total",
    "revenue",
    "sales",
    "price",
    "cost",
    "value",
    "сумма",
    "выручка",
    "продаж",
    "стоимость",
    "оборот",
    "cheque",
    "чек",
    "discounted_price",
    "actual_price",
)
ITEM_KEYWORDS = (
    "item",
    "product",
    "name",
    "category",
    "sku",
    "title",
    "товар",
    "продукт",
    "категор",
    "наимен",
)


class AnalysisService:
    def __init__(self, file_service: FileService) -> None:
        self.file_service = file_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def analyze(self, stored_file: StoredFile) -> dict[str, Any]:
        if stored_file.kind == "table":
            return self._analyze_table(stored_file)
        return self._analyze_image(stored_file)

    def detect_business_columns(self, dataframe: pd.DataFrame) -> dict[str, Optional[str]]:
        """Try to guess date / amount / item columns for sales-style datasets."""
        return {
            "date_col": self._find_date_column(dataframe),
            "amount_col": self._find_amount_column(dataframe),
            "item_col": self._find_item_column(dataframe),
        }

    def compute_business_metrics(
        self,
        stored_file: StoredFile,
        date_col: Optional[str] = None,
        amount_col: Optional[str] = None,
        item_col: Optional[str] = None,
        topn: int = 5,
    ) -> dict[str, Any]:
        """Compute sales-style metrics: totals, average ticket, orders, top items, time series."""
        if stored_file.kind != "table":
            raise ValueError("Business metrics требуют табличный файл.")

        dataframe = self.file_service.read_dataframe(stored_file).copy()
        detected = self.detect_business_columns(dataframe)
        date_col = date_col or detected["date_col"]
        amount_col = amount_col or detected["amount_col"]
        item_col = item_col or detected["item_col"]

        prepared = self._coerce_business_columns(dataframe, date_col, amount_col)

        if amount_col and amount_col in prepared.columns:
            total_sales = float(prepared[amount_col].sum())
            avg_ticket = float(prepared[amount_col].mean()) if len(prepared) else 0.0
        else:
            total_sales = 0.0
            avg_ticket = 0.0

        total_orders = int(len(prepared))

        top_items: list[dict[str, Any]] = []
        if item_col and amount_col and item_col in prepared.columns and amount_col in prepared.columns:
            top_series = (
                prepared.groupby(item_col)[amount_col]
                .sum()
                .sort_values(ascending=False)
                .head(topn)
            )
            top_items = [
                {"item": str(index), "amount": float(value)}
                for index, value in top_series.items()
            ]

        time_series: list[dict[str, Any]] = []
        if date_col and amount_col and date_col in prepared.columns and amount_col in prepared.columns:
            ts_frame = (
                prepared[[date_col, amount_col]]
                .dropna(subset=[date_col])
                .groupby(date_col)[amount_col]
                .sum()
                .reset_index()
                .sort_values(date_col)
            )
            ts_frame = self._resample_time_series(ts_frame, date_col, amount_col)
            time_series = [
                {"date": value.strftime("%Y-%m-%d") if isinstance(value, pd.Timestamp) else str(value), "amount": float(amount)}
                for value, amount in zip(ts_frame[date_col], ts_frame[amount_col])
            ]

        sample_rows = prepared.head(10).to_dict("records")

        return {
            "date_col": date_col,
            "amount_col": amount_col,
            "item_col": item_col,
            "total_sales": total_sales,
            "avg_ticket": avg_ticket,
            "total_orders": total_orders,
            "top_items": top_items,
            "time_series": time_series,
            "has_business_context": bool(amount_col or date_col),
            "sample_rows": sample_rows,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    def _analyze_table(self, stored_file: StoredFile) -> dict[str, Any]:
        dataframe = self.file_service.read_dataframe(stored_file)
        columns = self.file_service.describe_columns(dataframe)

        numeric_frame = dataframe.select_dtypes(include=[np.number])
        stats_records: list[dict[str, str]] = []
        if not numeric_frame.empty:
            for column in numeric_frame.columns:
                series = numeric_frame[column]
                stats_records.append(
                    {
                        "column": str(column),
                        "mean": self.file_service.format_value(series.mean(skipna=True)),
                        "median": self.file_service.format_value(series.median(skipna=True)),
                        "std": self.file_service.format_value(series.std(skipna=True)),
                        "min": self.file_service.format_value(series.min(skipna=True)),
                        "max": self.file_service.format_value(series.max(skipna=True)),
                    }
                )

        missing_summary = []
        total_rows = max(len(dataframe), 1)
        for column in dataframe.columns:
            missing_count = int(dataframe[column].isna().sum())
            if missing_count:
                missing_summary.append(
                    {
                        "column": str(column),
                        "missing": missing_count,
                        "percent": f"{(missing_count / total_rows) * 100:.1f}%",
                    }
                )

        insights = [
            f"Найдено {len(dataframe):,} строк и {len(dataframe.columns)} колонок.".replace(",", " "),
            "Числовая статистика рассчитана с игнорированием NaN, пропуски вынесены в отдельный блок.",
        ]
        if stats_records:
            widest_spread = max(stats_records, key=lambda item: self._to_float(item["std"]))
            insights.append(f"Наибольшая вариативность у колонки «{widest_spread['column']}».")

        category_candidates = [
            item for item in columns if item["kind"] in {"categorical", "text"} and item["missing"] < len(dataframe)
        ]
        if category_candidates:
            insights.append(
                f"Колонка «{category_candidates[0]['name']}» подходит для bar-chart сегментации."
            )

        detected = self.detect_business_columns(dataframe)
        if detected["date_col"] and detected["amount_col"]:
            insights.append(
                f"Похоже на данные продаж: дата «{detected['date_col']}», сумма «{detected['amount_col']}». "
                "Доступен бизнес-отчёт в PDF и PPTX."
            )

        logger.info("Completed tabular analysis for %s", stored_file.file_id)
        return {
            "kind": "table",
            "summary": {
                "rows": int(len(dataframe)),
                "columns": int(len(dataframe.columns)),
                "numeric_columns": int(len(numeric_frame.columns)),
                "missing_cells": int(dataframe.isna().sum().sum()),
            },
            "column_profile": columns,
            "stats": stats_records,
            "missing_summary": missing_summary,
            "insights": insights,
            "business_columns": detected,
        }

    def _analyze_image(self, stored_file: StoredFile) -> dict[str, Any]:
        image = self.file_service.open_image(stored_file)
        array = np.array(image)
        grayscale = np.array(image.convert("L"))

        insights = [
            f"Разрешение изображения: {image.width}×{image.height}.",
            f"Средняя яркость: {grayscale.mean():.2f}.",
            "Для изображений доступны histogram, bar и line графики на основе пиксельных значений.",
        ]

        if array.ndim == 3:
            channel_names = list(image.getbands())
            stats = []
            for index, channel_name in enumerate(channel_names):
                channel = array[:, :, index]
                stats.append(
                    {
                        "channel": channel_name,
                        "mean": self.file_service.format_value(float(channel.mean())),
                        "median": self.file_service.format_value(float(np.median(channel))),
                        "std": self.file_service.format_value(float(channel.std())),
                        "min": self.file_service.format_value(int(channel.min())),
                        "max": self.file_service.format_value(int(channel.max())),
                    }
                )
        else:
            stats = [
                {
                    "channel": "L",
                    "mean": self.file_service.format_value(float(grayscale.mean())),
                    "median": self.file_service.format_value(float(np.median(grayscale))),
                    "std": self.file_service.format_value(float(grayscale.std())),
                    "min": self.file_service.format_value(int(grayscale.min())),
                    "max": self.file_service.format_value(int(grayscale.max())),
                }
            ]

        logger.info("Completed image analysis for %s", stored_file.file_id)
        return {
            "kind": "image",
            "summary": {
                "rows": image.height,
                "columns": image.width,
                "numeric_columns": len(stats),
                "missing_cells": 0,
            },
            "column_profile": [],
            "stats": stats,
            "missing_summary": [],
            "insights": insights,
            "business_columns": {"date_col": None, "amount_col": None, "item_col": None},
        }

    def _coerce_business_columns(
        self,
        dataframe: pd.DataFrame,
        date_col: Optional[str],
        amount_col: Optional[str],
    ) -> pd.DataFrame:
        frame = dataframe.copy()
        if date_col and date_col in frame.columns:
            frame[date_col] = pd.to_datetime(frame[date_col], errors="coerce")
            frame = frame.dropna(subset=[date_col])
        if amount_col and amount_col in frame.columns:
            frame[amount_col] = pd.to_numeric(frame[amount_col], errors="coerce").fillna(0)
        return frame

    def _resample_time_series(
        self,
        ts_df: pd.DataFrame,
        date_col: str,
        amount_col: str,
    ) -> pd.DataFrame:
        if ts_df.empty:
            return ts_df
        span = (ts_df[date_col].max() - ts_df[date_col].min()).days
        if span > 180:
            freq = "MS"
        elif span > 60:
            freq = "W-MON"
        else:
            freq = "D"
        return (
            ts_df.set_index(date_col)
            .resample(freq)[amount_col]
            .sum()
            .reset_index()
        )

    def _find_date_column(self, dataframe: pd.DataFrame) -> Optional[str]:
        for column in dataframe.columns:
            if pd.api.types.is_datetime64_any_dtype(dataframe[column]):
                return str(column)
        for column in dataframe.columns:
            lowered = str(column).lower()
            if any(keyword in lowered for keyword in DATE_KEYWORDS):
                parsed = pd.to_datetime(dataframe[column], errors="coerce")
                if parsed.notna().mean() >= 0.6:
                    return str(column)
        for column in dataframe.select_dtypes(include=["object"]).columns:
            parsed = pd.to_datetime(dataframe[column], errors="coerce")
            if parsed.notna().mean() >= 0.8:
                return str(column)
        return None

    def _find_amount_column(self, dataframe: pd.DataFrame) -> Optional[str]:
        numeric_columns = [str(c) for c in dataframe.select_dtypes(include=[np.number]).columns]
        for column in numeric_columns:
            lowered = column.lower()
            if any(keyword in lowered for keyword in AMOUNT_KEYWORDS):
                return column
        if numeric_columns:
            variances = {
                column: float(dataframe[column].var(skipna=True) or 0)
                for column in numeric_columns
            }
            if variances:
                return max(variances, key=variances.get)
        return None

    def _find_item_column(self, dataframe: pd.DataFrame) -> Optional[str]:
        for column in dataframe.columns:
            lowered = str(column).lower()
            if any(keyword in lowered for keyword in ITEM_KEYWORDS):
                if dataframe[column].dtype == "object" or not pd.api.types.is_numeric_dtype(dataframe[column]):
                    return str(column)
        for column in dataframe.columns:
            series = dataframe[column]
            if pd.api.types.is_numeric_dtype(series):
                continue
            non_null = series.dropna()
            if non_null.empty:
                continue
            unique_ratio = non_null.nunique() / max(len(non_null), 1)
            if 0.02 <= unique_ratio <= 0.5:
                return str(column)
        return None

    def _to_float(self, value: str) -> float:
        try:
            return float(str(value).replace(" ", ""))
        except ValueError:
            return 0.0
