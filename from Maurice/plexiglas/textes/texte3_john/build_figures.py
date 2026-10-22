"""Regenerate English figures from the accompanying CSV files (no hardware)."""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
HERE=Path(__file__).resolve().parent
C=299792458.
def read(name):
    v=np.loadtxt(HERE/'data'/f'{name}.csv',delimiter=',',skiprows=1)
    return v[:,0],v[:,1]+1j*v[:,2]
def profile(f,s,signed=False):
    n=len(f); nf=16*n
    a=np.abs(np.fft.ifft(s*np.hanning(n),n=nf))*16
    if signed:
        d=np.fft.fftshift(np.fft.fftfreq(nf,d=f[1]-f[0]))*C/2*100
        return d,np.fft.fftshift(a)
    d=np.arange(nf)/(nf*(f[1]-f[0]))*C/2*100
    return d[:nf//2],a[:nf//2]
def db(a):return 20*np.log10(np.maximum(abs(a),1e-15))
f,bg=read('background')
fig,axs=plt.subplots(2,1,figsize=(9,7),layout='constrained')
rows=[]
for k,real in enumerate((50,60,70)):
    ft,s=read(f'plate_{real}cm');np.testing.assert_array_equal(f,ft)
    d,a=profile(f,s-bg)
    peaks=find_peaks(a)[0];best=sorted(sorted(peaks,key=lambda i:a[i],reverse=True)[:2],key=lambda i:d[i])
    rows.append([real,d[best[0]],d[best[1]],db(a[best[0]]),db(a[best[1]])])
    for ax in axs:ax.plot(d,db(a),label=f'Plate at approximately {real} cm',color=f'C{k}')
    axs[0].plot(d[best],db(a[best]),'o',color=f'C{k}')
for ax in axs:
    ax.set(xlabel='Apparent air-equivalent distance from SOL plane (cm)',ylabel='IFFT magnitude (dB re 1)',ylim=(-100,-50));ax.grid(alpha=.3);ax.legend(fontsize=9)
axs[0].set(xlim=(45,115),title='Target region: the two largest local maxima are marked')
axs[1].set(xlim=(0,d[-1]),title='Full positive-distance profile')
fig.savefig(HERE/'figures/profiles.pdf');plt.close(fig)
np.savetxt(HERE/'data/peak_summary.csv',rows,delimiter=',',header='physical_distance_cm,near_peak_cm,far_peak_cm,near_level_db,far_level_db',comments='')
fig,axs=plt.subplots(2,1,figsize=(9,6),layout='constrained')
axs[0].plot(f/1e9,db(bg),label='Background')
for real in (50,60,70):
    _,s=read(f'plate_{real}cm');axs[0].plot(f/1e9,db(s),label=f'Plate {real} cm');axs[1].plot(f/1e9,db(s-bg),label=f'Plate {real} cm minus background')
for ax in axs:ax.set(xlabel='Frequency (GHz)',ylabel='Magnitude (dB re 1)');ax.grid(alpha=.3);ax.legend(fontsize=9)
fig.savefig(HERE/'figures/spectra.pdf');plt.close(fig)
f,s=read('independent_short');d,a=profile(f,s,True)
fig,axs=plt.subplots(2,1,figsize=(9,5.8),layout='constrained')
axs[0].plot(f/1e9,db(s));axs[0].set(xlabel='Frequency (GHz)',ylabel='Corrected SHORT magnitude (dB)')
axs[1].plot(d,db(a));axs[1].axvline(0,color='gray',ls='--');axs[1].set(xlim=(-25,35),ylim=(-90,0),xlabel='Signed air-equivalent distance (cm)',ylabel='IFFT magnitude (dB re 1)')
for ax in axs:ax.grid(alpha=.3)
fig.savefig(HERE/'figures/short.pdf');plt.close(fig)
print('Peak table:', rows)
print('Independent SHORT peak (cm):',d[np.argmax(a)])

# Match the middle and bottom panels of phase_echo_bleue_50_60_70cm.png.
f,bg=read('background')
fig,axs=plt.subplots(2,1,figsize=(9,7),layout='constrained')
rows=[]
for k,real in enumerate((50,60,70)):
    _,s=read(f'plate_{real}cm')
    h=(s-bg)*np.exp(4j*np.pi*f*(real/100)/C)
    phase=np.unwrap(np.angle(h))
    weights=abs(h)**2;weights/=weights.max()
    x=f/1e9;centre=np.average(x,weights=weights)
    intercept,slope=np.polynomial.polynomial.polyfit(x-centre,phase,1,w=np.sqrt(weights))
    fit=intercept+slope*(x-centre)
    tau=-slope/(2*np.pi);offset=C*tau*1e-9/2*100
    axs[0].plot(x,np.degrees(phase),color=f'C{k}',label=f'Plate at {real} cm')
    axs[0].plot(x,np.degrees(fit),'--',color=f'C{k}',alpha=.7,label=f'Weighted slope: equivalent offset {offset:.1f} cm')
    axs[1].plot(x,np.degrees(phase-fit),color=f'C{k}',label=f'Plate at {real} cm')
    rows.append([real,tau,offset])
    np.savetxt(HERE/'data'/f'echo_phase_{real}cm.csv',np.column_stack((f,phase,fit,phase-fit,weights)),delimiter=',',header='frequency_hz,unwrapped_corrected_phase_rad,fit_rad,deviation_rad,weight',comments='')
axs[0].set(title='Phase after removing the geometric round-trip path',ylabel='Unwrapped phase (degrees)')
axs[1].set(title='Deviation from a constant-delay response',ylabel='Deviation from fitted line (degrees)')
for ax in axs:ax.set(xlabel='Frequency (GHz)');ax.grid(alpha=.3);ax.legend(fontsize=8)
fig.savefig(HERE/'figures/echo_phase.pdf');plt.close(fig)
np.savetxt(HERE/'data/echo_phase_slopes.csv',rows,delimiter=',',header='distance_cm,residual_delay_ns,equivalent_offset_cm',comments='')
print('Echo phase fits:',rows)
