import re
from langdetect import detect

def extract_metadata(text: str) -> dict:
    """
    Извлекает метаданные: язык (поддержка русского), команды USSD, 
    технические параметры, теги.
    """
    tags = []
    
    # Автоопределение языка
    try:
        lang = detect(text)
    except:
        lang = "ru" # По умолчанию
        
    # Команды USSD / SMS (например, *100#, *123*4#)
    if re.search(r'\*\d{3}(?:\*\d+)*#', text):
        tags.append("ussd")
        
    # Определение технических параметров
    lower_text = text.lower()
    
    if "apn" in lower_text or "точка доступа" in lower_text:
        tags.append("apn")
        
    if re.search(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', text):
        tags.append("ip_address")
        
    if "интернет" in lower_text:
        tags.append("internet")
    if "активация" in lower_text or "подключение" in lower_text:
        tags.append("activation")
        
    return {
        "language": lang,
        "tags": list(set(tags))  # Только уникальные теги
    }
