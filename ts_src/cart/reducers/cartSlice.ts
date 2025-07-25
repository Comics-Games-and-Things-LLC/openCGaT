import {createAsyncThunk, createSlice} from "@reduxjs/toolkit";
import getCookie from "../components/get_cookie";
import {ICart, IItem, IPOSProps} from "../interfaces";
import {RootState} from "../store";

const initialState = {
    cart: {} as ICart,
    pos: {} as IPOSProps,
    popoverOpen: false,
    buttonItems: [] as IItem[],
    errors: [] as string[],
}

interface IUpdateCart extends ICart {
    buttonItems: IItem[],
}


const preloadCartEl = document.getElementById("redux-preload:cart.cart");
if (preloadCartEl)
    initialState.cart = JSON.parse(preloadCartEl.textContent) as ICart; //Now loads just the cart ID

interface UpdateItemParams {
    id: number;
    quantity?: number;
    price?: number;
    pos?: boolean;
}

interface RemoveFromCartParams {
    id: number;
    pos?: boolean;
}


export const updateCart = createAsyncThunk<object, void, {
    state: RootState;
}>("cart/updateCart", async (_, {getState}) => {
    let item_ids = [] as number[];
    getState().cart.buttonItems.forEach((item) => {
        item_ids.push(item.id)
    })
    let cart = await fetch("/cart/cart/", {
        method: 'POST',
        body: JSON.stringify({"buttonItems": item_ids})
    }).then((response) => response.json());
    cart.loaded = true;
    return cart
});

// Update POS Cart is our more performant function which only updates the active cart, not the sidebar list
export const updatePOSCart = createAsyncThunk<// Return type of the payload creator
    object,
    // First argument to the payload creator
    void,
    // Types for ThunkAPI
    {
        state: RootState;
    }>("cart/updatePOSCart", async (_, {getState}) => {
    const pos = getState().cart.pos;
    return fetch(`${pos.url}/${pos.active_cart.id}/cart/`)
        .then((response) => response.json())
        .then((response) => response.active_cart); // Just the active cart part of the state
});

// Update POS refreshes both the cart and the list
export const updatePOSFull = createAsyncThunk<// Return type of the payload creator
    object,
    // First argument to the payload creator
    void,
    // Types for ThunkAPI
    {
        state: RootState;
    }>("cart/updatePOSFull", async (_, {getState, dispatch}) => {
    dispatch(setPOSLoading());
    const pos = getState().cart.pos;
    return fetch(`${pos.url}/${pos.active_cart.id}/data/`).then((response) =>
        response.json()
    );
});

export const updatePOSAndChangeToCartID = createAsyncThunk<// Return type of the payload creator
    object,
    // First argument to the payload creator
    number,
    // Types for ThunkAPI
    {
        state: RootState;
    }>("cart/updatePOSAndChangeToCartID", async (cartID, {getState}) => {
    const pos = getState().cart.pos;
    return fetch(`${pos.url}/${cartID}/cart/`)
        .then((response) => response.json())
        .then((response) => response.active_cart); // Just the active cart part of the state
});

export const addToCart = createAsyncThunk<// Return type of the payload creator
    object,
    // First argument to the payload creator
    UpdateItemParams,
    // Types for ThunkAPI
    {
        state: RootState;
    }>(
    "cart/addToCart",
    async (payload: UpdateItemParams, {getState, dispatch}) => {
        const pos = getState().cart.pos;
        if (payload.pos) {
            return fetch(
                `${pos.url}/${pos.active_cart.id}/add/${payload.id}/${payload.quantity}/`
            ).then(() => {
                return dispatch(updatePOSCart());
            });
        } else {
            return fetch(
                `/cart/add/${payload.id}/${payload.quantity}/`,
                {
                    method: "post",
                    body: JSON.stringify({
                        price: payload.price,
                    }),
                    headers: {"X-CSRFToken": getCookie("csrftoken")},
                }
            ).then(() => {
                return dispatch(updateCart());
            });
        }
    }
);

