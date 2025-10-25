import { useEffect, useRef } from 'react';
import { useTheme } from '@/contexts/ThemeContext';

export default function useAutoBrightness() {
  const { autoBrightness, setTheme } = useTheme();
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (!autoBrightness) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      return;
    }

    let mounted = true;

    const updateThemeByTime = () => {
      if (!mounted) return;

      const now = new Date();
      const hour = now.getHours();

      // Fallback logic: 6 AM to 7 PM is light, otherwise dark
      const shouldBeLight = hour >= 6 && hour < 19;
      setTheme(shouldBeLight ? 'light' : 'dark');
    };

    const applyFromCoords = async (lat: number, lon: number) => {
      try {
        // dynamic import so build doesn't fail if types missing
        const SunCalc = (await import('suncalc')).default;
        const now = new Date();
        const times = SunCalc.getTimes(now, lat, lon);
        const isNight = now < times.sunrise || now >= times.sunset;
        if (!mounted) return;
        setTheme(isNight ? 'dark' : 'light');
      } catch (error) {
        console.warn('Error in auto brightness with SunCalc:', error);
        updateThemeByTime(); // Fallback to time-based logic
      }
    };

    const initializeAutoBrightness = () => {
      if ('geolocation' in navigator) {
        navigator.geolocation.getCurrentPosition(
          (pos) => applyFromCoords(pos.coords.latitude, pos.coords.longitude),
          (error) => {
            console.warn('Geolocation error:', error);
            updateThemeByTime(); // Fallback to time-based logic
          },
          {
            maximumAge: 1000 * 60 * 60, // 1 hour
            timeout: 5000,
            enableHighAccuracy: false
          }
        );
      } else {
        updateThemeByTime(); // Fallback to time-based logic
      }
    };

    // Initial setup
    initializeAutoBrightness();

    // Set up interval to check every minute
    intervalRef.current = setInterval(() => {
      if (!mounted) return;
      initializeAutoBrightness();
    }, 60000); // Check every minute

    return () => {
      mounted = false;
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [autoBrightness, setTheme]);

  // Cleanup interval on unmount
  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, []);
}
