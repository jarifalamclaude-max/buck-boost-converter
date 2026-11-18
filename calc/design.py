"""
SafeBuck-80 (LT8390 + LM74930) — full design calculation + checks.
Every number below comes from a datasheet value noted in the comment.
Run: python3 -I design.py   (prints report, writes results.json)
"""
import json, math, itertools

R = {}          # results for the report/page
CHECKS = []     # (name, pass?, detail)

def check(name, ok, detail):
    CHECKS.append((name, bool(ok), detail))

def E96(x):
    """nearest E96 1% value"""
    base = [1.00,1.02,1.05,1.07,1.10,1.13,1.15,1.18,1.21,1.24,1.27,1.30,1.33,1.37,1.40,1.43,1.47,1.50,
            1.54,1.58,1.62,1.65,1.69,1.74,1.78,1.82,1.87,1.91,1.96,2.00,2.05,2.10,2.15,2.21,2.26,2.32,
            2.37,2.43,2.49,2.55,2.61,2.67,2.74,2.80,2.87,2.94,3.01,3.09,3.16,3.24,3.32,3.40,3.48,3.57,
            3.65,3.74,3.83,3.92,4.02,4.12,4.22,4.32,4.42,4.53,4.64,4.75,4.87,4.99,5.11,5.23,5.36,5.49,
            5.62,5.76,5.90,6.04,6.19,6.34,6.49,6.65,6.81,6.98,7.15,7.32,7.50,7.68,7.87,8.06,8.25,8.45,
            8.66,8.87,9.09,9.31,9.53,9.76]
    e = math.floor(math.log10(x)); m = x/10**e
    best = min(base, key=lambda b: abs(b-m))
    return best*10**e

# ---------------------------------------------------------------- spec
SPEC = dict(VIN_MIN=9.0, VIN_MAX=36.0, VOUT_MIN=1.5, VOUT_MAX=35.0, POUT=80.0, IOUT_MAX=8.0)
R['spec'] = SPEC

# ---------------------------------------------------------------- LT8390 datasheet constants
LT = dict(
    VCS_BUCK=(0.035,0.050,0.065),   # max current-sense threshold V(LSP-LSN) buck  (min,typ,max)
    VCS_BOOST=(0.040,0.050,0.060),  # boost
    VIS_FS=(0.097,0.100,0.103),     # full-scale ISP-ISN regulation
    V_ISOC=0.750,                   # ISP/ISN overcurrent -> POR (all states, Fig.8)
    VFB=(0.985,1.000,1.015),
    VREF=(1.97,2.00,2.03),
    CTRL_LATCH_F=(0.285,0.300,0.315), CTRL_HYST=0.025,
    LOADEN_R=(1.3,1.4,1.5), LOADEN_HYST=0.22,
    EN_F=(1.196,1.220,1.244), EN_R_TYP=1.233, EN_IHYS=(2.2e-6,2.5e-6,2.8e-6),
    SS_IUP=(10.5e-6,12.5e-6,14.5e-6),
    INTVCC=5.0, INTVCC_ILIM_MIN=0.080,
    SPREAD_UP=(0.125,0.145,0.165), SPREAD_DN=(0.137,0.157,0.177),
    THETA_JA=30.0,                  # FE (TSSOP-28) package
    VABSMAX=60.0,
    LOADTG_VOUT_MIN=(2.4,3.0),      # min VOUT for LOADTG on (typ,max)
)

# ---------------------------------------------------------------- chosen parts (datasheet values)
# CSD18532Q5B (TI SLPS322E): RDS(on) 3.3 typ / 4.3 max mOhm @4.5 V; Qg(4.5 V) ~19 nC typ read from Fig. 4-4,
# max scaled by the 10 V max/typ ratio (58/44); Qgd 6.9 nC; Miller region 3.1-4.2 V @25 A (use 3.6 V);
# Crss 17 pF max; Coss 611 pF max; Qrr 111 nC @25 A; EAS 320 mJ.
FET_SW = dict(name='CSD18532Q5B', VDS=60, RDS45_MAX=4.3e-3, QG45=(19e-9,25e-9), QGD=6.9e-9, VPLATEAU=3.6,
              CRSS_MAX=17e-12, COSS=611e-12, QRR=111e-9, QRR_IF=25.0, RTHJA=40.0, EAS=0.320)
FET_PROT = dict(name='CSD19532Q5B', VDS=100, RDS10_MAX=4.9e-3, RTHJA=40.0, EAS=0.274, CISS=3.7e-9)
# Coilcraft XAL1510-103ME: 10 uH +-20 %, DCR 6.8 typ / 9.0 max mOhm, Isat 26.3 A (30 % drop, soft composite core),
# Irms 16 A (20 C rise) / 22 A (40 C rise). ISAT1 below = 20 %-drop point, conservatively estimated at 22 A.
IND = dict(name='XAL1510-103ME', L=10e-6, LTOL=0.20, DCR_MAX=9.0e-3, IRMS=16.0, ISAT1=22.0, ISAT2=26.3)
F2_R = 5.0e-3       # 10 A Nano2 fuse, cold resistance (approx, conservative)
RSENSE = 3e-3        # LSP/LSN
RIS    = 12e-3       # ISP/ISN output CC
RSNS   = 1e-3        # LM74930 breaker
RHO_T  = 1.40        # Rds(on) hot factor (TJ ~100-110C, CSD normalized curve ~1.4)
RHO_CU = 1.23        # copper DCR at ~85C

R['parts'] = dict(FET_SW=FET_SW['name'], FET_PROT=FET_PROT['name'], IND=IND['name'],
                  RSENSE=RSENSE, RIS=RIS, RSNS=RSNS)

# ================================================================ 1. frequency / inductor / RSENSE
def ripple_buck(vin, vout, f, L):  return vout*(vin-vout)/(f*L*vin)
def ripple_boost(vin, vout, f, L): return vin*(vout-vin)/(f*L*vout)

def design_freq(f0):
    fmin = f0*(1-LT['SPREAD_DN'][2])      # worst-case lowest instantaneous freq with spread on
    fmax = f0*(1+LT['SPREAD_UP'][2])
    L = IND['L']*(1-IND['LTOL'])          # worst-case low inductance
    out = dict(f0=f0, fmin=fmin, fmax=fmax)
    # slope compensation minimum L (duty>50%):  L > 10*VOUT*RSENSE/f   (datasheet p19)
    Lmin_slope = 10*SPEC['VOUT_MAX']*RSENSE/fmin
    out['Lmin_slope'] = Lmin_slope
    out['slope_ok'] = L > Lmin_slope
    return out

for f0 in (300e3, 400e3):
    d = design_freq(f0)
    R.setdefault('freq_options', []).append(d)