export const removeFromCart = createAsyncThunk<// Return type of the payload creator
    object,
    // First argument to the payload creator
    RemoveFromCartParams,
    // Types for ThunkAPI
    {
        state: RootState;
    }>(
    "cart/removeFromCart",
    async (payload: RemoveFromCartParams, {getState, dispatch}) => {
        const pos = getState().cart.pos;
        if (payload.pos) {
            return fetch(
                `${pos.url}/${pos.active_cart.id}/remove/${payload.id}`
            ).then(() => {
                return dispatch(updatePOSCart());
            });
        } else {
            return fetch(`/cart/remove/${payload.id}`).then(() => {
                return dispatch(updateCart());
            });
        }
    }
);

export const updateLine = createAsyncThunk<// Return type of the payload creator
    object,
    // First argument to the payload creator
    UpdateItemParams,
    // Types for ThunkAPI
    {
        state: RootState;
    }>(
    "cart/updateLine",
    async (payload: UpdateItemParams, {getState, dispatch}) => {
        const pos = getState().cart.pos;
        if (payload.pos) {
            return fetch(
                `${pos.url}/${pos.active_cart.id}/update/${payload.id}/`,
                {
                    method: "post",
                    body: JSON.stringify({
                        quantity: payload.quantity,
                        price: payload.price,
                    }),
                    headers: {"X-CSRFToken": getCookie("csrftoken")},
                }
            ).then(() => {
                return dispatch(updatePOSCart());
            });
        } else {
            return fetch(
                "/cart/update/" + payload.id + "/" + payload.quantity
            ).then(() => {
                return dispatch(updateCart());
            });
        }
    }
);

export const createNewPOSCart = createAsyncThunk<// Return type of the payload creator
    object,
    // First argument to the payload creator
    void,
    // Types for ThunkAPI
    {
        state: RootState;
    }>("cart/createNewPOSCart", async (_, {getState, dispatch}) => {
    const pos = getState().cart.pos;
    return fetch(`${pos.url}/new/`)
        .then((response) => response.json())
        .then((data) => {
            dispatch(setPOSCartID(data.id));
            dispatch(updatePOSCart());
        });
});

interface AddNewPOSItemProps {
    barcode: string;
}

export const addNewPOSItem = createAsyncThunk<// Return type of the payload creator
    object,
    // First argument to the payload creator
    AddNewPOSItemProps,
    // Types for ThunkAPI
    {
        state: RootState;
    }>(
    "cart/addNewPOSItem",
    async (payload: AddNewPOSItemProps, {getState, dispatch}) => {
        const pos = getState().cart.pos;
        console.log(`Attempting to add ${payload.barcode}`)
        let response = await fetch(`${pos.url}/${pos.active_cart.id}/add/${payload.barcode}/`) //Don't actually do anything with the return value
        if (!response.ok) {
            console.log("Could not add that item, logging error")
            dispatch(errorAdded(`Could not add '${payload.barcode}'`));
        }// or check for response.status
        return dispatch(updatePOSCart());
    }
)

interface AddCustomPOSItemProps {
    description: string;
    price: Number;
}

export const addCustomPOSItem = createAsyncThunk<// Return type of the payload creator
    object,
    // First argument to the payload creator
    AddCustomPOSItemProps,
    // Types for ThunkAPI
    {
        state: RootState;
    }>(
    "cart/addCustomPOSItem",
    async (payload: AddCustomPOSItemProps, {getState, dispatch}) => {
        const pos = getState().cart.pos;
        let response = await fetch(
            `${pos.url}/${pos.active_cart.id}/add_custom/`,
            {
                method: "post",
                body: JSON.stringify({
                    description: payload.description,
                    price: payload.price,
                }),
                headers: {"X-CSRFToken": getCookie("csrftoken")},
            }
        );

        if (response.ok) {
            dispatch(updatePOSCart());
            return response.json();
        } else {
            let text = await response.text();
            throw new Error("Request Failed: " + text);
        }
    }
);

interface SetOwnerPOSProps {
    email: string;
}

