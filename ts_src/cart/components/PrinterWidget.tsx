import * as React from "react";
import {useCallback, useEffect, useRef, useState} from "react";
import ReceiptPrinterEncoder from '@point-of-sale/receipt-printer-encoder';
import WebUSBReceiptPrinter from '@point-of-sale/webusb-receipt-printer';
import WebSerialReceiptPrinter from '@point-of-sale/webserial-receipt-printer';
import WebBluetoothReceiptPrinter from '@point-of-sale/webbluetooth-receipt-printer';

interface IConnectResult {
    productId: string;
    vendorId: string;
}

interface IReceiptPrinter {
    connect(): Promise<void>;

    disconnect(): Promise<void>;

    reconnect(port: IConnectResult): Promise<void>;

    print(data: Uint8Array): Promise<void>;
}


const PrinterWidget: React.FunctionComponent = (props): JSX.Element => {
    const [isFormOpen, setIsFormOpen] = useState(false);
    const [driver, setDriver] = useState('usb');
    const [baudRate, setBaudRate] = useState('9600');
    const [printerModel, setPrinterModel] = useState('');
    const [isConnected, setIsConnected] = useState(false);
    const [canConnect, setCanConnect] = useState(false);
    const [printerModels, setPrinterModels] = useState([]);
    const receiptPrinterRef = useRef<IReceiptPrinter | null>(null);


    const openForm = () => setIsFormOpen(true);
    const closeForm = () => setIsFormOpen(false);

    const checkConnectionCapability = useCallback(() => {
        const canConnectNow = (
            (driver === 'bluetooth' && !!navigator.bluetooth) ||
            (driver === 'usb' && !!navigator.usb) ||
            (driver === 'serial' && !!navigator.serial)
        );
        setCanConnect(canConnectNow);
    }, [driver]);

    const handleDriverChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
        const newDriver = e.target.value;
        setDriver(newDriver);
        localStorage.setItem('driver', newDriver);
    };

    const handleBaudRateChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
        setBaudRate(e.target.value);
    };

    const handlePrinterModelChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
        const newModel = e.target.value;
        setPrinterModel(newModel);
        localStorage.setItem('printerModel', newModel);
    };

    const connect = () => {
        connectHandler(null)
    }

    const tryReconnect = async () => {
        const productId = localStorage.getItem('productId');
        const vendorId = localStorage.getItem('vendorId');

        if (productId && vendorId) {
            await connectHandler({productId: productId, vendorId: vendorId})
        }
    }

    const connectHandler = async (reconnect: IConnectResult | null) => {
        let tempPrinter;
        if (driver === 'usb') {
            tempPrinter = new WebUSBReceiptPrinter()
        }

        if (driver === 'serial') {
            tempPrinter = new WebSerialReceiptPrinter({
                baudRate: baudRate,
            })
        }

        if (driver === 'bluetooth') {
            tempPrinter = new WebBluetoothReceiptPrinter()
        }
        console.log('Connecting with driver:', driver);
        receiptPrinterRef.current = tempPrinter; // Store in ref immediately

        tempPrinter.addEventListener('connected', (connectResult: IConnectResult) => {
                localStorage.setItem("productId", connectResult.productId);
                localStorage.setItem("vendorId", connectResult.vendorId);
                setIsConnected(true);
                console.log(`Connected Successfully to ${JSON.stringify(connectResult)}`)
            }
        )
        if (!reconnect) {
            tempPrinter.connect()

        } else {
            console.log(`Attempting to reconnect to ${JSON.stringify(reconnect)}`)

            tempPrinter.reconnect(reconnect)
        }
        document.removeEventListener("rPrint", rPrint);
        document.addEventListener("rPrint", rPrint);
    };

    const disconnect = () => {
        receiptPrinterRef.current.disconnect();

        console.log('Disconnecting');
        setIsConnected(false);
    };

    const rPrint = useCallback((event: Event) => {
        if (!(event instanceof CustomEvent)) {
            console.log("Was not passed an custom event")
            return
        }
        let encoder = event.detail?.encoder
        if (!encoder) {
            console.log("Was not passed an encoder")
            return
        }
        encoder
            .newline()
            .newline()
            .newline()
            .newline()
            .cut()
        if (!receiptPrinterRef.current) {
            console.log("Printer object not initialized")
            return
        } else {
            receiptPrinterRef.current.print(encoder.encode())
        }
    }, [])

    const testPrint = () => {
        let encoder = new ReceiptPrinterEncoder();
        if (encoder) {
            encoder.line('How many lines do we need to feed before we cut?')
                .line('8 ----------------------------')
                .line('7 ----------------------------')
                .line('6 ----------------------------')
                .line('5 ----------------------------')
                .line('4 ----------------------------')
                .line('3 ----------------------------')
                .line('2 ----------------------------')
                .line('1 ----------------------------')
                .line('0 Last line, cut below! ------')

            receiptPrinterRef.current.print(encoder.encode());
        }
    };

    useEffect(() => {
        // Load saved preferences
        const savedDriver = localStorage.getItem('driver');
        const savedPrinterModel = localStorage.getItem('printerModel');

        if (savedDriver) {
            setDriver(savedDriver);
        }

        // Load printer models if ReceiptPrinterEncoder is available
        const models = ReceiptPrinterEncoder.printerModels || [];
        setPrinterModels(models);

        if (savedPrinterModel) {
            setPrinterModel(savedPrinterModel);
        }

        tryReconnect()


    }, []);

    useEffect(() => {
        checkConnectionCapability();
    }, [checkConnectionCapability]);

    return <div className="printer_controls">
        <button className="open-button btn btn-primary" onClick={openForm}>Controls</button>
        <div
            className="printer_controls_content"
            id="printer_controls_content"
            style={{display: isFormOpen ? 'block' : 'none'}}
        >
            <h1>Printer Controls</h1>
            <div id="printer-config">
                <div className="printer-config-header" style={{
                    display: 'flex',
                    gap: '10px',
                    alignItems: 'center',
                    marginBottom: '20px',
                    flexWrap: 'wrap'
                }}>
                    <select
                        id="driver"
                        value={driver}
                        onChange={handleDriverChange}
                        disabled={isConnected}
                        style={{padding: '5px'}}
                    >
                        <option value="usb">USB</option>
                        <option value="serial">Serial</option>
                        <option value="bluetooth">Bluetooth</option>
                    </select>

                    {driver === 'serial' && (
                        <select
                            id="baudrate"
                            value={baudRate}
                            onChange={handleBaudRateChange}
                            disabled={isConnected}
                            style={{padding: '5px'}}
                        >
                            <option value="9600">9600</option>
                            <option value="38400">38400</option>
                            <option value="115200">115200</option>
                        </select>
                    )}

                    <select
                        id="printerModel"
                        value={printerModel}
                        onChange={handlePrinterModelChange}
                        style={{padding: '5px'}}
                    >
                        <option value="">Generic</option>
                        {printerModels.map((model: any) => (
                            <option key={model.id} value={model.id}>
                                {model.name}
                            </option>
                        ))}
                    </select>

                    {!isConnected ? (
                        <button
                            id="connect"
                            onClick={connect}
                            disabled={!canConnect}
                            className="btn btn-success"
                            style={{display: 'flex', alignItems: 'center', gap: '5px'}}
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 30 30"
                                 style={{width: '16px', height: '16px'}}>
                                <path fill="#2196f3"
                                      d="M 17 2 A 1 1 0 0 0 16.123047 2.5214844 L 8.1738281 15.433594 L 8.1738281 15.435547 A 1 1 0 0 0 8 16 A 1 1 0 0 0 9 17 L 14.5 17 L 13.019531 26.800781 A 1 1 0 0 0 13 27 A 1 1 0 0 0 14 28 A 1 1 0 0 0 14.882812 27.466797 L 14.884766 27.466797 L 22.806641 14.589844 L 22.796875 14.572266 C 22.915239 14.407976 23 14.217804 23 14 C 23 13.448 22.552 13 22 13 L 16.5 13 L 17.955078 3.2949219 A 1 1 0 0 0 18 3 A 1 1 0 0 0 17 2 z"></path>
                            </svg>
                            Connect
                        </button>
                    ) : (
                        <button
                            id="disconnect"
                            onClick={disconnect}
                            className="btn btn-warning"
                            style={{display: 'flex', alignItems: 'center', gap: '5px'}}
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48"
                                 style={{width: '16px', height: '16px'}}>
                                <path fill="#9C27B0" d="M21 4H26.001V43H21z"
                                      transform="rotate(45.001 23.5 23.5)"></path>
                                <path fill="#9C27B0" d="M21 4H26.001V43H21z"
                                      transform="rotate(134.999 23.5 23.5)"></path>
                            </svg>
                            Disconnect
                        </button>
                    )}

                    <button
                        className="btn btn-primary print"
                        onClick={testPrint}
                        disabled={!isConnected}
                        style={{display: 'flex', alignItems: 'center', gap: '5px', marginLeft: 'auto'}}
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48"
                             style={{width: '16px', height: '16px'}}>
                            <path fill="#90caf9" d="M36 5L32 9 28 5 24 9 20 5 16 9 12 5 8 9 4 5 4 36.5 36 36.5z"></path>
                            <path fill="#1976d2"
                                  d="M10 14H22V16H10zM25 14H30V16H25zM10 18H16V20H10zM19 18H30V20H19zM10 22H14V24H10zM17 22H23V24H17zM26 22H30V24H26z"></path>
                            <path fill="#bbdefb"
                                  d="M38.522,30h-29L9.478,43c0,0,27.579-0.004,29,0c3.038,0.009,5.51-2.894,5.522-6.483 S41.559,30.009,38.522,30z"></path>
                            <path fill="#1976d2" d="M10 26H20V28H10zM22 26H30V28H22z"></path>
                            <path fill="#42a5f5"
                                  d="M9.522,30C6.484,29.991,4.012,32.894,4,36.483C3.988,40.073,6.441,42.991,9.478,43 s5.51-2.894,5.522-6.483S12.559,30.009,9.522,30z"></path>
                            <path fill="#1976d2"
                                  d="M9.509,33C8.33,33,7.008,34.492,7,36.493c-0.004,1.042,0.351,2.035,0.973,2.725 c0.264,0.291,0.81,0.78,1.514,0.782c0.002,0,0.003,0,0.004,0c1.178,0,2.501-1.492,2.509-3.493c0.007-2.003-1.307-3.504-2.487-3.507 C9.511,33,9.51,33,9.509,33z"></path>
                        </svg>
                        Test
                    </button>
                </div>
            </div>

            <button type="button" className="btn btn-secondary" onClick={closeForm}>Close</button>
        </div>
    </div>
}

export default PrinterWidget;