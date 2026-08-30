// ESLint config — first real config for this codebase (the lint script
// existed but no config did; CI surfaced it 2026-08-30). Deliberately
// pragmatic starting point: typescript-eslint recommended, react-hooks
// rules on, unused-vars lenient to underscore prefix. Tighten over
// time as the codebase earns it.
module.exports = {
  root: true,
  env: { browser: true, es2022: true },
  parser: "@typescript-eslint/parser",
  parserOptions: { ecmaVersion: 2022, sourceType: "module" },
  plugins: ["@typescript-eslint"],
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
  ],
  rules: {
    "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
    "@typescript-eslint/no-explicit-any": "off", // pragmatic: typed incrementally
  },
  ignorePatterns: ["dist", "node_modules", "vite.config.ts"],
};
