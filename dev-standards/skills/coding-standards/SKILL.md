---
name: coding-standards
description: Coding standards for writing or reviewing code in any of tatoflam's repositories — names the references to follow (OWASP ASVS, CWE Top 25, PEP 8, Google Shell Style) and explains the dev-standards edit hook and how to suppress a false positive narrowly. Use when writing new code, when the dev-standards hook reports findings, or when asked about coding rules / セキュアコーディング / 規約.
---

# コーディング規約


長い規約文は書かない。**拠り所を名指しし、機械で検査できるものは機械に任せる。**

| 対象 | 拠り所 |
|---|---|
| セキュリティ全般 | OWASP ASVS（検証要件）・CWE Top 25（典型的な弱点） |
| Python | PEP 8 / PEP 20。型ヒントは公開関数に付ける |
| シェル | Google Shell Style Guide。`set -euo pipefail` を基本に、変数は必ず `"$var"` で引用する |

- **秘密を書かない。**鍵・トークン・パスワードは環境変数か秘密管理から読む。例やテストでも本物の形をした値を置かない
- **外部入力を信用しない。**`shell=True`・`eval`・文字列連結の SQL・`pickle` / `yaml.load` の信頼できない入力を使わない。サブプロセスは引数のリストで渡す
- **効率は計測してから。**ただし O(n²) の素朴なループ・ループ内の I/O・同じものの再計算は書いた時点で避ける

## 編集ごとの検査（hook）

`Edit` / `Write` のたびに `.claude/hooks/check-edit.py` が ruff（pyflakes・bugbear・bandit 規則）・shellcheck（warning 以上）・gitleaks を回し、
**その編集で増えた指摘だけ**を返す（秘密は既存でも返す）。返ってきたら直す。誤検知なら理由を書いたうえで**いちばん狭い形で**抑止する:

```python
subprocess.run(cmd)  # noqa: S603 — cmd は固定の引数リスト
```
```bash
# shellcheck disable=SC2086  # 単語分割を意図している
```
```python
EXAMPLE = "AKIA..."  # gitleaks:allow — ドキュメント用のダミー
```

ファイル全体・規則全体を黙らせない。ブランチ単位の見直しは `/security-review`（PR の前）。役割を分ける: hook は 1 編集、`/security-review` は差分全体。

このリポジトリに `.claude/hooks/check-edit.py` が無い場合は、プラグインの同じ hook が動いている（ローカルのみ）。
クラウド（claude.ai/code）でも効かせるにはリポジトリに同期する: `dev-standards/scripts/sync-repo.sh <repo>`。
