"""Non-secret runtime/build metadata for diagnostic reproducibility."""
import platform
import sys
import numpy
import scipy
import sklearn
import torch


def fingerprint():
    return dict(python=sys.version,platform=platform.platform(),machine=platform.machine(),processor=platform.processor(),
        numpy=numpy.__version__,scipy=scipy.__version__,scikit_learn=sklearn.__version__,torch=torch.__version__,
        device='cpu',torch_threads=torch.get_num_threads(),mkldnn_enabled=torch.backends.mkldnn.enabled,
        deterministic_algorithms=torch.are_deterministic_algorithms_enabled(),torch_build=torch.__config__.show(),
        note='Same seed is not a guarantee of bit-identical weights across operating systems/CPU builds. No environment variables or credentials collected.')
