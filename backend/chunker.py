from logger import get_logger

logger = get_logger()

def chunk_text(sections, chunk_size_words=500, chunk_overlap=100):
    """
    Интеллектуальный semantic chunking.
    Уважает границы параграфов и секций.
    """
    chunks = []
    chunk_id = 1
    
    for sec in sections:
        heading = sec.get("heading", "Общая информация")
        text = sec.get("text", "")
        page_num = sec.get("page", 1)
        
        paragraphs = text.split("\n\n")
        current_chunk_words = []
        
        for p in paragraphs:
            words = p.split()
            if not words: continue
            
            # Если сложение параграфа с текущим чанком превысит лимит
            if len(current_chunk_words) + len(words) > chunk_size_words and current_chunk_words:
                chunk_text_str = " ".join(current_chunk_words)
                chunks.append({
                    "chunk_id": chunk_id,
                    "section": heading,
                    "page": page_num,
                    "text": chunk_text_str
                })
                chunk_id += 1
                
                overlap_words = current_chunk_words[-chunk_overlap:] if chunk_overlap > 0 else []
                current_chunk_words = overlap_words + words
            else:
                current_chunk_words.extend(words)
                
            # Если один параграф больше лимита
            while len(current_chunk_words) >= chunk_size_words:
                chunk_part = current_chunk_words[:chunk_size_words]
                chunk_text_str = " ".join(chunk_part)
                chunks.append({
                    "chunk_id": chunk_id,
                    "section": heading,
                    "page": page_num,
                    "text": chunk_text_str
                })
                chunk_id += 1
                current_chunk_words = current_chunk_words[chunk_size_words - chunk_overlap:]
                
        # Остаток
        if len(current_chunk_words) > 10: # Игнорируем слишком мелкий
            chunk_text_str = " ".join(current_chunk_words)
            chunks.append({
                "chunk_id": chunk_id,
                "section": heading,
                "page": page_num,
                "text": chunk_text_str
            })
            chunk_id += 1
            
    logger.info(f"Chunking: создано {len(chunks)} LLM semantic chunks.")
    return chunks
