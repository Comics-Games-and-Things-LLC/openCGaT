const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const ts = require('typescript');

function load(crypto, storage) {
    const source = fs.readFileSync(path.join(__dirname, 'printerClientId.ts'), 'utf8');
    const code = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS}}).outputText;
    const exports = {};
    vm.runInNewContext(code, {exports, crypto, localStorage: storage, Uint8Array});
    return exports.getPrinterClientId;
}

function storage(initial = null) {
    let value = initial;
    return {
        getItem: () => value,
        setItem: (key, id) => { value = id; },
    };
}

test('preserves a previously stored station ID', () => {
    assert.equal(load({}, storage('existing-id'))(), 'existing-id');
});

test('uses randomUUID when available and stores the result', () => {
    const store = storage();
    const getId = load({randomUUID: () => 'native-id'}, store);
    assert.equal(getId(), 'native-id');
    assert.equal(store.getItem(), 'native-id');
});

test('generates and persists a UUID without randomUUID', () => {
    const store = storage();
    const getId = load({getRandomValues: bytes => { bytes.fill(255); return bytes; }}, store);
    assert.equal(getId(), 'ffffffff-ffff-4fff-bfff-ffffffffffff');
    assert.equal(getId(), 'ffffffff-ffff-4fff-bfff-ffffffffffff');
});