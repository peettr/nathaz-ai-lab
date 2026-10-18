import sqlite3,json,os,re,hashlib,subprocess,base64,collections
DB='./ftkb_desktop/page_text_v2.sqlite'
OUT=os.path.dirname(__file__)
# group, SHA prefix, physical PDF page, paraphrased question, answer, exact source anchor
Q=[
('book','5543023d8571',56,'随机数据处理教材的均匀[0,1]模拟里，100次均值的方差实测是多少？','0.00067','VAR100 = 0.00067'),
('book','8c7d3adab50c',12,'ISO液压快速接头温度试验里，未连接阀式接头在最高工作温度下至少保持多久？','6小时','at least 6 h'),
('book','a593ba1bf460',50,'日本建筑风荷载建议在低矮建筑围护构件峰值风压计算时采用的典型作用面积是多少？','1 m²','1 m2 as a typical value'),
('book','9d049ac5f7d5',17,'FEMA 273采用线性程序分析耗能装置时，基本模态的等效阻尼上限占临界阻尼多少？','30%','shall not exceed 30%'),
('book','c2c6517b234e',26,'Harris振动手册的统计能量分析里，耦合损耗因子与波动传播中的哪一系数相关？','透射系数 τ','related to the transmission coefficient'),
('book','d7b857c0bc35',16,'结构与应力分析教材的ABCD简支梁算例里，5 kN斜向荷载由A支座承担的水平反力是多少？','2.5 kN','2.5 kN'),
('book','5e95499851f2',41,'圆柱风载ESDU资料修订经验关联时，哪一个修正因子未被改动，哪一个在高湍流参数下改了趋势？','粗糙度因子λR未改，湍流因子λTcrit趋势修改','not found necessary to amend'),
('book','16d55a988ec2',175,'Soong工程概率教材中，计数到第r次成功所用试验次数服从哪种分布？','负二项（Pascal）分布 NB(r,p)','negative binomial, or Pascal'),
('book','0181bbadd7b3',187,'斜拉桥风效应书中，为几乎抑制雨风致索振动，结构阻尼比应提高到大约多少？','0.65%','damping ratio to 0.65%'),
('book','23248b5a48c2',621,'Chopra结构动力学算例中，框架A第一、二模态的基底剪力峰值分别是多少？','48.4和53.9 kips','VbA1 = f11 + f21 = 48.4 kips'),
('literature','30ab99f25a93',8,'带上侧雨水线的圆柱模型在F50设置时，涡脱落强度和约化频率相较无雨水线与F40如何变化？','涡脱落增强，约化频率降低','increase in the intensity of the vortex shedding'),
('literature','edcf36602c44',8,'SCOUT在2013年6月5日西得州外流事件中，从StickNet观测到阵风峰值前的缓升时长至少是多少？','超过5分钟','slow ramp (> 5 minutes)'),
('literature','ae4b8875cbca',11,'贴近平面地面的圆柱在薄边界层条件下，仍有涡脱落的临界相对间隙G/D是多少？','0.4','critical gap G/D = 0.4'),
('literature','3c78535142b8',7,'50米拉索桅杆风振研究的弱风实测中，X向一阶模态最大识别阻尼比是多少？','1.81%','largest value is 1.81%'),
('literature','4825e868d9bd',6,'屋檐进水回归模型给灰泥/胶合板檐口采用的类型系数，与乙烯基/铝檐口相比是多少？','灰泥/胶合板0.3；乙烯基/铝1','stucco/plywood assemblies have a factor of 0.3'),
('literature','6074f429fc20',7,'工业屋顶太阳能板试验中，面板距屋面1米、横向间距600毫米时，屋面顶面与板底压力时间历程呈什么关系？','几乎相同','almost identical pressure histories'),
('literature','545924c9a99e',11,'城市微型风机测试平台钢索设计，为避开叶片旋转激励，钢索最低频率须高于多少？','12.5 Hz','greater than 12.5Hz'),
('literature','672a073ef0ee',6,'低矮建筑屋面风压的WERFL模型—实测对照中，哪组模拟最好重现实测，但平均压力系数仍偏大？','d7','simulation d7 best reproduces'),
('literature','4d2300e75739',6,'高楼干扰试验中，d=3B时横风向干扰因子仅在什么干扰角有峰值？','22.5°','only peaked at 22.5°'),
('literature','cc905cccfca6',7,'外伸臂梁—剪力墙栓钉连接模型中，抗拉连接承载力主要取决于单钉还是钉群？','钉群','groups of studs rather than on individual studs'),
('chinese','7ae265e33a0c',374,'高层建筑锥度化风洞研究中，两种非零锥度使最大基底弯矩系数至少降低多少？','超过25%','超过25%'),
('chinese','c2c2f0c4ab13',88,'轻钢建筑风灾易损性论文中，蒙特卡罗精度提高一位数字所需工作量约增至原来的几倍？','100倍','增加100 倍的工作'),
('chinese','52bcaa3544bd',42,'热带气旋风剖面研究中，C类场地前眼壁和后眼壁的风速峰值高度分别约在何处？','前眼壁800 m，后眼壁300 m','集中在800m'),
('chinese','70ef25ed9ecf',107,'风致响应现场监测论文识别的结构一阶自振频率，在X向与Y向分别是多少？','X向0.155 Hz，Y向0.153 Hz','0.155Hz 和 0.153Hz'),
('chinese','9a3c3c5cd291',122,'超高层横风向气动阻尼博士研究中，用多少个风洞工况分析阻尼特性？','33个工况','33 个工况'),
('ocr','049ff44faab1',196,'扫描弹性稳定书谈到非弹性屈曲，超过比例极限时原有弹性临界荷载式中的弹性模量要改用哪一种模量？','切线模量','切线模量'),
('ocr','3fce33900bab',399,'扫描版信号与系统教材指出，离散时间傅里叶变换的分析式和合成式之间是否具有连续时间变换的对偶性？','没有相应对偶性','No corresponding dualicy'),
('ocr','5a0f688fa75b',217,'扫描版应用数学书中，水力模型在保持足够高流速、处于湍流的近似条件下，可忽略哪项相似要求？','雷诺数相似要求','雷诺横数的大小'),
('ocr','96e5ac9b88eb',159,'扫描版地震工程教材中，到1985年全球强震加速度仪大约部署多少台？','约7000台','约布置有7000台'),
('ocr','6b2f0e7a61fb',233,'扫描版弹性理论中，受拉椭圆孔长轴端点的边缘应力相对远场拉应力S是多少？','-S','都是- S'),
]
c=sqlite3.connect('file:'+DB+'?mode=ro',uri=True)
questions=[]
for i,(g,prefix,pg,query,answer,anchor) in enumerate(Q,1):
 row=c.execute('select p.sha256,p.text,p.origin,d.aliases_json from pages p join documents d using(sha256) where p.sha256 like ? and p.physical_page=?',(prefix+'%',pg)).fetchone()
 if not row:raise ValueError((prefix,pg))
 sha,t,origin,aliases=row
 if re.sub(r'\s+','',anchor).casefold() not in re.sub(r'\s+','',t).casefold():raise ValueError(('missing anchor',prefix,anchor))
 a=json.loads(aliases);path=a[0]['wsl']
 questions.append(dict(id=f'R5-{i:02d}',group=g,question=query,answer=answer,sha256=sha,pdf_page=pg,source_pdf=path,windows_path='I:'+path[6:].replace('/','\\'),aliases=a,title=os.path.basename(path).removesuffix('.pdf'),evidence_anchor=anchor,ocr=(origin=='OCR 文本'),verification='pending'))
