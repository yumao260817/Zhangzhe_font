import torch

from src.gb2312 import level1_chars
from src.paths import PROCESSED, STDSRC
from src.stage_train import GeneratorUNet, PatchDiscriminator, load_pairs

chars = [c for c in level1_chars() if (STDSRC / f"{c}.png").exists() and (PROCESSED / f"{c}.png").exists()]
s, t = load_pairs(chars[:8])
print("pair shapes:", s.shape, t.shape)
x = torch.tensor(s[:8][:, None])
y = torch.tensor(t[:8][:, None])
G = GeneratorUNet(1, 1)
D = PatchDiscriminator(2)
out = G(x)
dout = D(torch.cat([x, out], 1))
print("gen out:", out.shape, "D out:", dout.shape)
assert out.shape == y.shape, "shape mismatch"
print("SMOKE OK")