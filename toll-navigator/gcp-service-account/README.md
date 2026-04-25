# Google Play API настройка (автозаливка AAB)

## Шаг 1: Google Cloud Console (делаешь ты, 2 минуты)
1. Открой https://console.cloud.google.com/
2. Выбери проект (Google Play использует один из твоих GCP проектов)
3. **APIs & Services → Library → Найди "Google Play Android Developer API" → Enable**
4. **APIs & Services → Credentials → Create Credentials → Service Account**
   - Name: `haulwallet-uploader`
   - Role: Editor (или минимум — "Service Account User")
   - Done
5. Зайди в созданный Service Account → Keys → Add Key → JSON → Download
6. Скинь скачанный JSON сюда (в этот каталог) или переименуй в `service-account.json`

## Шаг 2: Google Play Console (делаешь ты, 1 минута)
1. https://play.google.com/console → HaulWallet → Users and permissions
2. **Invite new users**
   - Email: тот самый адрес сервисной учётной записи (виден в поле из шага 1, формат: `...@...iam.gserviceaccount.com`)
   - Role: **Release manager** (может загружать билды)
   - Или Admin (полный доступ)
3. Save

## Шаг 3: Я делаю всё остальное
Как только JSON на месте, запущу скрипт который:
- Загружает AAB в Internal Testing
- Обновляет Store Listing (title, short desc, full desc)
- Загружает скриншоты + feature graphic
- Отправляет на ревью или оставляет в черновике

Всё это без браузера — чистой API.