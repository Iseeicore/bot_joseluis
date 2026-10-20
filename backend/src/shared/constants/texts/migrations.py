from src.shared.enums.migration_problem import MigrationProblem

MIGRATION_PROBLEM_TEXTS = {
    MigrationProblem.MALFORMED_NAME: "El nombre de la migración no sigue el formato NNNN_nombre.sql: {file_name}",
    MigrationProblem.DUPLICATE_VERSION: "El número de la migración está repetido: {file_name}",
    MigrationProblem.VERSION_GAP: "Falta una migración anterior en la numeración: {file_name}",
    MigrationProblem.EXECUTION_FAILED: "No se pudo aplicar la migración: {file_name}",
}


def migration_error_text(problem: MigrationProblem, file_name: str) -> str:
    return MIGRATION_PROBLEM_TEXTS[problem].format(file_name=file_name)
