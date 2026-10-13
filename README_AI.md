# 本機同音詞排序：實驗原型

這是 opt-in 原型，安裝檔案本身不會啟用模型。保留現有臺灣詞庫、快捷鍵、
詞頻學習。模型僅重排前八個候選，不新增詞，也不訓練模型。

## 已實作與限制

- Python 背景程式使用 Qwen/Qwen2.5-0.5B 基礎模型，以中文每字平均 log 機率評分差異後綴。
- 不需要先按 Enter：空的已送出前文仍會送出請求。已選但未送出的前段也可作為上下文。
  整句候選的共同前綴會當作上下文，例如「我們達成公事／我們達成共識」比較末尾差異。
- 僅比较前四個中與首選涵蓋相同拼音範圍、且文字等長的候選。原順位帶有保守偏好；
  最高調整分數比次高至少高 0.6 才提升一個候選，其餘保持原順序。
  0.6 與順位偏好是未校準的啟發式門檻，不能當作準確率或模型信心。
- 快速輸入時直接讀取最新請求計算，不額外等待停止輸入，另加實際推論時間；不阻塞打字。
- 只重排 Rime 已提供的候選，不產生新的整句或拼音解碼路徑。
  如果前四個只有一個整句而其餘是短詞，就保留原順序，無法修正整句中的同音詞。
- Lua 用上屏通知記住最近 128 字，以本機檔案交換請求；不在 Rime 主執行緒等推論。
- 新請求會讓舊結果失效；無符合請求的結果時使用原排序。
- Windows 上模型完成後會自動通知 Rime 刷新；只在原視窗／控制項及請求仍有效時通知。
  其他平台或通知失敗時仍可手動刷新。
- 無候選時 Enter 清前文、有輸入組字時 Enter 保留；60 秒閒置清除。
- Ctrl+Shift+BackSpace 手動清除前文。
- Ctrl+Shift+R 保留為備用手動刷新。成功套用時第一個候選旁有 [AI]。
- **尚未實作 Windows TSF 周邊文字讀取、焦點追蹤、游標移動與刪字回溯。**
  Enter 在送出/換行之間仍是保守規則，切換視窗後請手動重置。
- 尚未完成 Windows 小狼毫端到端測試、真實模型準確率或延遲測試。
  0.5B 模型不是為拼音選字訓練的專用模型，效果可能不如 Rime 原排序。
- 首次下載模型約需 GB 級空間；CPU 推論可能較慢，支援 CUDA 時會使用 GPU。
- 模型下載需要連線，之後可用 --local-only 禁止下載。輸入只留在本機
  ai_bridge 的單份請求檔，不寫完整歷史日誌，不要把此資料夾放到雲端。

## Windows 測試安裝

先安裝 Python 3.10 或更新版。用 Plum 安裝 ai-rerank-sync-prototype 分支，
再開 PowerShell，以下假設用戶資料夾是預設的 $env:APPDATA\Rime。
使用目前環境的 Python（可為 Miniconda），不需要 py launcher。
若解析到 WindowsApps 別名，將 $rimePython 改成實際 python.exe 的完整路徑：

```powershell
$rimeUserDir = Join-Path $env:APPDATA 'Rime'
$rimePython = (Get-Command python -CommandType Application | Select-Object -First 1).Source
& $rimePython -m pip install -r "$rimeUserDir\tools\ai_rerank\requirements.txt"
& $rimePython "$rimeUserDir\tools\ai_rerank\setup.py" --user-dir "$rimeUserDir" --enable-ai
& $rimePython "$rimeUserDir\tools\ai_rerank\worker.py" --bridge-dir "$rimeUserDir\ai_bridge"
```

保留背景程式視窗，重新部署小狼毫。先直接輸入 womendachenggongshi，先不要按 Enter；也可先打「代入這個」並選字上屏，
再輸入 gongshi，稍等觀察候選是否自動更新且出現 [AI]；手動刷新仍可備用。依序確認數字選字、
組句、臺灣詞、標點及快捷鍵仍正常。停掉背景程式時應維持原排序。
第一版沒有開機自動啟動，以免未驗證的功能影響日常輸入。

停用（保留已學習字彙）：

```powershell
& $rimePython "$rimeUserDir\tools\ai_rerank\setup.py" --user-dir "$rimeUserDir" --disable-ai
```

重新部署。setup 修改前會備份原始 YAML，所有既有設定會保留。
若重新安裝 Plum 覆蓋 custom 檔，需再跑一次 --enable-ai。

## 雲端同步已學習字彙

