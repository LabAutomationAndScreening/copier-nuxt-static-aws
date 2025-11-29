import vitest from "eslint-plugin-vitest";
import withNuxt from "./.nuxt/eslint.config.mjs";
export default withNuxt(
  {
    // Disallow <script lang="js"> in Vue files
    files: ["**/*.vue"],
    rules: {
      "vue/block-lang": [
        "error",
        {
          script: {
            lang: "ts",
          },
        },
      ],
    },
  },
  {
    // Disallow .js files in favor of typescript
    files: ["**/*.js"],
    ignores: [
      // add exceptions here if you must allow certain .js files
    ],
    rules: {
      "no-restricted-syntax": [
        "error",
        {
          selector: "Program",
          message: "Use .ts instead of .js.",
        },
      ],
    },
  },
  {
    files: ["**/*.{test,spec}.ts"],
    plugins: {
      vitest,
    },
    rules: {
      ...vitest.configs.all.rules,
      "vitest/no-focused-tests": ["error", { fixable: false }], // automatically fixing this could confuse the user
      "vitest/consistent-test-filename": ["error", { pattern: ".*\\.spec\\.ts$" }],
      "vitest/prefer-lowercase-title": "off", // no reason to force lowercase titles
      "vitest/consistent-test-it": "off", // consistency for this is overrated, let the dev choose what's most readable based on the test title
      "vitest/prefer-to-be-falsy": "off", // sometimes you want to check explicitly for false and not just falsy
      "vitest/prefer-to-be-truthy": "off", // sometimes you want to check explicitly for true and not just truthy
    },
  },
);
