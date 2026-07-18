import type { Config } from "tailwindcss";
export default { content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"], theme: { extend: { colors: { ink: "#111217", panel: "#18191f", line: "#292b33", acid: "#b8f36b", lilac: "#ad91d4" }, boxShadow: { glow: "0 0 40px rgba(184,243,107,.08)" } } }, plugins: [] } satisfies Config;
