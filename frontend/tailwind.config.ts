import type { Config } from 'tailwindcss';

// Groww-like palette from docs/TASKS_FRONTEND.md: white cards on #f6f7f9, green for positive, red for negative.
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        page: '#f6f7f9',
        brand: { DEFAULT: '#00b386', dark: '#009670', soft: '#e6f7f2' },
        loss: { DEFAULT: '#eb5b3c', soft: '#fdeeea' },
        ink: { DEFAULT: '#1f2937', muted: '#6b7280', faint: '#9ca3af' },
        line: '#e5e7eb',
      },
      borderRadius: { DEFAULT: '8px', lg: '8px' },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
    },
  },
  plugins: [],
} satisfies Config;
