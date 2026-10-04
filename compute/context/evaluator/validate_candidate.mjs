export const MAX_CANDIDATE_BYTES = 16384;
const fields = new Set(['actor.id','actor.tenantId','actor.authenticated','actor.active','document.id','document.tenantId','membership.actorId','membership.tenantId','membership.active']);
function exact(value, keys) {
  if (!value || typeof value !== 'object' || Array.isArray(value) || Object.getPrototypeOf(value)!==Object.prototype || Object.keys(value).sort().join('|')!==[...keys].sort().join('|')) throw new Error('Invalid candidate shape');
}
export function validateCandidate(candidate) {
  exact(candidate, ['format','expression']);
  if (candidate.format!=='recheck-policy-v1') throw new Error('Unsupported candidate format');
  let count=0;
  function operand(value) {
    if (++count>128) throw new Error('Candidate node limit');
    if (value && Object.hasOwn(value,'field')) {
      exact(value,['field']);
      if (!fields.has(value.field)) throw new Error('Disallowed field');
    } else {
      exact(value,['literal']);
      if (!(value.literal===null || typeof value.literal==='boolean' || (typeof value.literal==='string' && value.literal.length<=256))) throw new Error('Invalid literal');
    }
  }
  function visit(node,depth=0) {
    if (depth>16 || ++count>128) throw new Error('Candidate complexity limit');
    if (!node || typeof node!=='object') throw new Error('Invalid expression');
    switch(node.op) {
      case 'all': case 'any':
        exact(node,['op','args']);
        if (!Array.isArray(node.args) || node.args.length<1 || node.args.length>16) throw new Error('Invalid arguments');
        node.args.forEach(arg=>visit(arg,depth+1)); break;
      case 'not': exact(node,['op','arg']); visit(node.arg,depth+1); break;
      case 'eq': exact(node,['op','left','right']); operand(node.left); operand(node.right); break;
      case 'truthy': exact(node,['op','value']); operand(node.value); break;
      default: throw new Error('Unsupported operation');
    }
  }
  visit(candidate.expression);
  return candidate;
}
export function parseCandidate(text) {
  if (typeof text!=='string' || Buffer.byteLength(text)>MAX_CANDIDATE_BYTES) throw new Error('Candidate byte limit');
  if (Buffer.from(text).toString('utf8')!==text) throw new Error('Candidate must be valid Unicode');
  return validateCandidate(JSON.parse(text));
}
