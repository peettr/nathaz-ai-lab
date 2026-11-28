from pathlib import Path
r=Path(__file__).resolve().parent
p=r/'work/pack_stage/periodic_t4/src/setup.cpp';s=p.read_text()
a='''    const bool a1b=a1b_env && std::string(a1b_env)=="1";'''
b=a+'''
    const bool a1b_uniform=std::getenv("T17_A1B_UNIFORM") && std::string(std::getenv("T17_A1B_UNIFORM"))=="1";
    const bool a1b_diag=std::getenv("T17_A1B_DIAG") && std::string(std::getenv("T17_A1B_DIAG"))=="1";'''
assert s.count(a)==1;s=s.replace(a,b)
a='units.u(target_ustar/0.4f*std::log((zm+0.024f)/0.024f)+dux)';b='units.u(target_ustar/0.4f*std::log((zm+0.024f)/0.024f)+(a1b_uniform?0.0f:dux))';assert s.count(a)==1;s=s.replace(a,b)
a='lbm.u.y[n]=units.u(duy);';b='lbm.u.y[n]=units.u(a1b_uniform?0.0f:duy);';assert s.count(a)==1;s=s.replace(a,b)
a='''        if(step==1ul || step%cadence==0ul || step==steps || (a7_window && step==half_window)) sample(step);'''
b='''        if(step==1ul || (a1b_diag && step<=100ul) || (a1b_diag && step%10ul==0ul) || step%cadence==0ul || step==steps || (a7_window && step==half_window)) {
            // u is updated by stream_collide each step; explicit update_fields
            // ensures the host rho/u buffer reflects the current DDF parity.
            if(a1b_diag) lbm.update_fields();
            sample(step);
        }'''
assert s.count(a)==1;s=s.replace(a,b);p.write_text(s)
print('C1 uniform and stepwise ledger enabled')
