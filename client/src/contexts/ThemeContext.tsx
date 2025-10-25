'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';

export type Theme = 'light' | 'dark';
export interface ThemeContextState {
  theme: Theme;
  setTheme: (t: Theme) => void;
  autoBrightness: boolean;
  setAutoBrightness: (v: boolean) => void;
}

const ThemeContext = createContext<ThemeContextState | undefined>(undefined);

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [theme, setThemeState] = useState<Theme>(() => {
    try {
      const stored = localStorage.getItem('radex:theme');
      return (stored as Theme) || 'light';
    } catch {
      return 'light';
    }
  });
  const [autoBrightness, setAutoBrightnessState] = useState<boolean>(() => {
    try {
      return localStorage.getItem('radex:autoBrightness') === 'true';
    } catch {
      return false;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem('radex:theme', theme);
    } catch {}
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  useEffect(() => {
    try {
      localStorage.setItem('radex:autoBrightness', String(autoBrightness));
    } catch {}
  }, [autoBrightness]);

  const setTheme = (t: Theme) => setThemeState(t);
  const setAutoBrightness = (v: boolean) => setAutoBrightnessState(v);

  return (
    <ThemeContext.Provider value={{ theme, setTheme, autoBrightness, setAutoBrightness }}>
      {children}
    </ThemeContext.Provider>
  );
};

export const useTheme = () => {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used inside ThemeProvider');
  return ctx;
};