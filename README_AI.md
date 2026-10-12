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
- 快速輸入時等待約 150 ms 沒有新請求再計算，另加實際推論時間；不阻塞打字。
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
