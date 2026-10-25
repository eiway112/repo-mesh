#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate_governance.py — 行业专家·跨领域治理总则仓 门禁脚本 v0.11.1

v0.11.1（2026-10-25）：M1 第③项的短语表加第 4 条「推送顺序」。
    为什么：v1.13 发布实测——先推 main、后推 tag，main 的推送立即触发镜像工作流，
    而镜像 checkout 拉的是「推送那一刻」的远端 tag 集合，于是它把旧 tag 集合原样推回，
    push 退出码 0、日志显示成功，实际无变化；随后 verify 步按当前两端集合比对判 failure。
    T5 第 6 条已补第⑤条硬动作，本处同步加短语，使该条被删改时门禁报错。

v0.11.0（2026-10-25）：第三方审计（8 组缺陷注入）坐实五处判据缺口，本轮全部按"修根因不修表象"处置。
    ① **盘符正则只认反斜杠**：`[A-Za-z]:\\` 漏掉 `D:/x` 正斜杠写法与 UNC 共享路径。三处（M8/M10/M11）
       同源修改。**必须加左侧边界 `(?<![A-Za-z0-9])`**——否则 `[A-Za-z]:[\\\\/]` 会把 `https://` 里的
       `s:/` 判成盘符，改完就从漏报变成误报（这条是审计报告未提、本轮预检发现的）。
    ② **占位符是整行豁免**：原 `if placeholder_pat.search(l): continue` 意味着"一行只要含任一占位符，
       同行的人名/领域名/盘符全部免检"——豁免范围与风险方向相反，与本仓 v1.1 攻穿教训同型。
       改为"先剔除占位符片段，再查该行剩余"，且**占位符内部文本单独跑黑名单**（否则 `{真名}` 成了新藏法）。
       同时占位符定义由"含『路径』二字的 {...}"泛化为全部 `{...}` 与 `X://`：文档说"显式占位符"泛指，
       实现只认一种，属同族"文字与实现不符"。
    ③ **M11 不检 `~/`**：docstring 明写"豁免不含 `~/`"，实现里根本没有 `~` 检查——`~/…` 正是维护者
       真实运行时路径形态，开源后照样泄漏本机结构。
    ④ **未编号 `###` 截断按节判据的取段**：`extract_section` 以 `#{1,3} ` 为节界，于是未编号的
       `### D8 处置记录` 把它所属的 4.2.1 节拦腰截断，D8 整段（约 35 行）落在 M7 盲区里。
       治本不是给标题加白名单（那又是一份要同步的清单），而是**把"节界"判据化为"带编号"**：
       只有 `#{1,2}` 与编号形 `### （4.x / T数字）` 构成节界，未编号 `###` 是节内小标题。
    ⑤ **M8 盘符行整行豁免致归因失真**：盘符行里的领域名不报 M8（只有 M10 兜底），人按 M8 清单清干净
       仍被 M10 卡住。豁免的动机是"避免重复报"，但两条报的是不同缺陷，不构成重复，故删除豁免。

v0.10.0（2026-10-20）：M1 增第③项——T5 发布硬约束条款的存在性校验（T5_REQUIRED_CLAUSES）。
    为什么必须机检：T5 第 6 条是总则里唯一一条挡住"把含真实身份的完整历史推上公开仓"
    的条文，而该事故不可逆。它若被删改而门禁仍全绿，就是「声明了约束、实际没有约束」
    ——与 M1 差集要治的病同型，也与公理 G6（未标注的降级 = 未降级）同源。
    只校验条文存在性，不校验人有没有照做：推送动作发生在仓外，机检执行位置够不到。

