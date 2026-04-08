"""
Главный оркестратор Course Generator v5.
Управляет DAG, checkpoint'ами и восстановлением.
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from config import BASE_DIR, OUTPUT_DIR, STORAGE_DIR
from core.dag import DAG, DAGNode, NodeStatus, build_course_dag

logger = logging.getLogger(__name__)

CHECKPOINTS_DIR = STORAGE_DIR / "checkpoints"


class Orchestrator:
    """
    Главный оркестратор pipeline.
    
    - Читает task.json
    - Строит и запускает DAG
    - Сохраняет checkpoint после каждого узла
    - Восстанавливается с последнего checkpoint при перезапуске
    """
    
    def __init__(self):
        self._dag: Optional[DAG] = None
        self._task_data: Dict[str, Any] = {}
        self._session_id: str = ""
        self._start_time: float = 0
        self._checkpoints_dir: Path = CHECKPOINTS_DIR
        
        # Создаём директории
        self._checkpoints_dir.mkdir(parents=True, exist_ok=True)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    def _generate_session_id(self) -> str:
        """Генерировать уникальный ID сессии."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"session_{timestamp}"
    
    def _get_checkpoint_path(self, node_name: str) -> Path:
        """Путь к checkpoint файлу узла."""
        return self._checkpoints_dir / self._session_id / f"{node_name}.json"
    
    def _get_state_path(self) -> Path:
        """Путь к файлу состояния сессии."""
        return self._checkpoints_dir / self._session_id / "state.json"
    
    def _save_checkpoint(self, node: DAGNode) -> None:
        """Сохранить checkpoint после выполнения узла."""
        checkpoint_path = self._get_checkpoint_path(node.name)
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        
        checkpoint_data = {
            "node_name": node.name,
            "status": node.status.value,
            "duration": node.duration,
            "timestamp": datetime.now().isoformat(),
            "result": self._serialize_result(node.result),
            "error": str(node.error) if node.error else None
        }
        
        with open(checkpoint_path, "w", encoding="utf-8") as f:
            json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)
        
        logger.debug(f"Checkpoint сохранён: {node.name}")
    
    def _serialize_result(self, result: Any) -> Any:
        """Сериализовать результат для JSON."""
        if result is None:
            return None
        if isinstance(result, (str, int, float, bool)):
            return result
        if isinstance(result, dict):
            return {k: self._serialize_result(v) for k, v in result.items()}
        if isinstance(result, (list, tuple)):
            return [self._serialize_result(item) for item in result]
        if isinstance(result, Path):
            return str(result)
        # Для остальных типов — строковое представление
        return str(result)
    
    def _save_state(self) -> None:
        """Сохранить общее состояние сессии."""
        state_path = self._get_state_path()
        state_path.parent.mkdir(parents=True, exist_ok=True)
        
        state = {
            "session_id": self._session_id,
            "task_data": self._task_data,
            "start_time": self._start_time,
            "last_update": datetime.now().isoformat(),
            "node_statuses": self._dag.get_status() if self._dag else {}
        }
        
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    
    def _load_state(self, session_id: str) -> bool:
        """Загрузить состояние сессии для восстановления."""
        state_path = self._checkpoints_dir / session_id / "state.json"
        
        if not state_path.exists():
            return False
        
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            
            self._session_id = state["session_id"]
            self._task_data = state["task_data"]
            self._start_time = state.get("start_time", time.time())
            
            logger.info(f"Состояние восстановлено: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка загрузки состояния: {e}")
            return False
    
    def _restore_checkpoints(self) -> Dict[str, Any]:
        """Восстановить результаты из checkpoint'ов."""
        restored = {}
        checkpoints_path = self._checkpoints_dir / self._session_id
        
        if not checkpoints_path.exists():
            return restored
        
        for checkpoint_file in checkpoints_path.glob("*.json"):
            if checkpoint_file.name == "state.json":
                continue
            
            try:
                with open(checkpoint_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                node_name = data["node_name"]
                if data["status"] == "done":
                    restored[node_name] = data["result"]
                    logger.debug(f"Восстановлен checkpoint: {node_name}")
                    
            except Exception as e:
                logger.warning(f"Ошибка чтения checkpoint {checkpoint_file}: {e}")
        
        return restored
    
    def _on_node_complete(self, node: DAGNode) -> None:
        """Callback при завершении узла."""
        # Сохраняем checkpoint
        self._save_checkpoint(node)
        self._save_state()
        
        # Печатаем прогресс
        status_emoji = {
            NodeStatus.DONE: "✓",
            NodeStatus.FAILED: "✗",
            NodeStatus.SKIPPED: "⊘"
        }
        
        emoji = status_emoji.get(node.status, "?")
        duration_str = f" за {node.duration:.2f} сек" if node.duration else ""
        
        print(f"[{emoji}] {node.name}{duration_str}")
        
        if node.status == NodeStatus.FAILED:
            print(f"    Ошибка: {node.error}")
    
    async def run(self, task_path: Path, resume_session: Optional[str] = None) -> Path:
        """
        Запустить генерацию курсовой работы.
        
        Args:
            task_path: Путь к task.json
            resume_session: ID сессии для восстановления (опционально)
        
        Returns:
            Путь к сгенерированному .docx
        """
        self._start_time = time.time()
        
        # Восстановление или новая сессия
        if resume_session and self._load_state(resume_session):
            logger.info(f"Восстановление сессии: {resume_session}")
        else:
            self._session_id = self._generate_session_id()
            
            # Читаем task.json
            if not task_path.exists():
                raise FileNotFoundError(f"Файл задания не найден: {task_path}")
            
            with open(task_path, "r", encoding="utf-8") as f:
                self._task_data = json.load(f)
            
            logger.info(f"Новая сессия: {self._session_id}")
        
        print(f"\n{'='*60}")
        print(f"Course Generator v5 — Сессия: {self._session_id}")
        print(f"{'='*60}\n")
        
        # Строим DAG
        self._dag = build_course_dag()
        self._dag.set_context("task_data", self._task_data)
        self._dag.set_context("session_id", self._session_id)
        self._dag.on_node_complete(self._on_node_complete)
        
        # Восстанавливаем checkpoint'ы
        if resume_session:
            restored = self._restore_checkpoints()
            for node_name, result in restored.items():
                if node_name in self._dag._nodes:
                    self._dag._nodes[node_name].status = NodeStatus.DONE
                    self._dag._nodes[node_name].result = result
                    logger.info(f"Узел {node_name} восстановлен из checkpoint")
        
        # Сохраняем начальное состояние
        self._save_state()
        
        # Запускаем DAG
        print("Запуск pipeline...\n")
        results = await self._dag.run_all()
        
        # Итоги
        total_time = time.time() - self._start_time
        
        print(f"\n{'='*60}")
        print(f"Pipeline завершён за {total_time:.1f} сек")
        
        # Проверяем результат
        final_result = results.get("FINAL_OUTPUT", {})
        docx_path = final_result.get("docx", "")
        drawings = final_result.get("drawings", {})
        
        if docx_path:
            print(f"\n📄 Документ: {docx_path}")
        
        if drawings:
            print(f"📐 Чертежи:")
            for name, path in drawings.items():
                print(f"   - {name}: {path}")
        
        # Статистика ошибок
        failed_nodes = self._dag.get_failed_nodes()
        if failed_nodes:
            print(f"\n⚠️  Ошибки в узлах:")
            for node in failed_nodes:
                print(f"   - {node.name}: {node.error}")
        
        print(f"{'='*60}\n")
        
        return Path(docx_path) if docx_path else OUTPUT_DIR / "coursework.docx"
    
    def list_sessions(self) -> list:
        """Получить список доступных сессий для восстановления."""
        sessions = []
        
        for session_dir in self._checkpoints_dir.iterdir():
            if session_dir.is_dir():
                state_file = session_dir / "state.json"
                if state_file.exists():
                    try:
                        with open(state_file, "r", encoding="utf-8") as f:
                            state = json.load(f)
                        sessions.append({
                            "session_id": state["session_id"],
                            "last_update": state.get("last_update", "unknown"),
                            "node_statuses": state.get("node_statuses", {})
                        })
                    except Exception:
                        pass
        
        return sorted(sessions, key=lambda x: x["last_update"], reverse=True)


async def run_orchestrator(task_path: Path, resume: Optional[str] = None) -> Path:
    """Запустить оркестратор (удобная обёртка)."""
    orchestrator = Orchestrator()
    return await orchestrator.run(task_path, resume_session=resume)
