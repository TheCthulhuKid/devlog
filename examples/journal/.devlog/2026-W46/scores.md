Write a mark in each `[ ]`. A gold decision is `matched` or `missed`. A generated decision
is `wrong` or `extra` (true, but not in gold); leave it empty when it is the match of the
gold decision above it.

## Gold decisions

- [missed] Introduced run limits again to ensure fairness and stop when a run hangs (a4c6c84)
  - no match
- [missed] The judge was cached mainly to ensure a rerun gives the same score (b0f12d7)
  - no match

## Generated decisions not in gold

- [extra] Bake-off schema validity started as a computed `report is not None`, so every failed run counted as a schema failure. It became three-valued: True if a report came back, False only on the shared `InvalidReport` error, and None for run limits, timeouts, API errors, and cut-off or refused replies (`IncompleteReport`). The rate skips the None runs, because they never produced a whole report to judge. ([9159729](https://github.com/TheCthulhuKid/bake-off/commit/915972969e1d76bdf5ab71d28471219fffedc606), [1c39432](https://github.com/TheCthulhuKid/bake-off/commit/1c3943244d39e2db4fa2690f06120958ff83788f))
- [extra] Bake-off telemetry first kept the run deadline in a pydantic PrivateAttr on RunStats. It was moved to its own ContextVar beside the stats so RunStats stays plain data that loads back from a results file unchanged, and so code running in a copied context can see both. ([47f360f](https://github.com/TheCthulhuKid/bake-off/commit/47f360fb348b1650d99d8e175164eeee646fc061))
- [extra] In bake-off's derived fixtures, seeded duplicates are hand-rewritten to describe the same problem as a second reporter would, instead of being copies, because a copy would only test string matching. Translations are also written by hand, because building fixtures calls no model. ([9b44352](https://github.com/TheCthulhuKid/bake-off/commit/9b44352aa630bc6052729223b799ef9d492478fc), [6bd54b1](https://github.com/TheCthulhuKid/bake-off/commit/6bd54b1e8afeac3a574dc333cab9c8197527456d))
- [extra] The pip-tools derived slices are consecutive thirds in fixture order, except that #2096 was moved into slice 3. This keeps the natural duplicate pair #2096/#1902 (a maintainer found they share a root cause) in one fixture. The seeded duplicate in slice 3 was retargeted from #1902 to #1792 to match. ([b3aa813](https://github.com/TheCthulhuKid/bake-off/commit/b3aa8130da8670ba434a01ca8f9c486fb9c6c2e2))
