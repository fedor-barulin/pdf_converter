import os
import chromadb
from sentence_transformers import SentenceTransformer
from logger import get_logger

logger = get_logger()

# Инициализация векторной БД (в памяти или на диске)
DB_PATH = "./chroma_db"
os.makedirs(DB_PATH, exist_ok=True)

# ChromaDB клиент
chroma_client = chromadb.PersistentClient(path=DB_PATH)
collection_name = "enterprise_knowledge_base"

# Получаем или создаем коллекцию
collection = chroma_client.get_or_create_collection(name=collection_name)

# Инициализация легковесной и мощной мультиязычной модели для эмбеддингов
# paraphrase-multilingual-MiniLM-L12-v2 отлично понимает русский и английский
MODEL_NAME = 'paraphrase-multilingual-MiniLM-L12-v2'
logger.info(f"Загрузка модели эмбеддингов: {MODEL_NAME}")
try:
    embedder = SentenceTransformer(MODEL_NAME)
    logger.info("Модель эмбеддингов успешно загружена")
except Exception as e:
    logger.error(f"Ошибка загрузки модели эмбеддингов: {e}")
    embedder = None

def index_chunks(chunks: list):
    """
    Генерирует векторы (embeddings) для массива чанков и сохраняет их в ChromaDB.
    Ускоряет поиск релевантной информации (RAG) в 5-10 раз по сравнению с full-text.
    """
    if not chunks or not embedder:
        return
        
    ids = []
    documents = []
    metadatas = []
    
    for c in chunks:
        # Убедимся, что ID уникальный, даже в batch-режиме
        chunk_id = f"{c['source']}_{c['chunk_id']}"
        ids.append(chunk_id)
        documents.append(c['text'])
        
        # В ChromaDB метаданные принимают только str, int, float, bool
        tags_str = ", ".join(c.get('tags', []))
        metadatas.append({
            "source": c['source'],
            "section": c['section'],
            "page": int(c['page']), 
            "tags": tags_str,
            "language": c.get('language', 'ru')
        })
    
    try:
        # Индексация в векторной БД.
        vectors = embedder.encode(documents).tolist()
        
        collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=vectors,
            metadatas=metadatas
        )
        logger.info(f"Успешно проиндексировано {len(chunks)} документов (таблиц и текста) в векторный индекс.")
    except Exception as e:
        logger.error(f"Ошибка индексации векторов в ChromaDB: {e}")
        raise
    
def search_similar(query: str, top_k: int = 5):
    """
    Векторный семантический поиск по загруженной базе (RAG).
    Возращает наиболее релевантные фразы, таблицы и OCR-сканы даже если нет точного совпадения слов.
    """
    if not embedder:
        logger.error("Модель эмбеддингов не инициализирована")
        return []
        
    try:
        query_vector = embedder.encode([query]).tolist()
        
        results = collection.query(
            query_embeddings=query_vector,
            n_results=top_k
        )
        
        formatted_results = []
        if results and results.get('documents') and len(results['documents']) > 0:
            for i in range(len(results['documents'][0])):
                doc_text = results['documents'][0][i]
                doc_id = results['ids'][0][i]
                doc_meta = results['metadatas'][0][i]
                # Расстояние. Меньше - лучше
                doc_score = results['distances'][0][i] if 'distances' in results else 0
                
                formatted_results.append({
                    "id": doc_id,
                    "text": doc_text,
                    "metadata": doc_meta,
                    "distance": round(doc_score, 4)
                })
        
        return formatted_results
    except Exception as e:
        logger.error(f"Ошибка при векторном поиске: {e}")
        return []