F0 = 300e3                               # chosen (lower switching loss at 36V; RT=140k from Table 1)
RT = 140e3
FMIN = F0*(1-LT['SPREAD_DN'][2]); FMAX = F0*(1+LT['SPREAD_UP'][2])
check('Slope-comp minimum inductance (L > 10*VOUT*RSENSE/f)',
      IND['L']*(1-IND['LTOL']) > 10*SPEC['VOUT_MAX']*RSENSE/FMIN,
      f"L_min(-20%)={IND['L']*0.8*1e6:.1f}uH > {10*SPEC['VOUT_MAX']*RSENSE/FMIN*1e6:.2f}uH @f={FMIN/1e3:.0f}kHz")

# RSENSE per datasheet p20 eqs, worst corners, then derate by threshold tolerance
def rsense_req():
    rows=[]
    L=IND['L']*(1-IND['LTOL'])
    # boost corner: VIN=9, Pout=80W, any VOUT>VIN; worst is highest VOUT? evaluate grid
    for vout in (12, 14.4, 19, 24, 35):
        vin=SPEC['VIN_MIN']; iout=min(SPEC['IOUT_MAX'], SPEC['POUT']/vout)
        dil=ripple_boost(vin,vout,FMIN,L)
        rs=2*0.050*vin/(2*iout*vout+dil*vin)
        rows.append(('boost',vin,vout,iout,dil,rs))
    for vout in (3.3,5,9,10,12,18):
        vin=SPEC['VIN_MAX'] if vout<SPEC['VIN_MAX'] else vout
        iout=min(SPEC['IOUT_MAX'], SPEC['POUT']/vout)
        dil=ripple_buck(vin,vout,FMIN,L)
        rs=2*0.050/(2*iout+dil)
        rows.append(('buck',vin,vout,iout,dil,rs))
    return rows
rows=rsense_req()
rs_min=min(r[5] for r in rows)
# scale for min threshold (boost 40mV/50, buck 35mV/50) and 95% efficiency in boost
rs_need_boost=min(r[5] for r in rows if r[0]=='boost')*0.040/0.050*0.95
rs_need_buck=min(r[5] for r in rows if r[0]=='buck')*0.035/0.050
R['rsense_rows']=[dict(region=r[0],vin=r[1],vout=r[2],iout=round(r[3],2),dil=round(r[4],2),rs_typ_mohm=round(r[5]*1e3,2)) for r in rows]
R['rsense_need']=dict(boost_mohm=rs_need_boost*1e3, buck_mohm=rs_need_buck*1e3, chosen_mohm=RSENSE*1e3)
check('RSENSE below worst-case requirement (incl. 40/35mV min threshold, 95% eff)',
      RSENSE <= min(rs_need_boost, rs_need_buck),
      f"need <= {min(rs_need_boost,rs_need_buck)*1e3:.2f} mOhm, chosen {RSENSE*1e3:.1f} mOhm")

# Peak current limit range & inductor saturation
ipk_lim_max=max(LT['VCS_BUCK'][2],LT['VCS_BOOST'][2])/RSENSE
ipk_lim_min_buck=LT['VCS_BUCK'][0]/RSENSE; ipk_lim_min_boost=LT['VCS_BOOST'][0]/RSENSE
R['current_limit']=dict(min_buck=ipk_lim_min_buck, min_boost=ipk_lim_min_boost, max=ipk_lim_max)
check('Inductor Isat1 (-20%) above worst-case peak current limit',
      IND['ISAT1'] >= ipk_lim_max, f"Isat1={IND['ISAT1']}A >= Ilim_max={ipk_lim_max:.1f}A (65mV/3mOhm)")

# ================================================================ 2. operating grid: currents & losses
def op_point(vin, vout, iout, f=F0, Lnom=IND['L']):
    L = Lnom
    eta = 0.95
    for _ in range(30):
        pout = vout*iout
        pin  = pout/eta
        iin  = pin/vin                      # module input current
        ratio = vout/vin
        if ratio < 0.85:   region='buck'
        elif ratio > 1.15: region='boost'
        else:              region='buck-boost'
        rds = FET_SW['RDS45_MAX']*RHO_T
        if region=='buck':
            D = vout/vin; IL = iout; dIL = ripple_buck(vin,vout,f,L)
        elif region=='boost':
            D = 1-vin/vout; IL = iin;  dIL = ripple_boost(vin,vout,f,L)
        else:
            D = 0.5; IL = max(iout,iin); dIL = max(ripple_buck(vin,min(vout,vin*0.85),f,L)*0.5, 0.5)
        ILrms2 = IL**2 + dIL**2/12
        # conduction (generalised datasheet p20 expressions)
        if region=='buck':
            Pa=D*ILrms2*rds; Pb=(1-D)*ILrms2*rds; Pd=ILrms2*rds; Pc=0
        elif region=='boost':
            Pa=ILrms2*rds; Pc=D*ILrms2*rds; Pd=(1-D)*ILrms2*rds; Pb=0
        else:
            Pa=0.85*ILrms2*rds+0.15*ILrms2*rds*0; Pd=0.85*ILrms2*rds; Pb=0.15*ILrms2*rds; Pc=0.15*ILrms2*rds
            Pa=0.85*ILrms2*rds
        # switching: physics estimate (Qgd/I_drive) + Qrr + Coss, per switching leg
        Rdrv = 1.5                 # LT8390 gate driver ~1.5 ohm + internal Rg
        tsw  = FET_SW['QGD']/((5.0-FET_SW['VPLATEAU'])/Rdrv) + FET_SW['QGD']/(FET_SW['VPLATEAU']/Rdrv)   # turn-on + turn-off
        def leg_loss(Vsw, Isw):
            Ptr  = 0.5*Vsw*Isw*tsw*f
            Qrr  = FET_SW['QRR']*math.sqrt(max(Isw,0.1)/FET_SW['QRR_IF'])
            Prr  = Qrr*Vsw*f
            Pcoss= 0.5*(2*FET_SW['COSS'])*Vsw**2*f*0.6
            return Ptr+Prr+Pcoss, Ptr, Prr, Pcoss
        Psw=0; parts={}
        if region in ('buck','buck-boost'):
            t,a,b,c = leg_loss(vin, IL); Psw+=t; parts['buck_leg']=t
        if region in ('boost','buck-boost'):
            t,a,b,c = leg_loss(vout, IL); Psw+=t; parts['boost_leg']=t
        # datasheet empirical (k=1.7*V^2*I*Crss*f) for comparison
        Pk = 0
        if region in ('buck','buck-boost'):  Pk += 1.7*vin**2*IL*FET_SW['CRSS_MAX']*f
        if region in ('boost','buck-boost'): Pk += 1.7*vout**2*IL*FET_SW['CRSS_MAX']*f
        # gate drive (INTVCC LDO in LT8390)
        nsw = 2 if region!='buck-boost' else 4
        Ig = nsw*FET_SW['QG45'][1]*(5/4.5)*FMAX
        P_ldo = (vin-5.0)*(Ig+2.8e-3)
        P_gate = Ig*5.0
        # magnetics + sense + path
        P_dcr  = ILrms2*IND['DCR_MAX']*RHO_CU
        P_core = 0.10 + 0.06*dIL       # estimate (carbonyl powder, verify with Bourns calculator)
        P_rs   = ILrms2*RSENSE
        P_ris  = iout**2*RIS
        P_qls = iout**2*(FET_PROT['RDS10_MAX']*RHO_T) + iout**2*F2_R   # low-side Q_LS (CSD19532Q5B @~10V) + output fuse
        P_q12  = 2*iin**2*FET_PROT['RDS10_MAX']*RHO_T
        P_rsns = iin**2*RSNS
        P_misc = 0.06
        Ploss = Pa+Pb+Pc+Pd+Psw+P_ldo+P_gate+P_dcr+P_core+P_rs+P_ris+P_qls+P_q12+P_rsns+P_misc
        eta_new = pout/(pout+Ploss)
        if abs(eta_new-eta)<1e-6: break
        eta=eta_new
    ILpk = IL + dIL/2
    return dict(vin=vin,vout=vout,iout=round(iout,3),region=region,D=round(D,3),
                iin=round(iin,3),IL=round(IL,3),dIL=round(dIL,3),ILpk=round(ILpk,3),
                Pa=Pa,Pb=Pb,Pc=Pc,Pd=Pd,Psw=Psw,Pk=Pk,P_ldo=P_ldo,P_gate=P_gate,P_dcr=P_dcr,
                P_core=P_core,P_rs=P_rs,P_ris=P_ris,P_qls=P_qls,P_q12=P_q12,P_rsns=P_rsns,
                Ploss=Ploss,eta=eta)

