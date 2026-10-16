#!/usr/bin/env python3
"""Fixed, pre-retrieval fact questions, from seeded random candidate PDF pages.
Questions manually paraphrased; anchors checked against the local physical-page text.
"""
import sqlite3,json,hashlib,re
from pathlib import Path
root=Path(__file__).resolve().parent.parent
out=root/'questions_round2.jsonl'
assert not out.exists(),'Frozen question file exists; refuse overwrite'
# key, physical page, paraphrase question, evidence substring, stratum
q=[
('K3ASP9NE',60,'In the EEG spectral example, what sampling interval corresponds to the highest displayed frequency of 100 Hz?','sampling time of the EEG recording was 5 ms','book'),
('KPBJ2Q75',12,'When investigating only the lowest portion of the atmosphere, up to what altitude does the urban-flow CFD guide permit nondivergent, constant-density approximations?','lowest 200 m of the atmosphere','book'),
('39YYXL6Z',11,'What initial bearing and translation speed were assigned to the unrefined center trajectory for Hurricane Anita?','azimuth of 238° at a uniform speed of 4.9','book'),
('S65QCHK7',35,'How large was the RMS central-pressure error of the objective Dvorak technique against reconnaissance in the cited Australian-region technical review?','RMS error of 8.34 hPa','book'),
('RZEVJ5SF',57,'What approximate lateral-to-longitudinal integral length-scale ratio is suggested in the wind-effects textbook?','0.33 Lxu','book'),
('FLBEWYL9',63,'What dry-air gas constant in cgs units is quoted in the introductory fluid dynamics textbook?','2-870 x i o 6','book'),
('9WK23VTL',12,'在固体力学 PINN 反问题中，哪项损失通常比 PDE 残差更快接近零？','Ldata 更快的接近于零','chinese_source'),
('XERQ28BD',8,'该神经算子湍流研究用多少个历史时刻作输入，相邻时刻间隔多少 DNS 步？','5 个等间隔历史时刻','chinese_source'),
('END-5c6650f021459749',8,'台风风场综述所述美国规范阵风系数采用的平均时距是多少？','美国规范取平均时','chinese_source'),
('Y9PBXS6X',3,'莫拉克数值实验的内层网格水平分辨率和垂直层数分别是多少？','垂 直 分 层 41','chinese_source'),
('N8U68UKD',5,'该中文入口湍流综述指出，哪种离散合成方法没有在长度尺度设定中考虑与相干函数的关系？','DSRFG 方法中的 Ls 取值并未考虑','chinese_source'),
('END-8e2357a4ce1354e2',41,'飓风增强阶段，低等效位温入流在距中心大约多少公里内会潜入旋转气流之下？','within 100–200 km of the hurricane center','zh_to_en'),
('END-e5dff59bce47f62f',8,'QuikSCAT 极轨卫星的轨道高度约多少公里？','altitude of 802 km','zh_to_en'),
('END-277e15744c1bc5ab',8,'马斯达尔城城市冠层验证用了哪几个安装高度的风速传感器？','10, 30, 40, 49, 50 m','zh_to_en'),
('NRY39CFZ',8,'半主动调谐液柱阻尼器研究所用结构离散为几个楼层？','lumped at five levels','zh_to_en'),
('END-11337c33e67b01ef',17,'该解析台风场模型比较三个台风时采用的最大风速半径参数是多少公里？','rm = 80 km','zh_to_en'),
('T474JX49',8,'In the two-tall-building interference experiment, at roughly what turbulence intensity did the deflection buffeting factor approach unity?','17–18%','english_fact'),
('8IC5IFK5',14,'What peak-to-jet-speed ratio gave the best match between an individual physical simulation and a full-scale downburst record?','best agreement between the simulated and full-scale data resulted in a ratio of 1.5','english_fact'),
('EXPLLAVM',13,'When lateral and vertical length scales were altered by half, how much did the RMS vertical velocity change in the inflow-generation experiment?','less than 10% in vrms','english_fact'),
('END-89050149d0168200',10,'Which two horizontal grid spacings are contrasted for Bangladesh tropical cyclone simulation datasets?','between 1.5 km and 4.4 km','english_fact'),
('PCC65EWE',12,'In the rear-flank downdraft field transect, by how many kelvins did equivalent potential temperature fall as wind speed jumped?','12 K decrease','english_fact'),
('END-cbfdec8cf042f731',11,'What were the five above-sea-level measurement elevations used by the coupled WRF–OpenFOAM study?','65 m, 50 m, 14 m, 12.7 and 11.7','english_fact'),
('END-be1c418c110406d8',11,'What 12-hour wind-speed forecast error did the GFDL hurricane system exhibit, compared with other guidance?','6.1 m s21','english_fact'),
('END-96601aaef4ee6b2d',12,'How large was the reported lag at its upper end across heaving amplitudes in the oscillation-amplitude study?','10% with little variation','english_fact'),
('D7VX4FA2',11,'After what paddle-motion delay were two laboratory gusts compared for reproducibility?','2 s counted from the time','english_fact'),
('END-01cc42be5109592e',19,'What natural frequency was reported for the streamlined bridge model with length-scale ratio two?','0.083 Hz','english_fact'),
('26B88CI7',13,'How much larger than the isolated-building design value was the most negative peak pressure in the rectangular building interference cases?','50% higher than the design value','english_fact'),
('END-ce1f522e93687033',4,'What temporal coverage and native grid dimensions characterize the reanalysis in the WeatherBench dataset?','hourly for 40 years from 1979 to 2018','english_fact'),
('END-c26a0f24687a4766',4,'Which WRF-ARW version underpins the engineering tropical-cyclone wind field model?','WRF-ARW, version 3.4','english_fact'),
('END-93a00b9d52d359a7',4,'In the blunt-plate measurements, what upper bound was reported for the acquisition delay across channels?','up to 35 channels','english_fact'),
]
c=sqlite3.connect('./ftkb/index.sqlite')
rows=[]
for i,(key,page,question,anchor,group) in enumerate(q,1):
 v=c.execute('SELECT title,text,pdf,type FROM pages WHERE key=? AND page=?',(key,page)).fetchone()
 assert v,(key,page)
 assert anchor.casefold() in v[1].casefold(),(key,page,anchor)
 assert page>1
 rows.append(dict(id=f'R{i:02}',question=question,answer_key=key,answer_page=page,answer_title=v[0],source_pdf=v[2],source_type=v[3],stratum=group,evidence=anchor))
assert len(rows)==30 and len({r['answer_key'] for r in rows})==30
assert sum(x['stratum']=='book' for x in rows)>=5 and sum(x['stratum']=='chinese_source' for x in rows)>=5 and sum(x['stratum']=='zh_to_en' for x in rows)>=5
out.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows))
print('FROZEN',out,'N',len(rows),'sha256',hashlib.sha256(out.read_bytes()).hexdigest())
