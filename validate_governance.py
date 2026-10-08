#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate_governance.py — 行业专家·跨领域治理总则仓 门禁脚本 v0.8.0

判据：总则.md §4.1（M1–M11）+ 接入登记册格式检查。
退出码（沿用三值约定，见总则 §2.5 台账）：
    0 = 扫描完成，无 FAIL
    2 = 扫描完成，有 FAIL
    1 = 至少一个目标未能扫描（"没跑成"不等于"通过"）

自守（沿用 build-expert 断言模式库）：
    P-01 阴性失效拦截：检查对象数量为 0 时退出码 1，不静默通过。
    P-02 退出码可信：失败即非零。
    P-05 漂移数字不写字面量：假设声明数、锚点命中数均从文件解析。
    P-17 判据范围显式声明：M3 只查 §1.5 声明的术语；M4 只查 T/M/H/A 各行与 4.4 节；
         M2 只认公开远端域名或「（本机存档）」标记，不接受 ~/ 与盘符（本机符号换机器即失效）；
         M8/M9 黑名单为显式词表，仅"路径形态行"（含远端域名或盘符）对 M8 豁免；
         M10 盘符路径一律 FAIL，不对"（本机存档）"标记行豁免（2026-10-07 攻穿修复，见 check_m10 注释）；
         M11 扫描范围＝仓内一切文本文件（按内容判定，非扩展名白名单），减去冻结对象；
         与 M9/M10 共用同一份 PERSON_NAMES 黑名单；「（本机存档）」标记不构成M11 豁免，
         只有显式占位符才是。黑名单来自 names.local.json，缺失时回落内置示例值——
         此时 M8/M9/M11 的禁现能力形同虚设，门禁仍会PASS，须由调用者自行判断
         （总则 §4.5：未标注的降级 = 未降级，按未达标处理）。

用法：
    python validate_governance.py [--root PATH]   # --root 指定仓根（默认脚本所在目录；缺陷注入自证用）
