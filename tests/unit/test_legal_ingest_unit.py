from app.application.use_cases.legal_ingest import IngestLegalDocument
from app.domain.entities.legal import LegalDocument


class FakeLegalDocs:
    def __init__(self):
        self.docs: dict[str, LegalDocument] = {}
        self.relations = []

    def upsert(self, doc: LegalDocument) -> None:
        self.docs[doc.doc_id] = doc

    def get(self, doc_id: str):
        return self.docs.get(doc_id)

    def upsert_relations(self, relations):
        self.relations.extend(relations)


class FakeLegalChunks:
    def __init__(self):
        self.chunks = []

    def upsert_many(self, chunks):
        self.chunks.extend(chunks)

    def upsert_relations(self, relations):
        pass

    def get_texts_by_refs(self, chunk_refs):
        return {}

    def get_meta_by_refs(self, chunk_refs):
        return {}

    def count_for_doc(self, doc_id):
        return sum(1 for c in self.chunks if getattr(c, "doc_id", None) == doc_id)



class FakeEmbedder:
    def embed_documents(self, texts):
        return [[0.1] * 8 for _ in texts]

    def embed_query(self, text):
        return [0.1] * 8


class FakeGraph:
    def __init__(self):
        self.calls = []

    def ensure_schema(self):
        pass

    def upsert_document_tree(self, **kwargs):
        self.calls.append(("tree", kwargs))

    def upsert_doc_relations(self, relations):
        self.calls.append(("rels", relations))

    def upsert_chunk_relations(self, relations):
        pass

    def expand(self, chunk_refs, limit=80):
        return {"seeds": chunk_refs, "sibling_paths": [], "ancestor_paths": [], "related_docs": []}


def test_ingest_legal_document_skeleton():
    docs = FakeLegalDocs()
    chunks = FakeLegalChunks()
    graph = FakeGraph()
    result = IngestLegalDocument(docs, chunks, FakeEmbedder(), graph).execute(
        thuoc_tinh={
            "doc_id": "d1",
            "doc_num": "1/2024",
            "title": "Fixture",
            "doc_type": "Nghị định",
            "status_flag": 1,
        },
        chunks=[{"chunk_ref": "C1.D1.K1.a", "chunk_text": "Điều 1 khoản 1 điểm a", "chunk_type": "body"}],
    )
    assert result["doc_id"] == "d1"
    assert result["chunk_count"] == 1
    assert "d1" in docs.docs
    assert len(chunks.chunks) == 1
    assert chunks.chunks[0].embedding is not None
    assert graph.calls
