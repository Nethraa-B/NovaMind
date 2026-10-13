/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#152a3a',
        paper: '#f5f7f8',
        accent: '#476f82',
        line: '#dfe6e9',
      },
      fontFamily: {
        sans: ['DM Sans', 'Segoe UI', 'sans-serif'],
        display: ['Manrope', 'DM Sans', 'sans-serif'],
      },
      boxShadow: {
        panel: '0 1px 2px rgba(18, 42, 58, 0.04), 0 8px 24px rgba(18, 42, 58, 0.035)',
      },
    },
  },
  plugins: [],
}