import * as React from "react";
import {useCallback, useEffect, useRef, useState} from "react";
import ReceiptPrinterEncoder from '@point-of-sale/receipt-printer-encoder';
import WebUSBReceiptPrinter from '@point-of-sale/webusb-receipt-printer';
import WebSerialReceiptPrinter from './WebSerialReceiptPrinter/WebSerialReceiptPrinter';
import WebBluetoothReceiptPrinter from '@point-of-sale/webbluetooth-receipt-printer';
import getCookie from "./get_cookie";
import {
    POS_PRINT_CHANNEL_NAME,
    encodeCartReceipt,
    encodeCustomPayload,
    encodeCommands
} from "../printerBroadcast";

interface IConnectResult {
    productId?: string;
    vendorId?: string;
    type?: string;
}

interface IReceiptPrinter {
    connect(): Promise<void>;

    disconnect(): Promise<void>;

    reconnect(port: IConnectResult): Promise<void>;

    print(data: Uint8Array): Promise<void>;
}

interface PrinterWidgetProps {
    partnerSlug?: string;
}


const PrinterWidget: React.FunctionComponent<PrinterWidgetProps> = (props): JSX.Element => {
    const [isFormOpen, setIsFormOpen] = useState(false);
    const [driver, setDriver] = useState('usb');
    const [baudRate, setBaudRate] = useState('9600');
    const [printerModel, setPrinterModel] = useState('');
    const [isConnected, setIsConnected] = useState(false);
    const [canConnect, setCanConnect] = useState(false);
    const [printerModels, setPrinterModels] = useState([]);
    const receiptPrinterRef = useRef<IReceiptPrinter | null>(null);

    const [clientId, setClientId] = useState<string>('');
    const [printerName, setPrinterName] = useState<string>('');
    const [onlinePrinters, setOnlinePrinters] = useState<Array<{ client_id: string, name: string }>>([]);
    const [destinationPrinterId, setDestinationPrinterId] = useState<string>('local');


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

    const handlePrinterNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const newName = e.target.value;
        setPrinterName(newName);
        localStorage.setItem('printer_name', newName);
    };

    const handleDestinationChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
        const newDest = e.target.value;
        setDestinationPrinterId(newDest);
        localStorage.setItem('destination_printer_id', newDest);
    };

    const connect = () => {
        connectHandler(null)
    }

    const tryReconnect = async () => {
        const lastConnection = JSON.parse(localStorage.getItem('lastConnection'));

        if (!lastConnection || !lastConnection.type) {
            return
        }

        await connectHandler(lastConnection)
    }

    const connectHandler = async (reconnect: IConnectResult | null) => {
        let tempPrinter;
        let tempDriver = driver
        console.log(JSON.stringify(reconnect))
        if (reconnect && reconnect.type) {
            setDriver(reconnect.type)
            tempDriver = reconnect.type
        }

        if (tempDriver === 'usb') {
            tempPrinter = new WebUSBReceiptPrinter()
        }

        if (tempDriver === 'serial') {
            tempPrinter = new WebSerialReceiptPrinter({
                baudRate: Number(baudRate),
            })
        }

        if (tempDriver === 'bluetooth') {
            tempPrinter = new WebBluetoothReceiptPrinter()
        }
        console.log('Connecting with driver:', tempDriver);
        receiptPrinterRef.current = tempPrinter; // Store in ref immediately

        tempPrinter.addEventListener('connected', (connectResult: IConnectResult) => {
                localStorage.setItem("lastConnection", JSON.stringify(connectResult));
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
    };

    const disconnect = () => {
        receiptPrinterRef.current.disconnect();

        console.log('Disconnecting');
        setIsConnected(false);
    };

    const fetchOnlinePrinters = useCallback(async () => {
        if (!props.partnerSlug) return;
        try {
            const response = await fetch(`/partner/${props.partnerSlug}/print_queue/printers/online/`);
            if (response.ok) {
                const data = await response.json();
                setOnlinePrinters(data.printers || []);
            }
        } catch (e) {
            console.error("Failed to fetch online printers", e);
        }
    }, [props.partnerSlug]);

    const registerPrinter = useCallback(async () => {
        if (!props.partnerSlug || !clientId) return;
        const formData = new FormData();
        formData.append('client_id', clientId);
        formData.append('name', printerName);

        try {
            await fetch(`/partner/${props.partnerSlug}/print_queue/printers/register/`, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': getCookie('csrftoken') || '',
                }
            });
        } catch (e) {
            console.error("Failed to register printer", e);
        }
    }, [props.partnerSlug, clientId, printerName]);

    const claimJob = useCallback(async (jobId: number) => {
        if (!props.partnerSlug || !clientId) return;
        try {
            const response = await fetch(`/partner/${props.partnerSlug}/print_queue/jobs/claim/`, {
                method: 'POST',
                body: JSON.stringify({client_id: clientId, job_id: jobId}),
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken') || '',
                }
            });
            if (response.status === 200) {
                const data = await response.json();
                if (data.status === 'success') {
                    await processJob(data.job);
                }
            }
        } catch (e) {
            console.error("Failed to claim job", e);
        }
    }, [props.partnerSlug, clientId]);

    const processJob = async (job: any) => {
        console.log("Processing network job:", job);
        const {id, job_type, payload} = job;

        try {
            if (job_type === 'RECEIPT') {
                handleBroadcastMessage({type: 'PRINT_CART', payload});
            } else if (job_type === 'LABEL') {
                if (payload.url) {
                    const response = await fetch(payload.url, {method: 'POST', mode: 'same-origin'});
                    const blob = await response.blob();
                    if ((window as any).OpenPrintImagePage) {
                        (window as any).OpenPrintImagePage(URL.createObjectURL(blob));
                    }
                }
            } else if (job_type === 'RAW') {
                handleBroadcastMessage({type: 'PRINT_RAW', payload});
            }

            // Mark as printed
            await fetch(`/partner/${props.partnerSlug}/print_queue/jobs/${id}/mark_printed/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken') || '',
                }
            });
        } catch (e) {
            console.error("Failed to process job", e);
        }
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
        if (event.detail?.cut !== false) {
            encoder
                .newline()
                .newline()
                .newline()
                .newline()
                .cut()
        }
        if (!receiptPrinterRef.current) {
            console.log("Printer object not initialized")
            return
        } else {
            receiptPrinterRef.current.print(encoder.encode())
        }
    }, [])

    const handleBroadcastMessage = useCallback((data: any) => {
        if (!data) return;
        console.log("Received broadcast message for printer:", data);

        const type = data.type || (data.cart ? 'PRINT_CART' : (data.commands ? 'PRINT_COMMANDS' : (data.lines || data.title ? 'PRINT_CUSTOM' : 'UNKNOWN')));
        const payload = data.payload !== undefined ? data.payload : data;

        if (type === 'PRINT_RAW') {
            const rawBytes = payload.data || payload;
            const uint8Array = rawBytes instanceof Uint8Array ? rawBytes : new Uint8Array(rawBytes);
            if (!receiptPrinterRef.current) {
                console.log("Printer object not initialized for raw print");
                return;
            }
            receiptPrinterRef.current.print(uint8Array);
            return;
        }

        let encoder: any = null;
        let shouldCut = true;

        if (type === 'PRINT_CART') {
            const cart = payload.cart || payload;
            encoder = encodeCartReceipt(cart);
        } else if (type === 'PRINT_CUSTOM' || type === 'PRINT_FORMATTED' || type === 'PRINT_TEXT') {
            encoder = encodeCustomPayload(payload);
            if (payload.cut !== undefined) {
                shouldCut = payload.cut;
            }
        } else if (type === 'PRINT_COMMANDS') {
            const commands = payload.commands || payload;
            encoder = encodeCommands(commands);
            if (payload.cut !== undefined) {
                shouldCut = payload.cut;
            }
        } else if (payload.encoder) {
            encoder = payload.encoder;
            if (payload.cut !== undefined) {
                shouldCut = payload.cut;
            }
        } else if (typeof data === 'string') {
            encoder = encodeCustomPayload({ lines: [data] });
        }

        if (encoder) {
            if (shouldCut) {
                encoder
                    .newline()
                    .newline()
                    .newline()
                    .newline()
                    .cut();
            }
            if (!receiptPrinterRef.current) {
                console.log("Printer object not initialized");
                return;
            } else {
                receiptPrinterRef.current.print(encoder.encode());
            }
        }
    }, []);

    useEffect(() => {
        document.addEventListener("rPrint", rPrint);

        let channel: BroadcastChannel | null = null;
        if (typeof BroadcastChannel !== 'undefined') {
            channel = new BroadcastChannel(POS_PRINT_CHANNEL_NAME);
            channel.onmessage = (event: MessageEvent) => {
                handleBroadcastMessage(event.data);
            };
        }

        return () => {
            document.removeEventListener("rPrint", rPrint);
            if (channel) {
                channel.close();
            }
        };
    }, [rPrint, handleBroadcastMessage]);

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

        // Identity initialization
        let id = localStorage.getItem('printer_client_id');
        if (!id) {
            id = crypto.randomUUID();
            localStorage.setItem('printer_client_id', id);
        }
        setClientId(id);

        const savedName = localStorage.getItem('printer_name') || 'Station ' + id.substring(0, 4);
        setPrinterName(savedName);

        const savedDest = localStorage.getItem('destination_printer_id') || 'local';
        setDestinationPrinterId(savedDest);

        tryReconnect()
    }, []);

    useEffect(() => {
        if (!props.partnerSlug || !clientId) return;

        const heartbeat = setInterval(() => {
            registerPrinter();
            fetchOnlinePrinters();
        }, 60000); // Every minute

        registerPrinter();
        fetchOnlinePrinters();

        return () => clearInterval(heartbeat);
    }, [props.partnerSlug, clientId, registerPrinter, fetchOnlinePrinters]);

    useEffect(() => {
        if (!props.partnerSlug || !clientId) return;

        const url = `/partner/${props.partnerSlug}/print_queue/stream/?client_id=${clientId}`;
        const eventSource = new EventSource(url);

        eventSource.onmessage = (event) => {
            if (event.data.includes(': heartbeat')) return;
            try {
                const data = JSON.parse(event.data);
                if (data.event === 'NEW_JOB') {
                    claimJob(data.job_id);
                }
            } catch (e) {
                console.error("Failed to parse SSE message", e);
            }
        };

        eventSource.onerror = (e) => {
            console.error("SSE Error", e);
            eventSource.close();
        };

        return () => {
            eventSource.close();
        };
    }, [props.partnerSlug, clientId, claimJob]);

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

            <div id="printer-identity" style={{marginBottom: '20px'}}>
                <label>Printer Name:
                    <input
                        type="text"
                        value={printerName}
                        onChange={handlePrinterNameChange}
                        style={{marginLeft: '10px', padding: '5px', borderRadius: '4px', border: '1px solid #ccc'}}
                    />
                </label>
                <div style={{fontSize: '0.8em', color: '#666'}}>ID: {clientId}</div>
            </div>

            <div id="printer-destination" style={{marginBottom: '20px'}}>
                <label>Send Prints To:
                    <select
                        value={destinationPrinterId}
                        onChange={handleDestinationChange}
                        style={{marginLeft: '10px', padding: '5px'}}
                    >
                        <option value="local">Local Printer (This Tab)</option>
                        {onlinePrinters.filter(p => p.client_id !== clientId).map(p => (
                            <option key={p.client_id} value={p.client_id}>{p.name}</option>
                        ))}
                    </select>
                </label>
            </div>

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