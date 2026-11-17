import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from typing import TypedDict
import json

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

load_dotenv()

SERPER_API_KEY = os.getenv("SERPER_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-3.5-turbo")
MAX_ROUND = 5

llm = ChatOpenAI(
    api_key=OPENAI_API_KEY,
    base_url=OPENAI_BASE_URL,
    model=MODEL_NAME,
    temperature=0.2,
    streaming=True
)

# 原生Serper搜索，不再依赖langchain内置Serper工具
def serper_search(query: str):
    url = "https://google.serper.dev/search"
    payload = json.dumps({"q": query})
    headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, data=payload, timeout=15)
    return resp.json()

# 网页内容抓取
def scrape_url(url: str) -> str:
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        return text[:3000]
    except Exception as e:
        return f"【抓取失败】{str(e)}"


class ResearchState(TypedDict):
    user_query: str
    append_prompt: str
    is_append: bool
    output_format: str
    filter_ad: bool
    plan: str
    search_queries: list[str]
    search_results: list[dict]
    scraped_contents: list[dict]
    report: str
    sources: list[str]
    round_count: int
    need_more_search: bool


# Planner 节点
def planner(state: ResearchState):
    if state["is_append"]:
        prompt = f"""
这是追加迭代调研，不是全新调研。
原始调研需求：{state['user_query']}
当前已有的调研报告：{state['report'][:2000]}
用户新追加指令：{state['append_prompt']}

任务：
1. 判断仅利用现有资料是否足够完成追加要求；
2. 资料足够则 search_queries 为空数组；
3. 缺少信息最多生成2个补充搜索query；
输出JSON：{{"plan":"简要迭代计划","search_queries":[]}}
不要多余文字。
"""
    else:
        prompt = f"""
你是调研规划助手，用户调研需求：{state['user_query']}
输出JSON：{{"plan":"简要调研计划","search_queries":["query1","query2","query3"]}}
生成2~4个适合搜索引擎的查询词，不要多余文字。
"""
    resp = llm.invoke(prompt)
    data = json.loads(resp.content)
    return {
        **state,
        "plan": data["plan"],
        "search_queries": data["search_queries"],
    }


# Search 节点
def search_node(state: ResearchState):
    all_results = []
    for q in state["search_queries"]:
        res = serper_search(q)
        if "organic" in res:
            for item in res["organic"]:
                all_results.append({
                    "title": item.get("title"),
                    "link": item.get("link"),
                    "snippet": item.get("snippet")
                })
    return {
        **state,
        "search_results": state["search_results"] + all_results
    }


# Scrape 节点
def scrape_node(state: ResearchState):
    new_scraped = []
    new_links = []
    for item in state["search_results"]:
        link = item.get("link")
        if not link or link in state["sources"]:
            continue
        content = scrape_url(link)
        new_scraped.append({
            "title": item["title"],
            "link": link,
            "snippet": item["snippet"],
            "content": content
        })
        new_links.append(link)
    return {
        **state,
        "scraped_contents": state["scraped_contents"] + new_scraped,
        "sources": state["sources"] + new_links
    }


# Reviewer 节点
def reviewer(state: ResearchState):
    all_text = "\n\n".join([f'【{x["title"]}】\n{x["content"]}' for x in state["scraped_contents"]])
    if state["is_append"]:
        prompt = f"""
原始需求：{state['user_query']}
追加指令：{state['append_prompt']}
已有报告：{state['report'][:2000]}
现有资料：{all_text[:6000]}

判断信息是否足够完成本次追加修改。
缺信息返回 {{"need_more_search":true,"new_queries":["q1"]}}
足够返回 {{"need_more_search":false,"new_queries":[]}}
最多2个query，严格JSON，不要多余文字。
"""
    else:
        prompt = f"""
用户需求：{state['user_query']}
现有搜集资料：{all_text[:6000]}
判断信息是否足够写一份高质量调研报告。
不足返回 {{"need_more_search":true,"new_queries":["q1","q2"]}}
足够返回 {{"need_more_search":false,"new_queries":[]}}
最多2个query，严格JSON。
"""
    resp = llm.invoke(prompt)
    data = json.loads(resp.content)
    next_queries = data.get("new_queries", [])
    need_more = data.get("need_more_search", False)
    new_round = state["round_count"] + 1
    if new_round >= MAX_ROUND:
        need_more = False
    return {
        **state,
        "search_queries": next_queries,
        "need_more_search": need_more,
        "round_count": new_round
    }


