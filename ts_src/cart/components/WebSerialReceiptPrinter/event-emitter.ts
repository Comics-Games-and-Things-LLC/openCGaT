class EventEmitter {
    private _events: any;

    constructor() {
        this._events = {};
    }

    on(e: string | number, f: (...args: any[]) => void) {
        this._events[e] = this._events[e] || [];
        this._events[e].push(f);
    }

    emit(e: string | number, ...args: any[]) {
        let fs = this._events[e];
        if (fs) {
            fs.forEach((f: (...args: any[]) => void) => {
                setTimeout(() => f(...args), 0);
            });
        }
    }
}

export default EventEmitter;