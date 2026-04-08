"""
Chapter Validator - validates generated chapters for structural and content correctness.
Checks formula markers, figure references, cross-references, and Python data.
"""

import re
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class ChapterValidator:
    """
    Validates chapter content for correctness.
    """

    def __init__(self, calc_trace: Optional[Dict[str, Any]] = None):
        """
        Args:
            calc_trace: Calculation results for validation against chapter numbers
        """
        self.calc_trace = calc_trace or {}
        self.formula_marker_pattern = re.compile(r'\[FORMULA\](.*?)\[/FORMULA\]', re.DOTALL)
        self.figure_marker_pattern = re.compile(r'\[FIGURE:(.*?)\]')
        self.table_marker_pattern = re.compile(r'\[TABLE:(.*?)\]')
        logger.info(f"Initialized ChapterValidator with calc_trace entries: {len(self.calc_trace)}")

    async def validate(
        self,
        chapter_text: str,
        chapter_idx: int
    ) -> Dict[str, Any]:
        """
        Validate a chapter.

        Args:
            chapter_text: Full chapter text
            chapter_idx: Chapter number

        Returns:
            {
                "verdict": "PASS|FAIL",
                "issues": [...],
                "suggested_rewrites": [...]
            }
        """
        logger.info(f"=== Validating Chapter {chapter_idx} ===")

        issues = []

        # Check formula markers
        formula_issues = self._validate_formulas(chapter_text)
        issues.extend(formula_issues)

        # Check figure references
        figure_issues = self._validate_figures(chapter_text)
        issues.extend(figure_issues)

        # Check table references
        table_issues = self._validate_tables(chapter_text)
        issues.extend(table_issues)

        # Check cross-references
        reference_issues = self._validate_references(chapter_text)
        issues.extend(reference_issues)

        # Check chapter length
        length_issues = self._validate_length(chapter_text)
        issues.extend(length_issues)

        # Separate by severity
        critical_issues = [i for i in issues if i.get("severity") == "CRITICAL"]
        major_issues = [i for i in issues if i.get("severity") == "MAJOR"]
        minor_issues = [i for i in issues if i.get("severity") == "MINOR"]

        # Determine verdict
        verdict = "PASS"
        suggested_rewrites = []

        if critical_issues:
            verdict = "FAIL"
            suggested_rewrites = list(range(len(chapter_text.split("\n"))))

        elif major_issues:
            verdict = "REVIEW"
            # Suggest rewriting paragraphs with major issues
            for issue in major_issues:
                if "section_idx" in issue:
                    suggested_rewrites.append(issue["section_idx"])

        # Calculate score
        issue_count = len(critical_issues) * 2 + len(major_issues) + len(minor_issues) * 0.5
        max_issues = 30
        score = max(0.0, 1.0 - (issue_count / max_issues))

        result = {
            "chapter_idx": chapter_idx,
            "verdict": verdict,
            "score": round(score, 2),
            "issues": issues,
            "issues_summary": {
                "critical": len(critical_issues),
                "major": len(major_issues),
                "minor": len(minor_issues)
            },
            "suggested_rewrites": list(set(suggested_rewrites))
        }

        logger.info(f"Chapter {chapter_idx} validation: {verdict} (score: {score:.2f})")
        logger.info(f"  Issues - Critical: {len(critical_issues)}, Major: {len(major_issues)}, Minor: {len(minor_issues)}")

        return result

    def _validate_formulas(self, text: str) -> List[Dict[str, Any]]:
        """
        Validate formula markers.

        Args:
            text: Chapter text

        Returns:
            List of issues
        """
        issues = []

        # Find all formula markers
        formulas = self.formula_marker_pattern.findall(text)

        if not formulas and "формула" in text.lower():
            issues.append({
                "type": "MISSING_FORMULA_MARKER",
                "severity": "MAJOR",
                "location": "Упомянута формула, но нет маркеров [FORMULA]",
                "found": "текст без маркеров",
                "expected": "[FORMULA]выражение[/FORMULA]",
                "fix": "Заключите все формулы в маркеры [FORMULA] и [/FORMULA]"
            })

        # Verify formula markers are paired correctly
        open_markers = len(re.findall(r'\[FORMULA\]', text))
        close_markers = len(re.findall(r'\[/FORMULA\]', text))

        if open_markers != close_markers:
            issues.append({
                "type": "UNPAIRED_FORMULA_MARKERS",
                "severity": "CRITICAL",
                "location": f"Найдено {open_markers} открывающих и {close_markers} закрывающих маркеров",
                "found": f"[FORMULA] x {open_markers}, [/FORMULA] x {close_markers}",
                "expected": "Одинаковое количество",
                "fix": "Проверьте парность всех маркеров формул"
            })

        return issues

    def _validate_figures(self, text: str) -> List[Dict[str, Any]]:
        """
        Validate figure references.

        Args:
            text: Chapter text

        Returns:
            List of issues
        """
        issues = []

        # Find all figure markers
        figures = self.figure_marker_pattern.findall(text)

        if not figures:
            if "рис" in text.lower() or "figure" in text.lower():
                issues.append({
                    "type": "MISSING_FIGURE_MARKER",
                    "severity": "MINOR",
                    "location": "Упомянут рисунок, но нет маркеров [FIGURE]",
                    "found": "текст без маркеров",
                    "expected": "[FIGURE:Описание]",
                    "fix": "Добавьте маркеры [FIGURE:описание_рисунка] для всех упоминаемых рисунков"
                })

        return issues

    def _validate_tables(self, text: str) -> List[Dict[str, Any]]:
        """
        Validate table references.

        Args:
            text: Chapter text

        Returns:
            List of issues
        """
        issues = []

        # Find all table markers
        tables = self.table_marker_pattern.findall(text)

        if not tables:
            if "таблиц" in text.lower() or "table" in text.lower():
                issues.append({
                    "type": "MISSING_TABLE_MARKER",
                    "severity": "MINOR",
                    "location": "Упомянута таблица, но нет маркеров [TABLE]",
                    "found": "текст без маркеров",
                    "expected": "[TABLE:Название_таблицы]",
                    "fix": "Добавьте маркеры [TABLE:название_таблицы] для всех таблиц"
                })

        return issues

    def _validate_references(self, text: str) -> List[Dict[str, Any]]:
        """
        Validate cross-references and structure.

        Args:
            text: Chapter text

        Returns:
            List of issues
        """
        issues = []

        # Check for common reference issues
        if re.search(r'см\.\s+\(', text):
            issues.append({
                "type": "BROKEN_REFERENCE",
                "severity": "MINOR",
                "location": "Найдена ссылка без номера",
                "found": "см. (пусто)",
                "expected": "см. рисунок 2.1 или см. таблица 3.2",
                "fix": "Проверьте что все ссылки указывают на существующие объекты"
            })

        # Check for orphaned brackets
        if text.count('(') != text.count(')'):
            issues.append({
                "type": "UNBALANCED_BRACKETS",
                "severity": "MINOR",
                "location": "Несбалансированные скобки",
                "found": f"( : {text.count('(')}, ) : {text.count(')')}",
                "expected": "Одинаковое количество",
                "fix": "Проверьте парность всех скобок"
            })

        return issues

    def _validate_length(self, text: str) -> List[Dict[str, Any]]:
        """
        Validate chapter length.

        Args:
            text: Chapter text

        Returns:
            List of issues
        """
        from config import MIN_CHAPTER_LENGTH, MAX_CHAPTER_LENGTH

        issues = []
        text_length = len(text.strip())

        if text_length < MIN_CHAPTER_LENGTH:
            issues.append({
                "type": "TOO_SHORT",
                "severity": "MAJOR",
                "location": f"Глава содержит только {text_length} символов",
                "found": str(text_length),
                "expected": f"Минимум {MIN_CHAPTER_LENGTH}",
                "fix": f"Расширьте текст главы до {MIN_CHAPTER_LENGTH} символов"
            })

        elif text_length > MAX_CHAPTER_LENGTH:
            issues.append({
                "type": "TOO_LONG",
                "severity": "MINOR",
                "location": f"Глава содержит {text_length} символов",
                "found": str(text_length),
                "expected": f"Максимум {MAX_CHAPTER_LENGTH}",
                "fix": f"Сократите текст главы до {MAX_CHAPTER_LENGTH} символов"
            })

        return issues
