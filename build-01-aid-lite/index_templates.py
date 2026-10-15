"""AID stage 4, step 2: embed the 1,642 templates locally and index them as vectors in Azure AI Search (free tier).

Auth: Entra access token for https://search.azure.com passed by environment (SEARCH_ACCESS_TOKEN); no admin key.
Env: SEARCH_ENDPOINT (https://<service>.search.windows.net), SEARCH_ACCESS_TOKEN.
Model: sentence-transformers all-MiniLM-L6-v2 (384 dims), same as stage 1, run on this machine.
"""
import os, sys, json, hashlib
from pathlib import Path
import pandas as pd
from azure.core.credentials import AccessToken
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents import SearchClient
from azure.search.documents.indexes.models import (SearchIndex, SimpleField, SearchableField, SearchField,
    SearchFieldDataType, VectorSearch, HnswAlgorithmConfiguration, VectorSearchProfile)

HERE = Path(__file__).parent; DATA = HERE / "data"
EP, TOK = os.environ.get("SEARCH_ENDPOINT"), os.environ.get("SEARCH_ACCESS_TOKEN")
if not (EP and TOK): sys.exit("needs SEARCH_ENDPOINT, SEARCH_ACCESS_TOKEN")
INDEX = "aid-templates"; DIMS = 384

class Cred:
    def get_token(self, *a, **k): return AccessToken(TOK, 2**31 - 1)

def main():
    sys.path.insert(0, str(HERE / "function"))
    from detect import find_templates
    df = pd.read_csv(DATA / "IRAhandle_tweets_1.csv", low_memory=False)
    t = find_templates(df).reset_index(drop=True)
    print("templates:", len(t))

    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-MiniLM-L6-v2")
    vecs = model.encode(t["body"].tolist(), batch_size=128, normalize_embeddings=True, show_progress_bar=False)
    print("embedded:", vecs.shape)

    ic = SearchIndexClient(EP, Cred())
    idx = SearchIndex(name=INDEX, fields=[
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchableField(name="body", type=SearchFieldDataType.String),
        SimpleField(name="n_tweets", type=SearchFieldDataType.Int32, filterable=True, sortable=True),
        SimpleField(name="n_authors", type=SearchFieldDataType.Int32, filterable=True, sortable=True),
        SimpleField(name="top_category", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SearchField(name="vec", type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                    searchable=True, vector_search_dimensions=DIMS, vector_search_profile_name="hnsw"),
    ], vector_search=VectorSearch(algorithms=[HnswAlgorithmConfiguration(name="hnsw-alg")],
                                  profiles=[VectorSearchProfile(name="hnsw", algorithm_configuration_name="hnsw-alg")]))
    ic.create_or_update_index(idx); print("index ready:", INDEX)

    sc = SearchClient(EP, INDEX, Cred())
    docs = [{"id": hashlib.sha1(b.encode()).hexdigest(), "body": b, "n_tweets": int(r.n_tweets), "n_authors": int(r.n_authors),
             "top_category": str(r.top_category), "vec": vecs[i].tolist()} for i, (b, r) in enumerate(zip(t["body"], t.itertuples()))]
    for i in range(0, len(docs), 500):
        res = sc.upload_documents(docs[i:i+500]); print("uploaded", i + len(res), "ok:", all(x.succeeded for x in res))
    print("document count:", sc.get_document_count())

if __name__ == "__main__":
    main()