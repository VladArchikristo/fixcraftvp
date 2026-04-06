---
name: seo
description: SEO audit and optimization for websites. Analyze meta tags, performance, accessibility, keywords, and generate recommendations.
argument-hint: "[url or project path]"
allowed-tools: Bash, Read, Grep, Glob, WebSearch, WebFetch, Agent
---

# SEO Analyzer & Optimizer

Full SEO audit and optimization for web projects.

## Target

If `$ARGUMENTS` is a URL — fetch and analyze the live page.
If `$ARGUMENTS` is a path — analyze source code directly.
If empty — analyze current directory project.

## Audit Checks

### 1. Meta Tags
- Title tag: exists, length (50-60 chars), includes keywords
- Meta description: exists, length (150-160 chars), compelling
- Open Graph tags (og:title, og:description, og:image)
- Twitter Card tags
- Canonical URL
- Robots meta
- Viewport meta

### 2. Content Analysis
- H1 tag: exactly one per page, includes main keyword
- Heading hierarchy: H1 → H2 → H3 (no skipping)
- Image alt texts: all images must have descriptive alt
- Internal links: check for broken links
- Word count per page (minimum 300 for SEO)
- Keyword density analysis

### 3. Technical SEO
- sitemap.xml exists
- robots.txt exists and configured
- Page load performance (Lighthouse via CLI if available)
- Mobile-responsive check
- HTTPS check
- Structured data (JSON-LD schema)
- 404 page exists

### 4. Performance Impact on SEO
- Image optimization (format, size, lazy loading)
- JavaScript bundle size
- CSS optimization
- Core Web Vitals indicators

### 5. Local SEO (for business sites)
- NAP consistency (Name, Address, Phone)
- Google Business schema markup
- Local keywords usage
- Service area pages

## Output

```
=== SEO AUDIT ===

Score: 72/100

Critical (fix now):
  [FAIL] Missing meta descriptions on 3 pages
  [FAIL] No sitemap.xml

Warnings:
  [WARN] Images without alt text: 5
  [WARN] H1 missing on /pricing

Good:
  [PASS] Title tags on all pages
  [PASS] Mobile responsive
  [PASS] HTTPS enabled

Recommendations:
1. Add meta descriptions to...
2. Create sitemap.xml...
3. Add alt text to...
```

## Auto-Fix Mode
If user confirms, automatically:
- Add missing meta tags to layout.tsx
- Generate sitemap.xml
- Add alt texts to images
- Create robots.txt
- Add JSON-LD structured data
