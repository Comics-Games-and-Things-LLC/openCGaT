import * as React from "react";
import {useEffect} from "react";
import {FontAwesomeIcon} from "@fortawesome/react-fontawesome";
import {faBox, faDownload, faMinusSquare} from "@fortawesome/free-solid-svg-icons";
import {IItem, IRowProps} from "../interfaces";
import {Button} from "react-bootstrap";
import {useAppDispatch} from "../store";
import {removeFromCart, updateLine} from "../reducers/cartSlice";


const CartRow: React.FunctionComponent<IRowProps> = (props: IRowProps): JSX.Element => {
    const dispatch = useAppDispatch();

    let qty_id = "qty_" + props.item.id
    let price_id = "price_" + props.price_per_unit_override

    let partner_cell = null
    let total_price_cell = null
    let quantity_field = <td>{props.quantity} </td>
    let type_cell = null

    const handleUpdateQuantity = (item_id: number, event: React.ChangeEvent<HTMLInputElement>) => {
        let quantity = event.target.value as unknown as number
        dispatch(updateLine({
            id: item_id,
            quantity: quantity,
            pos: props.pos
        }));
    }

    const handleUpdatePrice = (item_id: number, event: React.ChangeEvent<HTMLInputElement>) => {
        let price = event.target.value as unknown as number
        dispatch(updateLine({
            id: item_id,
            price: price,
            pos: props.pos
        }));
    }

    const handleRemoveFromCart = (item: IItem, event: React.MouseEvent<HTMLElement, MouseEvent>) => {
        dispatch(
            removeFromCart({id: item.id, pos: props.pos})
        );
    }

    useEffect(() => {
            if (document.getElementById(qty_id)) {
                let qty_element: HTMLInputElement = document.getElementById(qty_id) as HTMLInputElement
                qty_element.value = String(props.quantity)
            }
        },
        [props.quantity]
    )
    useEffect(() => {
            if (document.getElementById(price_id) && props.price_per_unit_override) {
                let price_element: HTMLInputElement = document.getElementById(price_id) as HTMLInputElement
                price_element.value = String(props.price_per_unit_override)
            }
        },
        [props.price_per_unit_override]
    )
    if (props.full) {
        if (props.item.type != "DigitalItem" && props.open) {
            quantity_field =
                <td><input id={qty_id} type='number' onChange={handleUpdateQuantity.bind(this, props.item.id)}
                           defaultValue={props.quantity} max={999} min={0} style={{width: '60px',}}/></td>
        }
        if (!props.pos) {
            partner_cell = <td>{props.item.partner.name}</td>
            switch (props.item.type) {

                case "DigitalItem":
                    type_cell = <td><FontAwesomeIcon icon={faDownload}/></td>
                    break;
                case "InventoryItem":
                    type_cell = <td><FontAwesomeIcon icon={faBox}/></td>
                    break;
                default:
                    type_cell = <td> {props.item.type} </td>
            }
        }
    }

    return (
        <tr>
            <td>
                <a href={"/shop/product/" + props.item.product.slug + "/"}>{props.item.product.name}</a>
                {props.description ? <React.Fragment>
                    <br/>
                    <span className="font-medium font-italic">{props.description}</span>
                </React.Fragment> : ""}
                {props.discount_code_message ? <React.Fragment>
                    <br/>
                    <span className="font-medium font-italic">{props.discount_code_message}</span>
                </React.Fragment> : ""}

            </td>
            {type_cell}
            {partner_cell}
            {props.show_status_col ? <td>
                <text style={{whiteSpace: 'pre-wrap'}}>{props.status}</text>
            </td> : <></>}
            {quantity_field}
            <td>${props.pos ? props.item.price : props.price}
                {props.price != props.item.default_price &&
                    <span style={{textDecoration: "line-through"}}> ${props.item.default_price} </span>}
                {props.pos ?
                    <input id={price_id} type='number' onChange={handleUpdatePrice.bind(this, props.item.id)}
                           defaultValue={props.price_per_unit_override} max={9999} min={-9999}/>
                    : <></>}
            </td>
            {props.show_cost_col ? <td>
                ${props.estimated_cost ? props.estimated_cost.toFixed(2) : ""}
            </td> : <></>
            }
            {props.full ? <td>${(props.price * props.quantity).toFixed(2)}
                {
                    props.price != props.item.default_price &&
                    <span
                        style={{textDecoration: "line-through"}}> ${(props.item.default_price * props.quantity).toFixed(2)} </span>
                }

            </td> : <></>
            }
            {props.open ?

                <td>

                    <Button variant={"danger"} onClick={handleRemoveFromCart.bind(this, props.item)}>
                        <FontAwesomeIcon icon={faMinusSquare}/>
                    </Button>
                </td>
                : <></>
            }

        </tr>
    )
}

export default CartRow
