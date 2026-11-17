from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


INVALID_WINDOWS_CHARS = set('<>:"/\\|?*')
RESERVED_WINDOWS_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


@dataclass(frozen=True)
class RenameOptions:
    prefix: str = ""
    suffix: str = ""
    find_text: str = ""
    replace_text: str = ""
    remove_characters: str = ""
    case_mode: str = "Keep"
    add_number: bool = False
    number_start: int = 1
    number_width: int = 2
    number_separator: str = "_"


@dataclass(frozen=True)
class PreviewItem:
    source: Path
    destination: Path
    proposed_name: str
    errors: tuple[str, ...] = ()

    @property
    def changed(self) -> bool:
        return self.source.name != self.proposed_name


def _apply_case(value: str, mode: str) -> str:
    if mode == "UPPERCASE":
        return value.upper()
    if mode == "lowercase":
        return value.lower()
    if mode == "Title Case":
        return value.title()
    return value


def _proposed_name(source: Path, options: RenameOptions, sequence: int) -> str:
    stem, extension = os.path.splitext(source.name)
    if options.find_text:
        stem = stem.replace(options.find_text, options.replace_text)
    if options.remove_characters:
        stem = stem.replace(options.remove_characters, "")

    stem = f"{options.prefix}{stem}{options.suffix}"
    if options.add_number:
        number = str(options.number_start + sequence).zfill(max(1, options.number_width))
        stem = f"{stem}{options.number_separator}{number}"

    stem = _apply_case(stem, options.case_mode)
    return f"{stem}{extension}"


def make_destination(source: Path, options: RenameOptions, sequence: int) -> Path:
    proposed = _proposed_name(source, options, sequence)
    safe_name = proposed.replace("/", "_").replace("\\", "_")
    return source.with_name(safe_name)


def validate_filename(filename: str) -> tuple[str, ...]:
    errors: list[str] = []
    if not filename or filename in {".", ".."}:
        errors.append("The filename cannot be empty.")
        return tuple(errors)
    if any(character in INVALID_WINDOWS_CHARS or ord(character) < 32 for character in filename):
        errors.append('Contains a Windows-invalid character: < > : " / \\ | ? *')
    if filename.endswith((" ", ".")):
        errors.append("A Windows filename cannot end with a space or period.")
    base_name = filename.split(".", 1)[0].upper()
    if base_name in RESERVED_WINDOWS_NAMES:
        errors.append(f"{base_name} is a reserved Windows device name.")
    if len(filename) > 255:
        errors.append("The filename exceeds the 255-character Windows limit.")
    return tuple(errors)


def _path_key(path: Path) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(path)))


def preview_renames(
    sources: Sequence[Path], options: RenameOptions
) -> list[PreviewItem]:
    proposed_names = [
        _proposed_name(source, options, index)
        for index, source in enumerate(sources)
    ]
    changed_sources = {
        _path_key(source)
        for source, proposed_name in zip(sources, proposed_names)
        if source.name != proposed_name
    }

    items: list[PreviewItem] = []
    target_counts: dict[str, int] = {}
    for source, proposed_name in zip(sources, proposed_names):
        key = f"{_path_key(source.parent)}|{proposed_name.casefold()}"
        target_counts[key] = target_counts.get(key, 0) + 1

    for index, (source, proposed_name) in enumerate(zip(sources, proposed_names)):
        destination = make_destination(source, options, index)
        errors = list(validate_filename(proposed_name))
        target_key = f"{_path_key(source.parent)}|{proposed_name.casefold()}"
        if target_counts[target_key] > 1:
            errors.append("Multiple files would have this destination name.")
        if (
            source.name != proposed_name
            and not errors
            and destination.exists()
            and _path_key(destination) not in changed_sources
        ):
            errors.append("A file with this name already exists.")
        items.append(PreviewItem(source, destination, proposed_name, tuple(errors)))
    return items


def _move_no_replace(source: Path, destination: Path) -> None:
    if os.name == "nt":
        if destination.exists():
            raise FileExistsError(f"Destination already exists: {destination}")
        os.rename(source, destination)
    else:
        os.link(source, destination)
        try:
            source.unlink()
        except OSError:
            try:
                destination.unlink()
            except OSError as cleanup_error:
                raise OSError(
                    f"Could not complete or clean up move to {destination}: {cleanup_error}"
                )
            raise


