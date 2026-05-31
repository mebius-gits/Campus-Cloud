"""Teacher Judge managed script generation contract."""

from __future__ import annotations

RESULT_SCHEMA_VERSION = "teacher_judge_result.v1"
RAW_OUTPUT_CHAR_LIMIT = 400
SCRIPT_GENERATION_MAX_ATTEMPTS = 3

SCRIPT_GENERATION_CONTRACT_PROMPT = f"""
# 腳本品質契約
- 你產生的是受管資料收集腳本，不是自由發揮的診斷腳本；可讀性、可移植性、證據品質與狀態語意都必須穩定。
- 腳本目標是收集同學 VM/LXC 內的服務、port、process、localhost HTTP 等只讀資料，整理成單一 JSON。
- 腳本必須定義並使用這些 helper：`truncate_output`、`redact_sensitive_text`、`command_available`、`run_command`、`record_check`。
- `truncate_output(text, limit={RAW_OUTPUT_CHAR_LIMIT})` 必須將 raw 輸出截斷到固定長度。
- `redact_sensitive_text(text)` 必須遮罩 token、password、secret、api key、private key、bearer 等敏感字樣；不得使用裸 `key` 這種過度寬泛規則。建議使用下列結構：
  ```python
  def redact_sensitive_text(text: str) -> str:
      patterns = [
          (
              r"(?i)(password|passwd|secret|token|api_key|bearer|auth_token|access_token|private_key|ssh-rsa|id_rsa)\\s*[:=]\\s*[^\\s]+",
              r"\\1: [REDACTED]",
          ),
          (r"([a-f0-9]{32,})", "[REDACTED_HASH]"),
          (r"(\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3})", r"\\1"),
      ]
      redacted = text
      for pattern, replacement in patterns:
          redacted = re.sub(pattern, replacement, redacted)
      return redacted
  ```
- `command_available(command)` 必須用 `shutil.which(command)` 檢查外部工具是否存在。
- `run_command(argv, timeout=秒數)` 必須包裝 `subprocess.run([...], capture_output=True, text=True, check=False, timeout=...)`，並回傳包含 `stdout`、`stderr`、`returncode` 的 dict。
- `record_check(...)` 必須統一建立檢查結果，所有 `raw` 都必須先經過 `redact_sensitive_text` 與 `truncate_output`。

# 狀態語意
- `pass`：只有在必要條件被明確驗證成立時才能使用。
- `fail`：只有在必要條件被明確驗證不成立時才能使用。
- `warning`：收集大致可完成，但存在非阻斷異常、證據不完整、或結果有風險時使用。
- `unknown`：工具缺失、timeout、權限不足、解析失敗、環境差異導致無法判定時使用。
- `skipped`：此收集項目不適用目前 target/template 時使用。
- 只要 stdout / stderr 非空，不能直接判定為 `pass`。
- `command not found`、`FileNotFoundError`、`PermissionError`、`subprocess.TimeoutExpired` 不得判定為 `pass`。

# 可移植性與證據規則
- 優先使用 Python 標準函式庫；若需外部工具，先 `command_available()` 再執行。
- 若需執行外部指令，必須透過 `run_command()` 收集 stdout/stderr/returncode。
- 不要假設一定有 `systemctl`、`ss`、`curl`、`grep`；工具缺失時回 `unknown`。
- `evidence` 應是老師可讀的判斷摘要，不是原始輸出全文。
- `raw` 只能是必要片段，且必須經過脫敏與截斷；禁止直接保存完整 stdout/stderr。
- 發生例外時不能吞錯後標成 `pass`；應記錄到 `errors` 或回 `unknown` / `fail`。

# 結果契約
- 最後輸出單一 JSON，`schema_version` 固定為 `{RESULT_SCHEMA_VERSION}`。
- 最後必須使用 `json.dumps(..., ensure_ascii=False)`，避免繁體中文被 escape。
- 頂層 `metadata` 必須包含 `timestamp` 與 `platform`。
- 每個 check 需包含 `id`, `title`, `status`, `evidence`, `raw`。
- `id` 必須是語意化穩定 ID，例如 `runtime.python_version`、`service.n8n_port`，不可使用 `check-1`、`item-1`、`stable_check_id`。
- `title` 使用「收集」語意，例如「收集 Python 版本」、「收集 n8n 連接埠」，不要用「檢查」開頭。
- 允許狀態只有 `pass`, `fail`, `warning`, `unknown`, `skipped`。
""".strip()
