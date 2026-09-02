#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/claude"
target_dir="$HOME/.claude"
backup_dir="$HOME/.claude-config-backup-$(date +%Y%m%d%H%M%S)"

mkdir -p "$target_dir"

link() {
  local src="$1" dst="$2"
  if [ -e "$dst" ] || [ -L "$dst" ]; then
    mkdir -p "$backup_dir/$(dirname "${dst#"$target_dir"/}")"
    mv "$dst" "$backup_dir/${dst#"$target_dir"/}"
  fi
  mkdir -p "$(dirname "$dst")"
  ln -s "$src" "$dst"
  echo "linked: $dst -> $src"
}

link "$repo_dir/CLAUDE.md" "$target_dir/CLAUDE.md"
link "$repo_dir/settings.json" "$target_dir/settings.json"
link "$repo_dir/statusline.sh" "$target_dir/statusline.sh"
link "$repo_dir/hooks" "$target_dir/hooks"
link "$repo_dir/skills" "$target_dir/skills"
link "$repo_dir/agents" "$target_dir/agents"

if [ -d "$backup_dir" ]; then
  echo "existing files backed up to: $backup_dir"
fi
