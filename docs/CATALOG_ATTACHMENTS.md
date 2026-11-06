# Brief attachments

Attachments live inside the brief editor and belong to its selected project folder.
No extra model provider or dependency is introduced.

## Spreadsheet

Download the real XLSX template from the authenticated `/api/catalog-template` endpoint.
Use one worksheet. Replace placeholders and remove unused rows. One row describes
one product within one campaign group. Headers must remain unchanged:

| Column | Meaning |
| --- | --- |
| campaign_type | Required free text: any creator-defined content / campaign group |
| product_name | Required product or brand name |
| facts | Required user-supplied facts; no invented claims |
| price | Optional exact price, including currency |
| promo | Optional offer and conditions, supplied by the user |
| channels | Optional requested destinations |
| image_filename | Optional filename of an uploaded original image |

XLSX and UTF-8 CSV are accepted. Legacy XLS, macros, formulas and multiple sheets
are rejected. Maximum 200 rows and 5 MB per file. Each campaign group must fit the
existing 12,000-character source context; larger groups are rejected before saving.

The preview displays all parsed rows before explicit import. Confirmed groups are
stored in existing project sources, with source IDs and an audit event. Exact
re-imports reuse sources. Changed imports do not overwrite older sources; conflicting
prices/facts require user resolution rather than an assumed latest truth.

For catalogs imported during the current brief, Planner receives a schema requiring
campaign_type per task. Group names are free text, not a fixed taxonomy. Every requested group must be represented before plan
persistence. Catalog plans require human plan confirmation; no draft auto-generation.
Existing limit: six tasks per plan. Channel x campaign x product combinations can
need multiple batches; no full-catalog coverage claim is made beyond checked groups.

## Original photos

PNG/JPEG uploads are stored in an additive project_assets table, isolated by project
ownership, with SHA256 and audit events. Maximum 5 MB/file, 20 files per selection,
50 MB of original photos per project. Spreadsheet cells refer to filenames only.
No OCR, vision extraction, background removal or automatic filename-to-task matching
is implemented. Photo metadata is not evidence for product claims.

In the visual workbench, choose an original project photo and a canvas, then compose
it with the current draft. This uses the existing copy review and separate visual
human approval/export gates. Inspect cropping and text placement manually.

Uploaded photos are included in account data export and deleted with the project
through SQLite foreign-key cascade. Copies used in task compositions follow the
existing generated-image file lifecycle.

## Deployment and validation limits

Restart the backend to apply migration 011 and load the new routes. Existing tables
and user data are preserved. No environment or credentials are changed.

During implementation Python/JavaScript syntax and diff whitespace were checked.
Automated integration tests, live inference and real account uploads still require
validation. Browser preview alone does not prove backend upload or approval success.

## Draft preview and deadlines

Production deadline is optional in the brief and editable in the proposed plan.
It is copied to task.deadline on confirmation; no database schema change is needed.
Project detail lists saved proposed plans so a refresh does not require replanning.
Distinct titles may share a format/channel, such as four Instagram campaign posters.

Confirmation saves all tasks, generates only the first draft/review, then opens its
workbench. Other outputs remain planned until selected through Next output or the
project. Review and human approval rules are unchanged. This is a text draft preview;
image selection/generation remains a separate workbench operation.

Manage deadlines on project detail edits task deadlines atomically. Changes preserve
approval and planned publication time, log old/new deadline, and appear in Planner.

Focused fake-provider checks verified four same-channel posters can be confirmed,
deadline inheritance, recovery of proposed plans, audited deadline extension, and
rollback of an invalid deadline batch. Full live generation has not been verified.

## Open and remove project items

Source names open an owner-authenticated content preview. Catalog rows are shown as
product fields rather than raw JSON. Sources, proposed plans and tasks have separate
Delete actions with confirmation. Deletion archives active work; revisions, source
content, approvals and audit records remain stored. Archived sources are excluded
from new source context but remain resolvable by historical source ID. Archived tasks
are hidden from active project/Planner lists and task-id mutations are rejected.

Validation: 151 isolated backend tests passed, including five new project-action
tests. Initial targeted failures were fixture names lacking the required .md suffix;
production source validation was preserved. Calendar/list/diff JavaScript probes pass.
Browser source-preview click was checked with fixture data and no server writes.
