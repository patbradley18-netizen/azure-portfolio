# function_app.py - AID Lite stage 2: scheduled detection on Azure Functions.
#
# How the pieces connect (no secrets anywhere):
#   timer   -> runs weekly (CRON below). Can also be triggered by hand from the portal/CLI.
#   blob in -> the raw CSV, read through an identity-based connection named RawStorage
#              (app settings: RawStorage__serviceUri; the Function's managed identity has Blob Data Reader)
#   SQL out -> rows upserted into dbo.template_runs through an identity-based connection
#              (app setting SqlConnectionString = "Server=...;Database=...;Authentication=Active Directory Managed Identity")
#   AI Language -> key phrases for the top templates, called with the managed identity (Cognitive Services User)
import io, json, logging, os, uuid
from datetime import datetime, timezone
import azure.functions as func
import pandas as pd
from detect import find_templates, summarize

app = func.FunctionApp()

TOP_N_FOR_KEY_PHRASES = 50

@app.function_name("weekly_detect")
@app.timer_trigger(schedule="0 0 6 * * 1", arg_name="timer", run_on_startup=False)   # Mondays 06:00 UTC
@app.blob_input(arg_name="raw", path="raw/IRAhandle_tweets_1.csv", connection="RawStorage")
@app.sql_output(arg_name="rows", command_text="dbo.template_runs", connection_string_setting="SqlConnectionString")
def weekly_detect(timer: func.TimerRequest, raw: func.InputStream, rows: func.Out[str]) -> None:
    run_id = str(uuid.uuid4())
    run_time = datetime.now(timezone.utc).isoformat()
    logging.info("run %s started", run_id)

    df = pd.read_csv(io.BytesIO(raw.read()), usecols=["author", "content", "account_category", "language", "retweet"])
    eng = int(((df["language"] == "English") & (df["retweet"] == 0) & df["content"].notna()).sum())
    templates = find_templates(df)
    stats = summarize(templates, eng)
    logging.info("run %s stats %s", run_id, json.dumps(stats))

    phrases = key_phrases(templates["body"].head(TOP_N_FOR_KEY_PHRASES).tolist())

    out = []
    for i, r in templates.iterrows():
        out.append({
            "run_id": run_id, "run_time": run_time, "rank": int(i) + 1,
            "body": r["body"], "n_tweets": int(r["n_tweets"]), "n_authors": int(r["n_authors"]),
            "top_category": r["top_category"],
            "key_phrases": phrases.get(r["body"]) if i < TOP_N_FOR_KEY_PHRASES else None,
            "english_originals": eng,
        })
    rows.set(json.dumps(out))
    logging.info("run %s wrote %d rows", run_id, len(out))


def key_phrases(bodies: list[str]) -> dict[str, str]:
    """Top-N bodies -> 'phrase; phrase; ...' via Azure AI Language. Fails soft: returns {} on any error."""
    endpoint = os.environ.get("LANGUAGE_ENDPOINT")
    if not endpoint or not bodies:
        logging.warning("LANGUAGE_ENDPOINT not set or no bodies; skipping key phrases")
        return {}
    try:
        from azure.ai.textanalytics import TextAnalyticsClient
        from azure.identity import DefaultAzureCredential
        client = TextAnalyticsClient(endpoint=endpoint, credential=DefaultAzureCredential())
        result = {}
        for start in range(0, len(bodies), 10):                 # API takes up to 10 docs per call
            batch = bodies[start:start + 10]
            for doc, res in zip(batch, client.extract_key_phrases(batch, language="en")):
                if not res.is_error:
                    result[doc] = "; ".join(res.key_phrases)[:500]
        logging.info("key phrases for %d bodies", len(result))
        return result
    except Exception as e:                                      # noqa: BLE001 - teaching build; log and continue
        logging.error("key phrase step failed: %s", e)
        return {}