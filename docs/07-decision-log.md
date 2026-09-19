# Decision log

A record of the significant decisions, the options weighed, and the trade-offs accepted. This is deliberately preserved because the *reasoning* is as much a portfolio asset as the build — it shows judgement, not just tool knowledge.

## ADR-01 — Budgets, not Azure Monitor metric alerts, for spend thresholds
**Decision:** Use Cost Management Budgets + Action Groups.
**Context:** The original brief specified "Azure Monitor alert rules tied to spending thresholds."
**Why:** Cost is not an Azure Monitor metric, so a metric alert cannot watch spend. Budgets evaluate cost continuously and integrate natively with Action Groups, delivering the exact behaviour the brief intended.
**Trade-off:** None of substance — this is a correctness fix. The end behaviour (alert fires when spend crosses a threshold) is identical.

## ADR-02 — Cost Management Exports, not API polling
**Decision:** Ingest via scheduled Exports to storage.
**Why:** Exports are durable, replayable, and require no code to run on a schedule. Polling the Query API is fragile, rate-limited, and stateful. Amortised cost is exported so reservations/savings plans are spread correctly.
**Trade-off:** Slightly less "real-time" than on-demand queries, which is irrelevant for a daily/weekly cadence.

## ADR-03 — Serverless Functions, not Data Factory / Synapse
**Decision:** Do all transformation in Azure Functions with pandas/pyarrow.
**Why:** The data is small and the transforms are simple. ADF/Synapse add cost, services, and operational surface for no benefit at this scale. Choosing them would be over-engineering — contradicting the project's own cost-discipline message.
**Trade-off:** A single function reading everything into pandas has a ceiling at very large data volumes. Mitigation when needed: partition by date and process incrementally.

## ADR-04 — Two containers (`raw` + `curated`), not medallion (bronze/silver/gold)
**Decision:** Keep a simple raw → curated split.
**Why:** Medallion is a pattern for many sources and many consumers. With one source and tiny data it is vocabulary without value. Raw (audit trail) plus curated (source of truth) is honest and sufficient.
**Trade-off:** Less "lakehouse" résumé signal; gained simplicity and credibility.

## ADR-05 — No Event Grid
**Decision:** Trigger the transform on a timer after the daily export, not on a blob event.
**Why:** Near-real-time landing isn't needed for a daily/weekly system. A timer removes a service and is simpler to reason about.
**Trade-off:** Up to a few hours' latency between landing and transform, which does not matter here.

## ADR-06 — Do NOT write cost data to Log Analytics
**Decision:** Reject Log Analytics as a serving store for the Workbook.
**Context:** Workbooks query KQL sources natively, which tempted a Log Analytics custom table to feed the dashboard.
**Why:** Log Analytics is an append-only observability store. Cost data gets restated (late charges, credits, amortisation), and an append-only store cannot cleanly update rows — forcing dedupe-in-KQL or purge gymnastics. It is the wrong home for restate-able financial data, and it would create a second copy to keep in sync. Using a logging system as a financial datastore is off-label and not defensible to an experienced reviewer.
**Trade-off:** We forgo native KQL filtering in the Workbook and instead write aggregation logic in the `read-api` function (see ADR-07).

## ADR-07 — Workbook fed by a custom-endpoint read-API function
**Decision:** The Workbook calls an HTTP Function (custom/ARM endpoint) that reads `curated` Parquet and returns shaped JSON.
**Why:** Keeps Parquet as the single source of truth, adds no new service (reuses the Function App), and avoids ADR-06's pitfalls. Filters pass as query-string parameters; the function does grouping, deltas, and bucketing server-side.
**Trade-off:** More aggregation logic owned in function code rather than outsourced to KQL; cascading multi-select filters are wired deliberately rather than for free. Accepted for the cleaner, more honest architecture.

## ADR-08 — Azure Workbook, not Power BI
**Decision:** Dashboard in Azure Workbook.
**Why:** Native to the portal, no external BI tool or licence, lives where an Azure admin already works, and keeps the whole platform inside Azure.
**Trade-off:** Less polished executive visuals than Power BI; gained zero external dependency and zero licensing.

## ADR-09 — Terraform + Azure DevOps, not Bicep + GitHub
**Decision:** Terraform (`azurerm`) with Azure DevOps Pipelines.
**Why:** Matches the toolchain most mid-market/enterprise Azure shops run, strengthening the consulting story; Terraform offers broader familiarity and multi-cloud optionality. OIDC (Workload Identity Federation) service connection means no stored secrets.
**Trade-off:** Bicep is slightly more Azure-idiomatic, but the market-fit argument wins for a consulting portfolio.

## ADR-10 — Multi-subscription / multi-tenant by design
**Decision:** Carry a subscription dimension and scope at Management Group level from day one.
**Why:** A consultant's value is seeing across accounts and clients. Designing this in early costs nothing and turns a demo into a product.
**Trade-off:** Marginally more thought in the data model and RBAC up front.

## Future option (not now) — Azure Data Explorer
If a client's data grows to millions of rows per day, the principled upgrade is ADX — a real KQL analytics database (not a logging store) the Workbook can query natively. Deferred as a future-client problem to avoid a heavier, pricier service today.