v0.9.0（2026-10-20）：FOURTH_SUBSECTIONS 登记总则新增的 4.7「总则公理表（可反转前提）」。
    为什么必须同步：M1 的子节双向差集一旦漏登记，该节即处于无判据覆盖状态而门禁全绿
    （v1.5 攻穿已证：4.2.1 与 4.6 曾长期如此）。本处是脚本与文档之间唯一需要手工同步的清单。

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
         M2 只认公开远端域名、态②的私有远端占位标记、或「（本机存档）」标记，
         不接受 `~/` 与盘符（本机符号换机器即失效）；
         M8 扫本文件全文（**不再豁免盘符行**：盘符行里的领域名同样是缺陷，由 M10 另行报盘符本身）；
         M9/M11 共用同一份 PERSON_NAMES 黑名单；
         M10 盘符路径一律 FAIL，不对"（本机存档）"标记行豁免（2026-10-07 攻穿修复，见 check_m10 注释）；
         M11 扫描范围＝仓内一切文本文件（按内容判定，非扩展名白名单），减去 **M9/M10 专属对象
         （总则、脚本自身）** 与黑名单配置（`names.local*`）——注意这不等于"冻结四件"，
         README 与接入登记册仍在 M11 扫描面内；
         检出形态＝盘符路径（正/反斜杠）、`~/` 家目录、UNC 共享路径、黑名单词（人名/领域名/仓名）；
         「（本机存档）」标记不构成 M11 豁免，只有占位符才是；占位符**只剔除片段本身**，
         不豁免同行其余内容，且占位符内部文本同样跑黑名单；
         黑名单来自 names.local.json（**始终取脚本所在目录，与 `--root` 无关**），
         缺失时回落内置示例值——此时 M8/M9/M11 的禁现能力形同虚设，门禁仍会 PASS，
         须由调用者自行判断（总则 §4.5：未标注的降级 = 未降级，按未达标处理）。

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

