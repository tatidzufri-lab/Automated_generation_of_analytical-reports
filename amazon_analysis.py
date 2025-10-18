#!/usr/bin/env python3
"""
Детальный анализ данных Amazon с группировкой по категориям.
"""
import pandas as pd
import numpy as np
from report_cli import main as generate_report
import sys
import os

def analyze_amazon_data():
    """
    Выполняет детальный анализ данных Amazon.
    """
    print("🔄 Загрузка очищенных данных Amazon...")
    
    # Загружаем очищенные данные
    df = pd.read_csv('amazon_cleaned.csv')
    print(f"✅ Загружено {len(df)} записей")
    
    # Создаём колонку для группировки по категориям
    df['category_main'] = df['category'].str.split('|').str[0]
    
    print("\n📊 Анализ по основным категориям:")
    category_stats = df.groupby('category_main').agg({
        'discounted_price': ['count', 'sum', 'mean'],
        'actual_price': 'mean',
        'discount_percentage': 'mean',
        'rating': 'mean',
        'rating_count': 'sum'
    }).round(2)
    
    category_stats.columns = ['Количество товаров', 'Общая сумма со скидкой', 'Средняя цена со скидкой', 
                             'Средняя обычная цена', 'Средняя скидка %', 'Средний рейтинг', 'Общее количество оценок']
    
    print(category_stats)
    
    # Топ категории по продажам
    print(f"\n🏆 Топ-5 категорий по общей сумме продаж:")
    top_categories = category_stats.sort_values('Общая сумма со скидкой', ascending=False).head()
    for i, (category, row) in enumerate(top_categories.iterrows(), 1):
        print(f"   {i}. {category}: ₹{row['Общая сумма со скидкой']:,.0f}")
    
    # Анализ скидок
    print(f"\n💰 Анализ скидок:")
    print(f"   • Средняя скидка по всем товарам: {df['discount_percentage'].mean():.1f}%")
    print(f"   • Максимальная скидка: {df['discount_percentage'].max():.1f}%")
    print(f"   • Минимальная скидка: {df['discount_percentage'].min():.1f}%")
    
    # Анализ рейтингов
    print(f"\n⭐ Анализ рейтингов:")
    print(f"   • Средний рейтинг: {df['rating'].mean():.2f}")
    print(f"   • Максимальный рейтинг: {df['rating'].max():.2f}")
    print(f"   • Минимальный рейтинг: {df['rating'].min():.2f}")
    
    # Топ товары по рейтингу
    print(f"\n🌟 Топ-5 товаров по рейтингу:")
    top_rated = df.nlargest(5, 'rating')[['product_name', 'rating', 'rating_count', 'discounted_price']]
    for i, (_, row) in enumerate(top_rated.iterrows(), 1):
        name = row['product_name'][:60] + "..." if len(row['product_name']) > 60 else row['product_name']
        print(f"   {i}. {name}")
        print(f"      Рейтинг: {row['rating']:.1f}, Оценок: {row['rating_count']:,.0f}, Цена: ₹{row['discounted_price']:,.0f}")
    
    # Создаём отчёты для разных категорий
    print(f"\n📄 Создание отчётов для топ категорий...")
    
    for i, (category, _) in enumerate(top_categories.head(3).iterrows(), 1):
        category_df = df[df['category_main'] == category]
        
        # Сохраняем данные категории во временный файл
        temp_file = f'temp_category_{i}.csv'
        category_df.to_csv(temp_file, index=False)
        
        # Генерируем отчёт для категории
        print(f"   🔄 Генерация отчёта для категории: {category}")
        
        # Создаём аргументы для CLI
        sys.argv = [
            'report_cli.py',
            '-input', temp_file,
            '-amountcol', 'discounted_price',
            '-pdf', f'output/category_{i}_{category.replace("&", "and").replace(" ", "_")}.pdf',
            '-pptx', f'output/category_{i}_{category.replace("&", "and").replace(" ", "_")}.pptx',
            '-title', f'Анализ категории: {category}',
            '-topn', '10'
        ]
        
        try:
            generate_report()
            print(f"   ✅ Отчёт для категории '{category}' создан")
        except Exception as e:
            print(f"   ❌ Ошибка при создании отчёта для '{category}': {e}")
        finally:
            # Удаляем временный файл
            if os.path.exists(temp_file):
                os.remove(temp_file)
    
    print(f"\n🎉 Анализ завершён! Проверьте папку output/ для созданных отчётов.")

if __name__ == '__main__':
    analyze_amazon_data()
