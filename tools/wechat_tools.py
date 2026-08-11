"""14 个业务工具注册（业务侧真实逻辑后续接入；此处注册表 + stub 保证链路可跑）"""
from core.registry import get_registry
from tools.weather import query_weather
from tools.info_hunt import query_info_hunt


def _stub(tag: str):
    def fn(query: str = "", **kw) -> str:
        return f"[{tag}] {query[:60] or '已执行'} (stub)"
    return fn


TOOL_HANDLERS = {
    "weather": query_weather,
    "info_hunt": query_info_hunt,
}

# (id, 描述, 触发词, 例句, direct_reply, router_hint, router_exclude)
TOOLS = [
    ("weather", "天气工具",
     ["天气", "气温", "下雨", "冷不冷", "热不热"],
     ["深圳今天天气怎么样", "明天会下雨吗"], True,
     "查询指定城市/日期的天气预报与气温",
     "新闻、政策、经营报表"),

    ("news", "新闻工具",
     ["新闻", "热点", "头条", "资讯"],
     ["今天有什么热点新闻", "查下财经新闻"], False,
     "获取时事、热点、财经等新闻资讯",
     "政策细则查询、经营数据、发布视频"),

    ("info_hunt", "信息查询",
     ["政策", "财税", "补贴", "资质", "办事", "税收优惠", "创业补贴",
      "日报", "税务", "机器人补贴", "AI补贴", "扶持资金"],
     ["查一下创业补贴政策", "生成财税日报", "深圳有什么税收优惠"], True,
     "检索政策/补贴/财税信息；含「日报/财税/补贴」时生成完整财税日报",
     "热点新闻、经营报表、平台发布操作"),

    ("jingying_data", "经营数据",
     ["经营数据", "业绩", "销量", "报表"],
     ["查一下昨天的经营数据"], False,
     "查询经营/业务/销售类数据报表",
     "天气预报、新闻、政策、仅说「数据」但无经营语境"),

    ("bilibili_upload", "B站上传",
     ["B站", "bilibili", "上传", "发视频"],
     ["帮我上传B站视频 儿童节"], False,
     "向 B 站上传/发布视频",
     "回复评论、抖音操作、查资讯"),

    ("bilibili_comment", "B站评论回复",
     ["B站评论", "回复评论"],
     ["回复B站评论"], False,
     "回复或处理 B 站视频评论",
     "上传/发布视频、抖音操作"),

    ("douyin_publish", "抖音发布",
     ["抖音", "douyin", "发作品", "发视频"],
     ["帮我发布抖音作品"], False,
     "向抖音发布/上传作品或视频",
     "回复评论、B站操作、查资讯"),

    ("douyin_comment", "抖音评论回复",
     ["抖音评论"],
     ["回复抖音评论"], False,
     "回复或处理抖音作品评论",
     "发布作品、B站操作"),

    ("interactive_screen", "互动屏",
     ["互动屏", "互动", "大屏"],
     ["打开互动屏"], False,
     "打开或控制互动展示大屏",
     "全屏切换、演示模式、查数据"),

    ("demo_mode", "演示模式",
     ["演示", "演示模式"],
     ["进入演示模式"], False,
     "进入产品/方案演示模式",
     "全屏、互动屏、查数据"),

    ("fullscreen", "全屏",
     ["全屏", "最大化"],
     ["全屏显示"], False,
     "切换界面为全屏显示",
     "互动屏、演示模式"),

    ("task_kanban", "任务看板",
     ["看板", "kanban", "任务板"],
     ["看看任务看板"], False,
     "查看任务看板/待办进度",
     "经营数据报表、新闻"),

    ("xiaojiang_robot", "小匠机器人",
     ["小匠", "机器人"],
     ["小匠你好呀"], False,
     "与「小匠」机器人交互或唤起",
     "通用闲聊（无小匠字样时）"),

    ("general_qa", "通用问答",
     [], ["今天中午吃什么"], False,
     "闲聊、主观问答、无明确工具动作时的兜底",
     ""),
]


def register_tools():
    """注册全部工具（含 general_qa 兜底）"""
    reg = get_registry()
    for name, desc, keywords, examples, direct_reply, hint, exclude in TOOLS:
        fn = TOOL_HANDLERS.get(name, _stub(name))
        reg.register(name, fn, desc=desc, keywords=keywords, examples=examples,
                     direct_reply=direct_reply, router_hint=hint, router_exclude=exclude)
