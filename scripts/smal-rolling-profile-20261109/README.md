# Exact rolling guest profile

Source-only canonical placement of accepted rolling-profile v2. This does not grant
native GO, settle an old operation or establish current capacity/image/MOC admission.

## Compatibility boundary

- `plan.py` is the accepted source unchanged. The existing 19 stages remain serial:
  NODE02 20 CPU/96 GiB, NODE03 20/96, NODE01 16/64, infrastructure return, completion.
  NODE01 has no memory write. The outer host remains E64.
- `build.py` retains the accepted renderer and capsule assembly. Only repository-relative
  source placement, exact input/output hash checks, startup-gate idempotence and an
  offline JSON CLI are added. It does not dispatch, write files or call a transport.
- Existing R2 common/worker/stage and maintenance sources stay unchanged. Their pinned
  protected WIP is required input, including the worker even if it is not yet tracked.
  Parent must preserve and publish those exact dependencies, not replace them with HEAD.
- `scripts/start-smal-existing-guests.ps1` receives only the accepted profile interlock.
  The renderer accepts its exact before or installed bytes and produces identical output.
- R1 immutable worker identity, R2 immediate expanded-survivor infrastructure placement,
  R3 current Paused/exact-eight-device maintenance and returned/dead unknown-RPC refusal
  render byte-for-byte identically to the accepted v2 proposal.

Accepted manifest: `c83e62314dc5fedeea63c9c96e1e2eeadb66f567b833e0a5b1d8e21fb667d917`.
The 66-line proposal patch is not a patch for canonical R2. Do not apply it there.

## Offline interface

From the canonical repository root:

```bash
python3 -B scripts/smal-rolling-profile-20261109/build.py render
python3 -B -m unittest discover -s scripts/smal-rolling-profile-20261109 -p 'test_profile.py' -v
```

`render` prints JSON containing the four reviewed rendered sources, their canonical
input pins and an unsealed plan. It installs nothing. `capsule --plan PATH --stage STAGE
--source-commit HASH --mode dispatch|observe` prints the existing capsule result as JSON.
Dispatch assembly requires the unchanged sealed operation plus fresh stage proof.
The plan's original approval and expiry remain immutable. No live plan is supplied here.

Parent owns publication and the existing source-bound private PowerShell transport.
Publish exact generated capsule bytes under `scripts/` before that transport can accept
them. Retain the original capsule/source/plan/request and independent-proof envelope.
An original observe call uses its original source checkpoint and identical worker bytes,
including after expiry. Earlier legacy/R2/v1 attempts keep their own retained observe
capsules. This builder cannot turn them into v2 operations or clear retained roots.

Every effect still needs independent original-operation settlement before continuation.
Unknown RPC outcomes block. No replay, expiry renewal, marker cleanup, force-stop
fallback, credential path, schedule change or general dispatcher is added.

Checks are offline Python and isolated PowerShell guard fixtures only. Windows
PowerShell 5.1 bindings, actual placement/maintenance and native execution remain untested.
