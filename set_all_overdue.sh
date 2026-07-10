#!/bin/bash

for file in ./generated/*/last_executed_on.kf; do
    if [ -f "$file" ]; then
        echo "0" > "$file"
        echo "Updated: $file"
    fi
done

echo "All matching files have been reset to 0."
