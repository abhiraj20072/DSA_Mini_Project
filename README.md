# DSA Mini Project: Memory Allocator (First-Fit vs Best-Fit)

Data Structures mini project 3, Nov 1 to Nov 29, 2026.

## The problem

Every program needs memory in blocks of different sizes, and it gives those
blocks back at unpredictable times. A memory allocator is the part of the system
that keeps track of which memory is free and decides where each new request is
placed.

Over time, freed blocks leave gaps of different sizes scattered across memory.
This is called fragmentation. A program can have plenty of free memory in total
and still fail to get a block, because no single gap is big enough. How the
allocator chooses a gap for each request has a large effect on how bad this
gets.

## What we are doing

We build a small simulated memory allocator in Python and compare two ways of
choosing a gap:

- First-fit takes the first free gap that is large enough. It is quick,
  because the search stops early.
- Best-fit takes the smallest free gap that is large enough. It needs a full
  scan, but it tries to avoid breaking up large gaps.

Free memory is kept in a linked list of gaps. A simulator replays the same
random sequence of allocate and free requests through each policy, so the
comparison is fair. We measure:

- how fragmented the free memory becomes
- how often a request fails
- how many list entries a search has to look at

The goal is to find out when each policy performs better and what it costs.

## Plan

| Week | Work |
|---|---|
| 1 | Simulator and a baseline allocator (first-fit without merging freed gaps) |
| 2 | Both policies working, with merging of adjacent free gaps |
| 3 to 4 | Experiments and results |
| 4 | Report, demo and viva |

## Status

Week 1 is complete. The simulator and baseline are in the `week1_py` folder.

## Running the week 1 code

    cd week1_py
    python run_week1.py
