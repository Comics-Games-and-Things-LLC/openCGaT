export function getPrinterClientId(): string {
    let id = localStorage.getItem('printer_client_id');
    if (!id) {
        if (typeof crypto.randomUUID === 'function') {
            id = crypto.randomUUID();
        } else {
            const bytes = crypto.getRandomValues(new Uint8Array(16));
            bytes[6] = (bytes[6] & 0x0f) | 0x40;
            bytes[8] = (bytes[8] & 0x3f) | 0x80;
            const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
            id = `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
        }
        localStorage.setItem('printer_client_id', id);
    }
    return id;
}