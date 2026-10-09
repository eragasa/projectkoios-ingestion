# Reading-layout implementation

The package separates replaceable candidate production from deterministic
verification. Candidate producers may preserve source-order bias. The core
verifier therefore admits only an order mechanically supported by complete
native-block assignment, exact render-space geometry, configured direction,
and conservative closed rules.

The `evaluation` boundary consumes exactly one candidate order, one opaque
Search evidence identity, and at least two declared Agent-normalized replica
slots. It validates each normalized judgment, retains missing and malformed
slots, compares asserted precedence only on common coverage, and reports
replica agreement, aggregate coverage, per-replica candidate alignment,
pairwise disagreement, and deterministic escalation reasons as independent
dimensions.

The evaluator requires exact complete agreement with the candidate before
escalation can be false. Unanimous agreement on an alternative remains
`EXACT_AGREEMENT` among replicas but also reports `CANDIDATE_DISPUTED` and does
not emit that alternative as a correction.

The package does not authorize publication, infer Workflow state, retrieve
Search evidence, import Search or Agent contracts, invoke a model, construct a
prompt, report accuracy, compare multiple candidates, majority-vote, or repair
unresolved evidence.
