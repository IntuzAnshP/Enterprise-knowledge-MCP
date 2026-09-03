from typing import List
from sentence_transformers import CrossEncoder
from app.config import settings
from app.schemas.retrieval import RetrievedChunk

class RerankerService:
    _instance = None
    
    def __new__(cls):
        # Singleton pattern to load model only once at startup
        if cls._instance is None:
            cls._instance = super(RerankerService, cls).__new__(cls)
            if settings.ENABLE_RERANKER:
                cls._instance.model = CrossEncoder(settings.RERANKER_MODEL)
            else:
                cls._instance.model = None
        return cls._instance

    def rerank(self, query: str, chunks: List[RetrievedChunk], top_n: int) -> List[RetrievedChunk]:
        """
        Reranks a list of retrieved chunks using a CrossEncoder.
        Returns the top_n chunks sorted by the reranker's score.
        """
        if not self.model or not chunks:
            # If reranking is disabled or no chunks provided, return original chunks up to top_n
            return chunks[:top_n]
            
        # Prepare pairs of (query, chunk_content)
        pairs = [[query, chunk.content] for chunk in chunks]
        
        # Get scores from the cross-encoder
        scores = self.model.predict(pairs)
        
        # Update scores in the chunks
        for i, chunk in enumerate(chunks):
            # Convert numpy float32 to python float
            chunk.score = float(scores[i])
            
        # Sort chunks by score in descending order
        reranked_chunks = sorted(chunks, key=lambda x: x.score, reverse=True)
        
        return reranked_chunks[:top_n]
