#!/bin/sh
for fname in `git diff --name-only HEAD HEAD~1`; do
    black $fname;
    isort $fname;
    pylint $fname --rcfile standarts/pylintrc
done
