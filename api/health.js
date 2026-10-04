'use strict';
const { snapshot, respond, getOnly } = require('../lib/presenter');
module.exports = function health(req, res) {
  if (!getOnly(req, res)) return;
  const body = {
    service: 'recheck-read-only-presenter', ready: false,
    readiness: { memory: false, executor: false, repository: false },
    integrations: { memory: 'unavailable', executor: 'unavailable', repository: 'unavailable' },
    capabilities: { readOnlyState: true, hostedAgentPost: false },
    recordedEvidenceVerified: false,
    verificationScope: 'snapshot-contract-and-receipt-consistency',
    note: 'Recorded evidence only. No live provider health probe or hosted v1 POST handler.'
  };
  try {
    const state = snapshot();
    body.recordedEvidenceVerified = true;
    body.recordedEvidence = {
      source: 'recorded', live: false, runId: state.runId, capturedAt: state.updatedAt,
      executionProvider: state.environment.provider, environmentVerified: state.environment.verified,
      memoryProvider: state.memory.provider, memoryRetrieved: state.memory.status === 'retrieved',
      executionReceipts: state.stages.length, artifactHashesRecorded: true
    };
    respond(req, res, body);
  } catch (_) {
    body.capabilities.readOnlyState = false;
    respond(req, res, { ...body, error: 'cannot_verify' }, 503);
  }
};
