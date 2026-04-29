/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_TARS_API?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

// Vite's ?raw import — text-as-string at build time
declare module "*.md?raw" {
  const content: string;
  export default content;
}
