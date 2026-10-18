#!/usr/bin/env bash
# Runs every check the plan requires before a sample may live in a skill.
set -euo pipefail
cd "$(dirname "$0")"
dotnet build -warnaserror
dotnet format --verify-no-changes
# Docker-backed tests need a running container runtime: run them with
#   dotnet test -- --filter-trait "Category=Docker"
dotnet test -- --filter-not-trait "Category=Docker"
python3 check-samples.py
