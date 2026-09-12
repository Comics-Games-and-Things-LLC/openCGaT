const {merge} = require('webpack-merge');
const common = require('./webpack.common.js');
const webpack = require('webpack');

module.exports = merge(common, {
    mode: 'development',
    devtool: 'inline-source-map',
    watchOptions: {
        ignored: ['**/node_modules/**', '**/.git/**', '**/.venv/**'],
        aggregateTimeout: 300,
    },
    plugins: [
        new webpack.DefinePlugin({
            PRODUCTION: JSON.stringify(false),
            ENV_PROTOCOL: JSON.stringify("http://"),
        }),
    ]
});