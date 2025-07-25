#!/bin/bash
for fname in $(git diff --diff-filter=AM --name-only HEAD~1 HEAD); do
    if [[ $fname == *.py ]]
    then
        echo "Checking $fname with python linters"
        isort  --settings-path src/python --profile black "$fname"
        pylint "$fname" --rcfile standarts/pylintrc
        pyink -l 200 "$fname"
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
