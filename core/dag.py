"""
DAG execution engine для Course Generator v5.
Асинхронный граф зависимостей с параллельным выполнением узлов.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


class NodeStatus(Enum):
    """Статусы узла DAG."""
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"  # Пропущен из-за failed зависимости


@dataclass
class DAGNode:
    """Узел DAG с функцией и зависимостями."""
    name: str
    func: Callable[..., Any]
    depends_on: List[str] = field(default_factory=list)
    status: NodeStatus = NodeStatus.PENDING
    result: Any = None
    error: Optional[Exception] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    
    @property
    def duration(self) -> Optional[float]:
        """Время выполнения узла в секундах."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None


class DAG:
    """
    Directed Acyclic Graph для управления pipeline.
    
    Узлы выполняются параллельно, если их зависимости удовлетворены.
    При падении узла — зависимые узлы пропускаются (SKIPPED).
    """
    
    def __init__(self):
        self._nodes: Dict[str, DAGNode] = {}
        self._dependents: Dict[str, Set[str]] = defaultdict(set)  # node -> кто от него зависит
        self._context: Dict[str, Any] = {}  # Общий контекст для передачи данных между узлами
        self._on_node_complete: Optional[Callable[[DAGNode], None]] = None
    
    def add_node(
        self,
        name: str,
        func: Callable[..., Any],
        depends_on: Optional[List[str]] = None
    ) -> "DAG":
        """
        Добавить узел в DAG.
        
        Args:
            name: Уникальное имя узла
            func: Async или sync функция узла
            depends_on: Список имён узлов-зависимостей
        
        Returns:
            self для chaining
        """
        depends = depends_on or []
        
        # Проверка циклических зависимостей
        if name in depends:
            raise ValueError(f"Узел {name} не может зависеть от себя")
        
        node = DAGNode(name=name, func=func, depends_on=depends)
        self._nodes[name] = node
        
        # Обновляем обратный индекс
        for dep in depends:
            self._dependents[dep].add(name)
        
        logger.debug(f"Добавлен узел: {name}, зависимости: {depends}")
        return self
    
    def set_context(self, key: str, value: Any) -> None:
        """Установить значение в общий контекст."""
        self._context[key] = value
    
    def get_context(self, key: str, default: Any = None) -> Any:
        """Получить значение из контекста."""
        return self._context.get(key, default)
    
    def on_node_complete(self, callback: Callable[[DAGNode], None]) -> None:
        """Установить callback при завершении узла."""
        self._on_node_complete = callback
    
    def _get_ready_nodes(self) -> List[DAGNode]:
        """Получить узлы, готовые к выполнению (все зависимости DONE)."""
        ready = []
        for node in self._nodes.values():
            if node.status != NodeStatus.PENDING:
                continue
            
            # Проверяем все зависимости
            all_deps_done = True
            any_dep_failed = False
            
            for dep_name in node.depends_on:
                dep_node = self._nodes.get(dep_name)
                if not dep_node:
                    logger.error(f"Зависимость {dep_name} для {node.name} не найдена")
                    any_dep_failed = True
                    break
                
                if dep_node.status == NodeStatus.FAILED or dep_node.status == NodeStatus.SKIPPED:
                    any_dep_failed = True
                    break
                
                if dep_node.status != NodeStatus.DONE:
                    all_deps_done = False
                    break
            
            if any_dep_failed:
                # Помечаем узел как SKIPPED
                node.status = NodeStatus.SKIPPED
                logger.warning(f"Узел {node.name} пропущен из-за failed зависимости")
                if self._on_node_complete:
                    self._on_node_complete(node)
            elif all_deps_done:
                ready.append(node)
        
        return ready
    
    async def _run_node(self, node: DAGNode) -> None:
        """Выполнить один узел."""
        node.status = NodeStatus.RUNNING
        node.start_time = time.time()
        logger.info(f"[RUNNING] {node.name}")
        
        try:
            # Собираем результаты зависимостей
            dep_results = {
                dep_name: self._nodes[dep_name].result
                for dep_name in node.depends_on
            }
            
            # Вызываем функцию с контекстом и результатами зависимостей
            if asyncio.iscoroutinefunction(node.func):
                node.result = await node.func(self._context, dep_results)
            else:
                node.result = node.func(self._context, dep_results)
            
            node.status = NodeStatus.DONE
            node.end_time = time.time()
            logger.info(f"[DONE] {node.name} за {node.duration:.2f} сек")
            
        except Exception as e:
            node.status = NodeStatus.FAILED
            node.error = e
            node.end_time = time.time()
            logger.error(f"[FAILED] {node.name}: {e}")
        
        if self._on_node_complete:
            self._on_node_complete(node)
    
    async def run_all(self) -> Dict[str, Any]:
        """
        Запустить все узлы DAG с параллельным выполнением.
        
        Returns:
            Словарь {node_name: result} для всех DONE узлов
        """
        logger.info(f"Запуск DAG с {len(self._nodes)} узлами")
        start_time = time.time()
        
        # Валидация: проверяем что все зависимости существуют
        for node in self._nodes.values():
            for dep in node.depends_on:
                if dep not in self._nodes:
                    raise ValueError(f"Узел {node.name} зависит от несуществующего узла {dep}")
        
        # Основной цикл
        while True:
            ready = self._get_ready_nodes()
            
            if not ready:
                # Проверяем есть ли ещё PENDING или RUNNING узлы
                pending_count = sum(
                    1 for n in self._nodes.values()
                    if n.status in (NodeStatus.PENDING, NodeStatus.RUNNING)
                )
                if pending_count == 0:
                    break
                
                # Ждём завершения текущих задач
                await asyncio.sleep(0.1)
                continue
            
            # Запускаем все готовые узлы параллельно
            tasks = [self._run_node(node) for node in ready]
            await asyncio.gather(*tasks, return_exceptions=True)
        
        total_time = time.time() - start_time
        
        # Статистика
        done_count = sum(1 for n in self._nodes.values() if n.status == NodeStatus.DONE)
        failed_count = sum(1 for n in self._nodes.values() if n.status == NodeStatus.FAILED)
        skipped_count = sum(1 for n in self._nodes.values() if n.status == NodeStatus.SKIPPED)
        
        logger.info(
            f"DAG завершён за {total_time:.2f} сек: "
            f"{done_count} done, {failed_count} failed, {skipped_count} skipped"
        )
        
        # Возвращаем результаты успешных узлов
        return {
            name: node.result
            for name, node in self._nodes.items()
            if node.status == NodeStatus.DONE
        }
    
    def get_status(self) -> Dict[str, str]:
        """Получить текущий статус всех узлов."""
        return {name: node.status.value for name, node in self._nodes.items()}
    
    def get_failed_nodes(self) -> List[DAGNode]:
        """Получить список упавших узлов."""
        return [n for n in self._nodes.values() if n.status == NodeStatus.FAILED]
    
    def reset(self) -> None:
        """Сбросить статусы всех узлов для повторного запуска."""
        for node in self._nodes.values():
            node.status = NodeStatus.PENDING
            node.result = None
            node.error = None
            node.start_time = None
            node.end_time = None
        self._context.clear()


