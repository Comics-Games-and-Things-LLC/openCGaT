import * as React from "react";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faShoppingCart } from "@fortawesome/free-solid-svg-icons";
import { useRef } from "react";
import { Button, Overlay, Popover } from "react-bootstrap";
import { ICart } from "../interfaces";
import CartBody from "./CartBody";
import { setPopoverOpen as _setPopoverOpen } from "../reducers/cartSlice";
import { RootState, useAppDispatch } from "../store";
import { useSelector } from "react-redux";

const CartWidget: React.FunctionComponent<ICart> = (props: ICart): JSX.Element => {
    const popoverOpen = useSelector((state: RootState) => state.cart.popoverOpen);
    const currentCart = useSelector((state: RootState) => state.cart.cart);
    const dispatch = useAppDispatch();
    const setPopoverOpen = (state: boolean) => dispatch(_setPopoverOpen(state));
    const toggle = () => setPopoverOpen(!popoverOpen);
    const target = useRef(null);

    // HACKY, I'm so sorry
    document.getElementById('dropdown01').onclick = () => {
        setPopoverOpen(false);
    };

    let count = 0
    if (currentCart.lines) currentCart.lines.forEach(line => count += line.quantity)
    return (
        <div>
            <div onClick={toggle} ref={target} className="text-primary-600"><FontAwesomeIcon icon={faShoppingCart} />
                {currentCart.loaded ? count : <i className="fas fa-spinner fa-pulse"></i>
                }
            </div>
            <Overlay
                show={popoverOpen}
                target={target.current}
                placement="bottom"
                containerPadding={20}
                popperConfig={{strategy: 'fixed'}}
                rootClose
                onHide={() => setPopoverOpen(false)}
            >
                <Popover id="CartButton">
                    <Popover.Title>
                        <Button href={"/checkout/v2/"}>Checkout</Button>
                    </Popover.Title>

                    <Popover.Content>
                        <CartBody full={false} pos={false} cart={currentCart}/>
                    </Popover.Content>
                </Popover>
            </Overlay>
        </div>
    );

}

export default CartWidget
