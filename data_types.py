"""
Модуль для работы с типами данных и загрузки таблиц.
"""
import pandas as pd
import json
from typing import Optional
import os


def read_table(path: str) -> pd.DataFrame:
    """
    Читает табличные данные из CSV или JSON файла.
    
    Args:
        path: Путь к файлу с данными
        
    Returns:
        DataFrame с загруженными данными
        
    Raises:
        ValueError: Если формат файла не поддерживается
        FileNotFoundError: Если файл не найден
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Файл не найден: {path}")
    
    file_ext = os.path.splitext(path)[1].lower()
    
    try:
        if file_ext == '.csv':
            return pd.read_csv(path, encoding='utf-8', sep=',')
        elif file_ext == '.json':
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return pd.DataFrame(data)
        else:
            raise ValueError(f"Неподдерживаемый формат файла: {file_ext}. Поддерживаются только .csv и .json")
    except Exception as e:
        raise ValueError(f"Ошибка при чтении файла {path}: {str(e)}")


def enforce_types(df: pd.DataFrame, date_col: Optional[str], amount_col: Optional[str]) -> pd.DataFrame:
    """
    Приводит типы данных в DataFrame к нужным форматам.
    
    Args:
        df: Исходный DataFrame
        date_col: Имя колонки с датами (опционально)
        amount_col: Имя колонки с суммами (опционально)
        
    Returns:
        DataFrame с приведёнными типами данных
    """
    df = df.copy()
    
    # Обработка колонки с датами
    if date_col and date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        # Удаляем строки без корректной даты
        df = df.dropna(subset=[date_col])
    
    # Обработка колонки с суммами
    if amount_col and amount_col in df.columns:
        # Приводим к числовому типу, нечисловые значения становятся NaN
        df[amount_col] = pd.to_numeric(df[amount_col], errors='coerce')
        # Заполняем NaN нулями
        df[amount_col] = df[amount_col].fillna(0)
    
    return df
