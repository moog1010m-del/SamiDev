const assert = require('node:assert/strict');
const vm = require('node:vm');
const {protectSource} = require('./protect.cjs');
const input = `globalThis.publicResult = (() => {
 class Ball { getRank() { return 7; } }
 const ball = new Ball();
 return [ball.getRank(), ball['getRank'](), Ball.name];
})();`;
(async () => {
 const a = '1'.repeat(32), b = '2'.repeat(32);
 const first = await protectSource(input, a);
 assert.equal(first, await protectSource(input, a), 'Same seed must reproduce output');
 const second = await protectSource(input, b);
 assert.notEqual(first, second, 'Different release seeds must change output');
 for (const source of [first, second]) {
  const context = {}; vm.runInNewContext(source, context);
  assert.deepEqual(JSON.parse(JSON.stringify(context.publicResult)), [7, 7, 'Ball']);
  assert.ok(!source.includes('getRank'));
  assert.ok(!source.includes('sourceMappingURL'));
  assert.ok(!source.includes(a));
 }
 await assert.rejects(protectSource(input, 'invalid'), /seed/);
 console.log('Terser + obfuscator: stable replay, different releases, public bridge and behavior passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
