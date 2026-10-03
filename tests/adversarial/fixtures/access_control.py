"""Frozen synthetic multi-tenant access-control fixture contracts.

These are pure evaluation helpers for adversarial QA. They are not live RLS
execution and must not be treated as production authorization proof.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f'{label} must be a mapping')
    return value


def can_read_document_v1(
    actor: Mapping[str, Any],
    document: Mapping[str, Any],
    membership: Optional[Mapping[str, Any]] = None,
) -> bool:
    """v1: authenticated active actor may read a same-tenant document.

    Membership is ignored under v1. Cross-tenant and anonymous access fail.
    """
    actor = _require_mapping(actor, 'actor')
    document = _require_mapping(document, 'document')
    if membership is not None:
        _require_mapping(membership, 'membership')
    if not actor.get('authenticated') is True:
        return False
    if not actor.get('active') is True:
        return False
    if actor.get('tenantId') is None or document.get('tenantId') is None:
        return False
    return actor.get('tenantId') == document.get('tenantId')


def can_read_document_v2(
    actor: Mapping[str, Any],
    document: Mapping[str, Any],
    membership: Optional[Mapping[str, Any]] = None,
) -> bool:
    """v2: tenant match is insufficient; actor must hold active matching membership.

    Membership must belong to the actor and the document tenant. Passing any
    active membership for a different actor or tenant must not grant access.
    A revoked (inactive) same-tenant membership must deny.
    """
    actor = _require_mapping(actor, 'actor')
    document = _require_mapping(document, 'document')
    if not can_read_document_v1(actor, document, membership):
        return False
    if membership is None:
        return False
    membership = _require_mapping(membership, 'membership')
    if membership.get('actorId') != actor.get('id'):
        return False
    if membership.get('tenantId') != document.get('tenantId'):
        return False
    if membership.get('tenantId') != actor.get('tenantId'):
        return False
    return membership.get('active') is True


def evaluate_check(name: str, expected: Any, actual: Any) -> dict:
    """Independent check row. Missing results are not passes."""
    if actual is _MISSING:
        return {
            'name': name,
            'expected': expected,
            'actual': None,
            'passed': False,
            'evaluated': False,
            'diagnostic': 'missing_result',
        }
    passed = expected == actual
    return {
        'name': name,
        'expected': expected,
        'actual': actual,
        'passed': passed,
        'evaluated': True,
        'diagnostic': None if passed else 'mismatch',
    }


class _Missing:
    def __repr__(self) -> str:
        return 'MISSING'


_MISSING = _Missing()
MISSING = _MISSING


def verification_verdict(*, status: str, checks: list[dict], infrastructure_error: Optional[str] = None) -> str:
    """Map independent execution outcome to works | fails | cannot_verify.

    Infrastructure failure must not become a code-failure (fails) verdict.
    Model self-assessment is never an input here.
    """
    if infrastructure_error:
        return 'cannot_verify'
    if status in ('queued', 'running'):
        return 'cannot_verify'  # incomplete; not a terminal verdict for product display
    if status == 'blocked':
        return 'cannot_verify'
    if status != 'finished':
        return 'cannot_verify'
    if not checks:
        return 'cannot_verify'
    if any(not check.get('evaluated', True) for check in checks):
        return 'cannot_verify'
    if any(check.get('passed') is not True for check in checks):
        return 'fails'
    return 'works'


def may_record_experience(*, verification: Mapping[str, Any], checks: list[dict]) -> bool:
    """Only a finished works verification with complete independent checks may admit an experience.

    There is no client-writable verified flag. Model claims are ignored.
    """
    verification = _require_mapping(verification, 'verification')
    if verification.get('status') != 'finished':
        return False
    if verification.get('verdict') != 'works':
        return False
    required = verification.get('required_check_count')
    if type(required) is not int or required < 1:
        return False
    if len(checks) != required:
        return False
    if any(check.get('passed') is not True for check in checks):
        return False
    if verification.get('receipt') is None:
        return False
    receipt = verification['receipt']
    for field in ('id', 'at', 'environmentFingerprint', 'artifactHash', 'durationMs', 'executionProvider', 'model'):
        if receipt.get(field) is None:
            return False
    return True


def classify_evidence_mode(*, live_connection: bool, labelled_recorded: bool, animating_as_live: bool) -> str:
    """Stale/recorded evidence must not be presented as live execution."""
    if live_connection and not labelled_recorded:
        return 'live'
    if labelled_recorded and not animating_as_live:
        return 'recorded'
    if animating_as_live and not live_connection:
        return 'mislabelled_stale_as_live'
    if labelled_recorded and animating_as_live:
        return 'mislabelled_stale_as_live'
    return 'stale_or_unknown'


# Canonical actors for the synthetic scenario
TENANT_A = 'tenant-a'
TENANT_B = 'tenant-b'

ACTOR_ACTIVE = {
    'id': 'actor-active',
    'tenantId': TENANT_A,
    'authenticated': True,
    'active': True,
}
ACTOR_REVOKED = {
    'id': 'actor-revoked',
    'tenantId': TENANT_A,
    'authenticated': True,
    'active': True,  # account still active; membership revoked under v2
}
ACTOR_INACTIVE = {
    'id': 'actor-inactive',
    'tenantId': TENANT_A,
    'authenticated': True,
    'active': False,
}
ACTOR_ANON = {
    'id': 'actor-anon',
    'tenantId': TENANT_A,
    'authenticated': False,
    'active': True,
}
ACTOR_FOREIGN = {
    'id': 'actor-foreign',
    'tenantId': TENANT_B,
    'authenticated': True,
    'active': True,
}

DOC_A = {'id': 'doc-a', 'tenantId': TENANT_A}
DOC_B = {'id': 'doc-b', 'tenantId': TENANT_B}

MEMBERSHIP_ACTIVE = {
    'actorId': 'actor-active',
    'tenantId': TENANT_A,
    'active': True,
}
MEMBERSHIP_REVOKED = {
    'actorId': 'actor-revoked',
    'tenantId': TENANT_A,
    'active': False,
}
MEMBERSHIP_WRONG_ACTOR = {
    'actorId': 'actor-active',  # belongs to someone else relative to actor-revoked
    'tenantId': TENANT_A,
    'active': True,
}
MEMBERSHIP_WRONG_TENANT = {
    'actorId': 'actor-active',
    'tenantId': TENANT_B,
    'active': True,
}
