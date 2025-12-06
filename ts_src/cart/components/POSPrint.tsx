import * as React from "react";
import {useCallback} from "react";
// @ts-ignore
import Button from "./components/Button/Button.jsx";
// @ts-ignore
import Group from "./components/Group/Group.jsx";
// @ts-ignore
import Icon from "./components/Icon/Icon.jsx";
// @ts-ignore
import Text from "./components/Text/Text.jsx";
import ReceiptPrinterEncoder from '@point-of-sale/receipt-printer-encoder';
import {ICart} from "../interfaces";

interface IPosPrintProps {
    cart: ICart
}

const POSPrintButton: React.FunctionComponent<IPosPrintProps> = (props: IPosPrintProps): JSX.Element => {

    const printCart = useCallback(() => {
        const encoder = new ReceiptPrinterEncoder()

        const firstColumnWidth = Math.round(encoder.columns * 0.1);
        const secondColumnWidth = Math.round(encoder.columns * 0.7);
        encoder
            .align('center').size(2, 2).line(props.cart.payment_partner.name).size(1, 1)
            .align('center').line(`Order ${props.cart.id}`).align('left')
            .rule()
        encoder.table(
            [
                {width: firstColumnWidth, marginRight: 1, align: "right"},
                {width: secondColumnWidth, align: "left"},
                {
                    width: encoder.columns - firstColumnWidth - secondColumnWidth - 1,
                    align: "right",
                },
            ],

            props.cart.lines.map(line => {
                return [line.quantity.toString(), line.item.product.name, "$" + line.price.toFixed(2)]
            })
            ,
        );
        encoder.rule()
        encoder.table(
            [
                {width: firstColumnWidth + secondColumnWidth, marginRight: 1, align: "right"},
                {
                    width: encoder.columns - firstColumnWidth - secondColumnWidth - 1,
                    align: "right",
                },
            ],
            [
                ["Subtotal", "$" + (Number(props.cart.subtotal).toFixed(2))],
                ["Tax", "$" + props.cart.final_tax],
                ["Subtotal", "$" + props.cart.final_total],
            ]
            ,
        );
        document.dispatchEvent(new CustomEvent("rPrint", {detail: {encoder: encoder}}))

    }, [props.cart]);

    return <Button
        color="white"
        onClick={printCart}
        disabled={(props.cart?.open)}
        justifyContent="left"
    >
        <Group direction="row">

            <Text color="blue" size={14}>
                Print
            </Text>
        </Group>
    </Button>
}
export default POSPrintButton;