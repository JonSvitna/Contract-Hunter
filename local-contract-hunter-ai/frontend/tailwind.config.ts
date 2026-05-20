import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: "#0b2742",
        slate: "#334155",
        ink: "#0f172a",
        mist: "#f8fafc",
        sage: "#6a8f79"
      }
    }
  },
  plugins: []
};

export default config;
