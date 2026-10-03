from projectkoios.ingestion.ocr.reconciliation.batch.plan import (
    SelectiveOCRReconciliationPlan,
)

from tests.ocr_reconciliation_batch_support import reconciliation_fixture


def test__selective_ocr_reconciliation_plan__round_trips_exact_scope() -> None:
    item, _, _ = reconciliation_fixture()
    plan = SelectiveOCRReconciliationPlan(schema_version=1, items=(item,))

    assert SelectiveOCRReconciliationPlan.from_json(plan.to_json()) == plan
