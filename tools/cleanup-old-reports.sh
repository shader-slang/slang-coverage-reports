#!/bin/bash
set -euo pipefail

# Cleanup script to maintain only recent coverage reports
# Keeps: Last 1 day of reports + monthly snapshots
#
# Each daily snapshot holds full per-file HTML coverage for three platforms
# plus the merged/new-renderer views (~1.7GB uncompressed). Keeping more than
# one day pushes the deployed site over GitHub Pages' 1GB published-site cap
# (see shader-slang/slang-coverage-reports Pages deploy failures starting
# 2026-08-17), so retention is intentionally tight.

HISTORY_DIR="reports/history"
DAYS_TO_KEEP=1

if [ ! -d "$HISTORY_DIR" ]; then
    echo "History directory not found: $HISTORY_DIR"
    exit 0
fi

echo "Cleaning up old coverage reports..."
echo "Retention policy: Keep last ${DAYS_TO_KEEP} days + monthly snapshots"

# Get cutoff date (7 days ago)
CUTOFF_DATE=$(date -u -d "${DAYS_TO_KEEP} days ago" +%Y-%m-%d 2>/dev/null || date -u -v-${DAYS_TO_KEEP}d +%Y-%m-%d)
echo "Cutoff date: ${CUTOFF_DATE}"

# Track what we're keeping/removing
KEPT_COUNT=0
REMOVED_COUNT=0
REMOVED_SIZE=0

# Process each report directory
for report_dir in "${HISTORY_DIR}"/*; do
    if [ ! -d "$report_dir" ]; then
        continue
    fi

    report_name=$(basename "$report_dir")

    # Extract date from directory name (format: YYYY-MM-DD-commit)
    report_date=$(echo "$report_name" | grep -oE '^[0-9]{4}-[0-9]{2}-[0-9]{2}' || echo "")

    if [ -z "$report_date" ]; then
        echo "Warning: Could not parse date from $report_name, skipping"
        continue
    fi

    # Check if it's a monthly snapshot (1st of the month)
    report_day=$(echo "$report_date" | cut -d'-' -f3)
    is_monthly_snapshot=false
    if [ "$report_day" = "01" ]; then
        is_monthly_snapshot=true
    fi

    # Keep if:
    # 1. It's within the retention period, OR
    # 2. It's a monthly snapshot
    if [[ "$report_date" > "$CUTOFF_DATE" ]] || [[ "$report_date" == "$CUTOFF_DATE" ]] || [ "$is_monthly_snapshot" = true ]; then
        if [ "$is_monthly_snapshot" = true ]; then
            echo "Keeping (monthly snapshot): $report_name"
        else
            echo "Keeping (recent): $report_name"
        fi
        KEPT_COUNT=$((KEPT_COUNT + 1))
    else
        # Calculate size before removal
        size=$(du -sm "$report_dir" 2>/dev/null | cut -f1 || echo "0")
        REMOVED_SIZE=$((REMOVED_SIZE + size))

        echo "Removing (old): $report_name (${size}MB)"
        rm -rf "$report_dir"
        REMOVED_COUNT=$((REMOVED_COUNT + 1))
    fi
done

echo ""
echo "Cleanup summary:"
echo "  Kept: ${KEPT_COUNT} reports"
echo "  Removed: ${REMOVED_COUNT} reports (~${REMOVED_SIZE}MB)"

# Regenerate indexes after cleanup
if [ ${REMOVED_COUNT} -gt 0 ]; then
    echo ""
    echo "Regenerating indexes..."

    # Use relative paths from repo root
    if [ -f "tools/coverage/generate-history-index.sh" ]; then
        bash tools/coverage/generate-history-index.sh "${HISTORY_DIR}"
    fi

    if [ -f "tools/coverage/generate-landing-page.sh" ]; then
        bash tools/coverage/generate-landing-page.sh reports index.html
    fi

    if [ -f "tools/coverage/generate-data-export.sh" ]; then
        bash tools/coverage/generate-data-export.sh "${HISTORY_DIR}"
    fi

    echo "Indexes regenerated"
fi

echo ""
echo "Cleanup complete!"
