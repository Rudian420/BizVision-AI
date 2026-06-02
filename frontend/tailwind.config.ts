import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      // ── Colors ───────────────────────────────────────────
      colors: {
        void:    "#050A14",
        abyss:   "#080F1E",
        surface: {
          DEFAULT: "#0D1929",
          2:       "#112035",
          3:       "#162840",
        },
        border: {
          DEFAULT: "#1A2F4A",
          2:       "#243D5C",
        },
        cyan: {
          DEFAULT: "#00F5FF",
          dim:     "#00B8BF",
          muted:   "#006B70",
          glow:    "rgba(0, 245, 255, 0.15)",
        },
        gold: {
          DEFAULT: "#FFB800",
          dim:     "#CC9200",
        },
        violet: {
          DEFAULT: "#7C3AED",
          dim:     "#5B21B6",
        },
        emerald: {
          DEFAULT: "#10F07C",
          dim:     "#059669",
        },
        coral: {
          DEFAULT: "#FF3B6B",
          dim:     "#E11D48",
        },
        text: {
          primary:   "#E8F4FF",
          secondary: "#8AA0B8",
          muted:     "#4A6080",
          disabled:  "#2A3F55",
        },
      },

      // ── Typography ────────────────────────────────────────
      fontFamily: {
        ui:   ["var(--font-ui)", "system-ui", "sans-serif"],
        data: ["var(--font-data)", "monospace"],
      },
      fontSize: {
        "2xs": ["10px", { lineHeight: "1.4" }],
        xs:    ["11px", { lineHeight: "1.4" }],
        sm:    ["13px", { lineHeight: "1.5" }],
        base:  ["15px", { lineHeight: "1.6" }],
        lg:    ["18px", { lineHeight: "1.5" }],
        xl:    ["22px", { lineHeight: "1.4" }],
        "2xl": ["28px", { lineHeight: "1.3" }],
        "3xl": ["36px", { lineHeight: "1.2" }],
        "4xl": ["48px", { lineHeight: "1.1" }],
        "5xl": ["64px", { lineHeight: "1.0" }],
        hero:  ["96px", { lineHeight: "0.95" }],
      },

      // ── Spacing ───────────────────────────────────────────
      spacing: {
        "18": "4.5rem",
        "22": "5.5rem",
        "88": "22rem",
        "128": "32rem",
      },

      // ── Border Radius ─────────────────────────────────────
      borderRadius: {
        "4xl": "2rem",
        "5xl": "2.5rem",
      },

      // ── Box Shadow / Glow ─────────────────────────────────
      boxShadow: {
        "glow-cyan":    "0 0 20px rgba(0, 245, 255, 0.3), 0 0 60px rgba(0, 245, 255, 0.1)",
        "glow-gold":    "0 0 20px rgba(255, 184, 0, 0.3), 0 0 60px rgba(255, 184, 0, 0.1)",
        "glow-violet":  "0 0 20px rgba(124, 58, 237, 0.3), 0 0 60px rgba(124, 58, 237, 0.1)",
        "glow-emerald": "0 0 20px rgba(16, 240, 124, 0.3), 0 0 60px rgba(16, 240, 124, 0.1)",
        "glow-coral":   "0 0 20px rgba(255, 59, 107, 0.3), 0 0 60px rgba(255, 59, 107, 0.1)",
        glass: "0 4px 32px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(0, 245, 255, 0.04)",
      },

      // ── Animations ────────────────────────────────────────
      animation: {
        "ai-pulse":    "ai-pulse 3s ease-in-out infinite",
        "data-stream": "data-stream 2s linear infinite",
        "border-spin": "border-rotate 4s linear infinite",
        "float-slow":  "float 6s ease-in-out infinite",
        "float-fast":  "float 3s ease-in-out infinite",
      },
      keyframes: {
        "ai-pulse": {
          "0%, 100%": { opacity: "0.6", transform: "scale(1)" },
          "50%":      { opacity: "1",   transform: "scale(1.05)" },
        },
        "data-stream": {
          from: { transform: "translateY(0)", opacity: "1" },
          to:   { transform: "translateY(-100%)", opacity: "0" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%":      { transform: "translateY(-12px)" },
        },
      },

      // ── Backdrop Blur ─────────────────────────────────────
      backdropBlur: {
        xs: "2px",
      },

      // ── Background Image ──────────────────────────────────
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        "gradient-conic":  "conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))",
        "neural-grid": "linear-gradient(rgba(0,245,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(0,245,255,0.03) 1px, transparent 1px)",
      },
      backgroundSize: {
        "grid": "60px 60px",
      },
    },
  },
  plugins: [],
};

export default config;
