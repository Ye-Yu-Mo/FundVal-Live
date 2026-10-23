import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';

const { mockUserRef } = vi.hoisted(() => ({ mockUserRef: { current: null } }));

vi.mock('../api', () => ({
  preferencesAPI: {
    get: vi.fn(),
    update: vi.fn(),
  },
}));

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ user: mockUserRef.current }),
}));

import {
  PreferenceProvider,
  usePreference,
} from '../contexts/PreferenceContext';
import { preferencesAPI } from '../api';

const Consumer = () => {
  const { preferredSource } = usePreference();
  return <div data-testid="preferred-source">{preferredSource}</div>;
};

describe('PreferenceProvider', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUserRef.current = null;
    preferencesAPI.get.mockResolvedValue({
      data: { preferred_source: 'yangjibao', theme_mode: 'dark' },
    });
  });

  it('登录后重新加载偏好，不需要刷新页面', async () => {
    const { rerender } = render(
      <PreferenceProvider>
        <Consumer />
      </PreferenceProvider>,
    );

    expect(preferencesAPI.get).not.toHaveBeenCalled();

    mockUserRef.current = { id: 1 };
    rerender(
      <PreferenceProvider>
        <Consumer />
      </PreferenceProvider>,
    );

    await waitFor(() => {
      expect(preferencesAPI.get).toHaveBeenCalledTimes(1);
    });
    await waitFor(() => {
      expect(screen.getByTestId('preferred-source')).toHaveTextContent(
        'yangjibao',
      );
    });
  });
});
