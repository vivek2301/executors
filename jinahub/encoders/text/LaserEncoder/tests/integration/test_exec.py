__copyright__ = "Copyright (c) 2020-2021 Jina AI Limited. All rights reserved."
__license__ = "Apache-2.0"

import subprocess

import pytest
from jina import Document, DocumentArray, Flow

from ...laser_encoder import LaserEncoder

_EMBEDDING_DIM = 1024


@pytest.mark.parametrize('request_size', [1, 10, 50, 100])
def test_integration(request_size: int):
    docs = DocumentArray(
        [Document(text='just some random text here') for _ in range(50)]
    )
    with Flow(return_results=True).add(uses=LaserEncoder) as flow:
        resp = flow.post(
            on='/index',
            inputs=docs,
            request_size=request_size,
            return_results=True,
        )

    assert sum(len(resp_batch.docs) for resp_batch in resp) == 50
    for r in resp:
        for doc in r.docs:
            assert doc.embedding.shape == (_EMBEDDING_DIM,)


@pytest.mark.docker
def test_docker_runtime(build_docker_image: str):
    with pytest.raises(subprocess.TimeoutExpired):
        subprocess.run(
            [
                'jina',
                'executor',
                f'--uses=docker://{build_docker_image}',
            ],
            timeout=30,
            check=True,
        )
