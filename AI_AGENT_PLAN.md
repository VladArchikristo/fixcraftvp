# 🤖 FixCraft VP — AI Agent System Plan

**Goal:** Полностью автономный AI-агент для FixCraft VP, который принимает заказы, отвечает на вопросы, записывает в календарь и собирает лиды.

**Channels:** Website Chat Widget 💬 | SMS 📱 | Phone Calls 📞

---

## 📊 Системная Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT SIDE                               │
├──────────────┬──────────────┬───────────────────────────────────┤
│  🌐 Website   │   📱 SMS      │            📞 Phone              │
│ Chat Widget   │  Twilio API   │         VAPI.ai / Retell        │
│ (React)       │  (980-201-..) │      (голосовой AI бот)        │
└──────┬───────┴──────┬───────┴────────────┬──────────────────────┘
       │              │                    │
       └──────────────┴────────────────────┘
                          │
              ┌───────────▼────────────┐
              │   NODE.JS API SERVER   │
              │   (Mac Mini, 24/7)     │
              │  fixcraftvp.com/api    │
              └───────────┬────────────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
    ┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐
    │ OpenAI    │  │ Google    │  │  SQLite   │
    │ GPT-4o    │  │ Calendar  │  │   CRM     │
    │ (brain)   │  │ (booking) │  │  (leads)  │
    └───────────┘  └───────────┘  └───────────┘
```

---

## 🔥 Фаза 1: Чат-виджет на сайт (3-4 часа)

### Что строим:
Плавающая кнопка "Chat with us" → открывает окно переписки. AI отвечает мгновенно.

### Функции:
- ✅ Приветствие: *"Hi! I'm Vlad's AI assistant. Need furniture assembly or TV mounting help?"*
- ✅ Ответы на вопросы по услугам и ценам
- ✅ Определение типа работы (сборка мебели, монтаж TV, сантехника и т.д.)
- ✅ Сбор данных: имя, адрес, телефон, предпочтительное время
- ✅ Запись в Google Calendar (сразу создаёт слот)
- ✅ Отправка SMS-подтверждения клиенту
- ✅ Перевод на живого оператора (тебя) если AI не справляется

### Технология:
```
Frontend: React компонент (embed на Next.js сайт)
Backend:  Express.js API + Socket.io (real-time)
AI:       OpenAI GPT-4o + Function Calling
Storage:  SQLite (история чатов, лиды)
```

### UI/UX:
- Полупрозрачный фон с blur (как ты любишь)
- Темная тема (соответствует сайту)
- Анимация появления сообщений
- Индикатор "typing..." когда AI думает
- Кнопка "Call me" для перехода на голосовой

---

## 📱 Фаза 2: SMS-бот (2-3 часа)

### Что строим:
Клиент пишет SMS на 980-201-6705 → AI отвечает текстом.

### Сценарий:
```
Клиент: "Hi, I need my IKEA wardrobe assembled. How much?"
AI:     "Hi! Wardrobe assembly starts at $149. What's your zip code 
         so I can check availability?"
Клиент: "28277"
AI:     "Perfect! Ballantyne area — I can come today or tomorrow.
         What time works? Morning (9-12), Afternoon (12-5), or Evening (5-8)?"
Клиент: "Tomorrow afternoon"
AI:     "Great! To confirm your booking, what's your name and address?"
Клиент: "John, 14228 Plantation Park Blvd"
AI:     "Thanks John! Booked for tomorrow (Apr 27) 12-5pm at 
         14228 Plantation Park Blvd. You'll get a reminder 1 hour before. 
         Total estimate: $149-249 depending on wardrobe size. See you then!"
```

### Технология:
```
Provider: Twilio (номер уже есть)
AI:       OpenAI GPT-4o
Webhook:  POST /api/sms/incoming → AI отвечает → Twilio отправляет SMS
```

### Стоимость Twilio:
- Входящий SMS: $0.0075 / msg
- Исходящий SMS: $0.0075 / msg
- **Пример:** 100 клиентов × 5 сообщений = $7.50

---

## 📞 Фаза 3: Голосовой AI-бот (4-6 часов)

### Что строим:
Клиент звонит на 980-201-6705 → AI голосом отвечает как реальный диспетчер.

### Голос:
- Естественный мужской/нейтральный голос (американский акцент)
- Небольшие паузы, "um", "let me check" — чтобы звучало как человек
- Может перевести на тебя: *"Let me connect you with Vlad directly. One moment."*

### Сценарий звонка:
```
AI:   "Hello, FixCraft VP, this is Alex. How can I help you today?"
Клиент: "Yeah I got a leaky faucet"
AI:   "Alright, a leaky faucet. Is it in the kitchen or bathroom?"
Клиент: "Kitchen"
AI:   "Got it. Kitchen faucet repair usually runs $120 to $180. 
       I can get someone out today between 2 and 5pm. Does that work?"
