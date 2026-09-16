# AI 帳單與訂閱審核

讓 Codex 審核各家帳單，找出多收、重複扣款、未使用、自動續訂與尚未取得的付費權益，再準備退款、訂正或取回權益的草稿。

版本：**v0.2.0 / Stage 0**。這是一個可安裝的 Codex Skill，搭配本地帳單工具與測試。

## 審核範圍

| 帳單／情境 | 檢查內容 |
|---|---|
| SaaS、影音、工具訂閱、會籍 | 固定費、年繳、漲價、優惠到期、未使用與重複功能 |
| 雲端、API、電信、公用事業 | 單價、用量、席次、額度、超額費與服務期間 |
| 試用轉付費、自動續訂 | 試用／續訂時間、通知、使用情況、取消與退款條件 |
| App Store／支付平台帳單 | 實際銷售方、交易狀態與正確退款管道 |
| 一次性購買或服務 | 報價差異、明細、是否交付及退款／補償依據 |
| 已付費但未取得權益 | 功能、額度、服務期限、可恢復權益或申請補償的條件 |

通用流程適用於提供的所有商家。Railway 是其中一份商家補充指南；其他商家依其官方帳務、退款與客服規則調查。

## 工作流程

1. 從帳單、收據與歡迎／試用／方案／續訂／取消通知整理服務，使用者點名的服務即使缺收據也保留。
2. 分清帳單、已付款收據、預告、付款失敗與退款文件，保留來源。
3. 核對金額、明細、帳期、單價、用量、重複交易與續訂情況。
4. 檢查使用程度與服務依賴，評估退款、取回權益或未來節省的機會。
5. 交付可離線開啟的網頁：完整服務清單、目前狀態、費用、問題、處理步驟、證據與可複製的客服草稿。
6. 依使用者另行授權與可用工具提交；用收據及後續證據追蹤結果。

「沒有使用」會觸發退款評估。是否可退取決於購買管道、日期、商家條款及證據；條款不明時，可準備清楚說明情況的善意退款請求。取消未來續訂和要求退回已付費用會分別處理。

## 安裝與使用

將本倉庫的 [`skills/subscription-audit`](skills/subscription-audit) 資料夾放到 Codex 的 skills 目錄，通常為 `~/.codex/skills/`；若有設定 `CODEX_HOME`，則使用該目錄下的 `skills/`。更新既有版本時，替換同名 Skill 資料夾。

在 Codex 中指定檔案並輸入：

```text
使用 $subscription-audit 審核我提供的所有帳單。
找出多收、重複扣款、未使用、非預期續訂與沒拿到的權益，
以可視化網頁列出所有服務、目前狀態、費用、可能問題和處理方式，
保留證據缺口，並準備退款或客服申請草稿。
```

若要從信箱整理，請指定帳號與日期範圍，並使用已授權且在當前環境可用的郵件工具。Skill 本身沒有附帶 Gmail／Outlook 連接器；沒有連接器時，可以提供郵件匯出或帳單附件。範圍不完整會在報告中列明。

## 本地工具

測試環境：Python 3.12。金額核對工具只使用 Python 標準函式庫；PDF 文字擷取使用 `pypdf` 或已安裝的 Poppler `pdftotext`。可在獨立環境安裝這份倉庫的已測試依賴：

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

用合成範例驗證金額核對（此範例不是實際帳單）：

```sh
mkdir -p work
python skills/subscription-audit/scripts/check_facts.py \
  --input skills/subscription-audit/assets/example-facts.json \
  --output work/example-checks.json
```

擷取自己的 PDF：

```sh
python skills/subscription-audit/scripts/extract_pdf.py \
  /absolute/path/to/invoice.pdf --output-dir work/extracted
```

三個工具都支援 `--help`，既有輸出需要 `--force` 才會覆寫。`work/` 已排除於版本控制；請把實際帳單、郵件、帳號對照及審核輸出保留在私人工作目錄。

## 可視化訂閱文件

每次完整審核預設產出 `dashboard.html` 與 `dashboard.json`。網頁可離線使用，包含每項服務的狀態、費用依據、可能問題、處理方式、來源時間線，以及可複製的客服草稿。另列報銷、押金、退款和其他一次性帳務。

用合成範例產生網頁：

```sh
python skills/subscription-audit/scripts/render_dashboard.py \
  --input skills/subscription-audit/assets/example-dashboard.json \
  --output work/dashboard.html
```

未知費用不填零；目前固定月費、用量費、預付儲值、年／半年繳與歷史帳單分開。固定月費小計只納入有來源支持的項目，不代表完整支出。沒有連接所有帳戶時，清單會說明缺漏。

HTML 使用內嵌資料、樣式與程式，沒有外部字型、圖片或追蹤器；來源連結只會在點選時開啟。產生網頁不會寄信或提交客服申請。真實私人網頁不應提交至公開倉庫。

格式：[dashboard-contract.md](skills/subscription-audit/references/dashboard-contract.md)。

## 驗證

```sh
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests/subscription-audit -p 'test_*.py'
```

40 項自動測試涵蓋金額精度、文件去重、缺漏與衝突、PDF 擷取、異常文字字元警示，以及跨商家、年繳、電信、續訂與一次性帳單。所有測試及範例資料均為合成資料。

## v0.2.0 完整清單與網頁交付

- 保留所有發現的服務及使用者點名項目，區分當前證據、待確認和歷史狀態。
- 搜尋帳單以外的方案與服務生命週期訊號，避免漏掉沒有收據的訂閱。
- 沿同一事件追查後續狀態；較新付款訊號出現時，修正舊結論並停用不適用的草稿。
- 新增自包含 HTML renderer、合成範例及 8 項測試，檢查金額分幣別、未知／儲值排除與資料安全嵌入。

## v0.1.3 實測修正

- 郵件純文字為空白或 HTML 提示時，補讀 HTML 版本，避免漏掉帳單。
- 保留試用結束、服務收費開始與首次出帳日期的差異及衝突。
- 分別追蹤免費服務期、替換優惠碼及後續額度，不假設新補償已兌現舊權益。
- 在承諾的工作日窗口完整結束後才跟進，寄送前先確認是否已有回覆。
- 延續 v0.1.2 的 PDF 異常字元警示與原文保留。

## 第一版的能力邊界

- Codex 負責閱讀、商家政策調查、使用判斷與撰寫；腳本負責文字擷取與金額一致性核對。
- 帳單合計不等於已付款，數字相加正確也不表示計價合理。退款資格與使用情況需要各自的證據。
- 掃描圖片或複雜版面可能需要視覺檢查／OCR；工具不保證解析每種格式。若擷取文字出現 NUL 等異常控制字元，逐頁清單會列出警示，原文會保留供交叉核對，工具不會猜補字元。
- 發送、取消、調整方案與扣款上限依使用者授權及實際可用工具執行。完整審核預設交付本地網頁、JSON／CSV 和草稿。
- 本地腳本不發出網路請求；交給模型閱讀的內容可能由執行環境的模型供應商處理。

入口：[`SKILL.md`](skills/subscription-audit/SKILL.md) · 通用判斷：[`billing-review.md`](skills/subscription-audit/references/billing-review.md) · 證據格式：[`facts-contract.md`](skills/subscription-audit/references/facts-contract.md)
