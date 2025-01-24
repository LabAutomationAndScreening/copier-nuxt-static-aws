#!/usr/bin/env sh
set -ex

# Check if a bucket name argument is provided
if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <bucket-name>"
  exit 1
fi

BUCKET_NAME="$1"

SCRIPT_DIR="$(dirname "$0")"
APP_PROJECT_DIR="$(realpath "$SCRIPT_DIR")"

(cd $APP_PROJECT_DIR && npm run generate)

aws s3 sync --delete "$APP_PROJECT_DIR"/.output/public/ "s3://$BUCKET_NAME"
