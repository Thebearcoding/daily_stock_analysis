/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // 主色调 (Accent mapped to Terracotta)
        'cyan': {
          DEFAULT: '#D68663',
          dim: '#C57650',
          glow: 'rgba(214, 134, 99, 0.2)',
        },
        // 辅助色
        'purple': {
          DEFAULT: '#8B7B74',
          dim: '#7A6A63',
          glow: 'rgba(139, 123, 116, 0.2)',
        },
        // 状态色
        'success': '#059669',
        'warning': '#D97706',
        'danger': '#DC2626',
        // 背景色
        'base': '#F5F1E8',
        'card': '#ECE4D8',
        'elevated': '#E4D8C8',
        'hover': '#EBC9B3',
        // 文字色
        'primary': '#111111',
        'secondary': '#5B534B',
        'muted': '#8C8276',
        // 边框色
        'border': {
          dim: 'rgba(216, 205, 190, 0.4)',
          DEFAULT: '#D8CDBE',
          accent: '#D68663',
          purple: '#8B7B74',
        },
        // 新增专有暖色体系（可与 base/card 等混用）
        'warm-bg': '#FAF9F6',
        'warm-surface': '#FFFFFF',
        'warm-surface-alt': '#F8F6F2',
        'clay': {
          DEFAULT: '#D68663',
          soft: '#EBC9B3',
        },
        'charcoal': {
          DEFAULT: '#111111',
          muted: '#5B534B',
        },
        'warm-border': '#FAF9F6',
      },
      backgroundImage: {
        'gradient-purple-cyan': 'linear-gradient(135deg, rgba(214, 134, 99, 0.1) 0%, rgba(139, 123, 116, 0.1) 100%)',
        'gradient-card-border': 'none',
        'gradient-cyan': 'none',
      },
      boxShadow: {
        'glow-cyan': '0 4px 12px rgba(214, 134, 99, 0.15)',
        'glow-purple': '0 4px 12px rgba(139, 123, 116, 0.15)',
        'glow-success': '0 4px 12px rgba(5, 150, 105, 0.15)',
        'glow-danger': '0 4px 12px rgba(220, 38, 38, 0.15)',
      },
      borderRadius: {
        'xl': '12px',
        '2xl': '16px',
        '3xl': '20px',
      },
      fontSize: {
        'xxs': '10px',
        'label': '11px',
      },
      spacing: {
        '18': '4.5rem',
        '22': '5.5rem',
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.4s ease-out',
        'slide-in-right': 'slideInRight 0.3s ease-out',
        'pulse-glow': 'pulseGlow 2s ease-in-out infinite',
        'spin-slow': 'spin 2s linear infinite',
      },
      keyframes: {
        fadeIn: {
          'from': { opacity: '0' },
          'to': { opacity: '1' },
        },
        slideUp: {
          'from': { opacity: '0', transform: 'translateY(10px)' },
          'to': { opacity: '1', transform: 'translateY(0)' },
        },
        slideInRight: {
          'from': { opacity: '0', transform: 'translateX(100%)' },
          'to': { opacity: '1', transform: 'translateX(0)' },
        },
        pulseGlow: {
          '0%, 100%': { boxShadow: '0 0 20px rgba(0, 212, 255, 0.4)' },
          '50%': { boxShadow: '0 0 40px rgba(0, 212, 255, 0.6)' },
        },
      },
    },
  },
  plugins: [],
}
