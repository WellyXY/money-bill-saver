# AI 帳單與訂閱審核

讓 Codex 審核各家帳單，找出多收、重複扣款、未使用、自動續訂與尚未取得的付費權益，再準備退款、訂正或取回權益的草稿。

版本：**v0.1.1 / Stage 0**。這是一個可安裝的 Codex Skill，搭配本地帳單工具與測試。

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

1. 從指定的帳單 PDF、郵件、收據、付款或使用紀錄整理商家與帳單。
2. 分清帳單、已付款收據、預告、付款失敗與退款文件，保留來源。
3. 核對金額、明細、帳期、單價、用量、重複交易與續訂情況。
4. 檢查使用程度與服務依賴，評估退款、取回權益或未來節省的機會。
5. 整理報告，以及適用於商家 Email 或站內客服的草稿。
6. 依使用者另行授權與可用工具提交；用收據及後續證據追蹤結果。

「沒有使用」會觸發退款評估。是否可退取決於購買管道、日期、商家條款及證據；條款不明時，可準備清楚說明情況的善意退款請求。取消未來續訂和要求退回已付費用會分別處理。

## 安裝與使用

將本倉庫的 [`skills/subscription-audit`](skills/subscription-audit) 資料夾放到 Codex 的 skills 目錄，通常為 `~/.codex/skills/`；若有設定 `CODEX_HOME`，則使用該目錄下的 `skills/`。更新既有版本時，替換同名 Skill 資料夾。

在 Codex 中指定檔案並輸入：

```text
使用 $subscription-audit 審核我提供的所有帳單。
找出多收、重複扣款、未使用、非預期續訂與沒拿到的權益，
列出可處理的項目、證據缺口，並準備退款或客服申請草稿。
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

兩個工具都支援 `--help`，既有輸出需要 `--force` 才會覆寫。`work/` 已排除於版本控制；請把實際帳單、郵件、帳號對照及審核輸出保留在私人工作目錄。

## 驗證

```sh
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests/subscription-audit -p 'test_*.py'
```

31 項自動測試涵蓋金額精度、文件去重、缺漏與衝突、PDF 擷取，以及跨商家、年繳、電信、續訂與一次性帳單。所有測試及範例資料均為合成資料。

## 第一版的能力邊界

- Codex 負責閱讀、商家政策調查、使用判斷與撰寫；腳本負責文字擷取與金額一致性核對。
- 帳單合計不等於已付款，數字相加正確也不表示計價合理。退款資格與使用情況需要各自的證據。
- 掃描圖片或複雜版面可能需要視覺檢查／OCR；工具不保證解析每種格式。
- 發送、取消、調整方案與扣款上限依使用者授權及實際可用工具執行。第一版預設交付報告與草稿。
- 本地腳本不發出網路請求；交給模型閱讀的內容可能由執行環境的模型供應商處理。

入口：[`SKILL.md`](skills/subscription-audit/SKILL.md) · 通用判斷：[`billing-review.md`](skills/subscription-audit/references/billing-review.md) · 證據格式：[`facts-contract.md`](skills/subscription-audit/references/facts-contract.md)
