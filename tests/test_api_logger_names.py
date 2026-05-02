"""Logger namespace regression tests for extracted API modules."""

from __future__ import annotations


def test_branch_api_logger_uses_module_namespace() -> None:
    from workflow.api import branches

    assert branches.logger.name == "workflow.api.branches"


def test_branch_api_uses_workflow_db_helper_name() -> None:
    from workflow.api import branches

    assert hasattr(branches, "_ensure_workflow_db")
    assert not hasattr(branches, "_ensure_author_server_db")


def test_extensions_api_logger_uses_module_namespace() -> None:
    from workflow.api import extensions

    assert extensions.logger.name == "workflow.api.extensions"
