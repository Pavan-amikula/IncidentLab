"""Pinned local neural models. Remote custom code is disabled."""
import hashlib
import json
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModel, AutoModelForCausalLM, AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
MODELS = {
    'encoder': ('sentence-transformers/all-MiniLM-L6-v2', '1110a243fdf4706b3f48f1d95db1a4f5529b4d41',
                '53aa51172d142c89d9012cce15ae4d6cc0ca6895895114379cacb4fab128d9db'),
    'llm': ('Qwen/Qwen3-0.6B', 'c1899de289a04d12100db370d81485cdf75e47ca',
            'f47f71177f32bcd101b7573ec9171e6a57f4f4d31148d38e382306f42996874b'),
    'llm_medium': ('Qwen/Qwen3-1.7B', '70d244cc86ccca08cf5af4e1e306ecf908b1ad5e', {
        'model-00001-of-00002.safetensors': '169ad53ec313c3a34b06c0809216e4fc072cce444a5d4ff2b59690d064130ed5',
        'model-00002-of-00002.safetensors': '912becff8d60672aa8628ef08c05898d9adf17c2ad4ae3caf99b065622fdeff9'})}
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'


def file_sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def download(role):
    from huggingface_hub import snapshot_download
    repo, revision, expected = MODELS[role]
    directory = ROOT/'models'/role
    snapshot_download(repo_id=repo, revision=revision, local_dir=directory,
        allow_patterns=['*.json', '*.txt', '*.safetensors', 'LICENSE', 'README.md'])
    weights = expected if isinstance(expected, dict) else {'model.safetensors': expected}
    for name, weight_sha in weights.items():
        if file_sha(directory/name) != weight_sha:
            raise RuntimeError(f'{role}/{name} hash differs from publisher LFS hash')
    files = {str(path.relative_to(directory)): file_sha(path)
             for path in directory.rglob('*') if path.is_file() and '.cache' not in path.parts
             and path.name != 'provenance.json'}
    (directory/'provenance.json').write_text(json.dumps(dict(repo=repo, revision=revision,
        license='Apache-2.0', files=files, weight_sha256_verified=True), indent=2), encoding='utf-8')
    return directory


class Encoder:
    def __init__(self):
        directory = ROOT/'models/encoder'
        self.tokenizer = AutoTokenizer.from_pretrained(directory, local_files_only=True, trust_remote_code=False)
        self.model = AutoModel.from_pretrained(directory, local_files_only=True,
            trust_remote_code=False, use_safetensors=True).to(DEVICE).eval()

    def embed(self, texts, batch_size=64):
        vectors = []
        for start in range(0, len(texts), batch_size):
            encoded = self.tokenizer(texts[start:start+batch_size], padding=True,
                truncation=True, max_length=256, return_tensors='pt').to(DEVICE)
            with torch.inference_mode():
                tokens = self.model(**encoded).last_hidden_state.float()
                mask = encoded['attention_mask'].unsqueeze(-1).float()
                pooled = (tokens*mask).sum(1)/mask.sum(1).clamp_min(1e-9)
                vectors.append(torch.nn.functional.normalize(pooled, p=2, dim=1).cpu().numpy())
        return np.concatenate(vectors) if vectors else np.empty((0, 384), dtype=np.float32)


class LocalLLM:
    def __init__(self, role='llm'):
        self.role = role
        self.model_id, self.revision = MODELS[role][:2]
        directory = ROOT/'models'/role
        self.tokenizer = AutoTokenizer.from_pretrained(directory, local_files_only=True, trust_remote_code=False)
        self.model = AutoModelForCausalLM.from_pretrained(directory, local_files_only=True,
            trust_remote_code=False, use_safetensors=True,
            dtype=torch.float16 if DEVICE == 'cuda' else torch.float32).to(DEVICE).eval()

    def generate(self, system, user, max_tokens=256):
        text = self.tokenizer.apply_chat_template([dict(role='system', content=system),
            dict(role='user', content=user)], tokenize=False, add_generation_prompt=True, enable_thinking=False)
        inputs = self.tokenizer(text, return_tensors='pt', truncation=True, max_length=2048).to(DEVICE)
        with torch.inference_mode():
            output = self.model.generate(**inputs, max_new_tokens=max_tokens, do_sample=False,
                pad_token_id=self.tokenizer.eos_token_id)
        return self.tokenizer.decode(output[0, inputs['input_ids'].shape[1]:], skip_special_tokens=True), {
            'input_tokens': int(inputs['input_ids'].shape[1]),
            'output_tokens': int(output.shape[1]-inputs['input_ids'].shape[1])}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('role', choices=('encoder', 'llm', 'llm_medium', 'both'))
    args = parser.parse_args()
    for role in ('encoder', 'llm') if args.role == 'both' else (args.role,):
        print(f'Downloading and verifying {role}: {MODELS[role][0]}', flush=True)
        print(download(role), flush=True)
