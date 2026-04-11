"""Restricted environment that limits file access to an allowlist."""

import os
import re
from pathlib import Path
from typing import Any

from gemmacode.environments.local import LocalEnvironment


class RestrictedEnvironment:
    """Environment that restricts file access to an allowlist.

    This wrapper around LocalEnvironment intercepts commands and blocks access to files
    not on the allowlist. Useful for sandboxing task execution and preventing models from
    exploring the entire repository.
    """

    def __init__(self, allowed_files: list[str], base_env: LocalEnvironment | None = None):
        """Initialize the restricted environment.

        Args:
            allowed_files: List of file paths that are allowed to be read/written.
            base_env: Base environment to delegate to (defaults to LocalEnvironment).
        """
        self.allowed_files = allowed_files
        self.base_env = base_env or LocalEnvironment()
        self.config = self.base_env.config

    def execute(self, action: dict, cwd: str = "", **kwargs) -> dict[str, Any]:
        """Execute a command, checking file access restrictions.

        Args:
            action: Action dict with "command" key containing the shell command.
            cwd: Current working directory (passed through to base_env).
            **kwargs: Additional kwargs passed to base_env.execute().

        Returns:
            Result dict from base_env.execute() if command is allowed,
            or error dict with returncode != 0 if command is blocked.
        """
        command = action.get("command", "")

        # Extract potential file paths from the command
        file_paths = self._extract_file_paths(command, cwd)

        # Check if all extracted paths are in the allowlist
        forbidden_files = self._find_forbidden_files(file_paths)

        if forbidden_files:
            return self._create_error_response(forbidden_files)

        # Command is allowed, delegate to base environment
        return self.base_env.execute(action, cwd, **kwargs)

    def _extract_file_paths(self, command: str, cwd: str) -> set[str]:
        """Extract potential file paths from a shell command.

        Args:
            command: The shell command to analyze.
            cwd: Current working directory for resolving relative paths.

        Returns:
            Set of extracted file paths.
        """
        file_paths = set()

        # Pattern 1: cat "file", cat 'file', cat file
        for prefix in ["cat", "open", "vim", "nano"]:
            # Match quoted paths
            pattern = rf'\b{prefix}\s+(["\']?)([^\s"\']+)\1'
            for match in re.finditer(pattern, command):
                path = match.group(2).strip()
                if path and not path.startswith("-") and not path.startswith("$"):
                    file_paths.add(self._resolve_path(path, cwd))

        # Pattern 2: < file (input redirection) - with or without quotes
        for match in re.finditer(r'<\s*(["\']?)([^\s"\']+)\1', command):
            path = match.group(2).strip()
            if path and not path.startswith("-"):
                file_paths.add(self._resolve_path(path, cwd))

        # Pattern 3: > file, >> file (output redirection) - with or without quotes
        for match in re.finditer(r'[>]{1,2}\s*(["\']?)([^\s"\']+)\1', command):
            path = match.group(2).strip()
            if path and not path.startswith("-"):
                file_paths.add(self._resolve_path(path, cwd))

        # Pattern 4: echo ... > file
        for match in re.finditer(r'echo\s+[^>]*>\s*(["\']?)([^\s"\']+)\1', command):
            path = match.group(2).strip()
            if path and not path.startswith("-"):
                file_paths.add(self._resolve_path(path, cwd))

        # Pattern 5: files with known extensions (src/foo.py, tests/bar.py, etc.)
        # Match paths that look like file paths (contain / or . and have known extensions)
        pattern = r"(?:^|\s)([a-zA-Z0-9_./\-]+\.[a-zA-Z0-9]+)(?:\s|$)"
        for match in re.finditer(pattern, command):
            path = match.group(1).strip()
            if path and "." in path and len(path) > 2:
                # Avoid matching things like "3.14" or "v2.1"
                resolved = self._resolve_path(path, cwd)
                # Only add if it looks like a real file path
                if "/" in path or path.startswith("./"):
                    file_paths.add(resolved)

        return file_paths

    def _resolve_path(self, path: str, cwd: str) -> str:
        """Resolve a path to absolute form.

        Args:
            path: The path to resolve (can be relative or absolute).
            cwd: Current working directory for resolving relative paths.

        Returns:
            Absolute path as string.
        """
        if path.startswith("/"):
            return path

        cwd = cwd or os.getcwd()
        absolute = str(Path(cwd) / path)
        try:
            return str(Path(absolute).resolve())
        except Exception:
            return absolute

    def _find_forbidden_files(self, file_paths: set[str]) -> list[str]:
        """Find which paths are not in the allowlist.

        Args:
            file_paths: Set of file paths to check.

        Returns:
            List of forbidden file paths.
        """
        forbidden = []

        for file_path in file_paths:
            if not self._is_allowed(file_path):
                forbidden.append(file_path)

        return forbidden

    def _is_allowed(self, file_path: str) -> bool:
        """Check if a file path is in the allowlist.

        Args:
            file_path: The file path to check.

        Returns:
            True if file is allowed, False otherwise.
        """
        # Resolve the path to absolute form
        try:
            resolved = str(Path(file_path).resolve())
        except Exception:
            resolved = file_path

        # Check if resolved path matches any allowed file
        for allowed in self.allowed_files:
            try:
                allowed_resolved = str(Path(allowed).resolve())
                if resolved == allowed_resolved:
                    return True
            except Exception:
                pass

            # Also check suffix matching (for when we can't resolve)
            if resolved.endswith(allowed) or allowed.endswith(resolved):
                return True

            # Check if the allowed path is a directory and file_path is under it
            try:
                allowed_path = Path(allowed)
                if allowed_path.is_dir() or "/" in allowed:
                    # Treat as directory pattern
                    if resolved.startswith(str(allowed_path.parent)) or str(Path(resolved)).startswith(allowed):
                        return True
            except Exception:
                pass

        return False

    def _create_error_response(self, forbidden_files: list[str]) -> dict[str, Any]:
        """Create an error response for blocked file access.

        Args:
            forbidden_files: List of files that are forbidden.

        Returns:
            Error dict with returncode != 0.
        """
        allowed_list = "\n".join(f"  - {f}" for f in self.allowed_files[:10])
        if len(self.allowed_files) > 10:
            allowed_list += f"\n  ... and {len(self.allowed_files) - 10} more"

        forbidden_list = "\n".join(f"  - {f}" for f in forbidden_files[:5])
        if len(forbidden_files) > 5:
            forbidden_list += f"\n  ... and {len(forbidden_files) - 5} more"

        error_message = (
            f"Access denied: Command attempts to access files not in the allowlist.\n\n"
            f"Forbidden files:\n{forbidden_list}\n\n"
            f"Allowed files:\n{allowed_list}"
        )

        return {
            "output": error_message,
            "returncode": 1,
            "exception_info": "File access restricted",
            "extra": {"blocked": True, "forbidden_files": forbidden_files},
        }

    def get_template_vars(self, **kwargs) -> dict[str, Any]:
        """Get template variables for the environment.

        Returns:
            Dict with allowed_files and base environment variables.
        """
        base_vars = self.base_env.get_template_vars(**kwargs)
        return {"allowed_files": self.allowed_files, **base_vars}

    def serialize(self) -> dict:
        """Serialize the environment configuration.

        Returns:
            Serialized configuration dict.
        """
        return {
            "info": {
                "config": {
                    "allowed_files": self.allowed_files,
                    "base_environment": self.base_env.serialize(),
                    "environment_type": f"{self.__class__.__module__}.{self.__class__.__name__}",
                }
            }
        }
