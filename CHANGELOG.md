# Changelog

Versions follow [semantic versioning](https://semver.org/); each one is a git tag.

## [0.2.0] - 2026-11-27

### Added

- `devlog note` writes a note into the inbox from any folder. Run inside one of your repos, it
  records that repo and the branch it is on; `--repo` and `--branch` name others.
- A note that starts with `[repo]` or `[repo branch]` belongs to that repo and joins that
  branch's work in the draft.
- `devlog --version` prints the installed version.
- `python -m devlog` runs the command line.

### Changed

- A commit keeps its branch after its GitHub pull request is merged and the branch is deleted.
  Before, such a commit was read as `main` and grouped by the files it changed, so collecting a
  past week again can now group its work differently.

### Fixed

- Commits are matched by the whole email address, so a similar address no longer counts.
- A pick that is empty or names a claim that was not listed is asked again on the next run, not
  reused.
- A claim or thread line with a line break in it stays on one line of the entry.

## [0.1.0] - 2026-11-26

The first release: `collect`, `draft`, `sample`, `pick`, `stats` and `evaluate`.

[0.2.0]: https://github.com/TheCthulhuKid/devlog/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/TheCthulhuKid/devlog/releases/tag/v0.1.0
