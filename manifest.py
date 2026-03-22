import os
import hashlib
import json

def get_file_hash(filepath: str) -> str:
    """
    Generates an MD5 hash of a file's content.
    """
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

def check_for_changes(directory: str, manifest_path: str = "manifest.json"):
    """
    Compares the current state of a directory against a saved manifest.
    """
    # 1. Get current state
    current_state = {}
    for filename in os.listdir(directory):
        if filename.endswith(".md"):
            path = os.path.join(directory, filename)
            current_state[filename] = get_file_hash(path)

    # 2. Load previous state
    if not os.path.exists(manifest_path):
        print("No previous state found. Saving current state...")
        with open(manifest_path, "w") as f:
            json.dump(current_state, f)
        return

    with open(manifest_path, "r") as f:
        previous_state = json.load(f)

    # 3. Compare
    added = [f for f in current_state if f not in previous_state]
    removed = [f for f in previous_state if f not in current_state]
    modified = [f for f in current_state if f in previous_state and current_state[f] != previous_state[f]]

    # 4. Report
    if not (added or removed or modified):
        print("No changes detected.")
    else:
        if added: print(f"Added: {added}")
        if removed: print(f"Removed: {removed}")
        if modified: print(f"Modified: {modified}")

    # 5. Update manifest for next run
    with open(manifest_path, "w") as f:
        json.dump(current_state, f)
