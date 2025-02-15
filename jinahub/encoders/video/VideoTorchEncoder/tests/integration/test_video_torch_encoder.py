__copyright__ = "Copyright (c) 2020-2021 Jina AI Limited. All rights reserved."
__license__ = "Apache-2.0"

import os
import subprocess

import pytest
from jina import Document, Flow

from ...video_torch_encoder import VideoTorchEncoder

cur_dir = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture()
def kinects_videos():
    from torchvision.datasets import Kinetics400

    dataset = Kinetics400(
        root=os.path.join(cur_dir, '../data/kinetics400'), frames_per_clip=20
    )
    return [dataset[0][0], dataset[0][0]]


def test_video_torch_encoder(kinects_videos):
    f = Flow().add(uses=VideoTorchEncoder)
    with f:
        resp = f.post(
            on='/test',
            inputs=[Document(blob=video.detach().numpy()) for video in kinects_videos],
            return_results=True,
        )
        assert resp[0].docs[0].embedding.shape == (512,)
        assert resp[0].docs[1].embedding.shape == (512,)


@pytest.mark.docker
def test_docker_runtime(build_docker_image: str):
    with pytest.raises(subprocess.TimeoutExpired):
        subprocess.run(
            ['jina', 'executor', f'--uses=docker://{build_docker_image}'],
            timeout=30,
            check=True,
        )


@pytest.mark.gpu
@pytest.mark.docker
def test_docker_runtime_gpu(build_docker_image_gpu: str):
    with pytest.raises(subprocess.TimeoutExpired):
        subprocess.run(
            [
                'jina',
                'pea',
                f'--uses=docker://{build_docker_image_gpu}',
                '--gpus',
                'all',
                '--uses-with',
                'device:cuda',
            ],
            timeout=30,
            check=True,
        )
