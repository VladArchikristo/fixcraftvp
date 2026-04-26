import AsyncStorage from '@react-native-async-storage/async-storage';

const STORAGE_KEY = '@haulwallet_calcs';
const FREE_LIMIT = 5;

/**
 * Mock subscription service.
 * TODO: Replace with real payment integration (RevenueCat, Stripe, or App Store / Google Play subscriptions).
 */

export async function isPremium() {
  const val = await AsyncStorage.getItem('@haulwallet_premium');
  return val === 'true';
}

export async function getCalcsToday() {
  const data = await AsyncStorage.getItem(STORAGE_KEY);
  if (!data) return 0;
  const parsed = JSON.parse(data);
  const today = new Date().toISOString().split('T')[0];
  return parsed.date === today ? parsed.count : 0;
}

export async function incrementCalcs() {
  const today = new Date().toISOString().split('T')[0];
  const data = await AsyncStorage.getItem(STORAGE_KEY);
  let parsed = data ? JSON.parse(data) : { date: today, count: 0 };
  if (parsed.date !== today) {
    parsed = { date: today, count: 0 };
  }
  parsed.count += 1;
  await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(parsed));
  return parsed.count;
}

export async function checkLimit() {
  const premium = await isPremium();
  if (premium) return { allowed: true, remaining: Infinity };
  const count = await getCalcsToday();
  return {
    allowed: count < FREE_LIMIT,
    remaining: Math.max(0, FREE_LIMIT - count),
    limit: FREE_LIMIT,
    used: count,
  };
}

export async function upgradeToPremium() {
  // TODO: Integrate real payment (RevenueCat / Stripe / IAP)
  // This is a mock — sets premium flag in AsyncStorage
  await AsyncStorage.setItem('@haulwallet_premium', 'true');
  return true;
}

export async function restorePurchases() {
  // TODO: Check real purchase status from store
  return isPremium();
}

export const FREE_CALCULATIONS_LIMIT = FREE_LIMIT;
