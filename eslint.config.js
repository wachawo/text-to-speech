// eslint flat config for the web UI under www/ (Vue 2.7, no build step).
// The views are httpVueLoader components: a <script> that assigns
// module.exports, run in the browser as a plain script, so the source type is
// "script" and the loader's `module` is a global.
const js = require("@eslint/js");
const globals = require("globals");
const pluginVue = require("eslint-plugin-vue");

const APP_GLOBALS = {
  Vue: "readonly",
  Vuex: "readonly",
  VueRouter: "readonly",
  axios: "readonly",
  httpVueLoader: "readonly",
  bootstrap: "readonly",
  TtsRecorder: "readonly",
  TtsWait: "readonly",
  module: "writable",
};

module.exports = [
  { ignores: ["www/vendor/**", "www/fonts/**", "node_modules/**"] },
  js.configs.recommended,
  ...pluginVue.configs["flat/vue2-recommended"],
  {
    files: ["www/js/**/*.js", "www/views/**/*.vue"],
    languageOptions: {
      ecmaVersion: 2020,
      sourceType: "script",
      parserOptions: { ecmaVersion: 2020, sourceType: "script" },
      globals: { ...globals.browser, ...APP_GLOBALS },
    },
    rules: {
      // The catch parameter is kept for readability even when the handler
      // ignores it; the code predates optional catch bindings.
      "no-unused-vars": ["error", { caughtErrors: "none" }],
      // Markup formatting rules that fight hand-written .vue files: attributes
      // are broken across lines by meaning, elements like <i> and <audio> are
      // not self-closed, and components are registered as "tts-*" strings.
      "vue/max-attributes-per-line": "off",
      "vue/html-indent": "off",
      "vue/html-self-closing": "off",
      "vue/html-closing-bracket-newline": "off",
      "vue/first-attribute-linebreak": "off",
      "vue/singleline-html-element-content-newline": "off",
      "vue/multiline-html-element-content-newline": "off",
      "vue/attributes-order": "off",
      "vue/component-definition-name-casing": "off",
    },
  },
];
