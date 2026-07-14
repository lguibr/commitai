from enum import Enum


class TemplateType(str, Enum):
    COMMIT = "commit"
    PR = "pr"
