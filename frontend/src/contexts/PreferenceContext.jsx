import { createContext, useContext, useState, useEffect } from 'react';
import { preferencesAPI } from '../api';
import { useAuth } from './AuthContext';

const PreferenceContext = createContext();

export const PreferenceProvider = ({ children }) => {
  const { user } = useAuth();
  const [preferredSource, setPreferredSource] = useState('eastmoney');
  const [themeMode, setThemeMode] = useState('light');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (user) {
      loadPreference();
    } else {
      setPreferredSource('eastmoney');
      setThemeMode('light');
      setLoading(false);
    }
  }, [user]);

  const loadPreference = async () => {
    try {
      const res = await preferencesAPI.get();
      setPreferredSource(res.data.preferred_source || 'eastmoney');
      setThemeMode(res.data.theme_mode || 'light');
    } catch {
      setPreferredSource('eastmoney');
      setThemeMode('light');
    } finally {
      setLoading(false);
    }
  };

  const updatePreference = async (newSource) => {
    try {
      await preferencesAPI.update(newSource);
      setPreferredSource(newSource);
    } catch (error) {
      console.error('更新数据源偏好失败', error);
      throw error;
    }
  };

  const updateThemeMode = async (mode) => {
    try {
      await preferencesAPI.update({ theme_mode: mode });
      setThemeMode(mode);
    } catch (error) {
      console.error('更新主题偏好失败', error);
    }
  };

  return (
    <PreferenceContext.Provider
      value={{
        preferredSource,
        updatePreference,
        themeMode,
        updateThemeMode,
        loading,
      }}
    >
      {children}
    </PreferenceContext.Provider>
  );
};

export const usePreference = () => {
  const context = useContext(PreferenceContext);
  if (!context) {
    throw new Error('usePreference must be used within PreferenceProvider');
  }
  return context;
};
