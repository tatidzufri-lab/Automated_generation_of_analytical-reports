from __future__ import annotations

import logging
from typing import Any, Optional

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from app.core.config import Settings, get_settings
from app.services.analysis_service import AnalysisService
from app.services.artifact_naming import humanize_artifact_name
from app.services.file_service import FileReadError, FileService, StoredFile
from app.services.time_utils import filename_timestamp


logger = logging.getLogger(__name__)


BASIC_CHART_TYPES = {"line", "bar", "histogram"}
BUSINESS_CHART_TYPES = {
    "time_series",
    "top_items",
    "daily_count",
    "monthly_sales",
    "cumulative",
    "distribution",
}
SUPPORTED_CHART_TYPES = BASIC_CHART_TYPES | BUSINESS_CHART_TYPES


CHART_FIGSIZE = (10, 5.8)
CHART_DPI = 150
PALETTE = {
    "line": "#2E86AB",
    "top": "#A23B72",
    "count": "#28A745",
    "monthly": "#1F6FB2",
    "cumulative": "#8E44AD",
    "distribution": "#E74C3C",
    "hist": "#d06b4e",
    "bar": "#6c8b6b",
    "neutral": "#114b5f",
}


class ChartService:
    def __init__(
        self,
        file_service: FileService,
        settings: Settings | None = None,
        analysis_service: AnalysisService | None = None,
    ) -> None:
        self.file_service = file_service
        self.settings = settings or get_settings()
        self.analysis_service = analysis_service or AnalysisService(file_service)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate_chart(
        self,
        stored_file: StoredFile,
        chart_type: str,
        x_column: str | None = None,
        y_column: str | None = None,
    ) -> dict[str, Any]:
        chart_type = (chart_type or "").lower()
        if chart_type not in SUPPORTED_CHART_TYPES:
            raise FileReadError(
                "Поддерживаются графики: line, bar, histogram, time_series, top_items, daily_count, monthly_sales, cumulative, distribution."
            )

        self.file_service.ensure_storage()
        if chart_type in BUSINESS_CHART_TYPES:
            chart = self._generate_business_chart(stored_file, chart_type, x_column, y_column)
        elif stored_file.kind == "table":
            chart = self._generate_table_chart(stored_file, chart_type, x_column, y_column)
        else:
            chart = self._generate_image_chart(stored_file, chart_type)

        logger.info("Generated %s chart for %s", chart_type, stored_file.file_id)
        return chart

    def generate_default_charts(self, stored_file: StoredFile) -> list[dict[str, Any]]:
        charts: list[dict[str, Any]] = []
        for chart_type in ("histogram", "bar"):
            try:
                charts.append(self.generate_chart(stored_file, chart_type))
            except FileReadError:
                continue
        return charts

    def generate_business_charts(
        self,
        stored_file: StoredFile,
        date_col: Optional[str] = None,
        amount_col: Optional[str] = None,
        item_col: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Generate a full sales-style chart pack. Skips charts when data is insufficient."""
        if stored_file.kind != "table":
            return []

        detected = self.analysis_service.detect_business_columns(
            self.file_service.read_dataframe(stored_file)
        )
        date_col = date_col or detected["date_col"]
        amount_col = amount_col or detected["amount_col"]
        item_col = item_col or detected["item_col"]

        charts: list[dict[str, Any]] = []
        for chart_type in (
            "time_series",
            "top_items",
            "daily_count",
            "monthly_sales",
            "cumulative",
            "distribution",
        ):
            try:
                charts.append(
                    self._generate_business_chart(
                        stored_file,
                        chart_type,
                        x_column=date_col,
                        y_column=amount_col,
                        item_column=item_col,
                    )
                )
            except FileReadError as exc:
                logger.info("Skip %s chart for %s: %s", chart_type, stored_file.file_id, exc)
                continue
        return charts

    # ------------------------------------------------------------------
    # Business charts
    # ------------------------------------------------------------------
    def _generate_business_chart(
        self,
        stored_file: StoredFile,
        chart_type: str,
        x_column: Optional[str] = None,
        y_column: Optional[str] = None,
        item_column: Optional[str] = None,
    ) -> dict[str, Any]:
        if stored_file.kind != "table":
            raise FileReadError("Бизнес-графики требуют табличный файл.")

        dataframe = self.file_service.read_dataframe(stored_file)
        detected = self.analysis_service.detect_business_columns(dataframe)
        date_col = x_column or detected["date_col"]
        amount_col = y_column or detected["amount_col"]
        item_col = item_column or detected["item_col"]

        file_name = self._build_output_name(stored_file.file_id, chart_type, "png")
        output_path = self.settings.output_dir / file_name

        if chart_type == "time_series":
            description = self._plot_time_series(dataframe, date_col, amount_col, output_path)
            title = "Динамика продаж"
        elif chart_type == "top_items":
            description = self._plot_top_items(dataframe, item_col, amount_col, output_path)
            title = "Топ позиций"
        elif chart_type == "daily_count":
            description = self._plot_daily_count(dataframe, date_col, output_path)
            title = "Количество записей по дням"
        elif chart_type == "monthly_sales":
            description = self._plot_monthly_sales(dataframe, date_col, amount_col, output_path)
            title = "Продажи по месяцам"
        elif chart_type == "cumulative":
            description = self._plot_cumulative(dataframe, date_col, amount_col, output_path)
            title = "Накопленные продажи"
        else:
            description = self._plot_distribution(dataframe, amount_col, output_path)
            title = "Распределение сумм"

        return {
            "title": title,
            "description": description,
            "file_name": file_name,
            "display_name": humanize_artifact_name(file_name),
            "relative_path": f"outputs/{file_name}",
            "storage_url": f"/storage/outputs/{file_name}",
            "download_url": f"/download/{file_name}",
            "chart_type": chart_type,
        }

    def _plot_time_series(
        self,
        dataframe: pd.DataFrame,
        date_col: Optional[str],
        amount_col: Optional[str],
        output_path,
    ) -> str:
        if not date_col or not amount_col or date_col not in dataframe.columns or amount_col not in dataframe.columns:
            raise FileReadError("Для графика динамики нужны колонки даты и суммы.")

        frame = dataframe[[date_col, amount_col]].copy()
        frame[date_col] = pd.to_datetime(frame[date_col], errors="coerce")
        frame[amount_col] = pd.to_numeric(frame[amount_col], errors="coerce")
        frame = frame.dropna()
        if frame.empty:
            raise FileReadError("Недостаточно данных для графика динамики.")

        grouped = frame.groupby(date_col)[amount_col].sum().sort_index().reset_index()
        span = (grouped[date_col].max() - grouped[date_col].min()).days
        freq = "MS" if span > 180 else ("W-MON" if span > 60 else "D")
        resampled = grouped.set_index(date_col).resample(freq)[amount_col].sum().reset_index()

        figure, axis = self._make_axes()
        axis.plot(resampled[date_col], resampled[amount_col], linewidth=2.2, color=PALETTE["line"], marker="o", markersize=3)
        axis.fill_between(resampled[date_col], resampled[amount_col], alpha=0.08, color=PALETTE["line"])
        axis.set_title("Динамика продаж", fontweight="bold")
        axis.set_xlabel("Дата")
        axis.set_ylabel("Сумма")
        axis.grid(True, alpha=0.25)
        axis.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%Y"))
        axis.xaxis.set_major_locator(mdates.AutoDateLocator())
        axis.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _p: f"{x:,.0f}".replace(",", " ")))
        plt.setp(axis.xaxis.get_majorticklabels(), rotation=30, ha="right")
        self._save(figure, output_path)
        return f"Динамика «{amount_col}» по оси «{date_col}»."

    def _plot_top_items(
        self,
        dataframe: pd.DataFrame,
        item_col: Optional[str],
        amount_col: Optional[str],
        output_path,
    ) -> str:
        if not item_col or not amount_col or item_col not in dataframe.columns or amount_col not in dataframe.columns:
            raise FileReadError("Для топа позиций нужны колонки категории и суммы.")

        frame = dataframe[[item_col, amount_col]].copy()
        frame[amount_col] = pd.to_numeric(frame[amount_col], errors="coerce")
        frame = frame.dropna()
        if frame.empty:
            raise FileReadError("Недостаточно данных для топа позиций.")

        top = frame.groupby(item_col)[amount_col].sum().sort_values(ascending=True).tail(10)
        labels = [str(idx)[:32] + ("…" if len(str(idx)) > 32 else "") for idx in top.index]

        figure, axis = self._make_axes()
        axis.barh(labels, top.values, color=PALETTE["top"])
        axis.set_title("Топ позиций по продажам", fontweight="bold")
        axis.set_xlabel("Сумма")
        axis.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _p: f"{x:,.0f}".replace(",", " ")))
        axis.grid(True, alpha=0.25, axis="x")
        self._save(figure, output_path)
        return f"Топ позиций по сумме «{amount_col}», категория «{item_col}»."

    def _plot_daily_count(
        self,
        dataframe: pd.DataFrame,
        date_col: Optional[str],
        output_path,
    ) -> str:
        if not date_col or date_col not in dataframe.columns:
            raise FileReadError("Для графика количества нужна колонка даты.")
        dates = pd.to_datetime(dataframe[date_col], errors="coerce").dropna()
        if dates.empty:
            raise FileReadError("Недостаточно валидных дат для подсчёта.")

        daily = dates.dt.date.value_counts().sort_index()
        figure, axis = self._make_axes()
        axis.plot(daily.index, daily.values, linewidth=1.8, color=PALETTE["count"], marker="o", markersize=3)
        axis.fill_between(daily.index, daily.values, alpha=0.25, color=PALETTE["count"])
        axis.set_title("Количество записей по дням", fontweight="bold")
        axis.set_xlabel("Дата")
        axis.set_ylabel("Количество")
        axis.grid(True, alpha=0.25)
        plt.setp(axis.xaxis.get_majorticklabels(), rotation=30, ha="right")
        self._save(figure, output_path)
        return f"Количество записей по дням колонки «{date_col}»."

    def _plot_monthly_sales(
        self,
        dataframe: pd.DataFrame,
        date_col: Optional[str],
        amount_col: Optional[str],
        output_path,
    ) -> str:
        if not date_col or not amount_col or date_col not in dataframe.columns or amount_col not in dataframe.columns:
            raise FileReadError("Для месячных продаж нужны колонки даты и суммы.")
        frame = dataframe[[date_col, amount_col]].copy()
        frame[date_col] = pd.to_datetime(frame[date_col], errors="coerce")
        frame[amount_col] = pd.to_numeric(frame[amount_col], errors="coerce")
        frame = frame.dropna()
        if frame.empty:
            raise FileReadError("Недостаточно данных для месячного графика.")

        monthly = frame.groupby(frame[date_col].dt.to_period("M"))[amount_col].sum()
        labels = [str(period) for period in monthly.index]
        values = monthly.values
        colors = plt.cm.Blues(np.linspace(0.4, 0.9, max(len(labels), 1)))

        figure, axis = self._make_axes()
        axis.bar(labels, values, color=colors, edgecolor="#1a5276", linewidth=0.4)
        axis.set_title("Продажи по месяцам", fontweight="bold")
        axis.set_xlabel("Месяц")
        axis.set_ylabel("Сумма")
        axis.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _p: f"{x:,.0f}".replace(",", " ")))
        axis.grid(True, alpha=0.25, axis="y")
        plt.setp(axis.xaxis.get_majorticklabels(), rotation=45, ha="right")
        self._save(figure, output_path)
        return f"Сумма «{amount_col}» по месяцам «{date_col}»."

    def _plot_cumulative(
        self,
        dataframe: pd.DataFrame,
        date_col: Optional[str],
        amount_col: Optional[str],
        output_path,
    ) -> str:
        if not date_col or not amount_col or date_col not in dataframe.columns or amount_col not in dataframe.columns:
            raise FileReadError("Для накопленного графика нужны колонки даты и суммы.")
        frame = dataframe[[date_col, amount_col]].copy()
        frame[date_col] = pd.to_datetime(frame[date_col], errors="coerce")
        frame[amount_col] = pd.to_numeric(frame[amount_col], errors="coerce")
        frame = frame.dropna().sort_values(date_col)
        if frame.empty:
            raise FileReadError("Недостаточно данных для накопленного графика.")

        cumulative = frame.set_index(date_col)[amount_col].cumsum()
        figure, axis = self._make_axes()
        axis.plot(cumulative.index, cumulative.values, linewidth=2.2, color=PALETTE["cumulative"])
        axis.fill_between(cumulative.index, cumulative.values, alpha=0.2, color=PALETTE["cumulative"])
        axis.set_title("Накопленные продажи", fontweight="bold")
        axis.set_xlabel("Дата")
        axis.set_ylabel("Сумма")
        axis.grid(True, alpha=0.25)
        axis.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%Y"))
        axis.xaxis.set_major_locator(mdates.AutoDateLocator())
        axis.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _p: f"{x:,.0f}".replace(",", " ")))
        plt.setp(axis.xaxis.get_majorticklabels(), rotation=30, ha="right")
        self._save(figure, output_path)
        return f"Накопленная сумма «{amount_col}» по оси «{date_col}»."

    def _plot_distribution(
        self,
        dataframe: pd.DataFrame,
        amount_col: Optional[str],
        output_path,
    ) -> str:
        if not amount_col or amount_col not in dataframe.columns:
            raise FileReadError("Для распределения нужна колонка суммы.")
        values = pd.to_numeric(dataframe[amount_col], errors="coerce").dropna()
        if len(values) < 2:
            raise FileReadError("Недостаточно значений для распределения.")

        n_bins = int(min(25, max(10, len(values) // 15)))
        figure, axis = self._make_axes()
        axis.hist(values, bins=n_bins, color=PALETTE["distribution"], edgecolor="#C0392B", alpha=0.85)
        mean_value = float(values.mean())
        median_value = float(values.median())
        axis.axvline(mean_value, color="#2C3E50", linestyle="--", linewidth=1.6, label=f"Среднее: {mean_value:,.0f}".replace(",", " "))
        axis.axvline(median_value, color="#27AE60", linestyle="-.", linewidth=1.6, label=f"Медиана: {median_value:,.0f}".replace(",", " "))
        axis.set_title(f"Распределение «{amount_col}»", fontweight="bold")
        axis.set_xlabel("Сумма")
        axis.set_ylabel("Частота")
        axis.legend(loc="upper right")
        axis.grid(True, alpha=0.25, axis="y")
        axis.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _p: f"{x:,.0f}".replace(",", " ")))
        self._save(figure, output_path)
        return f"Распределение значений «{amount_col}»."

    # ------------------------------------------------------------------
    # Generic table / image charts (from the data_assistant base)
    # ------------------------------------------------------------------
    def _generate_table_chart(
        self,
        stored_file: StoredFile,
        chart_type: str,
        x_column: str | None,
        y_column: str | None,
    ) -> dict[str, Any]:
        dataframe = self.file_service.read_dataframe(stored_file)
        columns = self.file_service.describe_columns(dataframe)
        numeric_columns = [item["name"] for item in columns if item["kind"] == "numeric"]
        dimension_columns = [item["name"] for item in columns if item["kind"] in {"categorical", "datetime"}]

        selected_x = x_column or (dimension_columns or list(dataframe.columns))[0]
        selected_y = y_column or (numeric_columns or list(dataframe.columns))[0]
        file_name = self._build_output_name(stored_file.file_id, chart_type, "png")
        output_path = self.settings.output_dir / file_name

        figure, axis = self._make_axes()

        if chart_type == "histogram":
            if not numeric_columns:
                raise FileReadError("Для histogram нужен хотя бы один числовой столбец.")
            selected_x = x_column or numeric_columns[0]
            series = pd.to_numeric(dataframe[selected_x], errors="coerce").dropna()
            if series.empty:
                raise FileReadError("Недостаточно числовых значений для histogram.")
            bins = min(20, max(8, int(np.sqrt(len(series)))))
            axis.hist(series, bins=bins, color=PALETTE["hist"], edgecolor="#8d3f28")
            axis.set_title(f"Histogram: {selected_x}")
            axis.set_xlabel(selected_x)
            axis.set_ylabel("Частота")
            description = f"Распределение значений колонки «{selected_x}»."
        elif chart_type == "line":
            if not numeric_columns:
                raise FileReadError("Для line нужен хотя бы один числовой столбец.")
            plot_frame = dataframe[[selected_x, selected_y]].copy()
            plot_frame[selected_y] = pd.to_numeric(plot_frame[selected_y], errors="coerce")
            plot_frame = plot_frame.dropna(subset=[selected_y]).head(50)
            if plot_frame.empty:
                raise FileReadError("Недостаточно данных для line графика.")
            axis.plot(
                plot_frame[selected_x].astype(str),
                plot_frame[selected_y],
                color=PALETTE["neutral"],
                linewidth=2.2,
                marker="o",
            )
            axis.set_title(f"Line chart: {selected_y} от {selected_x}")
            axis.set_xlabel(selected_x)
            axis.set_ylabel(selected_y)
            axis.tick_params(axis="x", rotation=35)
            description = f"Линейная динамика «{selected_y}» по оси «{selected_x}»."
        else:
            if numeric_columns:
                group_x = x_column or (dimension_columns or list(dataframe.columns))[0]
                group_y = y_column or numeric_columns[0]
                grouped = (
                    dataframe[[group_x, group_y]]
                    .copy()
                    .dropna(subset=[group_x, group_y])
                    .groupby(group_x, dropna=True)[group_y]
                    .mean()
                    .sort_values(ascending=False)
                    .head(12)
                )
                if grouped.empty:
                    raise FileReadError("Недостаточно данных для bar графика.")
                axis.bar(grouped.index.astype(str), grouped.values, color=PALETTE["bar"])
                axis.set_ylabel(f"Среднее {group_y}")
                axis.set_title(f"Bar chart: {group_x}")
                description = f"Средние значения «{group_y}» по категориям «{group_x}»."
            else:
                counts = dataframe[selected_x].astype(str).value_counts().head(12)
                axis.bar(counts.index, counts.values, color=PALETTE["bar"])
                axis.set_ylabel("Количество")
                axis.set_title(f"Bar chart: {selected_x}")
                description = f"Частоты по колонке «{selected_x}»."
            axis.tick_params(axis="x", rotation=30)

        self._save(figure, output_path)
        return {
            "title": f"{chart_type.title()} chart",
            "description": description,
            "file_name": file_name,
            "display_name": humanize_artifact_name(file_name),
            "relative_path": f"outputs/{file_name}",
            "storage_url": f"/storage/outputs/{file_name}",
            "download_url": f"/download/{file_name}",
            "chart_type": chart_type,
        }

    def _generate_image_chart(self, stored_file: StoredFile, chart_type: str) -> dict[str, Any]:
        image = self.file_service.open_image(stored_file)
        array = np.array(image)
        grayscale = np.array(image.convert("L"))
        file_name = self._build_output_name(stored_file.file_id, chart_type, "png")
        output_path = self.settings.output_dir / file_name

        figure, axis = self._make_axes()

        if chart_type == "histogram":
            axis.hist(grayscale.ravel(), bins=32, color=PALETTE["hist"], edgecolor="#8d3f28")
            axis.set_title("Гистограмма яркости пикселей")
            axis.set_xlabel("Intensity")
            axis.set_ylabel("Количество")
            description = "Распределение интенсивности пикселей изображения."
        elif chart_type == "bar":
            if array.ndim == 2:
                labels = ["L"]
                values = [grayscale.mean()]
                colors = [PALETTE["neutral"]]
            else:
                labels = list(image.getbands())
                values = [array[:, :, index].mean() for index in range(array.shape[2])]
                colors = [PALETTE["neutral"], PALETTE["bar"], PALETTE["hist"], "#8d3f28"][: len(labels)]
            axis.bar(labels, values, color=colors)
            axis.set_title("Средние значения по каналам")
            axis.set_ylabel("Среднее значение")
            description = "Средние значения по каналам изображения."
        else:
            profile = grayscale.mean(axis=0)
            axis.plot(np.arange(len(profile)), profile, color=PALETTE["neutral"], linewidth=2.0)
            axis.set_title("Яркость по горизонтали")
            axis.set_xlabel("X coordinate")
            axis.set_ylabel("Средняя яркость")
            description = "Средняя яркость по горизонтальной оси изображения."

        self._save(figure, output_path)
        return {
            "title": f"{chart_type.title()} chart",
            "description": description,
            "file_name": file_name,
            "display_name": humanize_artifact_name(file_name),
            "relative_path": f"outputs/{file_name}",
            "storage_url": f"/storage/outputs/{file_name}",
            "download_url": f"/download/{file_name}",
            "chart_type": chart_type,
        }

    # ------------------------------------------------------------------
    # Figure helpers
    # ------------------------------------------------------------------
    def _make_axes(self):
        figure, axis = plt.subplots(figsize=CHART_FIGSIZE, dpi=CHART_DPI)
        figure.patch.set_facecolor("#f8f3ea")
        axis.set_facecolor("#fffaf3")
        return figure, axis

    def _save(self, figure, output_path) -> None:
        figure.tight_layout()
        figure.savefig(output_path, bbox_inches="tight")
        plt.close(figure)

    def _build_output_name(self, file_id: str, artifact_type: str, extension: str) -> str:
        return f"{file_id}__{artifact_type}__{filename_timestamp()}.{extension}"
