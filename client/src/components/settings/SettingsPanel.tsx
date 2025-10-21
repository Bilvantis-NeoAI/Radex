'use client';
import React, { useEffect } from 'react';
import ThemeSelector from './ThemeSelector';
import useAutoBrightness from '@/hooks/useAutoBrightness';
import { useTheme } from '@/contexts/ThemeContext';

const SettingsPanel: React.FC = () => {
  const { autoBrightness } = useTheme();
  useAutoBrightness(); // activates auto adjustments when enabled

  return (
    <div className="p-4 bg-white rounded shadow">
      <h3 className="text-lg font-semibold mb-3">Settings</h3>

      <section className="mb-4">
        <ThemeSelector />
      </section>

      {/* add other settings here */}
    </div>
  );
};

export default SettingsPanel;