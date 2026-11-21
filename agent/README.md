# Agent data schema v1.0.0

All links are relative to the file containing them. No external link should be inferred. All text comes from already-redacted bilingual source snapshots, with a second privacy scrub. Generated content is AI-authored and not peer reviewed.

`index.json` has `schema_version`, `groups`, `projects`. Project entries carry `id`, `slug`, `number`, `title.{zh,en}`, `group`, `parent` (ID/null), `depth` (root 0), `status.{zh,en}`, `status_class` (`run|todo|pause|pend|done`), `done`, `start`, `end` (only if done), `updated`, `conclusion.{zh,en}`, and `files.{project,claims,pdf}`. `files` links are relative to `agent/index.json`.

`projects/<slug>.json` has the same metadata plus `schema_version`, `task.{zh,en,goal_zh,goal_en}`, `report.{zh,en}` (Markdown text), `decisions`, `reviews` (including complete ruling text), `results`, `figures`, `code`, `timeline`, `files`. Documents have `id`, `ts`, `title`, `label`, `text`; figures have `id`, `ts`, `title`, `url`; code has `name`, `group`, `url`; timeline messages have `role`, `who`, `ts`, `text`. Figure/code/PDF links in project records are relative to the project JSON. Missing assets are omitted rather than linked.

The L22.1-only `projects/<slug>.claims.json` includes `schema_version`, `project_id`, and `claims[]`: `id`, verbatim `statement`, `scope`, nullable `quantity` (`value`, `unit`, `uncertainty`), `evidence` (document ID or report and optional timestamp/title), `status` (`supported|partial|refuted|open`), nullable `review`, and `source`. Claims are AI-extracted; their evidence excerpts were checked by Lead (10-17); `supported` means the cited project text supports the wording, not independent scientific validation. Decisions and reviews remain in source language.
