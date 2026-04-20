#!/usr/bin/env python3
"""
Тест общей памяти для всех ботов.
Проверяет: messages, profiles, facts, session_summaries, build_memory_prompt
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from shared_memory import (
    save_message, get_history, clear_history,
    save_profile, get_profile,
    save_fact, get_facts, get_all_facts, delete_fact, count_facts,
    save_session_summary, get_session_summaries,
    build_memory_prompt, init_db
)

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


# ===================== MESSAGES =====================

def test_messages():
    clear_history(TEST_USER_ID, "test_bot")
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
    clear_history(TEST_USER_ID, "test_limit")
    for i in range(30):
        save_message(TEST_USER_ID, "test_limit", "user", f"msg_{i}")
    history = get_history(TEST_USER_ID, "test_limit", limit=20)
    assert len(history) == 20
    assert history[0]["content"] == "msg_10"  # первые 10 обрезаны


def test_user_isolation():
    clear_history(TEST_USER_ID, "zina")
    clear_history(TEST_USER_ID + 1, "zina")
    save_message(TEST_USER_ID, "zina", "user", "Сообщение A")
    save_message(TEST_USER_ID + 1, "zina", "user", "Сообщение B")
    assert len(get_history(TEST_USER_ID, "zina")) == 1
    assert len(get_history(TEST_USER_ID + 1, "zina")) == 1


def test_bot_isolation():
    clear_history(TEST_USER_ID, "masha")
    clear_history(TEST_USER_ID, "philip")
    save_message(TEST_USER_ID, "masha", "user", "Маша")
    save_message(TEST_USER_ID, "philip", "user", "Филип")
    assert get_history(TEST_USER_ID, "masha")[0]["content"] == "Маша"
    assert get_history(TEST_USER_ID, "philip")[0]["content"] == "Филип"


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
    save_profile(TEST_USER_ID, "mood", "good")
    save_profile(TEST_USER_ID, "mood", "great")
    profile = get_profile(TEST_USER_ID)
    assert profile["mood"] == "great"


# ===================== FACTS (Level 2) =====================

def test_save_get_facts():
    # Очистка
    for f in get_facts(TEST_USER_ID, "test_facts"):
        delete_fact(TEST_USER_ID, "test_facts", f["fact"])

    save_fact(TEST_USER_ID, "test_facts", "Влад предпочитает Python", "preference")
    save_fact(TEST_USER_ID, "test_facts", "Портфель: SOL + ETH", "trading")
    save_fact(TEST_USER_ID, "test_facts", "Часовой пояс: EST", "preference")

    facts = get_facts(TEST_USER_ID, "test_facts")
    assert len(facts) == 3, f"Ожидали 3 факта, получили {len(facts)}"

    pref_facts = get_facts(TEST_USER_ID, "test_facts", category="preference")
    assert len(pref_facts) == 2


def test_fact_dedup():
    """Дублирующий факт не создаёт новую запись, а обновляет timestamp."""
    for f in get_facts(TEST_USER_ID, "test_dedup"):
        delete_fact(TEST_USER_ID, "test_dedup", f["fact"])

    save_fact(TEST_USER_ID, "test_dedup", "Факт X", "general")
    save_fact(TEST_USER_ID, "test_dedup", "Факт X", "general")
    save_fact(TEST_USER_ID, "test_dedup", "Факт X", "general")
    assert count_facts(TEST_USER_ID, "test_dedup") == 1


def test_delete_fact():
    save_fact(TEST_USER_ID, "test_del", "Удалить меня", "temp")
    delete_fact(TEST_USER_ID, "test_del", "Удалить меня")
    assert count_facts(TEST_USER_ID, "test_del") == 0


def test_cross_bot_facts():
    """Факты от разных ботов видны через get_all_facts."""
    save_fact(TEST_USER_ID, "vasily", "ETH long открыт", "trading")
    save_fact(TEST_USER_ID, "masha", "Сайт обновлён", "project")
    all_f = get_all_facts(TEST_USER_ID, limit=50)
    bot_names = {f["bot_name"] for f in all_f}
    assert "vasily" in bot_names
    assert "masha" in bot_names


def test_count_facts():
    for f in get_facts(TEST_USER_ID, "test_count"):
        delete_fact(TEST_USER_ID, "test_count", f["fact"])
    save_fact(TEST_USER_ID, "test_count", "Раз")
    save_fact(TEST_USER_ID, "test_count", "Два")
    assert count_facts(TEST_USER_ID, "test_count") == 2


# ===================== SESSION SUMMARIES (Level 3) =====================

def test_session_summary():
    save_session_summary(TEST_USER_ID, "test_sess", "Обсудили архитектуру памяти", 15)
    save_session_summary(TEST_USER_ID, "test_sess", "Починили LaunchAgent", 8)
    summaries = get_session_summaries(TEST_USER_ID, "test_sess", limit=5)
    assert len(summaries) >= 2
    assert "архитектуру" in summaries[-2]["summary"] or "LaunchAgent" in summaries[-1]["summary"]


def test_session_summary_limit():
    for i in range(10):
        save_session_summary(TEST_USER_ID, "test_limit_sess", f"Сессия {i}", i)
    summaries = get_session_summaries(TEST_USER_ID, "test_limit_sess", limit=3)
    assert len(summaries) == 3


# ===================== BUILD_MEMORY_PROMPT =====================

def test_build_memory_prompt_empty():
    prompt = build_memory_prompt(TEST_USER_ID + 999, "nonexistent")
    assert prompt == ""


def test_build_memory_prompt_with_data():
    uid = TEST_USER_ID + 500
    save_fact(uid, "test_prompt", "Любит Python", "preference")
    save_fact(uid, "test_prompt", "Проект FixCraft", "project")
    save_session_summary(uid, "test_prompt", "Настроили CI/CD", 12)

    prompt = build_memory_prompt(uid, "test_prompt")
    assert "ДОЛГОСРОЧНАЯ ПАМЯТЬ" in prompt
    assert "Python" in prompt
    assert "FixCraft" in prompt
    assert "ПРЕДЫДУЩИЕ СЕССИИ" in prompt
    assert "CI/CD" in prompt


def test_build_memory_prompt_cross_bot():
    uid = TEST_USER_ID + 600
    save_fact(uid, "vasily", "BTC на $95K", "trading")
    save_fact(uid, "kostya", "Свой факт", "general")

    prompt = build_memory_prompt(uid, "kostya")
    assert "ДРУГИХ БОТОВ" in prompt
    assert "BTC" in prompt


# ===================== ALL BOTS WRITE =====================

def test_all_bots():
    bots = ["zina", "masha", "kostya", "philip", "vasily", "peter"]
    for bot in bots:
        clear_history(TEST_USER_ID, bot)
        save_message(TEST_USER_ID, bot, "user", f"Тест от {bot}")
        assert len(get_history(TEST_USER_ID, bot)) == 1


# ===================== RUNNER =====================

if __name__ == "__main__":
    print("🔍 Тестирую shared memory систему (Level 1 + 2 + 3)...\n")
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

    print("\n--- build_memory_prompt ---")
    test("empty prompt", test_build_memory_prompt_empty)
    test("with data", test_build_memory_prompt_with_data)
    test("cross-bot", test_build_memory_prompt_cross_bot)

    print("\n--- All Bots ---")
    test("all 6 bots write", test_all_bots)

    print(f"\n{'='*50}")
    print(f"✅ Passed: {passed}  ❌ Failed: {failed}  Total: {passed + failed}")
    if failed == 0:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
    else:
        print(f"⚠️  {failed} тестов провалено!")
        sys.exit(1)
