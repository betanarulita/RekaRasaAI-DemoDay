# RekaRasaAI Writer Stage Evaluation

Date: 18 November 2026
Status: **Not ready for approval.** The code-level Writer changes are in place and focused regressions pass, but live quality evidence still contains unsupported product claims. The most recent prompt revision could not be tested live because Groq returned HTTP 429 rate limits. No Reviewer development or Reviewer logic changes were made.

## Scope and preserved contracts

This evaluation covers Writer instructions, Planner-to-Writer context, source selection, platform guidance, and the existing Groq request path. The configured provider remains Groq and the model remains `openai/gpt-oss-20b`. The Writer JSON schema and the Planner and Reviewer contracts were not changed. The Reviewer and revision-loop implementation were left untouched.

The Writer still receives the Planner's objective, audience, constraints, current task direction, relevant project sources, sibling deliverable directions, and completed sibling drafts. Its output continues to use the existing `drafts` contract with `task_id`, `content`, and `source_ids`.

## Changes made

- `app.py`: tightened the Writer and remediation instructions around Planner adherence, factual support, product attributes, source references, first-person experience, repeated angles, campaign variation, and optional copy elements. Writer calls use an explicit temperature of `0.85`; other roles retain their existing request settings. Shared payload construction and bounded source selection remain in place.
- `visual_content.py`: retains channel-specific direction for Instagram, TikTok, Facebook, Threads, X, and Marketplace.
- `test_app.py`: added or extended checks for Writer prompt requirements, selected sources, campaign context, and Writer-only temperature without changing the output schema.

The latest prompt revision is more explicit than the earlier version. In particular, it says that preparation instructions support only the stated preparation method, that audience/voice/angle/imagined scenes do not prove product attributes, and that product facts outrank creative embellishment. These instructions are not a deterministic claim validator.

## Automated validation

- Focused Writer prompt and context tests: **3 passed**.
- Selected Writer and workflow regressions: **10 passed**. This set included Writer temperature/schema behavior, the orchestrated Planner-to-Writer workflow, the existing revision/re-review path, sparse-brief handling, catalog facts reaching the plan, and multi-deliverable planning.
- Python syntax parsing: **passed** for `app.py`, `test_app.py`, and `visual_content.py`.
- `git diff --check`: **passed**.
- Full `test_app.py` run: **129 tests, 6 failures, 8 errors**. The failures/errors are in password-reset token logging, Pollinations expectations, image-provider configuration, and ComfyUI/image workflows. Examples include tests expecting `call_pollinations_provider`, test mocks that do not match the current ComfyUI `/system_stats` request, and image tests expecting a Pollinations default while the current app requires an explicit ComfyUI or Cloudflare choice. The password-reset tests expected warning-log fields that were absent. These failures were not changed as part of Writer work, but they have not been independently triaged in this stage and should not be described as proven pre-existing.

## Live Groq evidence

Controlled calls used the same Jahe Rasa awareness brief and product/brand sources, with the configured model. The product source stated only that Jahe Rasa is a ginger-and-honey drink, each pack contains 10 sachets, and one sachet is mixed with hot water. The brand source requested a warm, calm, simple voice and discouraged hard selling and health claims.

### Before the Writer changes

Three repeated outputs returned the same broad morning or pause concept. One opened with "Mulailah hari dengan singkat" and described a "segelas hangat" that was "mudah disiapkan" and ready to accompany activities. Other repetitions added "aroma segar," "aroma jahe serta madu," calm, or an implied emotional effect. The stated sources did not support those product or effect claims.

### After initial Writer changes, before the latest compact prompt

The same brief was run three times again. Phrasing changed, but the outputs still repeated the pre-activity pause idea and added unsupported sensory or effect language. Examples included "nikmati aroma hangat," "aroma madu lembut," and "menenangkan diri." One output also said 10 sachets were enough for "10 hari kecil," an invented duration, and narrated first-person product use.

A separate lower-temperature exploratory call at `0.35` did not establish a fix. Its outputs still included unsupported flavor and aroma statements, and the third request was rate-limited. The application configuration was not changed from `0.85` on the basis of that incomplete comparison.

### Ten requested brief categories

The scenario run produced 13 individual drafts across the ten categories below, since audience adaptation, multi-platform work, and multiple deliverables each included more than one output. These samples were generated with the expanded grounding prompt that preceded the current compact prompt. They are useful evidence of failure modes, not proof of the current prompt's performance.

