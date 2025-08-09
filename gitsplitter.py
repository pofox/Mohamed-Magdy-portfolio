import subprocess
import os
import argparse
import shlex

TRACKED_LARGE_FILES = "tracked_large_files.txt"
SIZE_LIMIT_MB_DEFAULT = 100

# -------------------------------
# Helper functions
# -------------------------------

def run_cmd(cmd):
    """Run a shell command and return output."""
    print(f"[DEBUG] Running command: {cmd}")
    result = subprocess.run(shlex.split(cmd), capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[ERROR] Command failed: {cmd}\n{result.stderr}")
    return result.stdout.strip()

def ensure_gitignore_entry(entry):
    """Ensure a given entry exists in .gitignore."""
    if not os.path.exists(".gitignore"):
        open(".gitignore", "w").close()
    with open(".gitignore", "r+") as gi:
        lines = gi.read().splitlines()
        if entry not in lines:
            gi.write(entry + "\n")
            print(f"[DEBUG] Added '{entry}' to .gitignore")
        else:
            print(f"[DEBUG] '{entry}' already exists in .gitignore")

def file_changed_in_git(file_path):
    """Check if a file has changes in git."""
    return subprocess.run(["git", "diff", "--quiet", "--", file_path]).returncode != 0

def commit_and_push(files, message):
    """Commit and push files if they have changes."""
    if not files:
        print(f"[DEBUG] No files specified for commit: {message}")
        return
    changed_files = [f for f in files if file_changed_in_git(f)]
    if not changed_files:
        print(f"[DEBUG] Skipping commit: No changes for {message}")
        return
    run_cmd(f"git add {' '.join(shlex.quote(f) for f in changed_files)}")
    run_cmd(f'git commit -m "{message}"')
    run_cmd("git push")
    print(f"[DEBUG] Committed and pushed: {', '.join(changed_files)}")

def get_changed_and_new_files():
    """Get changed and new files from git."""
    status_output = run_cmd("git status --porcelain")
    files = []
    for line in status_output.splitlines():
        status = line[:2]
        file_path = line[3:]
        if status in ("A ", "M ", "??"):
            if os.path.isdir(file_path):
                for root, _, filenames in os.walk(file_path):
                    for fname in filenames:
                        files.append(os.path.join(root, fname))
            else:
                files.append(file_path)
    return files

def get_deleted_files():
    """Get deleted files from git."""
    status_output = run_cmd("git status --porcelain")
    return [line[3:] for line in status_output.splitlines() if line[:2] == " D"]

def file_size_mb(path):
    """Return file size in MB."""
    if os.path.isfile(path):
        return os.path.getsize(path) / (1024 * 1024)
    return 0

def load_tracked_large_files():
    """Load tracked large files list."""
    if not os.path.exists(TRACKED_LARGE_FILES):
        return set()
    with open(TRACKED_LARGE_FILES, "r") as f:
        return set(line.strip() for line in f if line.strip())

def save_tracked_large_files(files):
    """Save tracked large files list."""
    with open(TRACKED_LARGE_FILES, "w") as f:
        for file in sorted(files):
            f.write(file + "\n")

def remove_from_gitignore(file_path):
    """Remove a file from .gitignore."""
    if not os.path.exists(".gitignore"):
        return
    with open(".gitignore", "r") as f:
        lines = f.readlines()
    new_lines = [line for line in lines if line.strip() != file_path]
    with open(".gitignore", "w") as f:
        f.writelines(new_lines)

def compress_file(file_path, part_size="50m"):
    """Compress file into same directory as source with best possible compression."""
    dir_name = os.path.dirname(file_path)
    base_name = os.path.basename(file_path)
    output_path = os.path.join(dir_name, base_name + ".7z")
    cmd = f'7z a -mx=9 -m0=lzma2 -md=512m -v{part_size} "{output_path}" "{file_path}"'
    run_cmd(cmd)

def delete_compressed_files(file_path):
    """Delete compressed parts related to a file."""
    dir_name = os.path.dirname(file_path)
    base_name = os.path.basename(file_path)
    for f in os.listdir(dir_name or "."):
        if f.startswith(base_name + ".7z"):
            os.remove(os.path.join(dir_name, f))
            print(f"[DEBUG] Deleted compressed file: {f}")

def get_changed_files_from_last_commit():
    """Get list of files changed in the latest commit."""
    output = run_cmd("git diff --name-only HEAD~1 HEAD")
    return output.splitlines()

# -------------------------------
# Main
# -------------------------------

def main():
    parser = argparse.ArgumentParser(description="Git Large File Splitter Tool")
    parser.add_argument("--size-limit", type=int, default=SIZE_LIMIT_MB_DEFAULT,
                        help="Size limit in MB for tracking large files")
    parser.add_argument("mode", choices=["push", "pull"], help="Mode to run: push or pull")
    args = parser.parse_args()

    tracked_files = load_tracked_large_files()

    if args.mode == "push":
        ensure_gitignore_entry("*.old")

        changed_files = get_changed_and_new_files()
        deleted_files = get_deleted_files()

        # Handle deleted files
        for f in deleted_files:
            if f in tracked_files:
                tracked_files.remove(f)
                remove_from_gitignore(f)
                delete_compressed_files(f)
                print(f"[DEBUG] Removed deleted file from tracking: {f}")

        # Detect large files
        large_files = set()
        for f in changed_files:
            if file_size_mb(f) >= args.size_limit:
                large_files.add(f)
        for f in tracked_files:
            if os.path.isfile(f) and file_size_mb(f) >= args.size_limit:
                large_files.add(f)

        # Compress and track
        for f in large_files:
            print(f"[DEBUG] Compressing large file: {f}")
            compress_file(f)
            tracked_files.add(f)
            ensure_gitignore_entry(f)

        save_tracked_large_files(tracked_files)

        # Commit tracked files + gitignore first
        commit_and_push([TRACKED_LARGE_FILES, ".gitignore"], "Update tracked_large_files and gitignore")

        # Commit each compressed file separately
        for f in large_files:
            dir_name = os.path.dirname(f)
            base_name = os.path.basename(f)
            part1_path = os.path.join(dir_name, base_name + ".7z.001")
            if os.path.exists(part1_path) and file_changed_in_git(part1_path):
                parts = [os.path.join(dir_name, p) for p in os.listdir(dir_name or ".") if p.startswith(base_name + ".7z")]
                commit_and_push(parts, f"Add compressed: {f}")
            else:
                print(f"[DEBUG] Skipping commit for {f}: No change in compressed parts")

    elif args.mode == "pull":
        print("[DEBUG] Pulling latest changes from git...")
        run_cmd("git pull")

        changed_in_commit = get_changed_files_from_last_commit()

        # Filter for changed .7z.001 files that match tracked large files
        changed_large_files = []
        for f in tracked_files:
            archive_part = os.path.join(os.path.dirname(f), os.path.basename(f) + ".7z.001")
            if archive_part in changed_in_commit:
                changed_large_files.append(f)

        print(f"[DEBUG] Changed large files to update: {changed_large_files}")

        # Rename and extract only changed large files
        for f in changed_large_files:
            if os.path.exists(f):
                os.rename(f, f + ".old")
                print(f"[DEBUG] Renamed existing file to {f}.old")
            cmd = f'7z x "{os.path.join(os.path.dirname(f), os.path.basename(f) + ".7z.001")}" -o"{os.path.dirname(f) or "."}" -y'
            run_cmd(cmd)

if __name__ == "__main__":
    main()
