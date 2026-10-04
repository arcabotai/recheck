import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
export const SUITE_HASHES=Object.freeze({
  v1:'366a30ed14373881cf54c5dbb6ec2a1b215cb280ff54984ae5e893510dc1a487',
  v2:'961a0f7218fbb263e91496b8e410e1e9fb5f17ce407b04ad4aa1ebdf4379163e',
});
export const sha256=value=>createHash('sha256').update(value).digest('hex');
function freeze(value) {
  if(value && typeof value==='object') { Object.values(value).forEach(freeze); Object.freeze(value); }
  return value;
}
export function validateManifestBytes(version,requirementBytes,checkBytes) {
  if (!Object.hasOwn(SUITE_HASHES,version)) throw new Error('Unknown suite');
  const hash=sha256(Buffer.concat([requirementBytes,Buffer.from('\n'),checkBytes]));
  if(hash!==SUITE_HASHES[version]) throw new Error('Frozen suite changed');
  const requirements=JSON.parse(requirementBytes),manifest=JSON.parse(checkBytes);
  if(requirements.requirementVersion!==version || manifest.requirementVersion!==version || !Array.isArray(manifest.checks) || !manifest.checks.length) throw new Error('Invalid suite');
  const names=new Set();
  for (const check of manifest.checks) {
    if(typeof check.name!=='string' || names.has(check.name) || typeof check.expected!=='boolean' || !check.input) throw new Error('Invalid check');
    names.add(check.name);
  }
  return freeze({version,hash,requirements,checks:manifest.checks});
}
export async function loadSuite(version) {
  if(!Object.hasOwn(SUITE_HASHES,version)) throw new Error('Unknown suite');
  const root=new URL('../fixtures/access-control/',import.meta.url);
  const [requirements,checks]=await Promise.all([readFile(new URL(`requirements-${version}.json`,root)),readFile(new URL(`checks-${version}.json`,root))]);
  return validateManifestBytes(version,requirements,checks);
}
