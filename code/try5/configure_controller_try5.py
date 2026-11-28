from pathlib import Path
r=Path(__file__).resolve().parent
p=r/'controller_t4.py';t=p.read_text();t=t.replace('try4','try5').replace('TRY4','TRY5').replace('luw-r214a-t4-try4-1116','luw-r214a-t4-try5-1116').replace('stage_t4_v4.tar.gz','stage_t4_v2.tar.gz').replace("for variant in ('off','on','gate0'):","for variant in ('off','on','gate0','gate0_B'):")
t=t.replace("('/content/t4_out/wall_gate0.csv','wall_gate0.csv'),('/content/t4_out/wall_gate0_solver.log','wall_gate0_solver.log'),", "('/content/t4_out/wall_gate0_A.csv','wall_gate0_A.csv'),('/content/t4_out/wall_gate0_A_metrics.json','wall_gate0_A_metrics.json'),('/content/t4_out/wall_gate0_A_solver.log','wall_gate0_A_solver.log'),('/content/t4_out/wall_gate0_B.csv','wall_gate0_B.csv'),('/content/t4_out/wall_gate0_B_metrics.json','wall_gate0_B_metrics.json'),('/content/t4_out/wall_gate0_B_solver.log','wall_gate0_B_solver.log'),")
t=t.replace("('/content/t4_out/wall_gate0.csv','wall_gate0.csv'),('/content/t4_out/wall_gate0_solver.log','wall_gate0_solver.log')", "('/content/t4_out/wall_gate0_A.csv','wall_gate0_A.csv'),('/content/t4_out/wall_gate0_A_metrics.json','wall_gate0_A_metrics.json'),('/content/t4_out/wall_gate0_A_solver.log','wall_gate0_A_solver.log'),('/content/t4_out/wall_gate0_B.csv','wall_gate0_B.csv'),('/content/t4_out/wall_gate0_B_metrics.json','wall_gate0_B_metrics.json'),('/content/t4_out/wall_gate0_B_solver.log','wall_gate0_B_solver.log')")
t=t.replace("('/content/t4_out/build_gate0.log','build_gate0.log')","('/content/t4_out/build_gate0.log','build_gate0.log'),('/content/t4_out/build_gate0_B.log','build_gate0_B.log')")
t=t.replace("R/'.colab_owner'","R/'.colab_owner'")
t=t.replace('T4 retry #050ea7a4','T4 try5 #8275f850')
# Host smoke gate must read the new fixture raw files.
t=t.replace("('/content/t4_out/wall_gate0.csv','wall_gate0.csv'),('/content/t4_out/wall_gate0_solver.log','wall_gate0_solver.log')", "('/content/t4_out/wall_gate0_A.csv','wall_gate0_A.csv'),('/content/t4_out/wall_gate0_B.csv','wall_gate0_B.csv')")
assert "stage_t4_v4" not in t and 'sessions-t4-try5' in t
p.write_text(t)
print('controller_configured',p)
