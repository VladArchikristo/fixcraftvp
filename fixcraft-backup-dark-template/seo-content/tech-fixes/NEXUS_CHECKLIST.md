# 🛠️ Чеклист для Nexus — Технические SEO фиксы fixcraftvp.com

Маша подготовила этот список. Nexus — тебе нужно применить эти изменения в коде сайта.

---

## 🔴 ПРИОРИТЕТ 1 — Срочно (влияет на ранжирование прямо сейчас)

### 1. Canonical URL — исправить конфликт www/non-www

**Проблема:** Сайт доступен на `www.fixcraftvp.com`, но canonical в head ссылается на `fixcraftvp.com` (без www). Google видит два разных сайта.

**Файл: `src/app/layout.tsx`** — найти `metadataBase` и изменить на:
```tsx
export const metadata: Metadata = {
  metadataBase: new URL('https://www.fixcraftvp.com'),
  alternates: {
    canonical: '/',
  },
  // ... остальное не трогать
}
```

**Файл: `next.config.ts`** — добавить redirect:
```ts
async redirects() {
  return [
    {
      source: '/:path*',
      has: [{ type: 'host', value: 'fixcraftvp.com' }],
      destination: 'https://www.fixcraftvp.com/:path*',
      permanent: true, // 301 redirect
    },
  ]
},
```

---

### 2. Добавить телефон на сайт (NAP для Local SEO)

**Проблема:** Нет телефона → -15 пунктов в Local SEO. Google Business требует NAP (Name, Address, Phone) на сайте.

**В Header/Navbar** — добавить ссылку:
```tsx
<a 
  href="tel:+17042091800"
  className="flex items-center gap-2 text-sm font-medium"
  aria-label="Call FixCraft VP"
>
  📞 (704) 209-1800
</a>
```

**В Footer** — добавить блок контактов:
```tsx
<address className="not-italic">
  <p>📍 Charlotte, NC 28202</p>
  <p>📞 <a href="tel:+17042091800">(704) 209-1800</a></p>
  <p>✉️ <a href="mailto:info@fixcraftvp.com">info@fixcraftvp.com</a></p>
</address>
```

> ⚠️ Номер телефона: уточни у Владимира реальный номер перед публикацией!

---

### 3. JSON-LD Schema — добавить telephone

**Файл: `src/app/layout.tsx`** — найти JSON-LD schema и добавить поле:
```json
{
  "@context": "https://schema.org",
  "@type": ["LocalBusiness", "HomeAndConstructionBusiness"],
  "name": "FixCraft VP",
  "url": "https://www.fixcraftvp.com",
  "telephone": "+17042091800",   ← ДОБАВИТЬ ЭТУ СТРОКУ
  ...
}
```

---

## 🟡 ПРИОРИТЕТ 2 — Важно (делай после Приоритета 1)

### 4. Alt тексты для изображений

**Найти все изображения без описательного alt:**
```bash
grep -rn 'alt=""' src/
grep -rn '<Image' src/ | grep -v 'alt='
```

**Заменить пустые/общие alt на описательные:**
```tsx
// Было:
<Image src="/hero.jpg" alt="" />
<Image src="/service.jpg" alt="image" />

// Стало:
<Image src="/hero.jpg" alt="Professional furniture assembly in Charlotte NC" />
<Image src="/ikea.jpg" alt="IKEA furniture assembly service Charlotte NC" />
<Image src="/tv-mount.jpg" alt="TV wall mounting service Charlotte NC by FixCraft VP" />
<Image src="/gallery.jpg" alt="Pottery Barn furniture assembled in Charlotte NC" />
```

---

### 5. Создать страницу /services (сейчас 404!)

**Проблема:** В навигации есть ссылка на `/services`, но страница возвращает 404. Это убивает авторитет и создаёт плохой UX.

**Вариант А:** Создать страницу `src/app/services/page.tsx` с описанием всех услуг
**Вариант Б:** Заменить ссылку в навигации на существующую страницу

Уточни у Владимира что предпочтительнее.

---

### 6. Open Graph image — указать конкретный URL

**Текущее:** `og:image` указывает на `https://fixcraftvp.com/opengraph-image` (без www)
**Исправить на:** `https://www.fixcraftvp.com/opengraph-image`

---

## ✅ НЕ ТРОГАТЬ (уже настроено правильно)

- robots.txt — корректный
- sitemap.xml — 20 страниц, все нужные есть
- Twitter Card теги — есть
- Viewport meta — есть
- HTTPS — включён
- Heading structure (H1→H2→H3) — правильная
- Title tag на главной — хороший
- Meta description на главной — хорошая
- Structured data базовая — есть (только телефон добавить)

---

## 📝 После внесения фиксов

1. Переиндексировать через Google Search Console: Inspect URL → Request Indexing
2. Проверить canonical через: `curl -I https://fixcraftvp.com` → должен вернуть 301 на www
3. Проверить schema через: https://validator.schema.org (вставить URL)
4. Проверить meta через: https://metatags.io

---

*Составила: Маша | Дата: 2026-04-03*
*Приоритет: Canonical + Телефон делать в первую очередь — это прямое влияние на Local SEO*
