import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#10151f",
        clay: "#d1764f",
        wheat: "#f4e7cf",
        ocean: "#245e6f",
        mint: "#a8d7cd"
      },
      fontFamily: {
        display: ["'Space Grotesk'", "sans-serif"],
        body: ["'Manrope'", "sans-serif"]
      }
    }
  },
  plugins: []
} satisfies Config;
