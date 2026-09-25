import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AdminPage from './AdminPage';
import { adminAPI } from '../api/api';

jest.mock('../api/api', () => ({
  adminAPI: {
    summary: jest.fn(), users: jest.fn(), modelConfig: jest.fn(), auditLog: jest.fn(),
    systemHealth: jest.fn(), models: jest.fn(), accounts: jest.fn(),
    checkTmdb: jest.fn(), clearTmdbCache: jest.fn(), verifyModels: jest.fn(),
    updateUser: jest.fn(), resetPassword: jest.fn(), mlProfile: jest.fn(),
    recommendations: jest.fn(), createModelConfig: jest.fn(), activateModelConfig: jest.fn(),
  },
}));

jest.mock('../context/AdminAuthContext', () => ({
  useAdminAuth: () => ({
    admin: { displayName: 'System Admin', email: 'admin@example.com' },
    logout: jest.fn(),
  }),
}));

const user = {
  id: 2, firstName: 'Ada', lastName: 'Lovelace', email: 'ada@example.com',
  favoriteGenres: ['Drama'], favoriteMovies: [550], watchedMovies: [],
  movielensUserId: 42, isActive: true,
  preferences: { includeWatched: false, watchingFrequency: 'weekly' },
};

beforeEach(() => {
  adminAPI.summary.mockResolvedValue({ data: {
    users: { total: 1, inactive: 0, passwordResetPending: 0 },
    administrators: { total: 1, active: 1 },
    integrations: { tmdb: { configured: true } }, model: {}, modelConfig: {},
  } });
  adminAPI.users.mockResolvedValue({ data: { items: [user], total: 1 } });
  adminAPI.modelConfig.mockResolvedValue({ data: {
    active: { id: 1, config: {
      popularityWeight: 1, funkSvdWeight: 0.35, neuMfWeight: 0.15,
      genreBoost: 0.25, candidatePoolSize: 400, similarUserCount: 5,
      minimumSimilarity: 0,
    } }, versions: [], defaults: {},
  } });
  adminAPI.auditLog.mockResolvedValue({ data: [] });
  adminAPI.systemHealth.mockResolvedValue({ data: {
    api: { healthy: true, uptimeSeconds: 12, python: '3.13' },
    database: { healthy: true, latencyMs: 1 },
    tmdb: { configured: true, authentication: 'api-key', cache: { entries: 0, maximumEntries: 100 } },
    models: { artifactsLoaded: false },
  } });
  adminAPI.models.mockResolvedValue({ data: {
    pipeline: ['candidate_pool', 'rank_and_enrich'],
    models: [{ key: 'hybrid', name: 'Hybrid Ranker', category: 'ensemble', purpose: 'Ranks movies', available: true, loaded: true, configuration: {}, artifacts: [] }],
  } });
  adminAPI.accounts.mockResolvedValue({ data: [
    { id: 1, displayName: 'System Admin', email: 'admin@example.com', isActive: true },
  ] });
});

test('loads users and opens the attribute editor', async () => {
  render(<MemoryRouter><AdminPage /></MemoryRouter>);
  expect(await screen.findByText('Ada Lovelace')).toBeInTheDocument();
  fireEvent.click(screen.getByText('Ada Lovelace'));
  await waitFor(() => expect(screen.getByDisplayValue('ada@example.com')).toBeInTheDocument());
  expect(screen.getByDisplayValue('42')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Create reset link' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Load ML diagnostics' })).toBeInTheDocument();
});
