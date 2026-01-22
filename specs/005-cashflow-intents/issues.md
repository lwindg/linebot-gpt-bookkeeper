• 以下是針對目前開發狀況與規格/程式碼的 review（先列問題，依嚴重度排序）：

  Issues

  - 高：現金流分流會誤判一般支出「轉帳」付款方式。_detect_cashflow_intent 只要出現「轉帳」
    就會走 cashflow prompt，導致像「午餐120元 Line Pay」被錯誤當成現金流。這是行為回歸風
    險。檔案：app/gpt_processor.py:54-58
  - 中：轉帳來源/目標帳戶推斷會被 alias 順序影響，不依訊息出現順序，可能把「富邦轉到合庫」
    反過來記。檔案：app/cashflow_rules.py:25-83
  - 中：規格與實作不一致。規格要求繳卡費一定是「帳戶 → 信用卡」，但實作會優先用訊息中的目標
    帳戶（例如富邦 Costco）。需要更新規格以反映目前行為。檔案：specs/005-cashflow-intents/
    spec.md:99-100、app/gpt_processor.py:700-705

  Questions / Assumptions

  - 是否希望「轉帳」在一般記帳中仍允許作為付款方式（如 Line Pay）？如果是，分流邏輯需要再
    加條件，例如只在包含「轉給/轉到/匯款/轉入/轉出」等動詞時才視為現金流。
  - 轉帳來源/目標是否要以「文字出現順序」為準？若要，infer_transfer_accounts 需改成用索引排
    序，而不是 alias list 順序。

  Status Snapshot

  - 分支：005-cashflow-intents 已推到遠端，較 origin/004-prompt-refactor 超前 11 個
    commit。
  - 工作目錄仍有未提交變更：specs/005-cashflow-intents/quickstart.md、specs/005-cashflow-
    intents/tasks.md、tests/curl-test-data.txt。

  如果要我先修其中一個問題，請告訴我優先順序：

  1. 轉帳分流誤判
  2. 轉帳來源/目標順序
  3. 規格同步修正
