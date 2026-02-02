import { useState, useEffect, useCallback } from 'react';
import type { SignalSettings, SignalRule } from '../types/signals';
import {
  DEFAULT_SIGNAL_SETTINGS,
  DEFAULT_SIGNAL_RULES,
  STORAGE_KEY,
} from '../types/signals';

function deepMergeRules(
  defaults: Record<string, SignalRule>,
  overrides: Record<string, Partial<SignalRule>>
): Record<string, SignalRule> {
  const merged: Record<string, SignalRule> = { ...defaults };
  
  for (const key of Object.keys(overrides)) {
    if (merged[key]) {
      merged[key] = {
        ...merged[key],
        ...overrides[key],
        percentile: {
          ...merged[key].percentile,
          ...(overrides[key]?.percentile ?? {}),
        },
        absolute: {
          ...merged[key].absolute,
          ...(overrides[key]?.absolute ?? {}),
        },
      };
    } else {
      // New metric not in defaults
      merged[key] = overrides[key] as SignalRule;
    }
  }
  
  return merged;
}

function loadSettings(): SignalSettings {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      return {
        enabled: parsed.enabled ?? DEFAULT_SIGNAL_SETTINGS.enabled,
        globalMode: parsed.globalMode ?? DEFAULT_SIGNAL_SETTINGS.globalMode,
        rules: deepMergeRules(DEFAULT_SIGNAL_RULES, parsed.rules ?? {}),
      };
    }
  } catch (e) {
    console.warn('Failed to load signal settings from localStorage:', e);
  }
  return { ...DEFAULT_SIGNAL_SETTINGS, rules: { ...DEFAULT_SIGNAL_RULES } };
}

function saveSettings(settings: SignalSettings): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  } catch (e) {
    console.warn('Failed to save signal settings to localStorage:', e);
  }
}

export function useSignalSettings() {
  const [settings, setSettings] = useState<SignalSettings>(loadSettings);

  // Save to localStorage when settings change
  useEffect(() => {
    saveSettings(settings);
  }, [settings]);

  const updateSettings = useCallback((updates: Partial<SignalSettings>) => {
    setSettings((prev) => ({
      ...prev,
      ...updates,
    }));
  }, []);

  const updateRule = useCallback((metricKey: string, updates: Partial<SignalRule>) => {
    setSettings((prev) => ({
      ...prev,
      rules: {
        ...prev.rules,
        [metricKey]: {
          ...prev.rules[metricKey],
          ...updates,
          percentile: {
            ...prev.rules[metricKey]?.percentile,
            ...(updates.percentile ?? {}),
          },
          absolute: {
            ...prev.rules[metricKey]?.absolute,
            ...(updates.absolute ?? {}),
          },
        },
      },
    }));
  }, []);

  const resetToDefaults = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setSettings({ ...DEFAULT_SIGNAL_SETTINGS, rules: { ...DEFAULT_SIGNAL_RULES } });
  }, []);

  const toggleEnabled = useCallback(() => {
    setSettings((prev) => ({ ...prev, enabled: !prev.enabled }));
  }, []);

  const setGlobalMode = useCallback((mode: 'percentile' | 'absolute') => {
    setSettings((prev) => ({ ...prev, globalMode: mode }));
  }, []);

  return {
    settings,
    updateSettings,
    updateRule,
    resetToDefaults,
    toggleEnabled,
    setGlobalMode,
  };
}
