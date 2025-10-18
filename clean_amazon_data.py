#!/usr/bin/env python3
"""
Скрипт для очистки данных Amazon CSV файла.
Приводит числовые значения к правильному формату.
"""
import pandas as pd
import re
import numpy as np

def clean_price(price_str):
    """
    Очищает цену от символов валют и запятых.
    
    Args:
        price_str: Строка с ценой (например, "₹1,099")
        
    Returns:
        float: Очищенное числовое значение
    """
    if pd.isna(price_str) or price_str == '':
        return np.nan
    
    # Удаляем символы валют и пробелы
    cleaned = re.sub(r'[₹$€£¥]', '', str(price_str))
    # Удаляем запятые
    cleaned = re.sub(r',', '', cleaned)
    # Удаляем все нечисловые символы кроме точки
    cleaned = re.sub(r'[^\d.]', '', cleaned)
    
    try:
        return float(cleaned) if cleaned else np.nan
    except ValueError:
        return np.nan

def clean_percentage(perc_str):
    """
    Очищает процент от символа %.
    
    Args:
        perc_str: Строка с процентом (например, "64%")
        
    Returns:
        float: Очищенное числовое значение
    """
    if pd.isna(perc_str) or perc_str == '':
        return np.nan
    
    # Удаляем символ %
    cleaned = re.sub(r'%', '', str(perc_str))
    
    try:
        return float(cleaned) if cleaned else np.nan
    except ValueError:
        return np.nan

def clean_rating_count(count_str):
    """
    Очищает количество оценок от запятых.
    
    Args:
        count_str: Строка с количеством (например, "24,269")
        
    Returns:
        float: Очищенное числовое значение
    """
    if pd.isna(count_str) or count_str == '':
        return np.nan
    
    # Удаляем запятые
    cleaned = re.sub(r',', '', str(count_str))
    
    try:
        return float(cleaned) if cleaned else np.nan
    except ValueError:
        return np.nan

def clean_amazon_data(input_file, output_file):
    """
    Очищает данные Amazon CSV файла.
    
    Args:
        input_file: Путь к исходному файлу
        output_file: Путь к очищенному файлу
    """
    print(f"🔄 Загрузка данных из {input_file}...")
    
    # Загружаем данные
    df = pd.read_csv(input_file)
    print(f"✅ Загружено {len(df)} записей")
    
    print("🔄 Очистка числовых данных...")
    
    # Очищаем цены
    df['discounted_price_clean'] = df['discounted_price'].apply(clean_price)
    df['actual_price_clean'] = df['actual_price'].apply(clean_price)
    
    # Очищаем процент скидки
    df['discount_percentage_clean'] = df['discount_percentage'].apply(clean_percentage)
    
    # Очищаем рейтинг (уже числовой, но проверим)
    df['rating_clean'] = pd.to_numeric(df['rating'], errors='coerce')
    
    # Очищаем количество оценок
    df['rating_count_clean'] = df['rating_count'].apply(clean_rating_count)
    
    # Удаляем строки где нет цены
    original_count = len(df)
    df = df.dropna(subset=['discounted_price_clean'])
    print(f"✅ Удалено {original_count - len(df)} записей без цены")
    
    # Создаём финальный датафрейм с очищенными данными
    cleaned_df = df.copy()
    
    # Заменяем исходные колонки на очищенные
    cleaned_df['discounted_price'] = cleaned_df['discounted_price_clean']
    cleaned_df['actual_price'] = cleaned_df['actual_price_clean']
    cleaned_df['discount_percentage'] = cleaned_df['discount_percentage_clean']
    cleaned_df['rating'] = cleaned_df['rating_clean']
    cleaned_df['rating_count'] = cleaned_df['rating_count_clean']
    
    # Удаляем временные колонки
    cleaned_df = cleaned_df.drop(columns=[
        'discounted_price_clean', 'actual_price_clean', 
        'discount_percentage_clean', 'rating_clean', 'rating_count_clean'
    ])
    
    # Сохраняем очищенные данные
    cleaned_df.to_csv(output_file, index=False)
    print(f"✅ Очищенные данные сохранены в {output_file}")
    
    # Выводим статистику
    print(f"\n📊 Статистика очищенных данных:")
    print(f"   • Количество записей: {len(cleaned_df):,}")
    print(f"   • Средняя цена со скидкой: ₹{cleaned_df['discounted_price'].mean():.2f}")
    print(f"   • Средняя обычная цена: ₹{cleaned_df['actual_price'].mean():.2f}")
    print(f"   • Средняя скидка: {cleaned_df['discount_percentage'].mean():.1f}%")
    print(f"   • Средний рейтинг: {cleaned_df['rating'].mean():.2f}")
    print(f"   • Среднее количество оценок: {cleaned_df['rating_count'].mean():.0f}")
    
    # Показываем примеры очищенных данных
    print(f"\n📋 Примеры очищенных данных:")
    print(cleaned_df[['product_name', 'discounted_price', 'actual_price', 'discount_percentage', 'rating', 'rating_count']].head())

if __name__ == '__main__':
    clean_amazon_data('amazon.csv', 'amazon_cleaned.csv')
