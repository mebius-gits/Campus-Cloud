# Teacher Judge Script Executor Execution Phase Plan

## 問題理解

本階段要把 Teacher Judge 已保存並核准的 managed script，實際送到群組內指定 VM/LXC 執行，回收 structured JSON 結果並保存到資料庫。

目前已存在的基礎：

- 腳本 artifact 存在 `teacher_judge_script_artifacts`，其中 `script_content` 是要上傳執行的 Python managed script。
- 執行紀錄表 `teacher_judge_script_runs` 已存在，含 `target_snapshot_json`、`progress_json`、`result_summary_json`、`target_results_json`。
- 後端已有 `POST /api/v1/groups/{group_id}/judge/scripts/{script_id}/runs` 可建立 run，但目前只建立 `pending` 紀錄，尚未真正 SSH 執行。
- 群組 VMID 解析目前可透過 `group -> batch_provision_jobs -> batch_provision_tasks -> resources` 邊界確認。
- AI-PVE 已有 SSH 執行參考，但 Teacher Judge 應新增專用 executor service，不把腳本執行責任塞進 AI chat flow。

本輪產品決策：第一版只支援老師手動指定目標 VM/LXC，不開放全群組自動執行或 running-only 自動掃描。

已確認的執行預設：

- SSH 登入帳號第一版固定使用 `root`。
- SSH 認證使用資料庫中 `resources.ssh_private_key_encrypted` 解密後的私鑰。
- 目標 VM/LXC 沒有 `python3` 時，該 target 標記為 `failed`，第一版不自動安裝 Python 或其他依賴。
- 單次 run 最大 target 數量預設為 5。
- SSH 執行並發數預設為 5。
- 每台 target 的執行結果保存上限採用：stdout 16KB、stderr 16KB、raw `result.json` 256KB。
- 背景執行第一版接專案既有 `app.infrastructure.worker.submit_sync`，不使用 FastAPI 內建 `BackgroundTasks`。
- 第一版不提供原始 JSON 下載，只確認後端能接收並保存 JSON，前端能顯示 valid/invalid 與 parsed JSON。
- 第一版先不自動清理遠端暫存目錄，保留後續補 cleanup / retention policy 的註解。
- 第一版不新增 `executor_error` 或 `cancel_requested_at` 欄位，後續若要取消或更完整的 executor error tracking 再補 schema。
- 第一版不拆 `teacher_judge_script_run_results`，先以 `target_results_json` 跑通測試 JSON 接收鏈條。

## 影響範圍

後端：

- `backend/app/ai/teacher_judge/script_run_service.py`
- 新增 Teacher Judge 專用 executor service，例如 `backend/app/ai/teacher_judge/script_executor_service.py`
- `backend/app/api/routes/teacher_judge_scripts.py`
- `backend/app/models/teacher_judge_script_run.py` 視需求小幅補欄位或維持 JSON 欄位
- `backend/app/ai/teacher_judge/script_policy.py` 的 `validate_managed_script_output()`
- 可能共用 `backend/app/infrastructure/ssh/client.py` 或 AI-PVE 現有 SSH DB 解析邏輯

前端：

- 群組 AI 檢測腳本頁的 run 建立 UI
- 目標 VM/LXC 手動勾選
- run progress polling
- JSON 結果解析與錯誤顯示

資料庫：

- 第一版優先沿用 `teacher_judge_script_runs.target_results_json`
- 若結果量變大，再另開 `teacher_judge_script_run_results`
- 不改動 `teacher_judge_script_artifacts.script_content` 的儲存方式

## 建議方案

採用「建立 run 後由後端背景 executor 執行，前端 polling 查看進度」。

```text
老師選擇 approved script
-> 老師手動勾選 group 內指定 VM/LXC
-> POST create run
-> 後端建立 teacher_judge_script_runs
-> 背景 executor 逐台 SSH 執行
-> 上傳 script.py 到 /tmp/campus-cloud-judge/<run_id>/
-> 遠端執行 python3 script.py > result.json
-> 抓回 result.json / stdout / stderr 摘要
-> validate_managed_script_output()
-> 寫入 target_results_json / result_summary_json / progress_json
-> 前端 polling 並解析顯示 JSON 是否格式正確
```

建議第一版不要讓 managed script 自己寫檔。既有腳本契約已要求最後以 stdout 輸出單一 JSON，因此 executor 在遠端用 shell redirect 產生 `result.json` 即可：

```bash
python3 script.py > result.json 2> stderr.log
```

這樣 managed script 仍維持只讀收集與 stdout JSON 輸出，不需要放寬目前禁止檔案寫入的安全政策。

## 實作步驟

1. 確認 target 解析邊界
   - `target_scope` 第一版固定只接受 `manual`
   - 後端不得信任前端 VMID 清單，必須每次從 DB 重查
   - 每個 VMID 必須同時符合：
     - 來自該 `group_id` 的 completed batch task
     - `resources.vmid` 仍存在
     - `resources.user_id` 等於該 group member user
     - live Proxmox 狀態是 `running`
     - resource 有可用 IP 與 SSH private key

2. 建立 executor service
   - 輸入：`session`、`run_id`
   - 載入 run、artifact、targets snapshot
   - 若 artifact 不是 `approved`，拒絕執行
   - 將 run 狀態更新為 `running`
   - 逐台 target 執行，第一版最多 5 台 target，SSH 並發上限 5
   - 背景執行建議接專案既有 `app.infrastructure.worker.submit_sync`，不要使用 FastAPI 內建 `BackgroundTasks`

