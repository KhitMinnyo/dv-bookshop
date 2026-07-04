#!/bin/bash
# Full lab reset — restore dv-bookshop to a pristine state.
# Re-seeds both databases, wipes uploaded files (keeps default.png),
# and resets all difficulty toggles to INSECURE.
# Safe to run while the app is stopped (recommended).
set -e
cd "$(dirname "$0")"

# Use the project venv if it exists, otherwise system python.
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

python3 -c "from app import full_lab_reset; s = full_lab_reset(); print('Reset OK:', s)"
echo "✅ Lab reset complete. Start the app with ./run.sh"