# Remote independent original-page text extraction, OCR from original page only for image PDFs.
remote='''import json,sys,subprocess,re\na=json.loads(__import__('base64').b64decode(sys.argv[1]));out=[]\nfor x in a:\n try:\n  pg=str(x['pdf_page']);r=subprocess.run(['pdftotext','-f',pg,'-l',pg,'-enc','UTF-8',x['source_pdf'],'-'],capture_output=True,timeout=40);text=r.stdout.decode('utf-8','replace')\n  needle=re.sub(r'\\s+','',x['evidence_anchor']).casefold();hay=re.sub(r'\\s+','',text).casefold()\n  out.append(dict(id=x['id'],found=needle in hay,ocr=x['ocr'],excerpt=text[:500].replace('\\n',' '),error=r.stderr.decode('utf-8','replace')[:150]))\n except Exception as e:out.append(dict(id=x['id'],found=False,error=str(e)))\nprint(json.dumps(out,ensure_ascii=False))'''
encoded=base64.b64encode(remote.encode()).decode();data=base64.b64encode(json.dumps(questions,ensure_ascii=False).encode()).decode()
ssh=['ssh','-n','-o','ControlPath=~/.ssh/sockets/[邮箱]','-o','ControlMaster=no','-o','BatchMode=yes','-o','ProxyCommand=false','[邮箱]',"nice -n 19 ionice -c3 /usr/bin/python3 -c 'import base64;exec(base64.b64decode(\""+encoded+"\"))' "+data]
# shell encoded source quoted via base64 decoding into python -c; no ssh stdin/FIFO.
r=subprocess.run(ssh,capture_output=True,text=True,timeout=360)
if r.returncode:raise RuntimeError(r.stderr[-2000:])
try:checks=json.loads(r.stdout)
except:raise RuntimeError(r.stdout[-2000:]+r.stderr[-1000:])
for q,x in zip(questions,checks):
 q['verification']='original_pdf_page_ocr_repeat' if q['ocr'] and x['found'] else ('original_pdf_text' if x['found'] else 'original_page_anchor_not_confirmed')
 q['verification_excerpt']=x.get('excerpt','')[:180]
 print(q['id'],q['verification'],x.get('error',''))
with open(os.path.join(OUT,'verification_draft.jsonl'),'w') as f:
 for q in questions:f.write(json.dumps(q,ensure_ascii=False)+'\n')
print('confirmed',collections.Counter(q['verification'] for q in questions))
