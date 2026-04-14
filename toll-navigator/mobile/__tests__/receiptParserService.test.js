/**
 * Tests for receiptParserService.js
 *
 * Pure logic tests — no native modules required.
 * Uses mocked ocrService and expo-file-system for scanAndParse.
 */

// ─────────────────────────────────────────────────────────────────────────────
// Module mocks (must be before require)
// ─────────────────────────────────────────────────────────────────────────────

jest.mock('../services/ocrService', () => ({
  extractTextFromBase64: jest.fn(),
  isMlKitAvailable: jest.fn(() => false),
  OCR_SOURCE: { ML_KIT: 'mlkit', API: 'api', FALLBACK: 'fallback' },
}));

jest.mock('expo-file-system', () => ({
  readAsStringAsync: jest.fn(),
  EncodingType: { Base64: 'base64' },
  cacheDirectory: '/tmp/',
  writeAsStringAsync: jest.fn(),
  deleteAsync: jest.fn(),
}));

const receiptParserService = require('../services/receiptParserService').default;

// ─────────────────────────────────────────────────────────────────────────────
// parseReceiptText — Loves Travel Stop (diesel)
// ─────────────────────────────────────────────────────────────────────────────

describe('parseReceiptText — Loves Travel Stop diesel', () => {
  const ocrText = [
    "LOVES TRAVEL STOP #450",
    "1234 HIGHWAY 40",
    "OKLAHOMA CITY OK 73101",
    "DIESEL 87.435 GAL @ $3.459",
    "TOTAL: $302.41",
  ].join('\n');

  let result;
  beforeAll(() => {
    result = receiptParserService.parseReceiptText(ocrText);
  });

  test('amount = 302.41', () => {
    expect(result.amount).toBe(302.41);
  });

  test('vendor = first line', () => {
    expect(result.vendor).toBe('LOVES TRAVEL STOP #450');
  });

  test('state = OK', () => {
    expect(result.state).toBe('OK');
  });

  test('gallons parsed', () => {
    expect(result.gallons).toBeCloseTo(87.435, 3);
  });

  test('pricePerGallon parsed', () => {
    expect(result.pricePerGallon).toBeCloseTo(3.459, 3);
  });

  test('suggestedCategory = diesel', () => {
    expect(result.suggestedCategory).toBe('diesel');
  });

  test('confidence > 0.5', () => {
    expect(result.confidence).toBeGreaterThan(0.5);
  });

  test('rawText preserved', () => {
    expect(result.rawText).toBe(ocrText);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// parseReceiptText — Goodyear maintenance
// ─────────────────────────────────────────────────────────────────────────────

describe('parseReceiptText — Goodyear maintenance', () => {
  const ocrText = [
    "GOODYEAR TIRE & RUBBER CO",
    "TRUCK SERVICE CENTER",
    "2850 INDUSTRIAL BLVD",
    "ALBUQUERQUE NM 87107",
    "LABOR: 2 TIRES MOUNTED",
    "TIRES: 2X 295/75R22.5",
    "TOTAL DUE: $847.00",
  ].join('\n');

  let result;
  beforeAll(() => {
    result = receiptParserService.parseReceiptText(ocrText);
  });

  test('amount = 847.00', () => {
    expect(result.amount).toBe(847.00);
  });

  test('suggestedCategory = maintenance', () => {
    expect(result.suggestedCategory).toBe('maintenance');
  });

  test('state = NM', () => {
    expect(result.state).toBe('NM');
  });

  test('gallons = null (not a fuel receipt)', () => {
    expect(result.gallons).toBeNull();
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// parseReceiptText — McDonald's food
// ─────────────────────────────────────────────────────────────────────────────

describe('parseReceiptText — McDonald\'s food', () => {
  const ocrText = [
    "MCDONALD'S #12847",
    "5500 E INTERSTATE 40",
    "AMARILLO TX 79118",
    "1 BIG MAC        $5.49",
    "1 MEDIUM FRY     $3.29",
    "1 COFFEE         $1.59",
    "SUBTOTAL:       $10.37",
    "TAX:             $0.91",
    "TOTAL           $14.73",
  ].join('\n');

  let result;
  beforeAll(() => {
    result = receiptParserService.parseReceiptText(ocrText);
  });

  test('amount = 14.73 (largest TOTAL)', () => {
    expect(result.amount).toBe(14.73);
  });

  test('suggestedCategory = food', () => {
    expect(result.suggestedCategory).toBe('food');
  });

  test('state = TX', () => {
    expect(result.state).toBe('TX');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// parseReceiptText — hotel
// ─────────────────────────────────────────────────────────────────────────────

describe('parseReceiptText — Best Western hotel', () => {
  const ocrText = [
    "BEST WESTERN PLUS",
    "123 MAIN ST",
    "MEMPHIS TN 38103",
    "1 NIGHT STAY",
    "ROOM RATE: $89.00",
    "TAX: $11.00",
    "TOTAL: $100.00",
  ].join('\n');

  let result;
  beforeAll(() => {
    result = receiptParserService.parseReceiptText(ocrText);
  });

  test('suggestedCategory = hotel', () => {
    expect(result.suggestedCategory).toBe('hotel');
  });

  test('amount = 100.00', () => {
    expect(result.amount).toBe(100.00);
  });

  test('state = TN', () => {
    expect(result.state).toBe('TN');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// parseReceiptText — date extraction
// ─────────────────────────────────────────────────────────────────────────────

describe('parseReceiptText — date extraction', () => {
  test('parses US date format MM/DD/YYYY', () => {
    const text = "PILOT TRAVEL CENTER\nDATE: 03/15/2025\nTOTAL: $250.00";
    const result = receiptParserService.parseReceiptText(text);
    expect(result.date).toBe('2025-03-15');
  });

  test('parses ISO date format YYYY-MM-DD', () => {
    const text = "FLYING J\n2025-07-04\nTOTAL: $180.00";
    const result = receiptParserService.parseReceiptText(text);
    expect(result.date).toBe('2025-07-04');
  });

  test('returns null when no date present', () => {
    const text = "SOME STORE\nTOTAL: $10.00";
    const result = receiptParserService.parseReceiptText(text);
    expect(result.date).toBeNull();
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// parseReceiptText — edge cases
// ─────────────────────────────────────────────────────────────────────────────

describe('parseReceiptText — edge cases', () => {
  test('empty string returns nulls and other category', () => {
    const result = receiptParserService.parseReceiptText('');
    expect(result.amount).toBeNull();
    expect(result.vendor).toBeNull();
    expect(result.suggestedCategory).toBe('other');
    expect(result.confidence).toBeGreaterThanOrEqual(0);
  });

  test('amount with comma decimal (302,41) is parsed correctly', () => {
    const text = "SOME STOP\nTOTAL: 302,41";
    const result = receiptParserService.parseReceiptText(text);
    expect(result.amount).toBe(302.41);
  });

  test('unknown vendor returns suggestedCategory other', () => {
    const text = "RANDOM UNKNOWN SHOP\n100 MAIN ST\nKANSAS CITY MO 64101\nTOTAL: $50.00";
    const result = receiptParserService.parseReceiptText(text);
    expect(result.suggestedCategory).toBe('other');
  });

  test('SPEEDCO classified as maintenance (dual-purpose vendor)', () => {
    const text = "SPEEDCO LUBE & TIRE\nTOTAL: $150.00";
    const result = receiptParserService.parseReceiptText(text);
    expect(result.suggestedCategory).toBe('maintenance');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// applyLearnedVendors
// ─────────────────────────────────────────────────────────────────────────────

describe('applyLearnedVendors', () => {
  const learned = {
    'PILOT FLYING J': 'diesel',
    'LOCAL DINER': 'food',
  };

  test('matches known learned vendor', () => {
    const result = receiptParserService.applyLearnedVendors(
      'PILOT FLYING J #221\nTOTAL: $300', learned
    );
    expect(result).toBe('diesel');
  });

  test('returns null when no match', () => {
    const result = receiptParserService.applyLearnedVendors(
      'RANDOM PLACE\nTOTAL: $20', learned
    );
    expect(result).toBeNull();
  });

  test('case-insensitive matching', () => {
    const result = receiptParserService.applyLearnedVendors(
      'local diner downtown', learned
    );
    expect(result).toBe('food');
  });

  test('null text returns null', () => {
    expect(receiptParserService.applyLearnedVendors(null, learned)).toBeNull();
  });

  test('null learnedVendors returns null', () => {
    expect(receiptParserService.applyLearnedVendors('some text', null)).toBeNull();
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// scanAndParse — mocked OCR
// ─────────────────────────────────────────────────────────────────────────────

describe('scanAndParse', () => {
  const { extractTextFromBase64 } = require('../services/ocrService');
  const FileSystem = require('expo-file-system');

  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('reads file, calls OCR, returns parsed receipt', async () => {
    FileSystem.readAsStringAsync.mockResolvedValue('base64imagedata');
    extractTextFromBase64.mockResolvedValue({
      text: "LOVES TRAVEL STOP #111\nOKLAHOMA CITY OK 73101\nDIESEL 50.000 GAL @ $3.500\nTOTAL: $175.00",
      source: 'mlkit',
      confidence: 0.92,
    });

    const result = await receiptParserService.scanAndParse('file:///path/to/image.jpg');

    expect(FileSystem.readAsStringAsync).toHaveBeenCalledWith(
      'file:///path/to/image.jpg',
      { encoding: 'base64' }
    );
    expect(extractTextFromBase64).toHaveBeenCalledWith('base64imagedata');
    expect(result.amount).toBe(175.00);
    expect(result.suggestedCategory).toBe('diesel');
    expect(result.state).toBe('OK');
    // Confidence should blend OCR confidence
    expect(result.confidence).toBeGreaterThan(0.5);
  });

  test('blends OCR confidence when provided', async () => {
    FileSystem.readAsStringAsync.mockResolvedValue('b64');
    extractTextFromBase64.mockResolvedValue({
      text: "GOODYEAR TRUCK\nTOTAL DUE: $500.00",
      source: 'mlkit',
      confidence: 0.8,
    });

    const result = await receiptParserService.scanAndParse('file:///img.jpg');
    // receipt confidence for 2 fields found (vendor + amount) = 0.3 + (2/4)*0.7 = 0.65
    // blended with 0.8 → (0.65 + 0.8) / 2 = 0.725
    expect(result.confidence).toBeCloseTo(0.73, 1);
  });

  test('works without OCR confidence (null)', async () => {
    FileSystem.readAsStringAsync.mockResolvedValue('b64');
    extractTextFromBase64.mockResolvedValue({
      text: "MCDONALD'S\nTOTAL $10.00",
      source: 'api',
      confidence: null,
    });

    const result = await receiptParserService.scanAndParse('file:///img.jpg');
    expect(result.suggestedCategory).toBe('food');
    expect(result.confidence).toBeGreaterThan(0);
  });
});