"""
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ---- 结构定义（与总则.md 同步演进：改章节名必须同步此处，M1 正是抓两者漂移的） ----
ANCHORS = [
    "## 一、定位与边界",
    "## 二、思想底座",
    "## 三、总则六件（T1–T6）",
    "## 四、验收与降级",
    "## 五、假设集中节",
]
T_SECTIONS = [
    "### T1 领域编号注册表",
    "### T2 接入登记册",
    "### T3 跨仓口径裁决规则",
    "### T4 骨架引用与裁剪规则",
    "### T5 发布通道纪律",
    "### T6 总则自身验收",
]
FOURTH_SUBSECTIONS = [
    "### 4.1 总则自举机检",
    "### 4.2 人裁",
    "### 4.2.1 待决事项登记",
    "### 4.3 实例仓接入验收",
    "### 4.4 跨仓一致性门禁",
    "### 4.5 降级与豁免",
    "### 4.6 机检脚本与退出码",
]
# M2：台账必须登记到的关键对象（正文"沿用"引用中出现过的）
LEDGER_MUST_CONTAIN = [
    "build-expert", "技能定义骨架规范", "README", "P-03", "P-04", "P-06",
    "P-07", "P-10", "P-11", "P-15", "退出码",
]
# ---- 黑名单：配置驱动（v0.7.0 起）----
# 为什么外置：黑名单若写死在脚本里，本脚本一旦开源分发，等于把维护者身份与
# 业务领域一并公开——实测历史 9/9 个提交都含真名，靠改文件无法收口。
# 为什么保留示例值：开源使用者拿到的是空名单时，M8/M9 会因"无对象"而永远 FAIL
# （见check_m11 的 P-01），等于脚本不可用。示例值让它开箱可跑；
# 使用者按自己情况改 names.local.json（该文件已 .gitignore）或改下面三处示例。
# 单一来源：M8/M9/M11 共用本处，不得各写一份。
_DEF_PERSON = ["维护者姓名占位", "维护者姓氏占位"]      # 示例值，非真实身份
_DEF_DOMAIN = ["示例领域词甲", "示例领域词乙"]           # 示例值，非真实领域
_DEF_PROJECT = ["示例仓库名占位", "example-org/example-repo"]  # 示例值


def _load_names():
    """读取 names.local.json；缺失或损坏则回落到内置示例值。

    回落到示例值而不是空列表：空名单会让所有黑名单判据恒为 0 命中，
    看起来"全绿"，实则无对象（P-01 要防的正是这个）。
    """
    local = Path(__file__).resolve().parent / "names.local.json"
    data = {}
    if local.is_file():
        try:
            data = json.loads(local.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"WARN[黑名单] names.local.json 解析失败，回落到内置示例值：{e}")
    return {
        "person": data.get("person") or _DEF_PERSON,
        "domain": data.get("domain") or _DEF_DOMAIN,
        "project": data.get("project") or _DEF_PROJECT,
    }


NAMES = _load_names()
PERSON_NAMES = NAMES["person"]      # M9：人名/个人称呼（总则正文禁现）
DOMAIN_NAMES = NAMES["domain"]      # M8：领域名（总则正文禁现）
PROJECT_NAMES = NAMES["project"]  # 仓名/远端：并入 M8（正文）与 M11（全仓）执行，不另立编号

# M10：台账"（本机存档）"标记（该类行的定位不随仓分发，见总则 §2.5 定位规则与假设 H-6）
LOCAL_ARCHIVE_MARK = "（本机存档）"
# 登记册必须存在的要素
LEDGER_FILE_MUST_CONTAIN = [
    "## 二、登记表", "## 三、前缀注册表",
    "PIE-", "MAT-", "CST-",
]

FAILS = []


def _is_text(raw: bytes) -> bool:
    """按内容判定文本 / 二进制，替代"按扩展名列举"。

    判据：能以 UTF-8 解码且不含 NUL 字节即视为文本。
    为什么不能用扩展名白名单：白名单 = 又一份名单 = "新增文件默认不在检查范围"
    （与 M11 治本时删掉的那份文件名单同一个病）。实测漏检 `.github/workflows/*.yml`，
    其中硬编码的真实邮箱因此长期零命中而门禁全绿——判据没执行，等于声明了检查。

    攻穿自证（v0.8.0）：对一张 PNG 判False、对 .yml/.md/.py 判 True，见 main 的负例。
    """
    if b"\x00" in raw[:8192]:
        return False
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def fail(code, msg):
    FAILS.append(f"[{code}] {msg}")


def extract_section(text, header_pat):
    """返回从标题行到下一个同级或更高级标题之间的文本。"""
    m = re.search(header_pat, text)
    if not m:
        return ""
    nxt = re.search(r"\n#{1,3} ", text[m.end():])
    end = m.end() + nxt.start() if nxt else len(text)
    return text[m.start():end]


def check_m1(text, lines):
    for a in ANCHORS:
        n = sum(1 for l in lines if l.strip() == a)
        if n != 1:
            fail("M1", f"锚点「{a}」命中 {n} 次（应为 1）——章节漂移或被复制")
    # --- 第四章子节双向差集（2026-10-07 攻穿新增）---
    # 历史缺陷：本函数原先只查一级章节，第四章子节完整性无人校验。FOURTH_SUBSECTIONS
    # 仅被M7 消费（且仅"节存在才查"），于是 4.2.1、4.6 这两节长期从未被任何判据覆盖，
    # 而门禁全绿。属"声明了检查、实际没执行"。
    # 修法不是补清单（那仍是两份要同步的清单），而是校验两个方向：
    #   声明 ⊆ 实际（登记的节必须真实存在）+ 实际 ⊆ 声明（实际节必须已登记）
    # 后者才是能自动抓出"新增节忘了登记"的那一半。
    actual_fourth = re.findall(r"^### (4\.\d+(?:\.\d+)*) ", text, re.M)
    if not actual_fourth:
        fail("M1", "未从总则.md 解析出任何第四章子节——正则或章节格式已变，判据失效")
        return
    declared = [re.match(r"### (4\.\d+(?:\.\d+)*)", s).group(1) for s in FOURTH_SUBSECTIONS]
    for d in declared:
        if d not in actual_fourth:
            fail("M1", f"脚本声明的子节 {d} 在总则.md 中不存在——判据清单与文档漂移")
    for a in actual_fourth:
        if a not in declared:
            fail("M1", f"总则.md 存在子节 {a} 但脚本 FOURTH_SUBSECTIONS 未登记——该节不受任何判据覆盖")


def check_m2(text):
    seg = extract_section(text, r"### 2\.5 沿用对象台账")
    if not seg:
        fail("M2", "未找到 2.5 沿用对象台账节")
        return
    rows = [l for l in seg.splitlines() if l.strip().startswith("|") and "---" not in l]
    body_rows = rows[1:] if rows else []
    if not body_rows:
        fail("M2", "台账表无数据行")
        return
    for r in body_rows:
        cells = [c.strip() for c in r.strip().strip("|").split("|")]
        if len(cells) < 4 or not all(cells[:4]):
            fail("M2", f"台账行三栏有空：{r[:60]}")
            continue
        if not re.search(r"\d{4}-\d{2}-\d{2}", cells[3]):
            fail("M2", f"台账行缺时效戳：{cells[0][:30]}")
        loc = cells[1]
        # 攻穿修复（2026-10-07）：原实现把 "~/" 也算作可复现定位，等于放行。
        # "~" 只在本机展开，换机器即失效——与"（本机存档）"同类，只是更隐蔽：
        # 它看起来像路径不像标记，登记人不会意识到自己写的是本机专属形式。
        if not ("github.com" in loc or "gitee.com" in loc or LOCAL_ARCHIVE_MARK in loc):
            fail("M2", f"台账行定位不可复现（只认公开远端域名或「{LOCAL_ARCHIVE_MARK}」标记；"
                       f"本机符号（如 ~ 开头、或盘符开头者）均不接受——前者只在本机展开，后者换机器即失效）：{cells[0][:30]}")
    for key in LEDGER_MUST_CONTAIN:
        if key not in seg:
            fail("M2", f"台账缺关键沿用对象登记：{key}")


def check_m3(text):
    scope_note = "（P-17：只查 1.5 节声明的术语）"
    sec15 = extract_section(text, r"### 1\.5 术语")
    terms = re.findall(r"^- \*\*(.+?)\*\*：", sec15, re.M)
    if len(terms) < 5:
        fail("M3", f"1.5 术语表行数异常：{len(terms)} {scope_note}")
        return
    for t in terms:
        n = len(re.findall(r"\*\*" + re.escape(t) + r"\*\*：", text))
        if n != 1:
            fail("M3", f"术语「{t}」定义出现 {n} 次（应仅 1 次）{scope_note}")


def check_m4(text, lines):
    for tname in T_SECTIONS:
        seg = extract_section(text, re.escape(tname))
        if not seg:
            fail("M4", f"未找到节：{tname}")
        elif not any(k in seg for k in ("沿用", "新立")):
            fail("M4", f"{tname} 节缺「沿用/新立」标注")
    for i in range(1, 12):
        row = [l for l in lines if l.strip().startswith(f"| M{i} |")]
        if not row:
            fail("M4", f"M{i} 行缺失")
        elif not any(k in row[0] for k in ("沿用", "新立")):
            fail("M4", f"M{i} 行缺「沿用/新立」标注")
    for i in range(1, 6):
        row = [l for l in lines if l.strip().startswith(f"| H{i} |")]
        if not row:
            fail("M4", f"H{i} 行缺失")
        elif not any(k in row[0] for k in ("沿用", "新立")):
            fail("M4", f"H{i} 行缺「沿用/新立」标注")
    for i in range(1, 7):
        row = [l for l in lines if l.strip().startswith(f"| A{i} |")]
        if not row:
            fail("M4", f"A{i} 行缺失")
        elif not any(k in row[0] for k in ("沿用", "新立")):
            fail("M4", f"A{i} 行缺「沿用/新立」标注")
    seg44 = extract_section(text, r"### 4\.4 跨仓一致性门禁")
    if seg44 and not any(k in seg44 for k in ("沿用", "新立")):
        fail("M4", "4.4 节缺「沿用/新立」标注")


def check_m5(text):
    sec5 = extract_section(text, r"## 五、假设集中节")
    if not sec5:
        fail("M5", "未找到第五章·假设集中节")
        return
    declared = re.search(r"【假设】共\s*(\d+)\s*条", sec5)
    if not declared:
        fail("M5", "第五章缺「【假设】共 N 条」声明行（P-05：声明数须写在文件内供解析）")
        return
    n_declared = int(declared.group(1))
    n_marks_sec5 = len(re.findall(r"【假设】H-", sec5))
    if n_declared != n_marks_sec5:
        fail("M5", f"声明 {n_declared} 条 vs 第五章 H- 标记 {n_marks_sec5} 条，不一致")
    n_total = len(re.findall(r"【假设】", text))
    n_in_sec5 = len(re.findall(r"【假设】", sec5))
    if n_total != n_in_sec5:
        fail("M5", f"【假设】标记出现在第五章之外（全文 {n_total} 次 vs 章内 {n_in_sec5} 次）")


def check_m6(text):
    pat = re.compile(r"【[^】]*[小中大][^】]*】")
    for tname in T_SECTIONS:
        seg = extract_section(text, re.escape(tname))
        if seg and not pat.search(seg):
            fail("M6", f"{tname} 节缺适用档位标注【小/中/大】")


def check_m7(text):
    three_kws = ("触发点", "谁做", "可删")
    scopes = [(re.escape(t), t) for t in T_SECTIONS] + \
             [(re.escape(s), s) for s in FOURTH_SUBSECTIONS]
    for pat, name in scopes:
        seg = extract_section(text, pat)
        if seg and "新立" in seg:
            for kw in three_kws:
                if kw not in seg:
                    fail("M7", f"{name} 节含新立机制，但三问缺「{kw}」")


def check_m8(lines):
    """总则正文零领域名 + 零仓名。

    豁免范围（v0.7.0 再收窄）：**只豁免盘符行**，不再豁免远端域名行。
    历史缺陷：为让沿用台账能写远端地址，把"含 github.com/gitee.com 的行"整行豁免，
    等于给出"领域名可藏在远端地址里"的放行口——实测总则 §2.5 台账正是这样带着
    3 处真实仓名长期全绿。公开版不该带任何仓名，故本条连远端域名一并判FAIL。
    远端地址若确需登记，写进接入登记册（该处已脱敏为占位），不写进总则正文。
    """
    drive_pat = re.compile(r"[A-Za-z]:\\")
    for i, l in enumerate(lines, 1):
        if drive_pat.search(l):
            continue  # 盘符行豁免（本机专属形态，且 M10 会另行判FAIL）
        for name in DOMAIN_NAMES:
            if name in l:
                fail("M8", f"第 {i} 行出现领域名「{name}」：{l.strip()[:60]}")
        for name in PROJECT_NAMES:
            if name in l:
                fail("M8", f"第 {i} 行出现仓名「{name}」（公开版不应带真实仓名）：{l.strip()[:60]}")


def check_m9(lines):
    for i, l in enumerate(lines, 1):
        for name in PERSON_NAMES:
            if name in l:
                fail("M9", f"第 {i} 行出现人名「{name}」：{l.strip()[:60]}（责任人身份以仓库托管平台账号登记）")


def check_m10(lines):
    """盘符绝对路径一律FAIL。

    历史缺陷（2026-10-07 攻穿发现并修复）：原实现对含"（本机存档）"标记的行整体豁免，
    而本机存档行恰恰最容易混入盘符路径（登记人习惯性写绝对路径），豁免等于放行。
    现改为：标记只豁免"路径可复现性"这一层表述诉求，不豁免盘符本身。
    """
    drive_pat = re.compile(r"[A-Za-z]:\\")
    for i, l in enumerate(lines, 1):
        if drive_pat.search(l):
            fail("M10", f"第 {i} 行出现本机盘符绝对路径（换机器即失效；本机存档行用标记+相对说明，私有远端行用远端+仓内相对路径）：{l.strip()[:60]}")


def check_m11(repo):
    """全仓开源卫生：全仓非冻结件中，本机路径 / 人名 / 领域名 / 仓名 = 0。

    与 M9/M10 的关系：M9/M10 只扫总则正文（本文件），本条扫本文件之外的一切文档，
    三者共用同一份黑名单（见文件头 NAMES），**不得各写一份**——
    判据一分叉就会从接缝长出新的放行点（2026-10-07 已实测两次）。

    豁免只认两种：仓内相对路径（不含盘符与 ~/）、显式占位符（{本机路径} / X://…）。
    「（本机存档）」这类标记**不是**豁免理由——它是给人看的说明，不是脱敏。

    v0.7.0 变更（治本）：扫描面由"reports/ + 策划方案"这份显式名单，
    改为"全仓 .md/.py/.json 减去冻结对象"。原名单漏掉了接入登记册与本脚本自身
    ——实测本脚本曾硬编码真实姓名、而门禁长期全绿。名单式扫描面的通病是
    "新增文件默认不在检查范围"，与 P-01 的假设直接冲突。

    v0.8.0 变更（治本·第二次）：扫描面由"后缀白名单 .md/.py/.json"改为
    **"仓内一切文本文件，按内容判定文本/二进制"**。原后缀白名单仍是名单式的一种变体——
    实测 v0.7.0 之后新增的 `.github/workflows/*.yml` 落在白名单外，
    其中硬编码的真实邮箱因此长期零命中、门禁全绿。后缀白名单与显式文件名单
    是同一个病的两种写法：**新增文件默认不在检查范围**。按内容判定则与扩展名无关，
    新增任何文本文件都自动进面。

    为什么不能靠扩后缀表（实测会自锁）：把 .yml 加进白名单本身是对的，
    但那只是把同一个漏洞往后推一格——下一种新后缀仍会漏。治本在取消名单机制本身。
    """
    drive_pat = re.compile(r"[A-Za-z]:\\")
    placeholder_pat = re.compile(r"\{[^}]*路径[^}]*\}|X://")

    # 冻结对象由 M9/M10 负责，不在本条重复扫描（职责不重叠，避免同报两次）
    # 本脚本自身进豁免：黑名单定义处即名单来源，扫自己等于自证（P-01 的同族问题）。
    # 代价是脚本内的黑名单字面量不受 M11 管——这正是 names.local.json 外置要解决的问题：
    # 配置外置后脚本内不再持有任何真实名单，此豁免的暴露面趋近于零。
    frozen = {"总则.md", "validate_governance.py"}
    targets = []
    for p in sorted(repo.rglob("*")):
        if p.is_dir() or ".git" in p.parts or "__pycache__" in p.parts:
            continue
        if p.name in frozen or p.name.startswith("names.local"):
            continue  # 黑名单本地配置本身就是名单，扫它等于自证
        raw = p.read_bytes()
        if not _is_text(raw):
            continue  # 二进制（图片、pyc 等）不参与文本判据
        targets.append(p)
    if not targets:
        fail("M11", "全仓未找到任何可扫描文件——M11 无对象，等于未检查")
        return

    for p in targets:
        txt = p.read_text(encoding="utf-8", errors="replace")
        rel = p.relative_to(repo).as_posix()
        for i, l in enumerate(txt.splitlines(), 1):
            if placeholder_pat.search(l):
                continue  # 显式占位符＝已脱敏，豁免成立
            if drive_pat.search(l):
                fail("M11", f"{rel} 第 {i} 行出现本机盘符路径：{l.strip()[:55]}")
            for name in PERSON_NAMES:
                if name in l:
                    fail("M11", f"{rel} 第 {i} 行出现个人身份「{name}」：{l.strip()[:45]}")
            for name in DOMAIN_NAMES + PROJECT_NAMES:
                if name in l:
                    fail("M11", f"{rel} 第 {i} 行出现禁现词「{name}」：{l.strip()[:45]}")


def check_ledger(ledger_text):
    for need in LEDGER_FILE_MUST_CONTAIN:
        if need not in ledger_text:
            fail("L1", f"接入登记册缺要素：{need}")


def main():
    args = [a for a in sys.argv[1:]]
    root = None
    if "--root" in args:
        i = args.index("--root")
        root = Path(args[i + 1])
    repo = root if root else Path(__file__).resolve().parent

    targets = {
        "总则.md": repo / "总则.md",
        "接入登记册.md": repo / "接入登记册.md",
        "README.md": repo / "README.md",
    }
    missing = [name for name, p in targets.items() if not p.is_file()]
    if missing:  # P-01：目标缺失=未能扫描，退出码 1
        for name in missing:
            print(f"ERROR[扫描失败] 未能扫描：{name}（路径：{targets[name]}）")
        print(f"共 {len(missing)} 个目标未能扫描——「没跑成」不等于「通过」")
        return 1

    text = targets["总则.md"].read_text(encoding="utf-8")
    lines = text.splitlines()
    ledger_text = targets["接入登记册.md"].read_text(encoding="utf-8")

    check_m1(text, lines)
    check_m2(text)
    check_m3(text)
    check_m4(text, lines)
    check_m5(text)
    check_m6(text)
    check_m7(text)
    check_m8(lines)
    check_m9(lines)
    check_m10(lines)
    check_m11(repo)
    check_ledger(ledger_text)

    if FAILS:
        for f_ in FAILS:
            print("FAIL:", f_)
        print(f"扫描完成，共 {len(FAILS)} 项 FAIL")
        return 2
    print("PASS：M1–M11 机检全部通过；接入登记册格式通过；全仓开源卫生通过")
    print("提示：机检全过 ≠ 合格，人裁 H1–H5 须另行裁定（总则 §4.2，机检与人裁分账）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