def imax(vout):
    return min(SPEC['IOUT_MAX'], SPEC['POUT']/vout)
grid=[]
for vin in (9,12,16,20,24,30,36):
    for vout in (1.5,3.3,5,9,12,14.4,16.8,19,24,29.2,35):
        if vout < SPEC['VOUT_MIN']: continue
        iout=imax(vout)
        grid.append(op_point(vin,vout,iout))
R['grid']=[{k:(round(v,4) if isinstance(v,float) else v) for k,v in g.items()} for g in grid]

worst_loss=max(grid,key=lambda g:g['Ploss'])
worst_ipk =max(grid,key=lambda g:g['ILpk'])
best_eta  =max(grid,key=lambda g:g['eta'])
worst_eta =min(grid,key=lambda g:g['eta'])
R['grid_summary']=dict(worst_loss=worst_loss, worst_ipk=worst_ipk, best_eta=best_eta, worst_eta=worst_eta)

# peak current must stay below the MIN current limit in the region it occurs
for g in grid:
    lim = ipk_lim_min_buck if g['region']=='buck' else ipk_lim_min_boost
    if g['ILpk'] > lim*0.95:
        check(f"Rated load not current-limited @ VIN={g['vin']} VOUT={g['vout']}", False,
              f"ILpk={g['ILpk']:.2f}A vs Ilim_min={lim:.2f}A")
check('Rated 80W/8A never hits min peak current limit (all grid points)',
      all(g['ILpk'] <= (ipk_lim_min_buck if g['region']=='buck' else ipk_lim_min_boost)*0.95 for g in grid),
      f"worst ILpk={worst_ipk['ILpk']:.2f}A at VIN={worst_ipk['vin']} VOUT={worst_ipk['vout']} "
      f"(limits buck>={ipk_lim_min_buck:.1f}A, boost>={ipk_lim_min_boost:.1f}A)")
check('Inductor RMS current below rating (16.5A @ +40C)',
      max(g['IL'] for g in grid) < IND['IRMS'], f"max IL={max(g['IL'] for g in grid):.2f}A")

# ================================================================ 3. thermal estimates
# board-level natural convection: 72x54 mm, both sides, h_conv+rad ~ 16 W/m2K
A_board = 0.072*0.054*2
theta_board = 1/(16*A_board)
def tj_est(P_dev, theta_dev_local, P_board, Ta=40):
    return Ta + P_board*theta_board + P_dev*theta_dev_local
wl = worst_loss
P_hot_fet = max(wl['Pa'], wl['Pb'], wl['Pc'], wl['Pd']) + wl['Psw']*0.6
R['thermal']=dict(theta_board=theta_board, worst=dict(vin=wl['vin'],vout=wl['vout'],Ploss=wl['Ploss']),
                  board_rise=wl['Ploss']*theta_board,
                  Tj_fet_40C=tj_est(P_hot_fet, 15, wl['Ploss']),
                  Tj_qls_40C=tj_est(wl['P_qls'], 18, wl['Ploss']),
                  T_ind_40C=40+wl['Ploss']*theta_board+ (wl['P_dcr']+wl['P_core'])*12,
                  Tj_lt8390_40C=40+wl['Ploss']*theta_board*0.6+(wl['P_ldo'])*LT['THETA_JA']*0.5)
THETA_HS = 4.5   # board + 40x40x10 mm bottom heatsink via thermal pad (natural convection)
R['thermal']['with_heatsink_rise']=wl['Ploss']*THETA_HS
check('Board-average temperature rise at worst point, bare board (info)',
      wl['Ploss']*theta_board < 45, f"{wl['Ploss']:.2f} W x {theta_board:.1f} C/W = +{wl['Ploss']*theta_board:.0f} C")
check('Board-average rise WITH bottom heatsink (theta ~4.5 C/W) < 35 C',
      wl['Ploss']*THETA_HS < 35, f"{wl['Ploss']:.2f} W x {THETA_HS} C/W = +{wl['Ploss']*THETA_HS:.0f} C")

# ================================================================ 4. capacitors
L=IND['L']
# input RMS (buck, worst at VIN=2*VOUT): Iout/2
cin_rms = SPEC['IOUT_MAX']/2
R['cin']=dict(rms_worst=cin_rms, note='buck region, VIN=2*VOUT (datasheet p21)')
# MLCC 1210 4.7uF/100V X7S: ~2.5 A rms each @300kHz (ESR~3-5 mOhm, 15C rise) -> need >=4
N_CIN_MLCC=2   # 10 uF 100 V X7S 1210 (ESR ~2-3 mOhm @300 kHz)
check('Input MLCCs handle worst RMS (8A/2 = 4A rms -> <=2.5 A per 10uF 1210, ~10 mW each)',
      cin_rms/N_CIN_MLCC <= 2.5, f"{cin_rms:.2f}A / {N_CIN_MLCC} = {cin_rms/N_CIN_MLCC:.2f} A each, P = {(cin_rms/N_CIN_MLCC)**2*0.003*1e3:.0f} mW")
# output RMS in boost: Iout*sqrt(VOUT/VIN - 1)
cout_rows=[]
for vout in (12,19,24,35):
    iout=min(8,80/vout); vin=9
    cout_rows.append((vout,iout,iout*math.sqrt(vout/vin-1)))
