"""Azure Functions app: timer transform + HTTP read API."""

from __future__ import annotations

import json
import logging

import azure.functions as func
from pydantic import ValidationError

from cost_readapi.loader import load_curated
from cost_readapi.panels import build_panel
from cost_readapi.params import parse_query
from cost_transform.config import Settings
from cost_transform.mapping import load_mapping
from cost_transform.storage import AzureBlobStore
from cost_transform.transform import run_transform

app = func.FunctionApp()


@app.function_name(name="transform")
@app.timer_trigger(schedule="0 0 3 * * *", arg_name="timer", run_on_startup=False, use_monitor=True)
def transform(timer: func.TimerRequest) -> None:  # pragma: no cover
    """Run the daily transform of raw cost exports into curated Parquet."""
    settings = Settings()  # type: ignore[call-arg]  # fields come from the environment
    store = AzureBlobStore(settings.storage_account_url)
    result = run_transform(store, settings, load_mapping())
    logging.info(
        "transform: processed=%s rows=%s periods=%s",
        result.processed,
        result.rows,
        result.periods,
    )


@app.function_name(name="costs")
@app.route(route="costs", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def costs(req: func.HttpRequest) -> func.HttpResponse:  # pragma: no cover
    """Serve curated cost panels as JSON for the dashboard.

    Anonymous in this phase so the Workbook custom-endpoint can call it without
    embedding a key. Production would front this with APIM / Entra auth.
    """
    settings = Settings()  # type: ignore[call-arg]  # fields come from the environment
    try:
        query = parse_query(dict(req.params))
    except ValidationError as exc:
        return func.HttpResponse(exc.json(), status_code=400, mimetype="application/json")
    store = AzureBlobStore(settings.storage_account_url)
    df = load_curated(store, settings.curated_container, settings.curated_prefix)
    return func.HttpResponse(json.dumps(build_panel(df, query)), mimetype="application/json")


@app.function_name(name="weekly_report")
@app.timer_trigger(schedule="0 0 7 * * 1", arg_name="timer", run_on_startup=False, use_monitor=True)
def weekly_report(timer: func.TimerRequest) -> None:  # pragma: no cover
    """Email the weekly cost report every Monday morning."""
    from cost_report.clients import read_secret, send_email
    from cost_report.compose import build_weekly_email
    from cost_report.config import ReportSettings

    storage = Settings()  # type: ignore[call-arg]  # fields come from the environment
    report = ReportSettings()  # type: ignore[call-arg]  # fields come from the environment
    store = AzureBlobStore(storage.storage_account_url)
    df = load_curated(store, storage.curated_container, storage.curated_prefix)
    email = build_weekly_email(df, budget=report.budget)
    connection = read_secret(report.key_vault_uri, report.acs_conn_secret)
    sender = read_secret(report.key_vault_uri, report.acs_sender_secret)
    send_email(connection, sender, report.recipient, email["subject"], email["text"], email["html"])
    logging.info("weekly report sent to %s", report.recipient)
