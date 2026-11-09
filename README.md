# Memory Allocator Simulator: Week 1 (Python)

Data Structures mini project 3. The goal of the project is to compare two ways
of placing memory requests in a linked free list, first-fit and best-fit. This
folder contains the week 1 deliverable: a working simulator and a baseline
allocator to measure against.

## What week 1 covers

- A simulated heap and a linked free list.
- A baseline allocator: first-fit placement with no merging of freed blocks.
- A seeded workload generator that produces repeatable streams of allocate and
  free events.
- A simulator that replays a stream on an allocator and collects metrics.
- Unit tests and a driver script that prints and saves baseline results.

Best-fit and block merging (coalescing) are the week 2 additions. The code is
structured so they can be added without changing the simulator.

## How to run

Requires Python 3.8 or newer. No external packages are needed.

    python run_week1.py
    python -m unittest discover -s tests -v

On Windows, use `py` in place of `python` if `python` is not recognised.

`run_week1.py` accepts options: `--heap` (heap size in bytes, default 262144),
`--ops` (operations per run, default 10000), `--seeds` (number of random seeds,
default 5), `--util` (target utilization, default 0.7) and `--out` (CSV file
name).

## Files

| File | Purpose |
|---|---|
| `allocator.py` | The baseline allocator and its linked free list |
| `workload.py` | Generates the stream of allocate and free events |
| `simulator.py` | Replays a stream on an allocator and measures it |
| `run_week1.py` | Script that runs the experiment and writes the results |
| `tests/test_week1.py` | Automated tests |
| `week1_results.csv` | Output of the last run of `run_week1.py` |

## Background

A running program asks for blocks of memory of varying sizes and gives them
back at unpredictable times. An allocator keeps track of which parts of memory
are free and decides where each new request goes. The difficulty is
fragmentation: memory can be free in total but split into pieces that are each
too small for the next request.

This project does not use real memory. The heap is a range of integer
addresses from 0 to the heap size, and the allocator keeps records of which
ranges are free and which are in use. This keeps the data structures and the
policy logic visible and makes experiments fast and repeatable.

## How the code works

### Free list (`allocator.py`)

Free memory is stored as a singly linked list of blocks, each holding a start
address, a size and a pointer to the next block. The list is always sorted by
start address. At the beginning it holds a single block covering the whole
heap.

Allocated memory is not stored in the list. A dictionary maps the address of
each live allocation to its size, so that `free(address)` knows how many bytes
to return.

### Allocating

1. The request size is rounded up to a multiple of 8.
2. First-fit walks the list from the front and stops at the first block that is
   large enough. The number of blocks examined is recorded as the search cost.
3. If a block is found, the bytes are taken from its front. The block shrinks,
   or is removed from the list when it fits exactly. The address and size are
   stored in the dictionary.
4. If no block is found, the request fails. The failure is classified as out of
   memory when the request is larger than all free memory, or as a
   fragmentation failure when enough memory is free in total but no single block
   is large enough.

### Freeing

1. The address is looked up in the dictionary. An unknown address or a second
   free of the same address raises an error.
2. The region is inserted into the free list at its sorted position.
3. In the baseline, neighbouring free regions are not merged. Each freed region
   stays as its own block. This is deliberate. Merging is the week 2 change.

### Workload generator (`workload.py`)

A trace is a list of events: allocate object N with a given size, or free
object N. The generator is seeded, so the same seed always produces the same
trace. The trace does not depend on any allocator, which allows the same trace
to be replayed on every policy for a fair comparison.

The first part of a trace only allocates, until a target number of live objects
is reached. After that the generator keeps the live count near the target by
allocating with probability 0.7 below it and 0.3 above it. Frees pick a random
live object.

Three request size distributions are used:

| Name | Sizes | Meaning |
|---|---|---|
| uniform | 16 to 512 bytes, all equally likely | Neutral reference |
| small | Mostly small with a rare larger request, capped at 2048 | Typical programs with many small objects |
| bimodal | 80% from 16 to 64 bytes, 20% from 512 to 2048 bytes | Mix of small objects and large buffers |

The target number of live objects is computed from the target utilization and
the average request size of each distribution, so that "70% load" means a
similar amount of memory in use for all three.

### Simulator (`simulator.py`)

`run(trace, heap_size)` creates a fresh allocator and processes the trace one
event at a time. If an allocation fails, the later free of that object is
skipped and counted. Every 50 events it samples the state of the heap. Samples
taken during the initial fill-up phase are discarded so that the averages
describe steady state. An optional mode runs the allocator's consistency check
after every event, which the tests use.

### Consistency check

`allocator.check()` verifies that the free list is sorted, has no overlapping or
empty blocks, and that the free and allocated regions together cover the heap
exactly with no gaps and no overlaps. The tests run it after every operation.

## Metrics

| Metric | Definition |
|---|---|
| External fragmentation | 1 minus (largest free block divided by total free memory). Near 0 means the free space is one large piece. Near 1 means it is broken into many small pieces. |
| Failure rate | Failed allocation requests divided by all allocation requests |
| Search cost | Average number of free-list blocks examined per allocation |
| Utilization | Allocated bytes divided by heap size |
| Free blocks | Average number of separate blocks in the free list |

## Baseline results

Heap of 262144 bytes, 10000 operations per run, 5 seeds, target utilization 0.7.
Values are averages over the seeds.

| Distribution | Ext. fragmentation | Failure rate | Blocks examined per allocation | Utilization | Free blocks |
|---|---|---|---|---|---|
| uniform | 0.868 | 0.0895 | 778.1 | 0.606 | 1601.5 |
| small | 0.362 | 0.0000 | 224.1 | 0.703 | 1047.3 |
| bimodal | 0.904 | 0.0447 | 336.6 | 0.526 | 1230.6 |

What the numbers show:

- Every failure is a fragmentation failure. The out-of-memory count is zero in
  all runs. Memory was available, but not in one contiguous piece.
- Without merging, freed regions pile up as separate small blocks, which gives
  between 1000 and 1600 free blocks and high fragmentation.
- Search cost is high because first-fit starts at the front each time and has to
  skip the many small leftover blocks that collect there.
- The small distribution does well because its requests are small enough to
  reuse the small leftover blocks.
- Utilization falls below the 0.7 target for uniform and bimodal because failed
  requests never become live objects.
- Results are consistent across seeds, so the pattern is not due to chance.

## Limitations

- The heap is simulated, so there is no real memory and no cost for pointer
  handling, headers or cache effects.
- Only one heap size and one target utilization are used in week 1.
- Five seeds give a stable pattern but wide statistical claims need more runs.

## Next steps (week 2 and later)

- Add coalescing so that freed neighbours merge into larger blocks.
- Add best-fit placement and run it against first-fit on the same traces.
- Run the full set of experiments across all distributions and loads and
  report the comparison.
