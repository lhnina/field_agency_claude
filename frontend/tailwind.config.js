/** Design System "Field Agency" — direção visual A, aprovada a 2 nov 2026.
 *  Os mesmos valores estão em src/design/tokens.json. */
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        petrol: { 50: '#E6F2EF', 100: '#D4EAE5', 600: '#0E6B63', 700: '#0A5650', 800: '#163937', 900: '#0F2B2A' },
        amber: { 400: '#F2A93B', 900: '#2A1A00' },
        ink: { DEFAULT: '#14201F', 80: '#3B4744', 60: '#5E6966', 40: '#A3ADA7' },
        bg: '#F3F4F1',
        line: { DEFAULT: '#E2E5E0', soft: '#EEF0ED', strong: '#D6DBD6' },
        ok: { DEFAULT: '#1E7F4F', bg: '#E3F2EA', fg: '#17663F' },
        warn: { DEFAULT: '#D98A0B', bg: '#FCEFD7', fg: '#7E4B00' },
        err: { DEFAULT: '#B5382A', bg: '#FBE7E3', fg: '#9E2F22' },
        info: { DEFAULT: '#2F64C8', bg: '#E5EDFB', fg: '#2654A8' },
        rep: { DEFAULT: '#0E6B63', bg: '#E2F0ED', fg: '#0B5A53' },
        pro: { DEFAULT: '#C2571A', bg: '#FBEADF', fg: '#8F3D0F' },
        log: { DEFAULT: '#2F64C8', bg: '#E5EDFB', fg: '#2654A8' },
        eqf: { DEFAULT: '#6B5BB5', bg: '#ECE8F8', fg: '#4F4196' },
      },
      fontFamily: {
        sans: ['Geist', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        mono: ['Geist Mono', 'ui-monospace', 'monospace'],
      },
      fontSize: { '2xs': ['11px', '16px'], xs: ['12px', '16px'], sm: ['13px', '18px'], base: ['14px', '20px'] },
      borderRadius: { md: '8px', lg: '9px', xl: '12px' },
      boxShadow: { seg: '0 1px 2px rgba(16,32,31,.14)', pop: '0 8px 24px rgba(16,32,31,.16)' },
      width: { sidebar: '248px' },
      height: { topbar: '64px' },
    },
  },
  plugins: [],
}
