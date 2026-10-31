#!/usr/bin/env python3
"""Create fresh pre-submit experiment cards; never replace existing cards."""
from pathlib import Path
import hashlib,datetime
base=Path(__file__).parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-4))).strftime('%m-%d %H:%M')
for tag in ('B0','B0prime','B1','REF'):
    card=base/f'EXPERIMENT_CARD_v12_{tag}.md'
    assert not card.exists(),card
    ctl=base/'case_config_v12'/('controlDict_REF' if tag=='REF' else 'controlDict')
    root=Path('/users/[用户]')/f'L22_6_T03_v12_{tag}_20261021_01'
    text=f'''# EXPERIMENT_CARD · L22.6 T03 v1.2 {tag}

① 假设：统计 5–120 s 后，B0 与 B0prime 的差刻画不同随机起始种子的噪声底；B1 不响应 psi，REF 的当地平均风向与协方差比 B1 更接近 B0。该卡唯一标签 {tag}。

② 唯一改动：相对 v1.1，复合改动为 endTime 40→120 s、任务拆为单核独立作业；{tag} 的输入 {'psi=0，原版 TInF' if tag in ('B0','B0prime') else ('带 psi 但原版忽略' if tag=='B1' else '带 psi，私有参考实现旋转平均与脉动')}。原版 RNG 用 time(NULL) 作种子，无数字 seed 控制键：B0/B0prime 分时启动，在运行日志记启动 epoch，无法如实声称固定种子 1/2。REF 源码仅驻 CRC 私有目录，sha256 在提交前核对并在报告列值。

③ 配置及 SHA-256：本线 stage_T03_v12.py {sha(base/'stage_T03_v12.py')}；本线 run_T03_v12.sh {sha(base/'run_T03_v12.sh')}；本线 case_config_v12/{ctl.name} {sha(ctl)}；上游 E7 输入 / TInF 8737a0d5，源运行根仅只读。

④ ComputeOps 申请：待回；作业号待提交后填；运行根 {root}；日志 {root}/workflow.log、log.pimpleFoam；提交后 rc-job --card 本卡；1 核、h_rt=6 h。

⑤ 通过判据（提交前写定 {now} 美东）：blockMesh/checkMesh/pimpleFoam 均退出 0，run.exitcode=0；50 个入口探针、统计窗 5–120 s 连续，分析按 0.005 s 抽样；五高度均值与 R 有限，对角 R 正；ρ 非对角按 |ρ候选−ρB0| 计算；首次零交点前积分，无零交点明确右删失。尺度仅供参考，不参与分级。噪声底各高度各主指标取 |B0prime−B0|；REF/B1 区分的操作定义为 REF 在五高度平均风向误差和 |ρ_yz−ρ_yz,B0| 至少各有 3 个高度低于 B1，另逐格报值与噪声底，不以此替代委托方正式阈值。失败如实回填，不事后改判据。
'''
    card.write_text(text)
    print(card)
