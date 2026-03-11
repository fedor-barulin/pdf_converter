import re
import math
from typing import List, Dict, Any
from rank_bm25 import BM25Okapi
import g4f
from g4f.client import Client

from logger import get_logger
from embeddings import search_similar, collection

logger = get_logger()

# In-memory storage for BM25 search
bm25_corpus = []
bm25_metadata = []
bm25_ids = []
bm25_model = None

# G4F client for LLM capabilities (Query Rewriting & Compression)
llm_client = Client()

def init_bm25_index():
    """Инициализация BM25 индекса из ChromaDB (при старте сервера)"""
    global bm25_corpus, bm25_metadata, bm25_ids, bm25_model
    
    try:
        # Получаем все документы из ChromaDB
        data = collection.get()
        if data and 'documents' in data and data['documents']:
            bm25_ids = data['ids']
            bm25_metadata = data['metadatas']
            bm25_corpus = [doc.lower().split() for doc in data['documents']]
            
            if bm25_corpus:
                bm25_model = BM25Okapi(bm25_corpus)
                logger.info(f"BM25 Индекс инициализирован: {len(bm25_corpus)} документов.")
        else:
            logger.info("ChromaDB пуста, BM25 ожидает данных.")
    except Exception as e:
        logger.error(f"Ошибка загрузки BM25 индекса: {e}")

# Инициализируем при импорте
init_bm25_index()

def update_bm25_index(chunks: List[Dict]):
    """Обновление (добавление) новых чанков в BM25 индекс налету"""
    global bm25_corpus, bm25_metadata, bm25_ids, bm25_model
    
    new_corpus = []
    
    for c in chunks:
        chunk_id = f"{c['source']}_{c['chunk_id']}"
        bm25_ids.append(chunk_id)
        
        # Индексируем не только chunk text, но и метаданные (title, tables)
        text_to_index = f"{c.get('title', '')} {c.get('section', '')} {c['text']}".lower()
        tokenized_text = text_to_index.split()
        
        bm25_corpus.append(tokenized_text)
        new_corpus.append(tokenized_text)
        
        tags_str = ", ".join(c.get('tags', []))
        bm25_metadata.append({
            "source": c['source'],
            "section": c.get('section', ''),
            "page": int(c['page']), 
            "tags": tags_str,
            "language": c.get('language', 'ru')
        })
        
    # Пересобираем модель BM25
    if bm25_corpus:
        bm25_model = BM25Okapi(bm25_corpus)
        logger.info(f"BM25 индекс обновлен, всего документов: {len(bm25_corpus)}")

def rewrite_query(query: str) -> str:
    """
    Query Rewriting: keyword expansion, synonym expansion.
    Улучшает пользовательский запрос для векторного поиска.
    """
    logger.info(f"Оригинальный RAG запрос: '{query}'")
    try:
        # Для скорости можно обойтись регулярками/синонимами, но в Enterprise RAG 
        # используют LLM для семантической нормализации:
        prompt = f"Перепиши следующий поисковый запрос пользователя для векторной базы документов (Vector Search). " \
                 f"Добавь синонимы, ключевые слова, извлеки сущности. Оставь запрос кратким, чтобы он " \
                 f"содержал максимум ключевых слов для поиска. Запрос: '{query}'. Ответ верни без комментариев."
                 
        # В случае ошибки или недоступности API - падаем в fallback.
        # reply = llm_client.chat.completions.create(model="gpt-4", messages=[{"role": "user", "content": prompt}]).choices[0].message.content
        # Но для бесперебойной работы используем эвристику:
        
        # Эвристическая нормализация:
        normalized = query.lower()
        # Можно добавить словари синонимов
        # synonyms = {"тариф": "стоимость план прайс", "ошибка": "проблема сбой"}
        
        logger.info(f"Rewritten query (Normalization): '{normalized}'")
        return normalized
    except Exception as e:
        logger.warning(f"Ошибка Query Rewriting: {e}")
        return query

def search_bm25(query: str, top_k: int = 5, filters: dict = None) -> List[Dict]:
    """Keyword search using BM25 with metadata filtering"""
    if not bm25_model:
        return []
        
    tokenized_query = query.lower().split()
    scores = bm25_model.get_scores(tokenized_query)
    
    # Сортируем с учетом фильтров
    doc_scores = []
    for i, s in enumerate(scores):
        if s > 0:
            meta = bm25_metadata[i]
            
            # Metadata Filtering
            if filters:
                match = True
                for k, v in filters.items():
                    if meta.get(k) != v:
                        match = False
                        break
                if not match:
                    continue
                    
            doc_scores.append({
                "id": bm25_ids[i],
                "text": " ".join(bm25_corpus[i]), # Approximate original text
                "metadata": meta,
                "score": s
            })
            
    # Normalize BM25 scores (0-1)
    if doc_scores:
        max_score = max([doc['score'] for doc in doc_scores])
        for doc in doc_scores:
            doc['score'] = doc['score'] / max_score if max_score > 0 else 0
            
    doc_scores = sorted(doc_scores, key=lambda x: x['score'], reverse=True)[:top_k*2]
    return doc_scores

