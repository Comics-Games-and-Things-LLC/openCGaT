import {ICart} from "../interfaces";
import * as React from "react";
import {ICartLists} from "./CartSelector";
import { useAppDispatch } from "../store";
import { updatePOSAndChangeToCartID } from "../reducers/cartSlice";


export interface ICartList {
    carts: [ICart?]
}

const CartList: React.FunctionComponent<ICartList> = (props: ICartList): JSX.Element => {
    

    return <>
        <ul>
            {props.carts.map((cart) =>
                <CartEntry key={cart.id} owner_info={cart.owner_info} cart_id={cart.id}/>
            )
            }
        </ul>
    </>
}

export default CartList

interface ICartLink {
    owner_info: string,
    cart_id: number,
}

const CartEntry: React.FunctionComponent<ICartLink> = (props: ICartLink): JSX.Element => {
    const dispatch = useAppDispatch();

    const handleOnClick = (event: React.MouseEvent<HTMLAnchorElement, MouseEvent>) => {
        dispatch(updatePOSAndChangeToCartID(props.cart_id));
    }
    return <li key={props.cart_id}>
        <a onClick={handleOnClick} >
            {props.cart_id} {props.owner_info}
        </a>
    </li>
}
