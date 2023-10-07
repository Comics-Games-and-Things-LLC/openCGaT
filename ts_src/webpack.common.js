const path = require("path");
const webpack = require('webpack');

module.exports = {
    entry: {
        "react_index": "./react_index.tsx",
        "download_engine": "./digital_files/download_engine.ts",
    },
    target: "web",
    output: {
        path: path.resolve(__dirname, "../openCGaT/static/js/"),
        filename: "[name].js",
    },
    resolve: {
        extensions: [".js", ".jsx", ".json", ".ts", ".tsx"],
        alias: {
            path: require.resolve("path-browserify")
        }
    },
    module: {
        rules: [
            {
                test: /\.(ts|tsx)$/,
                loader: "ts-loader",
            },
            {
                test: /\.jsx$/,
                loader: "babel-loader",
            },
            {
                enforce: "pre",
                test: /\.js$/,
                loader: "source-map-loader",
            },
            {
                test: /\.css$/,
                loader: "css-loader",
            },
            {
                test: /\.(svg|png)$/,
                loader: "file-loader",
            },
        ],
    },
    plugins: [
        // Work around for Buffer is undefined:
        // https://github.com/webpack/changelog-v5/issues/10
        new webpack.ProvidePlugin({
            Buffer: ['buffer', 'Buffer'],
        }),
    ],
};
