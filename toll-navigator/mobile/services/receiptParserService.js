/**
 * receiptParserService.js — AI Receipt Parser for Toll Navigator
 *
 * Parses OCR text from truck stop / fuel receipts.
 * Vendor classification is rule-based (no internet needed).
 * OCR scanning delegates to ocrService (ML Kit on-device + API fallback).
 *
 * Usage:
 *   import receiptParserService from './receiptParserService';
 *   const parsed = receiptParserService.parseReceiptText(ocrText);
 *   const parsed = await receiptParserService.scanAndParse(imageUri);
 */

import * as FileSystem from 'expo-file-system';
import { extractTextFromBase64 } from './ocrService';

// ─────────────────────────────────────────────────────────────────────────────
// Vendor classification tables
// ─────────────────────────────────────────────────────────────────────────────

const DIESEL_VENDORS = [
  'LOVES', "LOVE'S", 'PILOT', 'FLYING J', 'TA ', 'TRAVEL CENTERS',
  'PETRO', 'SAPP BROS', 'KWIK TRIP', 'CASEY', 'CIRCLE K DIESEL',
  'MARATHON', 'SUNOCO ULTRA', 'SPEEDCO',
];

const FOOD_VENDORS = [
  'MCDONALD', 'SUBWAY', 'BURGER KING', 'WENDYS', "WENDY'S",
  'LOVES DELI', 'PILOT DELI', 'FLYING J DELI',
  'DENNYS', "DENNY'S", 'WAFFLE HOUSE', 'IHOP',
];

const MAINTENANCE_VENDORS = [
  'GOODYEAR', 'BRIDGESTONE', 'MICHELIN', 'LOVES TIRE', 'TA TRUCK SERVICE',
  'SPEEDCO', 'PETRO LUBE', 'JIFFY LUBE', 'NAPA', 'AUTOZONE', 'OREILLY',
  "O'REILLY",
];

const HOTEL_VENDORS = [
  'BEST WESTERN', 'DAYS INN', 'COMFORT INN', 'SUPER 8', 'MOTEL 6',
  'HAMPTON INN', 'MARRIOTT', 'HILTON',
  'PILOT SHOWER', 'LOVES SHOWER', "LOVE'S SHOWER", 'TA SHOWER',
];

// 48 continental US state codes (+ DC)
const CONTINENTAL_STATES = new Set([
  'AL','AR','AZ','CA','CO','CT','DC','DE','FL','GA',
  'IA','ID','IL','IN','KS','KY','LA','MA','MD','ME',
  'MI','MN','MO','MS','MT','NC','ND','NE','NH','NJ',
  'NM','NV','NY','OH','OK','OR','PA','RI','SC','SD',
  'TN','TX','UT','VA','VT','WA','WI','WV','WY',
]);

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Normalise an amount string like "302,41" or "302.41" → 302.41
 */
function parseAmount(str) {
  if (!str) return null;
  const normalised = str.replace(',', '.');
  const val = parseFloat(normalised);
  return isNaN(val) ? null : Math.round(val * 100) / 100;
}

/**
 * Detect the suggested category from the upper-cased OCR text.
 * Returns one of: 'diesel'|'maintenance'|'food'|'hotel'|'permits'|'other'
 */
function classifyCategory(upper) {
  for (const v of MAINTENANCE_VENDORS) {
    if (upper.includes(v)) return 'maintenance';
  }
  for (const v of HOTEL_VENDORS) {
    if (upper.includes(v)) return 'hotel';
  }
  for (const v of FOOD_VENDORS) {
    if (upper.includes(v)) return 'food';
  }
  for (const v of DIESEL_VENDORS) {
    if (upper.includes(v)) return 'diesel';
  }
  // Keyword fallback
  if (/\bDIESEL\b|\bFUEL\b|\bGALLONS?\b/.test(upper)) return 'diesel';
  if (/\bTIRE|\bLUBE|\bOIL CHANGE|\bSERVICE CENTER/.test(upper)) return 'maintenance';
  if (/\bHOTEL|\bMOTEL|\bINN\b|\bSUITES?\b/.test(upper)) return 'hotel';
  if (/\bPERMIT|\bIFTA|\bWEIGH STATION/.test(upper)) return 'permits';
  return 'other';
}

/**
 * Extract vendor name: first non-empty line from the OCR text (typically the
 * header of a printed receipt).
 */
function extractVendor(lines) {
  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.length > 2) return trimmed;
  }
  return null;
}

/**
 * Extract the most likely total amount.
 * Priority: explicit TOTAL line → largest dollar amount in the text.
 */
function extractAmount(upper) {
  // 1. Explicit TOTAL (not SUBTOTAL)
  const totalMatch = upper.match(/(?<!SUB)TOTAL[^$\d]*\$?\s*(\d{1,4}[.,]\d{2})/i);
  if (totalMatch) return parseAmount(totalMatch[1]);

  // 2. Largest dollar amount on the receipt
  const allAmounts = [];
  const amountRe = /\$?\s*(\d{1,4}[.,]\d{2})/g;
  let m;
  while ((m = amountRe.exec(upper)) !== null) {
    const val = parseAmount(m[1]);
    if (val !== null) allAmounts.push(val);
  }
  if (allAmounts.length > 0) return Math.max(...allAmounts);
  return null;
}

/**
 * Extract gallons and price-per-gallon.
 * Returns { gallons, pricePerGallon }.
 */
