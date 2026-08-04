import json
import sys
from pathlib import Path

import cv2
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from .gb2312 import level1_chars
from .paths import ANCHORS, PROCESSED, REPORTS

N_CLUSTERS_MAX = 8


def imread_gray(path):
    return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)


def extract_features(img):
    bin_img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    dt = cv2.distanceTransform(bin_img, cv2.DIST_L2, 5)
    radius = dt[dt > 0]
    n, labels = cv2.connectedComponents(np.uint8(bin_img > 0))
    sizes = np.bincount(labels[labels > 0])
    nink = int(bin_img.sum() / 255)
    h, w = img.shape
    if len(radius):
        mean_r = float(radius.mean())
        std_r = float(radius.std())
        q75 = float(np.percentile(radius, 75))
    else:
        mean_r = std_r = q75 = 0.0
    mean_sz = float(sizes.mean()) if len(sizes) else 0.0
    ink_gray = float(img[bin_img > 0].mean()) if nink else 0.0
    return np.array([
        nink / (w * h),
        mean_r,
        std_r,
        q75,
        float(n - 1),
        mean_sz,
        ink_gray,
    ])


def run():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    chars = [c for c in level1_chars() if (PROCESSED / f"{c}.png").exists()]
    if not chars:
        print("无已处理源字，请先执行 preprocess")
        return
    names, vecs = [], []
    for ch in chars:
        im = imread_gray(PROCESSED / f"{ch}.png")
        if im is not None:
            vecs.append(extract_features(im))
            names.append(ch)
    print(f"特征提取完成 {len(names)} 字")
    X = StandardScaler().fit_transform(np.asarray(vecs))
    best_k, best_s = 2, -1.0
    for k in range(2, min(N_CLUSTERS_MAX, len(X))):
        lab = KMeans(n_clusters=k, n_init="auto", random_state=0).fit_predict(X)
        s = silhouette_score(X, lab)
        if s > best_s:
            best_k, best_s = k, s
    kmeans = KMeans(n_clusters=best_k, n_init="auto", random_state=0).fit(X)
    labels = kmeans.labels_
    s_final = silhouette_score(X, labels)
    ANCHORS.mkdir(parents=True, exist_ok=True)
    clusters = {}
    for c in range(best_k):
        inds = np.where(labels == c)[0]
        members = [names[i] for i in inds]
        dists = np.linalg.norm(X[inds] - kmeans.cluster_centers_[c], axis=1)
        anchor_char = names[inds[int(dists.argmin())]]
        anchor_img = imread_gray(PROCESSED / f"{anchor_char}.png")
        fname = ANCHORS / f"anchor_c{c}_{anchor_char}.png"
        cv2.imencode(".png", anchor_img)[1].tofile(str(fname))
        clusters[c] = {
            "anchor": anchor_char,
            "anchor_file": str(fname),
            "count": len(members),
            "members": members,
        }
    manifest = {
        "n": len(names),
        "k": best_k,
        "silhouette": round(float(s_final), 4),
        "clusters": clusters,
    }
    (ANCHORS / "anchors.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"聚类完成 k={best_k} silhouette={s_final:.4f}")
    for c, info in clusters.items():
        print(f"  簇{c}: {info['count']} 字, 锚点 {info['anchor']} -> {info['anchor_file']}")