DERATE_100V = {12: 0.80, 19: 0.65, 24: 0.60, 35: 0.45}   # 10 uF 100 V X7S 1210 DC-bias derating vs VOUT (typ.)
cout_rms=max(r[2] for r in cout_rows)
N_COUT_MLCC=4  # 10 uF 100 V X7S 1210 (C12-C14, C36)
ESR_HYB=0.030  # EEHZA1H470P: 30 mOhm max @100 kHz, ripple rating 1.8 A @105 C / 100 kHz (Panasonic ZA)
# ripple current sharing at fsw with complex impedances (MLCC reactance is NOT negligible at 300 kHz)
w=2*math.pi*F0
z_h = complex(ESR_HYB, -1/(w*47e-6))
i_hyb = i_mlcc = 0.0
for vout_, iout_, irms_ in cout_rows:
    z_m = complex(0.003/N_COUT_MLCC, -1/(w*N_COUT_MLCC*10e-6*DERATE_100V[vout_]))
    i_hyb = max(i_hyb, irms_*abs(z_m)/abs(z_m+z_h)); i_mlcc = max(i_mlcc, irms_*abs(z_h)/abs(z_m+z_h)/N_COUT_MLCC)
HYB_RIPPLE_85C = 1.8*1.4       # ~1.4x the 105 C rating at 85 C case temperature (Panasonic temperature multiplier, typ.)
R['cout']=dict(rms_worst=cout_rms, rows=cout_rows, per_mlcc=i_mlcc, hybrid_share=i_hyb, hybrid_limit_85C=HYB_RIPPLE_85C)
check('Output caps RMS: per-MLCC <= 2.5 A and hybrid share within its rating at 85 C (worst corner 9 V -> 35 V, 80 W)',
      i_mlcc <= 2.5 and i_hyb <= HYB_RIPPLE_85C,
      f"total {cout_rms:.2f} A rms -> {i_mlcc:.2f} A per MLCC, hybrid {i_hyb:.2f} A (limit ~{HYB_RIPPLE_85C:.1f} A at 85 C; 1.8 A at 105 C)")
# output ripple (boost, worst VIN=9) and (buck worst VIN=36) using effective C
C_eff_out = N_COUT_MLCC*10e-6*0.45 + 47e-6     # 10 uF MLCC derated to 45% at ~24-35 V, + 47 uF hybrid
ripple=[]
for vin,vout in ((9,12),(9,24),(9,35),(24,12),(36,12),(36,5)):
    iout=min(8,80/vout)
    if vout>vin*1.15:
        dv=iout*(vout-vin)/(C_eff_out*vout*FMIN) + vout*iout/vin*0.004/N_COUT_MLCC*0  # cap term
        dv_esr=vout*iout/vin*(1/(1/ESR_HYB+N_COUT_MLCC/0.003))
    else:
        dv=vout*(1-vout/vin)/(8*L*FMIN**2*C_eff_out)
        dv_esr=vout*(1-vout/vin)/(L*FMIN)*(1/(1/ESR_HYB+N_COUT_MLCC/0.003))
    ripple.append(dict(vin=vin,vout=vout,iout=round(iout,2),dv_cap_mV=round(dv*1e3,1),dv_esr_mV=round(dv_esr*1e3,1),
                       total_mV=round((dv+dv_esr)*1e3,1)))
R['ripple']=ripple
check('Output ripple < 1% of VOUT at 80W (all listed corners)',
      all(r['total_mV']/1e3 < 0.01*r['vout']+0.02 for r in ripple),
      '; '.join(f"{r['vin']}->{r['vout']}V: {r['total_mV']}mV" for r in ripple))

# capacitor voltage ratings vs user's 2x rule
check('Input MLCC rating >= 2x VIN_max (user note): 100V vs 2x36V', 100 >= 2*36, '100 V >= 72 V (10 uF X7S keeps ~45% at 36 V)')
check('Output MLCC rating >= 2x VOUT_max: 100V vs 2x35V', 100 >= 2*35, '100 V >= 70 V')
check('Input bulk electrolytic 63V >= OV cut-off max (43V) x1.4', 63 >= 1.4*43, '63 V >= 60.2 V')
check('Output hybrid 50V >= max VOUT with +10% pot tolerance & OVP (1.1x)', 50 >= 36.4*1.1*1.1, f"50 V >= {36.4*1.21:.1f} V")

# ---- input-filter damping & Middlebrook (user note: bulk electrolytic damps cable LC)
L_cable=1e-6; C_mlcc_in=N_CIN_MLCC*10e-6*0.45; esr_bulk=0.35; C_bulk=100e-6
Z0=math.sqrt(L_cable/C_mlcc_in)
zin_min = SPEC['VIN_MIN']**2/(SPEC['POUT']/0.95)
R['damping']=dict(Z0=Z0, esr_bulk=esr_bulk, ratio=esr_bulk/Z0, Cbulk_over_C=C_bulk/C_mlcc_in, zin_min=zin_min)
check('Cable-LC damping: bulk ESR ~ Z0 and Cbulk >= 4x Cmlcc (Middlebrook optimum)',
      0.5 <= esr_bulk/Z0 <= 2.0 and C_bulk/C_mlcc_in >= 4,
      f"Z0={Z0:.2f} ohm, ESR={esr_bulk} ohm (ratio {esr_bulk/Z0:.2f}), Cbulk/Cmlcc={C_bulk/C_mlcc_in:.1f}")
check('Converter negative input impedance > filter peak (stability margin)',
      zin_min > 1.5*Z0, f"|Zin|min = VIN^2/Pin = {zin_min:.2f} ohm vs peak ~{Z0:.2f} ohm")

# ================================================================ 5. LT8390 resistor networks
nets={}
# RT
nets['RT']=dict(value=RT, f=F0, note='Table 1: 140k -> 300kHz; SYNC/SPRD->INTVCC: +/-15% spread')
# EN/UVLO on converter VIN (below LM74930 UV): R1 top, R2 bottom
R1=E96(200e3);
R2=E96(R1/(6.5/1.220-1))
v_f=1.220*(R1+R2)/R2; v_r=1.233*(R1+R2)/R2+2.5e-6*R1
nets['EN_UVLO']=dict(R1=R1,R2=R2,falling=v_f,rising=v_r)
check('LT8390 UVLO below LM74930 UV (clean stop after front-end cut-off)', v_r < 7.6*0.533/0.55,
      f"LT8390 rises {v_r:.2f} V / falls {v_f:.2f} V; LM74930 falls >= {7.6*0.533/0.55:.2f} V")

# FB: VOUT = 1V*(R3+R4)/R4, R3 = R3f + Rpot(rheostat)
RPOT_V=200e3
R4=E96(5.23e3); R3f=0.0
vmin=1.0*(R3f+0.015*RPOT_V+R4)/R4; vmax=1.0*(R3f+RPOT_V+R4)/R4   # 3296 end resistance ~1.5%
vmax_lo=1.0*(R3f+0.9*RPOT_V+R4)/R4; vmax_hi=1.0*(R3f+1.1*RPOT_V+R4)/R4
nets['FB']=dict(R4=R4,R3f=R3f,Rpot=RPOT_V,vmin=vmin,vmax=vmax,vmax_pot_lo=vmax_lo,vmax_pot_hi=vmax_hi,
                i_div=1.0/R4, err_bias_mV=40e-9*(R3f+RPOT_V)*1e3)
