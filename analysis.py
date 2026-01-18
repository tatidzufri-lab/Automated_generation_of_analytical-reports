"""
Модуль для анализа данных и построения графиков.
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from typing import Dict, Optional
import os


def compute_metrics(df: pd.DataFrame, date_col: Optional[str], amount_col: Optional[str], topn: int = 5) -> Dict:
    """
    Вычисляет основные метрики для аналитического отчёта.
    
    Args:
        df: DataFrame с данными
        date_col: Имя колонки с датами
        amount_col: Имя колонки с суммами
        topn: Количество позиций в топе
        
    Returns:
        Словарь с метриками и данными для графиков
    """
    metrics = {}
    
    # Общие метрики
    if amount_col and amount_col in df.columns:
        metrics['total_sales'] = float(df[amount_col].sum())
        metrics['avg_ticket'] = float(df[amount_col].mean())
    else:
        metrics['total_sales'] = 0.0
        metrics['avg_ticket'] = 0.0
    
    metrics['total_orders'] = len(df)
    
    # Топ позиций
    top_items_df = _get_top_items(df, amount_col, topn)
    metrics['top_items'] = top_items_df
    
    # Временной ряд
    time_series_df = _get_time_series(df, date_col, amount_col)
    metrics['time_series'] = time_series_df
    
    return metrics


def _get_top_items(df: pd.DataFrame, amount_col: Optional[str], topn: int) -> pd.DataFrame:
    """
    Получает топ позиций по продажам.
    
    Args:
        df: DataFrame с данными
        amount_col: Имя колонки с суммами
        topn: Количество позиций в топе
        
    Returns:
        DataFrame с топ позициями
    """
    # Ищем колонку для группировки
    item_cols = ['item', 'product', 'name', 'category']
    item_col = None
    
    for col in item_cols:
        if col in df.columns:
            item_col = col
            break
    
    if not item_col or not amount_col or amount_col not in df.columns:
        # Если нет колонки для группировки или суммы, возвращаем пустой DataFrame
        return pd.DataFrame(columns=['item', 'amount'])
    
    # Группируем и суммируем
    top_items = df.groupby(item_col)[amount_col].sum().sort_values(ascending=False).head(topn)
    
    # Преобразуем в DataFrame
    result_df = pd.DataFrame({
        'item': top_items.index,
        'amount': top_items.values
    }).reset_index(drop=True)
    
    return result_df


def _get_time_series(df: pd.DataFrame, date_col: Optional[str], amount_col: Optional[str]) -> pd.DataFrame:
    """
    Создаёт временной ряд продаж.
    
    Args:
        df: DataFrame с данными
        date_col: Имя колонки с датами
        amount_col: Имя колонки с суммами
        
    Returns:
        DataFrame с временным рядом
    """
    if not date_col or not amount_col or date_col not in df.columns or amount_col not in df.columns:
        return pd.DataFrame(columns=['date', 'amount'])
    
    # Группируем по дате и суммируем
    ts_df = df.groupby(date_col)[amount_col].sum().reset_index()
    ts_df.columns = ['date', 'amount']
    
    # Определяем период для ресемплинга
    if len(ts_df) > 0:
        date_range = (ts_df['date'].max() - ts_df['date'].min()).days
        
        if date_range > 180:
            freq = 'MS'  # месяцы
        elif date_range > 60:
            freq = 'W-MON'  # недели
        else:
            freq = 'D'  # дни
        
        # Ресемплируем
        ts_df = ts_df.set_index('date').resample(freq).sum().reset_index()
    
    return ts_df


# Размеры графиков для PDF (2 графика на первой странице)
CHART_FIGSIZE = (10, 3.5)  # Крупные, хорошо читаемые графики
CHART_DPI = 120


def plot_time_series(ts_df: pd.DataFrame, out_path: str) -> str:
    """
    Строит график временного ряда продаж.
    
    Args:
        ts_df: DataFrame с временным рядом
        out_path: Путь для сохранения графика
        
    Returns:
        Путь к сохранённому файлу
    """
    if ts_df.empty or 'date' not in ts_df.columns or 'amount' not in ts_df.columns:
        # Создаём пустой график если нет данных
        fig, ax = plt.subplots(figsize=CHART_FIGSIZE)
        ax.text(0.5, 0.5, 'Нет данных', ha='center', va='center', transform=ax.transAxes, fontsize=8)
        ax.set_title('Динамика продаж', fontsize=10)
    else:
        fig, ax = plt.subplots(figsize=CHART_FIGSIZE)
        
        # Строим график
        ax.plot(ts_df['date'], ts_df['amount'], linewidth=1.5, color='#2E86AB')
        ax.set_title('Динамика продаж', fontsize=10, fontweight='bold')
        ax.set_xlabel('Дата', fontsize=8)
        ax.set_ylabel('Сумма', fontsize=8)
        
        # Форматируем оси
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, fontsize=6)
        plt.setp(ax.yaxis.get_majorticklabels(), fontsize=6)
        
        # Форматируем ось Y для отображения сумм
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:,.0f}'))
    
    plt.tight_layout()
    plt.savefig(out_path, dpi=CHART_DPI, bbox_inches='tight')
    plt.close()
    
    return out_path


def plot_top_items(top_df: pd.DataFrame, out_path: str) -> str:
    """
    Строит горизонтальный барчарт топ позиций.
    
    Args:
        top_df: DataFrame с топ позициями
        out_path: Путь для сохранения графика
        
    Returns:
        Путь к сохранённому файлу
    """
    if top_df.empty or 'item' not in top_df.columns or 'amount' not in top_df.columns:
        # Создаём пустой график если нет данных
        fig, ax = plt.subplots(figsize=CHART_FIGSIZE)
        ax.text(0.5, 0.5, 'Нет данных', ha='center', va='center', transform=ax.transAxes, fontsize=8)
        ax.set_title('Топ позиций', fontsize=10)
    else:
        fig, ax = plt.subplots(figsize=CHART_FIGSIZE)
        
        # Обрезаем длинные названия
        labels = [str(item)[:25] + '...' if len(str(item)) > 25 else str(item) for item in top_df['item']]
        
        # Строим горизонтальный барчарт
        bars = ax.barh(range(len(top_df)), top_df['amount'], color='#A23B72')
        ax.set_yticks(range(len(top_df)))
        ax.set_yticklabels(labels, fontsize=6)
        ax.set_xlabel('Сумма', fontsize=8)
        ax.set_title('Топ позиций по продажам', fontsize=10, fontweight='bold')
        
        # Форматируем ось X
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:,.0f}'))
        plt.setp(ax.xaxis.get_majorticklabels(), fontsize=6)
        ax.grid(True, alpha=0.3, axis='x')
    
    plt.tight_layout()
    plt.savefig(out_path, dpi=CHART_DPI, bbox_inches='tight')
    plt.close()
    
    return out_path


def plot_daily_count(df: pd.DataFrame, date_col: Optional[str], out_path: str) -> Optional[str]:
    """
    Строит график количества записей по дате.
    
    Args:
        df: DataFrame с данными
        date_col: Имя колонки с датами
        out_path: Путь для сохранения графика
        
    Returns:
        Путь к сохранённому файлу или None если нет данных
    """
    if not date_col or date_col not in df.columns:
        return None
    
    # Проверяем наличие валидных дат
    valid_dates = df[date_col].dropna()
    if valid_dates.empty:
        return None
    
    fig, ax = plt.subplots(figsize=CHART_FIGSIZE)
    
    # Группируем по дате и считаем количество
    daily_count = df.groupby(df[date_col].dt.date).size()
    
    if daily_count.empty:
        plt.close()
        return None
    
    # Строим график
    ax.plot(daily_count.index, daily_count.values, linewidth=1.5, color='#28A745', marker='o', markersize=2)
    ax.fill_between(daily_count.index, daily_count.values, alpha=0.3, color='#28A745')
    ax.set_title('Количество записей по дате', fontsize=10, fontweight='bold')
    ax.set_xlabel('Дата', fontsize=8)
    ax.set_ylabel('Количество', fontsize=8)
    
    # Форматируем оси
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, fontsize=6)
    plt.setp(ax.yaxis.get_majorticklabels(), fontsize=6)
    
    plt.tight_layout()
    plt.savefig(out_path, dpi=CHART_DPI, bbox_inches='tight')
    plt.close()
    
    return out_path


def plot_monthly_sales(df: pd.DataFrame, date_col: Optional[str], amount_col: Optional[str], out_path: str) -> Optional[str]:
    """
    Строит столбчатый график суммы продаж по месяцам.
    
    Args:
        df: DataFrame с данными
        date_col: Имя колонки с датами
        amount_col: Имя колонки с суммами
        out_path: Путь для сохранения графика
        
    Returns:
        Путь к сохранённому файлу или None если нет данных
    """
    if not date_col or date_col not in df.columns or not amount_col or amount_col not in df.columns:
        return None
    
    # Фильтруем валидные данные
    valid_df = df[[date_col, amount_col]].dropna()
    if valid_df.empty:
        return None
    
    fig, ax = plt.subplots(figsize=CHART_FIGSIZE)
    
    # Группируем по месяцам
    monthly = valid_df.groupby(valid_df[date_col].dt.to_period('M'))[amount_col].sum()
    
    if monthly.empty:
        plt.close()
        return None
    
    # Преобразуем индекс для отображения
    months = [str(m) for m in monthly.index]
    values = monthly.values
    
    # Создаём градиентные цвета
    colors = plt.cm.Blues(np.linspace(0.4, 0.9, len(months)))
    
    bars = ax.bar(months, values, color=colors, edgecolor='#1a5276', linewidth=0.5)
    ax.set_title('Сумма продаж по месяцам', fontsize=10, fontweight='bold')
    ax.set_xlabel('Месяц', fontsize=8)
    ax.set_ylabel('Сумма', fontsize=8)
    
    # Форматируем ось Y
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:,.0f}'))
    plt.setp(ax.yaxis.get_majorticklabels(), fontsize=6)
    ax.grid(True, alpha=0.3, axis='y')
    plt.xticks(rotation=45, ha='right', fontsize=6)
    
    plt.tight_layout()
    plt.savefig(out_path, dpi=CHART_DPI, bbox_inches='tight')
    plt.close()
    
    return out_path


def plot_cumulative_sales(df: pd.DataFrame, date_col: Optional[str], amount_col: Optional[str], out_path: str) -> Optional[str]:
    """
    Строит график накопленных (кумулятивных) продаж.
    
    Args:
        df: DataFrame с данными
        date_col: Имя колонки с датами
        amount_col: Имя колонки с суммами
        out_path: Путь для сохранения графика
        
    Returns:
        Путь к сохранённому файлу или None если нет данных
    """
    if not date_col or date_col not in df.columns or not amount_col or amount_col not in df.columns:
        return None
    
    # Фильтруем и сортируем данные
    valid_df = df[[date_col, amount_col]].dropna().sort_values(date_col)
    if valid_df.empty:
        return None
    
    fig, ax = plt.subplots(figsize=CHART_FIGSIZE)
    
    # Вычисляем накопленную сумму
    cumsum = valid_df.set_index(date_col)[amount_col].cumsum()
    
    if cumsum.empty:
        plt.close()
        return None
    
    # Строим график
    ax.plot(cumsum.index, cumsum.values, linewidth=1.5, color='#8E44AD')
    ax.fill_between(cumsum.index, cumsum.values, alpha=0.2, color='#8E44AD')
    ax.set_title('Накопленные продажи', fontsize=10, fontweight='bold')
    ax.set_xlabel('Дата', fontsize=8)
    ax.set_ylabel('Сумма', fontsize=8)
    
    # Форматируем оси
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:,.0f}'))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, fontsize=6)
    plt.setp(ax.yaxis.get_majorticklabels(), fontsize=6)
    
    plt.tight_layout()
    plt.savefig(out_path, dpi=CHART_DPI, bbox_inches='tight')
    plt.close()
    
    return out_path


def plot_distribution(df: pd.DataFrame, amount_col: Optional[str], out_path: str) -> Optional[str]:
    """
    Строит гистограмму распределения сумм продаж.
    
    Args:
        df: DataFrame с данными
        amount_col: Имя колонки с суммами
        out_path: Путь для сохранения графика
        
    Returns:
        Путь к сохранённому файлу или None если нет данных
    """
    if not amount_col or amount_col not in df.columns:
        return None
    
    # Фильтруем валидные данные
    values = df[amount_col].dropna()
    if values.empty or len(values) < 2:
        return None
    
    fig, ax = plt.subplots(figsize=CHART_FIGSIZE)
    
    # Определяем количество бинов (не более 20)
    n_bins = min(20, max(8, len(values) // 15))
    
    # Строим гистограмму
    n, bins, patches = ax.hist(values, bins=n_bins, color='#E74C3C', edgecolor='#C0392B', alpha=0.8)
    
    # Добавляем линию среднего
    mean_val = values.mean()
    ax.axvline(mean_val, color='#2C3E50', linestyle='--', linewidth=1.5, label=f'Сред: {mean_val:,.0f}')
    
    # Добавляем линию медианы
    median_val = values.median()
    ax.axvline(median_val, color='#27AE60', linestyle='-.', linewidth=1.5, label=f'Мед: {median_val:,.0f}')
    
    ax.set_title('Распределение сумм продаж', fontsize=10, fontweight='bold')
    ax.set_xlabel('Сумма', fontsize=8)
    ax.set_ylabel('Частота', fontsize=8)
    ax.legend(loc='upper right', fontsize=6)
    
    # Форматируем оси
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:,.0f}'))
    plt.setp(ax.xaxis.get_majorticklabels(), fontsize=6)
    plt.setp(ax.yaxis.get_majorticklabels(), fontsize=6)
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig(out_path, dpi=CHART_DPI, bbox_inches='tight')
    plt.close()
    
    return out_path
