#!/bin/bash

set -euo pipefail
set -x

main() {
	local source=$1
	local parent=$(dirname $source)
	find $source -type d | while read dir; do echo "$dir" | sed "s|${parent}/||g"; done | while read dir; do mkdir -p "$dir"; done
	find $source -type f | while read file; do echo "$file" | sed "s|${parent}/||g"; done | while read file; do touch "$file"; done
}

main $@

