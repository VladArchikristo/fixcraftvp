# Toll Navigator — Progress Log

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
