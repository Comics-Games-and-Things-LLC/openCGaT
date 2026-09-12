import ReceiptPrinterEncoder from '@point-of-sale/receipt-printer-encoder';
import {ICart} from './interfaces';

export const POS_PRINT_CHANNEL_NAME = 'pos_print_channel';

export type PrintTableColumn = {
    width?: number;
    align?: 'left' | 'center' | 'right';
    marginRight?: number;
    marginLeft?: number;
};

export type PrintTableRow = (string | number)[];

export interface IPrintTable {
    columns?: PrintTableColumn[];
    rows: PrintTableRow[];
}

export interface ICustomPrintPayload {
    title?: string;
    subtitle?: string;
    lines?: string[];
    table?: IPrintTable;
    tables?: IPrintTable[];
    footer?: string;
    cut?: boolean;
    barcode?: {
        value: string;
        symbology?: string;
        height?: number;
        width?: number;
    };
    qrcode?: {
        value: string;
        size?: number;
    };
}

export type PrintCommand = [string, ...any[]];

export interface IPrintCartMessage {
    type: 'PRINT_CART';
    payload: {
        cart: ICart;
    };
}

export interface IPrintCustomMessage {
    type: 'PRINT_CUSTOM';
    payload: ICustomPrintPayload;
}

export interface IPrintRawMessage {
    type: 'PRINT_RAW';
    payload: {
        data: Uint8Array | number[];
    };
}

export interface IPrintCommandsMessage {
    type: 'PRINT_COMMANDS';
    payload: {
        commands: PrintCommand[];
        cut?: boolean;
    };
}

export type IPrinterBroadcastMessage =
    | IPrintCartMessage
    | IPrintCustomMessage
    | IPrintRawMessage
    | IPrintCommandsMessage
    | { type: string; payload?: any; [key: string]: any };

/**
 * Helper to encode receipt title and subtitle.
 */
export function encodeHeader(
    title?: string,
    subtitle?: string,
    encoder: any = new ReceiptPrinterEncoder()
): any {
    if (title) {
        encoder.align('center').size(2, 2).line(title).size(1, 1);
    }
    if (subtitle) {
        encoder.align('center').line(subtitle).align('left');
    }
    return encoder;
}

/**
 * Calculates default column configurations based on column count and printer width.
 */
export function getDefaultTableColumns(numCols: number, totalColumns: number): PrintTableColumn[] {
    if (numCols === 2) {
        const firstCol = Math.max(4, Math.round(totalColumns * 0.15));
        const secondCol = totalColumns - firstCol - 1;
        return [
            {width: firstCol, marginRight: 1, align: 'right'},
            {width: secondCol, align: 'left'},
        ];
    }
    if (numCols === 3) {
        const firstCol = Math.max(3, Math.round(totalColumns * 0.1));
        const thirdCol = Math.max(6, Math.round(totalColumns * 0.2));
        const secondCol = totalColumns - firstCol - thirdCol - 2;
        return [
            {width: firstCol, marginRight: 1, align: 'right'},
            {width: secondCol, marginRight: 1, align: 'left'},
            {width: thirdCol, align: 'right'},
        ];
    }
    const colWidth = Math.floor(totalColumns / numCols);
    return Array.from({length: numCols}, () => ({
        width: colWidth,
        align: 'left' as const,
    }));
}

/**
 * Encodes a table onto the receipt printer encoder.
 */
export function encodeTable(
    table: IPrintTable,
    encoder: any = new ReceiptPrinterEncoder()
): any {
    if (!table.rows || table.rows.length === 0) {
        return encoder;
    }
    const columns = table.columns || getDefaultTableColumns(table.rows[0]?.length || 1, encoder.columns);
    encoder.table(columns, table.rows);
    return encoder;
}

/**
 * Encodes a cart into receipt printer encoder commands.
 */
