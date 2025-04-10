// https://nuxt.com/docs/api/configuration/nuxt-config
import { defineNuxtConfig } from "nuxt/config";
export default defineNuxtConfig({
  compatibilityDate: "2024-11-01",
  devtools: { enabled: true },
  modules: ["@nuxt/eslint", "@nuxt/ui"],
  css: ["~/assets/css/main.css"],
  experimental: { appManifest: false }, // https://github.com/nuxt/nuxt/issues/30461#issuecomment-2572616714
  vite: {
    // this seems to be explicitly needed when in a devcontainer in order for hot reloading to work
    server: {
      watch: {
        usePolling: true,
      },
    },
  },
});
