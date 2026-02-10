# -*- coding: utf-8 -*-
"""
LINE confirmation message formatters.
"""

from app.gpt.types import MultiExpenseResult, BookkeepingEntry


def format_confirmation_message(entry: BookkeepingEntry) -> str:
    """
    Format bookkeeping confirmation message (v1 單項目格式)

    Formats the bookkeeping entry data into a user-friendly confirmation message
    with all important details.
    """
    # Calculate TWD amount
    twd_amount = entry.原幣金額 * entry.匯率

    message = f"""✅ 記帳成功！

📋 {entry.品項}"""

    # Display currency info (v003-multi-currency)
    if entry.原幣別 != "TWD":
        message += f"""
💵 新台幣：{twd_amount:.2f} 元 (原幣 {entry.原幣金額:.2f} {entry.原幣別} / 匯率 {entry.匯率:.4f})"""
    else:
        message += f"\n💵 新台幣：{twd_amount:.0f} 元"

    message += f"""
💳 付款方式：{entry.付款方式}
📂 分類：{entry.分類}
⭐ 必要性：{entry.必要性}"""

    # Add advance payment information if present
    if entry.代墊狀態 == "代墊":
        message += f"\n💸 代墊給：{entry.收款支付對象}"
    elif entry.代墊狀態 == "需支付":
        message += f"\n💰 需支付給：{entry.收款支付對象}"
    elif entry.代墊狀態 == "不索取":
        message += f"\n🎁 不索取（代墊給：{entry.收款支付對象}）"

    message += f"""
📅 日期：{entry.日期}
🔖 交易ID：{entry.交易ID}"""

    # Add optional detail note if present
    if entry.明細說明:
        message += f"\n📝 明細說明：{entry.明細說明}"

    return message


def format_multi_confirmation_message(result: MultiExpenseResult, success_count: int, failure_count: int) -> str:
    """
    Format multi-item bookkeeping confirmation message (v1.5.0 新增)

    Formats multiple bookkeeping entries into a user-friendly confirmation message
    with all items listed.
    """
    entries = result.entries
    total_items = len(entries)

    if result.intent == "cashflow_intents":
        return format_cashflow_confirmation_message(entries, success_count, failure_count)

    # 單項目：使用 v1 格式（向後相容）
    if total_items == 1:
        return format_confirmation_message(entries[0])

    # 多項目：使用 v1.5.0 新格式
    if success_count == total_items:
        message = f"✅ 記帳成功！已記錄 {total_items} 個項目：\n"
    elif failure_count == total_items:
        message = f"❌ 記帳失敗！{total_items} 個項目均未能記錄。\n"
    else:
        message = f"⚠️ 部分記帳成功！已記錄 {success_count}/{total_items} 個項目：\n"

    # 列出所有項目
    for idx, entry in enumerate(entries, start=1):
        twd_amount = entry.原幣金額 * entry.匯率

        message += f"\n📋 #{idx} {entry.品項}"

        # Display currency info (v003-multi-currency)
        if entry.原幣別 != "TWD":
            # Foreign currency: show original amount, rate, and TWD amount
            message += f"\n💰 {entry.原幣金額:.2f} {entry.原幣別} (匯率: {entry.匯率:.4f})"
            message += f"\n💵 {twd_amount:.2f} 元 TWD"
        else:
            # TWD: show amount only
            message += f"\n💰 {twd_amount:.0f} 元"

        if entry.交易類型:
            message += f"\n🧾 {entry.交易類型}"

        message += f"\n📂 {entry.分類}"
        message += f"\n⭐ {entry.必要性}"

        if entry.明細說明:
            message += f"\n📝 {entry.明細說明}"

        # Add advance payment information if present
        if entry.代墊狀態 == "代墊":
            message += f"\n💸 代墊給：{entry.收款支付對象}"
        elif entry.代墊狀態 == "需支付":
            message += f"\n💰 需支付給：{entry.收款支付對象}"
        elif entry.代墊狀態 == "不索取":
            message += f"\n🎁 不索取（代墊給：{entry.收款支付對象}）"

        # 項目之間加空行（除了最後一個）
        if idx < total_items:
            message += "\n"

    # 顯示共用資訊
    if entries:
        message += f"\n\n💳 付款方式：{entries[0].付款方式}"
        message += f"\n🔖 交易ID：{entries[0].交易ID}"
        message += f"\n📅 日期：{entries[0].日期}"

    return message


def _summary_batch_id(entries: list[BookkeepingEntry]) -> str:
    for entry in entries:
        if entry.交易ID.endswith("-01") or entry.交易ID.endswith("-02"):
            return entry.交易ID.rsplit("-", 1)[0]
    return entries[0].交易ID


