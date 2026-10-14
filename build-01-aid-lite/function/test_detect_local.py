# test_detect_local.py - runs the detection on the local CSV. No Azure, no sign-in.
import time, pandas as pd
from detect import find_templates, summarize
t0 = time.time()
df = pd.read_csv("../data/IRAhandle_tweets_1.csv", usecols=["author","content","account_category","language","retweet"])
eng = int(((df["language"]=="English") & (df["retweet"]==0) & df["content"].notna()).sum())
t = find_templates(df)
print(summarize(t, eng)); print(t.head(3).to_string()); print(f"{time.time()-t0:.1f}s")