def perform_rename(pairs: Sequence[tuple[Path, Path]]) -> None:
    """Move files as a batch, using temporary names to support swaps safely."""
    changed = [(source, destination) for source, destination in pairs if source != destination]
    if not changed:
        return

    source_keys = {_path_key(source) for source, _ in changed}
    destination_keys: set[str] = set()
    for source, destination in changed:
        if not source.is_file():
            raise FileNotFoundError(f"Source file no longer exists: {source}")
        key = _path_key(destination)
        if key in destination_keys:
            raise FileExistsError(f"Duplicate destination: {destination}")
        destination_keys.add(key)
        if destination.exists() and key not in source_keys:
            raise FileExistsError(f"Destination already exists: {destination}")

    staged: list[tuple[Path, Path]] = []
    completed: list[tuple[Path, Path]] = []
    try:
        for source, _ in changed:
            temporary = source.with_name(f".{source.name}.{uuid.uuid4().hex}.renametmp")
            _move_no_replace(source, temporary)
            staged.append((source, temporary))
        for (source, destination), (_, temporary) in zip(changed, staged):
            _move_no_replace(temporary, destination)
            completed.append((source, destination))
    except Exception as error:
        rollback_errors: list[str] = []
        for source, destination in reversed(completed):
            try:
                _move_no_replace(destination, source)
            except OSError as rollback_error:
                rollback_errors.append(f"{destination} -> {source}: {rollback_error}")
        completed_sources = {_path_key(source) for source, _ in completed}
        for source, temporary in reversed(staged):
            if _path_key(source) in completed_sources or not temporary.exists():
                continue
            try:
                _move_no_replace(temporary, source)
            except OSError as rollback_error:
                rollback_errors.append(f"{temporary} -> {source}: {rollback_error}")
        detail = f"Rename failed: {error}"
        if rollback_errors:
            detail += "\nRollback was incomplete:\n" + "\n".join(rollback_errors)
        raise OSError(detail) from error


def default_history_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    root = Path(local_app_data) if local_app_data else Path.home()
    return root / "WindowsFileRenamer" / "history.json"


class RenameHistory:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_history_path()
        self.entries: list[dict[str, object]] = []
        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as history_file:
                data = json.load(history_file)
            if not isinstance(data, list) or any(
                not isinstance(entry, dict)
                or not isinstance(entry.get("pairs"), list)
                or any(
                    not isinstance(pair, list)
                    or len(pair) != 2
                    or not all(isinstance(value, str) for value in pair)
                    for pair in entry["pairs"]
                )
                for entry in data
            ):
                raise ValueError(f"Invalid rename history format: {self.path}")
            self.entries = data

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix="history-", suffix=".tmp", dir=self.path.parent
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as temporary_file:
                json.dump(self.entries, temporary_file, indent=2, ensure_ascii=False)
                temporary_file.write("\n")
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_name, self.path)
        except Exception:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise

    def record(self, pairs: Sequence[tuple[Path, Path]]) -> None:
        changed = [(source, destination) for source, destination in pairs if source != destination]
        if not changed:
            return
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pairs": [[str(source), str(destination)] for source, destination in changed],
        }
        self.entries.append(entry)
        try:
            self._save()
        except Exception:
            self.entries.pop()
            raise

    def undo_latest(self) -> list[tuple[Path, Path]]:
        if not self.entries:
            raise ValueError("There is no rename operation to undo.")
        entry = self.entries[-1]
        raw_pairs = entry.get("pairs")
        if not isinstance(raw_pairs, list):
            raise ValueError("The latest history entry is invalid.")
        pairs = [(Path(new), Path(old)) for old, new in raw_pairs]
        for source, destination in pairs:
            if not source.is_file():
                raise FileNotFoundError(f"Cannot undo; renamed file is missing: {source}")
            if destination.exists() and _path_key(destination) not in {
                _path_key(pair[0]) for pair in pairs
            }:
                raise FileExistsError(f"Cannot undo; original name is occupied: {destination}")

        perform_rename(pairs)
        removed = self.entries.pop()
        try:
            self._save()
        except Exception:
            self.entries.append(removed)
            try:
                perform_rename([(new, old) for old, new in pairs])
            except OSError as rollback_error:
                raise OSError(
                    f"Undo completed but history could not be saved, and rollback failed: {rollback_error}"
                )
            raise
        return pairs


def filtered_files(folder: Path, extension_filter: str = "") -> list[Path]:
    """Return files in a folder matching comma-separated extensions."""
    extensions = {
        value.strip().lower()
        for value in extension_filter.split(",")
        if value.strip() and value.strip() != "*"
    }
    if "*" in {value.strip() for value in extension_filter.split(",")}:
        extensions.clear()
    return sorted(
        (
            item for item in folder.iterdir()
            if item.is_file()
            and (not extensions or item.suffix.lower() in extensions)
        ),
        key=lambda item: item.name.casefold(),
    )