| Category | Observed result |
|---|---|
| Simple brief | Relevant product introduction, but added unsupported convenience and warmth language. |
| Complete product information | Marketplace listing mostly restated the supplied product, pack-count, and preparation facts. This was one of the strongest samples. |
| Limited product information | Stayed close to the one supplied fact, but collapsed to a bare product sentence with little creative value. |
| Specific brand voice | Tone was recognizable, but "penuh kehangatan" transferred a voice cue into an unsupported product impression. |
| Different target audiences | The commuter draft invented fresh aroma and a travel-day duration. The home-preparation draft inferred "siap pakai kapan saja." Audience adaptation was not reliably grounded. |
| Instagram and TikTok | The Instagram caption added taste, warmth, and a product trial. The TikTok script invented 200 ml, dissolution, a person smiling, and product-use claims. Script format appeared, but factual and execution quality were weak. |
| Multiple deliverables | Caption and carousel were distinct in shape, but both added unsupported taste, freshness, or convenience language. Variation did not protect factual accuracy. |
| Awareness objective | No purchase CTA was added, but the caption included unsupported convenience and taste claims. |
| Engagement objective | It invited a response, but proposed tea or coffee uses that were not present in the sources. |
| Conversion objective | The requested add-to-cart action fit the marketplace goal. The listing still inferred product taste and readiness. |

### Evidence-based quality score for the observed samples

Scale: 0 means a material failure in the observed samples, 1 means partial or inconsistent performance, and 2 means consistently meets the criterion. These are qualitative evaluator scores for the small live sample, not model metrics. **They apply to the observed pre-final-prompt samples only.**

| Criterion | Score | Evidence |
|---|---:|---|
| Relevance to brief and objective | 1/2 | Most drafts named the product and broad objective, but some replaced the task angle with generic morning or warmth copy. |
| Creative angle | 0/2 | Repeated pause, morning, warmth, and activity language dominated; the differences were often substitutions rather than new perspectives. |
| Hooks | 1/2 | Some openings were direct and usable, but several relied on familiar time cues or generic promotional openings. No mandatory hook is desirable, but the opening still needs a distinct point of view. |
| Naturalness | 1/2 | Several captions read smoothly; others included awkward or implausible phrasing, invented first-person use, or malformed TikTok lines. |
| Storytelling | 0/2 | Some scenes or reactions were invented as if they happened, rather than clearly framed as production direction. |
| Copywriting | 1/2 | There were usable factual listing structures and one goal-aligned CTA, but unsupported embellishment and generic phrasing weakened the rest. |
| Platform fit | 1/2 | Marketplace and carousel shapes were recognizable. The TikTok script included unsupported specifics and awkward execution; platform-specific quality was uneven. |
| Brand consistency | 1/2 | Some outputs echoed the requested restrained voice, but warmth and sensory wording became implied product claims. |
| Factual grounding | 0/2 | Unsupported aroma, taste, convenience, effects, product use, quantities, or durations appeared across the live samples. |
| Variation across repeated or sibling outputs | 0/2 | Three same-brief repetitions shared the morning/pause idea. Multi-deliverable samples differed in format more than in underlying idea. |

## Current prompt validation blocker

After the last live sample exposed continued unsupported claims, the Writer prompt was tightened and its focused test assertions were updated. The prompt tests pass. I then attempted one live request with the current prompt and a single provider attempt. Groq returned `provider_rate_limited`; no draft was produced. A separate end-to-end `/api/plan` to `/api/confirm-plan` to `/api/generate` live check also ended with the application's explicit `provider_rate_limited` response after the provider retries. It did not save a draft. Therefore, there is no live output from the current prompt revision to score.

## Decision and remaining work

**Do not approve the Writer stage yet.** The strongest unresolved issue is factual grounding: prompt wording alone has not reliably stopped sensory, convenience, duration, or implied-effect claims in live output. The current concise prompt may help, but this has not been demonstrated. Groq availability also prevented completion of the current-prompt repeat test and final live endpoint check.

When Groq is available again, resume with the unchanged Jahe Rasa brief for three controlled repeats using the current prompt and configured temperature. Then rerun any incomplete live scenarios, inspect the outputs against the stated facts, and retest the real endpoint. If unsupported claims persist, treat this as a Writer quality failure rather than reporting the prompt as fixed. Re-run the targeted suite and full suite after the final adjustment, and report the existing non-Writer suite failures separately.

No Reviewer development should begin until the user approves the Writer stage.
