---
name: scraper
description: Web scraping tool — extract data from websites, APIs, or pages. Supports structured data extraction, pagination, and export to JSON/CSV.
argument-hint: "[url] [what to extract]"
allowed-tools: Bash, Read, Write, WebFetch, WebSearch, Grep
---

# Web Scraper

Extract structured data from websites and APIs.

## Arguments

- URL and description of what to extract
- Example: `/scraper "https://example.com/products" "product names and prices"`

## Capabilities

### Page Scraping
- Extract text, links, images from HTML
- Parse tables into structured data
- Follow pagination (next page links)
- Handle dynamic content descriptions

### API Discovery
- Check for API endpoints (look for /api/, JSON responses)
- Test common API patterns
- Extract data from REST APIs

### Data Extraction Patterns
- **Lists** — product listings, directories, search results
- **Tables** — pricing tables, comparison charts, data tables
- **Cards** — blog posts, portfolio items, team members
- **Contact info** — emails, phones, addresses from pages

## Process

1. Fetch the target URL with WebFetch
2. Analyze page structure
3. Extract requested data
4. Clean and structure the data
5. Export to requested format

## Export Formats
- **JSON** — structured data file
- **CSV** — spreadsheet-ready
- **Markdown** — formatted table
- **TypeScript** — typed data array for code

## Output
```
=== SCRAPE COMPLETE ===
Source: https://example.com/products
Items extracted: 47
Format: JSON
Saved to: ~/Downloads/scraped-data.json
```

## Ethics & Safety
- Respect robots.txt
- Add reasonable delays between requests
- Don't scrape personal/private data
- Check terms of service
- Use for legitimate business purposes only
- Never bypass authentication or CAPTCHAs
