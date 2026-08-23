#!/bin/sh
set -eu
rm -rf node_modules package-lock.json npm-debug.log
printf '%s\n' 'Removed the prototype-pollution lab npm artifacts.'
