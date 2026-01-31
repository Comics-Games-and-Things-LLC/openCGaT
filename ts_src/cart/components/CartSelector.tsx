import * as React from "react";
import CartList from "./CartList";
import {createNewPOSCart, updatePOSFull, markCartComplete} from "../reducers/cartSlice";
import {RootState, useAppDispatch} from "../store";
import {useSelector} from "react-redux";
import {FontAwesomeIcon} from "@fortawesome/react-fontawesome";
import {faSync} from "@fortawesome/free-solid-svg-icons";


export interface ICartLists {
}

const CartSelector: React.FunctionComponent<ICartLists> = (props: ICartLists): JSX.Element => {

    const dispatch = useAppDispatch();
    const loading = useSelector((state: RootState) => state.cart.pos.loading);
    const open_carts = useSelector((state: RootState) => state.cart.pos.open_carts);
    const pay_in_store_carts = useSelector((state: RootState) => state.cart.pos.pay_in_store_carts);
    const pickup_carts = useSelector((state: RootState) => state.cart.pos.pickup_carts);


    const createNewCart = () => {
        dispatch(createNewPOSCart());
    }
    const completeAndCreateNew = () => {
        dispatch(markCartComplete());
        dispatch(createNewPOSCart());
    }

    const refresh = () => {
        dispatch(updatePOSFull());
    }

    return <>
        <div className="col">
            <h2>Carts</h2>
            <a className='btn btn-success' onClick={createNewCart}>New Cart</a>
            <a className='btn btn-primary' onClick={completeAndCreateNew}>Complete and New Cart</a>
            <a className='btn btn-secondary' onClick={refresh}>
                <FontAwesomeIcon icon={faSync}/>
            </a>
            {loading ? <i className="fas fa-spinner fa-pulse"></i>
                : <>
                    <ul>
                        <CartList carts={open_carts || []}/>
                    </ul>
                    <ul>
                        <h3>Pay in Store</h3>
                        <CartList carts={pay_in_store_carts || []}/>
                    </ul>
                    <ul>
                        <h3>Pickup</h3>
                        <CartList carts={pickup_carts || []}/>
                    </ul>
                </>}
        </div>
    </>

}
export default CartSelector