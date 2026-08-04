import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from .gb2312 import level1_chars
from .paths import MODELS, PROCESSED, STDSRC

GRID = 128
CH = 1


def imread_gray(path: Path):
    return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)


class UNetBlock(nn.Module):
    def __init__(self, in_c, out_c, down=True, dropout=False):
        super().__init__()
        self.down = down
        if down:
            self.block = nn.Sequential(
                nn.Conv2d(in_c, out_c, 4, 2, 1, bias=False),
                nn.BatchNorm2d(out_c),
                nn.LeakyReLU(0.2, True),
            )
        else:
            self.block = nn.Sequential(
                nn.ConvTranspose2d(in_c, out_c, 4, 2, 1, bias=False),
                nn.BatchNorm2d(out_c),
                nn.ReLU(True),
            )
            if dropout:
                self.block = nn.Sequential(self.block[0], self.block[1], nn.Dropout(0.5), self.block[2])

    def forward(self, x):
        return self.block(x)


class GeneratorUNet(nn.Module):
    def __init__(self, in_c=1, out_c=1):
        super().__init__()
        self.e1 = nn.Sequential(nn.Conv2d(in_c, 64, 4, 2, 1), nn.LeakyReLU(0.2, True))
        self.e2 = UNetBlock(64, 128, down=True)
        self.e3 = UNetBlock(128, 256, down=True)
        self.e4 = UNetBlock(256, 512, down=True)
        self.e5 = UNetBlock(512, 512, down=True)
        self.e6 = UNetBlock(512, 512, down=True)
        self.e7 = UNetBlock(512, 512, down=True)
        self.d1 = UNetBlock(512, 512, down=False, dropout=True)
        self.d2 = UNetBlock(1024, 512, down=False, dropout=True)
        self.d3 = UNetBlock(1024, 512, down=False, dropout=True)
        self.d4 = UNetBlock(1024, 512, down=False)
        self.d5 = UNetBlock(768, 256, down=False)
        self.d6 = UNetBlock(384, 128, down=False)
        self.d7 = UNetBlock(192, 64, down=False)
        self.head = nn.Sequential(nn.Conv2d(64, out_c, 3, 1, 1), nn.Tanh())

    def forward(self, x):
        e1 = self.e1(x)
        e2 = self.e2(e1)
        e3 = self.e3(e2)
        e4 = self.e4(e3)
        e5 = self.e5(e4)
        e6 = self.e6(e5)
        e7 = self.e7(e6)
        d1 = self.d1(e7)
        d2 = self.d2(torch.cat([d1, e6], 1))
        d3 = self.d3(torch.cat([d2, e5], 1))
        d4 = self.d4(torch.cat([d3, e4], 1))
        d5 = self.d5(torch.cat([d4, e3], 1))
        d6 = self.d6(torch.cat([d5, e2], 1))
        d7 = self.d7(torch.cat([d6, e1], 1))
        return self.head(d7)


class PatchDiscriminator(nn.Module):
    def __init__(self, in_c=2):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(in_c, 64, 4, 2, 1),
            nn.LeakyReLU(0.2, True),
            nn.Conv2d(64, 128, 4, 2, 1, bias=False),
            nn.BatchNorm2d(128),
            nn.LeakyReLU(0.2, True),
            nn.Conv2d(128, 256, 4, 2, 1, bias=False),
            nn.BatchNorm2d(256),
            nn.LeakyReLU(0.2, True),
            nn.Conv2d(256, 512, 4, 1, 1, bias=False),
            nn.BatchNorm2d(512),
            nn.LeakyReLU(0.2, True),
            nn.Conv2d(512, 1, 4, 1, 1),
        )

    def forward(self, x):
        return self.net(x)


def load_pairs(chars):
    srcs, tgts = [], []
    for ch in chars:
        sp, tp = STDSRC / f"{ch}.png", PROCESSED / f"{ch}.png"
        if not (sp.exists() and tp.exists()):
            continue
        s = cv2.resize(imread_gray(sp), (GRID, GRID))
        t = cv2.resize(imread_gray(tp), (GRID, GRID))
        srcs.append(s.astype(np.float32) / 255.0)
        tgts.append(t.astype(np.float32) / 255.0)
    return np.stack(srcs), np.stack(tgts)


