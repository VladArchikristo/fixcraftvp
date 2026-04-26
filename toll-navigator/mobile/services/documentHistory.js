import AsyncStorage from '@react-native-async-storage/async-storage';

const STORAGE_KEY = '@toll_navigator:document_history';

/**
 * Get all document history (newest first)
 * @returns {Promise<Array>}
 */
export async function getDocumentHistory() {
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const items = JSON.parse(raw);
    return Array.isArray(items) ? items : [];
  } catch (e) {
    console.error('documentHistory.getDocumentHistory:', e);
    return [];
  }
}

/**
 * Save new entry to history
 * @param {object} entry - { id, type, date, localPath, pages, pdfUri }
 */
export async function saveDocumentToHistory(entry) {
  try {
    const existing = await getDocumentHistory();
    const updated = [entry, ...existing].slice(0, 100); // max 100 entries
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
    return updated;
  } catch (e) {
    console.error('documentHistory.saveDocumentToHistory:', e);
    throw e;
  }
}

/**
 * Delete entry from history by id
 * @param {string} id
 */
export async function deleteDocumentFromHistory(id) {
  try {
    const existing = await getDocumentHistory();
    const updated = existing.filter(item => item.id !== id);
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
    return updated;
  } catch (e) {
    console.error('documentHistory.deleteDocumentFromHistory:', e);
    throw e;
  }
}

/**
 * Clear all history
 */
export async function clearDocumentHistory() {
  try {
    await AsyncStorage.removeItem(STORAGE_KEY);
  } catch (e) {
    console.error('documentHistory.clearDocumentHistory:', e);
    throw e;
  }
}

/**
 * Generate unique ID for entry
 */
export function generateDocumentId() {
  return `doc_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Format date for display
 */
export function formatDocumentDate(isoString) {
  const d = new Date(isoString);
  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}
