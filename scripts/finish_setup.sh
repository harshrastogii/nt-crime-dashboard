#!/usr/bin/env bash
#
# finish_setup.sh — completes the two steps that need your authorisation.
#
#   ./scripts/finish_setup.sh
#
# What it does, in order:
#   1. Grants the GitHub 'workflow' scope and pushes the Actions workflow.
#   2. Publishes the Kaggle dataset for the first time.
#   3. Stores your Kaggle credentials as GitHub secrets so the workflow can
#      publish future updates by itself.
#
# Your Kaggle key is read from ~/.kaggle/kaggle.json and piped straight into
# `gh secret set`. It is never printed, never written into the repository, and
# never passed on a command line.

set -euo pipefail
cd "$(dirname "$0")/.."

BOLD=$'\033[1m'; DIM=$'\033[2m'; OK=$'\033[32m'; WARN=$'\033[33m'; ERR=$'\033[31m'; OFF=$'\033[0m'
step() { echo; echo "${BOLD}== $* ==${OFF}"; }
ok()   { echo "${OK}✓${OFF} $*"; }
warn() { echo "${WARN}!${OFF} $*"; }
die()  { echo "${ERR}✗ $*${OFF}"; exit 1; }

# ---------------------------------------------------------------- identity --
step "Verifying commit identity"
NAME="$(git config user.name || true)"
EMAIL="$(git config user.email || true)"
[ "$NAME" = "harshrastogii" ] || die "git user.name is '$NAME', expected harshrastogii"
[ "$EMAIL" = "harshrastogi636@gmail.com" ] || die "git user.email is '$EMAIL'"
ok "$NAME <$EMAIL>"

# ------------------------------------------------------------ github scope --
step "Step 1 of 3 — GitHub workflow scope"
if gh auth status 2>&1 | grep -q "'workflow'"; then
  ok "workflow scope already granted"
else
  echo "Granting the 'workflow' scope. A browser window will open and you'll"
  echo "be asked to paste a one-time code shown below."
  gh auth refresh -h github.com -s workflow
  ok "scope granted"
fi

if [ -n "$(git log origin/main..HEAD --oneline)" ]; then
  git push origin main
  ok "workflow pushed to GitHub"
else
  ok "nothing left to push"
fi

# ------------------------------------------------------------------ kaggle --
step "Step 2 of 3 — Publishing to Kaggle"
CREDS="$HOME/.kaggle/kaggle.json"
if [ ! -f "$CREDS" ]; then
  cat <<EOF
${WARN}No Kaggle credentials found at ~/.kaggle/kaggle.json${OFF}

  1. Open  https://www.kaggle.com/settings/account
  2. Under ${BOLD}API${OFF}, click ${BOLD}Create New Token${OFF} (downloads kaggle.json)
  3. Run:
       mkdir -p ~/.kaggle && mv ~/Downloads/kaggle.json ~/.kaggle/ && chmod 600 ~/.kaggle/kaggle.json
  4. Re-run this script.

Do not paste the file's contents into a chat window.
EOF
  exit 1
fi
chmod 600 "$CREDS" 2>/dev/null || true
ok "credentials found (contents not displayed)"

python3 -m pip install --quiet --upgrade kaggle >/dev/null 2>&1 || true
python3 -m pipeline.publish_kaggle --message "Initial publication: 2008-2026, 222 months"

# ----------------------------------------------------------- github secrets --
step "Step 3 of 3 — GitHub secrets for automatic updates"
KU="$(python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.kaggle/kaggle.json')))['username'])")"
printf '%s' "$KU" | gh secret set KAGGLE_USERNAME --repo harshrastogii/nt-crime-dashboard
python3 -c "import json,os,sys;sys.stdout.write(json.load(open(os.path.expanduser('~/.kaggle/kaggle.json')))['key'])" \
  | gh secret set KAGGLE_KEY --repo harshrastogii/nt-crime-dashboard
ok "KAGGLE_USERNAME and KAGGLE_KEY stored as repository secrets"
echo "${DIM}  (values were piped directly to gh; never printed or logged)${OFF}"

step "Done"
echo "Kaggle dataset : https://www.kaggle.com/datasets/${KU}/northern-territory-crime-statistics-2008-2026"
echo "GitHub repo    : https://github.com/harshrastogii/nt-crime-dashboard"
echo "Automation     : daily check, next run within 24h. Trigger manually with:"
echo "                 gh workflow run update-data.yml --repo harshrastogii/nt-crime-dashboard"
