#!/usr/bin/env bash

# .gitignore에 포함되지 않은 대시보드 전체 변경사항을 커밋하고 현재 브랜치에 푸시합니다.

set -e

cd "$(dirname "$0")"
git rev-parse --is-inside-work-tree >/dev/null

BRANCH="$(git branch --show-current)"
if [ -z "$BRANCH" ]; then
    echo "현재 Git 브랜치를 확인할 수 없습니다."
    exit 1
fi

echo "대시보드 전체 변경사항 확인 중: $BRANCH"
git add -A

if git diff --cached --quiet; then
    echo "업로드할 변경사항이 없습니다."
    exit 0
fi

git commit -m "$(date '+%Y-%m-%d %H:%M:%S') 대시보드 업데이트"
git push -u origin "$BRANCH"

echo "대시보드 전체 업데이트 완료: origin/$BRANCH"
