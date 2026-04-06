---
name: landing
description: Create high-converting landing pages with animations, forms, and optimized copy. Single-page sites for products, services, or events.
argument-hint: "[product/service name] [goal: leads/sales/signup]"
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent, WebSearch
---

# Landing Page Builder

Create conversion-optimized landing pages fast.

## Arguments

- Product/service name and conversion goal
- Example: `/landing "AI Bot Service" leads`

## Structure (proven high-conversion layout)

### Above the Fold
1. **Headline** — clear value proposition (max 10 words)
2. **Subheadline** — supporting detail (1-2 sentences)
3. **CTA Button** — primary action
4. **Hero visual** — placeholder or animation

### Body Sections
5. **Problem** — what pain does the customer have?
6. **Solution** — how your product solves it
7. **Features/Benefits** — 3-4 key benefits with icons
8. **Social Proof** — testimonials, logos, numbers
9. **How It Works** — 3 simple steps
10. **Pricing** — clear pricing or "Get a Quote"
11. **FAQ** — 4-6 common questions
12. **Final CTA** — repeat the main call to action

### Footer
13. Contact info, legal links, social media

## Tech Stack

- Next.js (or plain HTML if requested)
- Tailwind CSS
- Framer Motion animations
- Contact form with API route
- Mobile-first responsive design

## Procedure

1. Ask for: business name, target audience, main benefit, preferred colors
2. Generate complete page code
3. Create project structure
4. Run `npm install && npm run dev`
5. Open preview

## Optimization
- Lighthouse score target: 90+
- Mobile-first design
- Fast loading (no heavy images initially)
- SEO meta tags included
- Open Graph tags for social sharing
