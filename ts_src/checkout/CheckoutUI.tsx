import * as React from "react";
import {useCallback, useEffect, useState} from "react";
import CheckoutStep, {step} from "./components/CheckoutStep";
import CheckoutEmailForm from "./components/CheckoutEmailForm";
import {RootState, useAppDispatch} from "../cart/store";
import {useSelector} from "react-redux";
import CheckoutDeliveryForm from "./components/CheckoutDeliveryMethod";
import CheckoutPaymentMethod from "./components/CheckoutPaymentMethod";
import {gap, xl_size} from "../components/ui_constants";
import CheckoutCartSummary from "./components/CheckoutCartSummary";


const CheckoutUI: React.FunctionComponent = (props): JSX.Element => {
    const currentCart = useSelector((state: RootState) => state.cart.cart);
    var dispatch = useAppDispatch();

    const [current_section, setSection] = useState(step.START)

    const [cartSummary, setCartSummary] = useState("")

    const [loginSummary, setLoginSummary] = useState("")
    const [deliverySummary, setDeliverySummary] = useState("")
    const [paymentSummary, setPaymentSummary] = useState("")

    const [xlView, setXLView] = useState(window.innerWidth >= xl_size)

    const handleXLView = useCallback(() => { // Set XL View when we are xl size, but not showing the cart. This determines if we show the cart in a sidebar
        setXLView((window.innerWidth >= xl_size) && (current_section != step.START))
    }, [current_section, window.innerWidth])

    useEffect(() => {
        window.addEventListener('resize', handleXLView);
        return () => window.removeEventListener('resize', handleXLView);
    }, [handleXLView]);

    useEffect(() => {
        handleXLView()
    }, [current_section])

    useEffect(() => {
        currentCart.ready_steps?.map((step) => {
                if (!(currentCart.completed_steps?.includes(step))) {
                    setSection(step)
                    // If we get a step from the server that's ready but not complete,
                    // set it as the current step.
                }
            }
        )
    }, [currentCart.ready_steps, currentCart.completed_steps])


    return <>
        <h2>Checkout</h2>

        <div className={`flex flex-col ${gap} overflow-x-auto ${(xlView ? "xl:flex-row-reverse" : "")}`}>

            <CheckoutStep title={"Cart summary"} id={step.START} summary={cartSummary}
                          current_section={current_section} setSection={setSection}
                          is_sidebar={xlView}>
                <CheckoutCartSummary setSection={setSection} xlView={xlView}/>

            </CheckoutStep>
            <div className={"flex flex-col grow w-full gap-2 lg:gap-4 xl:gap-8"}>
                <CheckoutStep title={"Login or Guest Checkout"} id={step.LOGIN} current_section={current_section}
                              setSection={setSection} summary={loginSummary}>
                    <CheckoutEmailForm setSummary={setLoginSummary}/>
                </CheckoutStep>

                {currentCart.is_shipping_required ?
                    <CheckoutStep title={"Delivery Method"} id={step.DELIVERY_METHOD} current_section={current_section}
                                  setSection={setSection} summary={deliverySummary}>
                        <CheckoutDeliveryForm setSummary={setDeliverySummary}/>
                    </CheckoutStep>
                    :
                    <CheckoutStep title={"Billing Address"} id={step.DELIVERY_METHOD} current_section={current_section}
                                  setSection={setSection} summary={deliverySummary}>
                        <CheckoutDeliveryForm setSummary={setDeliverySummary}/>
                    </CheckoutStep>
                }
                <CheckoutStep title={"Payment Method"} id={step.PAYMENT_COLLECTION} current_section={current_section}
                              setSection={setSection} summary={paymentSummary}>
                    <CheckoutPaymentMethod setSummary={setPaymentSummary}/>
                </CheckoutStep>
            </div>
        </div>

    </>
}


export default CheckoutUI;
