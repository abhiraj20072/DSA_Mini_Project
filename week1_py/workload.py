"""Seeded workload generator.

A trace is a list of operations:
    ("a", object_id, size)   allocate `size` bytes for object_id
    ("f", object_id)         free object_id
The trace does not depend on any allocator, so every policy can replay the same
sequence.
"""
import math
import random

DISTS = ("uniform", "small", "bimodal")


def sample_size(rng, dist):
    if dist == "uniform":
        return rng.randint(16, 512)
    if dist == "small":
        # Mostly small requests with an exponential tail, clipped to 2048.
        x = 16.0 - 48.0 * math.log(1.0 - rng.random())
        return min(2048, int(x))
    if dist == "bimodal":
        if rng.random() < 0.8:
            return rng.randint(16, 64)
        return rng.randint(512, 2048)
    raise ValueError(f"unknown distribution: {dist}")


def mean_size(dist, align=8, samples=20000):
    """Empirical mean request size after rounding up to `align`."""
    rng = random.Random(12345)
    total = 0
    for _ in range(samples):
        s = sample_size(rng, dist)
        total += (s + align - 1) // align * align
    return total / samples


def generate_trace(n_ops, seed, dist="uniform", target_live=100):
    """The first target_live operations are allocations (pre-fill). After that
    the number of live objects hovers around target_live: allocation probability
    is 0.7 below the target and 0.3 at or above it. Frees pick a uniformly
    random live object."""
    if n_ops <= 0:
        raise ValueError("n_ops must be positive")
    rng = random.Random(seed)
    ops = []
    live = []
    next_id = 0
    for i in range(n_ops):
        if not live or i < target_live:
            do_alloc = True
        else:
            do_alloc = rng.random() < (0.7 if len(live) < target_live else 0.3)
        if do_alloc:
            ops.append(("a", next_id, sample_size(rng, dist)))
            live.append(next_id)
            next_id += 1
        else:
            idx = rng.randrange(len(live))
            ops.append(("f", live[idx]))
            live[idx] = live[-1]  # swap-remove keeps this O(1)
            live.pop()
    return ops
