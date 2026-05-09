/** @type {import('tailwindcss').Config} */
export default {
  content: ["./src/**/*.{svelte,ts,html}"],
  theme: {
    extend: {
      colors: {
        green: {
          sponsor: "#16a34a",
        },
        red: {
          reject: "#dc2626",
        },
      },
    },
  },
  plugins: [],
};