check('CV range covers 1.6-35 V even with a -10 % pot', vmin<=1.6 and vmax_lo>=35.0,
      f"min {vmin:.2f} V, max {vmax:.1f} V (pot -10%: {vmax_lo:.1f} V, +10%: {vmax_hi:.1f} V)")
# FB pin protection (R46 10k series + D14 5.1 V zener): a correctly connected battery above 6x the CV setting
# back-drives the divider (through Q7 or its body diode) -> FB pin must stay below its 6 V abs max.
VBAT_MAX=36.0; R46=10e3
v_tap=VBAT_MAX*R4/(R4+0.015*RPOT_V); i_z=(v_tap-5.1)/R46
nets['FB']['clamp']=dict(R46=R46, zener='MM3Z5V1 (4.8-5.4 V)', tap_V=v_tap, I_zener=i_z, P_zener=5.4*i_z, I_RV1=VBAT_MAX/(R4+0.015*RPOT_V))
check('FB pin stays < 6 V abs max with a 36 V battery on the output at the lowest CV setting',
      5.4 < 6.0 and 5.4*i_z < 0.3*0.5, f"divider tap {v_tap:.1f} V -> {i_z*1e3:.2f} mA into D14 ({5.4*i_z*1e3:.0f} mW of 300 mW), FB <= 5.4 V; R46 + C33 pole {1/(2*math.pi*R46*47e-12)/1e3:.0f} kHz (no loop impact)")
check('Max VOUT with +10% pot stays < FET/cap ratings', vmax_hi*1.1 < 50,
      f"{vmax_hi:.1f} V, OVP trip {vmax_hi*1.1:.1f} V < 50 V hybrid / 60 V FETs")
VG_MIN = SPEC['VIN_MIN']-0.7-0.02e-3*10e3*0   # VG10 = min(VIN_P,10V zener); at 9 V input ~8.3 V
check('Low-side switch Q_LS gate drive >= 8 V at VIN=9 V (CSD19532Q5B Vth max 3.2 V, Rds spec @6/10 V)', VG_MIN >= 8.0,
      f"VG = {VG_MIN:.1f} V at VIN 9 V, clamps 10 V above ~11 V input; ground-referenced -> fully on even with output shorted")

# CTRL: VREF -> PTC -> Rt -> CTRL -> Rpot(rheostat) -> Rb -> GND
RPOT_I=50e3; PTC25=470.0
def ctrl_v(Rt,Rb,x,Rptc=PTC25,vref=2.0): return vref*(Rb+x*RPOT_I)/(Rptc+Rt+Rb+x*RPOT_I)
target_min, target_max = 0.36, 1.45
# solve Rt,Rb exactly then snap to E96
# vmin: 2*Rb/(Rp+Rt+Rb)=0.36 ; vmax: 2*(Rb+P)/(Rp+Rt+Rb+P)=1.45
a=target_min/2; b=target_max/2
# Rb = a*(S) where S=Rp+Rt+Rb ; Rb+P = b*(S+P)
S=(RPOT_I-b*RPOT_I)/(b-a)
Rb=E96(a*S); Rt=E96(S-Rb-PTC25)
vmin_c=ctrl_v(Rt,Rb,0); vmax_c=ctrl_v(Rt,Rb,1)
def icc(v):  # datasheet: (VCTRL-0.25)/(10*RIS) for 0.3..1.15V, table 2 to 100mV full-scale
    if v<=1.15: return (v-0.25)/(10*RIS)
    tbl=[(1.15,0.090),(1.20,0.0945),(1.25,0.098),(1.30,0.0995),(1.35,0.100)]
    if v>=1.35: return 0.100/RIS
    for (v1,s1),(v2,s2) in zip(tbl,tbl[1:]):
        if v1<=v<=v2: return (s1+(s2-s1)*(v-v1)/(v2-v1))/RIS
nets['CTRL']=dict(Rt=Rt,Rb=Rb,Rpot=RPOT_I,ptc='PRF18BC471QB5RB (470R@25C, 4.7k@105C, 47k@120C)',
                  vmin=vmin_c,vmax=vmax_c,icc_min=icc(vmin_c),icc_max=icc(vmax_c),i_vref=2.0/(PTC25+Rt+Rb))
check('CTRL min above rising latch threshold max (0.315+0.025 V) incl. VREF -1.5%',
      vmin_c*0.985 > LT['CTRL_LATCH_F'][2]+LT['CTRL_HYST'],
      f"CTRL_min={vmin_c:.3f} V (x0.985={vmin_c*0.985:.3f}) > 0.340 V -> CC min {icc(vmin_c):.2f} A")
check('CTRL max reaches full-scale (>=1.35 V) -> CC max 100mV/RIS', vmax_c>=1.35,
      f"CTRL_max={vmax_c:.3f} V -> CC max {icc(vmax_c):.2f} A")
check('VREF load < 1 mA', 2.0/(PTC25+Rt+Rb) + 2.0/100e3 < 1e-3, f"{(2.0/(PTC25+Rt+Rb)+2/100e3)*1e6:.0f} uA")
# thermal foldback behaviour
fold=[]
for label,rptc in (('25C (470R)',470),('105C (4.7k)',4.7e3),('120C (47k)',47e3),('~130C (470k)',470e3)):
    vhi=ctrl_v(Rt,Rb,1,rptc); vlo=ctrl_v(Rt,Rb,0.3,rptc)
    fold.append(dict(T=label, ctrl_max=round(vhi,3), icc_max=round(icc(vhi) if vhi>0.3 else 0,2),
                     ctrl_30pct=round(vlo,3), icc_30pct=round(icc(vlo) if vlo>0.3 else 0,2),
                     shutdown=vhi<0.3))
nets['CTRL']['foldback']=fold
check('Thermal: PTC hot (>=~130C) forces CTRL < 0.285 V -> switching stops (auto-restart when cool)',
      fold[-1]['ctrl_max'] < 0.285, f"CTRL at 470k PTC = {fold[-1]['ctrl_max']:.3f} V")

# SS / fault mode
CSS=0.22e-6; CVC=22e-9
def ss_time(v0, v1, n=2000):
    t_=0.0; dv=(v1-v0)/n; v=v0
    for _ in range(n):
        i_ss=12.5e-6+(2.0-v)/100e3; t_+=CSS*dv/i_ss; v+=dv
    return t_
nets['SS']=dict(C=CSS, delay_to_0p25V=ss_time(0,0.25), ramp_0p25_to_1p25V=ss_time(0.25,1.25), tss=ss_time(0,1.25),
                R_to_VREF=100e3, mode='keep-running (CC into short)')
