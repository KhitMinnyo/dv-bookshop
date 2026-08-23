#!/bin/sh
set -eu
rm -rf .venv __pycache__
printf '%s\n' 'Removed the WebSocket lab virtual environment and Python cache.'
