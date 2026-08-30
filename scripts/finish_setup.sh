#!/usr/bin/env bash
#
# finish_setup.sh — completes the one step that still needs your authorisation.
#
#   ./scripts/finish_setup.sh
#
# Kaggle is already published and its API token is already stored as the
# KAGGLE_API_TOKEN repository secret. All that remains is granting the GitHub
# 'workflow' scope so the Actions workflow file can be pushed; GitHub rejects
# workflow files from tokens without it.

set -euo pipefail
cd "$(dirname "$0")/.."

BOLD=$'\033[1m'; OK=$'\033[32m'; ERR=$'\033[31m'; OFF=$'\033[0m'
ok()  { echo "${OK}✓${OFF} $*"; }
die() { echo "${ERR}✗ $*${OFF}"; exit 1; }

echo "${BOLD}== Verifying commit identity ==${OFF}"
NAME="$(git config user.name || true)"; EMAIL="$(git config user.email || true)"
[ "$NAME" = "harshrastogii" ] || die "git user.name is '$NAME', expected harshrastogii"
[ "$EMAIL" = "harshrastogi636@gmail.com" ] || die "git user.email is '$EMAIL'"
ok "$NAME <$EMAIL>"

echo
echo "${BOLD}== Granting the GitHub 'workflow' scope ==${OFF}"
if gh auth status 2>&1 | grep -q "'workflow'"; then
  ok "already granted"
else
  echo "A browser window will open; paste the one-time code shown below."
  gh auth refresh -h github.com -s workflow
  ok "granted"
fi

echo
echo "${BOLD}== Pushing ==${OFF}"
if [ -n "$(git log origin/main..HEAD --oneline)" ]; then
  git push origin main
  ok "workflow pushed - automation is now live"
else
  ok "nothing left to push"
fi

echo
echo "Kaggle : https://www.kaggle.com/datasets/harshrastogiii/northern-territory-crime-statistics-2008-2026"
echo "GitHub : https://github.com/harshrastogii/nt-crime-dashboard"
echo "Trigger a run now:"
echo "  gh workflow run update-data.yml --repo harshrastogii/nt-crime-dashboard"
