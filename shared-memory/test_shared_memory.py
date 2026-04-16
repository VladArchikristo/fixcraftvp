#!/usr/bin/env python3
"""
Тест общей памяти для всех ботов.
Проверяет: save_message, get_history, clear_history, save_profile, get_profile
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from shared_memory import save_message, get_history, clear_history, save_profile, get_profile, init_db

TEST_USER_ID = 999999999  # тестовый, не реальный пользователь

def test_messages():
    print("\n=== Тест: save_message / get_history ===")
    # Очистим старые тестовые данные
    clear_history(TEST_USER_ID, "test_bot")

    save_message(TEST_USER_ID, "test_bot", "user", "Привет, я тестирую память!")
    save_message(TEST_USER_ID, "test_bot", "assistant", "Привет! Я всё помню.")
    save_message(TEST_USER_ID, "test_bot", "user", "Ты точно не забудешь?")
    save_message(TEST_USER_ID, "test_bot", "assistant", "Точно. Сохранено в SQLite.")

    history = get_history(TEST_USER_ID, "test_bot", limit=10)
    assert len(history) == 4, f"Ожидали 4 сообщения, получили {len(history)}"
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "Привет, я тестирую память!"
    assert history[3]["role"] == "assistant"
    print(f"  ✓ Сохранено и прочитано {len(history)} сообщений")
    for msg in history:
        print(f"    [{msg['role']}] {msg['content'][:60]}")

def test_isolation():
    print("\n=== Тест: изоляция по user_id ===")
    clear_history(TEST_USER_ID, "zina")
    clear_history(TEST_USER_ID + 1, "zina")

    save_message(TEST_USER_ID, "zina", "user", "Сообщение от пользователя A")
    save_message(TEST_USER_ID + 1, "zina", "user", "Сообщение от пользователя B")

    hist_a = get_history(TEST_USER_ID, "zina")
    hist_b = get_history(TEST_USER_ID + 1, "zina")

    assert len(hist_a) == 1, f"A должен видеть 1 сообщение, видит {len(hist_a)}"
    assert len(hist_b) == 1, f"B должен видеть 1 сообщение, видит {len(hist_b)}"
    assert hist_a[0]["content"] != hist_b[0]["content"]
    print(f"  ✓ Пользователи изолированы: A видит только своё, B — только своё")

def test_bot_isolation():
    print("\n=== Тест: изоляция по bot_name ===")
    clear_history(TEST_USER_ID, "masha")
    clear_history(TEST_USER_ID, "philip")

    save_message(TEST_USER_ID, "masha", "user", "Маша, помоги с маркетингом")
    save_message(TEST_USER_ID, "philip", "user", "Филип, помоги с промтом")

    hist_masha = get_history(TEST_USER_ID, "masha")
    hist_philip = get_history(TEST_USER_ID, "philip")

    assert len(hist_masha) == 1
    assert len(hist_philip) == 1
    assert hist_masha[0]["content"] != hist_philip[0]["content"]
    print(f"  ✓ Маша и Филип хранят историю отдельно")

def test_profile():
    print("\n=== Тест: save_profile / get_profile ===")
    save_profile(TEST_USER_ID, "name", "Владимир")
    save_profile(TEST_USER_ID, "timezone", "UTC-5")
    save_profile(TEST_USER_ID, "language", "ru")

    profile = get_profile(TEST_USER_ID)
    assert profile.get("name") == "Владимир", f"Имя: {profile.get('name')}"
    assert profile.get("timezone") == "UTC-5"
    assert profile.get("language") == "ru"
    print(f"  ✓ Профиль сохранён: {profile}")

def test_clear():
    print("\n=== Тест: clear_history ===")
    save_message(TEST_USER_ID, "test_bot", "user", "Это будет удалено")
    clear_history(TEST_USER_ID, "test_bot")
    history = get_history(TEST_USER_ID, "test_bot")
    assert len(history) == 0, f"После очистки должно быть 0, получили {len(history)}"
    print(f"  ✓ История очищена успешно")

def test_all_bots():
    print("\n=== Тест: все 6 ботов пишут в одну БД ===")
    bots = ["zina", "masha", "kostya", "philip", "vasily", "peter"]
    for bot in bots:
        clear_history(TEST_USER_ID, bot)
        save_message(TEST_USER_ID, bot, "user", f"Тест от {bot}")
        hist = get_history(TEST_USER_ID, bot)
        assert len(hist) == 1, f"{bot}: ожидали 1, получили {len(hist)}"
        print(f"  ✓ {bot}: OK")
    print(f"  ✓ Все {len(bots)} ботов пишут в общую memory.db")

if __name__ == "__main__":
    print("🔍 Тестирую shared memory систему...")
    try:
        init_db()
        test_messages()
        test_isolation()
        test_bot_isolation()
        test_profile()
        test_clear()
        test_all_bots()
        print("\n✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ — shared memory работает корректно!")
    except AssertionError as e:
        print(f"\n❌ ТЕСТ УПАЛ: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
