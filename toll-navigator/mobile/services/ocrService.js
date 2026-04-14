/**
 * ocrService.js — Offline OCR using ML Kit Text Recognition
 *
 * ML Kit runs 100% on-device — no internet required.
 * Works with EAS custom builds (development client / production).
 * Falls back gracefully to backend API when ML Kit is unavailable
 * (e.g. plain Expo Go, or if the native module failed to load).
 *
 * Usage:
 *   import { extractTextFromBase64, OCR_SOURCE } from './ocrService';
 *   const { text, source, confidence } = await extractTextFromBase64(base64String);
 */

import * as FileSystem from 'expo-file-system';
import { extractTextOCR } from './api';

// Source labels returned with every result so the UI can show the user
// where the text came from.
export const OCR_SOURCE = {
  ML_KIT: 'mlkit',   // on-device, offline
  API:     'api',    // backend Google Vision / mock
  FALLBACK:'fallback', // parse error, empty result
};

/**
 * Try to import ML Kit lazily so the app doesn't crash when running
 * in plain Expo Go (where the native module is absent).
 */
let TextRecognition = null;
let mlKitAvailable = false;

try {
  // Dynamic require — bundler resolves at build time but won't throw at
  // import time inside a try/catch when the native module is missing.
  const mlKit = require('@react-native-ml-kit/text-recognition');
  TextRecognition = mlKit.default || mlKit.TextRecognition || mlKit;
  if (TextRecognition && typeof TextRecognition.recognize === 'function') {
    mlKitAvailable = true;
    console.log('[OCR] ML Kit loaded — offline OCR available');
  }
} catch (e) {
  console.log('[OCR] ML Kit not available, will use backend API:', e.message);
}

/**
 * Write base64 image data to a temp file and return its local URI.
 * ML Kit requires a file URI, not raw base64.
 */
async function base64ToTempFile(base64) {
  const tmpPath = `${FileSystem.cacheDirectory}ocr_tmp_${Date.now()}.jpg`;
  await FileSystem.writeAsStringAsync(tmpPath, base64, {
    encoding: FileSystem.EncodingType.Base64,
  });
  return tmpPath;
}

/**
 * Clean up temp file silently.
 */
async function deleteTempFile(uri) {
  try {
    await FileSystem.deleteAsync(uri, { idempotent: true });
  } catch (_) {}
}

/**
 * Run ML Kit OCR on a base64-encoded image.
 * Returns { text, source, blocks, lines }
 */
async function runMlKit(base64) {
  const tmpUri = await base64ToTempFile(base64);
  try {
    const result = await TextRecognition.recognize(tmpUri);
    const text = result?.text || '';
    const blocks = (result?.blocks || []).map(b => ({
      text:       b.text,
      confidence: b.confidence,
      lines:      (b.lines || []).map(l => l.text),
    }));
    return {
      text,
      source: OCR_SOURCE.ML_KIT,
      blocks,
      lines: blocks.flatMap(b => b.lines),
      confidence: blocks.length > 0
        ? blocks.reduce((s, b) => s + (b.confidence || 0), 0) / blocks.length
        : null,
    };
  } finally {
    await deleteTempFile(tmpUri);
  }
}

/**
 * Run backend OCR (Google Vision or mock).
 * Returns { text, source, mock }
 */
async function runApiOcr(base64) {
  const res = await extractTextOCR(base64);
  const text = res.data?.text || '';
  return {
    text,
    source: OCR_SOURCE.API,
    mock:   res.data?.mock || false,
    blocks: [],
    lines:  [],
    confidence: null,
  };
}

/**
 * Main entry point.
 *
 * @param {string} base64 - JPEG image as base64 string (no data-URI prefix)
 * @param {object} [opts]
 * @param {boolean} [opts.forceApi=false] - skip ML Kit and go straight to API
 * @returns {Promise<{text: string, source: string, mock?: boolean, blocks: Array, lines: Array, confidence: number|null}>}
 */
export async function extractTextFromBase64(base64, opts = {}) {
  const { forceApi = false } = opts;

  // 1. Try ML Kit first (offline, no API key required)
  if (mlKitAvailable && !forceApi) {
    try {
      const result = await runMlKit(base64);
      if (result.text.trim().length > 0) {
        return result;
      }
      // ML Kit returned empty — fall through to API as backup
      console.log('[OCR] ML Kit returned empty text, trying API fallback');
    } catch (e) {
      console.warn('[OCR] ML Kit error, falling back to API:', e.message);
    }
  }

  // 2. Fall back to backend API
  try {
    return await runApiOcr(base64);
  } catch (e) {
    console.error('[OCR] API fallback failed:', e.message);
    return {
      text:       '(OCR failed — check connection)',
      source:     OCR_SOURCE.FALLBACK,
      mock:       false,
      blocks:     [],
      lines:      [],
      confidence: null,
    };
  }
}

/**
 * Returns true if ML Kit native module is loaded and ready.
 * Use this to show the user whether OCR is offline or online.
 */
export function isMlKitAvailable() {
  return mlKitAvailable;
}
