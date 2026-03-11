import re
from collections import defaultdict
from logger import get_logger

logger = get_logger()

class DocumentCleaner:
    def __init__(self, pages_data):
        self.pages_data = pages_data
        self.total_pages = len(pages_data)
        self.header_footer_lines = set()
        self.extracted_urls = set()
        
    def find_headers_footers(self):
        """Алгоритм поиска сквозных элементов (на >60% страниц)"""
        if self.total_pages < 2:
            return
            
        line_freq = defaultdict(int)
        for page in self.pages_data:
            saw_on_page = set()
            for line in page.get("lines", []):
                text = line.get("text", "").strip()
                if len(text) > 3 and text not in saw_on_page: # Игнорируем слишком короткие
                    line_freq[text] += 1
                    saw_on_page.add(text)
                    
        threshold = self.total_pages * 0.6
        for line_text, count in line_freq.items():
            if count >= threshold:
                self.header_footer_lines.add(line_text)
                
    def extract_url(self, text: str) -> str:
        """Поиск http/https URL в тексте"""
        urls = re.findall(r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[^\s]*', text)
        for url in urls:
            self.extracted_urls.add(url)
            
    def is_noise(self, text: str) -> bool:
        """Регулярки для системного мусора."""
        if text in self.header_footer_lines:
            return True
            
        # Время выгрузки: 12:45 21.03.2024
        if re.match(r'(?i).*(?:выгрузки|сформирован).*?\b\d{2}:\d{2}.*\d{2}\.\d{2}\.\d{4}', text):
            return True
            
        # Сформировано пользователем Иванов И.И.
        if re.match(r'(?i).*сформировано\s+пользователем.*', text):
            return True
            
        # Страница 2 из 15
        if re.match(r'(?i)^\s*стр(?:аница|\.?)\s*\d+\s*(?:из\s*\d+)?\s*$', text):
            return True
            
        # Watermarks (простые примеры)
        if re.search(r'(?i)документ\s+предоставлен\s+коммерческая\s+тайна', text):
            return True
            
        return False
        
    def clean(self):
        """Очищает страницы документа."""
        self.find_headers_footers()
        
        # Сначала ищем URL в header/footer
        for hf_text in self.header_footer_lines:
            self.extract_url(hf_text)
            
        cleaned_pages = []
        removed_lines_count = 0
        
        for page in self.pages_data:
            clean_lines = []
            
            for line_obj in page.get("lines", []):
                text = line_obj.get("text", "").strip()
                
                if not text:
                    continue
                    
                if self.is_noise(text):
                    removed_lines_count += 1
                    continue
                    
                # Ищем URL во всем документе (fallback)
                self.extract_url(text)
                
                clean_lines.append(line_obj)
                
            page["lines"] = clean_lines
            cleaned_pages.append(page)
            
        logger.info(f"Очистка: удалено {removed_lines_count} служебных строк (мусор).")
        
        best_url = list(self.extracted_urls)[0] if self.extracted_urls else ""
        return cleaned_pages, best_url
