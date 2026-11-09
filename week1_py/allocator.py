"""Week 1 baseline allocator: first-fit over a linked free list, no coalescing.

The heap is simulated. Addresses are plain integers from 0 to heap_size, and the
free list records which ranges are free. Allocated ranges are tracked in a dict
(address -> size) so that free(addr) knows how many bytes to return.
"""
from enum import Enum


class AllocStatus(Enum):
    OK = "ok"
    OOM = "oom"    # request is larger than the total free memory
    FRAG = "frag"  # enough free memory in total, but no single block fits


class Block:
    """One free region of the heap. The list is sorted by start address."""

    __slots__ = ("start", "size", "next")

    def __init__(self, start, size, nxt=None):
        self.start = start
        self.size = size
        self.next = nxt


class BaselineAllocator:
    def __init__(self, heap_size, align=8):
        if align <= 0 or heap_size <= 0 or heap_size % align != 0:
            raise ValueError("heap_size must be a positive multiple of align")
        self.heap_size = heap_size
        self.align = align
        self.head = Block(0, heap_size)
        self.total_free = heap_size
        self.allocated_bytes = 0
        self.live = {}  # address -> rounded size

    def round_size(self, size):
        return (size + self.align - 1) // self.align * self.align

    def alloc(self, size):
        """First-fit allocation.

        Returns (status, address or None, nodes_visited).
        """
        if size <= 0:
            raise ValueError("size must be positive")
        rounded = self.round_size(size)

        prev, node, visited = None, self.head, 0
        while node is not None:
            visited += 1
            if node.size >= rounded:
                break
            prev, node = node, node.next

        if node is None:
            status = AllocStatus.OOM if rounded > self.total_free else AllocStatus.FRAG
            return status, None, visited

        addr = node.start
        if node.size == rounded:  # exact fit: unlink the node
            if prev is None:
                self.head = node.next
            else:
                prev.next = node.next
        else:                     # split: keep the remainder, take from the front
            node.start += rounded
            node.size -= rounded

        self.total_free -= rounded
        self.allocated_bytes += rounded
        self.live[addr] = rounded
        return AllocStatus.OK, addr, visited

    def free(self, addr):
        """Returns the region at addr to the free list.

        Returns the number of nodes passed while finding the insertion point.
        Raises ValueError for an unknown address or a double free.
        """
        size = self.live.get(addr)
        if size is None:
            raise ValueError(f"invalid or double free at address {addr}")
        visited = self._insert(addr, size)
        del self.live[addr]
        self.allocated_bytes -= size
        return visited

    def _insert(self, start, size):
        """Sorted insert. Week 2 adds merging with adjacent blocks here."""
        prev, node, visited = None, self.head, 0
        while node is not None and node.start < start:
            visited += 1
            prev, node = node, node.next
        if prev is not None and prev.start + prev.size > start:
            raise RuntimeError("freed region overlaps a free block")
        if node is not None and start + size > node.start:
            raise RuntimeError("freed region overlaps a free block")
        new = Block(start, size, node)
        if prev is None:
            self.head = new
        else:
            prev.next = new
        self.total_free += size
        return visited

    # ---- metrics helpers ----

    def blocks(self):
        node = self.head
        while node is not None:
            yield node
            node = node.next

    def block_count(self):
        return sum(1 for _ in self.blocks())

    def largest_free(self):
        return max((b.size for b in self.blocks()), default=0)

    def ext_frag(self):
        """1 - largest free block / total free bytes (0.0 when nothing is free)."""
        if self.total_free == 0:
            return 0.0
        return 1.0 - self.largest_free() / self.total_free

    # ---- consistency check ----

    def check(self):
        """Raises AssertionError if any invariant is broken (for tests and debugging)."""
        total, prev_end = 0, 0
        first = True
        for b in self.blocks():
            assert b.size > 0, "zero-size free block"
            assert 0 <= b.start and b.start + b.size <= self.heap_size, "block outside heap"
            if not first:
                assert b.start >= prev_end, "free list unsorted or overlapping"
            prev_end = b.start + b.size
            first = False
            total += b.size
        assert total == self.total_free, "total_free mismatch"
        assert sum(self.live.values()) == self.allocated_bytes, "allocated_bytes mismatch"
        assert self.allocated_bytes + self.total_free == self.heap_size, "bytes not conserved"

        # Free and live regions must tile the heap exactly, with no gap or overlap.
        regions = [(b.start, b.size) for b in self.blocks()] + list(self.live.items())
        regions.sort()
        cursor = 0
        for start, size in regions:
            assert start == cursor, f"gap or overlap at {cursor}"
            assert size % self.align == 0 or start + size == self.heap_size
            cursor += size
        assert cursor == self.heap_size, "tiling does not cover the heap"
