import sys
import time
from multiprocessing import Pool

import numpy as np
from PIL import Image


def split_image(gray, n_parts):
    padded = np.pad(gray, 1, mode="edge")
    bounds = np.linspace(0, gray.shape[0], n_parts + 1, dtype=int)
    fragments = []
    for a, b in zip(bounds[:-1], bounds[1:]):
        pas = padded[a:b + 2]
        fragments.append(pas)
    return fragments


def sobel_fragment(p):
    p = p.astype(np.float32)
    gx = (p[:-2, 2:] + 2 * p[1:-1, 2:] + p[2:, 2:]) \
       - (p[:-2, :-2] + 2 * p[1:-1, :-2] + p[2:, :-2])
    gy = (p[2:, :-2] + 2 * p[2:, 1:-1] + p[2:, 2:]) \
       - (p[:-2, :-2] + 2 * p[:-2, 1:-1] + p[:-2, 2:])
    return np.hypot(gx, gy)


def merge_image(fragments):
    result = np.vstack(fragments)
    result = result / result.max() * 255 if result.max() > 0 else result
    return Image.fromarray(result.astype(np.uint8))

def save_fragment(processed, idx, out_path=None):
    vmax = max(f.max() for f in processed)
    frag = processed[idx] / vmax * 255 if vmax > 0 else processed[idx]
    out_path = out_path or f"fragment_{idx + 1}.png"
    Image.fromarray(frag.astype(np.uint8)).save(out_path)
    print(f"Zapisano fragment {idx + 1}/{len(processed)}: {out_path}")

def main(image_path, n_parts=8, out_path="wynik2.png"):
    gray = np.array(Image.open(image_path).convert("L"))

    t0 = time.perf_counter()
    fragments = split_image(gray, n_parts)

    with Pool(n_parts) as pool:
        processed = pool.map(sobel_fragment, fragments)

    save_fragment(processed, int(sys.argv[3]) if len(sys.argv) > 3 else 0)

    merge_image(processed).save(out_path)
    print(f"Gotowe: {out_path} ({n_parts} procesów, {time.perf_counter() - t0:.3f} s)")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "osa.png"
    parts = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    main(path, parts)