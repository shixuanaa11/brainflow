"""14 个业务工具注册（业务侧真实逻辑后续接入；此处注册表 + stub 保证链路可跑）"""
from core.registry import get_registry


def _stub(tag: str):
    def fn(query: str = "", **kw) -> str:
        return f"[{tag}] {query[:60] or '已执行'} (stub)"
    return fn


TOOLS = [
    # (id, 描述, 触发词, 例句)
    ("weather",            "天气工具",     ["天气", "气温", "下雨"], ["深圳今天天气怎么样", "明天会下雨吗"]),
    ("news",               "新闻工具",     ["新闻", "热点"],         ["今天有什么热点新闻", "查下财经新闻"]),
    ("info_hunt",          "信息查询",     ["政策", "财税", "补贴"], ["查一下创业补贴政策"]),
    ("jingying_data",      "经营数据",     ["经营数据", "数据"],     ["查一下昨天的经营数据"]),
    ("bilibili_upload",    "B站上传",      ["B站", "bilibili"],     ["帮我上传B站视频 儿童节"]),
    ("bilibili_comment",   "B站评论回复",  ["B站评论"],             ["回复B站评论"]),
    ("douyin_publish",     "抖音发布",     ["抖音", "douyin"],      ["帮我发布抖音作品"]),
    ("douyin_comment",     "抖音评论回复", ["抖音评论"],            ["回复抖音评论"]),
    ("interactive_screen", "互动屏",       ["互动屏", "屏幕"],      ["打开互动屏"]),
    ("demo_mode",          "演示模式",     ["演示"],                ["进入演示模式"]),
    ("fullscreen",         "全屏",         ["全屏"],                ["全屏显示"]),
    ("task_kanban",        "任务看板",     ["看板", "kanban"],     ["看看任务看板"]),
    ("xiaojiang_robot",    "小匠机器人",   ["小匠"],                ["小匠你好呀"]),
    ("general_qa",         "通用问答",     [],                      ["今天中午吃什么"]),
]


def register_tools():
    """注册全部工具（含 general_qa 兜底）"""
    reg = get_registry()
    for name, desc, keywords, examples in TOOLS:
        fn = _stub(name)          # ← 业务侧真实工具替换这里
        reg.register(name, fn, desc=desc, keywords=keywords, examples=examples)
