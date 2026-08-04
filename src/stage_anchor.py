import json
import sys
from pathlib import Path

import cv2
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score

from .gb2312 import level1_chars
from .paths import PROCESSED, ANCHORS, REPORTS
from .stage_preview import _imread_process, PROCESSED