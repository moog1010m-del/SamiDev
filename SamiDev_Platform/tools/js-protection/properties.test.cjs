const assert = require('node:assert/strict');
const vm = require('node:vm');
const {renameInternalProperties} = require('./properties.cjs');
const code = `
class Ball { getRank() { return 7; } isSinking() { return false; } }
const object = { getJustPocketed: () => [new Ball()], publicBridge: 'unchanged' };
const ball = new Ball();
[ball.getRank(), ball['getRank'](), ball?.getRank(), object.getJustPocketed()[0].getRank(), ball.isSinking(), object.publicBridge];`;
const renamed = renameInternalProperties(code);
assert.deepEqual(JSON.parse(JSON.stringify(vm.runInNewContext(renamed.source))),
  JSON.parse(JSON.stringify(vm.runInNewContext(code))));
assert.ok(!renamed.source.includes('getRank'));
assert.ok(renamed.source.includes('publicBridge'));
assert.throws(() => renameInternalProperties(`const key = 'getRank'; object[key]();`), /reflective/);
assert.throws(() => renameInternalProperties(`const getRank = 2; const obj = {getRank};`), /shorthand/);
const dynamic = `const getRank = 'publicName'; const obj = {publicName: 9}; obj[getRank];`;
assert.equal(vm.runInNewContext(renameInternalProperties(dynamic).source), 9);
assert.equal(renameInternalProperties(code).source, renamed.source);
console.log('Static methods, calls, optional and quoted access, public bridge, dynamic keys and refusal cases passed');
