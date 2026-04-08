"""
Parser модуль для чтения PDF и DOCX документов.
Читает файлы из data/sources/ и возвращает структурированные данные.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any
import pdfplumber
from docx import Document

logger = logging.getLogger(__name__)


def parse_sources(sources_dir: Path = None) -> List[Dict[str, Any]]:
    """
    Парсинг всех документов из папки sources.
    
    Args:
        sources_dir: Путь к папке с источниками. По умолчанию data/sources/
    
    Returns:
        Список документов: [{"filename": ..., "text": ..., "pages": ...}]
    """
    if sources_dir is None:
        sources_dir = Path("data/sources")
    
    if not sources_dir.exists():
        logger.warning(f"Папка источников не найдена: {sources_dir}")
        return []
    
    documents = []
    
    # Парсим PDF
    for pdf_file in sources_dir.glob("*.pdf"):
        logger.info(f"Парсинг PDF: {pdf_file.name}")
        doc = parse_pdf(pdf_file)
        if doc:
            documents.append(doc)
    
    # Парсим DOCX
    for docx_file in sources_dir.glob("*.docx"):
        logger.info(f"Парсинг DOCX: {docx_file.name}")
        doc = parse_docx(docx_file)
        if doc:
            documents.append(doc)
    
    logger.info(f"Всего документов распарсено: {len(documents)}")
    return documents


def parse_pdf(pdf_path: Path) -> Dict[str, Any]:
    """
    Парсинг PDF через pdfplumber.
    
    Args:
        pdf_path: Путь к PDF файлу
    
    Returns:
        {"filename": ..., "text": ..., "pages": ..., "format": "pdf"}
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages_text = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages_text.append(text.strip())
            
            full_text = "\n\n".join(pages_text)
            
            return {
                "filename": pdf_path.name,
                "text": full_text,
                "pages": len(pdf.pages),
                "format": "pdf",
                "path": str(pdf_path)
            }
    except Exception as e:
        logger.error(f"Ошибка при парсинге PDF {pdf_path.name}: {e}")
        return None


def parse_docx(docx_path: Path) -> Dict[str, Any]:
    """
    Парсинг DOCX через python-docx.
    
    Args:
        docx_path: Путь к DOCX файлу
    
    Returns:
        {"filename": ..., "text": ..., "pages": ..., "format": "docx"}
    """
    try:
        doc = Document(docx_path)
        paragraphs = []
        
        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                paragraphs.append(text)
        
        full_text = "\n\n".join(paragraphs)
        
        # Примерная оценка количества страниц (по количеству параграфов / 20)
        estimated_pages = max(1, len(paragraphs) // 20)
        
        return {
            "filename": docx_path.name,
            "text": full_text,
            "pages": estimated_pages,
            "format": "docx",
            "path": str(docx_path)
        }
    except Exception as e:
        logger.error(f"Ошибка при парсинге DOCX {docx_path.name}: {e}")
        return None


def parse_single_file(file_path: Path) -> Dict[str, Any]:
    """
    Парсинг одного файла (PDF или DOCX).
    
    Args:
        file_path: Путь к файлу
    
    Returns:
        Документ или None
    """
    suffix = file_path.suffix.lower()
    
    if suffix == ".pdf":
        return parse_pdf(file_path)
    elif suffix == ".docx":
        return parse_docx(file_path)
    else:
        logger.warning(f"Неподдерживаемый формат: {suffix}")
        return None
