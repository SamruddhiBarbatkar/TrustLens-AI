"""Low-storage, group-safe retraining for the TrustLens tampering detector.

The source dataset is streamed from Hugging Face. Source groups used by the
TrustLens compact evaluation pack are excluded before deterministic group
partitioning, so paired authentic/manipulated images cannot leak between
training, validation, and the final external evaluation.
"""

import argparse
import copy
import csv
import hashlib
import io
import json
import math
import random
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch import nn
from torch.utils.data import DataLoader, IterableDataset
from torchvision import models, transforms


DATASET_NAME = "KhangTruong/Tampered-Images-Combined-Dataset"
DATASET_SPLIT = "cross_test"
SYNTHETIC_DATASET_NAME = "TheKernel01/Tiny-GenImage"
SYNTHETIC_DATASET_SPLIT = "train"
IMAGE_SIZE = 224
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def source_group(identifier):
    """Map an original and all of its manipulated variants to one group."""
    identifier = str(identifier).lower()
    patterns = (
        ("sagid", r"^sagid_(?:coco|real)_(\d+)"),
        ("cocoglide", r"^cocoglide_(?:real_)?(\d+)$"),
        ("opensdid", r"^opensdid_(?:real|flux\.1|sd1\.5|sdxl)_(\d+)\.jpg$"),
    )
    for prefix, pattern in patterns:
        match = re.match(pattern, identifier)
        if match:
            return f"{prefix}-{int(match.group(1))}"
    return None


