import EventEmitter from "./event-emitter";

class ReceiptPrinterDriver {
}

/*

Based on https://github.com/NielsLeenheer/WebSerialReceiptPrinter aka
MIT License

Copyright (c) 2023 Niels Leenheer

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
*/

class WebSerialReceiptPrinter extends ReceiptPrinterDriver {

    emitter: EventEmitter;

    options: SerialOptions;
    port: SerialPort = null;
    reader: ReadableStreamDefaultReader<Uint8Array> = null;
    queue: any[] = [];
    state = {
        running: false,
        closing: false
    }

    constructor(options: SerialOptions) {
        super();

        this.emitter = new EventEmitter();

        this.options = Object.assign({
            baudRate: 9600,
            bufferSize: 255,
            dataBits: 8,
            flowControl: 'none',
            parity: 'none',
            stopBits: 1
        }, options);

        navigator.serial.addEventListener('disconnect', event => {
            if (this.port == event.target) {
                this.emitter.emit('disconnected');
            }
        });
    }

    async connect() {
        try {
            let port = await navigator.serial.requestPort();

            if (port) {
                await this.open(port);
            }
        } catch (error) {
            console.log('Could not connect! ' + error);
        }
    }

    async reconnect(_previousPort: any) {

        console.log("Reconnecting")

        //Only works with one serial device

        let ports = await navigator.serial.getPorts();

        if (ports.length == 1) {
            await this.open(ports[0]);
        }
    }

    async open(port: SerialPort) {
        this.port = port;
        this.state.closing = false;

        await this.port.open(this.options);

        let info = this.port.getInfo();

        this.emitter.emit('connected', {
            type: 'serial',
            vendorId: info.usbVendorId || null,
            productId: info.usbProductId || null,
            language: null,
            codepageMapping: null
        });
    }

    async disconnect() {
        if (!this.port) {
            return;
        }

        this.state.closing = true;
        await this.reader.cancel();

        await this.port.close();

        this.port = null;

        this.emitter.emit('disconnected');
    }

    async listen() {
        await this.read();
        return true;
    }

    private async read() {
        while (this.port.readable && this.state.closing === false) {
            this.reader = this.port.readable.getReader();

            try {
                while (true) {
                    const {value, done} = await this.reader.read();

                    if (done) {
                        break;
                    }
                    if (value) {
                        this.emitter.emit('data', value);
                    }
                }
            } catch (error) {
            } finally {
                this.reader.releaseLock();
            }
        }
    }

    async print(command: any) {
        this.queue.push(command);
        this.run();
    };

    async run() {
        if (this.state.closing) {
            return;
        }

        if (this.state.running) {
            return;
        }

        this.state.running = true;

        const writer = this.port.writable.getWriter();

        let command;

        while (command = this.queue.shift()) {
            await writer.write(command);
        }

        writer.releaseLock();

        this.state.running = false;
    }

    addEventListener(n: string | number, f: (...args: any[]) => void) {
        this.emitter.on(n, f);
    }
}

export default WebSerialReceiptPrinter;