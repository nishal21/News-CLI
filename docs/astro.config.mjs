import { defineConfig } from "astro/config";
import sitemap from "@astrojs/sitemap";

// Project Pages: https://nishal21.github.io/News-CLI/
export default defineConfig({
  site: "https://nishal21.github.io",
  base: "/News-CLI/",
  trailingSlash: "ignore",
  integrations: [
    sitemap({
      filter: (page) => !page.includes("/404"),
    }),
  ],
});
