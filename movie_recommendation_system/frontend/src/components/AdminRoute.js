import React from 'react';
import { useAdminAuth } from '../context/AdminAuthContext';
import AdminLoginPage from '../pages/AdminLoginPage';

export default function AdminRoute({ children }) {
  const { admin, loading } = useAdminAuth();

  if (loading) {
    return <main className="admin-login-page"><div className="admin-loader" /></main>;
  }
  return admin ? children : <AdminLoginPage />;
}
