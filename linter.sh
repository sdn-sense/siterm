#!/bin/bash
for fname in $(git diff --name-only HEAD HEAD~1); do
    if [[ $fname == *.py ]]
    then
        echo "Checking $fname with python linters"
        black "$fname"
        isort "$fname"
        pylint "$fname" --rcfile standarts/pylintrc
    fi
    if [[ $fname == *.yaml || $fname == *.yml ]]
    then
        echo "Checking $fname with yaml linters"
        yamllint "$fname"
    fi
    if [[ $fname == *.sh ]]
    then
        echo "Checking $fname with bash linter"
        bashlint "$fname"
    fi
done
