#!/bin/bash
cd ~/Documents/Claude/Projects/Jarvis/jarvis
echo "Pushing cursor/w309-cockpit-functional-restore..."
echo "  29e9cd9 — W309 functional restore brief (mic+WS+chat+TTS MVP)"
echo ""
echo "This brief is GATED on operator OK before Cursor starts step 1."
echo "Read it first: docs/handoff/W309_FUNCTIONAL_RESTORE_BRIEF.md"
echo ""
git push -u origin cursor/w309-cockpit-functional-restore
echo ""
echo "Done. Latest commit on branch:"
git log --oneline -3 cursor/w309-cockpit-functional-restore
echo ""
read -p "Press Enter to close..."
