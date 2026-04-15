// Единый источник URL для API
// Приоритет: EXPO_PUBLIC_API_URL env → production API
export const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_URL || 'https://api.haulwallet.com';
