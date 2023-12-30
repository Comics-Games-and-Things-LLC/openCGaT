import * as React from "react";
import {useState} from "react";
import {
    ConnectionStatus,
    DiscoverResult,
    ErrorResponse,
    IPaymentIntent,
    ISdkManagedPaymentIntent,
    Reader,
    Terminal
} from '@stripe/terminal-js';
import POSClient from "../POSClient";

import ConnectionInfo from "./ConnectionInfo/ConnectionInfo"

// @ts-ignore
import Readers from "./Forms/Readers"

import PaymentForm from "./Forms/PaymentForm"
// @ts-ignore
import RefundForm from "./Forms/RefundForm"
// @ts-ignore
import CartForm from "./Forms/CartForm"

import {ICart} from "../interfaces";
import {RootState, useAppDispatch} from "../store";
import {updatePOS} from "../reducers/cartSlice";
import {useSelector} from "react-redux";


interface IPOSPaymentProps {
    base_url: string
    cart: ICart
}

const POSPayment: React.FunctionComponent<IPOSPaymentProps> = (props): JSX.Element => {
    const [client, setClient] = useState<POSClient>()
    const [terminal, setTerminal] = useState<Terminal>()

    const dispatch = useAppDispatch();

    const [discoveredReaders, setDiscoveredReaders] = useState([])
    const [status, setStatus] = useState("requires_initializing")// requires_connecting || reader_registration || workflows
    const [reader, setReader] = useState<Reader>(null)
    const [workFlowInProgress, setWorkflowInProgress] = useState<string>()
    const [cancelablePayment, setCancelablePayment] = useState(false)
    const [discoveryWasCancelled, setDiscoveryWasCancelled] = useState(false)
    const [usingSimulator, setUsingSimulator] = useState(false)
    const [refundedChargeID, setRefundedChargeID] = useState<string>()
    const [refundedAmount, setRefundedAmount] = useState<number>()
    const [cancelableRefund, setCancelableRefund] = useState(false)
    const [pendingPaymentIntentSecret, setPendingPaymentIntentSecret] = useState<string>()

    const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus | string>()

    const [testCardNumber, setTestCardNumber] = useState("")
    const [testPaymentMethod, setTestPaymentMethod] = useState("visa")

    const errors = useSelector((state: RootState) => state.cart.errors);

    const isWorkflowDisabled = () =>
        cancelablePayment || (workFlowInProgress != null) || (errors.length > 0);

    const runWorkflow = async (workflowName: string, workflowFn: any) => {
        console.log(workflowName, workflowFn);
        setWorkflowInProgress(workflowName)
        try {
            await workflowFn();
        } finally {
            setWorkflowInProgress(null)
            dispatch(updatePOS());
        }
    };


    // 1. Stripe Terminal Initialization
    function initializeBackendClientAndTerminal() {


        // 1a. Initialize Client class, which communicates with the example terminal backend
        let client = new POSClient(props.base_url);


        // 1b. Initialize the StripeTerminal object
        let terminal = window.StripeTerminal.create({
            // 1c. Create a callback that retrieves a new ConnectionToken from the example backend
            onFetchConnectionToken: async () => {
                let connectionTokenResult = await client.createConnectionToken();
                return connectionTokenResult.secret;
            },
            // 1c. (Optional) Create a callback that will be called if the reader unexpectedly disconnects.
            // You can use this callback to alert your user that the reader is no longer connected and will need to be reconnected.
            onUnexpectedReaderDisconnect: () => {
                alert("Unexpected disconnect from the reader");
                setConnectionStatus("not_connected")
                setReader(null)
            },
            // 1c. (Optional) Create a callback that will be called when the reader's connection status changes.
            // You can use this callback to update your UI with the reader's connection status.
            onConnectionStatusChange: (ev) => {
                setConnectionStatus(ev.status)
                setReader(null)
            },
        })
        console.log("Initialization")
        setTerminal(terminal)
        setClient(client)
    }

    // 2. Discover and connect to a reader.
    const discoverReaders = async () => {
        setDiscoveryWasCancelled(false)

        // 2a. Discover registered readers to connect to.
        const discoverResult = await terminal.discoverReaders();

        if ((discoverResult as ErrorResponse).error) {
            console.log("Failed to discover: ", (discoverResult as ErrorResponse).error);
            return (discoverResult as ErrorResponse).error;
        } else {
            if (discoveryWasCancelled) return;
            setDiscoveredReaders((discoverResult as DiscoverResult).discoveredReaders)
            return (discoverResult as DiscoverResult).discoveredReaders;
        }
    };

    const cancelDiscoverReaders = () => {
        setDiscoveryWasCancelled(true)
    };

    const connectToSimulator = async () => {
        const simulatedResult = await terminal.discoverReaders({
            simulated: true,
        });
        await connectToReader((simulatedResult as DiscoverResult).discoveredReaders[0]);
    };

    const connectToReader = async (selectedReader: Reader) => {
            // 2b. Connect to a discovered reader.
            const connectResult = await terminal.connectReader(selectedReader);
            if ((connectResult as ErrorResponse).error) {
                console.log("Failed to connect:", (connectResult as ErrorResponse).error);
            } else {
                setUsingSimulator(selectedReader.id === "SIMULATOR")
                setStatus("workflows")
                setDiscoveredReaders([])
                setReader((connectResult as { reader: Reader }).reader)
            }
            return connectResult;
        }
    ;

    const disconnectReader = async () => {
        // 2c. Disconnect from the reader, in case the user wants to switch readers.
        await terminal.disconnectReader();
        setReader(null)
    };

    /*
    // 3. Terminal Workflows (Once connected to a reader)
    const updateLineItems = async () => {
        // 3a. Update the reader display to show cart contents to the customer
        await terminal.setReaderDisplay({
            type: "cart",
            cart: {
                line_items: [
                    // @ts-ignore
                    props.cart.lines.map((line) => {
                            return {
                                description: line.item.product.name,
                                amount: line.item.price,
                                quantity: line.quantity
                            }
                        }
                    )
                ],
                tax: Number(props.cart.final_tax),
                total: Number(props.cart.final_total),
            }
        });
        console.log("Reader Display Updated!");
        return;
    };*/

    // 3b. Collect a card present payment
    const collectCardPayment = async () => {
        // We want to reuse the same PaymentIntent object in the case of declined charges, so we
        // store the pending PaymentIntent's secret until the payment is complete.
        let paymentIntentSecret: string
        if (!pendingPaymentIntentSecret) {
            try {
                let chargeAmount = Number((document.getElementById('id_payment_amount') as HTMLInputElement).value)
                let cart_id = Number((document.getElementById('id_cart_id') as HTMLInputElement).value)
                let createIntentResponse = await client.createPaymentIntent(chargeAmount, cart_id);
                paymentIntentSecret = createIntentResponse.client_secret
                setPendingPaymentIntentSecret(createIntentResponse.client_secret);
            } catch (e) {
                // Suppress backend errors since they will be shown in logs
                console.log(e)
                return;
            }
        }
        console.log(paymentIntentSecret)
        // Read a card from the customer
        terminal.setSimulatorConfiguration({
            testPaymentMethod: testPaymentMethod,
            testCardNumber: testCardNumber,
        });
        const paymentMethodPromise = terminal.collectPaymentMethod(
            paymentIntentSecret
        );
        setCancelablePayment(true);
        const result = await paymentMethodPromise;
        if ((result as ErrorResponse).error) {
            console.log("Collect payment method failed:", (result as ErrorResponse).error.message);
        } else {
            const confirmResult = await terminal.processPayment(
                (result as { paymentIntent: ISdkManagedPaymentIntent }).paymentIntent
            );
            // At this stage, the payment can no longer be canceled because we've sent the request to the network.
            setCancelablePayment(false);
            if ((confirmResult as ErrorResponse).error) {
                alert(`Confirm failed: ${(confirmResult as ErrorResponse).error.message}`);
            } else if ((confirmResult as { paymentIntent: IPaymentIntent }).paymentIntent) {
                if ((confirmResult as { paymentIntent: IPaymentIntent }).paymentIntent.status !== "succeeded") {
                    try {
                        // Capture the PaymentIntent from your backend client and mark the payment as complete
                        let captureResult = await client.capturePaymentIntent(
                            (confirmResult as { paymentIntent: IPaymentIntent }).paymentIntent.id,
                            Number((document.getElementById('id_cart_id') as HTMLInputElement).value)
                        );
                        setPendingPaymentIntentSecret(null);
                        console.log("Payment Successful!");
                        return captureResult;
                    } catch (e) {
                        // Suppress backend errors since they will be shown in logs
                        return;
                    }
                } else {
                    setPendingPaymentIntentSecret(null);
                    console.log("Single-message payment successful!");
                    return confirmResult;
                }
            }
        }
    };

    // 3c. Cancel a pending payment.
    // Note this can only be done before calling `processPayment`.
    const cancelPendingPayment = async () => {
        await terminal.cancelCollectPaymentMethod();
        setPendingPaymentIntentSecret(null);
        setCancelableRefund(false)
        setWorkflowInProgress(null)
        console.log("Cancelled Pending Payment")
    };

    const collectCashPayment = async () => {
        let payment_amount: HTMLInputElement = document.getElementById('id_payment_amount') as HTMLInputElement
        let cart_id = Number((document.getElementById('id_cart_id') as HTMLInputElement).value)
        console.log(payment_amount)
        console.log(await client.payCash(Number(payment_amount.value), cart_id))

    }
    const submitCart = async () => {
        let cart_id = Number((document.getElementById('id_cart_id') as HTMLInputElement).value)
        console.log("Submitting cart")
        console.log(await client.payCash(0, cart_id))

    }


    const onChangeTestPaymentMethod = (value: string) => {
        setTestPaymentMethod(value);
    };

    const onChangeTestCardNumber = (value: string) => {
        setTestCardNumber(value);
    };

    const renderForm = () => {
        const no_reader = reader === null

        return (
            <>
                {no_reader ?
                    <Readers
                        onClickDiscover={() => discoverReaders()}
                        onClickCancelDiscover={() => cancelDiscoverReaders()}
                        readers={discoveredReaders}
                        onConnectToReader={connectToReader}
                        handleUseSimulator={connectToSimulator}
                    /> : <></>}

                <PaymentForm
                    workFlowDisabled={isWorkflowDisabled()}
                    cashOnly={no_reader}

                    onClickCollectCardPayments={() =>
                        runWorkflow("collectPayment", collectCardPayment)
                    }
                    onClickCollectCashPayments={() =>
                        runWorkflow("collectCashPayment", collectCashPayment)

                    }
                    onClickSubmit={() =>
                        runWorkflow("submitCart", submitCart)

                    }
                    onClickCancelPayment={cancelPendingPayment}
                    onChangeTestPaymentMethod={onChangeTestPaymentMethod}
                    onChangeTestCardNumber={onChangeTestCardNumber}
                    cancelablePayment={cancelablePayment}
                    usingSimulator={usingSimulator}
                    cart={props.cart}
                />
            </>
        );
    }

    React.useEffect(() => {
        initializeBackendClientAndTerminal()
    }, []); // <--- This hook is called only once

    return <div>
        <ConnectionInfo
            reader={reader}
            onClickDisconnect={disconnectReader}
        />
        {renderForm()}
    </div>
}

export default POSPayment