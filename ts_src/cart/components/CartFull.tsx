import * as React from "react";
import {useState} from "react";
import { IItem } from "../interfaces";
import CartBody from "./CartBody";
import { removeFromCart, updateLine } from "../reducers/cartSlice";
import { useSelector } from "react-redux";
import { RootState, useAppDispatch } from "../store";

const CartFull: React.FunctionComponent = (): JSX.Element => {
    const currentCart = useSelector((state: RootState) => state.cart.cart);

    return <CartBody key={currentCart.id} full={true} pos={false} cart={currentCart}/>;

}

export default CartFull
