{
  "$schema": "https://json.schemastore.org/eslintrc",
  "root": true,
  "env": {
    "browser": true,
    "es2020": true
  },
  "extends": [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:@typescript-eslint/stylistic",
    "plugin:react-hooks/recommended"
  ],
  "ignorePatterns": [
    "dist",
    ".eslintrc.cjs",
    "vite.config.ts"
  ],
  "parser": "@typescript-eslint/parser",
  "parserOptions": {
    "ecmaVersion": "latest",
    "sourceType": "module",
    "project": ["./tsconfig.json", "./tsconfig.node.json"]
  },
  "plugins": ["@typescript-eslint", "react-refresh"],
  "rules": {
    "@typescript-eslint/no-unused-vars": ["error", { "argsIgnorePattern": "^_" }],
    "@typescript-eslint/no-explicit-any": "warn",
    "react-refresh/only-export-components": [
      "warn",
      { "allowConstantExport": true }
    ]
  },
  "settings": {
    "react": {
      "version": "detect"
    }
  }
}