使用 Rime 原生「用戶資料同步」產生及合併快照，不同步正在使用中的 userdb。
你需要已登入並正在運作的 OneDrive、Dropbox 或其他雲端資料夾。
本工具不登入雲端、不建立雲端帳號，也不將學習資料推到公開 GitHub。

例如指定你的實際同步資料夾（請自行替換）：

```powershell
& $rimePython "$rimeUserDir\tools\ai_rerank\setup.py" --user-dir "$rimeUserDir" --sync-dir 'D:\MyCloud\RimeSync'
```

1. 每臺電腦都設定同一個雲端資料夾在該臺的本機路徑。
2. 保留每臺原本不同的 installation_id，不要複製別臺 installation.yaml。
3. 第一臺在小狼毫選單執行「用戶資料同步」，等雲端上傳完成。
4. 第二臺等雲端下載完成，再執行「用戶資料同步」，合併已學習詞彙和詞頻。
5. 日後需要同步時重複此步驟；第一版不是即時自動同步。

沿用 translator/user_dict: rime_ice，故兩臺會合併同一使用者詞典。
快照可能包含你輸入的人名、私人詞彙，請用私人雲端資料夾。
模型本身及暫存前文不在這項同步範圍內。

參考：
- https://github.com/rime/home/wiki/UserGuide
- https://huggingface.co/Qwen/Qwen2.5-0.5B
- https://github.com/hchunhui/librime-lua/wiki/Scripting

## Google Drive Desktop 快速設定（僅同步，不啟用 AI）

1. 在兩臺電腦登入相同 Google 帳號。第一臺在「我的雲端硬碟」建立 RimeSync
   資料夾；第二臺等這個資料夾同步完成。不要在「電腦」備份區各建一份。
2. 如果使用串流模式，對 RimeSync 按右鍵，設成「可離線使用」；
   Google Drive Desktop 保持執行。
3. Git Bash 更新本分支：

   ```bash
   cd ~/plum
   bash rime-install TaSirAz/rime-ice@ai-rerank-sync-prototype
   ```

4. 在 Windows PowerShell 執行（預設 Rime 用戶路徑）：

   ```powershell
   python -m pip install PyYAML
   powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File "$env:APPDATA\Rime\tools\ai_rerank\setup_google_drive.ps1"
   ```

   選取 Google Drive 裡剛才的 RimeSync 資料夾。這只設定同步，
   不會啟用 AI、下載模型或開啟背景推論。需要 Python 3.10 或更新版；支援 Miniconda。
   腳本優先使用 python，只有 py 時才使用 py -3。若只有 py，安裝 PyYAML
   時改用 py -3 -m pip install PyYAML。python 指令不能加 -3。
   若曾自訂小狼毫用戶路徑，啟動腳本時加 -RimeUserDir 指定實際資料夾。
   腳本也接受 -SyncDir 指定資料夾，以免虛擬磁碟在資料夾選單中沒有顯示。
5. 第一臺重新部署，從小狼毫選單執行「用戶資料同步」，等 Google Drive 完成上傳。
6. 第二臺執行相同設定，選同一個雲端資料夾，等下載完成後再執行「用戶資料同步」。
   此時應合併 rime_ice 已學習詞彙與詞頻。每臺保留原本的 installation_id。
7. 日後要傳遞新的學習資料，仍須執行「用戶資料同步」。Google Drive 自動傳檔，
   Rime 詞庫匯出與合併在這一版是手動觸發。

設定腳本已寫入本分支；尚未在 Windows 的資料夾選單／Google Drive 實測。
參考：https://support.google.com/drive/answer/13401938

## Windows 自動刷新與背景啟動

