import { validateCandidate } from './validate_candidate.mjs';
const MISSING=Symbol('missing');
function value(operand,input) {
  if (Object.hasOwn(operand,'literal')) return operand.literal;
  const [entity,key]=operand.field.split('.');
  const record=input[entity];
  if (!record || !Object.hasOwn(record,key)) return MISSING;
  const isFlag=key==='authenticated' || key==='active';
  if (isFlag ? typeof record[key]!=='boolean' : typeof record[key]!=='string' || record[key].length===0) return MISSING;
  return record[key];
}
function interpret(node,input) {
  switch(node.op) {
    case 'all': return node.args.every(arg=>interpret(arg,input));
    case 'any': return node.args.some(arg=>interpret(arg,input));
    case 'not': return !interpret(node.arg,input);
    case 'truthy': return value(node.value,input)===true;
    case 'eq': {
      const left=value(node.left,input),right=value(node.right,input);
      return left!==MISSING && right!==MISSING && left===right;
    }
    default: throw new Error('Unvalidated policy');
  }
}
export function compilePolicy(candidate) {
  validateCandidate(candidate);
  // Clone validated JSON so the caller cannot mutate a policy after validation.
  const expression=JSON.parse(JSON.stringify(candidate.expression));
  return function canReadDocument(actor,document,membership) {
    return interpret(expression,{actor,document,membership});
  };
}
