__copyright__ = "Copyright (c) 2020-2021 Jina AI Limited. All rights reserved."
__license__ = "Apache-2.0"

from typing import Dict, Iterable, Optional

import torch
from jina import DocumentArray, Executor, requests
from jina_commons.batching import get_docs_batch_generator
from sentence_transformers import SentenceTransformer


class TransformerSentenceEncoder(Executor):
    """
    Encode the Document text into embedding.

    :param embedding_dim: the output dimensionality of the embedding
    """

    def __init__(
        self,
        model_name: str = 'all-MiniLM-L6-v2',
        device: str = 'cpu',
        default_traversal_paths: Iterable[str] = ('r',),
        default_batch_size: int = 32,
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.default_batch_size = default_batch_size
        self.default_traversal_paths = default_traversal_paths
        self.model = SentenceTransformer(model_name, device=device)

    @requests
    def encode(self, docs: Optional[DocumentArray], parameters: Dict, **kwargs):
        """
        Encode all docs with text and store the encodings in the ``embedding`` attribute
        of the docs.

        :param docs: Documents to send to the encoder. They need to have the ``text``
            attribute get an embedding.
        :param parameters: Any additional parameters for the `encode` function.
        """
        for batch in get_docs_batch_generator(
            docs,
            traversal_path=parameters.get(
                'traversal_paths', self.default_traversal_paths
            ),
            batch_size=parameters.get('batch_size', self.default_batch_size),
            needs_attr='text',
        ):
            texts = batch.get_attributes('text')

            with torch.no_grad():
                embeddings = self.model.encode(texts)
                for doc, embedding in zip(batch, embeddings):
                    doc.embedding = embedding
