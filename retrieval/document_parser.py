"""
Document Parser - парсинг DOCX, PDF, TXT файлов
Извлекает текст и метаданные для индексации
"""
import logging
import numpy as np
from pathlib import Path
from typing import List, Dict, Any
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class DocumentParser(ABC):
    """Базовый класс для парсеров документов"""
    
    @abstractmethod
    def parse(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Парсит документ и возвращает список фрагментов
        
        Returns:
            [{"text": "...", "metadata": {"source": "...", "page": ..., ...}}]
        """
        pass


class DOCXParser(DocumentParser):
    """Парсер DOCX файлов"""
    
    def parse(self, file_path: Path) -> List[Dict[str, Any]]:
        """Парсит DOCX документ по параграфам"""
        from docx import Document
        
        logger.info(f"Парсинг DOCX: {file_path.name}")
        
        try:
            doc = Document(str(file_path))
            fragments = []
            current_section = "Введение"
            
            for para in doc.paragraphs:
                text = para.text.strip()
                if not text:
                    continue
                
                # Определяем заголовки (по стилю или размеру)
                if para.style.name.startswith('Heading') or len(text) < 100:
                    # Возможно это заголовок раздела
                    if any(keyword in text.lower() for keyword in 
                           ['введение', 'расчёт', 'анализ', 'заключение', 'глава']):
                        current_section = text
                        continue
                
                fragments.append({
                    "text": text,
                    "metadata": {
                        "source": file_path.name,
                        "type": "docx",
                        "section": current_section,
                        "is_etalon": file_path.name.startswith("2603-1716")
                    }
                })
            
            logger.info(f"  DOCX: {len(fragments)} фрагментов из {file_path.name}")
            return fragments
        
        except Exception as e:
            logger.error(f"Ошибка парсинга DOCX {file_path.name}: {e}")
            return []


class PDFParser(DocumentParser):
    """Парсер PDF файлов с OCR fallback"""
    
    def parse(self, file_path: Path) -> List[Dict[str, Any]]:
        """Парсит PDF документ постранично с OCR для отсканированных PDF"""
        try:
            from PyPDF2 import PdfReader
        except ImportError:
            logger.warning("PyPDF2 не установлен, пропускаем PDF файлы")
            return []
        
        logger.info(f"Парсинг PDF: {file_path.name}")
        
        try:
            reader = PdfReader(str(file_path))
            fragments = []
            
            for page_num, page in enumerate(reader.pages, 1):
                text = page.extract_text()
                if not text or len(text.strip()) < 50:
                    continue
                
                # Разбиваем страницу на абзацы
                paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
                
                for para in paragraphs:
                    if len(para) < 30:  # Слишком короткий фрагмент
                        continue
                    
                    fragments.append({
                        "text": para,
                        "metadata": {
                            "source": file_path.name,
                            "type": "pdf",
                            "page": page_num,
                            "is_etalon": False
                        }
                    })
            
            # Если фрагментов мало - просто логируем (OCR отключён для скорости)
            if len(fragments) < 5:
                logger.warning(f"  PDF дал мало фрагментов ({len(fragments)}), пропускаем (OCR отключён)")
            
            logger.info(f"  PDF: {len(fragments)} фрагментов из {file_path.name}")
            return fragments
        
        except Exception as e:
            logger.error(f"Ошибка парсинга PDF {file_path.name}: {e}")
            # OCR отключён для скорости - просто пропускаем проблемные PDF
            return []
    
    def _parse_with_ocr(self, file_path: Path) -> List[Dict[str, Any]]:
        """Парсит PDF через OCR (EasyOCR) с кэшированием reader"""
        try:
            import easyocr
            from pdf2image import convert_from_path
        except ImportError:
            logger.warning("easyocr или pdf2image не установлены. Установите: pip install easyocr pdf2image")
            return []
        
        try:
            from config import OCR_DPI, OCR_LANGUAGES, USE_OCR_FALLBACK, POPPLER_PATH
            
            if not USE_OCR_FALLBACK:
                return []
            
            # Используем глобальный кэш для EasyOCR reader (инициализация ~30 сек)
            global _ocr_reader
            if '_ocr_reader' not in globals() or _ocr_reader is None:
                logger.info(f"Инициализация EasyOCR (языки: {OCR_LANGUAGES})... (может занять ~30 сек)")
                _ocr_reader = easyocr.Reader(OCR_LANGUAGES, gpu=False, verbose=False)
            
            # Конвертируем PDF в изображения (с указанием пути к Poppler)
            logger.info(f"  OCR: конвертация {file_path.name} в изображения (dpi={OCR_DPI})...")
            images = convert_from_path(str(file_path), dpi=OCR_DPI, poppler_path=POPPLER_PATH)
            
            fragments = []
            total_pages = len(images)
            
            for page_num, image in enumerate(images, 1):
                if page_num % 5 == 0 or page_num == 1:
                    logger.info(f"  OCR: страница {page_num}/{total_pages}")
                
                # Распознаём текст со страницы
                result = _ocr_reader.readtext(np.array(image), detail=0, paragraph=True)
                
                for para in result:
                    text = para.strip()
                    if len(text) < 30:
                        continue
                    
                    fragments.append({
                        "text": text,
                        "metadata": {
                            "source": file_path.name,
                            "type": "pdf_ocr",
                            "page": page_num,
                            "is_etalon": False
                        }
                    })
            
            return fragments
        
        except Exception as e:
            logger.error(f"Ошибка OCR для {file_path.name}: {e}")
            return []

# Глобальный кэш OCR reader
_ocr_reader = None


class TXTParser(DocumentParser):
    """Парсер TXT файлов"""
    
    def parse(self, file_path: Path) -> List[Dict[str, Any]]:
        """Парсит TXT файл построчно или по абзацам"""
        logger.info(f"Парсинг TXT: {file_path.name}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Разбиваем по абзацам
            paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
            
            fragments = []
            for para in paragraphs:
                if len(para) < 20:  # Слишком короткий
                    continue
                
                fragments.append({
                    "text": para,
                    "metadata": {
                        "source": file_path.name,
                        "type": "txt",
                        "is_etalon": False
                    }
                })
            
            logger.info(f"  TXT: {len(fragments)} фрагментов из {file_path.name}")
            return fragments
        
        except Exception as e:
            logger.error(f"Ошибка парсинга TXT {file_path.name}: {e}")
            return []


def parse_all_sources(sources_dir: Path) -> List[Dict[str, Any]]:
    """
    Парсит все документы из директории sources
    
    Args:
        sources_dir: Путь к папке data/sources/
    
    Returns:
        Список всех фрагментов со всех документов
    """
    logger.info(f"=== ПАРСИНГ ВСЕХ ИСТОЧНИКОВ: {sources_dir} ===")
    
    all_fragments = []
    
    # DOCX файлы
    docx_parser = DOCXParser()
    for docx_file in sources_dir.glob("*.docx"):
        fragments = docx_parser.parse(docx_file)
        all_fragments.extend(fragments)
    
    # PDF файлы
    pdf_parser = PDFParser()
    for pdf_file in sources_dir.glob("*.pdf"):
        fragments = pdf_parser.parse(pdf_file)
        all_fragments.extend(fragments)
    
    # TXT файлы
    txt_parser = TXTParser()
    for txt_file in sources_dir.glob("*.txt"):
        fragments = txt_parser.parse(txt_file)
        all_fragments.extend(fragments)
    
    logger.info(f"=== ИТОГО ФРАГМЕНТОВ: {len(all_fragments)} ===")
    
    # Статистика по источникам
    sources_stat = {}
    for frag in all_fragments:
        src = frag["metadata"]["source"]
        sources_stat[src] = sources_stat.get(src, 0) + 1
    
    logger.info(f"Источников: {len(sources_stat)}")
    for src, count in sorted(sources_stat.items(), key=lambda x: -x[1])[:10]:
        logger.info(f"  {src}: {count} фрагментов")
    
    return all_fragments
