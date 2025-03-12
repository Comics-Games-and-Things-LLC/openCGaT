const defaultTheme = require("tailwindcss/defaultTheme");

//https://coolors.co/gradient-maker/f9ffff-f1fbff-e8f6fe-d6edfc-c2e3fb-abd7f9-92caf7-73baf4-54aaf1-3a9cef?position=0,5,10,20,30,40,50,60,70,80&opacity=100,100,100,100,100,100,100,100,100,100&type=linear&rotation=90
const primary = {
    "50": "#F1FBFF",
    "100": "#E8F6FE",
    "200": "#D6EDFC",
    "300": "#C2E3FB",
    "400": "#ABD7F9",
    "500": "#92CAF7",
    "600": "#73BAF4",
    "700": "#54AAF1",
    "800": "#3A9CEF",
    "900": "#3A9CEF",
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
