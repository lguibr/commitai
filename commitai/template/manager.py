import os
from typing import Optional

from commitai.git.core import get_repository_name
from commitai.types import TemplateType


def _get_template_path(template_type: TemplateType) -> str:
    """Returns the path for the given template type."""
    repo_path = get_repository_name()
    filename = (
        "commit_template.txt"
        if template_type == TemplateType.COMMIT
        else "pr_template.md"
    )
    return os.path.join(repo_path, ".git", filename)


def get_template(template_type: TemplateType) -> Optional[str]:
    """Retrieves a template by type ('commit' or 'pr')."""
    template_path = _get_template_path(template_type)
    if os.path.exists(template_path):
        with open(template_path, "r") as f:
            return f.read()

    # Fallback to env variables
    if template_type == TemplateType.COMMIT:
        return os.getenv("TEMPLATE_COMMIT")
    elif template_type == TemplateType.PR:
        return os.getenv("TEMPLATE_PR")
    return None


def save_template(template_type: TemplateType, content: str) -> None:
    """Saves a template by type ('commit' or 'pr')."""
    template_path = _get_template_path(template_type)
    with open(template_path, "w") as f:
        f.write(content)


def delete_template(template_type: TemplateType) -> None:
    """Deletes a template by type ('commit' or 'pr')."""
    template_path = _get_template_path(template_type)
    if os.path.exists(template_path):
        os.remove(template_path)
