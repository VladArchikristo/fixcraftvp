# Toll Navigator — TODO чеклист

## НЕДЕЛЯ 1 — Backend основа

### День 1 — Backend скелет
- [ ] Express сервер (server.js)
- [ ] .env конфиг
- [ ] Подключение PostgreSQL
- [ ] GET /health endpoint
- [ ] package.json

### День 2 — Схема БД
- [ ] database/schema.sql
- [ ] Таблица users
- [ ] Таблица routes  
- [ ] Таблица tolls
- [ ] Индексы + миграция

### День 3 — Auth API
- [ ] POST /register
- [ ] POST /login
- [ ] JWT генерация
- [ ] Middleware защиты роутов

## НЕДЕЛЯ 2 — Toll Data

### День 4 — Парсер данных
- [ ] Скрипт парсинга E-ZPass
- [ ] Данные по 5 штатам (TX, FL, NY, IL, CA)
- [ ] Загрузка в БД

### День 5 — Toll Calculator API
- [ ] POST /calculate-route
- [ ] Логика расчёта по штатам
- [ ] Кэш Redis

## НЕДЕЛЯ 3 — Mobile

### День 6 — Expo setup
- [ ] Инициализация Expo проекта
- [ ] Navigation (Stack + Tab)
- [ ] Экраны: Home, Route, History, Profile

### День 7 — Auth экраны
- [ ] Login экран
- [ ] Register экран
- [ ] SecureStore для JWT

### День 8 — Route Calculator экран
- [ ] Форма ввода маршрута
- [ ] Выбор типа грузовика
- [ ] Отображение результата

## НЕДЕЛЯ 4 — Карты и финиш

### День 9 — Mapbox интеграция
- [ ] Mapbox GL setup
- [ ] Отображение маршрута на карте
- [ ] Toll точки на карте

### День 10 — Тестирование + Deploy
- [ ] Backend на Hetzner
- [ ] Supabase production
- [ ] TestFlight (iOS)
