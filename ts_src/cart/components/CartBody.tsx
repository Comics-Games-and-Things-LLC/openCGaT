import * as React from "react";
import {FormEvent, useCallback, useEffect, useRef, useState} from "react";
import {Table} from 'react-bootstrap';
import CartRow from "./CartRow";
import {ICart, IRowProps} from "../interfaces";
import {useAppDispatch} from "../store";
import getCookie from "./get_cookie";
import {updateCart} from "../reducers/cartSlice";

export interface ICartBodyProps {
    cart: ICart;
    full: boolean;
    pos: boolean;
}


const CartBody: React.FunctionComponent<ICartBodyProps> = (props: ICartBodyProps): JSX.Element => {
    var dispatch = useAppDispatch();

    let type_header = null
    let partner_header = null
    let subtotal_header = null
    let summary = null


    let show_status_col = props.cart.show_status_col && props.full && !props.pos

    let num_empty_cols = 4;
    if (show_status_col) {
        num_empty_cols = 5
    } else if (props.pos) {
        num_empty_cols = 3
    }

    const remaining_balance = props.cart.final_total ?
        Number(props.cart.final_total) - Number(props.cart.total_paid) : Number(props.cart.estimated_total);

    const balance_string = "$" + (remaining_balance.toFixed(2))
    const balance_label = remaining_balance >= 0 ? "Balance" : "Change";

    const has_final_total = props.cart.final_total != null
    const total_label = has_final_total ? "Final Total" : "Estimated Total";
    const total_string = "$" + Number(has_final_total ? props.cart.final_total : props.cart.estimated_total).toFixed(2);

    const has_final_tax = props.cart.final_tax != null
    const tax_label = has_final_tax ? "Final Tax" : "Estimated Tax";
    const tax_string = "$" + Number(has_final_tax ? props.cart.final_tax : props.cart.estimated_tax).toFixed(2);

    const is_shipping_required = props.cart.is_shipping_required;
    const has_final_shipping = props.cart.final_ship != null
    const shipping_string = has_final_shipping ? "$" + (Number(props.cart.final_ship).toFixed(2)) : "Needs Address";

    const subtotal_string = "$" + (Number(props.cart.subtotal).toFixed(2))

    const total_paid_string = "$" + (Number(props.cart.total_paid).toFixed(2))
    const cash_paid_string = "$" + (Number(props.cart.cash_paid).toFixed(2))

    if (props.full) {
        partner_header = <th> Partner </th>
        type_header = <th scope="col">Type</th>
        subtotal_header = <th> Subtotal </th>


        summary = <>
            <FooterRow label={"Subtotal"} value={subtotal_string}
                       empty_cols={num_empty_cols} remove_col={props.cart.open}/>
            {is_shipping_required && <FooterRow label={"Shipping"} value={shipping_string}
                                                empty_cols={num_empty_cols} remove_col={props.cart.open}/>}
            <FooterRow label={tax_label} value={tax_string}
                       empty_cols={num_empty_cols} remove_col={props.cart.open}/>
            <FooterRow label={total_label} value={total_string}
                       empty_cols={num_empty_cols} remove_col={props.cart.open}/>
            {props.pos ? <>
                <FooterRow label={"Total Paid"} value={total_paid_string}
                           empty_cols={num_empty_cols} remove_col={props.cart.open}/>
                <FooterRow label={"Cash Paid"} value={cash_paid_string}
                           empty_cols={num_empty_cols} remove_col={props.cart.open}/>
                <FooterRow label={balance_label} value={balance_string}
                           empty_cols={num_empty_cols} remove_col={props.cart.open}/>

            </> : <></>}
        </>

    }

    let content = props.cart.loaded ?
        <p>Items in your cart will appear here.</p> :
        <i className="fas fa-spinner fa-pulse"></i>


    let count = 0
    if (props.cart.lines?.length > 0) {
        content = <Table className={"checkout-table w-full"}>
            <thead>
            <tr>
                <th>Item</th>
                {!props.pos ? <>
                    {type_header}
                    {partner_header}
                </> : <></>}

                {show_status_col ? <th>Status</th> : <></>}
                <th>#</th>
                <th>Price</th>
                {props.pos ? <th>Cost</th> : <></>}
                {subtotal_header}
                {props.cart.open ?
                    <th>Remove</th> : <></>
                }
            </tr>
            </thead>
            <tbody>
            {props.cart.lines.map((rowdata: IRowProps) => {
                rowdata = Object.assign({}, rowdata); // make a copy of the row props, so we can add additional params to it
                rowdata.key = rowdata.item.id
                rowdata.full = props.full
                rowdata.open = props.cart.open
                rowdata.show_status_col = show_status_col
                rowdata.pos = props.pos
                let row = React.createElement(CartRow, rowdata)
                count += rowdata.quantity
                return row
            })}
            {summary}
            </tbody>

        </Table>
    }
    const codeRef = useRef(null)
    const [code, setCode] = useState("")

    const [codeLoading, setCodeLoading] = useState(false)
    useEffect(() => setCodeLoading(false), [props.cart])
    const handleDiscountCode = useCallback((e: FormEvent) => {
        e.preventDefault()
        setCodeLoading(true)
        if (codeRef.current) {
            codeRef.current.value = "";
        }
        fetch(
            `/cart/code/${code}/`,
            {
                method: "post",
                body: JSON.stringify({}),
                headers: {"X-CSRFToken": getCookie("csrftoken")},
            }
        ).then(() => {
            return dispatch(updateCart());
        });


    }, [code, codeRef])
    return <div className="w-full">
        {content}
        {props.full && !props.pos ? <div>
            {props.cart.disclaimer}
        </div> : null}
        <div className="flex justify-end items-center p-2 w-full">
            {props.cart.discount_code || props.cart.discount_code_message ?
                <div className="flex-grow p-2">
                    Discount code: {props.cart.discount_code}
                    {props.cart.discount_code_message ? <React.Fragment>
                        <span className="font-medium font-italic">{props.cart.discount_code_message}</span>
                    </React.Fragment> : ""}
                </div>
                : ""}
            {props.cart.open && !props.pos ? <div className="flex-grow p-2">
                <form onSubmit={handleDiscountCode}>
                    <label>Code:</label>
                    <input type="text" name="discount_code" ref={codeRef} onChange={(e) => {
                        setCode(e.target.value)
                    }}></input>
                    {codeLoading ? <i className="fas fa-spinner fa-pulse"></i> :
                        <button type="submit" className="btn btn-primary">Apply</button>}

                </form>
            </div> : ""}
        </div>
    </div>
};

export default CartBody

interface ILabelRowProps {
    label: string;
    value: string | number | null;
    empty_cols: number
    remove_col: boolean; // Should we show the remove col (if the cart is open)
}

const FooterRow: React.FunctionComponent<ILabelRowProps> = (props: ILabelRowProps): JSX.Element => {
    return <tr>
        {Array(props.empty_cols).fill(undefined).map((e, i) => <td key={i}></td>)}
        <td>{props.label}</td>
        <td>{props.value}</td>
        {props.remove_col ? <td></td> : <></>}
    </tr>
}