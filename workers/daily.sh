#!/bin/zsh
# Wrapper for launchd: absolute paths, no login PATH.
cd /Users/geraldofori/Desktop/job-hunt
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
/opt/homebrew/bin/npm run daily >> logs/daily.log 2>&1
