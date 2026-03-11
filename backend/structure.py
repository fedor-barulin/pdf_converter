import re
from logger import get_logger

logger = get_logger()

class DocumentStructurer:
    def __init__(self, cleaned_pages):
        self.cleaned_pages = cleaned_pages
        self.sections = []
        self.seen_paragraphs = set()
        
    def build_structure(self):
        """
        Строит иерархическое дерево: разделы, параграфы, нормализует текст.
        Удаляет дубликаты строк и параграфов.
        """
        current_section_title = "Document Start"
        current_section = {
            "heading": current_section_title,
            "text": "",
            "page": 1
        }
        
        for p_data in self.cleaned_pages:
            page_num = p_data.get("page", 1)
            
            # Собираем параграфы текущей страницы
            for line_obj in p_data.get("lines", []):
                text = line_obj["text"]
                is_heading = line_obj.get("is_heading", False)
                
                if not text: 
                    continue
                    
                # Дедупликация (Deduplication)
                if text in self.seen_paragraphs:
                    continue
                self.seen_paragraphs.add(text)
                
                # Если это заголовок -> новый раздел
                if is_heading and len(text.split()) < 15: # Заголовок не может быть слишком длинным
                    if current_section["text"].strip():
                        # Нормализация текста (объединение broken sentences)
                        current_section["text"] = self.normalize_text(current_section["text"])
                        self.sections.append(current_section)
                        
                    current_section_title = text
                    current_section = {
                        "heading": current_section_title,
                        "text": "",
                        "page": page_num
                    }
                else:
                    current_section["text"] += text + "\n"
                    
        # Добавляем последний раздел
        if current_section["text"].strip():
            current_section["text"] = self.normalize_text(current_section["text"])
            self.sections.append(current_section)
            
        logger.info(f"Структура: найдено {len(self.sections)} логических разделов.")
        return self.sections
        
    def normalize_text(self, text: str) -> str:
        """Очистка и исправление текста: объединение broken sentences, удаление лишних переносов"""
        # Убираем лишние пробелы
        text = re.sub(r'[ \t]+', ' ', text)
        
        # Исправление OCR артефактов (например, замена случайных символов - базовая эвристика)
        text = text.replace(' | ', ' I ')
        
        # Объединение broken sentences. Если строка кончается не точкой, а следующая 
        # начинается с маленькой буквы -> это одно предложение.
        lines = text.split('\n')
        normalized = []
        for line in lines:
            line = line.strip()
            if not line: continue
            
            if normalized and not normalized[-1].endswith(('.','!','?',':',';')) and line[0].islower():
                normalized[-1] += " " + line
            else:
                normalized.append(line)
        
        # Отступы оставляем по абзацам
        return "\n\n".join(normalized)