def run(
    epochs=80,
    batch=16,
    lr=2e-4,
    l1=100.0,
    save_every=10,
    resume=None,
    log=None,
):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    torch.manual_seed(0)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"设备: {dev}")

    chars = [c for c in level1_chars() if (STDSRC / f"{c}.png").exists()]
    srcs, tgts = load_pairs(chars)
    n = len(srcs)
    if n == 0:
        print("无配对数据，先运行 stdsrc 与 preprocess")
        return
    print(f"配对样本: {n} 字")

    idx = np.random.permutation(n)
    val_n = max(1, int(n * 0.05))
    val_idx = idx[:val_n]
    train_idx = idx[val_n:]

    G = GeneratorUNet(CH, CH).to(dev)
    D = PatchDiscriminator(CH * 2).to(dev)
    optG = optim.Adam(G.parameters(), lr=lr, betas=(0.5, 0.999))
    optD = optim.Adam(D.parameters(), lr=lr, betas=(0.5, 0.999))
    gan = nn.MSELoss()
    l1l = nn.L1Loss()

    start = 0
    if resume:
        ck_path = Path(resume) if isinstance(resume, str) else resume
        ck = torch.load(ck_path, map_location=dev)
        G.load_state_dict(ck["G"])
        D.load_state_dict(ck["D"])
        optG.load_state_dict(ck["optG"])
        optD.load_state_dict(ck["optD"])
        start = int(ck["epoch"]) + 1

    MODELS.mkdir(parents=True, exist_ok=True)
    for ep in range(start, epochs):
        perm = torch.randperm(len(train_idx))
        gsum = dsum = l1sum = 0.0
        nb = 0
        for b in range(0, len(perm), batch):
            bi = train_idx[perm[b : b + batch]]
            s = torch.tensor(srcs[bi][:, None]).to(dev)
            t = torch.tensor(tgts[bi][:, None]).to(dev)

            for _ in range(1):
                D.zero_grad()
                real = D(torch.cat([s, t], 1))
                fake = G(s)
                fake_d = D(torch.cat([s, fake.detach()], 1))
                loss_d = 0.5 * (gan(real, torch.ones_like(real)) + gan(fake_d, torch.zeros_like(fake_d)))
                loss_d.backward()
                optD.step()

            G.zero_grad()
            fake = G(s)
            fake_d = D(torch.cat([s, fake], 1))
            loss_g = gan(fake_d, torch.ones_like(fake_d)) + l1 * l1l(fake, t)
            loss_g.backward()
            optG.step()

            gsum += loss_g.item()
            dsum += loss_d.item()
            l1sum += l1l(fake, t).item()
            nb += 1
        print(f"epoch {ep+1}/{epochs} G={gsum/nb:.3f} D={dsum/nb:.3f} L1={l1sum/nb:.4f}")

        if (ep + 1) % save_every == 0 or ep == epochs - 1:
            ck = {
                "G": G.state_dict(),
                "D": D.state_dict(),
                "optG": optG.state_dict(),
                "optD": optD.state_dict(),
                "epoch": ep,
            }
            p = MODELS / f"pix2pix_{ep+1:04d}.pt"
            torch.save(ck, p)
            print(f"checkpoint -> {p}")

    torch.save(
        {"G": G.state_dict()},
        MODELS / "pix2pix_final.pt",
    )
    print("训练完成: pix2pix_final.pt")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--epochs", type=int, default=80)
    p.add_argument("--batch", type=int, default=16)
    p.add_argument("--lr", type=float, default=2e-4)
    p.add_argument("--l1", type=float, default=100.0)
    p.add_argument("--save_every", type=int, default=10)
    p.add_argument("--resume", default=None)
    a = p.parse_args()
    run(epochs=a.epochs, batch=a.batch, lr=a.lr, l1=a.l1, save_every=a.save_every, resume=a.resume)