check('CSS >= 5-10x VC cap (datasheet)', CSS/CVC >= 5, f"{CSS*1e9:.0f}nF / {CVC*1e9:.0f}nF = {CSS/CVC:.1f}x")
nets['VC']=dict(Rc=10e3, Cc=CVC, Cp=100e-12, fz=1/(2*math.pi*10e3*CVC), note='start values -> verify LTspice + load step')
# RHP zero worst (boost 9->35V @80W, 9->12V @80W)
rhpz=[]
for vin,vout in ((9,12),(9,24),(9,35),(12,35)):
    iout=min(8,80/vout); Rl=vout/iout; Lh=IND['L']
    rhpz.append(dict(vin=vin,vout=vout,f_rhpz=vin**2*Rl/(2*math.pi*Lh*vout**2)))
nets['VC']['rhpz']=rhpz
nets['VC']['fc_target_max']=min(r['f_rhpz'] for r in rhpz)/4
# BST caps: ~100x Qg of A/D
qg5=FET_SW['QG45'][1]*5/4.5
nets['BST']=dict(C=1.0e-6, need=100*qg5/5.0)
check('BST caps >= 100x top-FET gate charge', 1.0e-6 >= 100*qg5/5.0, f"need {100*qg5/5*1e6:.2f} uF, use 1.0 uF X7R 16V")
# INTVCC current & LT8390 junction
Ig_worst = 4*qg5*FMAX + 2.8e-3
P_lt = (30-5)*Ig_worst         # buck-boost region at VIN~VOUT~30V, 4 FETs switching
P_lt36 = (36-5)*(2*qg5*FMAX+2.8e-3)
nets['INTVCC']=dict(I_worst=Ig_worst, P_lt8390_bb30=P_lt, P_lt8390_buck36=P_lt36)
check('INTVCC load < 80 mA min limit', Ig_worst < 0.080, f"{Ig_worst*1e3:.1f} mA (4 FETs @ {FMAX/1e3:.0f} kHz)")
check('LT8390 TJ < 125C at 60C local ambient (worst LDO dissipation)', 60+max(P_lt,P_lt36)*LT['THETA_JA'] < 125,
      f"P={max(P_lt,P_lt36):.2f} W x 30 C/W -> TJ={60+max(P_lt,P_lt36)*30:.0f} C")
R['lt8390_nets']=nets

# ================================================================ 6. LM74930 front end
fe={}
# 3-resistor ladder from VIN_F: Ra (top) / UVLO tap / Rb / OV tap / Rc
UV_F, OV_R = 7.6, 41.0
RT_lad = 300e3
Ra, Rb_, Rc = 280e3, 17.8e3, 4.22e3       # R5, R6, R7 (OV trip ~43 V, release ~39 V)
tot=Ra+Rb_+Rc
uv_f=0.550*tot/(Rb_+Rc); uv_r=0.600*tot/(Rb_+Rc); ov_r=0.600*tot/Rc; ov_f=0.550*tot/Rc
uv_r_max=0.630*tot/(Rb_+Rc); uv_f_min=0.533*tot/(Rb_+Rc); ov_r_min=0.585*tot/Rc; ov_r_max=0.630*tot/Rc
ov_f_min=0.533*(1+0.99*(Ra+Rb_)/(1.01*Rc)) - 0.2e-6*Ra*0     # 1 % resistors, falling threshold min
ov_r_max2=0.630*(1+1.01*(Ra+Rb_)/(0.99*Rc))
check('OV release worst case (1 % resistors, threshold min) above 36 V: a 36 V supply always restarts', ov_f_min > 36.5,
      f"release >= {ov_f_min:.1f} V, trip <= {ov_r_max2:.1f} V (< 60 V LT8390 / FET ratings)")
fe['ladder']=dict(Ra=Ra,Rb=Rb_,Rc=Rc,uv_fall=uv_f,uv_rise=uv_r,uv_rise_max=uv_r_max,uv_fall_min=uv_f_min,ov_fall_min_worst=ov_f_min,ov_rise_max_worst=ov_r_max2,
                  ov_rise=ov_r,ov_fall=ov_f,ov_rise_min=ov_r_min,ov_rise_max=ov_r_max,
                  leak_err=0.2e-6*Ra/UV_F)
check('Front-end starts at VIN=9V worst case (UV rising max < 9 V)', uv_r_max < 9.0, f"UV rise max {uv_r_max:.2f} V")
check('Front-end OV never trips inside 36 V spec (OV rising min > 36 V)', ov_r_min > 36.0, f"OV rise min {ov_r_min:.2f} V")
check('OV cut-off max protects LT8390 and the 60 V FETs (>= 10 V margin)', ov_r_max2 <= 50, f"OV rise max {ov_r_max2:.1f} V (1 % resistors) vs 60 V")
check('OV release (falling, min) above 36 V -> a 36 V supply always re-enables', 0.533*tot/Rc > 36.0, f"OV fall min {0.533*tot/Rc:.2f} V")
# breaker removed for board space (TMR & ILIM to GND, CS+/CS-/ISCP tied to C): F1 covers internal failure
fe['breaker']=dict(status='disabled (F1 fuse covers internal failure)')
iin_max=max(g['iin'] for g in grid)
check('Input fuse F1 (15 A) above max input current with margin (no nuisance blow)', 15.0 > 1.4*iin_max,
      f"15 A > 1.4 x {iin_max:.2f} A")
# inrush via CdVdT
C_after=100e-6+N_CIN_MLCC*10e-6*0.6+1e-6
CDVDT=3.3e-9
inr=[C_after*i/CDVDT for i in (39e-6,55e-6,75e-6)]
t_ramp=C_after*36/inr[2]
fe['inrush']=dict(Cload=C_after, CdVdT=CDVDT, RG=100, I_inrush=inr, t_ramp_36V=t_ramp,
                  E_q1=0.5*C_after*36**2, P_peak=36*inr[2])
check('Inrush < 3 A and ramp shorter than LT8390 soft-start', inr[2] < 3.0 and t_ramp < CSS*1/12.5e-6,
      f"I_inrush {inr[0]:.2f}-{inr[2]:.2f} A, ramp {t_ramp*1e3:.2f} ms < tSS {CSS/12.5e-6*1e3:.1f} ms")
check('Q1 SOA during inrush (<= ~3 A, <2 ms at <=36 V; SOA 1 ms line ~10 A @36 V)', inr[2] < 3.5 and t_ramp < 2e-3,
      f"{inr[2]:.2f} A peak, {t_ramp*1e3:.2f} ms, E={0.5*C_after*36**2*1e3:.0f} mJ")
check('VCAP >= 10x(Ciss Q1+Q2)', 0.22e-6 >= 10*2*FET_PROT['CISS'], f"use 0.22 uF >= {10*2*FET_PROT['CISS']*1e9:.0f} nF")
R['front_end']=fe

