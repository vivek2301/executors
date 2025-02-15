__copyright__ = "Copyright (c) 2020-2021 Jina AI Limited. All rights reserved."
__license__ = "Apache-2.0"

import subprocess
from typing import Iterable, Optional

from jina import DocumentArray, Executor, requests
from jina.logging.logger import JinaLogger
from jina_commons.batching import get_docs_batch_generator
from laserembeddings import Laser


class LaserEncoder(Executor):
    """
    LaserEncoder is a text encoder based on Facebook Research's LASER encoder.

    This encoder is suitable for producing multi-lingual sentence embeddings, enabling
    you to have sentences from multiple languages in the same latent space.

    :param path_to_bpe_codes: path to bpe codes from Laser. Defaults to
        ``Laser.DEFAULT_BPE_CODES_FILE.``
    :param path_to_bpe_vocab: path to bpe vocabs from Laser. Defaults to
        ``Laser.DEFAULT_BPE_VOCAB_FILE``.
    :param path_to_encoder: path to the encoder from Laser. Defaults to
        ``Laser.DEFAULT_ENCODER_FILE``.
    :param download_data: Whether data should be downloaded on initialization. This is
        convenient when just trying out the encoder, but should be turned off in a
        production setting (where you should already have the data on disk), as it can
        lead to large startup times.
    :param default_language: The default language of the text. Can be overriden by a
        request parameter. The full list of possible values can be found at
        [LASER](https://github.com/facebookresearch/LASER#supported-languages)
        with the language code
        ([ISO 639-1](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes))
    :param cpu: if True, forces the use of the CPU even when a GPU is available.
    :param default_batch_size: size of each batch
    :param default_traversal_paths: traversal path of the Documents, (e.g. 'r', 'c')
    :param args:  Additional positional arguments
    :param kwargs: Additional keyword arguments
    """

    def __init__(
        self,
        path_to_bpe_codes: Optional[str] = None,
        path_to_bpe_vocab: Optional[str] = None,
        path_to_encoder: Optional[str] = None,
        download_data: bool = True,
        default_language: str = 'en',
        cpu: bool = False,
        default_batch_size: int = 32,
        default_traversal_paths: Iterable[str] = ('r',),
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.logger = JinaLogger(self.__class__.__name__)

        self._path_to_bpe_codes = path_to_bpe_codes
        self._path_to_bpe_vocab = path_to_bpe_vocab
        self._path_to_encoder = path_to_encoder

        self.default_batch_size = default_batch_size
        self.default_traversal_paths = default_traversal_paths
        self.default_language = default_language

        if download_data:
            self.logger.info("Downloading data for the Laser model")
            subprocess.run(
                ['python', '-m', 'laserembeddings', 'download-models'], check=True
            )

        self.model = Laser(
            bpe_codes=self._path_to_bpe_codes,
            bpe_vocab=self._path_to_bpe_vocab,
            encoder=self._path_to_encoder,
            embedding_options={'cpu': cpu},
        )

    @requests
    def encode(self, docs: Optional[DocumentArray], parameters: dict, **kwargs):
        """
        Encode all docs with text and store the encodings in the embedding attribute
        of the docs.

        :param docs: documents sent to the encoder. The docs must have the ``text``
            attribute.
        :param parameters: dictionary to define the ``traversal_path``, the
            ``batch_size`` and ``language``. For example,
            ``{'traversal_paths': ['r'], 'batch_size': 10}``. This will override the
            default parameters set at init.
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

            for document_batch in document_batches_generator:
                text_batch = [d.text for d in document_batch]

                language = parameters.get('language', self.default_language)
                embeddings = self.model.embed_sentences(text_batch, lang=language)
                for document, embedding in zip(document_batch, embeddings):
                    document.embedding = embedding