export const setPOSOwner = createAsyncThunk<// Return type of the payload creator
    object,
    // First argument to the payload creator
    SetOwnerPOSProps,
    // Types for ThunkAPI
    {
        state: RootState;
    }>(
    "cart/setOwnerPOS",
    async (payload: SetOwnerPOSProps, {getState, dispatch}) => {
        const pos = getState().cart.pos;
        let response = await fetch(
            `${pos.url}/${pos.active_cart.id}/set_owner/`,
            {
                method: "post",
                body: JSON.stringify({
                    email: payload.email,
                }),
                headers: {"X-CSRFToken": getCookie("csrftoken")},
            }
        );

        if (response.ok) {
            dispatch(updatePOSCart());
            return response.json();
        } else {
            let text = await response.text();
            throw new Error("Request Failed: " + text);
        }
    }
);

export const clearPOSOwner = createAsyncThunk<// Return type of the payload creator
    object,
    // First argument to the payload creator
    void,
    // Types for ThunkAPI
    {
        state: RootState;
    }>(
    "cart/setOwnerPOS",
    async (payload: void, {getState, dispatch}) => {
        const pos = getState().cart.pos;
        let response = await fetch(`${pos.url}/${pos.active_cart.id}/clear_owner/`);

        if (response.ok) {
            dispatch(updatePOSCart());
            return response.json();
        } else {
            let text = await response.text();
            throw new Error("Request Failed: " + text);
        }
    }
);


interface setPOSDiscountCodeProps {
    code: string;
}

export const setPOSDiscountCode = createAsyncThunk<// Return type of the payload creator
    object,
    // First argument to the payload creator
    setPOSDiscountCodeProps,
    // Types for ThunkAPI
    {
        state: RootState;
    }>(
    "cart/setDiscountCodePOS",
    async (payload: setPOSDiscountCodeProps, {getState, dispatch}) => {
        const pos = getState().cart.pos;
        let response = await fetch(
            `${pos.url}/${pos.active_cart.id}/set_code/`,
            {
                method: "post",
                body: JSON.stringify({
                    code: payload.code,
                }),
                headers: {"X-CSRFToken": getCookie("csrftoken")},
            }
        );

        if (response.ok) {
            dispatch(updatePOSCart());
            return response.json();
        } else {
            let text = await response.text();
            throw new Error("Request Failed: " + text);
        }
    }
);

export const cartSlice = createSlice({
    name: "cart",
    initialState,
    reducers: {
        setCart(state, action) {
            state.cart = action.payload as ICart;
        },
        setPOSLoading(state) {
            state.pos.loading = true;
        },
        setPOS(state, action) {
            state.pos = action.payload as IPOSProps;
        },
        setPOSCartID(state, action) {
            state.pos.active_cart.id = action.payload as number;
        },
        setPopoverOpen(state, action) {
            state.popoverOpen = action.payload;
        },
        addButtonItem(state, action) {
            const newItem = action.payload as IItem
            const index = state.buttonItems.findIndex((item) => item.id == newItem.id)
            if (index >= 0) {
                state.buttonItems[index] = newItem
            } else {
                state.buttonItems.push(newItem)
            }
        },
        errorAdded(state, action) {
            state.errors.push(action.payload)
        },
        errorsClear(state) {
            state.errors = [];
        },
    },
    extraReducers: (builder) => {
        builder
            .addCase(updateCart.fulfilled, (state, action) => {
                state.cart = action.payload as ICart;
                (action.payload as IUpdateCart).buttonItems.forEach((newItem) => {
                    const index = state.buttonItems.findIndex((item) => item.id == newItem.id)
                    if (index >= 0) {
                        state.buttonItems[index] = newItem
                    } else {
                        state.buttonItems.push(newItem)
                    }

                })
            })
            .addCase(updatePOSFull.fulfilled, (state, action) => {
                state.pos = action.payload as IPOSProps;
            })
            .addCase(updatePOSAndChangeToCartID.fulfilled, (state, action) => {
                state.pos.active_cart = action.payload as ICart;
            })
            .addCase(updatePOSCart.fulfilled, (state, action) => {
                state.pos.active_cart = action.payload as ICart;
            })
    },
});

export const {
    setCart,
    setPOS,
    setPOSLoading,
    setPOSCartID,
    setPopoverOpen,
    addButtonItem,
    errorAdded,
    errorsClear,
} = cartSlice.actions;
export default cartSlice.reducer;
