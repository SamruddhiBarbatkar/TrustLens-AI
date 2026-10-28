"""Train a low-storage three-class TrustLens image authenticity candidate.

Classes are AUTHENTIC=0, TAMPERED=1, and SYNTHETIC=2. The combined
tampering dataset supplies the first two classes, Tiny-GenImage's training
split supplies the third, and source groups from every supplied evaluation
provenance file are excluded before deterministic partitioning.
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


TAMPER_DATASET = "KhangTruong/Tampered-Images-Combined-Dataset"
TAMPER_SPLIT = "cross_test"
SYNTHETIC_DATASET = "TheKernel01/Tiny-GenImage"
SYNTHETIC_SPLIT = "train"
CLASS_NAMES = {0: "AUTHENTIC", 1: "TAMPERED", 2: "SYNTHETIC"}
IMAGE_SIZE = 224
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def source_group(identifier):
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


def load_excluded_groups(paths):
    excluded = set()
    files = []
    for path in paths:
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(
                f"Evaluation provenance is required to prevent leakage: {path}"
            )
        files.append(str(path))
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            for row in csv.DictReader(source):
                if row.get("dataset") != TAMPER_DATASET:
                    continue
                group = source_group(row.get("source_id", ""))
                if group:
                    excluded.add(group)
    if not excluded:
        raise ValueError("No reserved tampering groups were found in provenance.")
    return excluded, files


def group_partition(group, seed, validation_fraction):
    digest = hashlib.sha256(f"{seed}:{group}".encode("utf-8")).digest()
    ratio = int.from_bytes(digest[:8], "big") / float(2**64)
    return "validation" if ratio < validation_fraction else "train"


class RandomJpegCompression:
    def __init__(self, minimum_quality=65, maximum_quality=98):
        self.minimum_quality = minimum_quality
        self.maximum_quality = maximum_quality

    def __call__(self, image):
        buffer = io.BytesIO()
        image.convert("RGB").save(
            buffer,
            format="JPEG",
            quality=random.randint(self.minimum_quality, self.maximum_quality),
        )
        buffer.seek(0)
        with Image.open(buffer) as compressed:
            return compressed.convert("RGB")


class RandomDownscaleRestore:
    """Simulate social-media resizing without changing the final dimensions."""

    def __init__(self, minimum_scale=0.45, maximum_scale=0.90):
        self.minimum_scale = minimum_scale
        self.maximum_scale = maximum_scale

    def __call__(self, image):
        image = image.convert("RGB")
        width, height = image.size
        scale = random.uniform(self.minimum_scale, self.maximum_scale)
        reduced = image.resize(
            (max(1, round(width * scale)), max(1, round(height * scale))),
            Image.Resampling.BICUBIC,
        )
        return reduced.resize((width, height), Image.Resampling.BICUBIC)


class BalancedThreeClassStream(IterableDataset):
    def __init__(
        self,
        partition,
        per_class,
        transform,
        excluded_groups,
        seed,
        buffer_size,
        validation_fraction,
        synthetic_start,
    ):
        self.partition = partition
        self.per_class = per_class
        self.transform = transform
        self.excluded_groups = frozenset(excluded_groups)
        self.seed = seed
        self.buffer_size = buffer_size
        self.validation_fraction = validation_fraction
        self.synthetic_start = synthetic_start

    def __len__(self):
        return self.per_class * len(CLASS_NAMES)

    def __iter__(self):
        from datasets import load_dataset

        combined_stream = load_dataset(
            TAMPER_DATASET,
            split=TAMPER_SPLIT,
            streaming=True,
        ).shuffle(seed=self.seed, buffer_size=self.buffer_size)

        def combined_samples():
            counts = {0: 0, 1: 0}
            for item in combined_stream:
                label = int(item["label"])
                if label not in counts or counts[label] >= self.per_class:
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
                if all(count == self.per_class for count in counts.values()):
                    return
            raise RuntimeError(
                f"The {self.partition} tampering stream ended before class "
                f"quotas were met: {counts}; requested {self.per_class}."
            )

        synthetic_stream = load_dataset(
            SYNTHETIC_DATASET,
            split=SYNTHETIC_SPLIT,
            streaming=True,
        ).shuffle(seed=self.seed, buffer_size=self.buffer_size)

        def synthetic_samples():
            skipped = 0
            yielded = 0
            for item in synthetic_stream:
                if int(item["label"]) != 1:
                    continue
                if skipped < self.synthetic_start:
                    skipped += 1
                    continue
                yielded += 1
                yield self.transform(item["image"].convert("RGB")), 2
                if yielded == self.per_class:
                    return
            raise RuntimeError(
                f"The synthetic stream yielded {yielded}/{self.per_class} "
                f"images after skipping {self.synthetic_start}."
            )

        synthetic_iterator = iter(synthetic_samples())
        synthetic_exhausted = False
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


def make_transforms(profile="basic"):
    if profile not in {"basic", "forensic"}:
        raise ValueError("Unknown augmentation profile: " + profile)

    if profile == "forensic":
        # Some batches retain global composition while others teach the model
        # to recognise traces in a local region. Compression and downscaling
        # approximate common upload/re-share paths seen by the application.
        spatial_transform = transforms.RandomChoice([
            transforms.Resize(
                (IMAGE_SIZE, IMAGE_SIZE),
                interpolation=transforms.InterpolationMode.BICUBIC,
            ),
            transforms.Resize(
                (IMAGE_SIZE, IMAGE_SIZE),
                interpolation=transforms.InterpolationMode.BICUBIC,
            ),
            transforms.RandomResizedCrop(
                IMAGE_SIZE,
                scale=(0.50, 1.0),
                ratio=(0.75, 1.3333333333),
                interpolation=transforms.InterpolationMode.BICUBIC,
            ),
        ])
        degradation_transforms = [
            transforms.RandomApply([RandomDownscaleRestore()], p=0.35),
            transforms.RandomApply(
                [RandomJpegCompression(minimum_quality=45)],
                p=0.55,
            ),
            transforms.RandomApply(
                [transforms.GaussianBlur(kernel_size=3, sigma=(0.1, 1.2))],
                p=0.15,
            ),
            transforms.RandomAdjustSharpness(sharpness_factor=1.6, p=0.12),
        ]
        color_probability = 0.35
        color_jitter = transforms.ColorJitter(
            brightness=0.12,
            contrast=0.12,
            saturation=0.08,
            hue=0.02,
        )
    else:
        spatial_transform = transforms.Resize(
            (IMAGE_SIZE, IMAGE_SIZE),
            interpolation=transforms.InterpolationMode.BICUBIC,
        )
        degradation_transforms = [
            transforms.RandomApply([RandomJpegCompression()], p=0.35),
        ]
        color_probability = 0.25
        color_jitter = transforms.ColorJitter(
            brightness=0.08,
            contrast=0.08,
            saturation=0.05,
        )

    train_transform = transforms.Compose([
        *degradation_transforms,
        spatial_transform,
        transforms.RandomHorizontalFlip(),
        transforms.RandomApply([color_jitter], p=color_probability),
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
    for block in model.features[-3:]:
        for parameter in block.parameters():
            parameter.requires_grad = True
    model.classifier[1] = nn.Linear(
        model.classifier[1].in_features,
        len(CLASS_NAMES),
    )
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
        batch_probabilities = torch.softmax(logits, dim=1)
        loss_sum += loss.item() * labels.size(0)
        correct += (logits.argmax(dim=1) == labels).sum().item()
        count += labels.size(0)
        probabilities.extend(batch_probabilities.cpu().tolist())
        labels_seen.extend(labels.cpu().tolist())

    probabilities = np.asarray(probabilities, dtype=float)
    labels_seen = np.asarray(labels_seen, dtype=int)
    per_class = {}
    for class_index, class_name in CLASS_NAMES.items():
        binary_labels = (labels_seen == class_index).astype(int)
        class_probabilities = probabilities[:, class_index]
        per_class[class_name] = {
            "auroc": roc_auc_score(binary_labels, class_probabilities),
            "average_precision": average_precision_score(
                binary_labels,
                class_probabilities,
            ),
            "expected_calibration_error": expected_calibration_error(
                class_probabilities,
                binary_labels,
            ),
        }
    return {
        "loss": loss_sum / count,
        "accuracy": correct / count,
        "minimum_class_auroc": min(
            metrics["auroc"] for metrics in per_class.values()
        ),
        "macro_auroc": sum(
            metrics["auroc"] for metrics in per_class.values()
        ) / len(per_class),
        "per_class": per_class,
        "count": count,
    }


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "training_outputs/evidence_authenticity_three_class_candidate.pth"
        ),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path(
            "training_outputs/evidence_authenticity_three_class_report.json"
        ),
    )
    parser.add_argument(
        "--exclude-provenance",
        type=Path,
        action="append",
        required=True,
        help="Repeat for every evaluation provenance CSV that must be excluded.",
    )
    parser.add_argument("--train-per-class", type=int, default=1600)
    parser.add_argument("--validation-per-class", type=int, default=300)
    parser.add_argument("--validation-fraction", type=float, default=0.18)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--patience", type=int, default=3)
    parser.add_argument("--buffer-size", type=int, default=8192)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument(
        "--augmentation-profile",
        choices=("basic", "forensic"),
        default="forensic",
        help=(
            "forensic adds local crops, resize degradation, stronger JPEG, "
            "mild blur, and sharpening; basic reproduces the earlier recipe."
        ),
    )
    parser.add_argument("--label-smoothing", type=float, default=0.05)
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
    if not 0.0 <= args.label_smoothing <= 0.2:
        raise ValueError("--label-smoothing must be between 0.0 and 0.2.")

    disable_caching()
    set_seed(args.seed)
    excluded_groups, provenance_files = load_excluded_groups(
        args.exclude_provenance
    )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    print(f"Reserved evaluation groups excluded: {len(excluded_groups)}")
    if device.type != "cuda":
        print("Warning: training is practical on a Colab GPU, not a local CPU.")

    train_transform, validation_transform = make_transforms(
        args.augmentation_profile
    )
    train_dataset = BalancedThreeClassStream(
        partition="train",
        per_class=args.train_per_class,
        transform=train_transform,
        excluded_groups=excluded_groups,
        seed=args.seed,
        buffer_size=args.buffer_size,
        validation_fraction=args.validation_fraction,
        synthetic_start=args.validation_per_class,
    )
    validation_dataset = BalancedThreeClassStream(
        partition="validation",
        per_class=args.validation_per_class,
        transform=validation_transform,
        excluded_groups=excluded_groups,
        seed=args.seed,
        buffer_size=args.buffer_size,
        validation_fraction=args.validation_fraction,
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
    criterion = nn.CrossEntropyLoss(label_smoothing=args.label_smoothing)
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

    best_score = -math.inf
    best_state = None
    epochs_without_improvement = 0
    history = []
    for epoch in range(1, args.epochs + 1):
        print(f"Epoch {epoch}/{args.epochs}")
        train_metrics = train_epoch(
            model, train_loader, criterion, optimizer, scaler, device
        )
        validation_metrics = evaluate(
            model, validation_loader, criterion, device
        )
        score = validation_metrics["minimum_class_auroc"]
        scheduler.step(score)
        record = {
            "epoch": epoch,
            "learning_rate": optimizer.param_groups[0]["lr"],
            "train": train_metrics,
            "validation": validation_metrics,
        }
        history.append(record)
        print(json.dumps(record, indent=2))
        if score > best_score + 1e-4:
            best_score = score
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
        "architecture": "EfficientNet-B0",
        "classes": CLASS_NAMES,
        "sources": {
            "authentic_and_tampered": {
                "dataset": TAMPER_DATASET,
                "split": TAMPER_SPLIT,
            },
            "synthetic": {
                "dataset": SYNTHETIC_DATASET,
                "split": SYNTHETIC_SPLIT,
            },
        },
        "partition": {
            "method": "sha256-source-group-and-shuffle-take-skip",
            "seed": args.seed,
            "validation_fraction": args.validation_fraction,
            "train_per_class": args.train_per_class,
            "validation_per_class": args.validation_per_class,
            "excluded_evaluation_groups": len(excluded_groups),
            "exclusion_provenance": provenance_files,
        },
        "selection_metric": "minimum_class_auroc",
        "training_recipe": {
            "augmentation_profile": args.augmentation_profile,
            "label_smoothing": args.label_smoothing,
            "inference_candidate": "GLOBAL_PLUS_FIVE_PATCHES_MEAN_V1",
        },
        "best_validation_minimum_class_auroc": best_score,
        "history": history,
        "checkpoint": str(args.output),
        "promotion_status": "CANDIDATE_REQUIRES_EXTERNAL_CALIBRATION",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Candidate checkpoint: {args.output}")
    print(f"Training report: {args.report}")
    print("Do not promote until a new external TrustLens audit passes.")


if __name__ == "__main__":
    main()
