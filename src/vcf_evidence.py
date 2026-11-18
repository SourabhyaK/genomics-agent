"""
Real, deterministic evidence-gathering functions the agents call as tools.
These don't need an LLM at all - they're the actual ground-truth checks
against your real VCF/BAM files from the variant-calling pipeline.

Point VCF_PATH at your real results/vcf/SRR2584866_final_variants.vcf
from the variant-calling repo to investigate the real 766-vs-775 discrepancy.
"""
from pathlib import Path


def parse_vcf_variants(vcf_path: str) -> list[dict]:
    """Parse a VCF file into a list of variant records (real parsing, no mocking)."""
    variants = []
    with open(vcf_path) as f:
        for line in f:
            if line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 8:
                continue
            variants.append({
                "chrom": fields[0],
                "pos": int(fields[1]),
                "ref": fields[3],
                "alt": fields[4],
                "qual": float(fields[5]) if fields[5] != "." else None,
                "filter": fields[6],
                "info": fields[7],
            })
    return variants


def count_variants(vcf_path: str) -> int:
    return len(parse_vcf_variants(vcf_path))


def variants_by_quality_threshold(vcf_path: str, min_qual: float) -> tuple[list[dict], list[dict]]:
    """Split variants into (above threshold, below threshold) by QUAL score.
    Tests hypothesis: 'the 9 extra variants are low-confidence calls near
    a quality cutoff that differs between tool versions.'"""
    variants = parse_vcf_variants(vcf_path)
    above = [v for v in variants if v["qual"] is not None and v["qual"] >= min_qual]
    below = [v for v in variants if v["qual"] is None or v["qual"] < min_qual]
    return above, below


def variants_near_position(vcf_path: str, position: int, window: int = 50) -> list[dict]:
    """Find variants clustered near a given genomic position.
    Tests hypothesis: 'the extra variants cluster in a repetitive region
    where alignment is ambiguous.'"""
    variants = parse_vcf_variants(vcf_path)
    return [v for v in variants if abs(v["pos"] - position) <= window]


def classify_variant_type(ref: str, alt: str) -> str:
    """Classify a variant by REF/ALT: SNP (single base change), multi-allelic
    (comma-separated ALTs), or INDEL (insertion/deletion, different lengths)."""
    if "," in alt:
        return "multi-allelic"
    if len(ref) == 1 and len(alt) == 1:
        return "SNP"
    return "INDEL"


def classify_all_extra_variants(observed_vcf: str, published_count: int) -> dict:
    """The rigorous version: classifies EVERY extra variant by type, not just
    one example, so a hypothesis like 'these are all INDELs/multi-allelic'
    can be checked against the full set rather than a single spot-check."""
    result = find_extra_variants(observed_vcf, published_count)
    if result["n_extra"] == 0:
        return {**result, "type_counts": {}, "all_same_type": None}

    classified = []
    for v in result["extra_variants"]:
        v_type = classify_variant_type(v["ref"], v["alt"])
        classified.append({**v, "variant_type": v_type})

    type_counts = {}
    for v in classified:
        type_counts[v["variant_type"]] = type_counts.get(v["variant_type"], 0) + 1

    all_same_type = len(type_counts) == 1

    return {
        "n_extra": result["n_extra"],
        "extra_variants_classified": classified,
        "type_counts": type_counts,
        "all_same_type": all_same_type,
        "note": (f"Of {result['n_extra']} extra variants, type breakdown: {type_counts}. "
                 f"{'All share the same type.' if all_same_type else 'Mixed types - not a single clean pattern.'}"),
    }


def find_extra_variants(observed_vcf: str, published_count: int) -> dict:
    """The actual diagnostic entry point: given your real observed VCF and
    the published benchmark count, identify which specific variants are
    the 'extra' ones (by QUAL, sorted ascending - the discrepancy is most
    likely the lowest-confidence calls)."""
    variants = parse_vcf_variants(observed_vcf)
    n_extra = len(variants) - published_count
    if n_extra <= 0:
        return {"n_extra": 0, "extra_variants": [], "note": "No discrepancy found."}
    sorted_by_qual = sorted(variants, key=lambda v: (v["qual"] is None, v["qual"] or 0))
    extra = sorted_by_qual[:n_extra]
    return {
        "n_extra": n_extra,
        "extra_variants": extra,
        "note": f"Lowest-QUAL {n_extra} variants, candidates for the discrepancy.",
    }
