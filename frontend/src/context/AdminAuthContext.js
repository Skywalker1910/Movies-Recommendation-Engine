import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { adminAPI } from '../api/api';

const AdminAuthContext = createContext(null);

export function AdminAuthProvider({ children }) {
  const [admin, setAdmin] = useState(null);
  const [loading, setLoading] = useState(Boolean(sessionStorage.getItem('adminToken')));

  const clearSession = useCallback(() => {
    sessionStorage.removeItem('adminToken');
    setAdmin(null);
    setLoading(false);
  }, []);

  useEffect(() => {
    const token = sessionStorage.getItem('adminToken');
    if (!token) {
      setLoading(false);
      return undefined;
    }
    adminAPI.me()
      .then(response => setAdmin(response.data))
      .catch(clearSession)
      .finally(() => setLoading(false));
    return undefined;
  }, [clearSession]);

  useEffect(() => {
    window.addEventListener('admin-auth-invalid', clearSession);
    return () => window.removeEventListener('admin-auth-invalid', clearSession);
  }, [clearSession]);

  const login = useCallback(async (email, password) => {
    const response = await adminAPI.login(email, password);
    sessionStorage.setItem('adminToken', response.data.token);
    setAdmin(response.data.admin);
    return response.data.admin;
  }, []);

  const logout = useCallback(async () => {
    try {
      await adminAPI.logout();
    } finally {
      clearSession();
    }
  }, [clearSession]);

  return (
    <AdminAuthContext.Provider value={{ admin, loading, login, logout }}>
      {children}
    </AdminAuthContext.Provider>
  );
}

export function useAdminAuth() {
  const value = useContext(AdminAuthContext);
  if (!value) throw new Error('useAdminAuth must be used within AdminAuthProvider');
  return value;
}
