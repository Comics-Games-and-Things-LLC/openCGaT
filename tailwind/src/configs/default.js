const defaultTheme = require("tailwindcss/defaultTheme");

const primary = {
    "50": "#f1f5f1",
    "100": "#dbf0e3",
    "200": "#ade7bf",
    "300": "#5dc969",
    "400": "#2caf5a",
    "500": "#1e9634",
    "600": "#1a8025",
    "700": "#196320",
    "800": "#13441a",
    "900": "#0d2a16",
};

module.exports = {
    content: ["../**/*.{html,tsx}"],
    theme: {
        // screens: {
        //   tw: "0px",
        //   ...defaultTheme.screens,
        // },
        extend: {
            colors: {
                primary: primary,
                neutral_back: {
                    DEFAULT: "#E5E7EB",
                    mid: "#343A40",
                    dark: "#1C211E",
                },
            },
            typography: {
                DEFAULT: {
                    css: {
                        lineHeight: "1.4",
                    },
                },
            },
            maxHeight: {
                "70-screen": "70vh",
            },
            outline: {
                "primary-500": primary["500"],
            },
        },
    },
    plugins: [
        require("@tailwindcss/forms"),
        require("@tailwindcss/typography"),
    ],
    corePlugins: {
        preflight: false,
        visibility: false, // Temporary fix for navbar
        textOpacity: false, // Disable text opacity for safari compatability

    },
    important: true,
};
