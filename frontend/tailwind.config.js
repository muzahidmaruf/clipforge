/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#0f0f0f',
        card: '#1a1a1a',
        border: '#2a2a2a',
        accent: '#7c3aed',
        'accent-hover': '#6d28d9',
        'score-green': '#22c55e',
        'score-yellow': '#eab308',
        'score-red': '#ef4444',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
