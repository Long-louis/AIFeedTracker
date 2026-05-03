import json
import os
import tempfile
from pathlib import Path


class CreatorStore:
    def __init__(self, file_path: str | Path):
        self._file_path = Path(file_path)

    def load_creators(self) -> list[dict]:
        if not self._file_path.exists():
            raise FileNotFoundError(f"Creator file not found: {self._file_path}")

        try:
            content = self._file_path.read_text(encoding="utf-8")
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid creator JSON in {self._file_path}") from exc

        creators = self._validate_creators_list(data)
        normalized = self._normalize_creators(creators)
        self._ensure_unique_uids(normalized)
        return normalized

    def save_creators(self, creators: list[dict]) -> None:
        validated = self._validate_creators_list(creators)
        normalized = self._normalize_creators(validated)
        self._ensure_unique_uids(normalized)

        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(normalized, ensure_ascii=False, indent=2) + "\n"

        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=self._file_path.parent,
            delete=False,
        ) as temp_file:
            temp_file.write(payload)
            temp_path = Path(temp_file.name)

        try:
            os.replace(str(temp_path), str(self._file_path))
        except Exception:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    def _validate_creators_list(self, creators: object) -> list[dict]:
        if not isinstance(creators, list):
            raise ValueError("Creators data must be a JSON list")

        for index, creator in enumerate(creators):
            if not isinstance(creator, dict):
                raise ValueError(f"Creator at index {index} must be a JSON object")

        return creators

    def _normalize_creators(self, creators: list[dict]) -> list[dict]:
        normalized: list[dict] = []
        for index, creator in enumerate(creators):
            normalized_creator = dict(creator)
            normalized_creator["uid"] = self._normalize_uid(creator, index)
            normalized.append(normalized_creator)
        return normalized

    def _normalize_uid(self, creator: dict, index: int) -> int:
        if "uid" not in creator:
            raise ValueError(f"Creator at index {index} is missing required field: uid")

        uid = creator["uid"]
        if isinstance(uid, bool):
            raise ValueError(f"Creator uid must be a positive int at index {index}")

        if isinstance(uid, int):
            normalized_uid = uid
        elif isinstance(uid, str):
            uid_stripped = uid.strip()
            if not uid_stripped:
                raise ValueError(f"Creator uid must be a positive int at index {index}")
            try:
                normalized_uid = int(uid_stripped)
            except ValueError as exc:
                raise ValueError(f"Creator uid must be a positive int at index {index}") from exc
        else:
            raise ValueError(f"Creator uid must be a positive int at index {index}")

        if normalized_uid <= 0:
            raise ValueError(f"Creator uid must be a positive int at index {index}")

        return normalized_uid

    def _ensure_unique_uids(self, creators: list[dict]) -> None:
        seen: set[int] = set()
        for index, creator in enumerate(creators):
            uid = creator["uid"]

            if uid in seen:
                raise ValueError(f"Duplicate creator uid: {uid}")
            seen.add(uid)