export function encodeCartReceipt(
    cart: ICart,
    encoder: any = new ReceiptPrinterEncoder()
): any {
    const firstColumnWidth = Math.round(encoder.columns * 0.1);
    const secondColumnWidth = Math.round(encoder.columns * 0.7);

    encodeHeader(cart.payment_partner?.name, cart.id ? `Order ${cart.id}` : undefined, encoder);
    encoder.rule();

    if (cart.lines && cart.lines.length > 0) {
        encoder.table(
            [
                {width: firstColumnWidth, marginRight: 1, align: 'right'},
                {width: secondColumnWidth, align: 'left'},
                {
                    width: encoder.columns - firstColumnWidth - secondColumnWidth - 1,
                    align: 'right',
                },
            ],
            cart.lines.map((line) => {
                const qty = line.quantity != null ? line.quantity.toString() : '1';
                const name = line.item?.product?.name || line.description || 'Item';
                const price =
                    typeof line.price === 'number'
                        ? '$' + line.price.toFixed(2)
                        : line.price
                        ? '$' + line.price
                        : '$0.00';
                return [qty, name, price];
            })
        );
    }

    encoder.rule();

    const subtotal = cart.subtotal
        ? Number(cart.subtotal).toFixed(2)
        : '0.00';
    const tax = cart.final_tax || '0.00';
    const total = cart.final_total || '0.00';

    encoder.table(
        [
            {width: firstColumnWidth + secondColumnWidth, marginRight: 1, align: 'right'},
            {
                width: encoder.columns - firstColumnWidth - secondColumnWidth - 1,
                align: 'right',
            },
        ],
        [
            ['Subtotal', '$' + subtotal],
            ['Tax', '$' + tax],
            ['Total', '$' + total],
        ]
    );

    return encoder;
}

/**
 * Encodes a custom print payload into receipt printer commands.
 */
export function encodeCustomPayload(
    payload: ICustomPrintPayload,
    encoder: any = new ReceiptPrinterEncoder()
): any {
    if (payload.title || payload.subtitle) {
        encodeHeader(payload.title, payload.subtitle, encoder);
        encoder.rule();
    }
    if (payload.lines && payload.lines.length > 0) {
        payload.lines.forEach((line) => {
            encoder.line(line);
        });
    }
    if (payload.table) {
        encodeTable(payload.table, encoder);
    }
    if (payload.tables && payload.tables.length > 0) {
        payload.tables.forEach((tbl) => {
            encodeTable(tbl, encoder);
        });
    }
    if (payload.barcode && payload.barcode.value) {
        encoder.barcode(
            payload.barcode.value,
            payload.barcode.symbology || 'code128',
            payload.barcode.height || 60
        );
    }
    if (payload.qrcode && payload.qrcode.value) {
        encoder.qrcode(payload.qrcode.value, payload.qrcode.size || 6);
    }
    if (payload.footer) {
        encoder.rule().align('center').line(payload.footer);
    }
    return encoder;
}

/**
 * Encodes arbitrary command list into receipt printer encoder commands.
 */
export function encodeCommands(
    commands: PrintCommand[],
    encoder: any = new ReceiptPrinterEncoder()
): any {
    for (const cmd of commands) {
        if (Array.isArray(cmd) && cmd.length > 0) {
            const [method, ...args] = cmd;
            if (typeof encoder[method] === 'function') {
                encoder[method](...args);
            }
        }
    }
    return encoder;
}

/**
 * Helper to get or create a BroadcastChannel instance.
 */
export function getPrintBroadcastChannel(
    channelName = POS_PRINT_CHANNEL_NAME
): BroadcastChannel | null {
    if (typeof BroadcastChannel !== 'undefined') {
        return new BroadcastChannel(channelName);
    }
    return null;
}

/**
 * Broadcast an arbitrary print message to other tabs.
 */
export function broadcastPrint(
    message: IPrinterBroadcastMessage,
    channelName = POS_PRINT_CHANNEL_NAME
): boolean {
    const channel = getPrintBroadcastChannel(channelName);
    if (!channel) return false;
    channel.postMessage(message);
    channel.close();
    return true;
}

/**
 * Broadcast a cart print request to other tabs.
 */
export function broadcastPrintCart(
    cart: ICart,
    channelName = POS_PRINT_CHANNEL_NAME
): boolean {
    return broadcastPrint(
        {
            type: 'PRINT_CART',
            payload: {cart},
        },
        channelName
    );
}

/**
 * Broadcast a custom print payload to other tabs.
 */
export function broadcastPrintCustom(
    payload: ICustomPrintPayload,
    channelName = POS_PRINT_CHANNEL_NAME
): boolean {
    return broadcastPrint(
        {
            type: 'PRINT_CUSTOM',
            payload,
        },
        channelName
    );
}

/**
 * Broadcast raw bytes to other tabs.
 */
export function broadcastPrintRaw(
    data: Uint8Array | number[],
    channelName = POS_PRINT_CHANNEL_NAME
): boolean {
    return broadcastPrint(
        {
            type: 'PRINT_RAW',
            payload: {data},
        },
        channelName
    );
}

/**
 * Broadcast encoder commands to other tabs.
 */
export function broadcastPrintCommands(
    commands: PrintCommand[],
    cut = true,
    channelName = POS_PRINT_CHANNEL_NAME
): boolean {
    return broadcastPrint(
        {
            type: 'PRINT_COMMANDS',
            payload: {commands, cut},
        },
        channelName
    );
}
