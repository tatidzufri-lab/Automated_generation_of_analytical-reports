"""
Модуль для анализа данных и построения графиков.
"""
import pandas as pd
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
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.text(0.5, 0.5, 'Нет данных для построения графика', 
                ha='center', va='center', transform=ax.transAxes)
        ax.set_title('Динамика продаж')
    else:
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Строим график
        ax.plot(ts_df['date'], ts_df['amount'], linewidth=2, color='#2E86AB')
        ax.set_title('Динамика продаж', fontsize=16, fontweight='bold')
        ax.set_xlabel('Дата', fontsize=12)
        ax.set_ylabel('Сумма продаж', fontsize=12)
        
        # Форматируем оси
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
        
        # Форматируем ось Y для отображения сумм
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:,.0f}'))
    
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
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
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, 'Нет данных для построения графика', 
                ha='center', va='center', transform=ax.transAxes)
        ax.set_title('Топ позиций')
    else:
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Строим горизонтальный барчарт
        bars = ax.barh(range(len(top_df)), top_df['amount'], color='#A23B72')
        ax.set_yticks(range(len(top_df)))
        ax.set_yticklabels(top_df['item'], fontsize=10)
        ax.set_xlabel('Сумма продаж', fontsize=12)
        ax.set_title('Топ позиций по продажам', fontsize=16, fontweight='bold')
        
        # Добавляем значения на бары
        for i, (bar, amount) in enumerate(zip(bars, top_df['amount'])):
            ax.text(bar.get_width() + max(top_df['amount']) * 0.01, 
                   bar.get_y() + bar.get_height()/2, 
                   f'{amount:,.0f}', 
                   va='center', ha='left', fontsize=9)
        
        # Форматируем ось X
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:,.0f}'))
        ax.grid(True, alpha=0.3, axis='x')
    
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    return out_path
