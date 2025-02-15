import os
import shutil
from pathlib import Path

import numpy as np
import PIL.Image as Image
import pytest
from jina import Document, DocumentArray, Executor

from ...big_transfer import BigTransferEncoder

directory = os.path.dirname(os.path.realpath(__file__))


def test_config():
    ex = Executor.load_config(str(Path(__file__).parents[2] / 'config.yml'))
    assert ex.model_path == 'pretrained'
    assert ex.model_name == 'Imagenet21k/R50x1'


def test_initialization_and_model_download():
    shutil.rmtree('pretrained', ignore_errors=True)
    # This call will download the model
    encoder = BigTransferEncoder()
    assert encoder.model_path == 'pretrained'
    assert encoder.model_name == 'Imagenet21k/R50x1'
    assert os.path.exists('pretrained')
    assert os.path.exists(os.path.join('pretrained', 'saved_model.pb'))
    # This call will use the downloaded model
    _ = BigTransferEncoder()
    shutil.rmtree('pretrained', ignore_errors=True)
    with pytest.raises(AttributeError):
        _ = BigTransferEncoder(model_name='model_not_exists')


def test_encoding():
    doc = Document(uri=os.path.join(directory, '../test_data/test_image.png'))
    doc.convert_image_uri_to_blob()

    encoder = BigTransferEncoder()

    encoder.encode(DocumentArray([doc]), {})
    assert doc.embedding.shape == (2048,)


def test_preprocessing():
    doc = Document(uri=os.path.join(directory, '../test_data/test_image.png'))
    doc.convert_image_uri_to_blob()

    encoder = BigTransferEncoder(target_dim=(256, 256, 3))

    encoder.encode(DocumentArray([doc]), {})
    assert doc.embedding.shape == (2048,)


def test_encoding_default_chunks():
    doc = Document(text="testing")
    chunk = Document(uri=os.path.join(directory, '../test_data/test_image.png'))
    for i in range(3):
        doc.chunks.append(chunk)
        doc.chunks[i].convert_image_uri_to_blob()

    encoder = BigTransferEncoder(default_traversal_paths=['c'])

    encoder.encode(DocumentArray([doc]), {})
    assert doc.embedding is None
    for i in range(3):
        assert doc.chunks[i].embedding.shape == (2048,)


def test_encoding_override_chunks():
    doc = Document(text="testing")
    chunk = Document(uri=os.path.join(directory, '../test_data/test_image.png'))
    for i in range(3):
        doc.chunks.append(chunk)
        doc.chunks[i].convert_image_uri_to_blob()

    encoder = BigTransferEncoder()
    assert encoder.default_traversal_paths == ('r',)

    encoder.encode(DocumentArray([doc]), parameters={'traversal_paths': ['c']})
    assert doc.embedding is None
    for i in range(3):
        assert doc.chunks[i].embedding.shape == (2048,)


@pytest.mark.gpu
def test_encoding_gpu():
    doc = Document(uri=os.path.join(directory, '../test_data/test_image.png'))
    doc.convert_image_uri_to_blob()

    assert doc.embedding is None

    encoder = BigTransferEncoder(device='/GPU:0')

    encoder.encode(DocumentArray([doc]), {})
    assert doc.embedding.shape == (2048,)
