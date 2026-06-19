"""
Job: take raw document dicts from any source (ArXiv, GitHub, HackerNews, etc.),
chunk their content, embed each chunk, and return chunk dicts ready for ChromaDB.
Designed to handle messy text from multiple sources, not just clean abstracts.
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
from typing import List

# Load model once at module level — no need to reload on every call
MODEL = SentenceTransformer("all-MiniLM-L6-v2")

# One splitter instance, reused for all sources
SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=1500,       
    chunk_overlap=50,      
    separators=["\n\n", "\n", ". ", " ", ""]  
)


def chunk_text(text: str) -> list[str]:
    """
    Splits any text into overlapping chunks using recursive strategy.
    Works on clean abstracts, messy READMEs, HN threads, blog posts.
    """
    return SPLITTER.split_text(text)


def embed_chunks(chunks: list[str]) -> list[list[float]]:
    """
    Converts a list of text chunks into 384-dim vectors.
    Batched for efficiency.
    """
    embeddings = MODEL.encode(chunks, show_progress_bar=False)
    return embeddings.tolist()


def process_documents(documents: list[dict]) -> list[dict]:
    """
    Main function. Takes document dicts from ANY source fetcher,
    returns chunk dicts ready to be stored in ChromaDB.

    Each input document must have:
        - "text" or "abstract" field  ← the content to chunk
        - "paper_id" or "doc_id"      ← unique identifier
        - "title", "url", "topic", "week", "source"

    Returns chunk dicts with full metadata inherited from the document.
    """
    all_chunks = []

    for doc in documents:
        # Handle both "abstract" (ArXiv) and "text" (future sources)
        content = doc.get("abstract") or doc.get("text", "")
        doc_id = doc.get("paper_id") or doc.get("doc_id", "unknown")

        if not content.strip():
            continue  # skip empty documents

        text_chunks = chunk_text(content)
        embeddings = embed_chunks(text_chunks)

        for i, (chunk, embedding) in enumerate(zip(text_chunks, embeddings)):
            chunk_dict = {
                "chunk_id":  f"{doc_id}_{i}",
                "text":      chunk,
                "embedding": embedding,
                # metadata — inherited from source document, never recalculated
                "doc_id":    doc_id,
                "title":     doc.get("title", ""),
                "url":       doc.get("url", ""),
                "topic":     doc.get("topic", ""),
                "source":    doc.get("source", "arxiv"),  # arxiv / github / hn
                "week":      doc.get("week", ""),         # ← critical for delta
            }
            all_chunks.append(chunk_dict)

    return all_chunks


# ── Quick test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sys.path.append(".")
    from ingestion.arxiv_fetcher import fetch_papers

    print("Fetching papers...")
    papers = fetch_papers(
        topic='cat:cs.LG AND abs:"large language model"',
        max_results=5,
        weeks_ago=0
    )
    print(f"Got {len(papers)} papers\n")

    print("Chunking and embedding...")
    chunks = process_documents(papers)

    print(f"Total chunks: {len(chunks)}\n")

    if chunks:
        c = chunks[0]
        print(f"chunk_id  : {c['chunk_id']}")
        print(f"week      : {c['week']}")
        print(f"source    : {c['source']}")
        print(f"topic     : {c['topic']}")
        print(f"title     : {c['title']}")
        print(f"text      : {c['text'][:100]}...")
        print(f"embedding : {len(c['embedding'])} dimensions")
        print(f"first 5   : {c['embedding'][:5]}")