# ---- 本机路径形态（三处判据共用的唯一定义：判据一分叉就会从接缝长出放行点）----
# 盘符：`D:\x` 与 `D:/x` 均属合法绝对路径写法，只认反斜杠等于把漏检交给"作者恰好写哪种"。
# 前置边界 `(?<![A-Za-z0-9])` 不可省：没有它，`https://` 里的 `s:/` 会被判成盘符——
# 改完 F2 反而会从漏报变误报（本机预检实测：注入一行普通 URL 即触发）。
DRIVE_PAT = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]")
# 家目录：`~/…` 只在本机展开，与盘符同性质。
# **要求 `~/` 后紧跟路径名字符**（v0.11.0）：这不是放宽，是分清"路径"与"提及路径"。
# 判据文档里必然要写"不接受 `~/` 这类本机符号"——句中 `~/` 后面是标点，不是路径；
# 若一律命中，则"解释这件事本身也会把词写进扫描面"，与本仓 M11 上线时抓到作者自己
# 两句人名是同一个坑（reports/P4 §五已记）。真实的"家目录 + 私有运行时子目录"路径仍会命中。
HOME_PAT = re.compile(r"(?<![A-Za-z0-9])~[\\/][A-Za-z0-9._$-]")
# UNC 共享路径：`\\server\share` 同样是本机网络结构信息，旧实现完全不在检出面。
UNC_PAT = re.compile(r"(?<![A-Za-z0-9])\\\\[^\s\\]+\\")
# 显式占位符：`{...}`（任意内容）与 `X://`（协议头占位）。
# 旧实现只认"含『路径』二字的 {...}"，而仓内实际占位符有多种命名（如 `{本仓远端}`），
# 于是"文档说泛指、实现只认一种"——同族第三次（前两次：M11 扫描面、判据口径）。
# `X://` 用前置边界限定为字面 X，避免把 `https://` 的 `s://` 当成占位符。
PLACEHOLDER_PAT = re.compile(r"\{[^}\n]*\}|(?<![A-Za-z])X://")

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
    "### 4.7 总则公理表（可反转前提）",
]
# M1 ③：T5 发布硬约束的关键短语（v0.10.0 新增）
# 为什么必须机检：T5 第 6 条挡的是"直接推送本地分支 ⇒ 含真实身份的完整历史被公开"，
# 该事故不可逆。条文若被删改而门禁全绿，等于条文不存在——与 4.2.1/4.6 曾长期无覆盖
# 是同一种病（声明了检查、实际没执行），只是这次声明的是"约束"而非"检查"。
# 为什么是短语而不是整段比对：整段比对会因一次措辞调整就误报，把判据变成格式锁；
# 短语取的是三个不可替代的动作要件——禁令本身、唯一合法做法、历史面扫描。
# 范围显式声明（P-17）：只查 T5 节内是否出现，不查别处，也不校验发布时是否照做。
T5_REQUIRED_CLAUSES = [
    "禁止直接推送",   # 核心禁令：不得直接推送本仓分支
    "干净仓",         # 唯一合法做法：另起干净仓单提交
    "逐提交",         # 历史面：逐提交扫全历史，不只扫 tip
    "推送顺序",       # 2026-10-25 补：main 与 tag 须同推，否则镜像拿到过期 tag 集合
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
# 为什么与 names.local.json.example 逐词一致（v0.11.0 起）：两套示例词会让"此刻在哪个态"
# 多一层心智负担——回落态与照抄 example 态的黑名单不同，排查"为什么没抓到"时先得搞清用的是哪套。
# 一致性不是靠注释保证的：example 文件在 M11 豁免面内（`names.local*` 前缀），
# 故词表相同不会自锁（旧注释说"生僻词才不自锁"，该前提在扫描面加上前缀豁免后已不成立）。
_DEF_PERSON = ["维护者姓名占位", "维护者姓氏占位"]      # 示例值，非真实身份
_DEF_DOMAIN = ["示例领域词甲", "示例领域词乙"]           # 示例值，非真实领域
_DEF_PROJECT = ["示例仓库名占位", "example-org/example-repo"]  # 示例值


def _load_names():
    """读取 names.local.json；缺失或损坏则回落到内置示例值。

    回落到示例值而不是空列表：空名单会让所有黑名单判据恒为 0 命中，
    看起来"全绿"，实则无对象（P-01 要防的正是这个）。

    **位置固定取脚本所在目录，与 `--root` 无关**（v0.11.0 写明）：缺陷注入自证时把仓复制到
    临时目录、用 `--root` 指过去，脚本读的仍是原仓的黑名单——不知道这点会把"读到了真实名单"
    误当成"临时仓没配名单"，从而把回落态当成真实态来解释读数。
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
# M2：态②（仅有私有远端）的显式占位标记（总则 §2.5 定位规则三态之态②）。
# v0.11.0 补：文档定义了态②这一合法写法，而实现只认公开远端域名与「（本机存档）」两种 token
# ——按文档规范登记的私有远端行会被判"定位不可复现"。制度承诺了一种机器不认的写法，
# 是本仓最忌讳的"制度与实现脱节"（F6 实测：按 §2.5 态② 规范改写一行即 FAIL）。
PRIVATE_REMOTE_MARK = "（占位：公开版不含真实远端"
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
    """返回从标题行到下一个**节界**之间的文本。

    节界判据（v0.11.0 改，治本）：`#`/`##` 级标题一律是节界；`###` 级**只有带编号的**
    （`4.x` 系列与 `T数字` 系列）才算节界。未编号的 `###` 是节内小标题，不截断。

    为什么改：旧实现以 `#{1,3} ` 为节界，于是未编号的 `### D8 处置记录` 把它所属的 4.2.1 截断，
    该段约 35 行落在 M7 盲区里而门禁全绿（2026-10-25 第三方审计 C4 注入坐实；现行文档已中招，
    不是假想风险）。修法**不是**给未编号标题加白名单——那又是一份要人工同步的清单，
    与本仓批判的"两份清单"同病；而是把"节界"判据化为"带编号"，新增节标题必须编号才能自成节，
    漏编号的后果是"内容归上一节、被上一节的判据覆盖"（安全方向），而不是"内容无人覆盖"。
    """
    m = re.search(header_pat, text)
    if not m:
        return ""
    nxt = re.search(r"\n(?:#{1,2} |### (?=\d|T\d))", text[m.end():])
    end = m.end() + nxt.start() if nxt else len(text)
    return text[m.start():end]


def strip_placeholders(line):
    """剔除行内显式占位符片段，返回 (剩余文本, 占位符内部文本列表)。

    为什么不是"整行豁免"（v0.11.0 治本）：旧写法 `if placeholder_pat.search(l): continue`
    意味着**一行只要含任一占位符，同行的人名/领域名/盘符全部免检**——实测注入
    `{本机路径}/x.md <真名> <真领域名>` 直接 exit 0。占位符的本意是"这个片段已脱敏"，
    实现却成了"这一行全部放行"，豁免范围与风险方向相反（与 v1.1 攻穿教训同型）。

    为什么要把占位符内部文本单独返回：剔除即豁免，那 `{某真实公司名}` 就成了新藏法。
    占位符只承诺"花括号里是占位内容"，不承诺"花括号里没有真实值"，故内部同样要过黑名单。
    """
    inner = []

    def _repl(m):
        tok = m.group(0)
        if tok.startswith("{"):
            inner.append(tok[1:-1])
        return ""

    return PLACEHOLDER_PAT.sub(_repl, line), inner


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
    # --- T5 发布硬约束条款存在性（v0.10.0 新增）---
    # 判据只守"条文在不在"。守不住"发布时有没有照做"——后者发生在仓外的推送动作上，
    # 本脚本的执行位置是仓内工作树，够不到。该边界已在总则 §4.1 M1 第③项三问处写明，
    # 不许把本项读作"发布已受机检保护"。
    t5 = extract_section(text, r"### T5 发布通道纪律")
    if not t5:
        fail("M1", "未找到 T5 发布通道纪律节——P-01：无对象即未能检查，不静默通过")
    else:
        for c in T5_REQUIRED_CLAUSES:
            if c not in t5:
                fail("M1", f"T5 节缺发布硬约束关键短语「{c}」——该条被删改后门禁会静默全绿")
    # --- ④ `###` 标题必须带编号（v0.11.0 新增）---
    # 为什么：`###` 是"这是第几节"的视觉约定，但节界只认编号（见 extract_section）。
    # 未编号的 `###` 看起来自成节、实际被并入上一节——形成"作者以为有判据、其实没有"的模糊地带。
    # 治理文档里最贵的一类缺陷是"负责这件事的人以为别人在负责"。
    # 修法是让"标题即节"重新成立：要么编号（4.x / 1.x / T数字），要么降为 `####`（节内小标题）。
    # 为什么不开白名单：白名单又是一份要靠人记性同步的清单，与本仓反复批判的
    # FOURTH_SUBSECTIONS 手工同步同病，只是把"忘登记"换成"忘加进白名单"，问题形状不变。
    bad_h3 = [h for h in re.findall(r"^### (.+)$", text, re.M)
              if not re.match(r"(?:\d|T\d)", h)]
    for h in bad_h3:
        fail("M1", f"`###` 级标题「{h[:40]}」未编号——未编号的 `###` 不构成节界，其内容会被并入上一节"
                   f"且不被单独检查。要么给它编号（如 `4.2.2`），要么降为 `####`（声明它是节内小标题）")


def check_m2(text):
    seg = extract_section(text, r"### 2\.5 沿用对象台账")
    if not seg:
        fail("M2", "未找到 2.5 沿用对象台账节")
        return
    # 分隔行判定用正则，不用子串（v0.11.0 改）：原 `"---" not in l` 会把**含该子串的数据行**
    # 一并丢掉，且丢得无声无息——审计实测：同一行"定位不可复现"的违规，加个 `a---b` 后就
    # 完全逃出 M2（报 1 项 → 报 0 项）。这不是"脆弱"，是"加个字符串就能绕过本条判据"。
    sep_row = re.compile(r"^\|[\s:|-]+\|$")
    rows = [l for l in seg.splitlines()
            if l.strip().startswith("|") and not sep_row.match(l.strip())]
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
        # v0.11.0 补态②（PRIVATE_REMOTE_MARK）：总则 §2.5 定义了三态，旧实现只认其中两态的写法，
        # 按文档规范登记的私有远端行反而 FAIL——机制与文档各说各话（见常量定义处注释）。
        if not ("github.com" in loc or "gitee.com" in loc
                or LOCAL_ARCHIVE_MARK in loc or PRIVATE_REMOTE_MARK in loc):
            fail("M2", f"台账行定位不可复现（只认公开远端域名、态②的「{PRIVATE_REMOTE_MARK}…」"
                       f"占位标记、或「{LOCAL_ARCHIVE_MARK}」标记；"
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


def _check_numbered_rows(lines, tag, upto, label):
    """编号行须存在且**每一行**都带「沿用/新立」标注。

    v0.11.0 改：原实现只查首个匹配行（`row[0]`），若同一编号出现两行（复制粘贴事故），
    第二行即使无标注也照样通过——"只检查第一个"与本仓 P-01（检查对象数量为 0 即未检查）
    是同一族：数量为 2 时检查了 1 个，无人知道。
    三组（M/H/A）原本是三段复制代码，此处合成一处，避免判据各写一份后各自演化。
    """
    for i in range(1, upto + 1):
        rows = [l for l in lines if l.strip().startswith(f"| {tag}{i} |")]
        if not rows:
            fail("M4", f"{tag}{i} 行缺失")
            continue
        for r in rows:
            if not any(k in r for k in ("沿用", "新立")):
                fail("M4", f"{tag}{i} 行缺「沿用/新立」标注" + ("（同编号出现多行，逐行检查）" if len(rows) > 1 else ""))


def check_m4(text, lines):
    for tname in T_SECTIONS:
        seg = extract_section(text, re.escape(tname))
        if not seg:
            fail("M4", f"未找到节：{tname}")
        elif not any(k in seg for k in ("沿用", "新立")):
            fail("M4", f"{tname} 节缺「沿用/新立」标注")
    _check_numbered_rows(lines, "M", 11, "机检判据")
    _check_numbered_rows(lines, "H", 5, "人裁判据")
    _check_numbered_rows(lines, "A", 6, "接入验收")
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

    豁免范围（v0.11.0）：**无豁免**。原实现豁免"含盘符的行"（理由是 M10 会另行判 FAIL），
    但两条报的是**不同缺陷**——盘符是路径泄漏，领域名是制度污染，同一行可以同时犯两条。
    豁免的实际后果是 M8 的报数偏少：人按 M8 清单清干净"领域名"，门禁仍被 M10 卡住，
    查不到是同一行里的另一半问题（审计 C7 实测：总则盘符行藏领域名，仅 M10 报、M8 静默）。
    更早的版本（v1.1 前）曾豁免"含 github.com/gitee.com 的行"，那次收窄已证明豁免方向与风险相反。
    """
    for i, l in enumerate(lines, 1):
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
    """本机绝对路径形态（盘符 / 家目录 / UNC）一律 FAIL。

    历史缺陷（2026-10-07 攻穿发现并修复）：原实现对含"（本机存档）"标记的行整体豁免，
    而本机存档行恰恰最容易混入盘符路径（登记人习惯性写绝对路径），豁免等于放行。
    现改为：标记只豁免"路径可复现性"这一层表述诉求，不豁免本机形态本身。

    v0.11.0 扩形态（审计 F2/F5 坐实）：原只认反斜杠盘符，`D:/x` 与 `~/…`、`\\\\server\\share`
    全部零检出。三种形态性质相同（换机器即失效、泄漏本机结构），故口径与 M11 统一。
    """
    for i, l in enumerate(lines, 1):
        # 路径检查在"剔除占位符后"的文本上做（v0.11.0）：否则占位符 `X://…` 里的 `X:/`
        # 会被 DRIVE_PAT 判成盘符——判据文档里写 `X://` 这个占位符本身就要报 FAIL，
        # 等于"文档不能提占位符长什么样"。剔除只作用于占位符片段，同行其余内容照查。
        visible, _ = strip_placeholders(l)
        if DRIVE_PAT.search(visible):
            fail("M10", f"第 {i} 行出现本机盘符绝对路径（换机器即失效；本机存档行用标记+相对说明，私有远端行用远端+仓内相对路径）：{l.strip()[:60]}")
        if HOME_PAT.search(visible):
            fail("M10", f"第 {i} 行出现家目录路径 `~/`（只在本机展开，换机器即失效）：{l.strip()[:60]}")
        if UNC_PAT.search(visible):
            fail("M10", f"第 {i} 行出现 UNC 共享路径（本机网络结构，其他使用者无此路径）：{l.strip()[:60]}")


def _m11_line(rel, lineno, text, where="", check_home=True):
    """对一段文本跑 M11 的全部检出形态。三处共用，防止"各写一份"后各自演化。"""
    at = f"{rel} 第 {lineno} 行" + (f"{where}" if where else "")
    if DRIVE_PAT.search(text):
        fail("M11", f"{at}出现本机盘符路径：{text.strip()[:55]}")
    if check_home and HOME_PAT.search(text):
        fail("M11", f"{at}出现家目录路径 `~/`：{text.strip()[:55]}")
    if UNC_PAT.search(text):
        fail("M11", f"{at}出现 UNC 共享路径：{text.strip()[:55]}")
    for name in PERSON_NAMES:
        if name in text:
            fail("M11", f"{at}出现个人身份「{name}」：{text.strip()[:45]}")
    for name in DOMAIN_NAMES + PROJECT_NAMES:
        if name in text:
            fail("M11", f"{at}出现禁现词「{name}」：{text.strip()[:45]}")


def check_m11(repo):
    """全仓开源卫生：全仓非本判据专属对象中，本机路径 / 人名 / 领域名 / 仓名 = 0。

    与 M9/M10 的关系：M9/M10 只扫总则正文（本文件），本条扫本文件之外的一切文档，
    三者共用同一份黑名单（见文件头 NAMES），**不得各写一份**——
    判据一分叉就会从接缝长出新的放行点（2026-10-07 已实测两次）。

    豁免只认三种：仓内相对路径（不含盘符、`~/`、UNC）、显式占位符（`{...}` / `X://`）、
    以及下面的"本判据专属对象"清单。
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

    v0.11.0 变更（三处，均由 2026-10-25 第三方审计注入坐实）：
    ① 占位符由"整行 continue"改为"剔除片段后查剩余"，且占位符内部文本同样过黑名单；
    ② 补 `~/` 与 UNC 形态（原 docstring 写着"豁免不含 ~/"，实现里根本没有 `~` 检查）；
    ③ 排除集由 basename 匹配改为仓内相对路径匹配（原实现会连带豁免子目录里的同名文件）。
    """
    # 本判据的专属对象（不扫）：
    #  - 总则.md：由 M9/M10 全权负责（本文件正文口径与全仓口径不同，重复扫会同一缺陷报两次）
    #  - 脚本自身：黑名单定义处即名单来源，扫自己等于自证（P-01 同族）。配置外置后
    #    脚本内不再持有真实名单，此豁免的暴露面趋近于零。
    #  - names.local*：黑名单本身即名单，扫它等于自证。
    # **措辞修正（v0.11.0）**：旧注释把这些称作"冻结对象"。冻结四件是总则/登记册/README/脚本，
    # 其中登记册与 README **在**本判据扫描面内——称"冻结对象"会被读成"这两件不扫"，
    # 措辞比实现更宽，属"检查器自称覆盖了它没覆盖的对象"的反向版本，同样必须改。
    OWNED_BY_M9M10 = {"总则.md", "validate_governance.py"}
    targets = []
    for p in sorted(repo.rglob("*")):
        if p.is_dir() or ".git" in p.parts or "__pycache__" in p.parts:
            continue
        rel = p.relative_to(repo).as_posix()
        if rel in OWNED_BY_M9M10 or p.name.startswith("names.local"):
            continue
        raw = p.read_bytes()
        if not _is_text(raw):
            continue  # 二进制（图片、pyc 等）不参与文本判据
        targets.append((p, rel))
    if not targets:
        fail("M11", "全仓未找到任何可扫描文件——M11 无对象，等于未检查")
        return

    for p, rel in targets:
        txt = p.read_text(encoding="utf-8", errors="replace")
        # `.github/` 下的 `~/` 指向 **CI runner 的家目录**（/home/runner），与任何使用者的本机
        # 目录结构无关——这是全仓唯一一处 `~/` 不指向"本机"的位置，属执行环境差异而非放水。
        # 其余形态（盘符 / UNC / 黑名单）在该目录内照常检查。
        is_ci = rel.startswith(".github/")
        for i, l in enumerate(txt.splitlines(), 1):
            visible, inner = strip_placeholders(l)
            _m11_line(rel, i, visible, check_home=not is_ci)
            for tok in inner:
                # 占位符**内部**不豁免：`{某真实公司名}` 是剔除法带来的新藏法，必须一并查。
                _m11_line(rel, i, tok, where="（占位符内）", check_home=not is_ci)


def check_ledger(ledger_text):
    for need in LEDGER_FILE_MUST_CONTAIN:
        if need not in ledger_text:
            fail("L1", f"接入登记册缺要素：{need}")


USAGE = "用法：python validate_governance.py [--root PATH]"


def _parse_args(argv):
    """手工解析参数，**不用 argparse**。

    为什么不用 argparse（2026-10-25 第三方审计建议 argparse 化，此处不采纳并写明理由）：
    argparse 对参数错误默认 `SystemExit(2)`，而本仓退出码的语义是
    2 = "扫描完成、有 FAIL"、1 = "至少一个目标未能扫描"。参数写错会被上游读成
    "扫完了、有失败"，与"没跑成"混为一谈——正是三值约定要防的那种混淆。
    故参数错误一律 exit 1。

    为什么未知参数必须报错而不是忽略（原实现静默忽略）：实测把 `--root` 拼成 `--rot` 时，
    原实现照常扫脚本所在目录并 exit 0——使用者以为"指定了根目录且通过"，实际扫的是另一个仓。
    "便捷信号 ≠ 权威状态"，静默忽略是它的典型形态。
    """
    root = None
    rest = list(argv)
    while rest:
        a = rest.pop(0)
        if a == "--root":
            if not rest:
                print(f"ERROR[参数] --root 缺少路径参数")
                print(USAGE)
                return None, 1
            root = Path(rest.pop(0))
        elif a in ("-h", "--help"):
            print(USAGE)
            return None, 0
        else:
            print(f"ERROR[参数] 未知参数：{a}（不接受位置参数；未知参数一律报错，不静默忽略）")
            print(USAGE)
            return None, 1
    return root, None


def main():
    root, code = _parse_args(sys.argv[1:])
    if code is not None:
        return code
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
    # 只报"在不在"不报绝对路径：绝对路径本身就是本机结构，门禁输出常被贴进 issue / 报告。
    _bl = Path(__file__).resolve().parent / "names.local.json"
    print(f"提示：M11 扫描面＝仓内一切文本文件，减 M9/M10 专属对象（总则、脚本自身）与 names.local*；"
          f"黑名单取自脚本同目录 names.local.json（{'在位' if _bl.is_file() else '缺失→已回落示例值，按 §4.5 读作未达标'}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
