/** @type {import('jest').Config} */
module.exports = {
  testEnvironment: 'node',
  // Трансформируем ESM через babel-jest с пресетом expo
  transform: {
    '^.+\\.[jt]sx?$': 'babel-jest',
  },
  // Не трансформируем node_modules, кроме expo и react-native
  transformIgnorePatterns: [
    'node_modules/(?!(expo-sqlite|expo-location|expo-task-manager|@react-native-async-storage)/)',
  ],
  // Алиас для нативных модулей, которые не нужны в тестах
  moduleNameMapper: {
    '^expo-sqlite$': '<rootDir>/__mocks__/expo-sqlite.js',
    '^expo-location$': '<rootDir>/__mocks__/expo-location.js',
    '^expo-task-manager$': '<rootDir>/__mocks__/expo-task-manager.js',
  },
  testMatch: ['**/__tests__/**/*.test.js'],
  clearMocks: false,
};
