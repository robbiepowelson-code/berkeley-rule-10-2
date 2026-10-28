"""Run tile2net inference on CPU by stubbing the CUDA-only calls.

tile2net hard-requires a CUDA runtime, but the model itself is plain PyTorch.
This shim makes every torch.cuda call a no-op and .cuda() an identity, then
hands off to tile2net's own CLI. Used for the AR 10.2 sidewalk sample run.
"""
import sys, types, torch

torch.cuda.is_available = lambda: True
torch.cuda.device_count = lambda: 1
torch.cuda.set_device = lambda *a, **k: None
torch.cuda.get_device_name = lambda *a, **k: "cpu (shim)"
torch.cuda.empty_cache = lambda: None
torch.cuda.reset_peak_memory_stats = lambda *a, **k: None
torch.cuda.max_memory_allocated = lambda *a, **k: 0
torch.cuda.max_memory_reserved = lambda *a, **k: 0
torch.cuda.synchronize = lambda *a, **k: None
torch.cuda.current_device = lambda: 0
torch.Tensor.cuda = lambda self, *a, **k: self
torch.nn.Module.cuda = lambda self, *a, **k: self
_load = torch.load
torch.load = lambda *a, **k: _load(*a, **{**k, "map_location": "cpu"})
torch.set_num_threads(2)

class _DP(torch.nn.Module):
    """DataParallel stand-in: wraps the module so .module works, runs on CPU."""
    def __init__(self, module, *a, **k):
        super().__init__(); self.module = module
    def forward(self, *a, **k): return self.module(*a, **k)
torch.nn.DataParallel = _DP
torch.nn.parallel.DataParallel = _DP
torch.Tensor.is_cuda = property(lambda self: True)   # placement check only

from tile2net.__main__ import main  # noqa: E402
sys.argv = ["tile2net"] + sys.argv[1:]
main()
