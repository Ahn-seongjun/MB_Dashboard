#!/usr/bin/env bash

# data 폴더의 CSV 변경사항만 커밋하고 현재 브랜치에 푸시합니다.

set -e

cd "$(dirname "$0")"
git rev-parse --is-inside-work-tree >/dev/null

BRANCH="$(git branch --show-current)"
if [ -z "$BRANCH" ]; then
    echo "현재 Git 브랜치를 확인할 수 없습니다."
    exit 1
fi

echo "CSV 변경사항 확인 중: $BRANCH"
git add -A -- ':(glob)data/**/*.csv'

if git diff --cached --quiet -- ':(glob)data/**/*.csv'; then
    echo "업로드할 CSV 변경사항이 없습니다."
    exit 0
fi

git commit -m "$(date '+%Y-%m-%d %H:%M:%S') CSV 데이터 업데이트" -- ':(glob)data/**/*.csv'
git push -u origin "$BRANCH"

echo "CSV 데이터 업데이트 완료: origin/$BRANCH"
