import { parseCandidate } from './validate_candidate.mjs';
import { compilePolicy } from './policy.mjs';
import { loadSuite } from './manifests.mjs';
const chunks=[];
let bytes=0;
for await (const chunk of process.stdin) {
  bytes+=chunk.length;
  if(bytes>65536) throw new Error('Worker input limit');
  chunks.push(chunk);
}
const request=JSON.parse(Buffer.concat(chunks).toString('utf8'));
const candidate=parseCandidate(request.artifact);
const suite=await loadSuite(request.version);
const canReadDocument=compilePolicy(candidate);
const checks=suite.checks.map(({name,input:{actor,document,membership}})=>({name,actual:canReadDocument(actor,document,membership)}));
// No expectations or verdict supplied by the candidate or worker output.
process.stdout.write(JSON.stringify({checks}));
