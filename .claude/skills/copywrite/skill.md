---
name: copywrite
description: Generate professional marketing copy, website text, SEO descriptions, social media posts, emails, and any business content. Supports Russian and English.
argument-hint: "[type: website/email/social/ad/seo] [topic or business name]"
allowed-tools: Read, Grep, Glob, WebSearch, Write
---

# Professional Copywriter

Generate high-quality marketing and business text content.

## Arguments

Parse `$ARGUMENTS` for content type and topic.
If no arguments — ask what type of content is needed.

## Content Types

### website — Website Copy
- Hero section (headline + subheadline + CTA)
- About page
- Services descriptions
- Testimonials templates
- FAQ section
- Privacy policy / Terms of service

### email — Email Marketing
- Welcome emails
- Newsletter templates
- Cold outreach
- Follow-up sequences
- Promotional campaigns

### social — Social Media
- Instagram/Facebook posts
- Twitter/X threads
- LinkedIn posts
- YouTube descriptions
- TikTok scripts

### ad — Advertising
- Google Ads copy (headlines + descriptions)
- Facebook/Instagram ad copy
- Landing page headlines
- A/B test variants

### seo — SEO Content
- Meta titles and descriptions
- Blog post outlines
- Keyword-optimized content
- Alt text for images

## Process

1. If a project path exists in current directory — read existing content for context and tone
2. Ask for target audience if not obvious
3. Generate 2-3 variants for headlines/short copy
4. Use the business context from memory (FixCraft = handyman, etc.)
5. Output in both Russian AND English if the project serves both audiences

## Quality Rules
- No generic filler text ("Lorem ipsum", "We are the best")
- Every sentence must add value
- Include specific numbers and details where possible
- Match the tone to the business (professional, friendly, technical)
- SEO: include natural keyword placement
- CTA: every page section should have a clear next step

## Output Format
Deliver copy in markdown, ready to paste into code. Include comments like `<!-- Hero Section -->` for easy placement.
