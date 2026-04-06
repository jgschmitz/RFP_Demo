from pymongo import MongoClient
import voyageai

# --- CONFIG ---
MONGODB_URI = ""
DB_NAME = "RFP_Demo"
VOYAGE_API_KEY = ""

mongo = MongoClient(MONGODB_URI)
db = mongo[DB_NAME]
vo = voyageai.Client(api_key=VOYAGE_API_KEY)

# --- QUERY ---
QUERY = "Describe your HIPAA compliance controls and audit process"

# --- EMBED QUERY ---
query_vec = vo.embed(
    texts=[QUERY],
    model="voyage-4-large"
).embeddings[0]

# --- SEARCH FUNCTION ---
def search_collection(name):
    return list(db[name].aggregate([
        {
            "$vectorSearch": {
                "index": "vector_index",
                "path": "embedding",
                "queryVector": query_vec,
                "numCandidates": 20,
                "limit": 3
            }
        },
        {
            "$project": {
                "_id": 1,
                "question_text": 1,
                "answer_text": 1,
                "title": 1,
                "chunk_text": 1,
                "review_status": 1,
                "outcome": 1,
                "score": {"$meta": "vectorSearchScore"}
            }
        }
    ]))

# --- COLLECT RESULTS ---
all_results = []

for name in ["knowledge_base", "historical_rfp_answers", "source_documents"]:
    results = search_collection(name)
    for r in results:
        r["source_collection"] = name
        all_results.append(r)

# --- RERANK FUNCTION ---
def rerank(doc):
    score = float(doc["score"])

    if doc.get("review_status") == "approved":
        score += 0.08
    if doc.get("review_status") == "stale":
        score -= 0.08

    if doc.get("outcome") == "won":
        score += 0.08
    if doc.get("outcome") == "lost":
        score -= 0.08

    return score

ranked = sorted(all_results, key=rerank, reverse=True)

# --- PRETTY PRINT (MAINFRAME STYLE) ---
def pretty_print(results):
    print("\n" + "="*80)
    print("RFP INTELLIGENCE SYSTEM v1.0")
    print("="*80)
    print(f"QUERY: {QUERY}")
    print("="*80)

    for i, r in enumerate(results, start=1):
        print("\n" + "-"*80)
        print(f"RESULT #{i}")
        print("-"*80)

        print(f"SOURCE        : {r['source_collection']}")
        print(f"VECTOR_SCORE  : {round(float(r['score']), 4)}")
        print(f"FINAL_SCORE   : {round(rerank(r), 4)}")

        if r.get("review_status"):
            print(f"STATUS        : {r['review_status']}")

        if r.get("outcome"):
            print(f"OUTCOME       : {r['outcome']}")

        # WHY LOGIC
        reasons = []
        if r.get("review_status") == "approved":
            reasons.append("APPROVED")
        if r.get("outcome") == "won":
            reasons.append("PRIOR_WIN")
        if r["source_collection"] == "source_documents":
            reasons.append("POLICY_SOURCE")

        if reasons:
            print(f"SIGNAL        : {', '.join(reasons)}")

        print("\nCONTENT:")
        print("-"*80)

        if r["source_collection"] == "source_documents":
            print(f"{r.get('title')}")
            print(f"{r.get('chunk_text')}")
        else:
            print(f"Q: {r.get('question_text')}")
            print(f"A: {r.get('answer_text')}")

    print("\n" + "="*80)
    print("END OF RESULTS")
    print("="*80 + "\n")

# --- RUN ---
pretty_print(ranked)
