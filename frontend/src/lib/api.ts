import axios from 'axios';

// The base URL relies on Next.js rewrites to proxy /api to the backend.
// This avoids CORS issues during local development.
export const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to automatically attach JWT token if available.
api.interceptors.request.use(
  (config) => {
    // We access storage in the browser
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for handling global errors (e.g., 401 Unauthorized)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Clear token and redirect to login if unauthorized
      if (typeof window !== 'undefined') {
        localStorage.removeItem('access_token');
        sessionStorage.removeItem('access_token');
        // Simple redirect (could also use Next.js router if passed down, 
        // but window.location is safe for global interceptors)
        if (!window.location.pathname.includes('/login')) {
          window.location.href = '/login';
        }
      }
    }
    return Promise.reject(error);
  }
);

// Settings APIs
export const getSettings = () => api.get('/admin/settings').then(res => res.data);
export const updateSettings = (settings: Record<string, string>) => api.post('/admin/settings', settings).then(res => res.data);
export const restartTelegram = () => api.post('/admin/telegram/restart').then(res => res.data);
export const sendCode = (data: {phone: string}) => api.post('/admin/telegram/send-code', data).then(res => res.data);
export const verifyOtp = (data: {phone: string, code: string, phone_code_hash: string, password?: string}) => api.post('/admin/telegram/verify-otp', data).then(res => res.data);
export const triggerManualCrawl = (data: {chat_id: number, limit?: number}) => api.post('/admin/telegram/crawl-history', data).then(res => res.data);
export const autoDiscoverGroups = () => api.post('/admin/telegram/auto-discover-groups').then(res => res.data);

// Upload API
export const uploadManualFile = (file: File) => {
  const formData = new FormData();
  formData.append('file', file);
  
  // Next.js rewrites have issues proxying large file uploads (memory buffering -> ERR_CONNECTION_RESET).
  // We bypass it by uploading directly to the FastAPI backend (port 8000) using the current hostname.
  const backendUrl = typeof window !== 'undefined' 
    ? `${window.location.protocol}//${window.location.hostname}:8000/api/admin/upload`
    : '/api/admin/upload';
    
  return api.post(backendUrl, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }).then(res => res.data);
};

// Model Edit API
export const updateModel = (modelId: string, data: any) => api.put(`/models/${modelId}`, data).then(res => res.data);
export const deleteModel = (modelId: string) => api.delete(`/models/${modelId}`).then(res => res.data);

// User APIs
export const getCurrentUser = () => api.get('/users/me').then(res => res.data);
export const updateCurrentUser = (data: any) => api.put('/users/me', data).then(res => res.data);
export const getFavorites = () => api.get('/users/me/favorites').then(res => res.data);
export const addFavorite = (modelId: string) => api.post('/users/me/favorites', { model_id: modelId }).then(res => res.data);
export const removeFavorite = (modelId: string) => api.delete(`/users/me/favorites/${modelId}`).then(res => res.data);
export const getHistory = () => api.get('/users/me/history').then(res => res.data);
export const recordHistory = (modelId: string) => api.post('/users/me/history', { model_id: modelId }).then(res => res.data);

// Admin User APIs
export const getAdminUsers = () => api.get('/users/admin/list').then(res => res.data);
export const updateAdminUser = (userId: string, data: any) => api.put(`/users/admin/${userId}`, data).then(res => res.data);
