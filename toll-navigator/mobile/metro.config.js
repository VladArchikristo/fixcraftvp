const { getDefaultConfig } = require('expo/metro-config');
const path = require('path');

const config = getDefaultConfig(__dirname);

// Exclude node_modules from file watching — fixes EMFILE on macOS
config.watchFolders = [__dirname];
config.resolver.blockList = [
  /node_modules\/.*\/node_modules\/.*/,
];

// Reduce number of watched files
config.watcher = {
  ...config.watcher,
  healthCheckInterval: 30000,
};

module.exports = config;
