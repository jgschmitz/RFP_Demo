from pymongo import MongoClient
import voyageai

# --- CONFIG ---
MONGODB_URI = ""
DB_NAME = "RFP_Demo"
VOYAGE_API_KEY = ""

mongo = MongoClient(MONGODB_URI)
db = mongo[DB_NAME]
vo = voyageai.Client(api_key=VOYAGE_API_KEY)

def clean(value):
    return "" if value is None else str(value).strip()

def build_embedding_text(name, doc):
    if name in ["knowledge_base", "historical_rfp_answers"]:
        return " ".join(filter(None, [
            clean(doc.get("question_text")),
            clean(doc.get("answer_text"))
        ]))
    if name == "source_documents":
        return " ".join(filter(None, [
            clean(doc.get("title")),
            clean(doc.get("chunk_text"))
        ]))
    return ""

def get_embedding(text):
    result = vo.embed(
        texts=[text],
        model="voyage-4-large"
    )
    return result.embeddings[0]

collections = ["knowledge_base", "historical_rfp_answers", "source_documents"]

for name in collections:
    col = db[name]
    print(f"\nProcessing {name}...")

    for doc in col.find({}, {
        "_id": 1,
        "question_text": 1,
        "answer_text": 1,
        "title": 1,
        "chunk_text": 1
    }):
        embedding_text = build_embedding_text(name, doc)

        update = {"embedding_text": embedding_text}

        if embedding_text:
            update["embedding"] = get_embedding(embedding_text)

        res = col.update_one(
            {"_id": doc["_id"]},
            {"$set": update}
        )

        print(f"{name} | {doc['_id']} | matched={res.matched_count} modified={res.modified_count} | embedding_text_len={len(embedding_text)}")

print("\nDone.")
