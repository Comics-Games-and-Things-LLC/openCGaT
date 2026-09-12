const mix = require("laravel-mix");

const output =
    process.env.TAILWIND_MODE == "watch" ? "../static/css" : "static/css";

console.log(output);

mix.webpackConfig({
    watchOptions: {
        ignored: ['**/node_modules/**', '**/.git/**', '**/.venv/**'],
    },
});

mix.setPublicPath(output);
mix.postCss("src/stylesheets/default.css", "default.css", [
    require("postcss-import"),
    require("tailwindcss")("src/configs/default.js"),
    require("autoprefixer"),
]);


mix.postCss("src/stylesheets/valhalla.css", "valhalla.css", [
    require("postcss-import"),
    require("tailwindcss")("src/configs/valhalla.js"),
    require("autoprefixer"),
]);