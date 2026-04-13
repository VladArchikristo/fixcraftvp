import axios from 'axios';
import { getToken } from './auth';

const API_URL = 'http://192.168.1.177:3001'; // Mac Mini IP

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