function extractFuelData(upper) {
  let gallons = null;
  let pricePerGallon = null;

  // Pattern: "DIESEL 87.435 GAL @ $3.459"  or  "87.435 GALLONS"
  const galMatch = upper.match(/(\d+[.,]\d{1,3})\s*(?:GAL\b|GALLONS?)/i);
  if (galMatch) gallons = parseFloat(galMatch[1].replace(',', '.'));

  // Pattern: "DIESEL 87.435 3.459" (gallons then PPG on same line)
  const dieselLine = upper.match(/DIESEL\s+(\d+[.,]\d{3})\s+(\d+[.,]\d{3})/i);
  if (dieselLine) {
    if (!gallons) gallons = parseFloat(dieselLine[1].replace(',', '.'));
    pricePerGallon = parseFloat(dieselLine[2].replace(',', '.'));
  }

  // Pattern: "@ $3.459" or "@ 3.459/GAL"
  if (!pricePerGallon) {
    const ppgMatch = upper.match(/@\s*\$?\s*(\d+[.,]\d{2,3})/);
    if (ppgMatch) pricePerGallon = parseFloat(ppgMatch[1].replace(',', '.'));
  }

  return { gallons, pricePerGallon };
}

/**
 * Extract 2-letter US state code from a zip-code address pattern.
 * e.g. "OKLAHOMA CITY OK 73101"
 */
function extractState(upper) {
  const zipRe = /\b([A-Z]{2})\s+\d{5}\b/g;
  let m;
  while ((m = zipRe.exec(upper)) !== null) {
    if (CONTINENTAL_STATES.has(m[1])) return m[1];
  }
  return null;
}

/**
 * Parse an approximate ISO date from the receipt.
 * Looks for MM/DD/YYYY, MM-DD-YYYY, or YYYY-MM-DD patterns.
 */
function extractDate(text) {
  // ISO-like: 2024-12-31
  let m = text.match(/\b(\d{4}-\d{2}-\d{2})\b/);
  if (m) return m[1];

  // US: 12/31/2024 or 12-31-2024
  m = text.match(/\b(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})\b/);
  if (m) {
    const [, mm, dd, yyyy] = m;
    return `${yyyy}-${mm.padStart(2,'0')}-${dd.padStart(2,'0')}`;
  }

  return null;
}

/**
 * Rough confidence score based on how many fields were successfully parsed.
 */
function calcConfidence(parsed) {
  const fields = ['amount','vendor','date','state'];
  const found = fields.filter(f => parsed[f] !== null).length;
  // Base 0.3 for having any text + up to 0.7 for filled fields
  return Math.round((0.3 + (found / fields.length) * 0.7) * 100) / 100;
}

// ─────────────────────────────────────────────────────────────────────────────
// Public API
// ─────────────────────────────────────────────────────────────────────────────

const receiptParserService = {
  /**
   * Parse OCR text and return a structured ParsedReceipt object.
   *
   * @param {string} ocrText
   * @returns {{
   *   amount: number|null,
   *   vendor: string|null,
   *   date: string|null,
   *   gallons: number|null,
   *   pricePerGallon: number|null,
   *   state: string|null,
   *   suggestedCategory: string,
   *   confidence: number,
   *   rawText: string
   * }}
   */
  parseReceiptText(ocrText) {
    const raw = ocrText || '';
    const upper = raw.toUpperCase();
    const lines = raw.split(/\r?\n/);

    const amount = extractAmount(upper);
    const vendor = extractVendor(lines);
    const date   = extractDate(raw);
    const { gallons, pricePerGallon } = extractFuelData(upper);
    const state  = extractState(upper);
    const suggestedCategory = classifyCategory(upper);

    const partial = { amount, vendor, date, state };
    const confidence = calcConfidence(partial);

    return {
      amount,
      vendor,
      date,
      gallons,
      pricePerGallon,
      state,
      suggestedCategory,
      confidence,
      rawText: raw,
    };
  },

  /**
   * Read an image URI, run OCR via ML Kit (or API fallback), then parse.
   *
   * @param {string} imageUri  — local file URI (file://) or content URI
   * @returns {Promise<ParsedReceipt>}
   */
  async scanAndParse(imageUri) {
    // Read file as base64 for ocrService
    const base64 = await FileSystem.readAsStringAsync(imageUri, {
      encoding: FileSystem.EncodingType.Base64,
    });

    const ocrResult = await extractTextFromBase64(base64);
    const parsed    = receiptParserService.parseReceiptText(ocrResult.text);

    // Blend OCR confidence into our receipt confidence
    if (ocrResult.confidence != null) {
      parsed.confidence = Math.round(
        ((parsed.confidence + ocrResult.confidence) / 2) * 100
      ) / 100;
    }

    return parsed;
  },

  /**
   * Check if any user-learned vendor mapping matches the text.
   * learnedVendors: { 'PILOT FLYING J': 'diesel', 'LOVES': 'diesel', ... }
   *
   * @param {string} text
   * @param {Record<string, string>} learnedVendors
   * @returns {string|null}  category or null if no match
   */
  applyLearnedVendors(text, learnedVendors) {
    if (!text || !learnedVendors) return null;
    const upper = text.toUpperCase();
    for (const [vendorKey, category] of Object.entries(learnedVendors)) {
      if (upper.includes(vendorKey.toUpperCase())) return category;
    }
    return null;
  },
};

export default receiptParserService;
