"""
Модуль для генерации PDF отчётов.
"""
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS
import os
from typing import Dict


def build_pdf(context: Dict, output_pdf: str) -> None:
    """
    Создаёт PDF отчёт на основе HTML шаблона.
    
    Args:
        context: Словарь с данными для шаблона
        output_pdf: Путь для сохранения PDF файла
        
    Raises:
        Exception: При ошибках генерации PDF
    """
    try:
        # Получаем абсолютный путь к проекту для base_url
        project_root = os.path.dirname(os.path.abspath(__file__))
        
        # Настраиваем Jinja2
        template_dir = os.path.join(project_root, 'templates')
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template('report.html')
        
        # Рендерим HTML
        html_content = template.render(**context)
        
        # Пути к CSS и изображениям
        css_path = os.path.join(template_dir, 'styles.css')
        weasyprint_css_path = os.path.join(template_dir, 'weasyprint.css')
        
        # Создаём PDF
        html_doc = HTML(string=html_content, base_url=project_root)
        css_doc = CSS(filename=css_path)
        weasyprint_css_doc = CSS(filename=weasyprint_css_path)
        
        # Создаём директорию для выходного файла если её нет
        os.makedirs(os.path.dirname(output_pdf), exist_ok=True)
        
        # Генерируем PDF
        html_doc.write_pdf(
            target=output_pdf,
            stylesheets=[css_doc, weasyprint_css_doc]
        )
        
        print(f"PDF отчёт сохранён: {output_pdf}")
        
    except Exception as e:
        raise Exception(f"Ошибка при создании PDF: {str(e)}")
