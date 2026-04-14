module.exports = function (api) {
  const isTest = api.env('test');
  api.cache(() => isTest);
  return {
    presets: ['babel-preset-expo'],
    plugins: isTest
      ? [['@babel/plugin-transform-dynamic-import', { loose: true }]]
      : [],
  };
};
