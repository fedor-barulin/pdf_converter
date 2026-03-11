import pdfplumber
import pytesseract
from pdf2image import convert_from_bytes
import io
import cv2
import numpy as np
from logger import get_logger

logger = get_logger()

def extract_pdf(file_content: bytes, filename: str) -> list:
    """Извлекает текст построчно и таблицы из PDF."""
    pages_data = []
    
    try:
        with pdfplumber.open(io.BytesIO(file_content)) as pdf:
            for i, page in enumerate(pdf.pages):
                lines = []
                tables_data = []
                
                # 1. Извлечение таблиц (структурированно)
                tables = page.extract_tables()
                if tables:
                    for t_idx, table in enumerate(tables):
                        table_rows = []
                        header = []
                        for r_idx, row in enumerate(table):
                            clean_row = [str(cell).replace('\n', ' ').strip() if cell else "" for cell in row]
                            if r_idx == 0:
                                header = clean_row
                            else:
                                table_rows.append(clean_row)
                                
                        tables_data.append({
                            "table_id": f"table_p{i+1}_{t_idx+1}",
                            "header": header,
                            "rows": table_rows
                        })
                
                # Извлечение строк с координатами (позволяет определять заголовки по размеру шрифта)
                words = page.extract_words(extra_attrs=['size'])
                if words:
                    # Группируем слова в строки по y0 координате (учитывая погрешность)
                    grouped_lines = {}
                    for w in words:
                        # округляем y0 чтобы собрать слова на одной линии
                        y_key = round(w['top'] / 4) * 4 
                        if y_key not in grouped_lines:
                            grouped_lines[y_key] = []
                        grouped_lines[y_key].append(w)
                    
                    # Сортируем линии сверху вниз
                    for y_key in sorted(grouped_lines.keys()):
                        line_words = grouped_lines[y_key]
                        line_words.sort(key=lambda x: x['x0']) # Слева направо
                        
                        text = " ".join([w['text'] for w in line_words])
                        # Берем максимальный размер шрифта в строке
                        max_size = max([w['size'] for w in line_words])
                        
                        # Эвристика: если шрифт больше 12 - возможно это заголовок
                        is_heading = max_size > 12.0
                        
                        lines.append({
                            "text": text,
                            "is_heading": is_heading,
                            "size": max_size
                        })
                
                # Если текста почти нет (меньше 5 слов), запускаем OCR для всей страницы
                if len(words) < 5:
                    logger.info(f"{filename}: Скан на странице {i+1}. Запуск авто-OCR...")
                    ocr_text = extract_ocr_from_page(file_content, i)
                    for ocr_line in ocr_text.split('\n'):
                        if ocr_line.strip():
                            lines.append({
                                "text": ocr_line.strip(),
                                "is_heading": False, # Сложно определить без анализа bbox в tesseract
                                "size": 11.0
                            })
                            
                pages_data.append({
                    "page": i + 1,
                    "lines": lines,
                    "tables": tables_data,
                    "source": filename
                })
    except Exception as e:
        logger.error(f"Ошибка парсинга PDF ({filename}): {e}")
        raise
            
    return pages_data

def extract_ocr_from_page(pdf_bytes: bytes, page_num: int) -> str:
    """Распознавание текста со скана (фото) с применением OpenCV."""
    try:
        images = convert_from_bytes(
            pdf_bytes, 
            first_page=page_num+1, 
            last_page=page_num+1, 
            dpi=300
        )
        if not images:
            return ""
            
        img = images[0]
        open_cv_image = np.array(img) 
        
        if len(open_cv_image.shape) == 3:
            open_cv_image = open_cv_image[:, :, ::-1].copy() 
            gray = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)
        else:
            gray = open_cv_image
            
        gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
        
        # Запускаем psm 3 (Fully automatic page segmentation) или 6 (Assume a single uniform block of text)
        text = pytesseract.image_to_string(gray, lang="rus+eng", config='--psm 3')
        return text.strip()
    except Exception as e:
        logger.error(f"Ошибка при OCR на странице {page_num+1}: {e}")
        return ""
