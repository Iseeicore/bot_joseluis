import re

MIGRATION_FILE_PATTERN = re.compile(r"(?P<version>\d{4})_[a-z0-9]+(?:_[a-z0-9]+)*\.sql")
