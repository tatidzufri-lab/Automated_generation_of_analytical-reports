#!/usr/bin/env python3
"""
CLI для генерации аналитических отчётов в PDF и PPTX форматах.
"""
import argparse
import os
import sys
from datetime import datetime
from typing import Optional

# Импорты модулей проекта
from data_types import read_table, enforce_types
from analysis import (
    compute_metrics, 
    plot_time_series, 
    plot_top_items,
    plot_daily_count,
    plot_monthly_sales,
    plot_cumulative_sales,
    plot_distribution
)
from build_pdf import build_pdf
from build_pptx import build_pptx


def create_output_directory(output_path: str) -> None:
    """Создаёт директорию для выходного файла если её нет."""
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)


def validate_file_exists(file_path: str, description: str) -> None:
    """Проверяет существование файла."""
    if not os.path.exists(file_path):
        print(f"Ошибка: {description} не найден: {file_path}")
        sys.exit(1)


def main():
    """Основная функция CLI."""
    parser = argparse.ArgumentParser(
        description='Генерация аналитических отчётов в PDF и PPTX форматах',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python report_cli.py -input data.csv -pdf output/report.pdf -title "Отчёт по продажам"
  python report_cli.py -input data.json -datecol Date -amountcol Amount -pdf report.pdf -pptx report.pptx
  python report_cli.py -input sales.csv -topn 10 -title "Анализ продаж Q1"
        """
    )
    
    # Обязательные аргументы
    parser.add_argument(
        '-input', '--input',
        required=True,
        help='Путь к входному файлу (CSV или JSON)'
    )
    
    # Опциональные аргументы
    parser.add_argument(
        '-datecol', '--datecol',
        help='Имя колонки с датами'
    )
    
    parser.add_argument(
        '-amountcol', '--amountcol',
        help='Имя колонки с суммами'
    )
    
    parser.add_argument(
        '-pdf', '--pdf',
        help='Путь для сохранения PDF файла'
    )
    
    parser.add_argument(
        '-pptx', '--pptx',
        help='Путь для сохранения PPTX файла'
    )
    
    parser.add_argument(
        '-title', '--title',
        default='Аналитический отчёт',
        help='Заголовок отчёта (по умолчанию: "Аналитический отчёт")'
    )
    
    parser.add_argument(
        '-topn', '--topn',
        type=int,
        default=5,
        help='Количество позиций в топе (по умолчанию: 5)'
    )
    
    args = parser.parse_args()
    
    # Проверяем, что указан хотя бы один выходной формат
    if not args.pdf and not args.pptx:
        print("Ошибка: Необходимо указать хотя бы один выходной формат (-pdf или -pptx)")
        sys.exit(1)
    
    # Проверяем существование входного файла
    validate_file_exists(args.input, "Входной файл")
    
    try:
        print("🔄 Загрузка данных...")
        
        # Загружаем данные
        df = read_table(args.input)
        print(f"✅ Загружено {len(df)} записей из {args.input}")
        
        # Приводим типы данных
        df = enforce_types(df, args.datecol, args.amountcol)
        print(f"✅ Обработано {len(df)} записей после приведения типов")
        
        # Вычисляем метрики
        print("🔄 Вычисление метрик...")
        metrics = compute_metrics(df, args.datecol, args.amountcol, args.topn)
        
        # Создаём директорию output если её нет
        if not os.path.exists('output'):
            os.makedirs('output')
        
        # Строим графики
        print("🔄 Построение графиков...")
        timeseries_png = None
        top_items_png = None
        daily_count_png = None
        monthly_sales_png = None
        cumulative_png = None
        distribution_png = None
        
        # 1. График динамики продаж
        if not metrics['time_series'].empty:
            timeseries_png = plot_time_series(metrics['time_series'], 'output/timeseries.png')
            print(f"✅ График динамики сохранён: {timeseries_png}")
        
        # 2. График топ позиций
        if not metrics['top_items'].empty:
            top_items_png = plot_top_items(metrics['top_items'], 'output/top_items.png')
            print(f"✅ График топ позиций сохранён: {top_items_png}")
        
        # 3. График количества записей по дате
        daily_count_png = plot_daily_count(df, args.datecol, 'output/daily_count.png')
        if daily_count_png:
            print(f"✅ График количества записей сохранён: {daily_count_png}")
        
        # 4. График месячных продаж
        monthly_sales_png = plot_monthly_sales(df, args.datecol, args.amountcol, 'output/monthly_sales.png')
        if monthly_sales_png:
            print(f"✅ График месячных продаж сохранён: {monthly_sales_png}")
        
        # 5. График накопленных продаж
        cumulative_png = plot_cumulative_sales(df, args.datecol, args.amountcol, 'output/cumulative.png')
        if cumulative_png:
            print(f"✅ График накопленных продаж сохранён: {cumulative_png}")
        
        # 6. Гистограмма распределения
        distribution_png = plot_distribution(df, args.amountcol, 'output/distribution.png')
        if distribution_png:
            print(f"✅ Гистограмма распределения сохранена: {distribution_png}")
        
        # Подготавливаем контекст для шаблонов
        context = {
            'title': args.title,
            'generated_at': datetime.now().strftime('%d.%m.%Y %H:%M'),
            'total_sales': metrics['total_sales'],
            'avg_ticket': metrics['avg_ticket'],
            'total_orders': metrics['total_orders'],
            'top_items': metrics['top_items'].to_dict('records') if not metrics['top_items'].empty else [],
            'timeseries_png': timeseries_png,
            'top_items_png': top_items_png,
            'daily_count_png': daily_count_png,
            'monthly_sales_png': monthly_sales_png,
            'cumulative_png': cumulative_png,
            'distribution_png': distribution_png,
            'sample_rows': df.head(10).to_dict('records')  # Первые 10 строк для примера
        }
        
        # Генерируем PDF
        if args.pdf:
            print("🔄 Генерация PDF...")
            create_output_directory(args.pdf)
            build_pdf(context, args.pdf)
            print(f"✅ PDF отчёт создан: {args.pdf}")
        
        # Генерируем PPTX
        if args.pptx:
            print("🔄 Генерация PowerPoint...")
            create_output_directory(args.pptx)
            build_pptx(context, args.pptx)
            print(f"✅ PowerPoint презентация создана: {args.pptx}")
        
        print("\n🎉 Генерация отчётов завершена успешно!")
        
        # Считаем количество сгенерированных графиков
        charts_count = sum(1 for chart in [timeseries_png, top_items_png, daily_count_png, 
                                           monthly_sales_png, cumulative_png, distribution_png] if chart)
        
        # Выводим краткую сводку
        print(f"\n📊 Краткая сводка:")
        print(f"   • Общая сумма продаж: {metrics['total_sales']:,.2f} руб.")
        print(f"   • Средний чек: {metrics['avg_ticket']:,.2f} руб.")
        print(f"   • Количество заказов: {metrics['total_orders']:,}")
        print(f"   • Топ позиций: {len(metrics['top_items'])}")
        print(f"   • Сгенерировано графиков: {charts_count}")
        
    except Exception as e:
        print(f"❌ Ошибка: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