更新整個 ai-rerank-sync-prototype 分支後，在 PowerShell 執行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:APPDATA\Rime\tools\ai_rerank\start_worker.ps1" -PythonExe "$env:USERPROFILE\Documents\FRS\miniconda3\python.exe"
```

若 Python 不在這個 Miniconda 路徑，指定實際的 python.exe。
啟動腳本會先執行 Python 排序規則、設定、通知協定／Windows INPUT 結構測試，再啟用 AI、自動刷新，
並僅停止相同 Python 執行檔執行的這份 worker.py，重新在背景啟動。
其他 Python 工作不會被停止。設定修改前會備份。

看到 worker.log 裡的 Ready 後重新部署。模型完成排序後應自動更新候選並顯示 [AI]。
不需要按 Ctrl+Shift+R。背景程式每次開機後需啟動一次，目前沒有加開機啟動。

實作使用 Windows SendInput 的 F24 作為 Rime 刷新通知；AI 元件會消耗此按鍵。
傳送前檢查來源前景視窗、PID、焦點控制項、最新請求／結果 ID，以及修飾鍵是否放開。
切換視窗、請求變更或通知逾時會丟棄通知。Rime 也會再核對組字輸入、前文與結果 ID。
此檢查不等同完整 TSF 周邊文字讀取或訊息送出判定。

需同步更新整個分支，包括 lua/ai_rerank.lua、worker.py、ranking.py、windows_notify.py 和 setup.py。
通知 helper 只記錄狀態與請求 ID，不讀取或記錄視窗文字。
診斷：status.log 應有 auto_refresh_received、result_applied；notify_status.log
應有 notification_sent。若出現 notification_failed，可能受 Windows 權限或應用程式限制；
仍可使用手動刷新。若需要實體 F24，將 ai_rerank/auto_refresh 設為 false 並重新部署。

Windows 原生自動刷新尚未完成實測。通知協定與結構的 Python 測試已在 Linux CI 通過；
啟動腳本會在使用者端再跑相容性測試。這些測試成功不代表原生 UI 通知已驗證。

參考：https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput

## 整句排序診斷（sentence-v6）

重新更新分支並執行 start_worker.ps1，重新部署。worker.log 應出現
`Ranking: sentence-v6, conservative promotion; no Enter required.` 與 Ready。
第一個候選旁 [AI] 表示結果已套用，也可能保留原順序；並不表示模型一定改動或判斷正確。

以固定例句檢查真實模型（不讀取個人輸入，不會下載已快取以外的模型）：

```powershell
& "$env:USERPROFILE\Documents\FRS\miniconda3\python.exe" "$env:APPDATA\Rime\tools\ai_rerank\evaluate.py" --local-only
```

此診斷列出已送出／未送出前文、共識／公事及公式／公司的固定例句，
同時包含原排序正確與錯誤的版本，報告選字及單次評分耗時。這不是代表性準確率評測。
0.5B 基礎模型未經拼音選字訓練；保守排序只能限制錯排幅度，不能保證品質改善。

本次本機執行環境沒有可用的 Python/Lua 執行器，改由 GitHub Actions 驗證。
提交 `2f7e7faa8ff13e188cd3bd029ac89609e8dfe932` 的 Python 測試、Lua 請求與迭代器回歸測試，
以及 `make -C others/script/ lint` 均已通過：
https://github.com/TaSirAz/rime-ice/actions/runs/38246455338
啟動腳本也會在本機先跑 Python 測試。Windows 候選視窗及實際模型品質仍待驗證。

## 等 AI 算完才顯示候選（wait-for-ai-v7）

啟動腳本預設啟用 `ai_rerank/wait_for_ai: true`。
AI 啟用、自動刷新啟用，而且 Windows 背景通知有新鮮焦點心跳時，
Lua 先送請求，等待期間暫不輸出候選，符合本次請求的排序完成後才一次顯示整張表。
持續打字會改送新請求；舊結果不會顯示在新輸入。

等待期間先按空白、Enter 或數字 1–9，會先恢復原候選再交給一般選字處理。
通知執行緒不受模型推論阻塞，約 2 秒未收到結果會通知恢復原候選。
逾時或使用者提前選字後，同一請求的晚到結果不再改動排序，避免二次跳動。
背景程式未 Ready／心跳過期、手動刷新模式或不支援的平台不隱藏候選。
若背景程式突然退出或 Windows 通知失敗，下一次按鍵／刷新可恢復；
Ctrl+Shift+R 也可備用。原生小狼毫 UI 與快速選字仍需在 Windows 實測。

目前採用「等待時不輸出候選」，而非小狼毫 UI 的動態隱藏開關。
若需恢復先顯示原候選的模式，只在 rime_ice.custom.yaml 設定
`ai_rerank/wait_for_ai: false` 並重新部署即可，AI 排序仍保留；
再次執行 start_worker.ps1／--enable-ai 會重新啟用等待模式。

更新整個分支後執行 start_worker.ps1，等 Ready，再重新部署。
診斷：status.log 中 waiting_hidden 後應有 result_applied，或 wait_timeout_received／wait_user_selection。
通知狀態中的 wait_timeout 表示逾時恢復。

## 評分延遲改善（fast-v8）

固定輸入合併等待由 150 ms 縮短為 50 ms，請求輪詢由 25 ms 縮短為 10 ms，
Windows 刷新通知輪詢由 50 ms 縮短為 20 ms。沒有至少兩個可比較候選時不等待、不推論。
支援的 Transformers 版本只輸出差異後綴需要的位置分數，舊版也只對後綴執行 log_softmax。
停用未使用的推論 KV cache，並在 Ready 前以固定測試字詞暖機一次。
模型大小、前文長度、候選比較範圍與排序門檻保持原設定，未切換低精度或縮小模型。

新增 test_fast_scoring.py 用 PyTorch 合成 logits 比較優化前後分數，
涵蓋新舊 forward 參數、空前文、长前文、共同前綴與不同 token 長度填充；
不下載真實模型。GitHub CI 安裝 CPU PyTorch 執行此測試，本機啟動脚本也會執行。
這是分數等價與程式測試，不是實際 Qwen 模型延遲基準。

重新更新分支、執行 start_worker.ps1 並等 Ready。worker.log 應有
`Scoring: fast-v8`、實際 device、PyTorch threads 和支援的 keep_logits 參數。
每次完成最新請求後會覆寫 ai_bridge/timing.json，只存耗時、評分數量及運算裝置，不含輸入文字：

```powershell
Get-Content "$env:APPDATA\Rime\ai_bridge\timing.json"
```

inference_ms 是候選評分呼叫耗時（快取命中可接近零）；worker_ms 是這次請求
被背景程式觀察後到结果寫出的耗時，包含輸入合併等待。
它不包含舊推論占用背景程式的時間，也不包含 Windows 通知或候選視窗繪製時間。
目前無法在使用者的硬體測量，實際加速幅度需比較本機耗時與打字感受。

## 直接刷新與流程耗時（immediate-v9）

移除額外的 50 ms 輸入等待，背景程式讀到最新請求便評分。
推論中的舊結果仍會核對並丟棄，完成最新結果後直接喚醒 Windows 通知執行緒。
通知執行緒平時以 10 ms 輪詢追蹤請求、結果與逾時，但新结果通知不必等待下一輪。
此修改不改模型、排序規則或等待 AI 才顯示候選的設定。

新增 ai_bridge/pipeline_timing.json，只含請求 ID、狀態與耗時：
- response_ms：通知執行緒首次看見這份請求到觀察到其結果。
- notification_ms：首次看見請求到 SendInput 成功返回。
- applied_ms：首次看見請求到觀察到 Lua 的候選套用確認。
- notification_to_applied_ms：通知送出到觀察到套用確認的間隔。
- mode：ai 表示套用 AI 結果；original 表示恢復原候選（例如逾時或提前選字）。

Lua 在即將提供候選時寫套用確認；這不是 Windows 實際繪製畫面或鍵盤到螢幕時間。
觀察時間含至多約一輪輪詢誤差，執行緒排程或磁碟 I/O 也可能增加延遲。
尚未完成的階段為 null。切換視窗、修飾鍵未放開或通知失敗時需配合 notify_status.log。
例行等待與舊結果不匹配不再每次寫日誌，降低磁碟寫入次數。

```powershell
Get-Content "$env:APPDATA\Rime\ai_bridge\pipeline_timing.json"
```

更新整個分支，重新執行 start_worker.ps1，等 Ready，再重新部署。
worker.log 應有 `Scoring: immediate-v9, no typing delay; event-driven refresh.`。
本次改善沒有使用者端端到端耗時基準，仍需用新紀錄及打字體感驗證。

## CPU 執行緒自動實測（cpu-tuning-v10）

背景程式啟動時，先以固定短／長前文、四個候選測試目前預設與可用的 1、2、4、8 執行緒。
每個設定先暖機，再量三輪未經結果快取的實際模型評分，選中位數耗時最低的設定。
最多測到 8 個替代執行緒數；原預設不論數量仍納入比較。
測試以約 8 秒為軟預算，至少比較原預設與一個替代；單次推論不能中途取消，
因此慢電腦可能超過此時間。這只在啟動時做，Ready 之後打字不再跑測試。

只調整此背景程序的 PyTorch CPU 執行緒數；不更換模型、精度、前文範圍或排序門檻。
CUDA 模式略過 CPU 實測。固定例句測出的最快設定不一定適合所有實際輸入，
也不包含小狼毫候選表繪製延遲；不能保證端到端低於 50 ms。

cpu_tuning.json 記錄原設定、選用執行緒數與各組固定例句中位耗時，沒有使用者輸入。
timing.json 另增加 cpu_threads。更新整個分支，重新執行 start_worker.ps1，等 Ready 並重新部署。

```powershell
Get-Content "$env:APPDATA\Rime\ai_bridge\cpu_tuning.json"
```

回歸測試確認以實測最快設定選擇、跳過結果快取、GPU 略過、核心數限制，
及測試例外時恢復原執行緒数。實際模型測速會在使用者電腦啟動時執行。

## 研究後的快路徑與原生選字（semantic-fast-v11）

參考 Rime 原生 Octagram 與 libime 系統／個人語言模型設計，先消除無意義的等待，
再保留 Transformer 處理真正可比较的候選：
- Lua 先按 Python 同樣的規則檢查前四個的字長及拼音範圍。少於兩個可比較候選時立即提供原候選，
  不寫请求、不隱藏、不走 F24 通知。
- 單 token 差異後綴只對共同前文 forward 一次（batch=1），取各候選 next-token 機率。
  多 token 仍走原路徑。數學評分相同，實際浮點運算可有微小差異。
- Lua 保存最多 64 組已成功套用的順位。前文、完整有序候選文字及可比較性完全相同時直接套用，
  不需背景計算／通知；使用目前的 Candidate 物件。逾時、人工提前選字及不完整排列不寫快取。
- 新鮮焦點 token 改變或手動重置會清除前文及快取，避免跨視窗語境污染。
- 快路徑保持候選一次顯示；真正的新歧義仍等待 AI。没有停用 AI。

pipeline_timing.json 只量背景請求路徑；快取或不可比較的立即顯示不會更新該檔，
因此看到舊耗時不代表目前按鍵仍在等。status.log 的 cache_hit 可辨識已完成結果快取。
此快取是本機工作階段資料，沒有把模型猜測寫成個人詞頻或同步到雲端。

### 原生詞序模型

上游 Rime 支援在 decoder 產生候選時使用 Octagram 語言模型：
https://github.com/iDvel/rime-ice/blob/main/others/recipes/grammar.recipe.yaml
官方模型與設定：
https://github.com/lotem/rime-octagram-data
https://github.com/lotem/rime-octagram-data/blob/master/grammar.yaml
libime 的系統／歷史語言模型插值：
https://github.com/fcitx/libime/blob/master/src/libime/core/userlanguagemodel.cpp

新增選用入口；使用模型 release 20260712 的
zh-hans-t-essay-bgw-compact.gram（40,925,228 bytes，約 39 MiB）。
下載後核對 release 的 SHA256：
d3cb2438c1fdcd6a855dd6ca8f5c1060a29273c6b64c2c2c69af67cd71b6aa7e。
校驗完成才修改設定；原自訂 YAML 會備份，有其他 grammar 設定時不覆盖。
源詞典主體是簡體，故用 hans，再沿用现有 OpenCC 正體顯示。
這不保證臺灣用語全受涵蓋，Qwen 和 Rime 使用者詞頻繼續保留。

更新整個分支後，啟動時加 -NativeGrammar：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:APPDATA\Rime\tools\ai_rerank\start_worker.ps1" -PythonExe "$env:USERPROFILE\Documents\FRS\miniconda3\python.exe" -NativeGrammar
```

