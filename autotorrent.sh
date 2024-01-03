#!/bin/bash
cd "$( dirname "${BASH_SOURCE[0]}" )"

echo "$@" > arg.txt

pipenv run python -m autotorrent "$@"