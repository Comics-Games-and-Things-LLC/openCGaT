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
import {ICart} from "../interfaces";
import {encodeCartReceipt, broadcastPrintCart} from "../printerBroadcast";

interface IPosPrintProps {
    cart: ICart
}

const POSPrintButton: React.FunctionComponent<IPosPrintProps> = (props: IPosPrintProps): JSX.Element => {

    const printCart = useCallback(() => {
        //const encoder = encodeCartReceipt(props.cart);
        //document.dispatchEvent(new CustomEvent("rPrint", {detail: {encoder: encoder}}));
        broadcastPrintCart(props.cart);
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