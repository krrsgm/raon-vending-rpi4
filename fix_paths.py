import os

def get_project_root():
    """Returns project root folder."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_absolute_path(filename):
    """Convert relative path to absolute path from project root."""
    return os.path.join(get_project_root(), filename)