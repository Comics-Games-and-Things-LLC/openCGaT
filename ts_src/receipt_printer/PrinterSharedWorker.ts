/// <reference lib="webworker" />

// @ts-ignore
import WebUSBReceiptPrinter from './WebReceiptPrinter/WebUSBReceiptPrinter';
import WebSerialReceiptPrinter from './WebReceiptPrinter/WebSerialReceiptPrinter';
// @ts-ignore
import WebBluetoothReceiptPrinter from '@point-of-sale/webbluetooth-receipt-printer';

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

    addEventListener(event: string, handler: (data: any) => void): void;
}

interface PrinterServiceMessage {
    type: string;
    data?: any;
    clientId?: string;
}

// Explicitly declare self as SharedWorkerGlobalScope
declare const self: SharedWorkerGlobalScope;

class PrinterSharedWorker {
    private printer: IReceiptPrinter | null = null;
    private isConnected: boolean = false;
    private ports: Set<MessagePort> = new Set();
    private connectionInfo: IConnectResult | null = null;

    constructor() {
        self.addEventListener('connect', this.handleConnect.bind(this));
    }

    private handleConnect(event: MessageEvent): void {
        const port = event.ports[0];
        this.ports.add(port);

        // Notify new client of current status immediately
        this.sendToPort(port, {
            type: 'CONNECTION_STATUS',
            data: {
                isConnected: this.isConnected,
                connectionInfo: this.connectionInfo
            }
        });

        port.addEventListener('message', (e) => this.handleMessage(e, port));
        port.start();
    }

    private async handleMessage(event: MessageEvent, port: MessagePort): Promise<void> {
        const {type, data}: PrinterServiceMessage = event.data;

        switch (type) {
            case 'CONNECT_PRINTER':
                await this.connectPrinter(data);
                break;
            case 'DISCONNECT_PRINTER':
                await this.disconnectPrinter();
                break;
            case 'RECONNECT_PRINTER':
                await this.reconnectPrinter(data);
                break;
            case 'PRINT_DATA':
                await this.printData(data);
                break;
            case 'GET_CONNECTION_STATUS':
                this.sendToPort(port, {
                    type: 'CONNECTION_STATUS',
                    data: {
                        isConnected: this.isConnected,
                        connectionInfo: this.connectionInfo
                    }
                });
                break;
        }
    }

    private debug_print(message: string): void {
        this.broadcast({
            type: 'DEBUG',
            data: {message: message}
        });
    }

    private async connectPrinter({driver, baudRate}: { driver: string; baudRate: string }): Promise<void> {
        try {
            let tempPrinter: IReceiptPrinter;

            if (driver === 'usb') {
                tempPrinter = new WebUSBReceiptPrinter();
            } else if (driver === 'serial') {
                tempPrinter = new WebSerialReceiptPrinter({
                    baudRate: Number(baudRate),
                });
            } else if (driver === 'bluetooth') {
                tempPrinter = new WebBluetoothReceiptPrinter();
            } else {
                throw new Error(`Unsupported driver: ${driver}`);
            }
            this.debug_print("Connecting to printer with driver: " + driver);
            this.debug_print("Printer: " + JSON.stringify(tempPrinter));


            // Event listener was here

            this.printer = tempPrinter;
            await tempPrinter.connect();

        } catch (error) {
            this.broadcast({
                type: 'PRINTER_ERROR',
                data: {message: error instanceof Error ? error.message : 'Unknown error'}
            });
            throw (error)
        }
    }

    private async disconnectPrinter(): Promise<void> {
        try {
            if (this.printer) {
                await this.printer.disconnect();
                this.printer = null;
                this.isConnected = false;
                this.connectionInfo = null;
                this.broadcast({
                    type: 'PRINTER_DISCONNECTED'
                });
            }
        } catch (error) {
            this.broadcast({
                type: 'PRINTER_ERROR',
                data: {message: error instanceof Error ? error.message : 'Unknown error'}
            });
        }
    }

    private async reconnectPrinter(connectionData: IConnectResult & { baudRate?: string }): Promise<void> {
        try {
            if (!connectionData || !connectionData.type) {
                throw new Error('No connection data provided for reconnection');
            }

            let tempPrinter: IReceiptPrinter;
            const {type: driver} = connectionData;

            if (driver === 'usb') {
                tempPrinter = new WebUSBReceiptPrinter();
            } else if (driver === 'serial') {
                tempPrinter = new WebSerialReceiptPrinter({
                    baudRate: Number(connectionData.baudRate || 9600),
                });
            } else if (driver === 'bluetooth') {
                tempPrinter = new WebBluetoothReceiptPrinter();
            } else {
                throw new Error(`Unsupported driver: ${driver}`);
            }

            tempPrinter.addEventListener('connected', (connectResult: IConnectResult) => {
                this.connectionInfo = {...connectResult, type: driver};
                this.isConnected = true;
                this.broadcast({
                    type: 'PRINTER_CONNECTED',
                    data: this.connectionInfo
                });
            });

            tempPrinter.addEventListener('disconnected', () => {
                this.isConnected = false;
                this.connectionInfo = null;
                this.broadcast({
                    type: 'PRINTER_DISCONNECTED'
                });
            });

            this.printer = tempPrinter;
            await tempPrinter.reconnect(connectionData);

        } catch (error) {
            this.broadcast({
                type: 'PRINTER_ERROR',
                data: {message: error instanceof Error ? error.message : 'Unknown error'}
            });
        }
    }

    private async printData(encodedData: Uint8Array): Promise<void> {
        try {
            if (!this.printer || !this.isConnected) {
                throw new Error('Printer not connected');
            }
            await this.printer.print(encodedData);
            this.broadcast({type: 'PRINT_SUCCESS'});
        } catch (error) {
            this.broadcast({
                type: 'PRINTER_ERROR',
                data: {message: error instanceof Error ? error.message : 'Unknown error'}
            });
        }
    }

    private broadcast(message: PrinterServiceMessage): void {
        this.ports.forEach(port => {
            try {
                this.sendToPort(port, message);
            } catch (error) {
                this.ports.delete(port);
            }
        });
    }

    private sendToPort(port: MessagePort, message: PrinterServiceMessage): void {
        port.postMessage(message);
    }
}

const printerService = new PrinterSharedWorker();

export {};