def format_cashflow_confirmation_message(entries: list[BookkeepingEntry], success_count: int, failure_count: int) -> str:
    total_items = len(entries)
    if total_items == 0:
        return "❌ 現金流記帳失敗！未能記錄項目。"

    if success_count == total_items:
        message = "✅ 現金流記帳完成\n"
    elif failure_count == total_items:
        message = "❌ 現金流記帳失敗！\n"
    else:
        message = f"⚠️ 部分記帳成功（{success_count}/{total_items}）\n"

    batch_id = _summary_batch_id(entries)

    grouped: dict[str, BookkeepingEntry] = {}
    for entry in entries:
        grouped[entry.交易類型] = entry

    if "提款" in grouped:
        withdrawal = grouped["提款"]
        amount = withdrawal.原幣金額 * withdrawal.匯率
        summary = f"🏧 提款：{withdrawal.付款方式} → 現金 {amount:.0f}"
        message += f"\n{summary}"
        message += f"\n📅 日期：{entries[0].日期}"
        message += f"\n🔖 批次ID：{batch_id}"
        return message

    if "轉帳" in grouped:
        transfer = grouped["轉帳"]
        amount = transfer.原幣金額 * transfer.匯率
        target_name = ""
        if "收入" in grouped:
            target_name = grouped["收入"].付款方式
        elif "支出" in grouped:
            target_name = grouped["支出"].付款方式

        if target_name:
            summary = f"🔁 轉帳：{transfer.付款方式} → {target_name} {amount:.0f}"
        else:
            summary = f"🔁 轉帳：{transfer.付款方式} {amount:.0f}"
        message += f"\n{summary}"
        message += f"\n📅 日期：{entries[0].日期}"
        message += f"\n🔖 批次ID：{batch_id}"
        return message

    if "收入" in grouped and len(grouped) == 1:
        income = grouped["收入"]
        amount = income.原幣金額 * income.匯率
        summary = f"💰 收入：{income.付款方式} {amount:.0f}"
        message += f"\n{summary}"
        message += f"\n📅 日期：{entries[0].日期}"
        message += f"\n🔖 批次ID：{batch_id}"
        return message

    message += f"\n- 記錄 {total_items} 筆現金流項目"
    return message


def format_settlement_report(project_name: str, data: dict) -> str:
    """
    Format project settlement report (v2.7 新增)
    """
    if not data or (data.get("total_spent", 0) == 0 and not data.get("settlement")):
        return f"❌ 找不到專案「{project_name}」的記帳資料，或是該專案尚無任何支出。"

    total_spent = data.get("total_spent", 0)
    settlement = data.get("settlement", {})

    report = [f"📊 【{project_name}】專案結算報告", ""]
    report.append(f"💰 專案總支出：NT$ {total_spent:,.0f}")
    report.append("-" * 20)

    if not settlement:
        report.append("（無代墊或需支付項目的結算細節）")
    else:
        # Filter settlement to only include counterparties with actual debt
        has_actual_settlement = False
        for counterparty, statuses in settlement.items():
            # Check if there's any status other than "無" with amount > 0
            # (Note: "無" is already filtered in notion_service.py, but we check amount > 0 here)
            valid_statuses = {s: a for s, a in statuses.items() if a > 0}
            
            if not valid_statuses:
                continue
                
            has_actual_settlement = True
            report.append(f"👤 對象：{counterparty}")
            for status, amount in valid_statuses.items():
                if status == "代墊":
                    report.append(f"  💸 他欠我 (代墊)：NT$ {amount:,.0f}")
                elif status == "需支付":
                    report.append(f"  💰 我欠他 (需支付)：NT$ {amount:,.0f}")
                elif status == "不索取":
                    report.append(f"  🎁 不索取 (已代墊)：NT$ {amount:,.0f}")
                else:
                    report.append(f"  ❓ {status}：NT$ {amount:,.0f}")
            report.append("")
        
        if not has_actual_settlement:
            report.append("（無代墊或需支付項目的結算細節）")

    report.append("💡 提示：以上金額由「原幣金額 * 匯率」計算得出。")
    return "\n".join(report).strip()


def create_flex_menu(current_project_lock: str = None) -> dict:
    """
    Create a JSON structure for a LINE Flex Message menu (v2.7 新增)
    """
    # Base buttons
    buttons = [
        {
            "type": "button",
            "action": {"type": "message", "label": "🔍 專案清單", "text": "專案清單"},
            "style": "primary",
            "color": "#4285F4",
            "margin": "sm"
        },
        {
            "type": "button",
            "action": {"type": "message", "label": "🔐 鎖定狀態", "text": "鎖定狀態"},
            "style": "secondary",
            "margin": "sm"
        },
        {
            "type": "button",
            "action": {"type": "message", "label": "🔓 全部解鎖", "text": "全部解鎖"},
            "style": "secondary",
            "margin": "sm"
        },
        {
            "type": "button",
            "action": {"type": "message", "label": "📖 記帳教學", "text": "記帳教學"},
            "style": "link",
            "margin": "sm"
        }
    ]

    # If lock exists, add settlement button at the top
    if current_project_lock:
        settlement_button = {
            "type": "button",
            "action": {
                "type": "message",
                "label": f"💰 結算 {current_project_lock}",
                "text": f"結算 {current_project_lock}"
            },
            "style": "primary",
            "color": "#34A853",
            "height": "md",
            "margin": "md"
        }
        buttons.insert(0, settlement_button)

    flex_contents = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "記帳助手功能選單", "weight": "bold", "size": "lg", "color": "#1DB446"}
            ]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": buttons
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "v2.7 Flex Menu", "size": "xs", "color": "#aaaaaa", "align": "center"}
            ]
        }
    }

    return flex_contents
