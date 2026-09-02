from typing import List
from sentence_transformers import SentenceTransformer

class EmbeddingService:
    MODEL_NAME = "BAAI/bge-base-en-v1.5"
    DIMENSION = 768
    
    _instance = None
    
    def __new__(cls):
        # Singleton pattern to load model only once at startup
        if cls._instance is None:
            cls._instance = super(EmbeddingService, cls).__new__(cls)
            cls._instance.model = SentenceTransformer(cls.MODEL_NAME)
        return cls._instance

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        # For document embedding in BGE models, we don't need a specific query prefix
        # We normalize embeddings so that dot product == cosine similarity
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    def embed_single(self, text: str) -> List[float]:
        return self.embed_batch([text])[0]