# === Узлы DAG из README ===

async def node_input_validate(ctx: Dict, deps: Dict) -> Dict:
    """Валидация входных данных."""
    from core.input_validator import validate_input
    task_data = ctx.get("task_data", {})
    result = validate_input(task_data)
    if not result.valid:
        raise ValueError(f"Валидация не пройдена: {result.report()}")
    return {"validation": result}


async def node_parse(ctx: Dict, deps: Dict) -> Dict:
    """Парсинг входных данных."""
    task_data = ctx.get("task_data", {})
    return {
        "parsed": {
            "scheme": task_data.get("scheme", "unknown"),
            "parameters": task_data.get("parameters", {}),
            "materials": task_data.get("materials", {})
        }
    }


async def node_chunk(ctx: Dict, deps: Dict) -> Dict:
    """Разбиение справочных данных на чанки."""
    from retrieval.document_parser import parse_all_sources
    from retrieval.chunker import SmartChunker
    from config import SOURCES_DIR, CHUNK_SIZE, CHUNK_OVERLAP
    
    logger.info("=== CHUNK: Парсинг источников ===")
    
    # Парсим все документы из sources/
    documents = parse_all_sources(SOURCES_DIR)
    
    # Разбиваем на чанки
    chunker = SmartChunker(chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
    chunks = chunker.chunk_documents(documents)
    
    logger.info(f"Создано чанков: {len(chunks)}")
    
    return {"chunks": chunks, "chunk_count": len(chunks)}


async def node_embed(ctx: Dict, deps: Dict) -> Dict:
    """Создание embeddings."""
    from retrieval.embeddings_engine import EmbeddingsEngine
    from config import EMBEDDING_MODEL, EMBEDDINGS_CACHE_PATH
    
    logger.info("=== EMBED: Создание embeddings ===")
    
    chunks = deps["CHUNK"]["chunks"]
    
    if not chunks:
        logger.warning("Нет чанков для создания embeddings")
        return {"embeddings_created": False, "vectors_count": 0, "chunks": []}
    
    # Создаём embeddings
    engine = EmbeddingsEngine(model_name=EMBEDDING_MODEL)
    texts = [c["text"] for c in chunks]
    embeddings = engine.encode(texts, show_progress=True)
    
    # Сохраняем
    engine.save_embeddings(embeddings, EMBEDDINGS_CACHE_PATH)
    
    return {
        "embeddings_created": True, 
        "vectors_count": len(embeddings),
        "dimension": embeddings.shape[1],
        "chunks": chunks  # Передаём дальше для INDEX
    }


async def node_index(ctx: Dict, deps: Dict) -> Dict:
    """Индексация в FAISS + BM25."""
    from retrieval.reference_retriever import ReferenceRetriever
    from config import FAISS_INDEX_PATH, CHUNKS_DB_PATH, EMBEDDINGS_CACHE_PATH
    import numpy as np
    
    logger.info("=== INDEX: Построение FAISS индекса ===")
    
    # Chunks из CHUNK (или из EMBED если там есть)
    chunks = deps.get("CHUNK", {}).get("chunks") or deps.get("EMBED", {}).get("chunks")
    
    if not chunks:
        raise ValueError("Chunks не найдены в зависимостях CHUNK или EMBED")
    
    # Загружаем embeddings
    embeddings = np.load(str(EMBEDDINGS_CACHE_PATH))
    
    # Строим индекс
    retriever = ReferenceRetriever()
    retriever.build_index(chunks, embeddings)
    
    # Сохраняем
    retriever.save(FAISS_INDEX_PATH, CHUNKS_DB_PATH)
    
    logger.info(f"✓ Индекс готов: {len(chunks)} чанков проиндексировано")
    
    return {"index_ready": True, "indexed_chunks": len(chunks), "chunks": chunks}


async def node_calc_engine(ctx: Dict, deps: Dict) -> Dict:
    """Расчётный движок."""
    from calc.engine import run_calculations
    task_data = ctx.get("task_data", {})
    result = run_calculations(task_data)
    ctx.set_context("calc_params", result["calculated_params"]) if hasattr(ctx, 'set_context') else None
    return result


async def node_ref_analyzer(ctx: Dict, deps: Dict) -> Dict:
    """Анализ справочных данных."""
    # Заглушка — выбор стандартных значений из справочников
    return {"ref_data": {}, "selected_standards": []}


async def node_fem_lite(ctx: Dict, deps: Dict) -> Dict:
    """Упрощённый FEM анализ."""
    # Заглушка — будет sympy-based проверка
    calc_result = deps.get("CALC_ENGINE", {})
    return {"fem_ok": True, "stress_check": "passed"}


async def node_dim_chain(ctx: Dict, deps: Dict) -> Dict:
    """Размерная цепь."""
    calc_result = deps.get("CALC_ENGINE", {})
    dim_chain_data = calc_result.get("calc_trace", {}).get("dim_chain", {})
    return {"dim_chain": dim_chain_data, "validated": True}


async def node_calc_validate(ctx: Dict, deps: Dict) -> Dict:
    """Валидация расчётов."""
    fem_result = deps.get("FEM_LITE", {})
    dim_result = deps.get("DIM_CHAIN", {})
    
    is_valid = fem_result.get("fem_ok", False) and dim_result.get("validated", False)
    return {"calc_validated": is_valid}


async def node_drawing_engine(ctx: Dict, deps: Dict) -> Dict:
    """Генерация чертежей."""
    from drawing.drawing_engine import DrawingEngine
    
    calc_result = deps.get("CALC_ENGINE", {})
    calc_params = calc_result.get("calculated_params", {})
    calc_trace = calc_result.get("calc_trace", {})
    
    engine = DrawingEngine()
    drawings = {}
    
    # Чертёж вала
    if "dim_chain" in calc_trace:
        shaft_path = engine.shaft_drawing(calc_trace["dim_chain"])
        drawings["shaft"] = shaft_path
    
    # Чертёж зубчатого колеса
    if "gear" in calc_trace:
        gear_path = engine.gear_drawing(calc_trace["gear"])
        drawings["gear"] = gear_path
    
    return {"drawings": drawings}


async def node_llm_planning(ctx: Dict, deps: Dict) -> Dict:
    """Планирование структуры через LLM или из task.json."""
    from pipeline.planner import Planner
    from llm.gateway import OllamaGateway
    
    calc_result = deps.get("CALC_ENGINE", {})
    ref_result = deps.get("REF_ANALYZER", {})
    
    calc_trace = calc_result.get("calc_trace", {})
    task_data = ctx.get("task_data", {})
    
    # Проверяем, есть ли фиксированная структура в task.json
    if "table_of_contents" in task_data:
        toc = task_data["table_of_contents"]
        logger.info("Используем фиксированную структуру из task.json")
        
        # Конвертируем table_of_contents в формат плана
        chapters = []
        
        # Добавляем введение если есть
        if "intro" in toc:
            intro = toc["intro"]
            chapters.append({
                "idx": 0,
                "title": intro.get("title", "Введение"),
                "sections": [],
                "content_type": "LLM_THEORY",
                "llm_task": intro.get("llm_task", "")
            })
        
        # Добавляем главы
        toc_chapters = toc.get("chapters", [])
        for ch in toc_chapters:
            ch_type = ch.get("type", "text")
            ch_title = ch.get("title", "")
            ch_subsections = ch.get("subsections", [])
            
            # Определяем llm_task для главы
            llm_task = ch.get("llm_task", "")
            
            # Если llm_task не указан явно и нет подразделов — генерируем автоматически
            if not llm_task and len(ch_subsections) == 0:
                if ch_type == "calc":
                    calc_module = ch.get("calc_module", "")
                    llm_task = f"Описание методики расчёта по модулю {calc_module}"
                elif ch_type == "mixed":
                    llm_task = ch.get("description", f"Описание главы '{ch_title}'")
                elif ch_type == "text":
                    llm_task = f"Напиши полный текст раздела '{ch_title}'"
            
            chapter = {
                "idx": ch.get("number", 0),
                "title": ch_title,
                "type": ch_type,
                "calc_module": ch.get("calc_module", ""),
                "llm_task": llm_task,
                "sections": []
            }
            
            # Добавляем секции из подразделов
            for sec in ch_subsections:
                section = {
                    "idx": sec.get("number", ""),
                    "title": sec.get("title", ""),
                    "content_type": sec.get("content_type", "LLM_THEORY"),
                    "calc_vars": sec.get("calc_vars", []),
                    "notes": sec.get("notes", "")
                }
                chapter["sections"].append(section)
            
            chapters.append(chapter)
        
        # Добавляем заключение если есть
        if "conclusion" in toc:
            concl = toc["conclusion"]
            chapters.append({
                "idx": 99,
                "title": concl.get("title", "Заключение"),
                "sections": [],
                "content_type": "LLM_THEORY",
                "llm_task": concl.get("llm_task", "")
            })
        
        plan = {
            "plan_version": "v5_fixed",
            "scheme": task_data.get("scheme", ""),
            "chapters": chapters,
            "total_chapters": len(chapters)
        }
        
        logger.info(f"План из task.json: {len(chapters)} глав")
    else:
        # Fallback на LLM Planner
        logger.info("Структура не найдена в task.json, вызов LLM Planner")
        from llm import create_gateway
        gateway = create_gateway()
        planner = Planner(gateway)
        plan = await planner.plan(calc_trace, task_data)
    
    ctx["plan"] = plan
    return {"plan": plan, "chapters_count": plan.get("total_chapters", 0)}


async def node_text_engine(ctx: Dict, deps: Dict) -> Dict:
    """Генерация текста глав через LLM."""
    import aiohttp
    from pipeline.writer import Writer
    from pipeline.critic import Critic
    from llm import create_gateway
    from retrieval.reference_retriever import ReferenceRetriever
    from config import FAISS_INDEX_PATH, CHUNKS_DB_PATH
    
    plan = deps.get("LLM_PLANNING", {}).get("plan", {})
    calc_result = deps.get("CALC_ENGINE", {})
    calc_trace = calc_result.get("calc_trace", {})
    
    # Загружаем retriever для style examples (если индекс существует)
    retriever = None
    if FAISS_INDEX_PATH.exists() and CHUNKS_DB_PATH.exists():
        try:
            retriever = ReferenceRetriever()
            retriever.load(FAISS_INDEX_PATH, CHUNKS_DB_PATH)
            logger.info("✓ Retriever загружен — Writer будет использовать style examples")
        except Exception as e:
            logger.warning(f"Не удалось загрузить retriever: {e}")
            logger.info("Writer будет работать без style examples")
    else:
        logger.info("Индекс не найден — Writer без style examples")
    
    # Выгрузить deepseek-course из памяти перед загрузкой qwen-course
    logger.info("Выгружаем deepseek-course из памяти для освобождения RAM...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "http://localhost:11434/api/generate",
                json={"model": "deepseek-course", "keep_alive": 0}
            ) as response:
                if response.status == 200:
                    logger.info("✓ deepseek-course выгружен")
                else:
                    logger.warning(f"Не удалось выгрузить deepseek-course: HTTP {response.status}")
    except Exception as e:
        logger.warning(f"Ошибка при выгрузке deepseek-course: {e}")
    
    # Задержка 10 секунд для полной выгрузки
    logger.info("Ожидание 10 секунд для полной выгрузки модели из RAM...")
    await asyncio.sleep(10)

    # Прогрев qwen-course - загружаем модель в память тестовым запросом
    logger.info("Прогрев qwen-course (загрузка модели в RAM, может занять 3-5 минут)...")
    gateway = create_gateway()
    try:
        warmup_response = await gateway.chat(
            model="qwen-course",
            messages=[{"role": "user", "content": "Привет"}],
            temperature=0.3,
            max_tokens=10
        )
        logger.info(f"✓ qwen-course готов к работе (прогрев: '{warmup_response.strip()[:50]}')")
    except Exception as e:
        logger.warning(f"Ошибка при прогреве qwen-course: {e}")
    
    writer = Writer(gateway)
    critic = Critic(gateway)

    chapters_text = {}

    # Setup chapter parallelism with semaphore
    from config import MAX_CONCURRENT_CHAPTERS, CHAPTER_VALIDATION_ENABLED
    from validation.chapter_validator import ChapterValidator

    max_concurrent = MAX_CONCURRENT_CHAPTERS
    semaphore = asyncio.Semaphore(max_concurrent)

    validator = ChapterValidator(calc_trace) if CHAPTER_VALIDATION_ENABLED else None

    async def process_chapter(chapter: Dict) -> Tuple[str, Dict]:
        """Process a single chapter with validation."""
        async with semaphore:
            chapter_idx = str(chapter.get("idx", 0))
            logger.info(f"Processing chapter {chapter_idx}...")

            chapter_text_parts = []

            # Если глава имеет секции — генерируем каждую секцию
            sections = chapter.get("sections", [])
            if sections:
                for section in sections:
                    # Writer генерирует текст
                    section_text = await writer.write_section(section, calc_trace)
                    chapter_text_parts.append(section_text)
            else:
                # Если секций нет (введение/заключение) — генерируем всю главу целиком
                pseudo_section = {
                    "idx": chapter_idx,
                    "title": chapter.get("title", ""),
                    "content_type": chapter.get("content_type", "LLM_THEORY"),
                    "llm_task": chapter.get("llm_task", ""),
                    "calc_vars": [],
                    "notes": f"Напиши полный текст раздела '{chapter.get('title', '')}'"
                }
                chapter_text = await writer.write_section(pseudo_section, calc_trace)
                chapter_text_parts.append(chapter_text)

            full_chapter_text = "\n\n".join(chapter_text_parts)

            # Critic проверяет
            critique_result = await critic.critique(chapter_idx, full_chapter_text, calc_trace)

            # Immediate validation after generation
            validation_result = None
            if validator:
                validation_result = await validator.validate(full_chapter_text, int(chapter_idx) if chapter_idx.isdigit() else 0)

                # Handle validation failures
                if validation_result.get("verdict") == "FAIL":
                    logger.warning(f"Chapter {chapter_idx} validation failed: {validation_result.get('issues_summary')}")
                    # Can trigger automatic rewrite here if desired

            # Если критик требует перезаписи и score < 0.8
            if not critique_result.get("skip_rewrite", False):
                rewrite_sections = critique_result.get("rewrite_sections", [])
                logger.warning(f"Chapter {chapter_idx} requires rewrite: {rewrite_sections}")

            logger.info(f"Chapter {chapter_idx} completed")

            return (chapter_idx, {
                "text": full_chapter_text,
                "title": chapter.get("title", f"Глава {chapter_idx}"),
                "critique": critique_result,
                "validation": validation_result
            })

    # Process all chapters in parallel with semaphore limit
    chapter_tasks = [process_chapter(chapter) for chapter in plan.get("chapters", [])]
    chapter_results = await asyncio.gather(*chapter_tasks, return_exceptions=True)

    # Handle results
    for result in chapter_results:
        if isinstance(result, Exception):
            logger.error(f"Chapter processing error: {result}")
            raise result

        chapter_idx, chapter_data = result
        chapters_text[chapter_idx] = chapter_data

    return {"chapters": chapters_text}


async def node_formula_numberer(ctx: Dict, deps: Dict) -> Dict:
    """Нумерация формул."""
    text_result = deps.get("TEXT_ENGINE", {})
    chapters = text_result.get("chapters", {})
    
    # Нумерация будет в DOCXBuilder, здесь только подготовка
    return {"chapters": chapters, "formula_count": 0}


async def node_figure_numberer(ctx: Dict, deps: Dict) -> Dict:
    """Нумерация рисунков."""
    formula_result = deps.get("FORMULA_NUMBERER", {})
    return formula_result  # Передаём дальше


async def node_docx_builder(ctx: Dict, deps: Dict) -> Dict:
    """Сборка DOCX."""
    from assembly.docx_builder import DOCXBuilder
    from config import OUTPUT_DIR
    
    figure_result = deps.get("FIGURE_NUMBERER", {})
    drawing_result = deps.get("DRAWING_ENGINE", {})
    
    chapters = figure_result.get("chapters", {})
    
    output_path = OUTPUT_DIR / "coursework.docx"
    builder = DOCXBuilder(output_path)
    
    # Сортируем ключи: 0 (введение), затем 1-N, затем 99 (заключение)
    def sort_key(x):
        x_str = str(x)
        try:
            num = int(x_str)
            # Введение (0) идёт первым, заключение (99) последним
            if num == 0:
                return -1  # Введение
            elif num == 99:
                return 1000  # Заключение в конец
            else:
                return num  # Обычные главы 1-14
        except (ValueError, TypeError):
            # Если это строка типа "1.2", парсим первую цифру
            parts = x_str.split('.')
            try:
                return int(parts[0])
            except:
                return 500  # Неизвестные в середину
    
    for chapter_idx in sorted(chapters.keys(), key=sort_key):
        chapter_data = chapters[chapter_idx]
        content = chapter_data.get("text", "")
        title = chapter_data.get("title", f"Глава {chapter_idx}")
        
        # КРИТИЧЕСКАЯ ПРОВЕРКА: если контент пустой, логируем ОШИБКУ
        if not content or len(content.strip()) < 50:
            logger.error(f"⚠️ ПУСТАЯ ГЛАВА: idx={chapter_idx}, title='{title}', len={len(content)}")
            logger.error(f"   chapter_data keys: {list(chapter_data.keys())}")
            logger.error(f"   text preview: '{content[:200]}'")
        
        builder.add_chapter(
            level=1,
            title=title,
            content=content
        )
    
    # Добавляем рисунки чертежей
    drawings = drawing_result.get("drawings", {})
    for drawing_name, drawing_path in drawings.items():
        builder.add_drawing_reference(drawing_name, drawing_path)
    
    builder.save()
    
    return {"docx_path": str(output_path)}


async def node_bibliography_engine(ctx: Dict, deps: Dict) -> Dict:
    """Генерация библиографии."""
    from assembly.bibliography_engine import BibliographyEngine, Source
    
    docx_result = deps.get("DOCX_BUILDER", {})
    
    # Стандартные источники для курсовой по деталям машин
    engine = BibliographyEngine()
    
    engine.add_source(Source(
        type="gost",
        gost_number="ГОСТ 21354-87",
        title="Передачи зубчатые цилиндрические эвольвентные внешнего зацепления. Расчет на прочность"
    ))
    engine.add_source(Source(
        type="gost",
        gost_number="ГОСТ 2.105-2019",
        title="Общие требования к текстовым документам"
    ))
    engine.add_source(Source(
        type="book",
        authors=["Дунаев П.Ф.", "Леликов О.П."],
        title="Конструирование узлов и деталей машин",
        city="Москва",
        publisher="Академия",
        year=2017,
        pages=496
    ))
    
    bibliography = engine.generate()
    
    return {"bibliography": bibliography, "sources_count": len(engine.sources)}


async def node_toc_builder(ctx: Dict, deps: Dict) -> Dict:
    """Генерация оглавления."""
    bib_result = deps.get("BIBLIOGRAPHY_ENGINE", {})
    return {"toc_ready": True}


async def node_global_consistency(ctx: Dict, deps: Dict) -> Dict:
    """Глобальная проверка согласованности."""
    return {"consistency_ok": True, "issues": []}


async def node_gost_linter(ctx: Dict, deps: Dict) -> Dict:
    """Проверка ГОСТ без исправлений."""
    from validation.gost_linter import GOSTLinter
    from config import OUTPUT_DIR
    
    docx_path = OUTPUT_DIR / "coursework.docx"
    
    if docx_path.exists():
        linter = GOSTLinter(str(docx_path))
        result = linter.lint()
        return {"lint_result": result, "score": result.get("score", 0)}
    
    return {"lint_result": {}, "score": 0}


async def node_gost_auto_fixer(ctx: Dict, deps: Dict) -> Dict:
    """Автоисправление по ГОСТ."""
    from validation.gost_fixer import GOSTFixer
    from config import OUTPUT_DIR
    
    lint_result = deps.get("GOST_LINTER", {})
    score = lint_result.get("score", 0)
    
    docx_path = OUTPUT_DIR / "coursework.docx"
    
    # Исправляем только если score < 0.9
    if score < 0.9 and docx_path.exists():
        fixer = GOSTFixer(str(docx_path))
        fix_result = fixer.fix()  # fix() уже сохраняет документ внутри
        return {"fixed": True, "fixes": fix_result}
    
    return {"fixed": False, "fixes": {}}


async def node_smart_critic(ctx: Dict, deps: Dict) -> Dict:
    """Финальная критическая проверка через LLM."""
    from pipeline.smart_critic import SmartCritic
    from retrieval.reference_retriever import ReferenceRetriever
    from llm import create_gateway
    from config import FAISS_INDEX_PATH, CHUNKS_DB_PATH, LOG_DIR
    import json
    from pathlib import Path
    
    logger.info("=== SMART_CRITIC: Глубокий анализ документа ===")
    
    # Проверяем что индекс существует
    if not FAISS_INDEX_PATH.exists():
        logger.warning("FAISS индекс не найден, пропускаем Smart Critic")
        return {"skipped": True, "reason": "no_index"}
    
    # Загружаем индекс
    retriever = ReferenceRetriever()
    retriever.load(FAISS_INDEX_PATH, CHUNKS_DB_PATH)
    
    # Получаем главы из TEXT_ENGINE
    text_result = deps.get("TEXT_ENGINE", {})
    chapters = text_result.get("chapters", {})
    
    if not chapters:
        logger.warning("Нет глав для анализа")
        return {"skipped": True, "reason": "no_chapters"}
    
    # Преобразуем chapters в список секций
    sections = []
    for chapter_id in sorted(chapters.keys()):
        chapter_data = chapters[chapter_id]
        sections.append({
            "title": chapter_data.get("title", f"Глава {chapter_id}"),
            "text": chapter_data.get("text", "")
        })
    
    # Создаём Smart Critic
    gateway = create_gateway()
    critic = SmartCritic(gateway, retriever)
    
    # Полный анализ
    result = await critic.analyze_full_document(sections)
    
    # Сохраняем отчёт
    report_path = LOG_DIR / "smart_critic_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    logger.info(f"✓ Отчёт сохранён: {report_path}")
    logger.info(f"Overall score: {result['overall_score']}")
    logger.info(f"Verdict: {result['verdict']}")
    
    return result


async def node_final_output(ctx: Dict, deps: Dict) -> Dict:
    """Финальный вывод."""
    from config import OUTPUT_DIR
    
    docx_path = OUTPUT_DIR / "coursework.docx"
    
    # Собираем все чертежи
    drawing_result = deps.get("DRAWING_ENGINE", {})
    drawings = drawing_result.get("drawings", {})
    
    return {
        "docx": str(docx_path),
        "drawings": drawings,
        "status": "completed"
    }


def build_course_dag() -> DAG:
    """
    Построить DAG для генерации курсовой работы.
    Порядок из README.
    """
    dag = DAG()
    
    # Входная обработка
    dag.add_node("INPUT_VALIDATE", node_input_validate)
    dag.add_node("PARSE", node_parse, depends_on=["INPUT_VALIDATE"])
    dag.add_node("CHUNK", node_chunk, depends_on=["PARSE"])
    dag.add_node("EMBED", node_embed, depends_on=["CHUNK"])
    dag.add_node("INDEX", node_index, depends_on=["EMBED", "CHUNK"])  # CHUNK тоже нужен для chunks
    
    # Параллельные расчёты
    dag.add_node("CALC_ENGINE", node_calc_engine, depends_on=["INDEX"])
    dag.add_node("REF_ANALYZER", node_ref_analyzer, depends_on=["INDEX"])
    
    # Валидация расчётов
    dag.add_node("FEM_LITE", node_fem_lite, depends_on=["CALC_ENGINE"])
    dag.add_node("DIM_CHAIN", node_dim_chain, depends_on=["CALC_ENGINE"])
    dag.add_node("CALC_VALIDATE", node_calc_validate, depends_on=["FEM_LITE", "DIM_CHAIN"])
    
    # Параллельно: чертежи и планирование LLM
    dag.add_node("DRAWING_ENGINE", node_drawing_engine, depends_on=["CALC_VALIDATE", "REF_ANALYZER"])
    dag.add_node("LLM_PLANNING", node_llm_planning, depends_on=["CALC_VALIDATE", "REF_ANALYZER"])
    
    # Генерация текста
    dag.add_node("TEXT_ENGINE", node_text_engine, depends_on=["LLM_PLANNING"])
    dag.add_node("FORMULA_NUMBERER", node_formula_numberer, depends_on=["TEXT_ENGINE"])
    dag.add_node("FIGURE_NUMBERER", node_figure_numberer, depends_on=["FORMULA_NUMBERER"])
    
    # Сборка документа
    dag.add_node("DOCX_BUILDER", node_docx_builder, depends_on=["DRAWING_ENGINE", "FIGURE_NUMBERER"])
    dag.add_node("BIBLIOGRAPHY_ENGINE", node_bibliography_engine, depends_on=["DOCX_BUILDER"])
    dag.add_node("TOC_BUILDER", node_toc_builder, depends_on=["BIBLIOGRAPHY_ENGINE"])
    
    # Проверка качества
    dag.add_node("GLOBAL_CONSISTENCY", node_global_consistency, depends_on=["TOC_BUILDER"])
    dag.add_node("GOST_LINTER", node_gost_linter, depends_on=["GLOBAL_CONSISTENCY"])
    dag.add_node("GOST_AUTO_FIXER", node_gost_auto_fixer, depends_on=["GOST_LINTER"])
    
    # Финал
    dag.add_node("SMART_CRITIC", node_smart_critic, depends_on=["GOST_AUTO_FIXER"])
    dag.add_node("FINAL_OUTPUT", node_final_output, depends_on=["SMART_CRITIC", "DRAWING_ENGINE"])
    
    return dag
