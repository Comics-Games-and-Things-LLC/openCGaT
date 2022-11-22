import * as React from "react";
import * as ReactDOM from "react-dom";

import {Provider} from "react-redux";
import store from "./cart/store";

import CartWidget from "./cart/components/CartWidget";
import CartFull from "./cart/components/CartFull";
import POS from "./cart/components/POS";
import AddToCartButton from "./cart/components/AddToCartButton";
import ProductListPageSort from "./cart/components/ProductListPageSort";
import {loadDownloads} from "./digital_files/download";
import {configUploadButtons} from "./digital_files/upload";
import {configureImageUploadButtons} from "./images/ImageUploader";

function wrapWithProviders(components: {
    [componentName: string]: React.FunctionComponent;
}) {
    Object.keys(components).forEach((componentName) => {
        let Component = components[componentName];
        components[componentName] = (props: any) => {
            return (
                <Provider store={store}>
                    <Component {...props} />
                </Provider>
            );
        };
    });

    return components;
}

const componentsUsingRedux = {
    CartWidget,
    CartFull,
    POS,
    AddToCartButton,
};

Object.assign(window, {
    // React
    React,
    ReactDOM,

    // components not using redux
    ProductListPageSort,

    // components using redux
    ...wrapWithProviders(componentsUsingRedux),
});

document.addEventListener("DOMContentLoaded", function () {
    loadDownloads();
    try {
        configUploadButtons();
    } catch {
    }
    configureImageUploadButtons();
});