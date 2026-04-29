# codex.md — FixCraft AI Estimator

## Задача
Создать веб-приложение (клон SimplyWise Cost Estimator) для handyman бизнеса в Charlotte, NC.

## Основная логика
1. Пользователь загружает фото ремонтной работы
2. Описывает проект текстом
3. AI (через GPT-4o Vision API) анализирует фото и генерирует детальную смету
4. Смета включает: материалы + труд + overhead + profit margin
5. Экспорт в branded PDF
6. Отправка клиенту по email

## Tech Stack
- Next.js 14 App Router + TypeScript
- Tailwind CSS + shadcn/ui
- PostgreSQL (Supabase)
- OpenAI GPT-4o Vision API
- Puppeteer (для PDF)
- Resend (для email)
- Vercel (хостинг)

## Ключевые файлы
- `app/new-estimate/page.tsx` — форма загрузки фото и описания
- `app/api/analyze/route.ts` — API для AI анализа
- `app/api/pdf/route.ts` — генерация PDF
- `lib/pricing.ts` — калькулятор цен с маркапом и overhead
- `lib/ai.ts` — обертка OpenAI Vision API
- `components/estimate-view.tsx` — отображение сметы

## Правила ценообразования (Charlotte NC Handyman)
- Labor rate: $95/hour standard
- Material markup: 1.3x
- Overhead: 15%
- Profit margin: 20%
- Minimum service call: $175

## Требования
- Mobile-first (большие кнопки, camera capture)
- Чистый профессиональный дизайн (contractor-style)
- Брендированный PDF с логотипом FixCraft VP
- Дисклеймер: "Estimate subject to on-site inspection"

## Интеграции
- OPENAI_API_KEY в .env
- RESEND_API_KEY в .env
- DATABASE_URL (Supabase) в .env

## Полная спецификация
См. `SPECS.md` в той же папке.
