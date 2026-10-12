# 本機同音詞排序：實驗原型

這是 opt-in 原型，安裝檔案本身不會啟用模型。保留現有臺灣詞庫、快捷鍵、
詞頻學習。模型僅重排前八個候選，不新增詞，也不訓練模型。

## 已實作與限制

- Python 背景程式使用 Qwen/Qwen2.5-0.5B 基礎模型，按前文條件機率評分。
- Lua 用上屏通知記住最近 128 字，以本機檔案交換請求；不在 Rime 主執行緒等推論。
- 新請求會讓舊結果失效；無符合請求的結果時使用原排序。結果在下一次候選更新時使用，
  不會主動刷新畫面，所以很快選字可能還是原排序。
- 無候選時 Enter 清前文、有輸入組字時 Enter 保留；60 秒閒置清除。
- Ctrl+Shift+BackSpace 手動清除前文。
- 等模型完成後按 Ctrl+Shift+R 手動刷新本次候選（原型測試用）。
- **尚未實作 Windows TSF 周邊文字讀取、焦點追蹤、游標移動與刪字回溯。**
  Enter 在送出/換行之間仍是保守規則，切換視窗後請手動重置。
- 尚未完成 Windows 小狼毫端到端測試、真實模型準確率或延遲測試。
  0.5B 模型不是為拼音選字訓練的專用模型，效果可能不如 Rime 原排序。
- 首次下載模型約需 GB 級空間；CPU 推論可能較慢，支援 CUDA 時會使用 GPU。
- 模型下載需要連線，之後可用 --local-only 禁止下載。輸入只留在本機
  ai_bridge 的單份請求檔，不寫完整歷史日誌，不要把此資料夾放到雲端。

## Windows 測試安裝

先安裝 Python 3.10 或更新版。用 Plum 安裝 ai-rerank-sync-prototype 分支，
再開 PowerShell，以下假設用戶資料夾是預設的 $env:APPDATA\Rime：

```powershell
$rimeUserDir = Join-Path $env:APPDATA 'Rime'
py -m pip install -r "$rimeUserDir\tools\ai_rerank\requirements.txt"
py "$rimeUserDir\tools\ai_rerank\setup.py" --user-dir "$rimeUserDir" --enable-ai
py "$rimeUserDir\tools\ai_rerank\worker.py" --bridge-dir "$rimeUserDir\ai_bridge"
```

保留背景程式視窗，重新部署小狼毫。先打「代入這個」並選字上屏，
再輸入 gongshi，稍等並按 Ctrl+Shift+R，觀察「公式」是否前移。依序確認數字選字、
組句、臺灣詞、標點及快捷鍵仍正常。停掉背景程式時應維持原排序。
第一版沒有開機自動啟動，以免未驗證的功能影響日常輸入。

停用（保留已學習字彙）：

```powershell
py "$rimeUserDir\tools\ai_rerank\setup.py" --user-dir "$rimeUserDir" --disable-ai
```

重新部署。setup 修改前會備份原始 YAML，所有既有設定會保留。
若重新安裝 Plum 覆蓋 custom 檔，需再跑一次 --enable-ai。

## 雲端同步已學習字彙

使用 Rime 原生「用戶資料同步」產生及合併快照，不同步正在使用中的 userdb。
你需要已登入並正在運作的 OneDrive、Dropbox 或其他雲端資料夾。
本工具不登入雲端、不建立雲端帳號，也不將學習資料推到公開 GitHub。

例如指定你的實際同步資料夾（請自行替換）：

```powershell
py "$rimeUserDir\tools\ai_rerank\setup.py" --user-dir "$rimeUserDir" --sync-dir 'D:\MyCloud\RimeSync'
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
   py -3 -m pip install PyYAML
   powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File "$env:APPDATA\Rime\tools\ai_rerank\setup_google_drive.ps1"
   ```

   選取 Google Drive 裡剛才的 RimeSync 資料夾。這只設定同步，
   不會啟用 AI、下載模型或開啟背景推論。需要先安裝 Python 3（包含 py launcher）。
   若曾自訂小狼毫用戶路徑，啟動腳本時加 -RimeUserDir 指定實際資料夾。
   腳本也接受 -SyncDir 指定資料夾，以免虛擬磁碟在資料夾選單中沒有顯示。
5. 第一臺重新部署，從小狼毫選單執行「用戶資料同步」，等 Google Drive 完成上傳。
6. 第二臺執行相同設定，選同一個雲端資料夾，等下載完成後再執行「用戶資料同步」。
   此時應合併 rime_ice 已學習詞彙與詞頻。每臺保留原本的 installation_id。
7. 日後要傳遞新的學習資料，仍須執行「用戶資料同步」。Google Drive 自動傳檔，
   Rime 詞庫匯出與合併在這一版是手動觸發。

設定腳本已寫入本分支；尚未在 Windows 的資料夾選單／Google Drive 實測。
參考：https://support.google.com/drive/answer/13401938
