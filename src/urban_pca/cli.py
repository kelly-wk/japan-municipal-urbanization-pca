"""Command-line entry points."""

from __future__ import annotations

import argparse
from pathlib import Path

from .analysis import run_analysis
from .data import prepare_to_csv


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="urban-pca")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="Build the processed municipal CSV")
    prepare.add_argument("--source-2024", type=Path, required=True)
    prepare.add_argument("--source-2026", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)

    analyze = subparsers.add_parser("analyze", help="Run the complete PCA study")
    analyze.add_argument("--input", type=Path, required=True)
    analyze.add_argument("--output", type=Path, required=True)
    analyze.add_argument("--seed", type=int, default=20260929)
    analyze.add_argument("--bootstrap", type=int, default=1_000)
    analyze.add_argument("--validation-bootstrap", type=int, default=2_000)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "prepare":
        data = prepare_to_csv(args.source_2024, args.source_2026, args.output)
        print(
            f"prepared {len(data)} published rows; "
            f"{int(data['analysis_eligible'].sum())} primary analysis rows"
        )
    else:
        metrics = run_analysis(
            args.input,
            args.output,
            seed=args.seed,
            bootstrap=args.bootstrap,
            validation_bootstrap=args.validation_bootstrap,
        )
        print(
            f"analyzed {metrics['analysis_rows']} municipalities; "
            f"PC1 explained variance={metrics['pc1_explained_variance_ratio']:.3f}"
        )


if __name__ == "__main__":
    main()

