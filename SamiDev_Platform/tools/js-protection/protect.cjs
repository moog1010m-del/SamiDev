// Build-time only. Never rename object properties or public bridge names.
const fs = require('node:fs');
const crypto = require('node:crypto');
const Obfuscator = require('javascript-obfuscator');
const file = process.argv[2];
const source = fs.readFileSync(file, 'utf8');
const seed = Number.parseInt(crypto.createHash('sha256').update(source).digest('hex').slice(0, 7), 16) || 1;
const result = Obfuscator.obfuscate(source, {
  target: 'browser', seed, compact: true, identifierNamesGenerator: 'hexadecimal',
  renameGlobals: false, renameProperties: false, ignoreImports: true,
  controlFlowFlattening: false, deadCodeInjection: false, debugProtection: false,
  disableConsoleOutput: false, selfDefending: false, stringArray: false,
  numbersToExpressions: false, simplify: false, splitStrings: false,
  transformObjectKeys: false, unicodeEscapeSequence: false, sourceMap: false,
});
fs.writeFileSync(file, result.getObfuscatedCode() + '\n');
