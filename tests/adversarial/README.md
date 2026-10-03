# Adversarial checks (RC-07)

Credential-free contract checks for false verification. They do not call a network, read credentials, or record a live executor result. `grok/qa` does not contain `evaluator/`, so these files carry their own fixtures and assertions.

Run from the repository root:

```sh
node --test tests/adversarial/false-verification.test.mjs
```

No package install is required. Node 22 is enough.

## Executable now

These rows are hypotheses locked against the local oracle in this directory. A green run means the oracle matches the fixtures. It does not mean Cad's backend, the evaluator on another branch, or a deployed presenter produced the result.

| Case | Local assertion |
| --- | --- |
| Authenticated active same-tenant actor | `canReadDocument` v1 and v2 return true |
| Revoked same-tenant member | v1 returns true; v2 returns false |
| Membership for another actor or tenant | v2 returns false |
| Stale v1 candidate against v2 checks | Verdict is `fails`, including expected false / actual true on the revoked check |
| v2 candidate against v2 checks | Verdict is `works` only with a finished executor and every required check passed |
| Model text `fixed` | Ignored. Without a finished executor the verdict is `cannot_verify` |
| Invalid candidate, thrown candidate, timeout, missing executor | `cannot_verify` |
| Missing, partial, or contradictory check results | Not a pass. Verdict is `cannot_verify` |
| Numeric zero | `actual: 0` can pass, and `durationMs: 0` stays 0 |
| Store a verified experience | Accepted only when `verificationId` names a same-workspace verification that classifies as `works` |
| Log and patch strings | Projected as text. The characters are unchanged and no HTML field is added |
| Receipt from another run id | Removed from the current-run projection. A failed current stage stays failed |

## Still needs a live endpoint

Actual behavior below was not observed. Do not treat this file as a passed review of a deployment.

| Case | What has to be called | Expected, still unchecked |
| --- | --- | --- |
| Foreign workspace reads a verification | `GET /api/v1/verifications/{id}` and the workspace tables | 404 or 403, and zero rows for the other workspace |
| Bad bearer token | `POST /api/v1/verifications` with an unsigned, expired, or wrong-issuer token | 401 before a job row is written |
| Current run reuses an old receipt | `GET /api/state` after a new `runId` | The response itself omits the previous receipt. The local projection above is only the rule |
| Secret in the public app | Shipped frontend, `GET /api/state`, and `GET /api/health` | No service-role key, provider key, or connection string |
| Sign-out and redirect | Auth session reuse, then a `redirect_to` outside the callback allowlist | Old token rejected. Redirect stays on the configured origin |
| Duplicate operator start | Two parallel `POST /api/demo` calls | One job. The second conflicts |
| Public state leaks another workspace | Unauthenticated `GET /api/state` and `GET /api/health` | Sanitized synthetic projection only |
| Real timeout or missing Compute | The integrated executor | `cannot_verify` from the observed process, not from this oracle |
| Browser handling of hostile logs | The deployed or locally served presenter | The page shows the literal string and does not run it |

## Out of scope for this lane

No files outside `tests/adversarial/` are part of this change. The known presenter failure `app.mountPresenter is not a function` belongs to the frontend lane. These checks do not start a run, spend model credits, or deploy.
