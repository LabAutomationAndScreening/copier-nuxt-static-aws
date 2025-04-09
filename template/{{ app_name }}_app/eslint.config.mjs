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
    // Disallow .js files in your source
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
);
