import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import MainLayout from '../layouts/MainLayout';

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ user: { username: 'test', role: 'user' }, logout: vi.fn() }),
  AuthProvider: ({ children }) => children,
}));
vi.mock('../contexts/PreferenceContext', () => ({
  usePreference: () => ({
    preferredSource: 'eastmoney',
    themeMode: 'light',
    updateThemeMode: vi.fn(),
    loading: false,
  }),
  PreferenceProvider: ({ children }) => children,
}));
vi.mock('../components/Footer', () => ({ default: () => null }));

describe('MainLayout', () => {
  it('桌面端渲染', () => {
    render(
      <BrowserRouter>
        <MainLayout>
          <div>content</div>
        </MainLayout>
      </BrowserRouter>
    );
    expect(screen.getByText('Fundval')).toBeInTheDocument();
  });
});
