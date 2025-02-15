from typing import Iterable, Optional

import torch
from jina import DocumentArray, Executor, requests
from jina.logging.logger import JinaLogger
from jina_commons.batching import get_docs_batch_generator
from transformers import (
    DPRContextEncoder,
    DPRContextEncoderTokenizerFast,
    DPRQuestionEncoder,
    DPRQuestionEncoderTokenizerFast,
)


class DPRTextEncoder(Executor):
    """
    Encode text into embeddings using a DPR model. You have to choose
    whether to use a context or a question encoder.

    For context encoders it is recommened to encode them together with the title,
    by setting the ``title_tag_key`` property. This is in order to match the
    encoding method used in model training.

    :param pretrained_model_name_or_path: Can be either:
        - the model id of a pretrained model hosted inside a model repo
          on [huggingface.co](huggingface.co).
        - A path to a directory containing model weights, saved using
          the transformers model's ``save_pretrained()`` method
    :param encoder_type: Either ``'context'`` or ``'question'``. Make sure this
        matches the model that you are using.
    :param base_tokenizer_model: Base tokenizer model. The possible values are
        the same as for the ``pretrained_model_name_or_path`` parameters. If not
        provided, the ``pretrained_model_name_or_path`` parameter value will be used
    :param title_tag_key: The key under which the titles are saved in the documents'
        tag property. It is recommended to set this property for context encoders,
        to match the model pre-training. It has no effect for question encoders.
    :param max_length: Max length argument for the tokenizer
    :param default_batch_size: Default batch size for encoding, used if the
        batch size is not passed as a parameter with the request.
    :param default_traversal_paths: Default traversal paths for encoding, used if the
        traversal path is not passed as a parameter with the request.
    :param device: The device (cpu or gpu) that the model should be on.
    """

    def __init__(
        self,
        pretrained_model_name_or_path: str = 'facebook/dpr-question_encoder-single-nq-base',
        encoder_type: str = 'question',
        base_tokenizer_model: Optional[str] = None,
        title_tag_key: Optional[str] = None,
        max_length: Optional[int] = None,
        default_batch_size: int = 32,
        default_traversal_paths: Iterable[str] = ('r',),
        device: str = 'cpu',
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.device = device
        self.max_length = max_length
        self.title_tag_key = title_tag_key
        self.logger = JinaLogger(self.__class__.__name__)

        if encoder_type not in ['context', 'question']:
            raise ValueError(
                'The ``encoder_type`` parameter should be either "context"'
                f' or "question", but got {encoder_type}'
            )
        self.encoder_type = encoder_type

        if not base_tokenizer_model:
            base_tokenizer_model = pretrained_model_name_or_path

        if encoder_type == 'context':
            if not self.title_tag_key:
                self.logger.warning(
                    'The `title_tag_key` argument is not set - it is recommended'
                    ' to encode the context text together with the title to match the'
                    ' model pre-training. '
                )
            self.tokenizer = DPRContextEncoderTokenizerFast.from_pretrained(
                base_tokenizer_model
            )
            self.model = DPRContextEncoder.from_pretrained(
                pretrained_model_name_or_path
            )
        elif encoder_type == 'question':
            self.tokenizer = DPRQuestionEncoderTokenizerFast.from_pretrained(
                base_tokenizer_model
            )
            self.model = DPRQuestionEncoder.from_pretrained(
                pretrained_model_name_or_path
            )

        self.model = self.model.to(self.device).eval()

        self.default_traversal_paths = default_traversal_paths
        self.default_batch_size = default_batch_size

    @requests
    def encode(self, docs: Optional[DocumentArray], parameters: dict, **kwargs):
        """
        Encode all docs with text and store the encodings in the embedding
        attribute of the docs.

        :param docs: documents sent to the encoder. The docs must have the
            ``text`` attribute.
        :param parameters: dictionary to define the ``traversal_path`` and the
            ``batch_size``. For example,
            ``parameters={'traversal_paths': ['r'], 'batch_size': 10}``
        """

        if docs:
            document_batches_generator = get_docs_batch_generator(
                docs,
                traversal_path=parameters.get(
                    'traversal_paths', self.default_traversal_paths
                ),
                batch_size=parameters.get('batch_size', self.default_batch_size),
                needs_attr='text',
            )

            for batch_docs in document_batches_generator:
                with torch.no_grad():
                    texts = batch_docs.get_attributes('text')
                    text_pairs = None
                    if self.encoder_type == 'context' and self.title_tag_key:
                        text_pairs = list(
                            filter(
                                lambda x: x is not None,
                                batch_docs.get_attributes(
                                    f'tags__{self.title_tag_key}'
                                ),
                            )
                        )
                        if len(text_pairs) != len(batch_docs):
                            raise ValueError(
                                'If you set `title_tag_key` property, all documents'
                                ' that you want to encode must have this tag. Found'
                                f' {len(text_pairs) - len(batch_docs)} documents'
                                ' without it.'
                            )

                    inputs = self.tokenizer(
                        text=texts,
                        text_pair=text_pairs,
                        max_length=self.max_length,
                        padding='longest',
                        truncation=True,
                        return_tensors='pt',
                    )
                    embeddings = self.model(**inputs).pooler_output.cpu().numpy()

                for doc, embedding in zip(batch_docs, embeddings):
                    doc.embedding = embedding
