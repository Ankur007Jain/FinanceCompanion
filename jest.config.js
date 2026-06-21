const nextJest = require("next/jest");
const createJestConfig = nextJest({ dir: "./" });

module.exports = createJestConfig({
  testEnvironment: "node",
  testPathIgnorePatterns: ["<rootDir>/node_modules/", "<rootDir>/tests/e2e/"],
  reporters: [
    "default",
    ["jest-junit", { outputDirectory: "reports", outputName: "jest.xml" }],
  ],
  setupFilesAfterEnv: ["<rootDir>/jest.setup.ts"],
});
