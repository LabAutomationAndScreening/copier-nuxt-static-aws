// eslint-disable-next-line @typescript-eslint/no-unused-vars
import { NuxtConfig } from "nuxt/schema"; // unclear why this is showing up as an unused-var...it seems to be used as interface down below

declare module "nuxt/schema" {
  interface NuxtConfig {
    apollo?: {
      clients: {
        default: {
          httpEndpoint: string;
        };
      };
    };
  }
}
