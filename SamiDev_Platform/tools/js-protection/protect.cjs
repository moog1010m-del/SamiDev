// Build-time only. Rename only the audited property list; preserve public bridges.
const fs = require('node:fs');
const crypto = require('node:crypto');
const Terser = require('terser');
const Obfuscator = require('javascript-obfuscator');
const acorn = require('acorn');
const {renameInternalProperties} = require('./properties.cjs');
function reflectedNames(source) {
  const declared = new Set(), read = new Set();
  function walk(node) {
    if (!node || typeof node !== 'object') return;
    if (Array.isArray(node)) { node.forEach(walk); return; }
    if (['ClassDeclaration', 'ClassExpression', 'FunctionDeclaration', 'FunctionExpression'].includes(node.type) && node.id) declared.add(node.id.name);
    if (node.type === 'VariableDeclarator' && node.id.type === 'Identifier' && ['ClassExpression', 'FunctionExpression', 'ArrowFunctionExpression'].includes(node.init?.type)) declared.add(node.id.name);
    if (node.type === 'MemberExpression' && node.object.type === 'Identifier' &&
      ((!node.computed && node.property.name === 'name') || (node.computed && node.property.value === 'name'))) read.add(node.object.name);
    for (const value of Object.values(node)) if (value && typeof value === 'object') walk(value);
  }
  walk(acorn.parse(source, {ecmaVersion: 'latest'}));
  return [...read].filter(name => declared.has(name)).map(name => '^' + name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '$');
}
async function protectSource(input, releaseSeed, realtime = false) {
  if (!/^[0-9a-f]{32}$/.test(releaseSeed || '')) throw new Error('A 32-character hex release seed is required');
  const renamed = renameInternalProperties(input, releaseSeed).source;
  // No property mangling or aggressive optimizer; retain reflected function/class names.
  const minified = await Terser.minify(renamed, {
    compress: false, mangle: {toplevel: false}, keep_fnames: true, keep_classnames: true,
    sourceMap: false, format: {comments: /^!|@preserve|@license|@cc_on/i},
  });
  if (!minified.code) throw new Error('Terser produced no code');
  const seed = Number.parseInt(crypto.createHash('sha256').update(releaseSeed + '\0' + input).digest('hex').slice(0, 7), 16) || 1;
  return Obfuscator.obfuscate(minified.code, {
    target: 'browser', seed, compact: true, identifierNamesGenerator: 'hexadecimal',
    renameGlobals: false, renameProperties: false, ignoreImports: true,
    reservedNames: reflectedNames(minified.code),
    controlFlowFlattening: !realtime, controlFlowFlatteningThreshold: 0.06,
    deadCodeInjection: false, debugProtection: false,
    disableConsoleOutput: false, selfDefending: false,
    stringArray: !realtime, stringArrayEncoding: ['rc4'], stringArrayThreshold: 0.75,
    stringArrayRotate: true, stringArrayShuffle: true, stringArrayIndexShift: true,
    stringArrayWrappersCount: 1, stringArrayCallsTransform: true,
    stringArrayCallsTransformThreshold: 0.25,
    numbersToExpressions: !realtime, simplify: false, splitStrings: !realtime, splitStringsChunkLength: 10,
    transformObjectKeys: false, unicodeEscapeSequence: false, sourceMap: false,
  }).getObfuscatedCode() + '\n';
}
module.exports = {protectSource};
if (require.main === module) {
  const file = process.argv[2];
  protectSource(fs.readFileSync(file, 'utf8'), process.argv[3], process.argv[4] === '--realtime')
    .then(code => fs.writeFileSync(file, code))
    .catch(error => { console.error(error.message); process.exitCode = 1; });
}
