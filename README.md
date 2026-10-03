# SketchStack 模板联合选版器

为脚手架文件生成阶段产出锁定清单：给定内存目录 `catalog`、目标技术栈 `stack`
和用户请求的根组件列表 `roots`，`resolve` 返回字典序最大根版本向量对应的完整
锁定结果，或明确的无解结果。只处理依赖清单，不解析/渲染 Jinja2 正文。

## 使用

```python
from sketchstack import Candidate, Dependency, resolve

catalog = [
    Candidate("A", "web", (2, 0, 0), (Dependency("X", (1, 0, 0), (2, 0, 0)),)),
    Candidate("A", "web", (1, 0, 0), (Dependency("X", (2, 0, 0), (3, 0, 0)),)),
    Candidate("B", "web", (2, 0, 0), (Dependency("X", (2, 0, 0), (3, 0, 0)),)),
    Candidate("B", "web", (1, 0, 0), (Dependency("X", (1, 0, 0), (2, 0, 0)),)),
    Candidate("X", "web", (1, 0, 0)),
    Candidate("X", "web", (2, 0, 0)),
]

result = resolve(catalog, "web", ["A", "B"])
if result.ok:
    print(result.locked)  # {'A': (2, 0, 0), 'B': (1, 0, 0), 'X': (1, 0, 0)}
else:
    print("无解:", result.reason)
```

## 约定

- 版本为三个非负整数 `(主, 次, 修订)`，依次比较；`parse_version("1.2.3")` 可解析字符串。
- 依赖区间 `[lower, upper)`：含下界、不含上界；`upper=None` 表示无上界。
- 所有依赖都是必需的，且只能在同一技术栈内解析，其他技术栈的候选不能补位。
- `roots` 顺序即版本新旧偏好优先级：只有前面的根无法保留时，才为后面的根降级。
- 锁定结果恰好包含根沿所选版本依赖可达的全部组件，每组件一个版本。
- 规模上限：500 个候选、100 个组件名、20 个根组件；循环依赖按普通约束求解，
  相容则成功，矛盾则判无解，不可达的矛盾不影响结果。

## 测试

```bash
python3 -m unittest discover -s tests -v
```

覆盖：根优先级与版本残留、依赖环（相容/矛盾/不可达）、20 根 500 候选的
5 秒限时强制降级用例，以及与暴力枚举对拍的随机化正确性测试。
