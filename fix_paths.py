import os

def get_project_root():
    """Returns project root folder (directory containing this file).

    Note: this file (`fix_paths.py`) lives in the project root, so returning
    the directory containing this file yields the project root. Previous
    implementation returned the parent of the project root which caused
    path resolution to point to the user's home directory by mistake.
    """
    return os.path.dirname(os.path.abspath(__file__))

def find_file_in_search_paths(filename):
    """
    Search for a file in multiple common locations:
    1. Home directory (~/)
    2. Project root directory
    3. Current working directory
    Returns the first path where the file exists, or None if not found.
    """
    search_paths = [
        os.path.join(os.path.expanduser("~"), filename),  # Home directory - properly join paths
        os.path.join(get_project_root(), filename),        # Project root
        os.path.join(os.getcwd(), filename),               # Current working directory
    ]
    
    for path in search_paths:
        # Normalize path separators for consistency
        path = os.path.normpath(path)
        if os.path.exists(path):
            return path
    
    return None

def get_absolute_path(filename):
    """
    Convert relative path to absolute path.
    Searches in multiple locations for maximum compatibility:
    1. Home directory (useful for extracted zips or running from anywhere)
    2. Project root directory
    3. Current working directory
    Falls back to project root if file not found.
    """
    # Special handling for data files and directories
    if filename in ['assigned_items.json', 'item_list.json', 'config.json', 'images', 'images/']:
        found = find_file_in_search_paths(filename)
        if found:
            return found
    
    # For paths like "images/SS1.png", try to find them in search paths
    if filename.startswith('images/'):
        found = find_file_in_search_paths(filename)
        if found:
            return found
    
    # Default: resolve relative to project root
    return os.path.join(get_project_root(), filename)