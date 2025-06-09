#!/bin/bash
for fname in $(git diff --name-only HEAD HEAD~1); do
    if [[ $fname == *.py ]]
    then
        echo "Checking $fname with python linters"
        isort --profile black "$fname"
        pylint "$fname" --rcfile standarts/pylintrc
        pyink -l 120 "$fname"
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
