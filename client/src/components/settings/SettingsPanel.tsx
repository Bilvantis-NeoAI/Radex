'use client';
import React from 'react';
import ThemeSelector from './ThemeSelector';
import useAutoBrightness from '@/hooks/useAutoBrightness';
import { useTheme } from '@/contexts/ThemeContext';

const SettingsPanel: React.FC = () => {
  const { autoBrightness } = useTheme();

  // Use auto brightness hook - this will activate auto adjustments when enabled
  // The hook now continuously monitors time and updates theme accordingly
  useAutoBrightness();

  return (
    <div className="max-w-4xl space-y-8">
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="px-8 py-6 border-b border-gray-200">
          <h2 className="text-2xl font-semibold text-gray-900">Display Settings</h2>
          <p className="text-sm text-gray-600 mt-2">Customize your appearance preferences and theme settings</p>
        </div>

        <div className="px-8 py-8">
          <ThemeSelector />
        </div>
      </div>
    </div>
  );
};

export default SettingsPanel;
