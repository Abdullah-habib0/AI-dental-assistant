"""Turns text into vectors with a Hugging Face model, run locally on the CPU.

This is the only file that knows which model is used. Swapping models means changing
this file and re-running the ingest script - nothing else.

The model is used through `transformers` directly rather than `sentence-transformers`.
On the development machine, sentence-transformers pulls in scipy, and Windows blocks one
of scipy's compiled files, so it cannot run there.
"""

import os
import threading

# Hugging Face prints a long warning on Windows about symlinks. It is harmless: the model
# files are simply copied instead of linked. Must be set before transformers is imported.
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

# BGE models search better when questions - and only questions - start with this.
_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
_BATCH_SIZE = 32


class Embedder:
    def __init__(self, model_name: str):
        # Imported here, not at the top, so starting the app or running tests does not
        # load PyTorch until something actually needs to embed text.
        import torch
        from transformers import AutoModel, AutoTokenizer
        from transformers.utils import logging

        logging.set_verbosity_error()
        self._torch = torch
        self._tokenizer = AutoTokenizer.from_pretrained(model_name)
        self._model = AutoModel.from_pretrained(model_name).eval()
        self._lock = threading.Lock()

        self.name = model_name
        self.dimension: int = self._model.config.hidden_size
        self.max_tokens: int = self._tokenizer.model_max_length

    def count_tokens(self, text: str) -> int:
        """Tokens the model will see, including its two special start and end tokens."""
        return len(self._tokenizer.encode(text, add_special_tokens=True))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # Refuse anything too long instead of letting the model quietly cut it short.
        # The chunker keeps chunks well under the limit, so this only fires on a bug.
        for text in texts:
            if self.count_tokens(text) > self.max_tokens:
                raise ValueError(
                    f"Text is longer than the model's {self.max_tokens}-token limit: {text[:80]!r}..."
                )
        vectors = []
        for start in range(0, len(texts), _BATCH_SIZE):
            vectors.extend(self._embed(texts[start : start + _BATCH_SIZE], truncate=False))
        return vectors

    def embed_query(self, question: str) -> list[float]:
        # A question long enough to hit the limit is cut short rather than refused: the
        # point of a question is nearly always near its start, and refusing would break
        # the chat over an unusually long message.
        return self._embed([_QUERY_PREFIX + question], truncate=True)[0]

    def _embed(self, texts: list[str], truncate: bool) -> list[list[float]]:
        limit = {"truncation": True, "max_length": self.max_tokens} if truncate else {}
        batch = self._tokenizer(texts, padding=True, return_tensors="pt", **limit)
        # One embedding at a time: the model is shared by every request.
        with self._lock, self._torch.no_grad():
            output = self._model(**batch).last_hidden_state[:, 0]  # BGE uses the first token
        # Length 1, so comparing two vectors is a simple dot product.
        return self._torch.nn.functional.normalize(output, dim=-1).tolist()
