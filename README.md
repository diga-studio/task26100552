# SketchStack 模板联合选版器

为脚手架文件生成阶段产出**锁定清单**：给定内存中的模板候选目录、目标技术栈和
一组根组件，选出一组同时满足全部依赖区间的版本。只处理清单层面的版本依赖，
不解析、不渲染 Jinja2 正文。

## 数据模型

- `Version`：`(major, minor, patch)` 三元组，均为非负整数，依次比较；
  不支持预发布/构建元数据。`parse_version("1.2.3")` / `format_version(v)` 互转。
- `Dependency(name, lower, upper)`：必需依赖，版本区间为 `[lower, upper)`，
  只能在同一技术栈内解析。
- `Candidate(name, stack, version, deps)`：一个已发布的模板候选。
- `LockResult`：`ok` 为 `False` 时 `reason` 说明无解原因；为 `True` 时
  `pins` 是 `{组件名: 版本}` 的锁定清单，`root_versions` 按 roots 顺序给出根版本。

## 用法

```python
from sketchstack import Candidate, Dependency, parse_version, resolve

catalog = [
    Candidate("page", "web", (2, 0, 0),
              (Dependency("base", (1, 0, 0), (2, 0, 0)),)),
    Candidate("page", "web", (1, 0, 0), ()),
    Candidate("base", "web", (1, 4, 0), ()),
]
result = resolve(catalog, "web", ["page"])
if result.ok:
    print(result.pins)          # {'base': (1, 4, 0), 'page': (2, 0, 0)}
    print(result.root_versions) # ((2, 0, 0),)
else:
    print(result.reason)
```

## 求解保证

- 锁定清单恰好包含根组件沿所选版本依赖可达的全部组件，回退过的组件不残留。
- 每个组件只选一个版本，全部依赖区间同时满足，其他技术栈的候选不能补位。
- 在所有合法结果中，根版本按 roots 顺序组成的向量字典序最大
  （只有前面的根保不住时才为后面的根降级）。
- 循环依赖按普通约束处理；无关组件的矛盾不影响求解。
- 不物化笛卡尔积，不设搜索次数/深度/耗时上限，无解判定是完整的。

规模假设：目录 ≤500 候选、≤100 组件名，一次请求 ≤20 个根组件。

## 测试

```bash
python3 -m pytest tests/ -q
```
