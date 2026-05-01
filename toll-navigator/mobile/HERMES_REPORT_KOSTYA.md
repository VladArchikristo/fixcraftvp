# Отчёт от Клона #2 (Костя) по HaulWallet

**Дата:** April 30, 2026
**Проект:** `~/Папка тест/fixcraftvp/toll-navigator/mobile`

---

## Текущий статус

| Параметр | Значение |
|---|---|
| приложение | HaulWallet |
| Версия | **1.14.0** |
| versionCode | **14** |
| Expo SDK | **52** |
| Последний коммит | `2bd17e8` — HaulWallet fixes + Beast parallel proc fix |
| Bundle ID | `com.haulwallet.app` |
| Expo Project ID | `ff7f070e-42d7-439b-9dc9-68ad352c23b0` |

---

## Уже сделано (v13 в коде)

1. **OSRM real driving routes** — заменили прямую линию на реальный машрут вождения
2. **Полный английский** (ZERO Cyrillic остался во всех экранах)
3. **Иконки грузовиков** — 🛻 (2-axle), 🚛 (5-axle)
4. **Subscription mock** — 5 бесплатных расчётов, затем paywall
5. **Layout fixes** — SafeAreaView, переполнение, уменьшены шрифты

---

## ⚠️ Блокер

**Expo login сброшен.**

- `eas whoami` → **Not logged in**
- На машине нет сохранённых токенов или сессий Expo
- Google Play service account JSON есть: `toll-navigator/gcp-service-account/service-account.json`
- Для локальной разработки (`npx expo start`) — готово
- Для EAS build / автозагрузки в GP — **нужен relogin**

---

## Проверки

- Backend: `https://api.haulwallet.com` в Docker, SQLite БД ~3,764 tolls, 2,483 дороги
- Zero-rate fix применен
- Docker ready (`Dockerfile` в backend/)

---

## Что нужно от Влада/Гермеса

1. Цель: что делаем сейчас?
2. Если новый билд для GP — нужен Expo login (vladimir92905) или EAS token
3. Если локальная разработка — `npx expo start` готов
4. Открытые баги: пока не известны, нужно тестирование

---

*Костя (Hermes Клон #2), апрель 2026*
