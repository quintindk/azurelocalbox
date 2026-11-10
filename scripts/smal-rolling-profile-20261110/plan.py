"""Pinned, new-operation continuation of the existing 25-stage profile contract."""
import os
from pathlib import Path
import hashlib

CANONICAL = Path(os.environ.get('SMAL_CANONICAL_ROOT', Path(__file__).resolve().parents[2]))
LEGACY_PLAN_PIN = 'c445509b9da307de2192ee25ea847be5d2a835415f32ac308d8ea4a55c4084d1'
OPERATION_ID = 'smal-foundation-profile-20261110-02'
ROOT = r'C:\ProgramData\AzureLocalBox\FoundationProfile-20261110-02'
DEADLINE = '2026-11-10T20:00:00+02:00'
RECONCILIATION = {
    'coordinatorReconciliationSha256': '00b33d1c8301f7ba76084d017dd283bcb271751d1c05c8fb4e638061068b8426',
    'originalOperationId': 'smal-foundation-profile-20261109-01',
    'originalPlanSha256': 'a778a5867740c0ea7de46f84f0cd4099eea27f4ba945364284ccb583a2d32b3a',
    'loaderCleanupReceiptSha256': '6aa5e017cee9fe9a74741d795dabb699ff306eccc582cbed81cb23819270065a',
    'independentStateReceiptSha256': '8d8030f5c2684e7965d57b9a4a95c33d26c8c1bc0af63682b600177239f1fcf7',
    'originalDisposition': 'loader-terminated-before-any-observed-durable-dispatch-or-worker-launch',
}
_path = CANONICAL / 'scripts/smal-rolling-profile-20261109/plan.py'
_raw = _path.read_bytes()
if hashlib.sha256(_raw).hexdigest() != LEGACY_PLAN_PIN:
    raise ValueError('Canonical input differs: original 25-stage plan')
# Keep the complete tested preflight/stage implementation. Change only the new
# operation identity and fixed bound in this private module, never the source file.
_source = _raw.decode().replace('smal-foundation-profile-20261109-01', OPERATION_ID).replace('2026-11-10T15:20:00+02:00', DEADLINE)
_source = _source[:_source.index("if __name__=='__main__':")]
exec(compile(_source, str(_path), 'exec'), globals())
_base_candidate = candidate
_base_preflight = execution_preflight


def candidate():
    value = _base_candidate()
    value['originalOperationReconciliation'] = dict(RECONCILIATION)
    return value


def execution_preflight(value, stage, proof, now=None):
    require(value.get('operationId') == OPERATION_ID, 'Exact new continuation operation required')
    require(value.get('originalOperationReconciliation') == RECONCILIATION, 'Exact original reconciliation binding required')
    require(proof.get('originalReconciliationSha256') == RECONCILIATION['coordinatorReconciliationSha256'], 'Fresh proof must bind original reconciliation')
    return _base_preflight(value, stage, proof, now)


if __name__ == '__main__':
    print(json.dumps(candidate(), indent=2))
