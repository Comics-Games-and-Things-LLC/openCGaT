import * as React from "react";
import {useEffect, useState} from "react";
import {iCheckoutForm} from "./interfaces";
import AddressForm from "./AddressForm";
import getCookie from "../../cart/components/get_cookie";
import {updateCart} from "../../cart/reducers/cartSlice";
import {RootState, useAppDispatch} from "../../cart/store";
import {useSelector} from "react-redux";
import SimpleCard from "../../components/SimpleCard";
import {gap} from "../../components/ui_constants";


const CheckoutDeliveryMethod: React.FunctionComponent<iCheckoutForm> = (props): JSX.Element => {
    const currentCart = useSelector((state: RootState) => state.cart.cart);
    const [partnerSlug, setPartnerSlug] = useState(currentCart.pickup_partner?.slug)
    const dispatch = useAppDispatch();

    useEffect(() => {
        props.setSummary(summary())
    }, [currentCart.delivery_method, currentCart.pickup_partner, currentCart.shipping_address]);

    useEffect(() => {
        setPartnerSlug(currentCart.pickup_partner?.slug)
    }, [currentCart.pickup_partner])

    function summary(): string {
        if (currentCart.is_shipping_required) {
            console.log("Set summary for delivery method")
            if (currentCart.delivery_method === "Pickup All" && currentCart.pickup_partner) {
                return "Picking up at " + currentCart.pickup_partner.name;
            }
            if (currentCart.delivery_method === "Ship All" && currentCart.shipping_address) {
                return "Shipping to " + currentCart.shipping_address.first_name + " " + currentCart.shipping_address.last_name +
                    "\n" + currentCart.shipping_address.line1 + "\n" + currentCart.shipping_address.line2
            }
            return "Choose to pick up your order or set your shipping address";
        } else {
            if (currentCart.shipping_address) {
                return "Billing to " + currentCart.shipping_address.first_name + " " + currentCart.shipping_address.last_name +
                    "\n" + currentCart.shipping_address.line1 + "\n" + currentCart.shipping_address.line2
            }
            return "Set Billing Address"
        }
    }

    async function setPickup() {
        let response = await fetch(
            "/cart/api/set/pickup_partner/",
            {
                method: "post",
                body: JSON.stringify({
                    partner_slug: partnerSlug,
                }),
                headers: {"X-CSRFToken": getCookie("csrftoken")},
            }
        );
        if (response.ok) {
            dispatch(updateCart());
            console.log("Set Pickup Location!")
        } else {
            let text = await response.text();
            throw new Error("Request Failed: " + text);
        }
    }


    return <div className={`flex flex-col xl:flex-row ${gap}`}>
        {currentCart.available_pickup_partners?.length ?
            <SimpleCard>
                <div className={`flex justify-center ${gap}`}>
                    <h4>Pickup in store</h4>
                </div>
                {currentCart.in_store_pickup_only && <p>
                    This order is only eligible for in-store pickup
                </p>}
                <select name="pickupPartner" required={true} id="id_pickup_partner"
                        value={partnerSlug}
                        className="rounded-md"
                        onChange={(event) => {
                            setPartnerSlug(event.target.value)
                        }}>
                    <option value="">---------</option>
                    {currentCart.available_pickup_partners.map((partner) => {
                        return <option value={partner.slug}>{partner.name}</option>
                    })}
                </select>
                <div className={`flex justify-end ${gap}`}>
                    <button type="submit" className="btn btn-primary" onClick={setPickup}>Pickup at this Location
                    </button>
                </div>
            </SimpleCard> : <></>}
        {currentCart.is_shipping_required ? //Is shipping required means "is this a physical item order"
            currentCart.in_store_pickup_only ? "" : //If in store pickup is the only option, hide the shipping field
            <SimpleCard>
                <div className={`flex justify-center ${gap}`}>
                    <h4>Ship</h4>
                    <p>US only, $5.50 Flat Rate Shipping</p>
                </div>
                <AddressForm address={currentCart.shipping_address} phoneRequired={true}
                             limit_country_options={true} endpoint={`/cart/api/set/shippingAddress/`}/>
            </SimpleCard> : //Otherwise show the billing address field for digital orders
            <SimpleCard>
                <div className={`flex justify-center ${gap}`}>
                    <h4>Billing Address</h4>
                </div>
                <AddressForm address={currentCart.shipping_address} phoneRequired={false}
                             endpoint={`/cart/api/set/shippingAddress/`}/>
            </SimpleCard>}
    </div>
}


export default CheckoutDeliveryMethod;