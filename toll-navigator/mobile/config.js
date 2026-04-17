// Единый источник URL для API
// Приоритет: EXPO_PUBLIC_API_URL env → production API
export const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_URL || 'https://api.haulwallet.com';

export const GOOGLE_CLIENT_ID =
  process.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID || 'YOUR_GOOGLE_CLIENT_ID';

export const GOOGLE_IOS_CLIENT_ID =
  process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID || 'YOUR_GOOGLE_IOS_CLIENT_ID';
