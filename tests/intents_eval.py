"""意图识别准确性评估：测试集 + 准确率报告（目标 ≥ 90%）"""
import sys
from pathlib import Path

# Windows 终端 GBK 兼容：强制 UTF-8 输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

TEST_CASES = [
    ("深圳今天天气怎么样", "weather"),
    ("明天会下雨吗", "weather"),
    ("帮我上传B站视频 儿童节", "bilibili_upload"),
    ("发布B站视频，主题暑期特辑", "bilibili_upload"),
    ("今天有什么热点新闻", "news"),
    ("帮我查一下最新的财经新闻", "news"),
    ("查一下创业补贴政策", "info_hunt"),
    ("回复B站评论：视频很棒", "bilibili_comment"),
    ("帮我发布抖音作品", "douyin_publish"),
    ("打开互动屏", "interactive_screen"),
    ("进入演示模式", "demo_mode"),
    ("全屏显示", "fullscreen"),
    ("看看任务看板", "task_kanban"),
    ("小匠你好呀", "xiaojiang_robot"),
    ("查一下昨天的经营数据", "jingying_data"),
    ("今天中午吃什么", "general_qa"),
    ("你觉得人生意义是什么", "general_qa"),
]


def evaluate():
    from core.registry import get_registry
    from core.router import RouterAgent
    from tools.wechat_tools import register_tools

    register_tools()
    router = RouterAgent()

    total, correct = len(TEST_CASES), 0
    errors = []
    for text, expected in TEST_CASES:
        try:
            got = router.classify(text)
        except Exception as e:
            print(f"  ⚠️ LLM 不可用，跳过评估: {e}")
            return None
        ok = (got == expected)
        if ok:
            correct += 1
        else:
            errors.append((text, expected, got))
        print(("  ✅ " if ok else "  ❌ ") + f"[期望 {expected}] {text} → {got}")

    acc = correct / max(total, 1)
    print("-" * 50)
    print(f"意图识别准确率: {acc:.1%} ({correct}/{total})")
    for text, exp, got in errors:
        print(f"  错误: {text} | 期望 {exp} | 实际 {got}")
    return acc


if __name__ == "__main__":
    acc = evaluate()
    if acc is None:
        sys.exit(2)  # LLM 不可用
    sys.exit(0 if acc >= 0.90 else 1)
