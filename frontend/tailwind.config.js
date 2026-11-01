/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,jsx}",
    "./components/**/*.{js,jsx}",
    "./context/**/*.{js,jsx}",
    "./lib/**/*.{js,jsx}",
  ],
  theme: {
    extend: {
      colors: {
        // "ink" is the dark surface scale used across the UI. 950/900/800/700
        // match --bg / --panel / --panel-2 / --border in styles/globals.css.
        ink: {
          950: "#05070a",
          900: "#0a0e13",
          800: "#10161d",
          700: "#1c2530",
          600: "#2a3644",
          500: "#3b4a5c",
        },
        // text-text / text-text-dim / bg-text. Hex (not CSS vars) so opacity
        // modifiers like text-text-dim/60 work.
        text: {
          DEFAULT: "#e7edf2",
          dim: "#8494a3",
        },
        accent: {
          DEFAULT: "#4dd9ec",
          dim: "#0fa8be",
          violet: "#a78bfa",
        },
        // One muted hue per agent. Used everywhere an agent is identified
        // (nav, dashboard panels, chat) so Echo/Atlas/Compass/Nova read as
        // one connected family. See lib/agents.js for the class strings.
        agent: {
          echo: "#4dd9ec",
          atlas: "#7c9cff",
          compass: "#e0b050",
          nova: "#a78bfa",
        },
      },
      boxShadow: {
        panel: "0 1px 0 rgba(255,255,255,0.03) inset, 0 12px 28px -16px rgba(0,0,0,0.65)",
      },
      fontFamily: {
        sans: ['"Inter"', "ui-sans-serif", "system-ui", "sans-serif"],
        display: ['"Space Grotesk"', "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "SFMono-Regular", "monospace"],
      },
    },
  },
  plugins: [],
};
