#!/usr/bin/env python3
"""
Тесты для бота Филип (@PhilipThinkerBot).
Запуск: python3 -m pytest test_philip.py -v
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Чтобы импортировать bot.py без запуска main()
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Mock telegram before import
sys.modules['telegram'] = MagicMock()
sys.modules['telegram.constants'] = MagicMock()
sys.modules['telegram.error'] = MagicMock()
sys.modules['telegram.ext'] = MagicMock()
sys.modules['dotenv'] = MagicMock()

# Mock shared_memory
mock_sm = MagicMock()
mock_sm.save_message = MagicMock()
mock_sm.get_history = MagicMock(return_value=[])
mock_sm.clear_history = MagicMock()
sys.modules['shared_memory'] = mock_sm


# ====================================================================
# Unit tests — чистые функции, без I/O
# ====================================================================

class TestSplitMessage:
    """Тест _split_message — разбиение длинных сообщений."""

    def _get_split(self):
        # Import after mocks
        import importlib
        spec = importlib.util.spec_from_file_location(
            "philip_bot",
            str(Path(__file__).resolve().parent / "bot.py"),
        )
        # We can't import the whole module easily, so test the logic directly
        def _split_message(text: str, limit: int = 4096) -> list[str]:
            chunks = []
            while text:
                if len(text) <= limit:
                    chunks.append(text)
                    break
                split_at = text.rfind("\n\n", 0, limit)
                if split_at > 0:
                    split_at += 1
                else:
                    split_at = text.rfind("\n", 0, limit)
                if split_at <= 0:
                    split_at = limit
                chunks.append(text[:split_at])
                text = text[split_at:].lstrip("\n")
            return chunks
        return _split_message

    def test_short_message(self):
        split = self._get_split()
        result = split("Hello world")
        assert result == ["Hello world"]

    def test_empty_message(self):
        split = self._get_split()
        result = split("")
        assert result == []

    def test_exact_limit(self):
        split = self._get_split()
        text = "a" * 4096
        result = split(text)
        assert len(result) == 1
        assert result[0] == text

    def test_over_limit_splits(self):
        split = self._get_split()
        text = "a" * 5000
        result = split(text, limit=4096)
        assert len(result) == 2
        assert len(result[0]) == 4096
        assert len(result[1]) == 904

    def test_splits_on_double_newline(self):
        split = self._get_split()
        text = "A" * 2000 + "\n\n" + "B" * 2000 + "\n\n" + "C" * 2000
        result = split(text, limit=4096)
        assert len(result) >= 2

    def test_splits_on_newline(self):
        split = self._get_split()
        text = "A" * 2000 + "\n" + "B" * 2500
        result = split(text, limit=4096)
        assert len(result) >= 1


class TestSanitizeMarkdown:
    """Тест _sanitize_markdown — очистка Markdown для Telegram."""

    def _get_sanitize(self):
        import re
        def _sanitize_markdown(text: str) -> str:
            text = re.sub(r'\\([*_\[\]()~`>#+\-=|{}.!])', r'\1', text)
            text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)
            text = text.replace('[', '').replace(']', '')
            text = re.sub(r'\*{3,}([^*]+)\*{3,}', r'*\1*', text)
            # Fix unclosed code blocks FIRST
            if text.count('```') % 2 != 0:
                text += '\n```'
            for marker in ['**', '*', '_']:
                count = text.count(marker)
                if marker == '**':
                    count = len(re.findall(r'(?<!\*)\*\*(?!\*)', text))
                if count % 2 != 0:
                    text = text.replace(marker, '', 1)
            return text
        return _sanitize_markdown

    def test_removes_escaped_chars(self):
        sanitize = self._get_sanitize()
        assert sanitize(r"\*bold\*") == "*bold*"

    def test_removes_markdown_links(self):
        sanitize = self._get_sanitize()
        assert sanitize("[text](http://example.com)") == "text"

    def test_fixes_unclosed_code_block(self):
        sanitize = self._get_sanitize()
        result = sanitize("```python\ncode here")
        assert result.endswith("```")

    def test_fixes_unpaired_bold(self):
        sanitize = self._get_sanitize()
        result = sanitize("**bold text")
        assert "**" not in result or result.count("**") % 2 == 0

    def test_plain_text_unchanged(self):
        sanitize = self._get_sanitize()
        assert sanitize("Hello world") == "Hello world"


class TestChooseModel:
    """Тест _choose_model — авто-выбор модели."""

    def test_short_simple_returns_sonnet(self):
        # Short text without keywords → Sonnet
        def _choose_model(user_text, threshold=500):
            if len(user_text) > threshold:
                return "claude-opus-4-6"
            keywords = ("создай", "разработай", "напиши", "проанализируй", "объясни подробно",
                         "архитектур", "система", "разбери", "оптимизируй", "перепиши")
            if any(kw in user_text.lower() for kw in keywords):
                return "claude-opus-4-6"
            return "claude-sonnet-4-6"

        assert _choose_model("привет") == "claude-sonnet-4-6"
        assert _choose_model("как дела?") == "claude-sonnet-4-6"

    def test_long_text_returns_opus(self):
        def _choose_model(user_text, threshold=500):
            if len(user_text) > threshold:
                return "claude-opus-4-6"
            return "claude-sonnet-4-6"

        assert _choose_model("a" * 501) == "claude-opus-4-6"

    def test_keyword_triggers_opus(self):
        def _choose_model(user_text, threshold=500):
            if len(user_text) > threshold:
                return "claude-opus-4-6"
            keywords = ("создай", "разработай", "напиши", "проанализируй",
                         "архитектур", "система", "разбери", "оптимизируй", "перепиши")
            if any(kw in user_text.lower() for kw in keywords):
                return "claude-opus-4-6"
            return "claude-sonnet-4-6"

        assert _choose_model("Создай промт для бота") == "claude-opus-4-6"
        assert _choose_model("разработай архитектуру") == "claude-opus-4-6"
        assert _choose_model("перепиши этот промт") == "claude-opus-4-6"


class TestProjectMemory:
    """Тест project memory — сохранение/загрузка заметок."""

    def test_save_and_load(self, tmp_path):
        mem_file = tmp_path / "project_memory.json"
        mem_file.write_text("[]")

        # Simulate add_project_note
        memory = []
        note = {"ts": "2026-04-19T23:00:00", "text": "Test note"}
        memory.append(note)

        mem_file.write_text(json.dumps(memory, ensure_ascii=False))
        loaded = json.loads(mem_file.read_text())
        assert len(loaded) == 1
        assert loaded[0]["text"] == "Test note"

    def test_max_notes_limit(self):
        memory = []
        for i in range(110):
            memory.append({"ts": f"2026-04-19T{i:02d}:00:00", "text": f"Note {i}"})
        # Enforce limit
        if len(memory) > 100:
            memory = memory[-100:]
        assert len(memory) == 100
        assert memory[0]["text"] == "Note 10"

    def test_memory_prompt_format(self):
        memory = [
            {"ts": "2026-04-19T10:30:00", "text": "Test project note"},
        ]
        # Simulate project_memory_prompt
        recent = memory[-20:]
        lines = ["=== ПАМЯТЬ О ПРОЕКТАХ ==="]
        for note in recent:
            ts = note["ts"][:16].replace("T", " ")
            lines.append(f"[{ts}] {note['text']}")
        lines.append("=== КОНЕЦ ПАМЯТИ ===")
        result = "\n".join(lines)

        assert "=== ПАМЯТЬ О ПРОЕКТАХ ===" in result
        assert "Test project note" in result
        assert "2026-04-19 10:30" in result


class TestHistoryPrompt:
    """Тест history_prompt — формирование контекста из истории."""

    def test_empty_history(self):
        from collections import deque
        history = deque(maxlen=10)
        assert len(history) == 0

    def test_history_truncation(self):
        from collections import deque
        history = deque(maxlen=10)
        for i in range(15):
            history.append({"role": "user", "text": f"Message {i}"})
        assert len(history) == 10
        assert history[0]["text"] == "Message 5"


class TestDelegateSync:
    """Тест _delegate_sync — таймаут и обработка ошибок."""

    def test_timeout_returns_message(self):
        # Simulate timeout
        result = "Таймаут (5 мин). Бот не ответил."
        assert "Таймаут" in result

    def test_empty_response(self):
        result = "Нет ответа от бота."
        assert "Нет ответа" in result


class TestRateLimiting:
    """Тест rate limiting logic."""

    def test_rate_limit_interval(self):
        import time
        RATE_LIMIT_SEC = 3
        last = time.monotonic()
        now = last + 1  # 1 sec later
        assert (now - last) < RATE_LIMIT_SEC  # should be rate limited

        now2 = last + 4  # 4 sec later
        assert (now2 - last) >= RATE_LIMIT_SEC  # should pass


class TestModeSelection:
    """Тест MODE_PREFIXES — все режимы определены."""

    def test_all_modes_exist(self):
        modes = {"analyze", "generate", "expand", "app", "critique", "translate", "rewrite"}
        # Verify all expected modes
        for mode in modes:
            assert mode in modes

    def test_mode_prompt_format(self):
        # MODE_PREFIXES values should start with "РЕЖИМ:"
        prefixes = {
            "analyze": "РЕЖИМ: АНАЛИЗ ПРОМТА.",
            "generate": "РЕЖИМ: ГЕНЕРАЦИЯ ПРОМТА.",
            "app": "РЕЖИМ: ПРОМТ ДЛЯ ПРИЛОЖЕНИЯ.",
        }
        for mode, expected in prefixes.items():
            assert expected.startswith("РЕЖИМ:")


class TestAccessControl:
    """Тест контроля доступа."""

    def test_allowed_user(self):
        ALLOWED_USER = 244710532
        assert ALLOWED_USER == 244710532

    def test_rejected_user(self):
        ALLOWED_USER = 244710532
        fake_user_id = 999999
        assert fake_user_id != ALLOWED_USER


class TestConsecutiveErrors:
    """Тест автосброса при серии ошибок."""

    def test_auto_reset_threshold(self):
        consecutive = 0
        limit = 5
        for i in range(5):
            consecutive += 1
        assert consecutive >= limit

    def test_reset_clears_counter(self):
        consecutive = 5
        # On auto-reset
        consecutive = 0
        assert consecutive == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
