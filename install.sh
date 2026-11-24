#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/claude"
target_dir="$HOME/.claude"
backup_dir="$HOME/.claude-config-backup-$(date +%Y%m%d%H%M%S)"

mkdir -p "$target_dir"

# Symlink one file (or whole dir, when dst doesn't exist yet — stow-style folding).
# Idempotent: re-running leaves already-correct symlinks untouched.
link_file() {
  local src="$1" dst="$2"

  if [ -L "$dst" ]; then
    if [ "$(readlink "$dst")" = "$src" ]; then
      return
    fi
    rm "$dst"
  elif [ -e "$dst" ]; then
    mkdir -p "$backup_dir/$(dirname "${dst#"$target_dir"/}")"
    mv "$dst" "$backup_dir/${dst#"$target_dir"/}"
  fi

  mkdir -p "$(dirname "$dst")"
  ln -s "$src" "$dst"
  echo "linked: $dst -> $src"
}

# Merge src_dir into dst_dir per-entry, recursing into real (non-symlink)
# directories on the target so local-only files/dirs are left in place.
link_tree() {
  local src_dir="$1" dst_dir="$2"
  [ -d "$src_dir" ] || return 0
  mkdir -p "$dst_dir"

  local entry name
  for entry in "$src_dir"/*; do
    name="$(basename "$entry")"
    if [ -d "$entry" ] && [ ! -L "$dst_dir/$name" ] && [ -d "$dst_dir/$name" ]; then
      link_tree "$entry" "$dst_dir/$name"
    else
      link_file "$entry" "$dst_dir/$name"
    fi
  done
}

link_file "$repo_dir/CLAUDE.md" "$target_dir/CLAUDE.md"
link_file "$repo_dir/settings.json" "$target_dir/settings.json"
link_file "$repo_dir/statusline.sh" "$target_dir/statusline.sh"
link_tree "$repo_dir/hooks" "$target_dir/hooks"
link_tree "$repo_dir/skills" "$target_dir/skills"
link_tree "$repo_dir/agents" "$target_dir/agents"

if [ -d "$backup_dir" ]; then
  echo "existing files backed up to: $backup_dir"
fi
