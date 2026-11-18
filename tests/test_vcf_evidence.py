import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.vcf_evidence import (
    parse_vcf_variants, count_variants, variants_by_quality_threshold,
    variants_near_position, find_extra_variants,
    classify_variant_type, classify_all_extra_variants,
)

FIXTURE = os.path.join(os.path.dirname(__file__), "fixture.vcf")


def test_parse_vcf_variants_real_file():
    variants = parse_vcf_variants(FIXTURE)
    assert len(variants) == 6
    assert variants[0]["pos"] == 1000
    assert variants[0]["ref"] == "A"
    assert variants[0]["alt"] == "T"
    assert variants[0]["qual"] == 250.0


def test_count_variants():
    assert count_variants(FIXTURE) == 6


def test_variants_by_quality_threshold_splits_correctly():
    above, below = variants_by_quality_threshold(FIXTURE, min_qual=100.0)
    assert len(above) == 3
    assert len(below) == 3
    assert all(v["qual"] >= 100.0 for v in above)
    assert all(v["qual"] < 100.0 for v in below)


def test_variants_near_position_finds_cluster():
    # the three low-QUAL variants are clustered around position 4000-4020
    nearby = variants_near_position(FIXTURE, position=4010, window=50)
    assert len(nearby) == 3


def test_variants_near_position_empty_when_isolated():
    nearby = variants_near_position(FIXTURE, position=1000, window=10)
    assert len(nearby) == 1  # only itself


def test_find_extra_variants_identifies_lowest_qual():
    result = find_extra_variants(FIXTURE, published_count=3)
    assert result["n_extra"] == 3
    extra_positions = {v["pos"] for v in result["extra_variants"]}
    # the 3 deliberately low-QUAL variants should be flagged as the "extra" ones
    assert extra_positions == {4000, 4010, 4020}


def test_find_extra_variants_no_discrepancy():
    result = find_extra_variants(FIXTURE, published_count=6)
    assert result["n_extra"] == 0
    assert result["extra_variants"] == []


def test_find_extra_variants_negative_discrepancy_handled():
    # published count HIGHER than observed - shouldn't crash
    result = find_extra_variants(FIXTURE, published_count=100)
    assert result["n_extra"] == 0


def test_classify_variant_type_snp():
    assert classify_variant_type("A", "T") == "SNP"


def test_classify_variant_type_indel_insertion():
    assert classify_variant_type("A", "ATG") == "INDEL"


def test_classify_variant_type_indel_deletion():
    assert classify_variant_type("ATG", "A") == "INDEL"


def test_classify_variant_type_multiallelic():
    assert classify_variant_type("A", "T,G") == "multi-allelic"


def test_classify_all_extra_variants_all_same_type():
    # all 3 fixture "extra" variants (lowest-QUAL) are SNPs in the fixture
    result = classify_all_extra_variants(FIXTURE, published_count=3)
    assert result["n_extra"] == 3
    assert result["all_same_type"] is True
    assert result["type_counts"] == {"SNP": 3}


def test_classify_all_extra_variants_checks_every_one_not_just_one():
    # this is the actual fix: verify the function reports on ALL extra
    # variants, not a single spot-checked example
    result = classify_all_extra_variants(FIXTURE, published_count=3)
    assert len(result["extra_variants_classified"]) == 3
    assert sum(result["type_counts"].values()) == 3
