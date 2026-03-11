import os
from logger import get_logger
from pdf_parser import extract_pdf
from docx_parser import extract_docx
from cleaner import DocumentCleaner
from structure import DocumentStructurer
from chunker import chunk_text
from metadata import extract_metadata

logger = get_logger()

class EnterprisePipeline:
    def __init__(self, file_content: bytes, filename: str):
        self.file_content = file_content
        self.filename = filename
        self.ext = os.path.splitext(filename)[1].lower()
        
    def process(self):
        """Полный цикл обработки документа."""
        logger.info(f"Запуск Enterprise Pipeline для {self.filename}")
        
        # 1. Извлечение парсером (с таблицами и OCR при необходимости)
        if self.ext == '.pdf':
            pages_data = extract_pdf(self.file_content, self.filename)
        elif self.ext in ['.docx', '.doc']:
            # Временно сохраняем для docx парсера, так как он принимает путь
            temp_path = f"temp_{self.filename}"
            with open(temp_path, "wb") as f:
                f.write(self.file_content)
            try:
                pages_data = extract_docx(temp_path)
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        else:
            raise ValueError(f"Неподдерживаемый формат: {self.ext}")
            
        # Сбор страниц и таблиц
        total_pages = len(pages_data)
        all_tables = []
        for p in pages_data:
            all_tables.extend(p.get("tables", []))
            
        logger.info(f"Найдено таблиц: {len(all_tables)}.")

        # 2. Очистка и удаление мусора
        cleaner = DocumentCleaner(pages_data)
        cleaned_pages, article_url = cleaner.clean()
        
        # 3. Построение дерева структуры
        structurer = DocumentStructurer(cleaned_pages)
        sections = structurer.build_structure()
        
        # Полный очищенный текст (content)
        full_content = "\n\n".join(s["heading"] + "\n" + s["text"] for s in sections)
        
        # Извлечение языка через метаданные NLP
        lang_meta = "ru" # default
        try:
            meta = extract_metadata(full_content)
            lang_meta = meta.get("language", "ru")
        except Exception as e:
            logger.warning(f"Ошибка извлечения сложных метаданных. {e}")
            
        # 4. Semantic Chunking
        chunks = chunk_text(sections, chunk_size_words=500, chunk_overlap=100)
        
        # 5. Сбор финального JSON
        final_json = {
            "title": os.path.splitext(self.filename)[0],
            "article_url": article_url,
            "content": full_content,
            "sections": sections,
            "tables": all_tables,
            "chunks": chunks,
            "metadata": {
                "source_file": self.filename,
                "pages": total_pages,
                "language": lang_meta,
                "table_count": len(all_tables),
                "chunk_count": len(chunks)
            }
        }
        
        logger.info(f"[{self.filename}] Итоговое Логирование:")
        logger.info(f"Найденный URL статьи: {article_url if article_url else 'Не найден'}")
        logger.info(f"Количество semantic chunks: {len(chunks)}")
        logger.info(f"Количество извлеченных таблиц: {len(all_tables)}")
        
        return final_json
