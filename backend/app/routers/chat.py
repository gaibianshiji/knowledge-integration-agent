from fastapi import APIRouter
from pydantic import BaseModel
from app.services.llm_service import call_deepseek
from app.services.integration_service import get_integration_result, adjust_decision

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []

@router.post("/message")
async def chat_message(request: ChatRequest):
    integration = get_integration_result()

    context = ""
    if integration:
        stats = integration.get("stats", {})
        decisions = integration.get("decisions", [])[:10]
        context = f"\n当前整合状态：共{stats.get('original', 0)}个知识点，整合后{stats.get('merged', 0)}个，{stats.get('decisions_count', 0)}项决策。"
        if decisions:
            context += "\n最近的整合决策：\n"
            for d in decisions:
                context += f"- {d['action']}: {d['reason']}\n"

    system_prompt = f"""你是一个学科知识整合助手，帮助教师理解和调整教材整合方案。
你可以：
1. 解释整合决策的原因
2. 根据教师反馈调整整合方案
3. 回答关于知识图谱和教材内容的问题
{context}
请用专业但易懂的语言回答。"""

    # Build messages with history
    messages = [{"role": "system", "content": system_prompt}]
    for msg in request.history[-10:]:  # Keep last 10 messages for context
        if isinstance(msg, dict) and "role" in msg and "content" in msg:
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": request.message})

    # Use multi-turn capable call
    from app.services.llm_service import call_deepseek_messages
    response = await call_deepseek_messages(messages)

    return {
        "response": response,
        "role": "assistant"
    }

@router.post("/adjust")
async def adjust_integration(request: ChatRequest):
    """Allow teacher to adjust integration decisions via natural language"""
    integration = get_integration_result()
    if not integration:
        return {"response": "当前没有整合结果，请先执行跨教材整合。", "success": False}

    system_prompt = """你是一个学科知识整合助手。教师要调整整合方案。
请根据教师的要求，判断需要修改哪些整合决策，并输出JSON格式的调整指令。

输出格式：
{"adjustments": [{"decision_id": "xxx", "new_action": "keep/merge/remove", "reason": "教师要求..."}]}

如果没有找到匹配的决策，返回 {"adjustments": []}"""

    from app.services.llm_service import extract_json_from_llm
    adjustments = await extract_json_from_llm(request.message, system_prompt)

    applied = []
    for adj in adjustments.get("adjustments", []):
        result = await adjust_decision(
            adj.get("decision_id", ""),
            adj.get("new_action", "keep"),
            adj.get("reason", "教师手动调整")
        )
        if result.get("success"):
            applied.append(adj.get("decision_id"))

    return {
        "response": f"已应用 {len(applied)} 项调整。" if applied else "未找到匹配的决策，请检查决策ID。",
        "adjustments_applied": len(applied),
        "success": len(applied) > 0
    }
