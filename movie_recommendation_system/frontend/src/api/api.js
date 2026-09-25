import axios from 'axios';

const BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000';

const http = axios.create({ baseURL: BASE_URL });
const adminHttp = axios.create({ baseURL: BASE_URL });

// ── Request interceptor: attach Bearer token ──────────────────────────────
http.interceptors.request.use(config => {
  const token = localStorage.getItem('token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// ── Response interceptor: clear token on 401 ─────────────────────────────
http.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 401) {
      const isAuthCall = err.config?.url?.includes('/auth/');
      if (!isAuthCall) {
        localStorage.removeItem('token');
        window.location.href = '/login';
      }
    }
    return Promise.reject(err);
  }
);

// Administration has an independent credential and request pipeline.
adminHttp.interceptors.request.use(config => {
  const token = sessionStorage.getItem('adminToken');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

adminHttp.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 401 && !err.config?.url?.includes('/admin/auth/login')) {
      sessionStorage.removeItem('adminToken');
      window.dispatchEvent(new Event('admin-auth-invalid'));
    }
    return Promise.reject(err);
  }
);

// ── Auth ──────────────────────────────────────────────────────────────────
export const authAPI = {
    register: data     => http.post('/auth/register', data),
    login:   (em, pw) => http.post('/auth/login', { email: em, password: pw }),
    me:      ()       => http.get('/auth/me'),
    resetPassword: data => http.post('/auth/reset-password', data),
};

// ── Movies ────────────────────────────────────────────────────────────────
export const moviesAPI = {
  search:          (q, limit = 10)            => http.get('/movies/search',          { params: { q, limit } }),
  trending:        (limit = 20)               => http.get('/movies/trending',         { params: { limit } }),
  getById:         id                         => http.get(`/movies/${id}`),
  getBatch:        ids                        => http.post('/movies/batch',           { ids }),
  similar:         (id, n = 10)              => http.get(`/movies/similar/${id}`,   { params: { n } }),
  recommendations: (section = 'recommended', n = 20) =>
    http.get('/movies/recommendations', { params: { section, n } }),
};

// ── User ──────────────────────────────────────────────────────────────────
export const userAPI = {
  getProfile:     ()      => http.get('/user/profile'),
  updateProfile:  data    => http.put('/user/profile', data),
  changePassword: data    => http.put('/user/password', data),
  markWatched:    movieId => http.post('/user/watch',        { movieId }),
  removeWatched:  movieId => http.delete(`/user/watch/${movieId}`),
};

export const adminAPI = {
  login:         (email, password)        => adminHttp.post('/admin/auth/login', { email, password }),
  me:            ()                       => adminHttp.get('/admin/auth/me'),
  logout:        ()                       => adminHttp.post('/admin/auth/logout'),
  setPassword:   data                     => adminHttp.post('/admin/auth/reset-password', data),
  summary:       ()                       => adminHttp.get('/admin/summary'),
  accounts:      ()                       => adminHttp.get('/admin/accounts'),
  systemHealth:  ()                       => adminHttp.get('/admin/system/health'),
  checkTmdb:     ()                       => adminHttp.post('/admin/integrations/tmdb/check'),
  clearTmdbCache: ()                      => adminHttp.delete('/admin/integrations/tmdb/cache'),
  models:        ()                       => adminHttp.get('/admin/models'),
  verifyModels:  ()                       => adminHttp.post('/admin/models/verify'),
  users:         (q = '', page = 1)      => adminHttp.get('/admin/users', { params: { q, page } }),
  user:          id                       => adminHttp.get(`/admin/users/${id}`),
  updateUser:    (id, data)               => adminHttp.patch(`/admin/users/${id}`, data),
  resetPassword: id                       => adminHttp.post(`/admin/users/${id}/password-reset`),
  mlProfile:     id                       => adminHttp.get(`/admin/users/${id}/ml-profile`),
  recommendations: (id, n = 10)          => adminHttp.get(`/admin/users/${id}/recommendations`, { params: { n } }),
  modelConfig:   ()                       => adminHttp.get('/admin/model-config'),
  createModelConfig: data                 => adminHttp.post('/admin/model-config/versions', data),
  activateModelConfig: id                 => adminHttp.post(`/admin/model-config/versions/${id}/activate`),
  auditLog:      (limit = 50)             => adminHttp.get('/admin/audit-log', { params: { limit } }),
};

export default http;
