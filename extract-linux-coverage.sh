#!/bin/bash

# Extract Linux CPU coverage data from git history
# Output: CSV with Date and decimal coverage percentages (no %)
#
# Options:
#   --percent   Append % sign to coverage values in output

percent_suffix=""
if [ "$1" = "--percent" ]; then
    percent_suffix="%"
fi

echo "date,line_coverage,region_coverage,function_coverage,branch_coverage"

# Get all coverage report commits
git log --all --oneline --grep="multi-platform coverage" --format="%H" | while read -r commit; do
    # Extract date from commit message
    commit_msg=$(git log -1 --format="%s" "$commit")
    date=$(echo "$commit_msg" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}')
    slang_commit=$(echo "$commit_msg" | grep -oE '\([0-9a-f]{7,40}\)' | tr -d '()')

    if [ -n "$date" ]; then
        linux_file=""

        if [ -n "$slang_commit" ]; then
            candidate="reports/history/${date}-${slang_commit}/linux/coverage-summary.json"
            if git show "$commit:$candidate" >/dev/null 2>&1; then
                linux_file="$candidate"
            fi
        fi

        if [ -z "$linux_file" ] && git show "$commit:reports/latest/linux/coverage-summary.json" >/dev/null 2>&1; then
            linux_file="reports/latest/linux/coverage-summary.json"
        fi

        if [ -z "$linux_file" ]; then
            linux_file=$(git ls-tree -r "$commit" --name-only \
                | grep "reports/.*linux/coverage-summary.json" \
                | sort \
                | tail -1)
        fi

        if [ -n "$linux_file" ]; then
            # Extract the JSON content
            if json=$(git show "$commit:$linux_file" 2>/dev/null); then
                # Parse coverage data using grep and strip trailing %
                line_cov=$(echo "$json" | grep -o '"line_coverage": "[^"]*"' | cut -d'"' -f4 | tr -d '%')
                region_cov=$(echo "$json" | grep -o '"region_coverage": "[^"]*"' | cut -d'"' -f4 | tr -d '%')
                function_cov=$(echo "$json" | grep -o '"function_coverage": "[^"]*"' | cut -d'"' -f4 | tr -d '%')
                branch_cov=$(echo "$json" | grep -o '"branch_coverage": "[^"]*"' | cut -d'"' -f4 | tr -d '%')

                if [ -n "$line_cov" ] && [ -n "$region_cov" ] && [ -n "$function_cov" ] && [ -n "$branch_cov" ]; then
                    echo "$date,$line_cov$percent_suffix,$region_cov$percent_suffix,$function_cov$percent_suffix,$branch_cov$percent_suffix"
                fi
            fi
        fi
    fi
done | sort -t',' -k1
