"""Low-storage multi-generator training for the TrustLens AI detector.

The source dataset is streamed from Hugging Face. The script intentionally uses
only Tiny-GenImage's training split; TrustLens's compact validation pack uses
different rows and remains untouched for the final promotion decision.
"""

import argparse
import copy
import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from datasets import disable_caching, load_dataset
from PIL import Image
from sklearn.metrics import average_precision_score, roc_auc_score
from torch import nn
from torch.utils.data import DataLoader, IterableDataset
from torchvision import models, transforms
from tqdm.auto import tqdm


DATASET_NAME = "TheKernel01/Tiny-GenImage"
DATASET_SPLIT = "train"
IMAGE_SIZE = 224
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


class RandomJpegCompression:
    def __init__(self, minimum_quality=55, maximum_quality=98):
        self.minimum_quality = minimum_quality
        self.maximum_quality = maximum_quality

    def __call__(self, image):
        import io

        quality = random.randint(self.minimum_quality, self.maximum_quality)
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="JPEG", quality=quality)
        buffer.seek(0)
        with Image.open(buffer) as compressed:
            return compressed.convert("RGB")


class TinyGenImageStream(IterableDataset):
    """A deterministic take/skip partition over a shuffled remote stream."""

    def __init__(self, start, count, transform, seed, buffer_size):
        self.start = start
        self.count = count
        self.transform = transform
        self.seed = seed
        self.buffer_size = buffer_size

    def __len__(self):
        return self.count

    def __iter__(self):
        stream = load_dataset(
            DATASET_NAME,
            split=DATASET_SPLIT,
            streaming=True,
        )
        stream = stream.shuffle(
            seed=self.seed,
            buffer_size=self.buffer_size,
        )
        if self.start:
            stream = stream.skip(self.start)
        stream = stream.take(self.count)
        for item in stream:
            image = item["image"].convert("RGB")
            # Dataset labels: real=0, fake=1.
            # Deployed TrustLens checkpoint labels: FAKE=0, REAL=1.
            target = 0 if int(item["label"]) == 1 else 1
            yield self.transform(image), target


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def make_transforms():
    train_transform = transforms.Compose([
        transforms.RandomResizedCrop(
            IMAGE_SIZE,
            scale=(0.65, 1.0),
            interpolation=transforms.InterpolationMode.BICUBIC,
        ),
        transforms.RandomHorizontalFlip(),
        transforms.RandomApply([
            transforms.ColorJitter(
                brightness=0.12,
                contrast=0.12,
                saturation=0.08,
            )
        ], p=0.35),
        transforms.RandomApply([RandomJpegCompression()], p=0.65),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])
    validation_transform = transforms.Compose([
        transforms.Resize(
            (IMAGE_SIZE, IMAGE_SIZE),
            interpolation=transforms.InterpolationMode.BICUBIC,
        ),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])
    return train_transform, validation_transform


def build_model():
    model = models.efficientnet_b0(
        weights=models.EfficientNet_B0_Weights.DEFAULT,
    )
    for parameter in model.features.parameters():
        parameter.requires_grad = False
    # Adapt higher-level visual features while retaining the ImageNet base.
    for block in model.features[-3:]:
        for parameter in block.parameters():
            parameter.requires_grad = True
    model.classifier[1] = nn.Linear(model.classifier[1].in_features, 2)
    return model


def expected_calibration_error(probabilities, labels, bins=10):
    probabilities = np.asarray(probabilities, dtype=float)
    labels = np.asarray(labels, dtype=int)
    result = 0.0
    for index in range(bins):
        lower = index / bins
        upper = (index + 1) / bins
        mask = (probabilities >= lower) & (probabilities < upper)
        if index == bins - 1:
            mask |= probabilities == 1.0
        if not mask.any():
            continue
        result += mask.mean() * abs(
            probabilities[mask].mean() - labels[mask].mean()
        )
    return float(result)


def train_epoch(model, loader, criterion, optimizer, scaler, device):
    model.train()
    loss_sum = 0.0
    correct = 0
    count = 0
    use_amp = device.type == "cuda"
    for images, labels in tqdm(loader, desc="train", leave=False):
        images = images.to(device, non_blocking=True)
        labels = labels.to(device, non_blocking=True)
        optimizer.zero_grad(set_to_none=True)
        with torch.amp.autocast(device_type=device.type, enabled=use_amp):
            logits = model(images)
            loss = criterion(logits, labels)
        scaler.scale(loss).backward()
        scaler.step(optimizer)
        scaler.update()
        loss_sum += loss.item() * labels.size(0)
        correct += (logits.argmax(dim=1) == labels).sum().item()
        count += labels.size(0)
    return {
        "loss": loss_sum / count,
        "accuracy": correct / count,
        "count": count,
    }


