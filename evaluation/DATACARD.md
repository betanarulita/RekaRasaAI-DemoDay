# Claim evaluation v1

## Purpose and provenance

240 **synthetic test cases**, authored from 12 explicit claim families, two evidence
conditions, and 10 placements. These are examples for regression and subsequent
Reviewer evaluation, not 240 independent research samples, product facts, a training
corpus, or verified regulatory decisions. No customer data or real certificate is used.

The generator is [build_claim_evaluation.py](../scripts/build_claim_evaluation.py).
The stored [JSONL](./claims-v1.jsonl) contains the complete source, draft, exact claim
span, policy ID, proposed verdict, rationale, split, and provenance for each case.

## Method

- Contrastive evidence pairs: retain the same claim, add or remove its synthetic
  supporting source. Disease-cure statements stay prohibited under the demo policy
  even when a source repeats them; a testimonial is not an exemption.
- Controlled placement variation: test the same claim inside headline, body,
  caption, listing and voiceover placements. This tests location coverage, not
  linguistic diversity. Most cases are Bahasa Indonesia; no trilingual benchmark
  claim is made.
- Group split: all evidence pairs and placements of a claim family remain together.
  Development has eight families (160 rows), calibration two (40), held-out two (40).
  Calibration contains halal and testimonial examples; held-out contains clinical
  testing and diabetes-cure examples. Never tune prompts on held-out labels then
  describe their score as an untouched test result.
- Rule-oriented labels, not subjective quality scores. `Pass`, `Fail`, and
  `Needs Evidence` refer to project policy and supplied fixtures. A cited source
  still needs authenticity/applicability checks in real use.

## Annotation status

Labels are **author-proposed and not independently adjudicated**. Before reporting
model quality, two independent people should label each family/evidence condition,
record disagreements, and have a third reviewer adjudicate them. Report raw
agreement and Cohen's kappa on the overlapping annotations. No annotators,
agreement figures, legal validation, or annotation work are invented here.

## Running an evaluation

Collect predictions from an actual Reviewer run, preserving each case ID and the
returned verdict, rule ID, exact claim and source ID. The scoring script does not
call a paid provider and does not manufacture predictions:

```powershell
python scripts/evaluate_claim_predictions.py --predictions path/to/actual-predictions.jsonl
# Only held-out families:
python scripts/evaluate_claim_predictions.py --predictions path/to/actual-predictions.jsonl --split held_out
```

It reports coverage, confusion matrix, per-class precision/recall, balanced accuracy,
unsafe-pass rate, and correctly grounded passes. Missing predictions count against
recall. A perfect verdict with an unrelated source is not a grounded pass. Run
separately for held-out families before reporting final results, and report
family-level errors; placement replicas must not inflate statistical confidence.

## Limits

No actual Reviewer benchmark has been run on these 240 cases. Existing fake-provider
integration tests prove control flow, not Groq factual accuracy. This corpus does not
cover adversarial multilingual paraphrases, certificate expiry, product categories,
allergies, personal data leakage, demographic fairness or every Indonesian law.
See the [official reference map](../governance/references.json). Do not import this
corpus into a real project's sources or use synthetic certificates as evidence.

## Method references

- [CheckList, Ribeiro et al. (ACL 2020)](https://aclanthology.org/2020.acl-main.442/):
  behavior-oriented tests motivate the claim/evidence and placement matrix here.
- [Datasheets for Datasets, Gebru et al.](https://arxiv.org/abs/1803.09010):
  document provenance, intended use, composition, annotation status and limitations.

This small corpus borrows those practices; it is not a reproduction of their
benchmarks or evidence that an annotation study has been conducted.
