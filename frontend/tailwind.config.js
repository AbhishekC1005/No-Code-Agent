/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["'Outfit'", "sans-serif"],
      },
      colors: {
        page: "#F8FAFC",
        heading: "#0F172A",
        body: "#475569",
        muted: "#94A3B8",
        borderLight: "#E5E7EB",
        brand: {
          blue: "#3B82F6",
          green: "#16A34A",
          purple: "#7C3AED",
        },
      },
      boxShadow: {
        soft: "0 4px 20px -2px rgba(15, 23, 42, 0.05)",
      },
      backdropBlur: {
        xs: "2px",
      },
    },
  },
  plugins: [],
};
