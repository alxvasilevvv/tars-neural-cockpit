#!/bin/bash
cd ~/Documents/Claude/Projects/Jarvis/jarvis
echo "Pushing claude/w307-design-refresh..."
echo "  6231b34 — W307 resolution addendum (5 OQs answered)"
echo "  145ee09 — W308 step-2 brief + audit + SYNC for 6231b34"
echo "  10b7102 — PUSH-W307-RESOLUTION.command (this helper)"
echo "  d5ade97 — gap-fill after W308 step 2+3 (marketing override + refreshed refs)"
echo ""
git push origin claude/w307-design-refresh
echo ""
echo "Done. Latest commits on branch:"
git log --oneline -8 claude/w307-design-refresh
echo ""
read -p "Press Enter to close..."
