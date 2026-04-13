# Toll Navigator — Progress Log

## День 6 — 12 апр 2026
### ✅ Сделано
- Добавлены 5 новых штатов в БД: WA (5 roads), AZ (5), NV (5), CO (5), MN (4)
- Итого в БД: 96 toll roads, 20 штатов
- ROUTE_DISTANCES обновлены для CO, WA, AZ, NV, MN (20+ новых пар)
- CORRIDORS обновлены — West Coast / Mountain / Midwest маршруты
- Мобильное приложение: API_URL = http://192.168.1.177:3001 ✅ (IP совпадает)
- Бэкенд: работает на порту 3001, /health ✅, /api/tolls/states → 20 штатов ✅

### Тест API
- GET /api/tolls/route?from=Seattle,WA&to=Las Vegas,NV&truck_type=5-axle → работает
- GET /api/tolls/states → ["AZ","CA","CO","FL","GA","IL","IN","MA","MD","MN","NC","NJ","NV","NY","OH","OK","PA","TX","VA","WA"]

### 📋 Следующий шаг (День 7)
- React Native экран расчёта маршрута (from/to input + truck_type selector)
- Отображение breakdown по штатам
- Тест на реальном устройстве через Expo Go

---

## День 5 — 12 апр 2026
### ✅ Сделано
- Добавлен эндпоинт GET /api/tolls/route?from=City,STATE&to=City,STATE&truck_type=5-axle
- Карта городов → штаты (80+ городов: TX, CA, FL, NY, IL, PA, OH, GA, NC, NJ, VA, TN, LA, OK, KS, MD, MA, IN, CO, AZ, WA, NV)
- Авто-определение расстояния между штатами
- Сервер работает на порту 3001
- Тест: Dallas,TX → Houston,TX → $153.92 для 5-axle ✅

### 📋 Следующий шаг (День 6)
- React Native мобильное приложение (Expo)
- Экран: вводишь откуда/куда + тип грузовика → видишь цену
- Подключение к backend API

---

## День 1 — 12 апр 2026
### 📋 Задача дня
- Создать Express сервер (backend/server.js)
- Подключение к PostgreSQL (Supabase)
- .env конфиг
- GET /health endpoint
- package.json с зависимостями

### ✅ Сделано
- Создана полная структура папок проекта
- package.json (express, pg, dotenv, cors, jwt, bcrypt, ioredis)
- .env.example шаблон
- src/server.js — Express + cors + GET /health
- src/db.js — PostgreSQL Pool
- src/middleware/auth.js — JWT verifyToken

### ⚠️ Проблемы
- Нужно заполнить .env реальными значениями (Supabase URL, JWT_SECRET)

### 📋 Следующий шаг (День 2)
- database/schema.sql — таблицы users, routes, tolls
- Применить миграцию к Supabase
- Агент: Костя

---
<!-- Каждый день добавляй новый блок выше -->
