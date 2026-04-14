import axios from 'axios';
import Constants from 'expo-constants';
import { getToken } from './auth';
import { API_BASE_URL } from '../config';

// Priority: EXPO_PUBLIC_API_URL env var → app.json extra.apiUrl → config.js fallback
const getApiUrl = () => {
  if (process.env.EXPO_PUBLIC_API_URL) {
    return process.env.EXPO_PUBLIC_API_URL;
  }
  const extraUrl = Constants.expoConfig?.extra?.apiUrl || Constants.manifest?.extra?.apiUrl;
  if (extraUrl) return extraUrl;
  return API_BASE_URL;
};

const API_URL = getApiUrl();

const api = axios.create({
  baseURL: API_URL,
  timeout: 10000,
});

api.interceptors.request.use(async (config) => {
  const token = await getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Auth
export const register = (data) => api.post('/api/auth/register', data);
export const login = (data) => api.post('/api/auth/login', data);

// Toll Calculator — GET /api/tolls/route
export const calculateRoute = (from, to, truckType) =>
  api.get('/api/tolls/route', { params: { from, to, truck_type: truckType } });

export default api;