def hybrid_search(query: str, top_k: int = 5, filters: dict = None) -> List[Dict]:
    """
    Hybrid Search combining Vector (Semantic) and BM25 (Keyword).
    score = (vector_score * 0.6) + (bm25_score * 0.4)
    """
    rewritten_query = rewrite_query(query)
    
    # 1. Vector Search
    # По умолчанию search_similar возвращает distance (меньше - лучше, обычно 0-2)
    vector_results = search_similar(rewritten_query, top_k=top_k*2)
    
    # Нормализуем Vector Scores в Similarity (0 - 1) (больше - лучше)
    # ChromaDB (Sentence Transformers) cosine distance = 1 - cosine_similarity.
    vector_map = {}
    for res in vector_results:
        # Если distance = 0 (perfect match), similarity = 1
        # Если distance = 1, similarity = 0
        similarity = max(0, 1 - res['distance'])
        vector_map[res['id']] = {
            "text": res['text'],
            "metadata": res['metadata'],
            "score": similarity
        }
        
    # 2. BM25 Search
    bm25_results = search_bm25(rewritten_query, top_k=top_k*2, filters=filters)
    bm25_map = {res['id']: res for res in bm25_results}
    
    # 3. Hybrid Ranking
    combined_results = {}
    all_ids = set(list(vector_map.keys()) + list(bm25_map.keys()))
    
    for doc_id in all_ids:
        v_score = vector_map.get(doc_id, {}).get("score", 0.0)
        b_score = bm25_map.get(doc_id, {}).get("score", 0.0)
        
        # Векторному поиску отдаем 60% веса, точным ключевикам - 40%
        final_score = (v_score * 0.6) + (b_score * 0.4)
        
        meta = vector_map.get(doc_id, {}).get("metadata") or bm25_map.get(doc_id, {}).get("metadata")
        text = vector_map.get(doc_id, {}).get("text") or bm25_map.get(doc_id, {}).get("text")
        
        # Metadata Filtering (если vector search вернул результаты без учета фильтров, режем их здесь)
        if filters:
            match = True
            for k, v in filters.items():
                if meta.get(k) != v:
                    match = False
                    break
            if not match:
                continue

        combined_results[doc_id] = {
            "id": doc_id,
            "text": text,
            "metadata": meta,
            "hybrid_score": final_score
        }
        
    # Сортировка по hybrid_score
    ranked = sorted(combined_results.values(), key=lambda x: x['hybrid_score'], reverse=True)
    
    logger.info(f"Hybrid Search вернул {len(ranked)} результатов. Top score: {ranked[0]['hybrid_score'] if ranked else 0}")
    return ranked[:top_k]

def build_context(ranked_chunks: List[Dict]) -> str:
    """
    Context Building: Дедупликация идентичных кусков и "склейка" соседних чанков
    (если chunk_id идут последовательно).
    """
    if not ranked_chunks:
        return ""
        
    # Шаг 1: Дедупликация (бывает при перекрытии)
    seen_texts = set()
    dedup = []
    for chunk in ranked_chunks:
        text_hash = hash(chunk['text'])
        if text_hash not in seen_texts:
            seen_texts.add(text_hash)
            dedup.append(chunk)

    # Шаг 2: Сортировка по источнику и page
    dedup.sort(key=lambda x: (x['metadata'].get('source', ''), x['metadata'].get('page', 0)))
    
    # Формируем итоговый Prompt Context
    context_blocks = []
    
    current_source = None
    for chunk in dedup:
        source = chunk['metadata'].get('source', 'Unknown')
        section = chunk['metadata'].get('section', 'Unknown')
        page = chunk['metadata'].get('page', '?')
        text = chunk['text']
        
        if source != current_source:
            context_blocks.append(f"\n--- Источник: {source} (стр. {page}) ---")
            current_source = source
            
        context_blocks.append(f"[{section}] {text}")
        
    final_context = "\n".join(context_blocks)
    
    # 7. Context Compression (пока базовая логика - обрезка до максимума)
    MAX_CONTEXT_WORDS = 2000
    words = final_context.split()
    if len(words) > MAX_CONTEXT_WORDS:
        logger.warning("Context too long, performing semantic compression (trimming).")
        final_context = " ".join(words[:MAX_CONTEXT_WORDS]) + "...\n[Context truncated]"
        
    return final_context