@torch.no_grad()
def evaluate(model, loader, criterion, device):
    model.eval()
    loss_sum = 0.0
    correct = 0
    count = 0
    fake_probabilities = []
    fake_labels = []
    for images, labels in tqdm(loader, desc="validation", leave=False):
        images = images.to(device, non_blocking=True)
        labels = labels.to(device, non_blocking=True)
        logits = model(images)
        loss = criterion(logits, labels)
        probabilities = torch.softmax(logits, dim=1)
        loss_sum += loss.item() * labels.size(0)
        correct += (logits.argmax(dim=1) == labels).sum().item()
        count += labels.size(0)
        fake_probabilities.extend(probabilities[:, 0].cpu().tolist())
        fake_labels.extend((labels == 0).int().cpu().tolist())
    return {
        "loss": loss_sum / count,
        "accuracy": correct / count,
        "auroc": roc_auc_score(fake_labels, fake_probabilities),
        "average_precision": average_precision_score(
            fake_labels,
            fake_probabilities,
        ),
        "expected_calibration_error": expected_calibration_error(
            fake_probabilities,
            fake_labels,
        ),
        "count": count,
    }


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("training_outputs/ai_detector_multigen_candidate.pth"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("training_outputs/ai_detector_multigen_report.json"),
    )
    parser.add_argument("--train-samples", type=int, default=8000)
    parser.add_argument("--validation-samples", type=int, default=1200)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--patience", type=int, default=3)
    parser.add_argument("--buffer-size", type=int, default=4096)
    parser.add_argument("--seed", type=int, default=2026)
    return parser.parse_args()


def main():
    args = parse_args()
    if args.train_samples < 1000 or args.validation_samples < 200:
        raise ValueError("Use at least 1000 training and 200 validation samples.")
    if args.train_samples + args.validation_samples > 28000:
        raise ValueError("Requested sample count exceeds Tiny-GenImage train.")

    disable_caching()
    set_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    if device.type != "cuda":
        print("Warning: training is practical on a Colab GPU, not a local CPU.")

    train_transform, validation_transform = make_transforms()
    # Shuffle first, then reserve the head for validation and the following
    # rows for training. The same seed makes the partitions reproducible.
    validation_dataset = TinyGenImageStream(
        start=0,
        count=args.validation_samples,
        transform=validation_transform,
        seed=args.seed,
        buffer_size=args.buffer_size,
    )
    train_dataset = TinyGenImageStream(
        start=args.validation_samples,
        count=args.train_samples,
        transform=train_transform,
        seed=args.seed,
        buffer_size=args.buffer_size,
    )
    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        num_workers=0,
        pin_memory=device.type == "cuda",
    )
    validation_loader = DataLoader(
        validation_dataset,
        batch_size=args.batch_size,
        num_workers=0,
        pin_memory=device.type == "cuda",
    )

    model = build_model().to(device)
    criterion = nn.CrossEntropyLoss(label_smoothing=0.05)
    trainable = [parameter for parameter in model.parameters() if parameter.requires_grad]
    optimizer = torch.optim.AdamW(
        trainable,
        lr=args.learning_rate,
        weight_decay=args.weight_decay,
    )
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer,
        mode="max",
        factor=0.5,
        patience=1,
    )
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")

    best_auroc = -math.inf
    best_state = None
    epochs_without_improvement = 0
    history = []
    for epoch in range(1, args.epochs + 1):
        print(f"Epoch {epoch}/{args.epochs}")
        train_metrics = train_epoch(
            model,
            train_loader,
            criterion,
            optimizer,
            scaler,
            device,
        )
        validation_metrics = evaluate(
            model,
            validation_loader,
            criterion,
            device,
        )
        scheduler.step(validation_metrics["auroc"])
        record = {
            "epoch": epoch,
            "learning_rate": optimizer.param_groups[0]["lr"],
            "train": train_metrics,
            "validation": validation_metrics,
        }
        history.append(record)
        print(json.dumps(record, indent=2))

        if validation_metrics["auroc"] > best_auroc + 1e-4:
            best_auroc = validation_metrics["auroc"]
            best_state = copy.deepcopy(model.state_dict())
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= args.patience:
                print("Early stopping triggered.")
                break

    if best_state is None:
        raise RuntimeError("Training did not produce a checkpoint.")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    cpu_state = {name: tensor.cpu() for name, tensor in best_state.items()}
    torch.save(cpu_state, args.output)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset": DATASET_NAME,
        "dataset_split": DATASET_SPLIT,
        "dataset_label_mapping": {"real": 0, "fake": 1},
        "checkpoint_label_mapping": {"FAKE": 0, "REAL": 1},
        "partition": {
            "method": "shuffle-then-take-skip",
            "seed": args.seed,
            "buffer_size": args.buffer_size,
            "validation_start": 0,
            "validation_count": args.validation_samples,
            "train_start": args.validation_samples,
            "train_count": args.train_samples,
        },
        "selection_metric": "validation_auroc",
        "best_validation_auroc": best_auroc,
        "history": history,
        "checkpoint": str(args.output),
        "promotion_status": "CANDIDATE_REQUIRES_EXTERNAL_CALIBRATION",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Candidate checkpoint: {args.output}")
    print(f"Training report: {args.report}")
    print("Do not promote until the external TrustLens calibration gates pass.")


if __name__ == "__main__":
    main()
