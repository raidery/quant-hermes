---
name: quant-wencai
description: 同花顺问财自然语言选股 — quant-claw-skill 安装、配置、常见 bug 修复
category: research
tags: [quant, A股, 选股, 同花顺, 问财]
---

# quant-wencai

同花顺问财自然语言选股工具。通过自然语言描述条件，查询符合条件的所有 A 股股票。

## 安装

```bash
# 正确方式：指定 --agent hermes，装到 ~/.hermes/skills/
curl -fsSL https://raw.githubusercontent.com/raidery/quant-claw-skill/main/install.sh | bash -s -- --agent hermes

# 安装后路径
~/.hermes/skills/quant-claw-skill/
```

**常见错误**：不加 `--agent hermes` 会装到 `~/.agents/skills/`（OpenClaw 目录），Hermes 无法识别。

## 配置 Cookie

问财需要登录 cookie（有效期约 1 个月）：

1. 浏览器登录 `https://www.iwencai.com`
2. F12 → Application → Cookies → 复制 `WENCAI_COOKIE` 的 value
3. 写入 cookie 文件：

```bash
# 方式 A：直接写入 cookie 文件
cat > ~/.hermes/skills/quant-claw-skill/.wencai_cookie << 'EOF'
你的cookie字符串
EOF

# 方式 B：写配置文件
mkdir -p ~/.wencai
echo '{"cookie": "你的cookie字符串"}' > ~/.wencai/config.json
```

环境变量 `WENCAI_COOKIE` 优先级最高，会覆盖文件配置。

## 使用方法

```bash
cd ~/.hermes/skills/quant-claw-skill
export WENCAI_COOKIE=$(cat .wencai_cookie)   # 或提前 export

# 基本查询
python3 query.py "涨幅大于5%"

# 指定返回行数
python3 query.py "连续3天涨跌幅大于0% 股票简称不包含st" --max 30
```

支持的查询类型：
- 涨跌幅条件：`涨幅大于5%`、`跌跌幅在0%到10%之间`
- 财务指标：`市盈率小于20`、`市值大于100亿`
- 行情特征：`60天涨停次数大于3次`、`收盘获利大于80%`
- 组合条件：用空格分隔多个条件
- 排除项：`股票简称不包含st`

## pywencai 安装（关键！）

quant-claw-skill 依赖 `pywencai`。安装位置必须是 Hermes 的 venv：

```bash
# 正确方式：uv pip 安装到指定 Python
uv pip install pywencai --python /home/claw/.hermes/hermes-agent/venv/bin/python

# 验证
/home/claw/.hermes/hermes-agent/venv/bin/python -c "import pywencai; print('OK')"
```

**常见错误**：
- `python3 -m pip install pywencai` 会装到系统 Python（3.12），而 Hermes 用的是 3.11 venv
- venv 没有 pip：用 `uv pip install --python /path/to/python` 而非 `python -m pip`
- pywencai 包不完整（缺少 `wencai.py`）：先删掉再重装 `rm -rf venv/lib/python3.11/site-packages/pywencai*`

## query.py 已知 bug（已修复）

原版 query.py 有 3 个 bug，已在 `/home/claw/.hermes/skills/quant-claw-skill/query.py` 中修复：

1. **CLI 参数不生效**：原版固定执行"退市股票"测试代码，完全忽略命令行参数
   - 修复：添加 `argparse`，`query` 作为位置参数，`--max` 控制行数

2. **`extract_main_dataframe` 不处理 Series**：pywencai 有时返回 `pd.Series`（列名=index，值=一行数据），原版函数会 raise ValueError
   - 修复：增加 `isinstance(result, pd.Series)` 分支 → `pd.DataFrame([result.values], columns=result.index)`

3. **`clean_column_names` 正则不完整**：无法去除 `[20260410]`、`:前复权[日期]` 等后缀，导致同名列出现多列
   - 修复：新增规则去除 `:\d{8}`、`前复权`、`日复权`、`日线数据` 等；添加列名去重（追加 `_2`, `_3`）

如需同步到远程仓库：`cd ~/.hermes/skills/quant-claw-skill && git commit -a -m "fix: CLI args, Series handling, column name cleaning" && git push`

## CSV 输出列索引（重要发现）

`query.py` 输出格式为 `|` 分隔的表格，但**列索引不等于视觉奇偶**，原因是输出包含大量前置空格，肉眼看到的"第几列"和程序 split 后的索引完全不同。

**正确解析方式**（已验证 2026-04-13）：

```python
# query.py 原始输出示例：
# | 000762.SZ  | 西藏矿业   |    33.88 |      10      |            33 | 000762 |
# [0]         [1]          [2]         [3]            [4]            [5]

for line in stdout.split("\n"):
    stripped = line.strip()
    if "|" not in stripped or "代码" in stripped or "---" in stripped:
        continue
    parts = [p.strip() for p in line.split("|")]
    if len(parts) < 5:
        continue
    code  = parts[1]   # 股票代码（含后缀 .SZ/.SH）
    name  = parts[2]   # 股票简称
    price = parts[3]   # 最新价
    chg   = parts[4]   # 涨跌幅（%），已处理 +/- 符号
```

**验证方法**：如遇涨跌幅数字异常大（如 447%），先 `repr(line)` 打印原始行，确认 split 后的实际索引。

## 数据说明

- 查询范围：A 股全市场（含北交所）
- 数据区间：通常是最近 60~90 个交易日
- 收盘获利 = 买入成本 vs 当前价格差百分比（问财特有指标）
- 新股/北交所首日股票涨跌幅可能 > 10%，属于正常数据

## cron 环境使用

```python
# ~/.hermes/scripts/my-stock-query.py
import sys, os
sys.path.insert(0, '/home/claw/.hermes/skills/quant-claw-skill')
os.environ['WENCAI_COOKIE'] = open('/home/claw/.hermes/skills/quant-claw-skill/.wencai_cookie').read().strip()

from query import query_wencai
result = query_wencai('你的查询条件', max_rows=20)
print(result)
```
