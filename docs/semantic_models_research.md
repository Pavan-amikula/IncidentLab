# Compact semantic models: source-verified selection

Checked 2026-10-05. Recommendation: use a frozen MiniLM encoder for log novelty features and an optional Qwen narrator for evidence summaries. No installation, training, throughput benchmark, or target-runtime compatibility test was performed for this note.

## Models and immutable provenance

| Role | Model ID | Pinned repository revision | License |
|---|---|---|---|
| Text/log embeddings | `sentence-transformers/all-MiniLM-L6-v2` | `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` | Apache-2.0 |
| Optional instruction-following explanations | `Qwen/Qwen3-0.6B` | `c1899de289a04d12100db370d81485cdf75e47ca` | Apache-2.0 |

Revision and license fields were fetched directly from the first-party [MiniLM model API](https://huggingface.co/api/models/sentence-transformers/all-MiniLM-L6-v2?blobs=true) and [Qwen model API](https://huggingface.co/api/models/Qwen/Qwen3-0.6B?blobs=true). These APIs describe the observed repository state; use the full commit hashes above instead of mutable `main`. The Hub supports revision-specific downloads. [Hub download guide](https://huggingface.co/docs/huggingface_hub/guides/download)

The observed `model.safetensors` file metadata was:

| Model | Bytes | LFS SHA-256 |
|---|---:|---|
| MiniLM | 90,868,376 | `53aa51172d142c89d9012cce15ae4d6cc0ca6895895114379cacb4fab128d9db` |
| Qwen | 1,503,300,328 | `f47f71177f32bcd101b7573ec9171e6a57f4f4d31148d38e382306f42996874b` |

These are API-reported artifact hashes, not locally verified downloads. Git `blobId` differs from an artifact's SHA-256. Record local SHA-256 for every downloaded tokenizer/config/weight file, package versions, CUDA/device/dtype, normalization version, input-data hashes, training split IDs, thresholds, pooling, sequence cap, and explanation prompt/generation settings in run manifests. This is a provenance recommendation, not a claim of completed verification. [Hub API reference](https://huggingface.co/docs/huggingface_hub/package_reference/hf_api)

## Encoder usage

MiniLM outputs 384-dimensional vectors and targets sentence/short-paragraph similarity. Its card specifies mask-aware mean pooling followed by L2 normalization; its sentence-transformer configuration caps sequences at 256 tokens. Raw Transformers tokenization should explicitly apply that cap. [MiniLM card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2), [pinned sequence configuration](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/blob/1110a243fdf4706b3f48f1d95db1a4f5529b4d41/sentence_bert_config.json)

```python
import torch
import torch.nn.functional as F
from transformers import AutoModel, AutoTokenizer

repo = "sentence-transformers/all-MiniLM-L6-v2"
revision = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
device = "cuda" if torch.cuda.is_available() else "cpu"
tokenizer = AutoTokenizer.from_pretrained(repo, revision=revision)
encoder = AutoModel.from_pretrained(
    repo, revision=revision, use_safetensors=True
).to(device).eval()

def embed(texts):
    inputs = tokenizer(texts, padding=True, truncation=True,
                       max_length=256, return_tensors="pt").to(device)
    with torch.inference_mode():
        tokens = encoder(**inputs).last_hidden_state.float()
        mask = inputs["attention_mask"].unsqueeze(-1).float()
        pooled = (tokens * mask).sum(1) / mask.sum(1).clamp_min(1e-9)
        return F.normalize(pooled, p=2, dim=1).cpu()
```

## Optional local explanation model

Qwen is post-trained and supports chat templates with thinking disabled. Its card requires Transformers >=4.51.0 and recommends non-thinking sampling temperature 0.7, top-p 0.8, top-k 20. The example below deliberately bounds output for concise evidence narration. [Qwen card](https://huggingface.co/Qwen/Qwen3-0.6B)

```python
from transformers import AutoModelForCausalLM, AutoTokenizer

repo = "Qwen/Qwen3-0.6B"
revision = "c1899de289a04d12100db370d81485cdf75e47ca"
tokenizer = AutoTokenizer.from_pretrained(repo, revision=revision)
dtype = (torch.bfloat16 if device == "cuda" and torch.cuda.is_bf16_supported()
         else torch.float16 if device == "cuda" else torch.float32)
llm = AutoModelForCausalLM.from_pretrained(
    repo, revision=revision, dtype=dtype, use_safetensors=True
).to(device).eval()
messages = [
    {"role": "system", "content": "Summarize supplied evidence only. Separate observations from hypotheses. Do not invent causes."},
    {"role": "user", "content": evidence_text},
]
text = tokenizer.apply_chat_template(messages, tokenize=False,
                                     add_generation_prompt=True,
                                     enable_thinking=False)
inputs = tokenizer(text, add_special_tokens=False,
                   return_tensors="pt").to(device)
with torch.inference_mode():
    ids = llm.generate(**inputs, max_new_tokens=256, do_sample=True,
                       temperature=0.7, top_p=0.8, top_k=20)
answer = tokenizer.decode(ids[0, inputs.input_ids.shape[1]:],
                          skip_special_tokens=True)
```

Modern Transformers documents the `dtype` model-loading option. Older supported releases may use `torch_dtype` instead; pin and test the installed version. Avoid `device_map="auto"` here to avoid requiring Accelerate. Both architectures have native Transformers support. [Model-loading API](https://huggingface.co/docs/transformers/main_classes/model)

The Qwen card advertises 32,768 context tokens, while the pinned config has `max_position_embeddings=40960`; use a conservative explicit application prompt cap (for example 2,048 tokens) and retain raw evidence separately. [Pinned Qwen configuration](https://huggingface.co/Qwen/Qwen3-0.6B/blob/c1899de289a04d12100db370d81485cdf75e47ca/config.json)

The small weight files make both reasonable candidates for a 16 GB GPU, but file size is not measured VRAM consumption: activations, KV cache, batch size, driver support, and other models matter. No source reviewed validates the exact Windows/Python 3.14/PyTorch 2.11/cu128 combination. Transformers broadly documents Python 3.10+ and PyTorch 2.5+ testing; the actual environment still needs import, CUDA, embedding, and generation smoke checks. [Transformers installation documentation](https://huggingface.co/docs/transformers/installation)

## What healthy-only training establishes

Novelty detection learns a reference distribution from clean observations and scores unseen deviations; it does not supply fault labels. [scikit-learn novelty detection documentation](https://scikit-learn.org/stable/modules/outlier_detection.html)

Project inference: a frozen general-language encoder plus a detector trained on healthy logs can support semantic novelty, nearest healthy examples, and corroborating evidence. It does not establish causal root diagnosis. General-text pretraining is not validation on this project's log dialect; long entries lose text after the cap; numeric identifiers, negation, rare templates, and paraphrases need empirical checks. Normal operation changes can also be novel, and faulty events can resemble healthy text. Keep original log line IDs and timestamps; join semantic evidence with telemetry and timing; report causes as hypotheses unless independently confirmed. Qwen-generated summaries should not determine anomaly labels, fabricate probabilities, or upgrade novelty to a causal claim. These are methodological conclusions, not model benchmark results.

## Additional development comparison: Qwen3-1.7B

Checked 2026-10-05 from the first-party [Qwen3-1.7B model API](https://huggingface.co/api/models/Qwen/Qwen3-1.7B?blobs=true). Pin `Qwen/Qwen3-1.7B` to **`70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`**. Its metadata declares Apache-2.0; the repository includes the [pinned license](https://huggingface.co/Qwen/Qwen3-1.7B/blob/70d244cc86ccca08cf5af4e1e306ecf908b1ad5e/LICENSE).

There is no single `model.safetensors` file: the pinned repository has two shards plus an index. The [revision-specific API](https://huggingface.co/api/models/Qwen/Qwen3-1.7B/revision/70d244cc86ccca08cf5af4e1e306ecf908b1ad5e?blobs=true) reports:

| File | Bytes | LFS SHA-256 |
|---|---:|---|
| `model-00001-of-00002.safetensors` | 3,441,185,608 | `169ad53ec313c3a34b06c0809216e4fc072cce444a5d4ff2b59690d064130ed5` |
| `model-00002-of-00002.safetensors` | 622,329,984 | `912becff8d60672aa8628ef08c05898d9adf17c2ad4ae3caf99b065622fdeff9` |

Total shard size: 4,063,515,592 bytes. `model.safetensors.index.json` is 25,605 bytes, Git blob `986d7db875b47d21f68530f6baac038f1b297b39`; this Git blob identifier is not a SHA-256 download checksum. Hash all three downloaded files locally before recording verification.

The model card describes a post-trained causal language model, a 32,768-token context, and native Qwen3 support requiring Transformers >=4.51.0. It supports the same thinking switch as the smaller model. [Qwen3-1.7B card](https://huggingface.co/Qwen/Qwen3-1.7B)

The pinned [tokenizer configuration](https://huggingface.co/Qwen/Qwen3-1.7B/blob/70d244cc86ccca08cf5af4e1e306ecf908b1ad5e/tokenizer_config.json) includes a Jinja chat template. Its generation prefix is `<|im_start|>assistant\n`; with `enable_thinking=False`, it appends an empty `<think>\n\n</think>\n\n` block to the **input** prefix. Use `apply_chat_template(..., tokenize=False, add_generation_prompt=True, enable_thinking=False)` followed by tokenization with `add_special_tokens=False`, exactly as above; change only the model ID and revision. Both Qwen repositories observed here have identical `tokenizer_config.json` Git blob `417d038a63fa3de29cfde265caedae14d1a58d92`.

This pin is a candidate for a fresh development comparison, not evidence of improved log diagnosis. No source reviewed establishes that it fixes structural output rejection or false reviews of healthy logs. Compare those measured outcomes on new native trials with the same prompt, evidence selection, output validator, generation settings, and error accounting. Keep selection trials separate from final evaluation. These are experimental-design recommendations; no larger-model execution or download was performed for this addendum.