def load_excluded_groups(path):
    """Load combined-dataset groups reserved by the external evaluation."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(
            "Evaluation provenance is required to prevent leakage: "
            f"{path}"
        )
    excluded = set()
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            if row.get("dataset") != DATASET_NAME:
                continue
            group = source_group(row.get("source_id", ""))
            if group:
                excluded.add(group)
    if not excluded:
        raise ValueError(
            "No reserved tampering groups were found in the provenance file."
        )
    return excluded


def group_partition(group, seed, validation_fraction):
    digest = hashlib.sha256(f"{seed}:{group}".encode("utf-8")).digest()
    ratio = int.from_bytes(digest[:8], "big") / float(2**64)
    return "validation" if ratio < validation_fraction else "train"


class RandomJpegCompression:
    def __init__(self, minimum_quality=70, maximum_quality=98):
        self.minimum_quality = minimum_quality
        self.maximum_quality = maximum_quality

    def __call__(self, image):
        quality = random.randint(self.minimum_quality, self.maximum_quality)
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="JPEG", quality=quality)
        buffer.seek(0)
        with Image.open(buffer) as compressed:
            return compressed.convert("RGB")


class BalancedTamperingStream(IterableDataset):
    """Stream balanced tampering data with synthetic hard negatives."""

    def __init__(
        self,
        partition,
        per_class,
        transform,
        excluded_groups,
        seed,
        buffer_size,
        validation_fraction,
        synthetic_negative_fraction,
        synthetic_start,
    ):
        self.partition = partition
        self.per_class = per_class
        self.transform = transform
        self.excluded_groups = frozenset(excluded_groups)
        self.seed = seed
        self.buffer_size = buffer_size
        self.validation_fraction = validation_fraction
        self.synthetic_negative_fraction = synthetic_negative_fraction
        self.synthetic_start = synthetic_start

    def __len__(self):
        return self.per_class * 2

    def __iter__(self):
        from datasets import load_dataset

        synthetic_target = round(
            self.per_class * self.synthetic_negative_fraction
        )
        natural_target = self.per_class - synthetic_target

        stream = load_dataset(
            DATASET_NAME,
            split=DATASET_SPLIT,
            streaming=True,
        ).shuffle(seed=self.seed, buffer_size=self.buffer_size)
        combined_targets = {0: natural_target, 1: self.per_class}

        def combined_samples():
            counts = {0: 0, 1: 0}
            for item in stream:
                label = int(item["label"])
                if label not in counts or counts[label] >= combined_targets[label]:
                    continue
                group = source_group(item.get("id", ""))
                if not group or group in self.excluded_groups:
                    continue
                if group_partition(
                    group,
                    self.seed,
                    self.validation_fraction,
                ) != self.partition:
                    continue
                counts[label] += 1
                yield self.transform(item["image"].convert("RGB")), label
                if all(
                    counts[label] == combined_targets[label]
                    for label in counts
                ):
                    return
            raise RuntimeError(
                f"The {self.partition} combined stream ended before quotas "
                f"were met: {counts}; requested {combined_targets}."
            )

        synthetic_stream = load_dataset(
            SYNTHETIC_DATASET_NAME,
            split=SYNTHETIC_DATASET_SPLIT,
            streaming=True,
        ).shuffle(seed=self.seed, buffer_size=self.buffer_size)

        def synthetic_samples():
            skipped = 0
            yielded = 0
            for item in synthetic_stream:
                # Tiny-GenImage labels: real=0, fake=1. Fully generated images
                # are hard negatives for localized tampering detection.
                if int(item["label"]) != 1:
                    continue
                if skipped < self.synthetic_start:
                    skipped += 1
                    continue
                yield self.transform(item["image"].convert("RGB")), 0
                yielded += 1
                if yielded == synthetic_target:
                    return
            raise RuntimeError(
                f"The synthetic stream yielded {yielded}/{synthetic_target} "
                f"hard negatives after skipping {self.synthetic_start}."
            )

        synthetic_iterator = iter(synthetic_samples())
        synthetic_exhausted = synthetic_target == 0
        for index, sample in enumerate(combined_samples(), start=1):
            yield sample
            if not synthetic_exhausted and index % 2 == 0:
                try:
                    yield next(synthetic_iterator)
                except StopIteration:
                    synthetic_exhausted = True
        if not synthetic_exhausted:
            yield from synthetic_iterator


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def make_transforms():
    train_transform = transforms.Compose([
        transforms.Resize(
            (IMAGE_SIZE, IMAGE_SIZE),
            interpolation=transforms.InterpolationMode.BICUBIC,
        ),
        transforms.RandomHorizontalFlip(),
        transforms.RandomApply([
            transforms.ColorJitter(
                brightness=0.08,
                contrast=0.08,
                saturation=0.05,
            )
        ], p=0.25),
        transforms.RandomApply([RandomJpegCompression()], p=0.35),
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
    model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
    for parameter in model.parameters():
        parameter.requires_grad = False
    for block in (model.layer3, model.layer4):
        for parameter in block.parameters():
            parameter.requires_grad = True
    model.fc = nn.Linear(model.fc.in_features, 2)
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
    from tqdm.auto import tqdm

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
    if not count:
        raise RuntimeError("Training stream produced no observations.")
    return {
        "loss": loss_sum / count,
        "accuracy": correct / count,
        "count": count,
    }


@torch.no_grad()
def evaluate(model, loader, criterion, device):
    from sklearn.metrics import average_precision_score, roc_auc_score
    from tqdm.auto import tqdm

    model.eval()
    loss_sum = 0.0
    correct = 0
    count = 0
    probabilities = []
    labels_seen = []
    for images, labels in tqdm(loader, desc="validation", leave=False):
        images = images.to(device, non_blocking=True)
        labels = labels.to(device, non_blocking=True)
        logits = model(images)
        loss = criterion(logits, labels)
        batch_probabilities = torch.softmax(logits, dim=1)[:, 1]
        loss_sum += loss.item() * labels.size(0)
        correct += (logits.argmax(dim=1) == labels).sum().item()
        count += labels.size(0)
        probabilities.extend(batch_probabilities.cpu().tolist())
        labels_seen.extend(labels.cpu().tolist())
    if not count:
        raise RuntimeError("Validation stream produced no observations.")
    return {
        "loss": loss_sum / count,
        "accuracy": correct / count,
        "auroc": roc_auc_score(labels_seen, probabilities),
        "average_precision": average_precision_score(
            labels_seen,
            probabilities,
        ),
        "expected_calibration_error": expected_calibration_error(
            probabilities,
            labels_seen,
        ),
        "count": count,
    }


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "training_outputs/tampering_multisource_hardnegative_candidate.pth"
        ),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path(
            "training_outputs/tampering_multisource_hardnegative_report.json"
        ),
    )
    parser.add_argument(
        "--exclude-provenance",
        type=Path,
        default=Path("calibration/compact_provenance.csv"),
    )
    parser.add_argument("--train-per-class", type=int, default=2000)
    parser.add_argument("--validation-per-class", type=int, default=400)
    parser.add_argument("--validation-fraction", type=float, default=0.18)
    parser.add_argument(
        "--synthetic-negative-fraction",
        type=float,
        default=0.5,
    )
    parser.add_argument("--epochs", type=int, default=6)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--patience", type=int, default=2)
    parser.add_argument("--buffer-size", type=int, default=8192)
    parser.add_argument("--seed", type=int, default=2026)
    return parser.parse_args()


def main():
    from datasets import disable_caching

    args = parse_args()
    if args.train_per_class < 500 or args.validation_per_class < 100:
        raise ValueError(
            "Use at least 500 training and 100 validation images per class."
        )
    if not 0.1 <= args.validation_fraction <= 0.3:
        raise ValueError("--validation-fraction must be between 0.1 and 0.3.")
    if not 0.25 <= args.synthetic_negative_fraction <= 0.75:
        raise ValueError(
            "--synthetic-negative-fraction must be between 0.25 and 0.75."
        )

    disable_caching()
    set_seed(args.seed)
    excluded_groups = load_excluded_groups(args.exclude_provenance)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    print(f"Reserved evaluation groups excluded: {len(excluded_groups)}")
    if device.type != "cuda":
        print("Warning: training is practical on a Colab GPU, not a local CPU.")

    train_transform, validation_transform = make_transforms()
    train_dataset = BalancedTamperingStream(
        partition="train",
        per_class=args.train_per_class,
        transform=train_transform,
        excluded_groups=excluded_groups,
        seed=args.seed,
        buffer_size=args.buffer_size,
        validation_fraction=args.validation_fraction,
        synthetic_negative_fraction=args.synthetic_negative_fraction,
        synthetic_start=round(
            args.validation_per_class * args.synthetic_negative_fraction
        ),
    )
    validation_dataset = BalancedTamperingStream(
        partition="validation",
        per_class=args.validation_per_class,
        transform=validation_transform,
        excluded_groups=excluded_groups,
        seed=args.seed,
        buffer_size=args.buffer_size,
        validation_fraction=args.validation_fraction,
        synthetic_negative_fraction=args.synthetic_negative_fraction,
        synthetic_start=0,
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
    optimizer = torch.optim.AdamW(
        [parameter for parameter in model.parameters() if parameter.requires_grad],
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
    torch.save(
        {name: tensor.cpu() for name, tensor in best_state.items()},
        args.output,
    )
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset": DATASET_NAME,
        "dataset_split": DATASET_SPLIT,
        "checkpoint_label_mapping": {"AUTHENTIC": 0, "TAMPERED": 1},
        "partition": {
            "method": "sha256-source-group",
            "seed": args.seed,
            "validation_fraction": args.validation_fraction,
            "train_per_class": args.train_per_class,
            "validation_per_class": args.validation_per_class,
            "excluded_evaluation_groups": len(excluded_groups),
            "exclusion_provenance": str(args.exclude_provenance),
            "synthetic_negative_fraction": args.synthetic_negative_fraction,
            "synthetic_negative_dataset": SYNTHETIC_DATASET_NAME,
            "synthetic_negative_split": SYNTHETIC_DATASET_SPLIT,
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
