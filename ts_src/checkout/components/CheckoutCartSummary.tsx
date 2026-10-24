import * as React from "react";
import {Dispatch, FormEvent, SetStateAction} from "react";
import SimpleCard from "../../components/SimpleCard";
import CartBody from "../../cart/components/CartBody";
import getCookie from "../../cart/components/get_cookie";
import {updateCart} from "../../cart/reducers/cartSlice";
import {step} from "./CheckoutStep";
import {useSelector} from "react-redux";
import {RootState, useAppDispatch} from "../../cart/store";
import {gap} from "../../components/ui_constants";

interface iCartSummaryProps {
    setSection: Dispatch<SetStateAction<step>>
    xlView: boolean;
}

const CheckoutCartSummary: React.FunctionComponent<iCartSummaryProps> = (props): JSX.Element => {
    const currentCart = useSelector((state: RootState) => state.cart.cart);
    const dispatch = useAppDispatch();

    async function freezeCart(event: FormEvent) {
        event.preventDefault()
        let response = await fetch(
            `/cart/api/freeze/`,
            {
                method: "post",
                headers: {"X-CSRFToken": getCookie("csrftoken")},
            }
        );

        if (response.ok) {
            dispatch(updateCart());
            console.log("Froze Cart")
            props.setSection(step.LOGIN)
        } else {
            let text = await response.text();
            throw new Error("Request Failed: " + text);
        }
    }

    async function thawCart(event: FormEvent) {
        event.preventDefault()
        let response = await fetch(
            `/cart/api/thaw/`,
            {
                method: "post",
                headers: {"X-CSRFToken": getCookie("csrftoken")},
            }
        );

        if (response.ok) {
            dispatch(updateCart());
            console.log("Thawed Cart")
            props.setSection(step.START)
        } else {
            let text = await response.text();
            throw new Error("Request Failed: " + text);
        }
    }

    return <SimpleCard>
        <CartBody key={currentCart.id} cart={currentCart} full={true} pos={false}/>
        <div className={""}>
            <div className={`flex justify-end ${gap}`}>

                <button onClick={thawCart} className={"btn btn-secondary"}>
                    Edit
                </button>

                {/* Only show the next button if the cart isn't already frozen
                and can be frozen (has lines).
                */}
                {!props.xlView && (currentCart.lines.length > 0) ?
                    <button onClick={freezeCart} className={"btn btn-primary"}>
                        Next
                    </button>
                    : ""
                }
            </div>
        </div>
    </SimpleCard>;
}

export default CheckoutCartSummary;