首次下載需連網，之後已驗證檔案不再下載。等 Ready 後重新部署。
啟用 lotem 官方的 contextual_suggestions 與同音／同形候選上限，並在未自訂時設定 max_sentences=3
（多整句需 librime >=1.17），讓更多完整候選可被比較。
一般官方小狼毫內建 Octagram；若自行換過 rime.dll，需確認 grammar 模組。
INFO 日誌中的 registering components from module 'grammar' 是正向證據；
沒有日志不代表沒有插件。未確認相容性的自訂版本可先省略 -NativeGrammar，只用快路徑。

### 驗證與限制

新增不可比較輸入不等待、語義快取／焦點清除、無效排列拒絕，以及單 token 與原評分等價測試。
原生 installer 測試檢查完整性失敗不改設定、已驗證檔案不重下載、保留既有 AI／使用者詞典設定。
沒有修改詞典源文件；依 AGENTS.md，這次執行 Python/Lua 回歸與 make -C others/script/ lint。
目前本機執行器不可用，測試由 GitHub CI 執行。

單 token 與快路徑可減少已知重複工作，但不是 Windows 實機延遲或 CPM 的保證。
原生模型安裝入口的下載／設定測試不等同其真實候選準確率測試；
需在使用者的 Weasel 部署後確認。建議同一篇文章以相同方式各打三次，
記錄 CPM、修改次數與錯排例句，同時檢查 AI 修正錯詞以及把原本正確詞改錯的情況。
