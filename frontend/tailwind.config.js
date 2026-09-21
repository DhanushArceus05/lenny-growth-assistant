/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        ink: "#12100E",
        "ink-raised": "#1B1815",
        parchment: "#F4EFE8",
        amber: {
          DEFAULT: "#D98E39",
          soft: "#3A2A17",
        },
        slate: {
          DEFAULT: "#5B6B79",
          soft: "#2A3038",
        },
      },
      fontFamily: {
        display: [
          "Fraunces",
          "ui-serif",
          "Georgia",
          "serif",
        ],
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};
