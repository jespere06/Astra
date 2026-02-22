/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: "#00e5ff",
        secondary: "#7c3aed",
        bg: {
          dark: "#030308",
          card: "rgba(16, 16, 32, 0.6)",
        }
      }
    },
  },
  plugins: [],
}
