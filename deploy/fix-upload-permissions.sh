#!/bin/bash
# Fix uploads directory permissions for Instagram media serving
# Run from project root: ./deploy/fix-upload-permissions.sh
# Or: bash deploy/fix-upload-permissions.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
UPLOADS_DIR="$PROJECT_ROOT/uploads"

echo "Fixing permissions for $UPLOADS_DIR"

if [ ! -d "$UPLOADS_DIR" ]; then
    mkdir -p "$UPLOADS_DIR"
    echo "Created uploads directory"
fi

# Directories: 755 (rwxr-xr-x)
find "$UPLOADS_DIR" -type d -exec chmod 755 {} \;

# Files: 644 (rw-r--r--)
find "$UPLOADS_DIR" -type f -exec chmod 644 {} \;

echo "Done. Directories: 755, Files: 644"
