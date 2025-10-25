'use client';
import React from 'react';
import { Sun, Moon, Zap, Info } from 'lucide-react';
import { useTheme } from '@/contexts/ThemeContext';

const ThemeSelector: React.FC = () => {
  const { theme, setTheme, autoBrightness, setAutoBrightness } = useTheme();

  const themeOptions = [
    {
      id: 'light',
      name: 'Light Mode',
      description: 'Clean and bright interface for daytime use',
      icon: Sun,
      color: 'text-orange-500',
      bgColor: 'bg-orange-50 hover:bg-orange-100',
      borderColor: 'border-orange-200',
      iconBg: 'bg-orange-100',
    },
    {
      id: 'dark',
      name: 'Dark Mode',
      description: 'Easy on the eyes for nighttime use',
      icon: Moon,
      color: 'text-indigo-500',
      bgColor: 'bg-indigo-50 hover:bg-indigo-100',
      borderColor: 'border-indigo-200',
      iconBg: 'bg-indigo-100',
    },
    {
      id: 'auto',
      name: 'Auto Mode',
      description: 'Automatically switch between light and dark based on time',
      icon: Zap,
      color: 'text-blue-500',
      bgColor: 'bg-blue-50 hover:bg-blue-100',
      borderColor: 'border-blue-200',
      iconBg: 'bg-blue-100',
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-xl font-semibold text-gray-900 mb-2">Theme Preference</h3>
        <p className="text-sm text-gray-600 mb-6">Choose your preferred theme or enable automatic switching based on your local time</p>

        <div className="grid gap-4">
          {/* Light Mode */}
          <div className={`relative flex items-center justify-between p-5 rounded-xl border-2 transition-all duration-200 cursor-pointer ${
            theme === 'light' && !autoBrightness
              ? 'border-orange-300 bg-orange-50 shadow-md'
              : 'border-gray-200 bg-white hover:border-gray-300 hover:shadow-sm'
          }`}
          onClick={() => {
            setAutoBrightness(false);
            setTheme('light');
          }}>
            <div className="flex items-center space-x-4">
              <div className={`p-3 rounded-full ${theme === 'light' && !autoBrightness ? 'bg-orange-100' : 'bg-gray-100'}`}>
                <Sun className={`w-6 h-6 ${theme === 'light' && !autoBrightness ? 'text-orange-600' : 'text-gray-500'}`} />
              </div>
              <div>
                <label className="text-base font-medium text-gray-900 cursor-pointer">Light Mode</label>
                <p className="text-sm text-gray-600 mt-1">Clean and bright interface for daytime use</p>
              </div>
            </div>
            <div className="relative">
              <input
                id="light-mode"
                type="radio"
                name="theme"
                checked={theme === 'light' && !autoBrightness}
                onChange={() => {
                  setAutoBrightness(false);
                  setTheme('light');
                }}
                className="sr-only"
                aria-describedby="light-mode-description"
              />
              <label htmlFor="light-mode" className="sr-only">Light Mode</label>
              <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center transition-all cursor-pointer ${
                theme === 'light' && !autoBrightness
                  ? 'border-orange-500 bg-orange-500'
                  : 'border-gray-300 bg-white hover:border-gray-400'
              }`}>
                {theme === 'light' && !autoBrightness && (
                  <div className="w-2 h-2 rounded-full bg-white"></div>
                )}
              </div>
            </div>
          </div>

          {/* Dark Mode */}
          <div className={`relative flex items-center justify-between p-5 rounded-xl border-2 transition-all duration-200 cursor-pointer ${
            theme === 'dark' && !autoBrightness
              ? 'border-indigo-300 bg-indigo-50 shadow-md'
              : 'border-gray-200 bg-white hover:border-gray-300 hover:shadow-sm'
          }`}
          onClick={() => {
            setAutoBrightness(false);
            setTheme('dark');
          }}>
            <div className="flex items-center space-x-4">
              <div className={`p-3 rounded-full ${theme === 'dark' && !autoBrightness ? 'bg-indigo-100' : 'bg-gray-100'}`}>
                <Moon className={`w-6 h-6 ${theme === 'dark' && !autoBrightness ? 'text-indigo-600' : 'text-gray-500'}`} />
              </div>
              <div>
                <label className="text-base font-medium text-gray-900 cursor-pointer">Dark Mode</label>
                <p className="text-sm text-gray-600 mt-1">Easy on the eyes for nighttime use</p>
              </div>
            </div>
            <div className="relative">
              <input
                id="dark-mode"
                type="radio"
                name="theme"
                checked={theme === 'dark' && !autoBrightness}
                onChange={() => {
                  setAutoBrightness(false);
                  setTheme('dark');
                }}
                className="sr-only"
                aria-describedby="dark-mode-description"
              />
              <label htmlFor="dark-mode" className="sr-only">Dark Mode</label>
              <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center transition-all cursor-pointer ${
                theme === 'dark' && !autoBrightness
                  ? 'border-indigo-500 bg-indigo-500'
                  : 'border-gray-300 bg-white hover:border-gray-400'
              }`}>
                {theme === 'dark' && !autoBrightness && (
                  <div className="w-2 h-2 rounded-full bg-white"></div>
                )}
              </div>
            </div>
          </div>

          {/* Auto Mode */}
          <div className={`relative flex items-center justify-between p-5 rounded-xl border-2 transition-all duration-200 cursor-pointer ${
            autoBrightness
              ? 'border-blue-300 bg-blue-50 shadow-md'
              : 'border-gray-200 bg-white hover:border-gray-300 hover:shadow-sm'
          }`}
          onClick={() => setAutoBrightness(!autoBrightness)}>
            <div className="flex items-center space-x-4">
              <div className={`p-3 rounded-full ${autoBrightness ? 'bg-blue-100' : 'bg-gray-100'}`}>
                <Zap className={`w-6 h-6 ${autoBrightness ? 'text-blue-600' : 'text-gray-500'}`} />
              </div>
              <div>
                <label className="text-base font-medium text-gray-900 cursor-pointer">Auto Mode</label>
                <p className="text-sm text-gray-600 mt-1">Automatically switch between light and dark based on time</p>
              </div>
            </div>
            <div className="relative">
              <input
                id="auto-mode"
                type="radio"
                name="theme"
                checked={autoBrightness}
                onChange={() => setAutoBrightness(!autoBrightness)}
                className="sr-only"
                aria-describedby="auto-mode-description"
              />
              <label htmlFor="auto-mode" className="sr-only">Auto Mode</label>
              <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center transition-all cursor-pointer ${
                autoBrightness
                  ? 'border-blue-500 bg-blue-500'
                  : 'border-gray-300 bg-white hover:border-gray-400'
              }`}>
                {autoBrightness && (
                  <div className="w-2 h-2 rounded-full bg-white"></div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Information Panel */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-5">
        <div className="flex items-start space-x-3">
          <div className="flex-shrink-0">
            <Info className="h-5 w-5 text-blue-600 mt-0.5" />
          </div>
          <div>
            <h4 className="text-sm font-semibold text-blue-900 mb-2">Theme Information</h4>
            <div className="text-sm text-blue-800 space-y-2">
              <div className="flex items-start space-x-2">
                <Sun className="w-4 h-4 text-orange-500 mt-0.5 flex-shrink-0" />
                <span><strong>Light Mode:</strong> Clean and bright interface optimized for daytime use with maximum readability.</span>
              </div>
              <div className="flex items-start space-x-2">
                <Moon className="w-4 h-4 text-indigo-500 mt-0.5 flex-shrink-0" />
                <span><strong>Dark Mode:</strong> Easy on the eyes for nighttime use, reduces eye strain in low-light conditions.</span>
              </div>
              <div className="flex items-start space-x-2">
                <Zap className="w-4 h-4 text-blue-500 mt-0.5 flex-shrink-0" />
                <span><strong>Auto Mode:</strong> Automatically switches between light and dark themes based on your local sunrise and sunset times.</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ThemeSelector;
