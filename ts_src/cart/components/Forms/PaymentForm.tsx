//@flow

import * as React from "react";
import {useEffect} from "react";

// @ts-ignore
import Button from "../components/Button/Button.jsx";
// @ts-ignore
import Group from "../components/Group/Group.jsx";
// @ts-ignore
import Icon from "../components/Icon/Icon.jsx";
// @ts-ignore
import Section from "../components/Section/Section.jsx";
// @ts-ignore
import Text from "../components/Text/Text.jsx";
// @ts-ignore
import TestPaymentMethods from "./TestPaymentMethods.jsx";

import {ICart} from "../../interfaces";

interface IPaymentFormProps {
    onClickCollectCardPayments: () => void;
    onClickCollectCashPayments: () => void;
    onClickCancelPayment: () => void
    onChangeTestCardNumber: (value: string) => void
    onChangeTestPaymentMethod: (value: string) => void
    onClickSubmit: (value: string) => void
    cashOnly?: boolean
    cancelablePayment: boolean | null
    workFlowDisabled: string | true
    usingSimulator: boolean | null
    cart: ICart
}

const PaymentForm: React.FunctionComponent<IPaymentFormProps> = (props: IPaymentFormProps): JSX.Element => {

    const id_payment_amount = 'id_payment_amount'

    useEffect(() => {
            if (document.getElementById(id_payment_amount) && props.cart) {
                let payment_amount: HTMLInputElement = document.getElementById(id_payment_amount) as HTMLInputElement
                let remaining_balance = ""
                if (props.cart.final_total) {
                    remaining_balance = (Number(props.cart.final_total) - Number(props.cart.total_paid)).toFixed(2)
                } else {
                    remaining_balance = Number(props.cart.estimated_total).toFixed(2)
                }
                payment_amount.value = remaining_balance
            }
        },
        [props.cart]
    )

    return (
        <Section>
            <Group direction="column" spacing={16}>
                <Text size={16} color="dark">
                    Payment Options
                </Text>
                <Group direction="column" spacing={8}>
                    {props.usingSimulator && (
                        <TestPaymentMethods
                            onChangeTestCardNumber={props.onChangeTestCardNumber}
                            onChangeTestPaymentMethod={props.onChangeTestPaymentMethod}
                        />
                    )}
                    <input type={"number"} step='0.01' id={id_payment_amount}>
                    </input>
                    {!props.cashOnly ?
                        <Button
                            color="white"
                            onClick={props.onClickCollectCardPayments}
                            disabled={props.workFlowDisabled}
                            justifyContent="left"
                        >
                            <Group direction="row">
                                <Icon icon="card"/>
                                <Text color="blue" size={14}>
                                    Card
                                </Text>
                            </Group>
                        </Button>
                        : <></>}
                    <Button
                        color="white"
                        onClick={props.onClickCollectCashPayments}
                        disabled={props.workFlowDisabled}
                        justifyContent="left"
                    >
                        <Group direction="row">
                            <Icon icon="payments"/>
                            <Text color="blue" size={14}>
                                Cash
                            </Text>
                        </Group>
                    </Button>
                    <Button
                        color="white"
                        onClick={props.onClickCancelPayment}
                        disabled={!props.cancelablePayment}
                        justifyContent="left"
                    >
                        <Group direction="row">
                            <Icon icon="cancel"/>
                            <Text color="blue" size={14}>
                                Cancel payment
                            </Text>
                        </Group>
                    </Button>
                    <Button
                        color="white"
                        onClick={props.onClickSubmit}
                        disabled={props.workFlowDisabled || !(props.cart?.open)}
                        justifyContent="left"
                    >
                        <Group direction="row">
                            <Icon icon="lock"/>
                            <Text color="blue" size={14}>
                                Submit
                            </Text>
                        </Group>
                    </Button>
                </Group>
            </Group>
        </Section>
    );
}

export default PaymentForm;
