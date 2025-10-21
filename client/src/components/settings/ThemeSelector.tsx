'use client';
import React from 'react';
import { useTheme } from '@/contexts/ThemeContext';

const ThemeSelector: React.FC = () => {
  const { theme, setTheme, autoBrightness, setAutoBrightness } = useTheme();

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-gray-700">Theme</label>

      <div className="flex gap-2">
        <button
          className={`px-3 py-1 rounded ${theme === 'light' ? 'bg-blue-600 text-white' : 'bg-gray-100'}`}
          onClick={() => {
            setAutoBrightness(false);
            setTheme('light');
          }}
        >
          Light
        </button>

        <button
          className={`px-3 py-1 rounded ${theme === 'dark' ? 'bg-blue-600 text-white' : 'bg-gray-100'}`}
          onClick={() => {
            setAutoBrightness(false);
            setTheme('dark');
          }}
        >
          Dark
        </button>

        <button
          className={`px-3 py-1 rounded ${autoBrightness ? 'bg-blue-600 text-white' : 'bg-gray-100'}`}
          onClick={() => setAutoBrightness(!autoBrightness)}
        >
          Auto
        </button>
      </div>
      <p className="text-xs text-gray-500">Default: Light. Auto uses your location to switch at sunrise/sunset.</p>
    </div>
  );
};

export default ThemeSelector;