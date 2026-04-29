# FixCraft AI Estimator — Technical Specification
## Клон SimplyWise под FixCraft VP (Handyman, Charlotte NC)

---

## 🎯 Goal
Веб-приложение (PWA), где:
1. Клиент/Влад делает фото работы
2. AI (GPT-4o Vision / Claude) анализирует фото + описание
3. Генерирует детальную смету (материалы + работа) с ценами под Charlotte NC
4. Экспорт в branded PDF
5. Отправка клиенту по SMS/email

---

## 📱 Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 14 + Tailwind CSS + shadcn/ui |
| Backend | Next.js API Routes (Serverless) |
| Database | PostgreSQL (Neon или Supabase) |
| File Storage | Supabase Storage / AWS S3 |
| AI Vision | OpenAI GPT-4o Vision (или Anthropic Claude 3 when ready) |
| PDF Generation | Puppeteer + HTML template / react-pdf |
| Auth | NextAuth.js (Google OAuth) |
| Hosting | Vercel |
| SMS | Twilio |
| Email | Resend / Gmail API |

---

## 🏗️ Core Features (MVP Phase 1)

### 1. Photo Upload + AI Analysis
- Drag & drop или camera capture (mobile-optimized)
- Пользователь пишет описание: "Need to fix this door frame after tenant moved out"
- AI анализирует фото + текст, определяет:
  - Тип работы (drywall repair, door frame, painting, flooring, etc.)
  - Объём работы (sq ft, linear ft, etc.)
  - Материалы (sheetrock 1/2", joint compound, tape, primer, paint, etc.)
  - Трудоёмкость (hours)

### 2. Pricing Engine
- База цен на материалы (Home Depot API или хардкод для Charlotte):
  - Sheetrock 4x8: $12-15
  - Joint compound bucket: $18-25
  - Painter's tape: $6
  - Primer gallon: $25-35
  - Paint gallon: $35-55
  - Door frame kit: $45-80
  - Baseboard linear ft: $2-5
  - etc.
- Labor rates для Charlotte handyman:
  - Standard: $75-95/hour
  - Emergency/same-day: $120-150/hour
  - Minimum service call: $150-200
- Markup multiplier (настраивается Владом):
  - Materials markup: 1.3x (30%)
  - Labor markup: 1.0x (flat rate)
  - Overhead: 15%
  - Profit margin: 20%

### 3. Estimate Breakdown (Itemized)
```
FIXCRAFT VP — ESTIMATE
Client: [Name]
Address: [Address]
Date: [Date]

JOB: Drywall Repair + Door Frame

MATERIALS:
- 2x Sheetrock 4x8 (1/2") ............ $28.00
- 1x Joint compound (3.5 gal) ......... $22.00
- 1x Drywall tape (250 ft) ............ $8.50
- 1x Primer (1 gal) ................... $32.00
- 1x Paint (1 gal, semi-gloss) ........ $48.00
- Misc (sandpaper, screws, etc.) ...... $15.00
  Subtotal Materials .................. $153.50
  Materials Markup (30%) .............. $46.05

LABOR:
- Prep & demo (1.5 hrs) ............... $142.50
- Drywall install (2 hrs) ............. $190.00
- Mud/tape/sand (2.5 hrs) ............. $237.50
- Prime & paint (1.5 hrs) ............. $142.50
- Cleanup (0.5 hrs) ................... $47.50
  Subtotal Labor ...................... $760.00

OVERHEAD (15%) ........................ $114.00

TOTAL ESTIMATE ........................ $1,073.55

Valid for 30 days. 50% deposit required to schedule.
```

### 4. Branded PDF Export
- Header: FixCraft VP logo + contact info
- Professional layout (table-based)
- Terms & conditions footer
- Signature line
- "Accept Estimate" button (digital signature)

### 5. Client Portal
- Клиент получает ссылку на estimate
- Может просмотреть, скачать PDF, принять (Accept) или запросить изменения
- При принятии — уведомление Владу в Telegram/email

### 6. Dashboard (для Влада)
- Все estimates (Pending / Accepted / Declined / Completed)
- Revenue stats
- Conversion rate
- Average job value
- Photo gallery по проектам

---

## 🧠 AI Prompt Engineering

### Vision Analysis Prompt
```
You are an expert handyman estimator with 20+ years experience in Charlotte, NC.
Analyze the provided photo and description to create a detailed repair estimate.

Identify:
1. Type of repair needed
2. Materials required (be specific with quantities)
3. Estimated labor hours (be realistic)
4. Any safety concerns or code requirements
5. Potential hidden issues

Return ONLY a JSON object:
{
  "job_type": "drywall_repair",
  "description": "...",
  "materials": [
    {"item": "Sheetrock 4x8 1/2in", "qty": 2, "unit_price": 14.00, "notes": "..."}
  ],
  "labor_hours": 7.5,
  "labor_breakdown": [
    {"task": "Prep & demo", "hours": 1.5},
    {"task": "Drywall install", "hours": 2.0}
  ],
  "difficulty": "medium",
  "hidden_issues": ["..."],
  "notes": "..."
}
```

### Pricing Calculation (separate step)
```
Take the AI analysis and apply Charlotte NC handyman pricing:
- Labor rate: $95/hour (standard), $130/hour (emergency)
- Apply material markup: 1.3x
- Apply overhead: 15%
- Apply profit margin: 20%
- Minimum service call: $175

Generate final itemized estimate.
```

---

## 📊 Database Schema (simplified)

### estimates
- id (uuid)
- client_name
- client_phone
- client_email
- address
- photos[] (URLs)
- description
- ai_analysis (JSON)
- line_items (JSON)
- subtotal_materials
- subtotal_labor
- overhead_amount
- profit_amount
- total_amount
- status (draft / sent / accepted / declined / completed)
- created_at
- updated_at

### clients
- id
- name
- phone
- email
- address
- source (google / referral / repeat)
- created_at

### pricing_config (для Влада)
- labor_rate_standard
- labor_rate_emergency
- material_markup
- overhead_percent
- profit_margin_percent
- minimum_service_call

---

## 🎨 UI/UX Requirements

### Mobile-First (Vlad uses phone on job sites)
- Large buttons (thumb-friendly)
- Camera integration (direct photo capture)
- One-page estimate view
- Swipe gestures between photos

### Design System
- Primary: FixCraft brand color (orange/blue — whatever Vlad has)
- Clean, contractor-professional look
- Before/after photo comparison slider
- Progress indicators

### Pages
1. **/dashboard** — Overview + recent estimates
2. **/new-estimate** — Upload photos → Describe → AI Analysis → Review → Send
3. **/estimates/[id]** — Full estimate view
4. **/client/[id]** — Client history
5. **/settings** — Pricing config, profile, integrations

---

## 🔌 Integrations

### Phase 1 (MVP)
- [ ] OpenAI GPT-4o Vision API
- [ ] PDF generation
- [ ] Email sending (Resend)

### Phase 2
- [ ] Twilio SMS (send estimate link)
- [ ] Google Calendar (schedule jobs from accepted estimates)
- [ ] QuickBooks Online (invoice sync)
- [ ] Telegram bot (notify Vlad of new accepted estimates)

### Phase 3
- [ ] AI Before/After render (like SimplyWise)
- [ ] LiDAR room scanning (iOS only)
- [ ] Client signature collection
- [ ] Payment processing (Stripe)

---

## 💰 Cost to Build vs Buy

| | SimplyWise | Своё решение |
|---|---|---|
| Monthly | $29.99 | ~$20-50 (Vercel + DB + AI) |
| Setup | $0 | $0 (сам пишешь) |
| Кастомизация | Ограничена | Полная |
| Charlotte pricing | Generic | Exact |
| FixCraft branding | Нет | Полная |
| Telegram интеграция | Нет | Да |

---

## 🚀 Development Phases

### Phase 1 — MVP (2-3 недели)
- [ ] Next.js setup + auth
- [ ] Photo upload + storage
- [ ] AI vision integration
- [ ] Basic estimate generation
- [ ] PDF export
- [ ] Simple dashboard

### Phase 2 — Polish (1-2 недели)
- [ ] Mobile camera optimization
- [ ] Client shareable links
- [ ] Email/Telegram notifications
- [ ] Pricing config UI
- [ ] Better AI prompts

### Phase 3 — Scale
- [ ] SMS integration
- [ ] Calendar sync
- [ ] Analytics
- [ ] AI upsells

---

## 📁 Project Structure

```
fixcraft-estimator/
├── app/
│   ├── (dashboard)/
│   ├── new-estimate/
│   ├── api/
│   │   ├── analyze/
│   │   ├── estimates/
│   │   └── pdf/
│   └── layout.tsx
├── components/
│   ├── estimate/
│   ├── photo-upload/
│   └── ui/
├── lib/
│   ├── ai.ts
│   ├── pricing.ts
│   ├── pdf.ts
│   └── db.ts
├── types/
├── public/
└── codex.md
```

---

## ⚠️ Critical Notes for Developer

1. **AI costs**: GPT-4o Vision ~$0.005-0.015 per image. 100 estimates = ~$1-2.
2. **Photo quality**: Bad lighting/blurry photos = bad estimates. Add user guidance.
3. **Pricing accuracy**: AI gives rough estimates. Vlad MUST review before sending.
4. **Legal disclaimer**: Add "Estimate subject to on-site inspection" to every PDF.
5. **Mobile-first**: Vlad will use this on job sites with his phone. Performance critical.

---

Prepared for: FixCraft VP (EAST VLADIPRI INC)
Location: Charlotte, NC 28277
Target: Handyman / Small home repairs / Interior work
