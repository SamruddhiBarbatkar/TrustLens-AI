"""Safe server-side persistence for owner-authorized image display artifacts."""

from pathlib import Path
from uuid import uuid4

from PIL import Image


class ImageArtifactStore:
    """Stores normalized image pixels outside the public web root.

    The generated filename is persisted with an analysis record and is never
    accepted from a client or used as a public static path.
    """

    def __init__(self, uploads_path: Path) -> None:
        self._uploads_path = uploads_path.resolve()

    def save(self, image: Image.Image) -> str:
        self._uploads_path.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid4().hex}.png"
        destination = self._uploads_path / filename
        temporary = self._uploads_path / f".{filename}.tmp"
        image.save(temporary, format="PNG")
        temporary.replace(destination)
        return filename

    def path_for(self, filename: str | None) -> Path | None:
        if not filename or Path(filename).name != filename or Path(filename).suffix != ".png":
            return None
        candidate = (self._uploads_path / filename).resolve()
        try:
            candidate.relative_to(self._uploads_path)
        except ValueError:
            return None
        return candidate if candidate.is_file() else None

    def remove(self, filename: str | None) -> None:
        path = self.path_for(filename)
        if path is not None:
            path.unlink(missing_ok=True)
