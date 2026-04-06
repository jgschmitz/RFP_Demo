import streamlit as st
st.set_page_config(
    page_title="RFP Intelligence System",
    layout="wide"
)

from pymongo import MongoClient
import voyageai

# =========================
# CONFIG
# =========================
MONGODB_URI = ""
DB_NAME = "RFP_Demo"
VOYAGE_API_KEY = ""

INDEX_NAME = "vector_index"
EMBED_MODEL = "voyage-4-large"

COLLECTIONS = [
    "knowledge_base",
    "historical_rfp_answers",
    "source_documents"
]

# =========================
# CLIENTS
# =========================
@st.cache_resource
def get_mongo():
    client = MongoClient(MONGODB_URI)
    return client[DB_NAME]

@st.cache_resource
def get_voyage():
    return voyageai.Client(api_key=VOYAGE_API_KEY)

db = get_mongo()
vo = get_voyage()

# =========================
# HELPERS
# =========================
def embed_query(text: str):
    return vo.embed(
        texts=[text],
        model=EMBED_MODEL
    ).embeddings[0]

def search_collection(name: str, query_vec: list, limit: int = 3):
    pipeline = [
        {
            "$vectorSearch": {
                "index": INDEX_NAME,
                "path": "embedding",
                "queryVector": query_vec,
                "numCandidates": 20,
                "limit": limit
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
    ]
    results = list(db[name].aggregate(pipeline))
    for r in results:
        r["source_collection"] = name
    return results

def rerank_score(doc: dict) -> float:
    score = float(doc.get("score", 0))

    if doc.get("review_status") == "approved":
        score += 0.08
    if doc.get("review_status") == "stale":
        score -= 0.08

    if doc.get("outcome") == "won":
        score += 0.08
    if doc.get("outcome") == "used":
        score += 0.03
    if doc.get("outcome") == "lost":
        score -= 0.08

    return score

def explain_signals(doc: dict):
    signals = []

    if doc.get("review_status") == "approved":
        signals.append("APPROVED")
    if doc.get("review_status") == "stale":
        signals.append("STALE")
    if doc.get("outcome") == "won":
        signals.append("PRIOR_WIN")
    if doc.get("outcome") == "used":
        signals.append("PREVIOUSLY_USED")
    if doc.get("outcome") == "lost":
        signals.append("PRIOR_LOSS")
    if doc.get("source_collection") == "source_documents":
        signals.append("POLICY_SOURCE")

    return signals

def run_search(query: str, per_collection_limit: int = 3):
    # ✅ THIS IS THE FIX — dynamic query
    query_vec = embed_query(query)

    all_results = []
    for name in COLLECTIONS:
        all_results.extend(search_collection(name, query_vec, per_collection_limit))

    for r in all_results:
        r["final_score"] = rerank_score(r)
        r["signals"] = explain_signals(r)

    ranked = sorted(all_results, key=lambda x: x["final_score"], reverse=True)
    return ranked

def source_label(name: str):
    return {
        "knowledge_base": "Knowledge Base",
        "historical_rfp_answers": "Historical RFP Answers",
        "source_documents": "Source Documents"
    }.get(name, name)

# =========================
# UI
# =========================
st.title("RFP Intelligence System v1.0")
st.caption("Answer Selection (Pre-Generation)")

with st.sidebar:
    st.subheader("Settings")
    per_collection_limit = st.slider(
        "Results per collection",
        1, 5, 3
    )

# default only — NOT used in logic
default_query = "Describe your HIPAA compliance controls and audit process"

query = st.text_input(
    "RFP Question",
    value=default_query
)

run = st.button("Run Answer Selection", type="primary", use_container_width=True)

# =========================
# RUN
# =========================
if run:
    with st.spinner("Selecting best answers across systems..."):
        ranked = run_search(query, per_collection_limit)

    st.success("Selection complete.")

    top = ranked[0]

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Top Recommended Result")
        st.write(f"**Source:** {source_label(top['source_collection'])}")
        st.write(f"**Final Score:** {top['final_score']:.4f}")
        st.write(f"**Vector Score:** {float(top['score']):.4f}")

        if top.get("review_status"):
            st.write(f"**Status:** {top['review_status']}")
        if top.get("outcome"):
            st.write(f"**Outcome:** {top['outcome']}")
        if top.get("signals"):
            st.write(f"**Signals:** {', '.join(top['signals'])}")

        if top["source_collection"] == "source_documents":
            st.write(f"**Title:** {top.get('title')}")
            st.write(top.get("chunk_text"))
        else:
            st.write(f"**Question:** {top.get('question_text')}")
            st.write(top.get("answer_text"))

    with col2:
        st.subheader("Why this Result")
        st.write("- semantic similarity")
        st.write("- approval status")
        st.write("- prior win signals")
        st.write("- source grounding")

    st.markdown("---")
    st.subheader("Ranked Results")

    for i, r in enumerate(ranked, 1):
        with st.container(border=True):
            st.write(f"### Result #{i}")
            st.write(f"Source: {source_label(r['source_collection'])}")
            st.write(f"Final Score: {r['final_score']:.4f}")

            if r["source_collection"] == "source_documents":
                st.write(r.get("title"))
                st.write(r.get("chunk_text"))
            else:
                st.write(r.get("question_text"))
                st.write(r.get("answer_text"))
