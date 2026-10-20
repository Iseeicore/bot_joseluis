from src.shared.constants.texts.migrations import migration_error_text
from src.shared.enums.migration_problem import MigrationProblem


class MigrationError(Exception):
    def __init__(self, problem: MigrationProblem, file_name: str) -> None:
        super().__init__(migration_error_text(problem, file_name))
        self.problem = problem
        self.file_name = file_name