Клиент: "Yeah that works"
AI:   "Perfect. Can I get your name and the address?"
...собирает данные...
AI:   "Great John, you're all set. Vlad will be there between 2 and 5pm today. 
       The technician will call 30 minutes before arrival. Thanks for choosing FixCraft!"
```

### Технология:
```
Provider: VAPI.ai (лучшее соотношение цена/качество)
Fallback: Retell.ai (если VAPI не подойдёт)
Voice:    ElevenLabs (самый реалистичный голос)
```

### Стоимость звонков:
| Платформа | Цена за минуту | Примечание |
|-----------|---------------|------------|
| VAPI.ai   | $0.05/min     | Бесплатный старт $10 |
| Retell.ai | $0.07/min     | Бесплатный старт $20 |
| Twilio    | $0.013/min    | Только телефония |

**Пример:** Средний звонок 3 минуты = $0.15. 100 звонков = $15.

---

## 💰 Полный Бюджет (API + Инфраструктура)

### Разовые затраты:
| Что | Сколько |
|-----|---------|
| Разработка (Hermes + Клод) | $0 (твой Mac Mini) |
| Twilio номер (уже есть) | $0 |

### Ежемесячные API-расходы (пример: 200 клиентов/мес):

| Сервис | Расчёт | Итого |
|--------|--------|-------|
| **OpenAI GPT-4o** | ~500K tokens | **~$10-15** |
| **Twilio SMS** | 200 клиентов × 4 msg × $0.0075 | **~$6** |
| **VAPI.ai звонки** | 50 звонков × 3 min × $0.05 | **~$7.50** |
| **Сервер (Mac Mini)** | Уже работает 24/7 | **$0** |
| **ИТОГО/мес** | | **~$20-30** |

### Для сравнения — стоимость наёмного диспетчера:
- Part-time диспетчер: $2,000-3,000/мес
- Call center: $1,500-2,500/мес
- **AI-агент: $20-30/мес** ✅

---

## 🛡️ Безопасность и Ограничения

### Что AI НЕ делает:
- ❌ Не даёт юридических советов
- ❌ Не обещает конкретную цену без осмотра
- ❌ Не принимает платежи (пока)
- ❌ Не отменяет записи сам (только перенаправляет на тебя)

### Перевод на живого оператора:
AI автоматически переводит если:
- Клиент просит "talk to a person"
- AI 3 раза не понял запрос
- Клиент спрашивает что-то вне зоны компетенции
- Запрос содержит слова: "complaint", "refund", "lawsuit", "manager"

---

## 🎯 Roadmap (по порядку)

| # | Фаза | Время | Статус |
|---|------|-------|--------|
| 1 | Бэкенд API (Express + OpenAI + SQLite) | 2 ч | 🔲 |
| 2 | Чат-виджет React (UI + интеграция) | 2 ч | 🔲 |
| 3 | Интеграция Google Calendar (booking) | 1 ч | 🔲 |
| 4 | SMS через Twilio | 1 ч | 🔲 |
| 5 | Голосовой бот VAPI.ai | 3 ч | 🔲 |
| 6 | Тестирование + отладка | 2 ч | 🔲 |
| 7 | Deploy на production | 1 ч | 🔲 |
| | **ИТОГО** | **~12 часов** | |

---

## ✅ Что нужно от тебя сейчас:

1. **Twilio Account SID + Auth Token** (для SMS)
2. **Подтверждение номера** (980-201-6705 уже подключён к Twilio?)
3. **VAPI.ai API Key** (создам аккаунт если нужно)
4. **OpenAI API Key** (уже должен быть)
5. **Доступ к Google Calendar** (уже настроен для FixCraft)

---

## 🚀 Запускаем?

**Я готов начать прямо сейчас.** Первым делом соберу бэкенд API + чат-виджет.

Скажи — **поехали?** Или хочешь что-то изменить в плане?
