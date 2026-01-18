#!/usr/bin/env python3
"""
Streamlit веб-интерфейс для генерации аналитических отчётов.
Запуск: streamlit run streamlit_app.py
"""
import streamlit as st
import pandas as pd
import os
import tempfile
from datetime import datetime
from io import BytesIO

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


# Настройка страницы
st.set_page_config(
    page_title="Генератор аналитических отчётов",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Кастомные стили
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #2E86AB;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 4px solid #A23B72;
        margin-bottom: 1rem;
    }
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .stDownloadButton > button {
        width: 100%;
        background-color: #2E86AB;
        color: white;
    }
</style>
""", unsafe_allow_html=True)


def load_data(uploaded_file) -> pd.DataFrame:
    """Загружает данные из загруженного файла."""
    # Определяем расширение файла
    file_ext = os.path.splitext(uploaded_file.name)[1].lower()
    
    if file_ext == '.csv':
        # Пробуем разные кодировки
        for encoding in ['utf-8', 'cp1251', 'latin-1']:
            try:
                uploaded_file.seek(0)  # Сбрасываем позицию чтения
                df = pd.read_csv(uploaded_file, encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError("Не удалось определить кодировку файла")
    elif file_ext == '.json':
        df = pd.read_json(uploaded_file)
    else:
        raise ValueError(f"Неподдерживаемый формат: {file_ext}")
    
    # Пытаемся преобразовать колонки с числами, записанными как строки
    for col in df.columns:
        if df[col].dtype == 'object':
            try:
                # Пробуем преобразовать в числа
                numeric_col = pd.to_numeric(df[col].astype(str).str.replace(',', '.').str.strip(), errors='coerce')
                # Если больше 50% значений успешно преобразовались — применяем
                if numeric_col.notna().sum() / len(df) > 0.5:
                    df[col] = numeric_col
            except:
                pass
    
    return df


def generate_charts(df: pd.DataFrame, date_col: str, amount_col: str, metrics: dict, temp_dir: str) -> dict:
    """Генерирует все графики и возвращает пути к ним."""
    charts = {}
    
    # 1. График динамики продаж
    if not metrics['time_series'].empty:
        path = os.path.join(temp_dir, 'timeseries.png')
        charts['timeseries_png'] = plot_time_series(metrics['time_series'], path)
    
    # 2. График топ позиций
    if not metrics['top_items'].empty:
        path = os.path.join(temp_dir, 'top_items.png')
        charts['top_items_png'] = plot_top_items(metrics['top_items'], path)
    
    # 3. График количества записей по дате
    if date_col:
        path = os.path.join(temp_dir, 'daily_count.png')
        result = plot_daily_count(df, date_col, path)
        if result:
            charts['daily_count_png'] = result
    
    # 4. График месячных продаж
    if date_col and amount_col:
        path = os.path.join(temp_dir, 'monthly_sales.png')
        result = plot_monthly_sales(df, date_col, amount_col, path)
        if result:
            charts['monthly_sales_png'] = result
    
    # 5. График накопленных продаж
    if date_col and amount_col:
        path = os.path.join(temp_dir, 'cumulative.png')
        result = plot_cumulative_sales(df, date_col, amount_col, path)
        if result:
            charts['cumulative_png'] = result
    
    # 6. Гистограмма распределения
    if amount_col:
        path = os.path.join(temp_dir, 'distribution.png')
        result = plot_distribution(df, amount_col, path)
        if result:
            charts['distribution_png'] = result
    
    return charts


def main():
    # Заголовок
    st.markdown('<p class="main-header">📊 Генератор аналитических отчётов</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Загрузите данные и получите готовый PDF-отчёт и PowerPoint-презентацию</p>', unsafe_allow_html=True)
    
    # Боковая панель с настройками
    with st.sidebar:
        st.header("⚙️ Настройки")
        
        # Загрузка файла
        st.subheader("📁 Загрузка данных")
        uploaded_file = st.file_uploader(
            "Выберите CSV или JSON файл",
            type=['csv', 'json'],
            help="Поддерживаются файлы CSV и JSON с табличными данными"
        )
        
        # Настройки отчёта
        st.subheader("📝 Параметры отчёта")
        report_title = st.text_input(
            "Заголовок отчёта",
            value="Аналитический отчёт",
            help="Заголовок, который появится в PDF и PPTX"
        )
        
        top_n = st.slider(
            "Количество топ позиций",
            min_value=3,
            max_value=20,
            value=5,
            help="Сколько позиций показывать в топе"
        )
    
    # Основная область
    if uploaded_file is not None:
        try:
            # Загружаем данные
            df = load_data(uploaded_file)
            
            # Показываем информацию о данных
            st.success(f"✅ Загружено {len(df)} записей из файла **{uploaded_file.name}**")
            
            # Определяем числовые колонки
            numeric_cols = df.select_dtypes(include=['int64', 'float64', 'int32', 'float32']).columns.tolist()
            
            # Информация о найденных колонках
            if numeric_cols:
                st.info(f"🔢 Найдены числовые колонки: **{', '.join(numeric_cols)}**")
            else:
                st.warning("⚠️ Числовые колонки не обнаружены автоматически. Выберите колонку вручную.")
            
            # Автоопределение колонки с датами
            def detect_date_column(dataframe):
                """Определяет колонку с датами."""
                date_keywords = ['date', 'дата', 'datetime', 'time', 'timestamp', 'day', 'month', 'year']
                
                # Сначала ищем по ключевым словам в названии
                for col in dataframe.columns:
                    col_lower = col.lower()
                    for keyword in date_keywords:
                        if keyword in col_lower:
                            # Проверяем, можно ли преобразовать в дату
                            try:
                                test = pd.to_datetime(dataframe[col].head(10), errors='coerce')
                                if test.notna().sum() > 5:
                                    return col
                            except:
                                pass
                
                # Пробуем каждую колонку типа object
                for col in dataframe.columns:
                    if dataframe[col].dtype == 'object':
                        try:
                            test = pd.to_datetime(dataframe[col].head(20), errors='coerce')
                            if test.notna().sum() > 10:
                                return col
                        except:
                            pass
                
                return None
            
            detected_date_col = detect_date_column(df)
            
            # Две колонки для настроек колонок
            col1, col2 = st.columns(2)
            
            with col1:
                # Выбор колонки с датами
                date_options = ['(не выбрано)'] + df.columns.tolist()
                
                # Определяем индекс по умолчанию
                if detected_date_col and detected_date_col in df.columns.tolist():
                    default_date_idx = date_options.index(detected_date_col)
                    st.success(f"🗓️ Автоопределена колонка с датами: **{detected_date_col}**")
                else:
                    default_date_idx = 0
                
                date_col_selected = st.selectbox(
                    "📅 Колонка с датами",
                    options=date_options,
                    index=default_date_idx,
                    help="Выберите колонку, содержащую даты для построения временных графиков."
                )
                date_col = None if date_col_selected == '(не выбрано)' else date_col_selected
            
            with col2:
                # Выбор колонки с суммами — показываем все колонки
                all_columns = df.columns.tolist()
                # Если есть числовые — ставим первую по умолчанию
                default_idx = 0
                if numeric_cols:
                    # Приоритет: price, amount, sum, discounted_price, actual_price
                    priority_keywords = ['price', 'amount', 'sum', 'total', 'sales', 'цена', 'сумма']
                    for keyword in priority_keywords:
                        for i, col in enumerate(all_columns):
                            if keyword in col.lower() and col in numeric_cols:
                                default_idx = i
                                break
                        else:
                            continue
                        break
                    else:
                        # Если не нашли по ключевым словам — берём первую числовую
                        default_idx = all_columns.index(numeric_cols[0]) if numeric_cols[0] in all_columns else 0
                
                amount_col = st.selectbox(
                    "💰 Колонка с суммами/ценами",
                    options=all_columns,
                    index=default_idx,
                    help="Выберите колонку с числовыми значениями (суммы, цены, рейтинги)"
                )
            
            # Предпросмотр данных
            with st.expander("👁️ Предпросмотр данных", expanded=False):
                st.dataframe(df.head(10), use_container_width=True)
            
            # Информация о графиках
            charts_count = 0
            charts_list = []
            
            if date_col:
                charts_count += 4  # timeseries, daily_count, monthly_sales, cumulative
                charts_list.extend(['📈 Динамика продаж', '📊 Записи по дате', '📊 Продажи по месяцам', '📈 Накопленные продажи'])
            
            # top_items и distribution доступны всегда
            charts_count += 2
            charts_list.extend(['📊 Топ позиций', '📊 Распределение сумм'])
            
            st.info(f"📊 Будет сгенерировано **{charts_count} графиков**: {', '.join(charts_list)}")
            
            if not date_col:
                st.warning("⚠️ Без колонки дат будет создано только 2 графика. Выберите колонку с датами для полного набора!")
            
            # Кнопка генерации
            st.markdown("---")
            
            if st.button("🚀 Сгенерировать отчёты", type="primary", use_container_width=True):
                with st.spinner("⏳ Генерация отчётов..."):
                    
                    # Создаём временную директорию
                    temp_dir = tempfile.mkdtemp()
                    
                    # Приводим типы данных
                    df_processed = enforce_types(df.copy(), date_col, amount_col)
                    
                    # Вычисляем метрики
                    metrics = compute_metrics(df_processed, date_col, amount_col, top_n)
                    
                    # Генерируем графики
                    charts = generate_charts(df_processed, date_col, amount_col, metrics, temp_dir)
                    
                    # Подготавливаем контекст
                    context = {
                        'title': report_title,
                        'generated_at': datetime.now().strftime('%d.%m.%Y %H:%M'),
                        'total_sales': metrics['total_sales'],
                        'avg_ticket': metrics['avg_ticket'],
                        'total_orders': metrics['total_orders'],
                        'top_items': metrics['top_items'].to_dict('records') if not metrics['top_items'].empty else [],
                        'sample_rows': df.head(10).to_dict('records'),
                        **charts
                    }
                    
                    # Генерируем PDF
                    pdf_path = os.path.join(temp_dir, 'report.pdf')
                    build_pdf(context, pdf_path)
                    
                    # Генерируем PPTX
                    pptx_path = os.path.join(temp_dir, 'presentation.pptx')
                    build_pptx(context, pptx_path)
                    
                    # Сохраняем в session state
                    with open(pdf_path, 'rb') as f:
                        st.session_state['pdf_data'] = f.read()
                    with open(pptx_path, 'rb') as f:
                        st.session_state['pptx_data'] = f.read()
                    st.session_state['metrics'] = metrics
                    st.session_state['charts'] = charts
                    st.session_state['generated'] = True
                
                st.success("✅ Отчёты успешно сгенерированы!")
            
            # Показываем результаты если они есть
            if st.session_state.get('generated'):
                st.markdown("---")
                st.subheader("📈 Результаты анализа")
                
                # Метрики
                metrics = st.session_state['metrics']
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric(
                        label="💰 Общая сумма продаж",
                        value=f"{metrics['total_sales']:,.2f} руб."
                    )
                
                with col2:
                    st.metric(
                        label="🧾 Средний чек",
                        value=f"{metrics['avg_ticket']:,.2f} руб."
                    )
                
                with col3:
                    st.metric(
                        label="📦 Количество заказов",
                        value=f"{metrics['total_orders']:,}"
                    )
                
                # Графики
                st.subheader("📊 Графики")
                charts = st.session_state['charts']
                
                # Отображаем графики в сетке
                chart_cols = st.columns(2)
                chart_items = list(charts.items())
                
                chart_titles = {
                    'timeseries_png': 'Динамика продаж',
                    'top_items_png': 'Топ позиций',
                    'daily_count_png': 'Количество записей по дате',
                    'monthly_sales_png': 'Продажи по месяцам',
                    'cumulative_png': 'Накопленные продажи',
                    'distribution_png': 'Распределение сумм'
                }
                
                for i, (key, path) in enumerate(chart_items):
                    with chart_cols[i % 2]:
                        if path and os.path.exists(path):
                            st.image(path, caption=chart_titles.get(key, key), use_container_width=True)
                
                # Кнопки скачивания
                st.markdown("---")
                st.subheader("📥 Скачать отчёты")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.download_button(
                        label="📄 Скачать PDF отчёт",
                        data=st.session_state['pdf_data'],
                        file_name=f"{report_title.replace(' ', '_')}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
                
                with col2:
                    st.download_button(
                        label="📊 Скачать PowerPoint",
                        data=st.session_state['pptx_data'],
                        file_name=f"{report_title.replace(' ', '_')}.pptx",
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        use_container_width=True
                    )
        
        except Exception as e:
            st.error(f"❌ Ошибка: {str(e)}")
            st.info("Убедитесь, что файл имеет правильный формат и содержит табличные данные.")
    
    else:
        # Показываем инструкцию если файл не загружен
        st.info("👆 Загрузите файл с данными в боковой панели слева, чтобы начать работу.")
        
        # Пример данных
        with st.expander("📋 Пример поддерживаемого формата данных"):
            example_data = pd.DataFrame({
                'Date': ['2024-01-15', '2024-01-16', '2024-01-17'],
                'item': ['Ноутбук Dell', 'Мышь Logitech', 'Клавиатура'],
                'Amount': [45000, 2500, 3500],
                'Category': ['Электроника', 'Аксессуары', 'Аксессуары']
            })
            st.dataframe(example_data, use_container_width=True)
            st.caption("CSV файл должен содержать колонки с датами, названиями товаров и суммами.")
    
    # Футер
    st.markdown("---")
    st.markdown(
        "<p style='text-align: center; color: #666;'>Генератор аналитических отчётов | Портфолио проект</p>",
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
