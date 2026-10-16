# test_f0.py - one-record test: does the free-tier Language resource permit summarization? Token by env, no key.
import os
from azure.core.credentials import AccessToken
from azure.ai.textanalytics import TextAnalyticsClient
class Cred:
    def get_token(self, *a, **k): return AccessToken(os.environ["LANG_ACCESS_TOKEN"], 2**31 - 1)
c = TextAnalyticsClient(os.environ["LANGUAGE_ENDPOINT"], Cred())
doc = ("The unemployment rate for veterans who served on active duty in the U.S. Armed Forces at any time since September 2001, "
       "a group referred to as Gulf War-era II veterans, was 3.3 percent in 2024, the U.S. Bureau of Labor Statistics reported today. "
       "The jobless rate for all veterans was 2.9 percent, and the rate for nonveterans was 3.8 percent. "
       "In 2024, 25 percent of Gulf War-era II veterans reported a service-connected disability.")
print("chars:", len(doc), "-> records:", -(-len(doc) // 1000))
for name, poller in (("extractive", c.begin_extract_summary([doc], max_sentence_count=2)),
                     ("abstractive", c.begin_abstract_summary([doc], sentence_count=1))):
    try:
        for r in poller.result():
            if r.is_error: print(name, "ERROR", r.error.code, r.error.message)
            else:
                print(name, "OK:", " ".join(s.text for s in (r.sentences if name == "extractive" else r.summaries))[:200])
    except Exception as e:
        print(name, "EXC", type(e).__name__, str(e)[:200])