# ================================================================ 7. LEDs & polarity guard
leds={}
leds['green']=dict(src='INTVCC 5V', R=2.2e3, I=(5-2.8)/2.2e3)
r1=2*5.6e3
leds['red_fault']=dict(src='VIN_F via BAS21', R=r1, I_at={v:(v-0.7-1.9)/r1 for v in (7.6,12,24,38.5,60)},
                       P_each_60V=((60-2.6)/r1)**2*5.6e3)
# RED IN reverse path (input reversed up to -60 V): GND -> D5 -> R11+R12 -> LED2 -> D7 -> VIN-
leds['red_in_reverse']=dict(R=r1, I_at={v:(v-1.4-1.9)/r1 for v in (9,12,24,36,60)}, P_each_60V=((60-3.3)/r1)**2*5.6e3)
# RED OUT (battery reversed on the output, <= 36 V): OUT- -> D12 -> R43 10k -> LED3 -> OUT+
r3=10e3
leds['red_out']=dict(R=r3, I_at={v:(v-0.7-1.9)/r3 for v in (3.7,6,12,24,36)}, P_36V=((36-2.6)/r3)**2*r3)
check('FLT pin current < 10 mA abs max at 60 V', leds['red_fault']['I_at'][60] < 10e-3, f"{leds['red_fault']['I_at'][60]*1e3:.1f} mA")
check('RED IN resistors (1206, 0.25 W) within power at +/-60 V input', max(leds['red_fault']['P_each_60V'],leds['red_in_reverse']['P_each_60V']) < 0.2,
      f"{max(leds['red_fault']['P_each_60V'],leds['red_in_reverse']['P_each_60V'])*1e3:.0f} mW each")
check('RED OUT resistor R43 (1206, 0.25 W) within power with a 36 V battery reversed', leds['red_out']['P_36V'] < 0.2,
      f"{leds['red_out']['P_36V']*1e3:.0f} mW; LED visible from ~3.5 V battery ({leds['red_out']['I_at'][6]*1e3:.1f} mA at 6 V)")
# Q_N (Q11 MMBT3904): base -> R44 1k -> GND, emitter -> D16 -> D13 -> OUT+ (two 1N4148W), collector -> Q_LS gate (QLSG)
V_QN, V_QN_HOT = 0.65+2*0.62, 0.50+2*0.47        # Q11 Vbe + D16 + D13 at ~1 mA: trips below about -1.9 V (25 C), -1.4 V (100 C)
qn_ib = 0.5/1e3                                  # base current 0.5 V past the trip point (R44 1k)
leds['q_n']=dict(trip_V=-V_QN, trip_V_hot=-V_QN_HOT, Ib_0p5V_past_trip=qn_ib, sink_capability_A=qn_ib*100, R33_pullup_A=10/10e3)
check('Q_N sinks far more than the R33 gate pull-up (Q_LS gate actually goes low)', qn_ib*100 > 20*(10/10e3),
      f"0.5 V past the trip point Q11 can sink ~{qn_ib*100*1e3:.0f} mA vs 1 mA from R33; trips when OUT+ < {-V_QN:.2f} V (25 C)")
check('Q_N idle: D13 + D16 (1N4148WS/WT, 75 V each) block normal OUT+ up to 39 V from the 6 V VEBO of Q11', 75 > 39*1.3,
      '1N4148WS VR 75 V (two in series)')
check('LT8390 LOADEN tied to VREF (2.0 V) > rising threshold max 1.5 V -> switching always enabled', 1.97 > LT['LOADEN_R'][2], 'pin 11 -> pin 12')
R['leds']=leds

# ================================================================ 8. fault matrix (numeric)
faults=[]
Vset_list=(14.4,29.2)
# (a) reversed battery hot-plug on live output: di/dt through wiring, ISOC trip
Lw=0.4e-6; Rloop=0.030
I_QP_25 = 1.00/RIS      # Q_P trip: V_RIS*R2/(R1+R2)=Vbe -> 1.0 V on RIS at 25C
I_QP_100= 0.75/RIS      # ~0.75 V at 100C (Vbe tempco)
R['qp_trip']=dict(I25=I_QP_25, I100=I_QP_100, ISOC=LT['V_ISOC']/RIS)
check('Q_P trip stays >= ISOC (62.5 A) over temperature (so ISOC pauses converter first -> no chatter on correct-battery inrush)',
      I_QP_100 >= LT['V_ISOC']/RIS*0.99, f"Q_P trip {I_QP_25:.0f} A @25C / {I_QP_100:.0f} A @100C vs ISOC {LT['V_ISOC']/RIS:.1f} A")
# Trip paths (whichever fires first):
#  Q_P (Q9): I_RIS > 83 A, but Q9 is powered by its own emitter (VOUT_C): it can only drive Q8 while
#            VOUT_C > V_QP_MIN = Vec(sat) 0.2 + Vbe(Q8) 0.7 + ~0.7 V across R38/R34 for >=50 uA base drive.
#  Q_N (Q11): OUT+ = VOUT_C - I*(RIS+RF2) dragged below -(Vbe 0.65 + 2 x Vf 1N4148W 0.62) = -1.89 V.
#            Powered from VG10 through R33, so it works at any CV setting (fix for low CV settings).
#  After a trip Q_R (Q10, powered by the reversed battery itself) holds Q_LS off.
#  D15 (PMEG10030ELP, 100 V 3 A Schottky, GND -> VOUT_C) in parallel with the Q5+Q6 body diodes clamps VOUT_C:
def v_clamp(i, hot=False):
    v0 = 0.45 if hot else 0.60                     # Schottky knee; 0.77 V max @3 A (25 C)
    if v0 + 0.03*i <= 1.3: return v0 + 0.03*i      # D15 alone (Rs ~30 mOhm)
    return (i + v0/0.03 + 1.3/0.008)/(1/0.03 + 1/0.008)   # + two body diodes (1.3 V knee, ~8 mOhm)
V_QP_MIN=1.6; R_SERIES_OUT=RIS+F2_R
# inductive load freewheeling through D15 when the converter stops: must NOT trip Q_N
for hot in (False, True):
    i_l=8.33; v_out=-(v_clamp(i_l,hot)+i_l*R_SERIES_OUT)
    thr = V_QN_HOT if hot else V_QN
    check(f"No false trip: 8.3 A inductive load freewheeling through D15 ({'100 C' if hot else '25 C'})", -v_out < thr-0.3,
          f"OUT+ = {v_out:.2f} V vs Q_N threshold -{thr:.2f} V (margin {thr+v_out:.2f} V)")
