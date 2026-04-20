#!/usr/bin/env python3
"""
Тест общей памяти для всех ботов.
Проверяет: messages, profiles, facts, session_summaries, build_memory_prompt,
           auto-session detection, fact_extractor v2
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(__file__))
from shared_memory import (
    save_message, get_history, clear_history,
    save_profile, get_profile,
    save_fact, get_facts, get_all_facts, delete_fact, count_facts,
    save_session_summary, get_session_summaries,
    build_memory_prompt, init_db,
    _auto_detect_session, _generate_summary, _get_conn,
    SESSION_GAP_SECONDS, MIN_MESSAGES_FOR_SUMMARY
)
from fact_extractor import extract_facts, extract_facts_from_exchange, _normalize_fact

TEST_USER_ID = 999999999  # тестовый, не реальный пользователь
passed = 0
failed = 0


def test(name, func):
    global passed, failed
    try:
        func()
        passed += 1
        print(f"  ✅ {name}")
    except Exception as e:
        failed += 1
        print(f"  ❌ {name}: {e}")


def cleanup_test_data(bot_name):
    """Очищает тестовые данные."""
    clear_history(TEST_USER_ID, bot_name)
    for f in get_facts(TEST_USER_ID, bot_name):
        delete_fact(TEST_USER_ID, bot_name, f["fact"])
    conn = _get_conn()
    conn.execute("DELETE FROM session_summaries WHERE user_id=? AND bot_name=?", (TEST_USER_ID, bot_name))
    conn.commit()
    conn.close()


# ===================== MESSAGES =====================

def test_messages():
    cleanup_test_data("test_bot")
    save_message(TEST_USER_ID, "test_bot", "user", "Привет!")
    save_message(TEST_USER_ID, "test_bot", "assistant", "Здорово!")
    save_message(TEST_USER_ID, "test_bot", "user", "Как дела?")
    save_message(TEST_USER_ID, "test_bot", "assistant", "Отлично.")
    history = get_history(TEST_USER_ID, "test_bot", limit=10)
    assert len(history) == 4, f"Ожидали 4, получили {len(history)}"
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "Привет!"
    assert history[3]["content"] == "Отлично."


def test_message_limit():
    cleanup_test_data("test_limit")
    for i in range(30):
        save_message(TEST_USER_ID, "test_limit", "user", f"msg_{i}")
    history = get_history(TEST_USER_ID, "test_limit", limit=20)
    assert len(history) == 20
    assert history[0]["content"] == "msg_10"  # первые 10 обрезаны


def test_user_isolation():
    clear_history(TEST_USER_ID, "test_iso_u")
    clear_history(TEST_USER_ID + 1, "test_iso_u")
    save_message(TEST_USER_ID, "test_iso_u", "user", "Сообщение A")
    save_message(TEST_USER_ID + 1, "test_iso_u", "user", "Сообщение B")
    assert len(get_history(TEST_USER_ID, "test_iso_u")) == 1
    assert len(get_history(TEST_USER_ID + 1, "test_iso_u")) == 1


def test_bot_isolation():
    cleanup_test_data("test_iso_a")
    cleanup_test_data("test_iso_b")
    save_message(TEST_USER_ID, "test_iso_a", "user", "Бот A")
    save_message(TEST_USER_ID, "test_iso_b", "user", "Бот B")
    assert get_history(TEST_USER_ID, "test_iso_a")[0]["content"] == "Бот A"
    assert get_history(TEST_USER_ID, "test_iso_b")[0]["content"] == "Бот B"


def test_clear():
    save_message(TEST_USER_ID, "test_clear", "user", "Удалить")
    clear_history(TEST_USER_ID, "test_clear")
    assert len(get_history(TEST_USER_ID, "test_clear")) == 0


# ===================== PROFILES =====================

def test_profile():
    save_profile(TEST_USER_ID, "name", "Владимир")
    save_profile(TEST_USER_ID, "timezone", "UTC-5")
    profile = get_profile(TEST_USER_ID)
    assert profile["name"] == "Владимир"
    assert profile["timezone"] == "UTC-5"


def test_profile_update():
    save_profile(TEST_USER_ID, "test_mood", "good")
    save_profile(TEST_USER_ID, "test_mood", "great")
    profile = get_profile(TEST_USER_ID)
    assert profile["test_mood"] == "great"


# ===================== FACTS (Level 2) =====================

def test_save_get_facts():
    cleanup_test_data("test_facts2")
    save_fact(TEST_USER_ID, "test_facts2", "Влад предпочитает Python", "preference")
    save_fact(TEST_USER_ID, "test_facts2", "Портфель: SOL + ETH", "trading")
    save_fact(TEST_USER_ID, "test_facts2", "Часовой пояс: EST", "preference")
    facts = get_facts(TEST_USER_ID, "test_facts2")
    assert len(facts) == 3, f"Ожидали 3 факта, получили {len(facts)}"
    pref_facts = get_facts(TEST_USER_ID, "test_facts2", category="preference")
    assert len(pref_facts) == 2


def test_fact_dedup():
    cleanup_test_data("test_dedup2")
    save_fact(TEST_USER_ID, "test_dedup2", "Факт X", "general")
    save_fact(TEST_USER_ID, "test_dedup2", "Факт X", "general")
    save_fact(TEST_USER_ID, "test_dedup2", "Факт X", "general")
    assert count_facts(TEST_USER_ID, "test_dedup2") == 1


def test_delete_fact():
    cleanup_test_data("test_del2")
    save_fact(TEST_USER_ID, "test_del2", "Удалить меня", "temp")
    delete_fact(TEST_USER_ID, "test_del2", "Удалить меня")
    assert count_facts(TEST_USER_ID, "test_del2") == 0


def test_cross_bot_facts():
    cleanup_test_data("test_cross_v")
    cleanup_test_data("test_cross_m")
    save_fact(TEST_USER_ID, "test_cross_v", "ETH long", "trading")
    save_fact(TEST_USER_ID, "test_cross_m", "Сайт обновлён", "project")
    all_f = get_all_facts(TEST_USER_ID, limit=50)
    bot_names = {f["bot_name"] for f in all_f}
    assert "test_cross_v" in bot_names
    assert "test_cross_m" in bot_names


def test_count_facts():
    cleanup_test_data("test_cnt2")
    save_fact(TEST_USER_ID, "test_cnt2", "Раз")
    save_fact(TEST_USER_ID, "test_cnt2", "Два")
    assert count_facts(TEST_USER_ID, "test_cnt2") == 2


# ===================== SESSION SUMMARIES (Level 3) =====================

def test_session_summary():
    cleanup_test_data("test_sess2")
    save_session_summary(TEST_USER_ID, "test_sess2", "Обсудили архитектуру памяти", 15)
    save_session_summary(TEST_USER_ID, "test_sess2", "Починили LaunchAgent", 8)
    summaries = get_session_summaries(TEST_USER_ID, "test_sess2", limit=5)
    assert len(summaries) == 2
    assert "архитектуру" in summaries[0]["summary"]
    assert "LaunchAgent" in summaries[1]["summary"]


def test_session_summary_limit():
    cleanup_test_data("test_lim_sess2")
    for i in range(10):
        save_session_summary(TEST_USER_ID, "test_lim_sess2", f"Сессия {i}", i)
    summaries = get_session_summaries(TEST_USER_ID, "test_lim_sess2", limit=3)
    assert len(summaries) == 3


# ===================== AUTO-SESSION DETECTION =====================

def test_generate_summary():
    """Тест генерации резюме из сообщений."""
    import sqlite3
    # Создаём фейковые Row-объекты
    class FakeRow:
        def __init__(self, role, content, created_at):
            self._data = {"role": role, "content": content, "created_at": created_at}
        def __getitem__(self, key):
            return self._data[key]

    messages = [
        FakeRow("user", "Как настроить бота?", "2026-04-20 10:00:00"),
        FakeRow("assistant", "Вот инструкция...", "2026-04-20 10:01:00"),
        FakeRow("user", "А как добавить память?", "2026-04-20 10:05:00"),
        FakeRow("assistant", "Нужно SQLite...", "2026-04-20 10:06:00"),
        FakeRow("user", "Спасибо!", "2026-04-20 10:10:00"),
        FakeRow("assistant", "Обращайся!", "2026-04-20 10:10:30"),
    ]
    summary = _generate_summary(messages)
    assert "6 сообщ." in summary
    assert "настроить" in summary.lower() or "Как" in summary
    assert "память" in summary.lower() or "добавить" in summary.lower()


def test_auto_session_no_gap():
    """Без паузы — резюме не создаётся."""
    cleanup_test_data("test_auto_ng")
    # Быстрые сообщения подряд
    for i in range(6):
        save_message(TEST_USER_ID, "test_auto_ng", "user", f"msg {i}")
    summaries = get_session_summaries(TEST_USER_ID, "test_auto_ng")
    assert len(summaries) == 0, "Не должно быть резюме без паузы"


# ===================== BUILD_MEMORY_PROMPT =====================

def test_build_memory_prompt_empty():
    prompt = build_memory_prompt(TEST_USER_ID + 999, "nonexistent")
    assert prompt == ""


def test_build_memory_prompt_with_data():
    uid = TEST_USER_ID + 500
    cleanup_test_data_uid(uid, "test_bmp")
    save_fact(uid, "test_bmp", "Любит Python", "preference")
    save_fact(uid, "test_bmp", "Проект FixCraft", "project")
    save_session_summary(uid, "test_bmp", "Настроили CI/CD", 12)

    prompt = build_memory_prompt(uid, "test_bmp")
    assert "ДОЛГОСРОЧНАЯ ПАМЯТЬ" in prompt
    assert "Python" in prompt
    assert "FixCraft" in prompt
    assert "ПРЕДЫДУЩИЕ СЕССИИ" in prompt
    assert "CI/CD" in prompt


def test_build_memory_prompt_cross_bot():
    uid = TEST_USER_ID + 600
    cleanup_test_data_uid(uid, "test_bmp_v")
    cleanup_test_data_uid(uid, "test_bmp_k")
    save_fact(uid, "test_bmp_v", "BTC на $95K", "trading")
    save_fact(uid, "test_bmp_k", "Свой факт", "general")

    prompt = build_memory_prompt(uid, "test_bmp_k")
    assert "ДРУГИХ БОТОВ" in prompt
    assert "BTC" in prompt


def cleanup_test_data_uid(uid, bot_name):
    clear_history(uid, bot_name)
    for f in get_facts(uid, bot_name):
        delete_fact(uid, bot_name, f["fact"])
    conn = _get_conn()
    conn.execute("DELETE FROM session_summaries WHERE user_id=? AND bot_name=?", (uid, bot_name))
    conn.commit()
    conn.close()


# ===================== FACT EXTRACTOR v2 =====================

def test_normalize_fact():
    assert _normalize_fact("  hello world...  ") == "hello world"
    assert _normalize_fact("a" * 200) == "a" * 147 + "…"
    assert _normalize_fact("  пробелы   много   ") == "пробелы много"


def test_extract_remember():
    """Прямая команда 'запомни' должна создавать explicit факт."""
    cleanup_test_data("test_extr_rem")
    result = extract_facts(TEST_USER_ID, "test_extr_rem", "запомни: мой пароль от WiFi - qwerty123")
    assert len(result) >= 1
    facts = get_facts(TEST_USER_ID, "test_extr_rem", category="explicit")
    assert len(facts) >= 1
    assert "wifi" in facts[0]["fact"].lower() or "пароль" in facts[0]["fact"].lower()


def test_extract_preference_ru():
    """Русские предпочтения."""
    cleanup_test_data("test_extr_pref")
    result = extract_facts(TEST_USER_ID, "test_extr_pref", "я предпочитаю Python для скриптов")
    assert len(result) >= 1
    facts = get_facts(TEST_USER_ID, "test_extr_pref", category="preference")
    assert len(facts) >= 1


def test_extract_decision():
    """Решения и планы."""
    cleanup_test_data("test_extr_dec")
    result = extract_facts(TEST_USER_ID, "test_extr_dec", "решил переехать на TypeScript")
    assert len(result) >= 1
    facts = get_facts(TEST_USER_ID, "test_extr_dec", category="decision")
    assert len(facts) >= 1


def test_extract_trading():
    """Трейдинг."""
    cleanup_test_data("test_extr_trd")
    result = extract_facts(TEST_USER_ID, "test_extr_trd", "купил ETH на 500 долларов")
    assert len(result) >= 1
    facts = get_facts(TEST_USER_ID, "test_extr_trd", category="trading")
    assert len(facts) >= 1


def test_extract_english():
    """Английские паттерны."""
    cleanup_test_data("test_extr_en")
    result = extract_facts(TEST_USER_ID, "test_extr_en", "I prefer using Docker for deployment")
    assert len(result) >= 1


def test_extract_from_exchange():
    """Извлечение из пары user+bot."""
    cleanup_test_data("test_extr_exc")
    result = extract_facts_from_exchange(
        TEST_USER_ID, "test_extr_exc",
        "покажи портфель",
        "Итог: портфель показывает +15% за месяц, основной актив ETH"
    )
    # Должен извлечь хотя бы из бот-ответа (итог)
    facts = get_facts(TEST_USER_ID, "test_extr_exc")
    assert len(facts) >= 1


def test_extract_short_text():
    """Короткие сообщения не должны создавать фактов."""
    cleanup_test_data("test_extr_shrt")
    result = extract_facts(TEST_USER_ID, "test_extr_shrt", "да")
    assert len(result) == 0


def test_extract_no_duplicates():
    """Дубли не создаются."""
    cleanup_test_data("test_extr_dup")
    extract_facts(TEST_USER_ID, "test_extr_dup", "я предпочитаю Python для всего")
    extract_facts(TEST_USER_ID, "test_extr_dup", "я предпочитаю Python для всего")
    facts = get_facts(TEST_USER_ID, "test_extr_dup")
    # Проверяем что нет дублей одного и того же факта
    unique_facts = set(f["fact"] for f in facts)
    assert len(unique_facts) == len(facts), f"Найдены дубли: {[f['fact'] for f in facts]}"


# ===================== ALL BOTS WRITE =====================

def test_all_bots():
    bots = ["zina", "masha", "kostya", "philip", "vasily", "peter"]
    for bot in bots:
        cleanup_test_data(f"test_all_{bot}")
        save_message(TEST_USER_ID, f"test_all_{bot}", "user", f"Тест от {bot}")
        assert len(get_history(TEST_USER_ID, f"test_all_{bot}")) == 1


# ===================== RUNNER =====================

if __name__ == "__main__":
    print("🔍 Тестирую shared memory v2 (Level 1 + 2 + 3 + auto-session + extractor v2)...\n")
    init_db()

    print("--- Messages (Level 1) ---")
    test("save/get messages", test_messages)
    test("message limit", test_message_limit)
    test("user isolation", test_user_isolation)
    test("bot isolation", test_bot_isolation)
    test("clear history", test_clear)

    print("\n--- Profiles ---")
    test("save/get profile", test_profile)
    test("profile update", test_profile_update)

    print("\n--- Facts (Level 2) ---")
    test("save/get facts", test_save_get_facts)
    test("fact dedup", test_fact_dedup)
    test("delete fact", test_delete_fact)
    test("cross-bot facts", test_cross_bot_facts)
    test("count facts", test_count_facts)

    print("\n--- Session Summaries (Level 3) ---")
    test("save/get summaries", test_session_summary)
    test("summary limit", test_session_summary_limit)

    print("\n--- Auto-Session Detection ---")
    test("generate summary", test_generate_summary)
    test("no gap = no summary", test_auto_session_no_gap)

    print("\n--- build_memory_prompt ---")
    test("empty prompt", test_build_memory_prompt_empty)
    test("with data", test_build_memory_prompt_with_data)
    test("cross-bot", test_build_memory_prompt_cross_bot)

    print("\n--- Fact Extractor v2 ---")
    test("normalize fact", test_normalize_fact)
    test("extract 'запомни'", test_extract_remember)
    test("extract preference (RU)", test_extract_preference_ru)
    test("extract decision", test_extract_decision)
    test("extract trading", test_extract_trading)
    test("extract English", test_extract_english)
    test("extract from exchange", test_extract_from_exchange)
    test("short text = no facts", test_extract_short_text)
    test("no duplicates", test_extract_no_duplicates)

    print("\n--- All Bots ---")
    test("all 6 bots write", test_all_bots)

    print(f"\n{'='*50}")
    print(f"✅ Passed: {passed}  ❌ Failed: {failed}  Total: {passed + failed}")
    if failed == 0:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
    else:
        print(f"⚠️  {failed} тестов провалено!")
        sys.exit(1)
