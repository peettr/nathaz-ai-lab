import json,subprocess
inst=json.load(open("/content/out/rmse_better_but_miss.json"))
for g,p,a,b in (("G2_win40",95,"bilinear_c4","M0"),("G1_full200",95,"bilinear_c5","M0")):
    c=[i for i in inst if i["group"]==g and i["pct"]==p and i["A_rmse_better"]==a and i["B"]==b]
    best=max(c,key=lambda i:(i["RMSE_B"]-i["RMSE_A"])/i["RMSE_B"]*min(1,len(i["regions_missed_by_A"])))
    print(g,best["time"],best["RMSE_A"],best["RMSE_B"],best["coverA"],best["coverB"])
    print(subprocess.run(["python","/content/plot_instance.py",g,str(best["time"]),a,b,str(p)],capture_output=True,text=True,cwd="/content"))