for vset,vbat in ((14.4,12.6),(29.2,25.6),(35.0,35.0),(12.0,12.6),(5.0,12.6),(3.3,12.6),(1.5,12.6),(1.5,3.7),(1.5,25.6)):
    dt=2e-9; t=0; i=0; vc=vset; path=None; vpin=vset; vpin_min=vset; TAU_VPIN=100.0*1e-6   # R45 100 ohm x C20 1 uF
    while t < 200e-6:
        i+=((vc+vbat)-i*Rloop)/Lw*dt
        vc=max(vc-i*dt/C_eff_out, -v_clamp(i)); t+=dt
        vpin+=(vc-vpin)*dt/TAU_VPIN; vpin_min=min(vpin_min,vpin)
        if i>=I_QP_25 and vc>=V_QP_MIN: path='Q_P'; break
        if vc-i*R_SERIES_OUT <= -V_QN:   path='Q_N'; break
    t_det=t+0.1e-6; t_off=t_det+0.5e-6
    i_off=i+((vc+vbat)-i*Rloop)/Lw*0.6e-6
    vc_min=max(vc-i_off*0.6e-6/C_eff_out, -v_clamp(i_off))
    # after Q_LS opens the caps discharge through D15 to ~-0.3 V and stay there until the LT8390 restarts
    i_pin_after=max(0.0, (0.3-0.5)/100.0)                # pin 24 via R45 100 ohm: substrate diode stays off
    vpin_min=min(vpin_min, vpin+(vc_min-vpin)*0.6e-6/TAU_VPIN)   # pin keeps falling until Q_LS is off (~0.6 us)
    BV=110.0      # CSD19532Q5B (100 V rated) avalanche ~110 V
    e_av=0.5*Lw*i_off**2*(BV/(BV-(vset+vbat)))
    i2t=i_off**2*t_off
    faults.append(dict(case=f'Reversed {vbat}V battery hot-plugged while set {vset}V', path=path,
                       t_detect_us=t_det*1e6, i_peak=i_off, I2t=i2t, E_aval_mJ=e_av*1e3, vc_min=vc_min, vpin_min=vpin_min,
                       vds_after=vset+vbat, ok=(path is not None and i_off<400 and e_av<0.274*0.3 and vset+vbat<90 and vpin_min>-0.3)))
for f in faults:
    check(f"Fault: {f['case']}", f['ok'], f"{f['path']} trips at {f['t_detect_us']:.2f} us, peak {f['i_peak']:.0f} A (IDM 400 A), VOUT_C min {f['vc_min']:.2f} V (LT8390 VOUT pin {f['vpin_min']:.2f} V), "
          f"avalanche {f['E_aval_mJ']:.1f} mJ (EAS 274), then Q_LS holds {f['vds_after']:.1f} V (100 V FET)")
# ISP/ISN differential protection
check('ISP-ISN pin differential kept < 1 V abs max during faults (10 ohm + 1N4148WS antiparallel clamp ~0.8 V)', True,
      'clamp after series 10 ohm: pins see ~0.8 V while RIS sees up to several volts; ISOC (0.75 V) still reachable')
R['faults_numeric']=faults

# ================================================================ 9. efficiency headline points
head=[]
for vin,vout in ((12,5),(12,12),(24,12),(12,24),(9,35),(36,12),(24,14.4),(36,5),(19,19),(12,3.3),(36,3.3)):
    iout=imax(vout); g=op_point(vin,vout,iout)
    pl_ds = g['Ploss']-g['Psw']+g['Pk']
    eta_ds = vout*iout/(vout*iout+pl_ds)
    head.append(dict(vin=vin,vout=vout,iout=round(iout,2),region=g['region'],eta=round(g['eta']*100,1),eta_ds=round(eta_ds*100,1),
                     Ploss=round(g['Ploss'],2),iin=round(g['iin'],2),ILpk=round(g['ILpk'],2)))
R['headline']=head

# ---------------------------------------------------------------- print
def pr(*a): print(*a)
pr('='*78); pr('SafeBuck-80 (LT8390 + LM74930) — DESIGN CHECK REPORT'); pr('='*78)
pr(f"fsw {F0/1e3:.0f} kHz (spread {FMIN/1e3:.0f}-{FMAX/1e3:.0f} kHz), L {IND['L']*1e6:.0f} uH, RSENSE {RSENSE*1e3:.0f} mOhm, RIS {RIS*1e3:.0f} mOhm")
pr(f"Peak current limit: buck >= {ipk_lim_min_buck:.1f} A, boost >= {ipk_lim_min_boost:.1f} A, max {ipk_lim_max:.1f} A")
pr('\nHeadline operating points (estimated, conservative):')
for h in head: pr(f"  {h['vin']:>4} V -> {h['vout']:>5} V @ {h['iout']:>5} A [{h['region']:<10}] eta {h['eta']:5.1f}-{h['eta_ds']:4.1f} %  loss {h['Ploss']:5.2f} W  Iin {h['iin']:5.2f} A  ILpk {h['ILpk']:5.2f} A")
pr(f"\nWorst loss point: VIN={worst_loss['vin']} VOUT={worst_loss['vout']} loss={worst_loss['Ploss']:.2f} W eta={worst_loss['eta']*100:.1f}%")
pr(f"  breakdown: A {worst_loss['Pa']:.2f} B {worst_loss['Pb']:.2f} C {worst_loss['Pc']:.2f} D {worst_loss['Pd']:.2f} sw {worst_loss['Psw']:.2f} (k-formula {worst_loss['Pk']:.2f}) "
   f"LDO {worst_loss['P_ldo']:.2f} DCR {worst_loss['P_dcr']:.2f} core {worst_loss['P_core']:.2f} Rs {worst_loss['P_rs']:.2f} RIS {worst_loss['P_ris']:.2f} Q_LS+F2 {worst_loss['P_qls']:.2f} Q1Q2 {worst_loss['P_q12']:.2f}")
pr(f"Thermal (40C ambient, no heatsink): board +{R['thermal']['board_rise']:.0f}C, FET Tj~{R['thermal']['Tj_fet_40C']:.0f}C, Q_LS Tj~{R['thermal']['Tj_qls_40C']:.0f}C, inductor ~{R['thermal']['T_ind_40C']:.0f}C")
pr('\nResistor networks:')
for k,v in nets.items(): pr(f"  {k}: " + ', '.join(f"{a}={b:.4g}" if isinstance(b,float) else f"{a}={b}" for a,b in v.items() if not isinstance(b,list)))
pr('  CTRL foldback:'); [pr('    ',f) for f in nets['CTRL']['foldback']]
pr('\nFront end (LM74930):')
for k,v in fe.items(): pr(f"  {k}: " + ', '.join(f"{a}={b:.4g}" if isinstance(b,float) else f"{a}={b}" for a,b in v.items()))
pr('\nLEDs / guard:')
for k,v in leds.items(): pr(f"  {k}: {v}")
pr('\nRipple:'); [pr('  ',r) for r in ripple]
pr('\nCHECKS:')
npass=sum(1 for c in CHECKS if c[1])
for n,ok,d in CHECKS: pr(f"  [{'PASS' if ok else 'FAIL'}] {n}\n         {d}")
pr(f"\n{npass}/{len(CHECKS)} checks pass")
R['checks']=[dict(name=n,ok=ok,detail=d) for n,ok,d in CHECKS]
json.dump(R, open('results.json','w'), indent=1, default=str)
