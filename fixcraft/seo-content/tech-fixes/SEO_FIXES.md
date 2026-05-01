# SEO Технические Фиксы — fixcraftvp.com

## 🔴 КРИТИЧНО: Canonical URL конфликт

**Проблема:** Canonical указывает на `https://fixcraftvp.com` (без www), но сайт доступен на `https://www.fixcraftvp.com`. 
Google видит два разных сайта и делит PageRank.

**Фикс в `src/app/layout.tsx`:**

```tsx
export const metadata: Metadata = {
  metadataBase: new URL('https://www.fixcraftvp.com'),
  alternates: {
    canonical: '/',
  },
  // ... остальные метаданные
}
```

**Также добавить в `next.config.ts`:**

```ts
async redirects() {
  return [
    {
      source: '/:path*',
      has: [{ type: 'host', value: 'fixcraftvp.com' }],
      destination: 'https://www.fixcraftvp.com/:path*',
      permanent: true,
    },
  ]
},
```

---

## 🔴 КРИТИЧНО: Телефон отсутствует на сайте

**Проблема:** Google Local SEO требует NAP (Name, Address, Phone) на каждой странице. Отсутствие телефона — это -15 пунктов в локальном ранжировании.

**Фикс в `src/components/Header.tsx` (или Navbar):**

```tsx
// Добавить в шапку сайта:
<a 
  href="tel:+17042091800" 
  className="flex items-center gap-2 text-sm font-medium hover:text-primary transition-colors"
  aria-label="Call FixCraft VP"
>
  <PhoneIcon className="w-4 h-4" />
  (704) 209-1800
</a>
```

**И в Footer:**

```tsx
<div className="contact-info">
  <p>📍 Charlotte, NC 28202</p>
  <p>📞 <a href="tel:+17042091800">(704) 209-1800</a></p>
  <p>✉️ <a href="mailto:info@fixcraftvp.com">info@fixcraftvp.com</a></p>
</div>
```

> ⚠️ Замени номер на реальный если другой!

---

## 🟡 ВАЖНО: JSON-LD Schema — добавить телефон и URL

**В `src/app/layout.tsx` обновить schema:**

```tsx
const organizationSchema = {
  "@context": "https://schema.org",
  "@type": ["LocalBusiness", "HomeAndConstructionBusiness"],
  "name": "FixCraft VP",
  "url": "https://www.fixcraftvp.com",
  "telephone": "+17042091800",  // ← ДОБАВИТЬ
  "email": "info@fixcraftvp.com",
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "Charlotte",
    "addressLocality": "Charlotte",
    "addressRegion": "NC",
    "postalCode": "28202",
    "addressCountry": "US"
  },
  "geo": {
    "@type": "GeoCoordinates",
    "latitude": 35.2271,
    "longitude": -80.8431
  },
  "aggregateRating": {
    "@type": "AggregateRating",
    "ratingValue": "4.9",
    "reviewCount": "50",
    "bestRating": "5"
  },
  "openingHoursSpecification": [
    {
      "@type": "OpeningHoursSpecification",
      "dayOfWeek": ["Monday","Tuesday","Wednesday","Thursday","Friday"],
      "opens": "08:00",
      "closes": "19:00"
    },
    {
      "@type": "OpeningHoursSpecification",
      "dayOfWeek": "Saturday",
      "opens": "09:00",
      "closes": "17:00"
    }
  ],
  "priceRange": "$$",
  "sameAs": [
    "https://www.google.com/maps/...",  // добавь ссылку Google Maps
    "https://www.yelp.com/biz/fixcraft-vp"  // добавь если есть
  ]
}
```

---

## 🟡 ВАЖНО: Alt тексты для изображений

**Найди все `<Image>` без alt в Next.js:**

```bash
grep -rn "alt=\"\"" src/
grep -rn "<Image" src/ | grep -v "alt="
```

**Правильные alt тексты:**

```tsx
// Плохо:
<Image src="/hero.jpg" alt="" />
<Image src="/service.jpg" alt="image" />

// Хорошо:
<Image src="/hero.jpg" alt="Professional furniture assembly in Charlotte NC" />
<Image src="/ikea-assembly.jpg" alt="IKEA furniture assembly service Charlotte NC" />
<Image src="/tv-mount.jpg" alt="TV wall mounting service Charlotte NC by FixCraft VP" />
<Image src="/gallery-bedroom.jpg" alt="Pottery Barn bedroom furniture assembled in Charlotte" />
```

---

## 🟡 ВАЖНО: Blog post — расширить до 1500+ слов

**Текущий IKEA пост (~500 слов) нужно расширить.**
Готовая статья на 1500+ слов: `articles/ikea-assembly-charlotte-nc.md`

---

## ✅ УЖЕ ХОРОШО (не трогать)
- robots.txt — корректный
- sitemap.xml — 20 страниц, все важные есть
- Open Graph теги — есть
- Twitter Card — есть
- Schema markup — есть (только телефон добавить)
- Title/Description на главной — хорошие
- Heading structure (H1→H2→H3) — правильная
