/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        mono: ['"JetBrains Mono"', '"Fira Code"', '"Cascadia Code"', 'monospace'],
      },
      colors: {
        drift: {
          bg: '#0d1117',
          panel: '#161b22',
          border: '#30363d',
          accent: '#58a6ff',
          critical: '#f85149',
          high: '#e85d04',
          medium: '#d29922',
          low: '#3fb950',
          info: '#8b949e',
          pass: '#3fb950',
        },
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
    },
  },
  plugins: [],
}
