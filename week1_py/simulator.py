"""Replays a trace on an allocator and collects metrics."""
from dataclasses import dataclass, field

from allocator import AllocStatus, BaselineAllocator


@dataclass
class Result:
    # counters
    attempts: int = 0
    successes: int = 0
    fail_frag: int = 0
    fail_oom: int = 0
    frees: int = 0
    skipped_frees: int = 0  # freeing an object whose allocation had failed
    alloc_visits: int = 0
    free_visits: int = 0
    nsamples: int = 0
    max_ext_frag: float = 0.0
    # derived metrics, filled in at the end of the run
    mean_alloc_visits: float = 0.0  # list nodes examined per allocation attempt
    mean_free_visits: float = 0.0
    failure_rate: float = 0.0
    mean_ext_frag: float = 0.0
    mean_util: float = 0.0          # allocated bytes / heap size
    mean_blocks: float = 0.0        # mean free-list length
    series: list = field(default_factory=list)  # (op, ext_frag, util, nblocks)


def run(trace, heap_size, *, align=8, sample_every=50, warmup_ops=0,
        check_every=0, record_series=False, allocator_cls=BaselineAllocator):
    """Replays `trace` on a fresh allocator.

    sample_every: sample fragmentation metrics every N ops (0 = never)
    warmup_ops:   samples taken within the first N ops are discarded
    check_every:  run allocator.check() every N ops (0 = never, slow)
    """
    alloc = allocator_cls(heap_size, align)
    addr_of = {}  # object id -> address, only for allocations that succeeded
    res = Result()
    sum_frag = sum_util = sum_blocks = 0.0

    for i, op in enumerate(trace, start=1):
        if op[0] == "a":
            _, oid, size = op
            status, addr, visited = alloc.alloc(size)
            res.attempts += 1
            res.alloc_visits += visited
            if status is AllocStatus.OK:
                res.successes += 1
                addr_of[oid] = addr
            elif status is AllocStatus.FRAG:
                res.fail_frag += 1
            else:
                res.fail_oom += 1
        else:
            addr = addr_of.pop(op[1], None)
            if addr is None:
                res.skipped_frees += 1
            else:
                res.frees += 1
                res.free_visits += alloc.free(addr)

        if check_every and i % check_every == 0:
            alloc.check()

        if sample_every and i % sample_every == 0 and i > warmup_ops:
            frag = alloc.ext_frag()
            util = alloc.allocated_bytes / heap_size
            nb = alloc.block_count()
            sum_frag += frag
            sum_util += util
            sum_blocks += nb
            res.max_ext_frag = max(res.max_ext_frag, frag)
            res.nsamples += 1
            if record_series:
                res.series.append((i, frag, util, nb))

    if res.attempts:
        res.mean_alloc_visits = res.alloc_visits / res.attempts
        res.failure_rate = (res.fail_frag + res.fail_oom) / res.attempts
    if res.frees:
        res.mean_free_visits = res.free_visits / res.frees
    if res.nsamples:
        res.mean_ext_frag = sum_frag / res.nsamples
        res.mean_util = sum_util / res.nsamples
        res.mean_blocks = sum_blocks / res.nsamples
    return res
