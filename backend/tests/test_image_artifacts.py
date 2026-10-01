from pathlib import Path

from PIL import Image

from app.services.image_artifacts import ImageArtifactStore


def test_image_artifact_store_writes_normalized_png_and_rejects_paths(tmp_path: Path) -> None:
    store = ImageArtifactStore(tmp_path)

    filename = store.save(Image.new("RGB", (5, 3), "white"))
    artifact = store.path_for(filename)

    assert artifact is not None
    assert artifact.parent == tmp_path.resolve()
    assert artifact.suffix == ".png"
    with Image.open(artifact) as image:
        assert image.size == (5, 3)
        assert image.format == "PNG"
    assert store.path_for("../outside.png") is None
    assert store.path_for("not-an-artifact.jpg") is None
