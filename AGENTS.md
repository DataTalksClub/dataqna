# Working in this repo

## Commit as you go

Commit each coherent change as soon as it works. Do not let the working tree
accumulate — a tree with twenty modified files cannot be split back into honest
commits afterwards, so the history loses the reasoning that made each change
worth making, and there is nothing to revert when one of them turns out wrong.

Committing is also how work reaches people. A push to `main` runs Test, and a
green Test triggers Deploy (`.github/workflows/`), which is what puts the change
on qna.dtcdev.click. Until it is committed and pushed, nobody can look at it on
a real device — a screenshot taken from the deployed site is showing the last
commit, not the working tree.

Run `make test` before committing, and keep every commit deployable on its own.

## Commit messages

An imperative subject line, no full stop, roughly 72 characters or less, saying
what the change does rather than which files it touches. Then a blank line and
prose — paragraphs, not bullet lists — explaining why the change was worth
making and what was considered and rejected. `git log` is this project's design
record; read a few entries before writing one.
