import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from allocator import AllocStatus, BaselineAllocator  # noqa: E402
from simulator import run  # noqa: E402
from workload import DISTS, generate_trace, mean_size  # noqa: E402


def free_list(a):
    return [(b.start, b.size) for b in a.blocks()]


class TestAllocator(unittest.TestCase):
    def test_init(self):
        a = BaselineAllocator(1024, 8)
        self.assertEqual(free_list(a), [(0, 1024)])
        a.check()
        for bad in [(1001, 8), (1024, 0), (0, 8)]:
            with self.assertRaises(ValueError):
                BaselineAllocator(*bad)

    def test_alloc_rounds_and_splits(self):
        a = BaselineAllocator(1024, 8)
        status, x, visited = a.alloc(100)
        self.assertEqual((status, x, visited), (AllocStatus.OK, 0, 1))
        self.assertEqual(a.allocated_bytes, 104)  # 100 rounded up to a multiple of 8
        status, y, _ = a.alloc(1)
        self.assertEqual(y, 104)
        self.assertEqual(a.allocated_bytes, 112)  # 1 byte still takes one aligned unit
        self.assertEqual(free_list(a), [(112, 912)])
        a.check()

    def test_exact_fit_removes_node(self):
        a = BaselineAllocator(100, 1)
        a.alloc(40)
        status, y, _ = a.alloc(60)
        self.assertEqual((status, y), (AllocStatus.OK, 40))
        self.assertIsNone(a.head)
        self.assertEqual(a.total_free, 0)
        self.assertEqual(a.ext_frag(), 0.0)
        self.assertEqual(a.alloc(1)[0], AllocStatus.OOM)
        a.check()

    def test_free_does_not_coalesce(self):
        a = BaselineAllocator(300, 1)
        addrs = [a.alloc(100)[1] for _ in range(3)]
        for addr in addrs:
            a.free(addr)
        # Baseline: the three adjacent blocks stay separate.
        self.assertEqual(free_list(a), [(0, 100), (100, 100), (200, 100)])
        self.assertEqual(a.total_free, 300)
        a.check()

    def test_frag_vs_oom_classification(self):
        a = BaselineAllocator(300, 1)
        addrs = [a.alloc(100)[1] for _ in range(3)]
        for addr in addrs:
            a.free(addr)
        self.assertEqual(a.alloc(150)[0], AllocStatus.FRAG)  # 300 free, largest 100
        self.assertEqual(a.alloc(400)[0], AllocStatus.OOM)   # larger than all free memory
        a.check()

    def test_first_fit_takes_first_not_best(self):
        # Heap 1000 with holes [100,+200] and [400,+50]; request 40.
        a = BaselineAllocator(1000, 1)
        addr = [a.alloc(s)[1] for s in (100, 200, 100, 50, 550)]
        a.free(addr[1])
        a.free(addr[3])
        self.assertEqual(free_list(a), [(100, 200), (400, 50)])
        status, got, visited = a.alloc(40)
        self.assertEqual((got, visited), (100, 1))
        self.assertEqual(free_list(a), [(140, 160), (400, 50)])
        a.check()

    def test_invalid_and_double_free(self):
        a = BaselineAllocator(1024, 8)
        _, x, _ = a.alloc(64)
        a.free(x)
        with self.assertRaises(ValueError):
            a.free(x)
        with self.assertRaises(ValueError):
            a.free(12345)
        with self.assertRaises(ValueError):
            a.alloc(0)
        a.check()

    def test_free_keeps_list_sorted(self):
        a = BaselineAllocator(1000, 1)
        addr = [a.alloc(100)[1] for _ in range(10)]
        for i in (7, 2, 9, 0, 5):
            a.free(addr[i])
            a.check()
        self.assertEqual([s for s, _ in free_list(a)], [0, 200, 500, 700, 900])


class TestWorkload(unittest.TestCase):
    def test_deterministic(self):
        a = generate_trace(2000, 7, "bimodal", 50)
        b = generate_trace(2000, 7, "bimodal", 50)
        c = generate_trace(2000, 8, "bimodal", 50)
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_frees_refer_to_live_objects(self):
        for dist in DISTS:
            live = set()
            for op in generate_trace(3000, 3, dist, 80):
                if op[0] == "a":
                    self.assertNotIn(op[1], live)
                    live.add(op[1])
                else:
                    self.assertIn(op[1], live)
                    live.remove(op[1])

    def test_prefill_then_steady(self):
        trace = generate_trace(1000, 1, "uniform", 100)
        self.assertTrue(all(op[0] == "a" for op in trace[:100]))
        live = sum(1 if op[0] == "a" else -1 for op in trace)
        self.assertTrue(70 <= live <= 130)  # hovers near the target

    def test_sizes_in_range(self):
        bounds = {"uniform": (16, 512), "small": (16, 2048), "bimodal": (16, 2048)}
        for dist, (lo, hi) in bounds.items():
            sizes = [op[2] for op in generate_trace(3000, 2, dist, 50) if op[0] == "a"]
            self.assertTrue(lo <= min(sizes) and max(sizes) <= hi, dist)

    def test_mean_size_positive(self):
        for dist in DISTS:
            self.assertGreater(mean_size(dist), 16)


class TestSimulator(unittest.TestCase):
    def test_invariants_after_every_op(self):
        heap = 32768
        for dist in DISTS:
            target = int(0.85 * heap / mean_size(dist))
            trace = generate_trace(3000, 4, dist, target)
            res = run(trace, heap, sample_every=25, check_every=1)
            self.assertEqual(res.attempts, res.successes + res.fail_frag + res.fail_oom)
            n_free_ops = sum(1 for op in trace if op[0] == "f")
            self.assertEqual(res.frees + res.skipped_frees, n_free_ops)
            self.assertTrue(0.0 <= res.mean_ext_frag <= 1.0)
            self.assertTrue(0.0 <= res.mean_util <= 1.0)

    def test_same_trace_same_result(self):
        trace = generate_trace(2000, 9, "uniform", 100)
        r1 = run(trace, 65536)
        r2 = run(trace, 65536)
        self.assertEqual(r1, r2)

    def test_warmup_discards_samples(self):
        trace = generate_trace(1000, 1, "uniform", 50)
        full = run(trace, 65536, sample_every=50, warmup_ops=0)
        warm = run(trace, 65536, sample_every=50, warmup_ops=500)
        self.assertEqual(full.nsamples, 20)
        self.assertEqual(warm.nsamples, 10)

    def test_failed_alloc_then_free_is_skipped(self):
        # Heap holds exactly one 64-byte object, so the second allocation fails.
        trace = [("a", 0, 64), ("a", 1, 64), ("f", 1), ("f", 0)]
        res = run(trace, 64, sample_every=0, check_every=1)
        self.assertEqual((res.successes, res.fail_oom, res.skipped_frees, res.frees),
                         (1, 1, 1, 1))

    def test_series_recording(self):
        trace = generate_trace(500, 1, "small", 30)
        res = run(trace, 65536, sample_every=50, record_series=True)
        self.assertEqual(len(res.series), res.nsamples)
        self.assertEqual(res.series[0][0], 50)


if __name__ == "__main__":
    unittest.main()
