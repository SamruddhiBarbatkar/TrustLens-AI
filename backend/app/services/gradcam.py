"""Model-agnostic Grad-CAM rendering for backend-only image classifiers."""

import base64
from io import BytesIO

import numpy as np
import torch
from PIL import Image
from torch import nn


class GradCAMError(RuntimeError):
    """Raised when an explainability artifact cannot be calculated."""


def render_gradcam(
    model: nn.Module,
    target_layer: nn.Module,
    tensor: torch.Tensor,
    image: Image.Image,
) -> tuple[torch.Tensor, Image.Image]:
    """Render a heatmap for the predicted class from this exact forward pass.

    The returned image highlights regions that influenced the model output. It
    is explanatory evidence, not a segmentation mask or forensic conclusion.
    """
    activations: list[torch.Tensor] = []
    gradients: list[torch.Tensor] = []

    def capture_activation(_module: nn.Module, _inputs: tuple[object, ...], output: torch.Tensor) -> None:
        activations.append(output)
        output.register_hook(lambda gradient: gradients.append(gradient))

    hook = target_layer.register_forward_hook(capture_activation)
    try:
        model.zero_grad(set_to_none=True)
        logits = model(tensor)
        if logits.ndim != 2 or logits.shape[0] != 1:
            raise GradCAMError("Grad-CAM requires one classifier prediction.")
        class_index = int(torch.argmax(logits, dim=1).item())
        logits[0, class_index].backward()
    finally:
        hook.remove()

    if not activations or not gradients:
        raise GradCAMError("Grad-CAM activations are unavailable.")
    weights = gradients[0].mean(dim=(2, 3), keepdim=True)
    cam = torch.relu((weights * activations[0]).sum(dim=1))[0]
    maximum = float(cam.max().item())
    if maximum <= 0:
        raise GradCAMError("Grad-CAM did not produce visual evidence.")
    normalized = (cam / maximum).detach().cpu().numpy()
    heatmap = Image.fromarray(np.uint8(normalized * 255)).resize(image.size, Image.Resampling.BILINEAR)
    colors = np.zeros((heatmap.height, heatmap.width, 3), dtype=np.uint8)
    values = np.asarray(heatmap, dtype=np.float32) / 255.0
    colors[..., 0] = np.uint8(np.clip(255 * values, 0, 255))
    colors[..., 1] = np.uint8(np.clip(220 * (1 - np.abs(values - 0.55) * 2), 0, 255))
    colors[..., 2] = np.uint8(np.clip(255 * (1 - values), 0, 255))
    return logits.detach(), Image.blend(image.convert("RGB"), Image.fromarray(colors), 0.42)


def image_data_url(image: Image.Image) -> str:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
