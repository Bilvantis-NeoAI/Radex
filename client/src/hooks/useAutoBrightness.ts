import { useEffect } from 'react';
import SunCalc from 'suncalc';
import { useTheme } from '@/contexts/ThemeContext';

/**
 * useAutoBrightness:
 * - If autoBrightness is enabled, uses geolocation to compute sunrise/sunset
 * - switches theme to 'dark' when current time is before sunrise or after sunset
 * - falls back to timezone-hour heuristic if geolocation denied
 */
export default function useAutoBrightness() {
  const { autoBrightness, setTheme } = useTheme();

  useEffect(() => {
    if (!autoBrightness) return;

    let mounted = true;
    const applyFromCoords = (lat: number, lon: number) => {
      try {
        const now = new Date();
        const times = SunCalc.getTimes(now, lat, lon);
        const isNight = now < times.sunrise || now >= times.sunset;
        if (!mounted) return;
        setTheme(isNight ? 'dark' : 'light');
      } catch {
        // ignore and fallback
      }
    };

    const fallbackByHour = () => {
      const hour = new Date().getHours();
      setTheme(hour < 6 || hour >= 19 ? 'dark' : 'light');
    };

    if ('geolocation' in navigator) {
      navigator.geolocation.getCurrentPosition(
        (pos) => applyFromCoords(pos.coords.latitude, pos.coords.longitude),
        () => fallbackByHour(),
        { maximumAge: 1000 * 60 * 60, timeout: 5000 }
      );
    } else {
      fallbackByHour();
    }

    return () => {
      mounted = false;
    };
  }, [autoBrightness, setTheme]);
}