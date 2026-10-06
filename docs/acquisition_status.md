# Verified acquisition — 5 October 2026

All three selected full releases are on disk in `data/research/`. They were not randomly sampled.

| Dataset | Locally verified acquisition |
|---|---|
| RCAEval | 2,080 files, 3,442,007,684 bytes; pinned revision `afeacb11bcc94dadfd1c8f483ee4377b2b8b614e`; SHA-256 for every file. |
| OpenStack | Complete archive and extracted logs; 207,820 actual log lines; four labeled VM instance identifiers; published archive MD5 matched. |
| AnoMod | Complete 201,917,396-byte archive; 38,349 file entries; 3,076,340,723 expanded bytes; published archive MD5 matched. Extractor supports long Windows paths. |

RCAEval audit: 735 cases, 1,335 Parquet files including the index, zero missing expected telemetry files and zero row-count mismatches with the index. RE2 contains 43,631,464 log rows and 101,806,286 trace rows; RE3 contains 6,021,307 log rows and 8,907,766 trace rows. These counts represent telemetry observations, not independent failures. RE1 is metric-only. Sock Shop has no traces; one RE2 case has no logs, matching declared metadata.

Sources: [maintainer RCAEval release](https://huggingface.co/datasets/phamquiluan/RCAEval), [OpenStack deposit](https://zenodo.org/records/8196385), [AnoMod author deposit](https://zenodo.org/records/18342898).

Local evidence: `data/research/RCAEval.provenance.json`, `data/research/OpenStack.tar.gz.provenance.json`, `data/research/AnoMod.zip.provenance.json`, and `artifacts/research/data_audit.json`.

Paper review and architecture decisions are in `docs/literature_review.md` and `docs/project_specification.md`. The first conventional full-data baseline has now been trained, calibrated and tested; see `docs/baseline_results.md`. The separate dashboard on port 8768 replays actual held-out telemetry. The earlier dashboard on port 8767 remains the synthetic fixture.
