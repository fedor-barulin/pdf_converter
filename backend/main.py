import json
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from typing import List

from logger import get_logger
from pipeline import EnterprisePipeline
from embeddings import index_chunks
from hyper_rag import update_bm25_index, hybrid_search, build_context

logger = get_logger()

app = FastAPI(title="Enterprise AI Document Ingestion Pipeline", 
              description="Мощный движок для обработки PDF/DOC/DOCX. Идеален для LLM RAG систем с поддержкой BM25 Hybrid Search.",
              version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    logger.info("Enterprise Document Ingestion Server запущен.")

def background_indexing(chunks):
    """Фоновая задача для обновления всех поисковых индексов (Vector + BM25)"""
    try:
        index_chunks(chunks)
        update_bm25_index(chunks)
        logger.info("Векторный поиск (Chroma) и Keyword поиск (BM25) обновлены.")
    except Exception as e:
        logger.error(f"Ошибка фоновой индексации: {e}")

@app.post("/api/upload")
async def upload_document(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)):
    """
    Обработка документов: OCR, удаление мусора, извлечение структуры, URL и таблиц.
    Подготовка Semantic Chunks для RAG.
    Возвращает унифицированный JSON формат.
    """
    outputs = []
    
    for file in files:
        logger.info(f"Начало обработки документа: {file.filename}")
        content = await file.read()
        filename = file.filename
        
        try:
            # Инициализация Pipeline
            pipeline = EnterprisePipeline(content, filename)
            final_json = pipeline.process()
            
            # Подготовка чанков для Векторной БД и BM25
            chunks_for_db = []
            for c in final_json["chunks"]:
                c_copy = c.copy()
                c_copy["source"] = filename
                c_copy["tags"] = [] # Метаданные теги если нужно передавать
                chunks_for_db.append(c_copy)
                
            # Добавим таблицы как отдельные чанки для Table-aware retrieval
            for t in final_json.get("tables", []):
                t_str = " | ".join(t.get("header", [])) + "\n"
                for row in t.get("rows", []):
                    t_str += " | ".join(row) + "\n"
                chunks_for_db.append({
                    "chunk_id": t.get("table_id"),
                    "source": filename,
                    "section": "Таблица",
                    "page": 1,
                    "text": t_str,
                    "tags": ["table"]
                })
                
            # Асинхронно индексируем чанки Vector + BM25
            background_tasks.add_task(background_indexing, chunks_for_db)
            
            outputs.append(final_json)
            logger.info(f"Документ {filename} успешно обработан и преобразован в Enterprise JSON.")
            
        except ValueError as ve:
            logger.warning(f"Пропуск {filename}: {str(ve)}")
            continue
        except Exception as e:
            logger.error(f"Критическая ошибка обработки {filename}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Ошибка обработки {filename}: {str(e)}")
            
    # Возвращаем ОДИН файл (если отправлен 1 документ, то возвращаем его)
    if len(outputs) == 1:
        return outputs[0]
        
    return outputs

@app.get("/api/search")
async def search_documents_rag(query: str, top_k: int = 5, source_filter: str = None, section_filter: str = None):
    """
    Enterprise Hyper-RAG Search API.
    Объединяет Vector Search + BM25 Keyword Search + Metadata filtering.
    """
    logger.info(f"Hyper-RAG search: '{query}' (top_k={top_k})")
    try:
        # 1. Metadata Filters
        filters = {}
        if source_filter: filters["source"] = source_filter
        if section_filter: filters["section"] = section_filter
        
        # 2. Hybrid Search (Vector + BM25)
        results = hybrid_search(query, top_k=top_k, filters=filters)
        
        if not results:
            return {"query": query, "message": "Result not found", "results": []}
            
        # 3. Context Building
        # Формируем готовый Prompt Context для LLM, объединяя соседние чанки и убирая дубли
        llm_context = build_context(results)
            
        return {
            "query": query, 
            "results": results, 
            "llm_context_prompt": llm_context
        }
    except Exception as e:
        logger.error(f"Hyper-RAG error: {str(e)}")
        raise HTTPException(status_code=500, detail="Search Engine Error")

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "Enterprise AI Document Pipeline"}
