// Frontendni oldindan yig'adi: JSX -> JS (esbuild), Tailwind -> CSS, kutubxonalar va shrift -> ../static/.
// Ishga tushirish:  cd frontend && npm install && npm run build
// Natija (static/dist, static/vendor) loyiha bilan birga yetkaziladi: oddiy ishlatishda Node kerak emas.
import { build } from "esbuild";
import { execSync } from "node:child_process";
import { copyFileSync, mkdirSync } from "node:fs";

const out = "../static";
mkdirSync(`${out}/dist`, { recursive: true });
mkdirSync(`${out}/vendor`, { recursive: true });

await build({
  entryPoints: ["src/app.jsx"],
  outfile: `${out}/dist/app.js`,
  loader: { ".jsx": "jsx" },
  jsx: "transform",
  minify: true,
  target: ["chrome90", "safari14"],
  logLevel: "info",
});

execSync(`npx tailwindcss -c tailwind.config.js -i in.css -o ${out}/dist/app.css --minify`, { stdio: "inherit" });

const libs = {
  "node_modules/react/umd/react.production.min.js": "react.min.js",
  "node_modules/react-dom/umd/react-dom.production.min.js": "react-dom.min.js",
  "node_modules/prop-types/prop-types.min.js": "prop-types.min.js",
  "node_modules/recharts/umd/Recharts.js": "recharts.min.js",
  "node_modules/lucide/dist/umd/lucide.min.js": "lucide.min.js",
};
for (const [from, to] of Object.entries(libs)) copyFileSync(from, `${out}/vendor/${to}`);
for (const w of [400, 500, 600, 700]) {
  copyFileSync(`node_modules/@fontsource/inter/files/inter-latin-${w}-normal.woff2`, `${out}/vendor/inter-${w}.woff2`);
}
console.log("Frontend yig'ildi.");
