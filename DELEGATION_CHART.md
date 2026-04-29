# 🤖 Разделение работы: Hermes vs Claude vs Vlad

## 🧠 HERMES (я)

**Что делаю САМ:**
- ✅ Архитектура системы (какие сервисы, как связаны)
- ✅ Интеграции API (Twilio, VAPI.ai, OpenAI, Google Calendar)
- ✅ Безопасность (API keys, .env, не трогаю bot.py)
- ✅ База данных (SQLite схема, миграции, связи)
- ✅ Deploy и инфраструктура (Mac Mini, nginx, systemd)
- ✅ Проверка кода Клода (аудит, ревью, баги)
- ✅ Сложная логика (AI prompt engineering, function calling)
- ✅ Google Play Console / Expo builds

**Пример:** Настраиваю Twilio webhook → мой Express API → OpenAI → Google Calendar

---

## 👨‍💻 CLAUDE CODE (Клод)

**Что делегирую ЕМУ:**
- 📝 React компоненты (чат-виджет, UI, стили)
- 📝 Express.js роуты (CRUD, простые endpoints)
- 📝 CSS/Tailwind (вёрстка, адаптив, анимации)
- 📝 Простые SQL запросы (SELECT, INSERT, UPDATE)
- 📝 Тесты (Jest, простые unit-тесты)
- 📝 Повторяющийся boilerplate код

**Пример:** "Создай React компонент ChatWidget с полем ввода, кнопкой отправки, списком сообщений. Стили тёмная тема, полупрозрачный фон с blur."

---

## 👤 VLAD (ты)

**Что делаешь ТЫ:**
- 📱 Тестирование на телефоне (звонить боту, писать SMS)
- 🌐 Тест чата (заходить на сайт, писать сценарии)
- 🗣️ Проверка голоса (звонить, слушать, говорить что звучит как человек)
- 📊 Проверка данных (календарь создался? SMS пришло?)
- 🎯 Решение "делать / не делать" (фичи, приоритеты)

**Пример:** Звонишь на 980-201-6705, говоришь "У меня протечка" → проверяешь что AI ответил нормально → смотришь создалась ли запись в календаре

---

## 📋 По задачам FixCraft AI Agent

| Задача | Кто | Время |
|--------|-----|-------|
| **Backend API архитектура** | Hermes | 1ч |
| **OpenAI Function Calling** | Hermes | 1ч |
| **Twilio + VAPI интеграция** | Hermes | 1ч |
| **SQLite схема (лиды, чаты)** | Hermes | 30м |
| **React ChatWidget UI** | **Claude** | 2ч |
| **Express CRUD endpoints** | **Claude** | 1ч |
| **CSS стили (blur, dark theme)** | **Claude** | 1ч |
| **Google Calendar booking logic** | Hermes | 1ч |
| **SMS webhook handler** | Hermes | 30м |
| **Голосовой бот (VAPI prompt)** | Hermes | 1ч |
| **Deploy на Mac Mini** | Hermes | 30м |
| **Тестирование звонков/SMS** | **Vlad** | 1ч |
| **Тест чата на сайте** | **Vlad** | 30м |

---

## 🔥 Главное правило

**Hermes проектирует → Claude строит → Vlad проверяет**

Если Клод накосячит — я поймаю на ревью.
Если я накосячу — ты поймаешь на тесте.
Если всё ок — мы деплоим и клиенты радуются.
