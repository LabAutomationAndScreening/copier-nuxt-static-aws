/// <reference types="nuxt/app" />
// needed to help avoid typescript error in app.config.ts
declare global {
  const defineAppConfig: typeof import("nuxt/app").defineAppConfig;
}

export {};
