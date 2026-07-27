import os
import shutil
import zipfile
import git
from typing import Optional, Tuple, List

REPOS_DIR = "/tmp/codelens_repos"

def prepare_repository(project_id: str, repo_url: Optional[str] = None, zip_path: Optional[str] = None) -> Tuple[str, List[str]]:
    os.makedirs(REPOS_DIR, exist_ok=True)
    target_dir = os.path.join(REPOS_DIR, project_id)

    if os.path.exists(target_dir):
        shutil.rmtree(target_dir)

    if repo_url:
        print(f"Cloning GitHub repository: {repo_url} into {target_dir}")
        git.Repo.clone_from(repo_url, target_dir)
    elif zip_path and os.path.exists(zip_path):
        print(f"Extracting ZIP archive: {zip_path} into {target_dir}")
        os.makedirs(target_dir, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(target_dir)
        
        # If extracted ZIP contains a single root wrapper directory, unwrap it
        items = os.listdir(target_dir)
        if len(items) == 1 and os.path.isdir(os.path.join(target_dir, items[0])):
            single_folder = os.path.join(target_dir, items[0])
            for f in os.listdir(single_folder):
                shutil.move(os.path.join(single_folder, f), target_dir)
            os.rmdir(single_folder)
    else:
        raise ValueError("Either valid repo_url or zip_path must be provided")

    detected_languages = detect_languages(target_dir)
    return target_dir, detected_languages

def detect_languages(repo_dir: str) -> List[str]:
    ext_map = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".java": "java",
    }
    found_langs = set()

    for root, dirs, files in os.walk(repo_dir):
        # Skip node_modules, venv, git, build dirs
        dirs[:] = [d for d in dirs if d not in [".git", "node_modules", ".venv", "__pycache__", "dist", "build", "target"]]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in ext_map:
                found_langs.add(ext_map[ext])

    return list(found_langs)
