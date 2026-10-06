# Third-party data and provenance

The author's project source, measured testbed evidence and documentation are distinct from external datasets and libraries. No blanket license is applied to third-party material.

## RCAEval

Luan Pham, Hongyu Zhang, Huong Ha, Flora Salim and Xiuzhen Zhang, “RCAEval: A Benchmark for Root Cause Analysis of Microservice Systems with Telemetry Data,” arXiv:2412.17015 (2024, revised 2025), DOI 10.48550/arXiv.2412.17015.

- Dataset card and declared MIT license: https://huggingface.co/datasets/phamquiluan/RCAEval
- Maintainer repository: https://github.com/phamquiluan/RCAEval
- Original record: https://zenodo.org/records/14590730

Included processed Parquet features are transformations of the acquired telemetry: aggregation, causal warm-up normalization, modality features and explicit partition assignments. They are not a newly authored source dataset. Acquisition/preparation reports retain release references and hashes.

## AnoMod

Source: EvoTestOps/AnoMod and author deposit https://zenodo.org/records/18342898 . The recorded dataset license is CC BY 4.0; source-code licensing is distinct. License: https://creativecommons.org/licenses/by/4.0/ . Included processed inputs are transformations for external/development evaluation; preserve attribution and negative results. The original large raw archive is not included.

## OpenStack / Loghub

OpenStack log investigations use the Loghub source identified in the acquisition and research notes. See https://github.com/logpai/loghub and the original acquisition provenance. Raw log collections are not redistributed in this edition. Saved analysis/checkpoints do not transfer ownership of upstream data.

## Libraries

PyTorch, scikit-learn, FastAPI, NumPy, SciPy, PyArrow, Drain3, Docker, Kubernetes and kind retain their respective licenses. Dependencies are installed from their official/package-registry sources rather than vendored here.

## Historical provenance

`docs/provenance/` retains the original README, transfer manifest and amendment manifest. Some original paths refer to the college PC. Publication packaging omits local databases and transient logs; `repository_manifest.json` is the inventory for this edition.
