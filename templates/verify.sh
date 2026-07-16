#!/bin/bash

# --- Configuration (Populated via Python F-String) ---
SRC="{source_dir}"
DST="{remote_dir}"
EXCLUDE_FILE="{exclude_file}"

# Track if we encounter any critical issues
EXIT_STATUS=0

echo "=================================================="
echo "          BACKUP VERIFICATION REPORT             "
echo "=================================================="
echo "Source:      $SRC"
echo "Destination: $DST"
echo "Excludes:    $EXCLUDE_FILE"
echo "--------------------------------------------------"

# --- 1. Accessibility Checks ---
if [ ! -d "$SRC" ]; then
    echo "[CRITICAL] Source directory does not exist or is inaccessible!"
    exit 1
fi

if [ ! -d "$DST" ]; then
    echo "[CRITICAL] Remote/Destination directory does not exist or is unmounted!"
    exit 1
fi

# --- 2. Size & Count Check ---
echo -e "\n[1/5] Calculating Sizes and Counts..."

src_size=$(du -sh "$SRC" 2>/dev/null | cut -f1)
src_files=$(find "$SRC" -type f 2>/dev/null | wc -l)
src_dirs=$(find "$SRC" -type d 2>/dev/null | wc -l)

dst_size=$(du -sh "$DST" 2>/dev/null | cut -f1)
dst_files=$(find "$DST" -type f 2>/dev/null | wc -l)
dst_dirs=$(find "$DST" -type d 2>/dev/null | wc -l)

echo "  - Source Size: $src_size | Files: $src_files | Dirs: $src_dirs"
echo "  - Remote Size: $dst_size | Files: $dst_files | Dirs: $dst_dirs"

# --- 3. Missing Files (Excluding 'excluded.txt' matches) ---
echo -e "\n[2/5] Checking for Missing/Modified Files (Respecting Excludes)..."
# -n runs a dry-run; we filter out directory structures and rsync's header/footer output
missing_files=$(rsync -rvn --exclude-from="$EXCLUDE_FILE" "$SRC/" "$DST/" 2>/dev/null | \
                grep -v -E '^sending incremental file list|^$|bytes/sec|^total size' | \
                grep -v '/$')

if [ -z "$missing_files" ]; then
    echo "  -> PASS: All non-excluded files are safely backed up."
else
    echo "  -> FAIL: The following files are missing or modified in the remote directory:"
    echo "$missing_files" | sed 's/^/     /'
    EXIT_STATUS=1
fi

# --- 4. Excluded Files Missing in Remote (Separate Category) ---
echo -e "\n[3/5] Checking for Excluded Files Missing in Remote..."
if [ -f "$EXCLUDE_FILE" ]; then
    # We invert the logic: include *only* what is in the exclude file, and exclude everything else.
    # This shows us exactly which excluded files exist locally but are not on the remote.
    excluded_missing=$(rsync -rvn --include-from="$EXCLUDE_FILE" --exclude='*' "$SRC/" "$DST/" 2>/dev/null | \
                       grep -v -E '^sending incremental file list|^$|bytes/sec|^total size' | \
                       grep -v '/$')
    
    if [ -z "$excluded_missing" ]; then
        echo "  -> Note: No excluded files are missing from the remote."
    else
        echo "  -> Info: The following excluded files exist in Source but NOT Remote (as expected):"
        echo "$excluded_missing" | sed 's/^/     /'
    fi
else
    echo "  -> Note: Exclude file not found. Skipping this step."
fi

# --- 5. Orphan Files Check (Exist in Remote, but NOT in Source) ---
echo -e "\n[4/5] Checking for Orphan Files (In Remote, NOT in Source)..."
# Using rsync's delete dry-run tells us what would be deleted from the remote to match the source.
orphans=$(rsync -rvn --delete --exclude-from="$EXCLUDE_FILE" "$SRC/" "$DST/" 2>/dev/null | \
          grep "^deleting " | sed 's/^deleting //')

if [ -z "$orphans" ]; then
    echo "  -> PASS: No orphaned files found in remote."
else
    echo "  -> Info: The following files exist in Remote but not in Source (or are excluded):"
    echo "$orphans" | sed 's/^/     /'
fi

# --- 6. Silent Failure & Integrity Checks ---
echo -e "\n[5/5] Performing Extra Integrity Checks..."

# A) Empty (0-Byte) Files Check
# Often, interrupted transfers write the file headers but fail on the content, leaving empty files.
empty_files=$(find "$DST" -type f -size 0 2>/dev/null | wc -l)
if [ "$empty_files" -gt 0 ]; then
    echo "  -> WARNING: Found $empty_files empty (0-byte) files in the remote directory!"
    # We don't fail the exit status just for this, but it raises a flag.
else
    echo "  -> PASS: No empty files detected."
fi

# B) Write Permissions Check
# Verifies the remote location hasn't locked up or gone read-only.
if touch "$DST/.backup_write_test" 2>/dev/null; then
    rm "$DST/.backup_write_test"
    echo "  -> PASS: Remote directory remains writeable."
else
    echo "  -> FAIL: Remote directory is READ-ONLY or write-protected!"
    EXIT_STATUS=1
fi

echo -e "\n================================================--"
if [ $EXIT_STATUS -eq 0 ]; then
    echo "          VERIFICATION RESULT: SUCCESS          "
else
    echo "          VERIFICATION RESULT: FAILED           "
fi
echo "================================================--"

exit $EXIT_STATUS
