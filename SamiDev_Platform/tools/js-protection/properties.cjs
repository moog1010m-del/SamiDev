// An explicit audited list, not unrestricted property mangling.
const acorn = require('acorn');
const crypto = require('node:crypto');
const profile = require('./property-profile.json');
function renameInternalProperties(source, releaseSeed = '') {
  const names = new Map(profile.properties.map(name => [name, '_p' + crypto.createHash('sha256')
    .update(profile.version + ':' + releaseSeed + ':' + name).digest('hex').slice(0, 12)]));
  for (const value of names.values()) {
    if (source.includes(value)) throw new Error('Property alias already exists in input');
  }
  const edits = new Map();
  const counts = Object.fromEntries(profile.properties.map(name => [name, 0]));
  function visit(node, parent) {
    if (!node || typeof node !== 'object') return;
    if (Array.isArray(node)) { for (const value of node) visit(value, parent); return; }
    const name = node.type === 'Identifier' ? node.name : node.type === 'Literal' ? node.value : null;
    if (names.has(name)) {
      const staticKey = node.type === 'Literal' || !parent?.computed;
      const member = staticKey && parent?.type === 'MemberExpression' && parent.property === node;
      const key = staticKey && ['Property', 'MethodDefinition', 'PropertyDefinition'].includes(parent?.type) && parent.key === node;
      if (member || key) {
        if (parent.shorthand) throw new Error('Unsupported shorthand property: ' + name);
        edits.set(node.start, {end: node.end, value: node.type === 'Literal' ? JSON.stringify(names.get(name)) : names.get(name)});
        counts[name]++;
      } else if (node.type === 'Literal') {
        throw new Error('Unreviewed reflective property string: ' + name);
      }
    }
    for (const [key, value] of Object.entries(node)) {
      if (!['start', 'end', 'type'].includes(key) && value && typeof value === 'object') visit(value, node);
    }
  }
  visit(acorn.parse(source, {ecmaVersion: 'latest', sourceType: 'script'}), null);
  for (const [start, edit] of [...edits.entries()].sort((a, b) => b[0] - a[0])) {
    source = source.slice(0, start) + edit.value + source.slice(edit.end);
  }
  return {source, counts};
}
module.exports = {renameInternalProperties};
