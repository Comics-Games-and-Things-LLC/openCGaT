import * as React from "react";
import {useEffect} from "react";
import {ButtonStyles, IItem} from "../interfaces";
import {addButtonItem, addToCart, removeFromCart, setPopoverOpen, updateLine,} from "../reducers/cartSlice";
import {RootState, useAppDispatch} from "../store";
import {useSelector} from "react-redux";


export interface IAddProps extends IItem {
    pos: boolean;
}

const AddToCartButton: React.FunctionComponent<IAddProps> = (
    props: IAddProps
): JSX.Element => {

    const dispatch = useAppDispatch();

    useEffect(() => {
        dispatch(addButtonItem(props))
    }, [])


    const item: IItem = useSelector((state: RootState) => {
        const index = (state.cart.buttonItems as IItem[]).findIndex((item) => (item.id == props.id))
        if (index >= 0) {
            return state.cart.buttonItems[index] as IItem
        } else {
            return props as IItem
        }
    });

    const quantity_id = props.id + "_quantity_to_add";
    const quantity = useSelector((state: RootState) => {
        const itemLines = state.cart.cart?.lines?.filter(
            (row) => row.item.id === props.id
        );
        if (!itemLines || itemLines.length == 0) return 0;
        else return itemLines[0].quantity;
    });


    if (quantity < 1) {
        const handleAddToCart = () => {
            const price_input = document.getElementById(price_id) as HTMLInputElement
            dispatch(
                addToCart({
                    id: props.id,
                    quantity: 1,
                    pos: props.pos,
                    price: parseFloat(price_input?.value),
                })
            ).then(() => {
                dispatch(setPopoverOpen(true));
                const quantityInput = document.getElementById(
                    quantity_id
                ) as HTMLInputElement;
                if (quantityInput) {
                    quantityInput.focus();
                    quantityInput.setSelectionRange(0, quantityInput.value.length);
                }
            });
        };

        let color = [ //Button style Good
            "bg-primary-600",
            "hover:bg-primary-700",
            "focus:ring-primary-500",
        ];
        switch (item.button_status.style) {
            case ButtonStyles.BUTTON_STYLE_SOLD_OUT:
                color = ["bg-red-600"];
                break;
            case ButtonStyles.BUTTON_STYLE_BACKORDER:
                color = [
                    "bg-yellow-600",
                    "hover:bg-yellow-700",
                    "focus:ring-yellow-500",
                ];
                break;
            case ButtonStyles.BUTTON_STYLE_GOOD:
            default:
            //Leave color as the default from above.
        }

        if (props.type != "DigitalItem") {
            //InventoryItem or MTO item
            if (item.inventory <= 0) { //Use state in case inventory changes
                //TODO: Ensure max value is respected when quantity is increased
            }
        }

        let classes = [
            "inline-flex",
            "items-center",
            "justify-center",
            "px-6",
            "py-3",
            "border",
            "border-transparent",
            "text-xl",
            "font-medium",
            "rounded-md",
            "shadow-sm",
            "text-white",
            "focus:outline-none",
            "focus:ring-2",
            "focus:ring-offset-2",
            "w-full",
        ];

        // merge the color array with the classes array
        classes = classes.concat(color);
        const price_id = props.id + "_price_to_add_at";

        return (
            <div className="inline-flex flex-row gap-2 items-center">
                {props.is_pay_what_you_want ? <>
                    <label htmlFor={price_id} className="sr-only">
                        Price
                    </label>
                    <input
                        type="number"
                        id={price_id}
                        className="shadow-sm focus:ring-indigo-500 focus:border-indigo-500 block w-full border-2 border-gray-300 rounded-md"
                        placeholder="0"
                        step=".01"
                        defaultValue={props.default_price}
                        //onBlur={handleQuantityChange}
                    />
                </> : <></>
                }
                <button
                    id={"add_to_cart_" + props.id}
                    type="button"
                    className={classes.join(" ")}
                    onClick={handleAddToCart}
                    disabled={!item.button_status.enabled} //use state in case changes
                >
                    {item.button_status.text}
                </button>
            </div>
        );
    } else {
        const handleQuantityChange = (event: any) => {
            dispatch(
                updateLine({
                    id: props.id,
                    quantity: event.target.value,
                    pos: props.pos,
                })
            );
        };

        const changeQuantityBy = (delta: number) => {
            return () => {
                const inputField = document.getElementById(
                    quantity_id
                ) as HTMLInputElement;
                const currentValue = parseInt(inputField.value);
                if (currentValue + delta < 0) return;
                if (inputField) inputField.value = currentValue + delta + "";
                if (currentValue + delta == 0) {
                    dispatch(removeFromCart({id: props.id, pos: props.pos}));
                } else {
                    dispatch(
                        updateLine({
                            id: props.id,
                            quantity: currentValue + delta,
                            pos: props.pos,
                        })
                    );
                }
            };
        };

        const removeFromCartHandler = () => {
            dispatch(
                removeFromCart({
                    id: props.id,
                    pos: props.pos,
                })
            );
        };

        if (props.type == "DigitalItem") {
            return (
                <div className="inline-flex flex-row gap-2 items-center w-full justify-between">
                    <span
                        className="text-base p-3 border-2 border-transparent bg-gray-300 rounded-md flex-grow inline-flex justify-between items-center">
                        <i className="fas fa-download"/>&nbsp;Digital item in
                        cart
                    </span>
                    <button
                        type="button"
                        className="inline-flex items-center p-3 border-2 text-gray-500 border-gray-300 rounded-md shadow-sm bg-white hover:bg-gray-50 hover:text-gray-600 hover:border-gray-400 focus:outline-none focus:border-gray-400"
                        onClick={removeFromCartHandler}
                        aria-label="Remove from cart"
                    >
                        <svg
                            xmlns="http://www.w3.org/2000/svg"
                            className="h-6 w-6"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                        >
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth="2"
                                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                            />
                        </svg>
                    </button>
                </div>
            );
        } else {
            return (
                <div className="inline-flex flex-row gap-2 items-center">
                    <button
                        type="button"
                        className="inline-flex items-center p-3 border-2 text-gray-500 border-gray-300 rounded-md shadow-sm bg-white hover:bg-gray-50 hover:text-gray-600 hover:border-gray-400 focus:outline-none focus:border-gray-400"
                        onClick={changeQuantityBy(-1)}
                        aria-label="Decrease quantity"
                    >
                        <svg
                            xmlns="http://www.w3.org/2000/svg"
                            className="h-6 w-6"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                        >
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth="2"
                                d="M20 12H4"
                            />
                        </svg>
                    </button>
                    <label htmlFor={quantity_id} className="sr-only">
                        Quantity
                    </label>
                    <input
                        type="text"
                        id={quantity_id}
                        className="shadow-sm focus:ring-indigo-500 focus:border-indigo-500 block w-full border-2 border-gray-300 rounded-md"
                        placeholder="0"
                        defaultValue={quantity}
                        onBlur={handleQuantityChange}
                    />
                    <span className="text-base">in&nbsp;cart</span>
                    <button
                        type="button"
                        className="inline-flex items-center p-3 border-2 text-gray-500 border-gray-300 rounded-md shadow-sm bg-white hover:bg-gray-50 hover:text-gray-600 hover:border-gray-400 focus:outline-none focus:border-gray-400"
                        onClick={changeQuantityBy(1)}
                        aria-label="Increase quantity"
                    >
                        <svg
                            className="h-6 w-6"
                            xmlns="http://www.w3.org/2000/svg"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                            aria-hidden="true"
                        >
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth="2"
                                d="M12 4v16m8-8H4"
                            />
                        </svg>
                    </button>
                </div>
            );
        }
    }
};

export default AddToCartButton;
