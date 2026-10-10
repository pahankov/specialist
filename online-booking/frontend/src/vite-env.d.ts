/// <reference types="vite/client" />
/// <reference types="vitest/globals" />

// Vite define() injects these at build time — TypeScript needs to know about them
declare const __BUILD_ID__: string;

interface ImportMetaEnv {
  readonly VITE_API_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