# Writer 节点（流式写报告）
def writer(state: ResearchState):
    all_text = "\n\n".join([f'【{x["title"]}】\n{x["content"]}' for x in state["scraped_contents"]])
    source_list = "\n".join([f"- {u}" for u in state["sources"]])
    filter_note = "严格过滤广告、营销软文内容" if state["filter_ad"] else "保留全部内容"
    fmt = state["output_format"]

    if state["is_append"]:
        prompt = f"""
你是调研写作者。
原始需求：{state['user_query']}
追加指令：{state['append_prompt']}
原有报告：
{state['report']}
输出格式：{fmt}
内容规则：{filter_note}

要求：在原有报告基础上修改补充，不要全盘抛弃；冲突信息标注 ⚠️信息冲突；找不到内容如实写暂未查到；
全部资料：
{all_text[:8000]}

最后附上参考来源列表。
"""
    else:
        prompt = f"""
你是调研写作者，用户需求：{state['user_query']}
输出格式：{fmt}
内容规则：{filter_note}
资料：
{all_text[:8000]}

要求：结构清晰、结论客观；冲突信息标注 ⚠️信息冲突；找不到内容如实写暂未查到；文末附上参考来源。
"""
    chunks = []
    for chunk in llm.stream(prompt):
        chunks.append(chunk.content)
    report_body = "".join(chunks)
    full_report = report_body + "\n\n## 参考来源\n" + source_list
    return {**state, "report": full_report}


# 路由判断
def route_review(state: ResearchState):
    if state["need_more_search"]:
        return "search"
    return "writer"


# 构建图
builder = StateGraph(ResearchState)
builder.add_node("planner", planner)
builder.add_node("search", search_node)
builder.add_node("scrape", scrape_node)
builder.add_node("reviewer", reviewer)
builder.add_node("writer", writer)

builder.set_entry_point("planner")
builder.add_edge("planner", "search")
builder.add_edge("search", "scrape")
builder.add_edge("scrape", "reviewer")
builder.add_conditional_edges("reviewer", route_review, {"search": "search", "writer": "writer"})
builder.add_edge("writer", END)

graph = builder.compile()


# 对外流式接口函数，给main.py调用
def stream_research(
    user_query: str,
    output_format: str = "要点清单",
    filter_ad: bool = True,
    append_prompt: str = "",
    old_state: dict = None
):
    if old_state is None:
        init_state: ResearchState = {
            "user_query": user_query,
            "append_prompt": "",
            "is_append": False,
            "output_format": output_format,
            "filter_ad": filter_ad,
            "plan": "",
            "search_queries": [],
            "search_results": [],
            "scraped_contents": [],
            "report": "",
            "sources": [],
            "round_count": 0,
            "need_more_search": False
        }
    else:
        init_state: ResearchState = {
            **old_state,
            "append_prompt": append_prompt,
            "is_append": True,
            "search_queries": [],
            "need_more_search": False,
            "round_count": 0
        }

    for event in graph.stream(init_state, stream_mode="values"):
        node_name = event.get("__name__", "")
        if node_name == "planner":
            yield json.dumps({"type": "status", "msg": "✅ 拆解调研目标", "plan": event["plan"]}, ensure_ascii=False)
        elif node_name == "search":
            yield json.dumps({"type": "status", "msg": "🔍 正在搜索相关网页", "queries": event["search_queries"]}, ensure_ascii=False)
        elif node_name == "scrape":
            yield json.dumps({"type": "status", "msg": "📖 正在精读网页提取内容"}, ensure_ascii=False)
        elif node_name == "reviewer":
            if event["need_more_search"]:
                yield json.dumps({"type": "status", "msg": "🧐 信息不足，补充检索", "new_queries": event["search_queries"]}, ensure_ascii=False)
            else:
                yield json.dumps({"type": "status", "msg": "✅ 信息收集完成，开始撰写报告"}, ensure_ascii=False)
        elif node_name == "writer":
            yield json.dumps({"type": "report", "content": event["report"]}, ensure_ascii=False)

    yield json.dumps({"type": "done", "msg": "调研任务结束", "full_state": init_state}, ensure_ascii=False)
