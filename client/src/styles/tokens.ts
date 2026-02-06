/**
 * Design System Tokens
 * 
 * Centralized design tokens for consistent theming across the application.
 * These values should be used instead of hardcoded colors/spacing.
 */

export const colors = {
  // Semantic colors
  primary: {
    DEFAULT: "#3b82f6",
    light: "#60a5fa",
    dark: "#2563eb",
    50: "#eff6ff",
    100: "#dbeafe",
    200: "#bfdbfe",
    300: "#93c5fd",
    400: "#60a5fa",
    500: "#3b82f6",
    600: "#2563eb",
    700: "#1d4ed8",
    800: "#1e40af",
    900: "#1e3a8a",
  },
  
  success: {
    DEFAULT: "#10b981",
    light: "#34d399",
    dark: "#059669",
    50: "#ecfdf5",
    100: "#d1fae5",
    200: "#a7f3d0",
    300: "#6ee7b7",
    400: "#34d399",
    500: "#10b981",
    600: "#059669",
    700: "#047857",
    800: "#065f46",
    900: "#064e3b",
  },
  
  warning: {
    DEFAULT: "#f59e0b",
    light: "#fbbf24",
    dark: "#d97706",
    50: "#fffbeb",
    100: "#fef3c7",
    200: "#fde68a",
    300: "#fcd34d",
    400: "#fbbf24",
    500: "#f59e0b",
    600: "#d97706",
    700: "#b45309",
    800: "#92400e",
    900: "#78350f",
  },
  
  error: {
    DEFAULT: "#ef4444",
    light: "#f87171",
    dark: "#dc2626",
    50: "#fef2f2",
    100: "#fee2e2",
    200: "#fecaca",
    300: "#fca5a5",
    400: "#f87171",
    500: "#ef4444",
    600: "#dc2626",
    700: "#b91c1c",
    800: "#991b1b",
    900: "#7f1d1d",
  },
  
  // Surface colors (dark theme)
  surface: {
    base: "#020617",      // slate-950
    elevated: "#0f172a",  // slate-900
    overlay: "#1e293b",   // slate-800
    hover: "#334155",     // slate-700
  },
  
  // Text colors
  text: {
    primary: "#f8fafc",    // slate-50
    secondary: "#cbd5e1",  // slate-300
    tertiary: "#64748b",   // slate-500
    disabled: "#475569",   // slate-600
    inverted: "#0f172a",   // slate-900
  },
  
  // Border colors
  border: {
    DEFAULT: "#334155",    // slate-700
    light: "#475569",      // slate-600
    heavy: "#1e293b",      // slate-800
    subtle: "#1e293b",     // slate-800
  },
  
  // Special purpose colors
  info: {
    DEFAULT: "#3b82f6",
    light: "#60a5fa",
    dark: "#2563eb",
  },
  
  purple: {
    DEFAULT: "#a855f7",
    light: "#c084fc",
    dark: "#9333ea",
  },
};

export const spacing = {
  xs: "0.25rem",     // 4px
  sm: "0.5rem",      // 8px
  md: "1rem",        // 16px
  lg: "1.5rem",      // 24px
  xl: "2rem",        // 32px
  "2xl": "3rem",     // 48px
  "3xl": "4rem",     // 64px
  "4xl": "6rem",     // 96px
};

export const borderRadius = {
  sm: "0.375rem",    // 6px
  md: "0.5rem",      // 8px
  lg: "0.75rem",     // 12px
  xl: "1rem",        // 16px
  "2xl": "1.5rem",   // 24px
  full: "9999px",
};

export const fontSize = {
  xs: "0.75rem",     // 12px
  sm: "0.875rem",    // 14px
  base: "1rem",      // 16px
  lg: "1.125rem",    // 18px
  xl: "1.25rem",     // 20px
  "2xl": "1.5rem",   // 24px
  "3xl": "1.875rem", // 30px
  "4xl": "2.25rem",  // 36px
  "5xl": "3rem",     // 48px
};

export const fontWeight = {
  normal: "400",
  medium: "500",
  semibold: "600",
  bold: "700",
};

export const lineHeight = {
  tight: "1.25",
  normal: "1.5",
  relaxed: "1.75",
};

export const shadows = {
  sm: "0 1px 2px 0 rgb(0 0 0 / 0.05)",
  DEFAULT: "0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)",
  md: "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)",
  lg: "0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)",
  xl: "0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)",
  "2xl": "0 25px 50px -12px rgb(0 0 0 / 0.25)",
  inner: "inset 0 2px 4px 0 rgb(0 0 0 / 0.05)",
  none: "0 0 #0000",
};

export const transitions = {
  fast: "150ms",
  normal: "200ms",
  slow: "300ms",
  slower: "500ms",
};

export const zIndex = {
  dropdown: 1000,
  sticky: 1020,
  fixed: 1030,
  modalBackdrop: 1040,
  modal: 1050,
  popover: 1060,
  tooltip: 1070,
};

// Breakpoints (for reference in media queries)
export const breakpoints = {
  sm: "640px",
  md: "768px",
  lg: "1024px",
  xl: "1280px",
  "2xl": "1536px",
};

export default {
  colors,
  spacing,
  borderRadius,
  fontSize,
  fontWeight,
  lineHeight,
  shadows,
  transitions,
  zIndex,
  breakpoints,
};
