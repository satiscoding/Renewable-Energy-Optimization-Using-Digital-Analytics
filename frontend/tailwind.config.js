/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        control: {
          bg: "#090D16",
          card: "rgba(15, 23, 42, 0.65)",
          cardHover: "rgba(22, 34, 60, 0.75)",
          primaryGlass: "rgba(30, 41, 59, 0.70)",
          border: "rgba(255, 255, 255, 0.08)",
          borderGlow: "rgba(245, 158, 11, 0.35)",
        },
        energy: {
          amber: "#F59E0B",
          amberLight: "#FBBF24",
          cyan: "#06B6D4",
          cyanLight: "#22D3EE",
        },
        status: {
          healthy: "#10B981",
          warning: "#F59E0B",
          critical: "#EF4444",
          muted: "#64748B",
        }
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "Consolas", "monospace"],
      },
      boxShadow: {
        "glass-sm": "0 4px 16px 0 rgba(0, 0, 0, 0.37)",
        "glass-amber": "0 0 35px -5px rgba(245, 158, 11, 0.22)",
        "glass-cyan": "0 0 35px -5px rgba(6, 182, 212, 0.22)",
        "glass-emerald": "0 0 25px -5px rgba(16, 185, 129, 0.25)",
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      }
    },
  },
  plugins: [],
};
