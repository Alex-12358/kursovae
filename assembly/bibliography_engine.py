"""
Bibliography Engine - генерация библиографии по ГОСТ 7.0.5-2008
Поддержка: книги, ГОСТы, статьи, веб-ресурсы
"""
import logging
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class Source:
    """Библиографический источник"""
    type: str  # 'book', 'gost', 'article', 'web'
    title: str
    authors: Optional[List[str]] = None
    year: Optional[int] = None
    publisher: Optional[str] = None
    city: Optional[str] = None
    pages: Optional[int] = None
    url: Optional[str] = None
    access_date: Optional[str] = None
    gost_number: Optional[str] = None
    journal: Optional[str] = None
    volume: Optional[str] = None
    number: Optional[str] = None
    page_range: Optional[str] = None


class BibliographyEngine:
    """
    Генератор библиографии по ГОСТ 7.0.5-2008
    Форматирует источники в соответствии со стандартом
    """
    
    def __init__(self):
        self.sources: List[Source] = []
        logger.info("Инициализирован BibliographyEngine")
    
    def add_source(self, source: Source):
        """
        Добавить источник в библиографию
        
        Args:
            source: Объект Source
        """
        self.sources.append(source)
        logger.debug(f"Добавлен источник: {source.type} - {source.title[:50]}...")
    
    def generate(self) -> List[str]:
        """
        Сгенерировать список литературы
        
        Returns:
            Список отформатированных строк
        """
        logger.info(f"Генерация библиографии, источников: {len(self.sources)}")
        
        bibliography = []
        for idx, source in enumerate(self.sources, start=1):
            formatted = self._format_source(source, idx)
            bibliography.append(formatted)
        
        logger.debug(f"Сгенерировано библиографических записей: {len(bibliography)}")
        return bibliography
    
    def _format_source(self, source: Source, index: int) -> str:
        """
        Форматировать источник по ГОСТ 7.0.5
        
        Args:
            source: Источник
            index: Номер в списке
            
        Returns:
            Отформатированная строка
        """
        if source.type == 'book':
            return self._format_book(source, index)
        elif source.type == 'gost':
            return self._format_gost(source, index)
        elif source.type == 'article':
            return self._format_article(source, index)
        elif source.type == 'web':
            return self._format_web(source, index)
        else:
            logger.warning(f"Неизвестный тип источника: {source.type}")
            return f"{index}. {source.title}"
    
    def _format_book(self, source: Source, index: int) -> str:
        """
        Форматировать книгу
        Формат: Автор(ы). Название / Автор(ы). — Издательство, Год. — Страниц с.
        
        Args:
            source: Источник типа 'book'
            index: Номер
            
        Returns:
            Отформатированная строка
        """
        parts = [f"{index}."]
        
        # Авторы
        if source.authors:
            authors_str = self._format_authors(source.authors)
            parts.append(authors_str)
        
        # Название
        parts.append(source.title)
        
        # Издательские данные
        pub_parts = []
        if source.publisher:
            pub_parts.append(source.publisher)
        if source.year:
            pub_parts.append(str(source.year))
        
        if pub_parts:
            parts.append("— " + ", ".join(pub_parts) + ".")
        
        # Объём
        if source.pages:
            parts.append(f"— {source.pages} с.")
        
        result = " ".join(parts)
        logger.debug(f"Книга: {result[:80]}...")
        return result
    
    def _format_gost(self, source: Source, index: int) -> str:
        """
        Форматировать ГОСТ
        Формат: ГОСТ XXXXX-YYYY. Название. — Введ. ГГГГ-ММ-ДД. — М. : Стандартинформ, ГГГГ. — ХХ с.
        
        Args:
            source: Источник типа 'gost'
            index: Номер
            
        Returns:
            Отформатированная строка
        """
        parts = [f"{index}."]
        
        # Обозначение ГОСТ
        if source.gost_number:
            parts.append(f"ГОСТ {source.gost_number}.")
        
        # Название
        parts.append(source.title)
        
        # Издательские данные
        if source.year:
            parts.append(f"— М. : Стандартинформ, {source.year}.")
        
        # Объём
        if source.pages:
            parts.append(f"— {source.pages} с.")
        
        result = " ".join(parts)
        logger.debug(f"ГОСТ: {result[:80]}...")
        return result
    
    def _format_article(self, source: Source, index: int) -> str:
        """
        Форматировать статью из журнала
        Формат: Автор(ы). Название статьи // Название журнала. — Год. — Т. Х, № Y. — С. A-B.
        
        Args:
            source: Источник типа 'article'
            index: Номер
            
        Returns:
            Отформатированная строка
        """
        parts = [f"{index}."]
        
        # Авторы
        if source.authors:
            authors_str = self._format_authors(source.authors)
            parts.append(authors_str)
        
        # Название статьи
        parts.append(source.title)
        
        # Название журнала
        if source.journal:
            parts.append(f"// {source.journal}.")
        
        # Год
        if source.year:
            parts.append(f"— {source.year}.")
        
        # Том и номер
        journal_details = []
        if source.volume:
            journal_details.append(f"Т. {source.volume}")
        if source.number:
            journal_details.append(f"№ {source.number}")
        
        if journal_details:
            parts.append("— " + ", ".join(journal_details) + ".")
        
        # Страницы
        if source.page_range:
            parts.append(f"— С. {source.page_range}.")
        
        result = " ".join(parts)
        logger.debug(f"Статья: {result[:80]}...")
        return result
    
    def _format_web(self, source: Source, index: int) -> str:
        """
        Форматировать веб-ресурс
        Формат: Название [Электронный ресурс]. — URL: адрес (дата обращения: ДД.ММ.ГГГГ).
        
        Args:
            source: Источник типа 'web'
            index: Номер
            
        Returns:
            Отформатированная строка
        """
        parts = [f"{index}."]
        
        # Название
        parts.append(f"{source.title} [Электронный ресурс].")
        
        # URL
        if source.url:
            parts.append(f"— URL: {source.url}")
            
            # Дата обращения
            if source.access_date:
                parts.append(f"(дата обращения: {source.access_date}).")
            else:
                parts[-1] += "."
        
        result = " ".join(parts)
        logger.debug(f"Веб-ресурс: {result[:80]}...")
        return result
    
    def _format_authors(self, authors: List[str]) -> str:
        """
        Форматировать список авторов по ГОСТ
        До 3 авторов: Иванов И. И., Петров П. П., Сидоров С. С.
        4+ авторов: Иванов И. И. [и др.]
        
        Args:
            authors: Список авторов
            
        Returns:
            Отформатированная строка
        """
        if not authors:
            return ""
        
        if len(authors) <= 3:
            return ", ".join(authors) + "."
        else:
            return f"{authors[0]} [и др.]."
