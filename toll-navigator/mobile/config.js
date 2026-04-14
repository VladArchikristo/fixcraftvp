// Единый источник URL для API
// Приоритет: EXPO_PUBLIC_API_URL env → app.json extra.apiUrl → localhost fallback
export const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_URL || 'http://localhost:3001';
