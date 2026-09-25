import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import AdminRoute       from './components/AdminRoute';
import { AdminAuthProvider } from './context/AdminAuthContext';
import LandingPage      from './pages/LandingPage';
import LoginPage        from './pages/LoginPage';
import RegisterPage     from './pages/RegisterPage';
import DashboardPage    from './pages/DashboardPage';
import MovieDetailsPage from './pages/MovieDetailsPage';
import ProfilePage      from './pages/ProfilePage';
import TmdbAttribution  from './components/TmdbAttribution';
import AdminPage        from './pages/AdminPage';
import ResetPasswordPage from './pages/ResetPasswordPage';
import AdminPasswordSetupPage from './pages/AdminPasswordSetupPage';

export default function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          {/* Public */}
          <Route path="/"         element={<LandingPage />} />
          <Route path="/login"    element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/admin/setup" element={<AdminPasswordSetupPage />} />

          {/* Protected */}
          <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
          <Route path="/movie/:id" element={<ProtectedRoute><MovieDetailsPage /></ProtectedRoute>} />
          <Route path="/profile"   element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
          <Route path="/admin" element={
            <AdminAuthProvider><AdminRoute><AdminPage /></AdminRoute></AdminAuthProvider>
          } />

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        <TmdbAttribution />
      </Router>
    </AuthProvider>
  );
}
