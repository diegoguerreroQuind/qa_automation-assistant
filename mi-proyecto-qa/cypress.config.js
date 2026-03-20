const { defineConfig } = require("cypress");
const createBundler = require("@bahmutov/cypress-esbuild-preprocessor");
const { addCucumberPreprocessorPlugin } = require("@badeball/cypress-cucumber-preprocessor");
const { createEsbuildPlugin } = require("@badeball/cypress-cucumber-preprocessor/esbuild");

module.exports = defineConfig({
  e2e: {
    specPattern: "cypress/e2e/features/**/*.feature", // Enrutado a tu carpeta específica
    async setupNodeEvents(on, config) {
      // Configuramos el plugin de Cucumber
      await addCucumberPreprocessorPlugin(on, config);
      
      // Configuramos esbuild para compilar los steps
      on(
        "file:preprocessor",
        createBundler({
          plugins: [createEsbuildPlugin(config)],
        })
      );

      return config;
    },
    supportFile: false, // Apagado porque son pruebas de API
  },
});