3. 單台 SSH 執行流程
   - 解析 target IP 與 SSH private key
   - 建立遠端目錄 `/tmp/campus-cloud-judge/<run_id>/<vmid>/`
   - 使用 SFTP 上傳 `script.py`
   - 執行 `python3 script.py > result.json 2> stderr.log`
   - 設定 timeout
   - 下載 `result.json` 與 `stderr.log`
   - 第一版先保留遠端暫存目錄，方便確認執行鏈條；後續再補 cleanup / retention policy

4. 結果驗證與保存
   - 對 `result.json` 呼叫 `validate_managed_script_output()`
   - JSON 正確時保存 parsed result
   - JSON 錯誤時保存 validation error、stdout/stderr 摘要與 exit code
   - stdout/stderr/result 都要設定保存上限，避免 DB 過大
   - 保存上限只限制執行結果，不影響 `teacher_judge_script_artifacts.script_content`；managed script 仍直接保存在資料庫
   - 第一版每台 target 保存上限：
     - stdout 摘要最多 16KB
     - stderr 摘要最多 16KB
     - raw `result.json` 文字最多 256KB
     - parsed JSON 驗證成功後保存結構化結果；若超過上限則標記 target failed 並保存錯誤摘要
   - 每台 target 的結果寫入 `target_results_json.targets[]`
   - 整體統計寫入 `result_summary_json`
   - polling 狀態寫入 `progress_json`

5. API 與前端
   - create run 後回傳 run public object
   - 補 run detail API，讓前端 polling 查詢最新狀態
   - 前端只顯示可執行的 running VM/LXC
- 前端顯示每台 target 狀態：queued、running、completed、failed
- 前端顯示 JSON 格式驗證：valid / invalid，並可展開 parsed JSON
- 第一版不提供原始 JSON 下載功能

## 驗證方式

後端單元測試：

- manual target 不是群組 VMID 時拒絕
- target 是舊 batch task 但 current resource owner 不一致時拒絕
- target stopped 時拒絕
- artifact 非 approved 時拒絕
- SSH 成功時保存 valid parsed result
- SSH exit code 非 0 時保存 failed target
- result JSON malformed 時保存 invalid validation result
- 單台失敗時其他 target 仍可繼續執行

整合或手動驗證：

- 建立 group、batch provision resource、approved artifact
- 前端指定 1 台 running LXC/VM 執行
- 確認 run 從 pending -> running -> completed
- 確認 `target_results_json` 有 parsed JSON
- 確認前端能顯示「JSON 格式正確」

環境驗證：

- 後端 lint：`uv run ruff check .`
- 後端 typecheck：`uv run mypy .`
- 後端測試需從專案根目錄執行：`bash ./scripts/test.sh`
- 前端 build 或相關 unit test：`bun run build` / `bun run test:unit`

## 風險與假設

風險：

- SSH private key 解密與使用必須只留在後端，不可回傳前端。
- VMID 可能被刪除後重用，所以不能只信 batch task 的歷史 VMID。
- managed script 即使通過靜態審查，執行期仍可能輸出非 JSON 或超大量內容。
- 遠端 VM/LXC 可能沒有 `python3`，第一版應回報 target failed，而不是自動安裝。
- 同時執行太多台會壓垮 backend worker 或 SSH 連線。
- 背景任務若被服務重啟中斷，run 可能停在 `running`，需要後續 stale run 修復策略。

假設：

- 第一版 SSH 使用者固定使用 `root`。
- 第一版 SSH private key 來自資料庫 `resources.ssh_private_key_encrypted`。
- 第一版只執行 approved Python managed script。
- 第一版目標沒有 `python3` 時標記 target failed，不自動安裝。
- 第一版 run result 先收斂存在 `teacher_judge_script_runs.target_results_json`。
- 第一版只做資料收集與 JSON 顯示，不自動回填正式成績。
- 第一版不開放老師手動編輯 script content。
- 第一版不新增 executor 專用欄位，executor error 與狀態補充先寫在 JSON 欄位。
- 第一版不拆 per-target result table，先驗證 JSON 能被後端接收、保存、前端解析。

## 後續補強備註

以下不列入第一版，但實作時應在對應程式碼附近留下短註解，避免後續忘記邊界：

1. 遠端暫存目錄目前先保留；未來應補 cleanup / retention policy，避免 `/tmp/campus-cloud-judge/` 長期累積。
2. executor error 與 cancel request 第一版先放 JSON 欄位；未來若要支援取消、重試與更完整查詢，再補 `executor_error` / `cancel_requested_at` 等 schema 欄位。
3. per-target result table 第一版先不拆；未來若要支援全班大量執行、單台重跑、下載原始結果或長期稽核，再拆 `teacher_judge_script_run_results`。
4. 原始 JSON 下載第一版先不做；目前只要求後端接收到 JSON、驗證格式、保存結果，並讓前端顯示 parsed JSON。

## 第一版收斂結論

第一版 executor phase 建議只做到：

- 手動指定 group 內 running VM/LXC
- approved script 才能執行
- SSH 使用 `root` 搭配資料庫金鑰登入
- 單次 run 最大 target 數與 SSH 並發數都預設為 5
- SSH 上傳並執行 Python managed script
- 回收 stdout JSON 並驗證 `teacher_judge_result.v1`
- 保存 per-target 結果到 `target_results_json`
- 前端 polling 顯示進度與 JSON valid/invalid
- 第一版目標是讓測試 JSON 能被接收、驗證、保存與前端解析，先跑通 executor 鏈條

暫不做：

- 全群組自動執行
- running-only 自動掃描
- 自動安裝 Python 或依賴
- 自動清理遠端暫存目錄
- 原始 JSON 下載
- executor 專用錯誤/取消欄位
- LLM evidence judgement
- 成績回填
- 單台重跑
- per-target result table
