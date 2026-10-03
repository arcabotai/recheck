"""Public, synthetic-only projection. No private records are projected here."""


def blocked_state():
    return {
        'project': 'Recheck', 'status': 'blocked', 'runId': None,
        'startedAt': None, 'updatedAt': None,
        'environment': {'provider': 'Supabase Compute', 'verified': False},
        'memory': {'provider': 'Honcho', 'status': 'blocked', 'lesson': None, 'sourceRunId': None},
        'stages': [dict(id=stage, title=title, status='blocked', agent='', summary='',
                        patch='', checks=[], logs=[], receipt=None)
                   for stage, title in [('learn', 'Learn the fix'), ('replay', 'Recheck the memory'),
                                        ('repair', 'Adapt to the change')]],
        'events': [], 'limits': {'syntheticData': True, 'productionWrites': False},
        'error': 'orchestration_unavailable',
    }
