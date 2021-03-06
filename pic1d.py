#!/bin/bash python


#(Currently includes the wall sink, but not neutrals, etc.)

import numpy as np
import time
import matplotlib.pyplot as plt;plt.ion()
from scipy.integrate import odeint
from scipy.interpolate import LinearNDInterpolator

##constants of the simulation
mass = 9.11e-31 #electron mass
charge = 1.609e-19
ne = 1e19 #electron density (const along SOL flux tube)
Te = 39 #90 #electron temperature (const along SOL flux tube)
potSheath = 3.*Te
Np =int(1.0e6) #number of markers
Nsubcycle = 100
Ntimes = 5
sml_dt = 0.002
sml_initial_deltaf_noise = 1e-15
sml_ev2j = charge
sml_j2ev = 1./charge
file_grid = 'grid.npz'
file_neutrals = 'neutrals.npz'
t = 0


def interpolate_fieldLineFollow(Lstart,phiEnd,Binterp):

    #define RHS of ODE system of equations, dy/dt = f(y,t)
    def f(L,phi,Binterp):
        R=L[0]
        Z=L[1]
        B=Binterp(R,Z)
        BR=B[0]
        BZ=B[1]
        Bphi=B[2]
        #model equations
        f0 = R*BR/Bphi
        f1 = R*BZ/Bphi
        #f2 = 1.
        return [f0,f1]#,f2]

    #create an array of phi coordinates for which the particle position
    #will be calculated, in between the initial and end phi poisitions
    Npts = 100
    phi = np.linspace(Lstart[2],phiEnd,Npts)
    dphi = phi[1]-phi[0]

    soln = odeint(f,Lstart[0:2],phi,args=(Binterp,))
    Lout = np.hstack((soln,phi[:,np.newaxis]))
    return Lout

def create_1d_grid():
    #do field-line interpolation to get parallel distance between grid points
    f = np.load(file_grid)
    RZ = f['RZ']
    wall_nodes = f['wall_nodes']
    Bgrid = f['Bgrid']

    Binterp = LinearNDInterpolator(RZ, Bgrid, fill_value = np.inf)
    ind = wall_nodes[2]
    #inds = range(wall_nodes[2],wall_nodes[2]+180)
    inds = range(wall_nodes[2],wall_nodes[3]+1)
    Lstart = np.array([RZ[ind,0],RZ[ind,1],0.])
    phiEnd = -25*np.pi
    Lout = interpolate_fieldLineFollow(Lstart,phiEnd,Binterp)
    LparallelOut = np.hstack((0.,np.cumsum(np.sqrt(np.diff(Lout[:,0]*np.cos(-Lout[:,2]))**2. + \
                            np.diff(Lout[:,0]*np.sin(-Lout[:,2]))**2. + \
    
                        np.diff(Lout[:,1])**2. ) )))
    print(LparallelOut)
    #beforeMid = np.where(Lout[:,1]>0.)[0][0]
    lastind = np.where(np.isnan(LparallelOut))[0][0]
    #x = np.interp(RZ[inds,1],Lout[0:lastind,1],LparallelOut[0:lastind])
    Ltheta = np.cumsum(np.sqrt(np.diff(RZ[inds,0])**2 + np.diff(RZ[inds,1])**2))
    Ltheta = np.hstack((0.,Ltheta))
    Lthetaout = np.cumsum(np.sqrt(np.diff(Lout[:,0])**2 + np.diff(Lout[:,1])**2))
    Lthetaout = np.hstack((0.,Lthetaout))
    x = np.interp(Ltheta, Lthetaout[0:lastind], LparallelOut[0:lastind])
    #plt.figure()
    #plt.plot(Lout[:,0],Lout[:,1], '.')
    #plt.plot(RZ[wall_nodes, 0],RZ[wall_nodes, 1], '.')
    print(Ltheta)
    #plt.plot(Lthetaout,LparallelOut)
    return x

def load_markers(x,mass,ne,Te,Np,marker_den):

    ##first, load particle position uniformly in 1d
    xp = np.random.rand(int(Np))*(x[-1]-x[0]) + x[0]

    ##second, load particle velocity using XGC algorithm for inverse sampling
    temp = Te*sml_ev2j
    vth = np.sqrt(temp/mass)

    #marker params, in XGC with sml_ prefix
    marker_decay_start = 3.
    marker_cutoff = 5.
    marker_width = 1.
    va = marker_decay_start*vth
    vc = marker_cutoff*vth
    vwidth = marker_width*vth

    C = 1./(va + vwidth*(1-np.exp(-(vc-va)/vwidth)))
    A = np.random.rand(Np)

    indslt = np.where(A < C*va)[0]
    indsge = np.where(A >= C*va)[0]

    #v = np.empty((Np,))
    v = np.zeros((Np,))
    #g = np.empty((Np,))
    g = np.zeros((Np,))

    v[indslt] = A[indslt]/C
    v[indsge] = va - vwidth*np.log(1.+(va-A[indsge]/C)/vwidth)
    
    g[indslt] = C
    g[indsge] = C*np.exp(-(v[indsge]-va)/vwidth)

    #set velocity forward and backwards (vparallel)
    vp = v*np.sign(np.random.rand(v.size)-0.5)

    maxwell_norm=np.sqrt(mass/(2.*np.pi*temp))
    w0_adjust = maxwell_norm*np.exp(-0.5*mass*vp*vp/temp) / (g*0.5)   #actual g is half due to -v and v direction

    w0 = ne/marker_den*w0_adjust
    #f0 = ne*maxwell_norm*np.exp(-0.5*(vp/vth)**2.)
    f0 = ne/Te*np.exp(-0.5*(vp/vth)**2.)
    w1 = sml_initial_deltaf_noise*2.*(np.random.rand(Np)-0.5)
    w2 = sml_initial_deltaf_noise*2.*(np.random.rand(Np)-0.5)
    #w2 = w1.copy() #XGC uses same w1 and w2 initial. Can cause issues I think
    return xp,vp,w0,f0,w1,w2

def load_neutrals(file_neutrals):
    f = np.load(file_neutrals)
    return f['n_n']

def get_f0(xp,vp):
    temp = Te*sml_ev2j
    vth = np.sqrt(temp/mass)
    f0a = ne/Te*np.exp(-0.5*(vp/vth)**2.)
    #this is the old way that matches load. Need to change load to match above commented version
    #f0a = ne*np.sqrt(1./(2.*np.pi))/vth*np.exp(-0.5*(vp/vth)**2.)
    #TODO: Add in f0g eventually
    return f0a

def charge_update(xp,vp,w1,w2,f0):
    f0new = get_f0(xp,vp)
    w2new = 1. - f0new/f0
    w1new = w1 + (w2new-w2)
    return w1new,w2new,f0new

def calc_f(x,v,xp,vp,w0,w1):
    tinterp = time.time()
    indv = np.interp(vp,v,np.arange(v.size))
    print('interpolation complete, took %0.2f sec' % (time.time() - tinterp))
    wpv = indv - np.floor(indv)
    #f = np.zeros((x.size, v.size))
    f = np.ones((x.size, v.size))*np.inf
    tloop = time.time()
    indx = np.round(np.interp(xp,x,np.arange(x.size))).astype(int)
    vth = np.sqrt(Te*sml_ev2j/mass)
    Vnear = np.zeros(x.shape)
    Vnear[1:-1] = (x[2:]-x[0:-2])/2
    Vnear[0] = (x[1]-x[0])/2
    Vnear[-1] = (x[-1]-x[-2])/2
    #Vgrid = Vnear * (v[1]-v[0])*Te/np.sqrt(2*np.pi)
    Vgrid = Vnear * (v[1]-v[0])/vth*Te/np.sqrt(2*np.pi)
    #check how to use 2 index arrays e.g f[indx,indv]
    for ip in range(xp.size):
        
        if np.isinf(f[indx[ip], np.floor(indv[ip]).astype(int)]):
               f[indx[ip], np.floor(indv[ip]).astype(int)] = 0
        if np.isinf(f[indx[ip], np.ceil(indv[ip]).astype(int)]):
               f[indx[ip], np.ceil(indv[ip]).astype(int)] = 0
        f[indx[ip], np.floor(indv[ip]).astype(int)] += (1-wpv[ip])*w0[ip]*w1[ip]/Vgrid[indx[ip]]
        f[indx[ip], np.ceil(indv[ip]).astype(int)] += wpv[ip]*w0[ip]*w1[ip]/Vgrid[indx[ip]]
    print('loop complete, took %0.2f sec' % (time.time() - tloop))
    return f

def calc_eden(x,xp,w0,w1):
    indx = np.interp(xp,x,np.arange(x.size))
    wp = indx - np.floor(indx)
    cnts1,_ = np.histogram(xp,bins=x,weights=wp*w0*w1)
    cnts2,_ = np.histogram(xp,bins=x,weights=(1.-wp)*w0*w1)
    eden = np.zeros(x.shape)
    return eden
def f_sourcegrid(f,xp,vp,w0,w1,n_n):
    dfel = n_n[:,np.newaxis]*(0.8e-8*np.sqrt(Te)*np.exp(-13.56/Te)*(1./(1+0.01*Te))*1e-6)*dt*f
    w1new =  meshtoparticle(dfel,x,xp,vp,w0,w1)
    return w1new

def meshtoparticle(df,x,xp,vp,w0,w1):
    temp = Te*sml_ev2j
    v = np.linspace(-4*np.sqrt(temp/mass),4*np.sqrt(temp/mass),32)
    dv = v[1]-v[0]
    w1new = w1.copy()
    indv = np.interp(vp,v,np.arange(v.size))
    wpv = indv - np.floor(indv)
    wpv1 = wpv
    wpv2 = 1-wpv
    #wpv1 is for left mesh index, wpv2 is for right mesh index
    indx = np.interp(xp,x,np.arange(x.size))
    indx = np.round(indx)
    wpdens = 0*df.copy()
    Vnear = np.zeros(x.shape)
    Vnear[1:-1] = (x[2:]-x[0:-2])/2
    Vnear[0] = (x[1]-x[0])/2
    Vnear[-1] = (x[-1]-x[-1])/2
    Vgrid = Vnear * (v[1]-v[0])*Te/np.sqrt(2*np.pi)
    #"particle way" of doing things
    indx = np.round(np.interp(xp,x,np.arange(x.size))).astype(int)
    indv = np.interp(vp,v,np.arange(v.size), right = np.nan,left = np.nan)
    indvfloor = np.floor(indv).astype(int)
    wpv = indv-indvfloor
    wpv1 = 1-wpv
    wpv2 = wpv
    wpden = np.zeros((x.size,v.size))
    for ip in range(Np):
        if np.isnan(indv[ip]): continue
        wpden[indx[ip],indvfloor[ip]] += wpv1[ip]
        wpden[indx[ip],indvfloor[ip]+1] += wpv2[ip]
    for ip in range(Np):
        if np.isnan(indv[ip]): continue
        w1new[ip] += (wpv1[ip]*df[indx[ip],indvfloor[ip]]/wpden[indx[ip],indvfloor[ip]] + wpv2[ip]*df[indx[ip],indvfloor[ip]+1]/wpden[indx[ip],indvfloor[ip]+1])/w0[ip] 
    return w1new
    for ix in range(x.size):
        #to do: fix for end cases, since dx varies
        xinds = np.where (indx == ix)[0]
        #switched to v
        for iv in range(v.size):
            if iv == 0:
                vstart = v[0]
                vend = v[1]
            elif iv == v.size-1:
                vstart = v[-2]
                vend = v[-1]
            else:
                vstart = v[iv-1]
                vend = v[iv+1]
            #end of switching to v
            vinds = np.where((vp > vstart) & (vp <= vend))[0]
            if iv == 0:
                vstart1 = v[0]
                vend1 = v[0] + dv/2
            elif iv == v.size-1:
                vstart1 = v[-1] - dv/2
                vend1 = v[-1]
            else:
                vstart1 = v[iv] - dv/2
                vend1 = v[iv] + dv/2
            #vinds1 = np.where((vp > vstart1) & (vp <= vend1))[0]
            #vinds2 = np.setdiff1d(vinds, vinds1)
            vinds1 = np.where((vp < v[iv]) & (vp >= vstart))[0]
            vinds2 = np.where((vp > v[iv]) & (vp <= vend))[0]
            inds1 = np.intersect1d(xinds,vinds1)
            inds2 = np.intersect1d(xinds,vinds2)
            inds = np.intersect1d(xinds,vinds)
            if inds.size == 0:continue
            wpden = np.sum(wpv1[inds1]) + np.sum(wpv2[inds2])
            dfep1 = (wpv1[inds1]/wpden)*(df[ix,iv])*Vgrid[ix]
            dfep2 = (wpv2[inds2]/wpden)*(df[ix,iv])*Vgrid[ix]
            w1new[inds1] += dfep1/w0[inds1]
            w1new[inds2] += dfep2/w0[inds2]
            wpdens[ix,iv] = wpden
    #return w1new,wpdens
    return w1new

def pushe(xp,vp,w1,w2):
    #subcycle electrons (100 subcycle steps)
    #print(dt)
    xpold= xp.copy()
    vpold = vp.copy()
    vpnew = vp.copy()
    w1old = w1.copy()
    for itn in range(Nsubcycle):
        xpnew = xpold + vpold*dt/float(Nsubcycle)

        #check for particles that went through sheath. THIS IS AN EFFECTIVE SOURCE
        outinds = np.where((xpnew<0) | (xpnew>x[-1]))[0]
        if outinds.size>0:
            xpnew[outinds] = xpold[outinds] #put particle to previous position
            vpnew[outinds] = -vpold[outinds] #reflect velocity of particle
            #print("sanity check")
            En = 0.5*mass*vpnew[outinds]**2.*sml_j2ev
            highEinds = np.where(En>potSheath)[0]
            if highEinds.size>0:
                w1[outinds[highEinds]] = -1. + w2[outinds[highEinds]]

        #check for particles that went past LFS midplane
        #lostinds = np.where(xpnew>x[-1])[0]
        #if lostinds.size>0:
            #w1[lostinds] = 0.
            #w2[lostinds] = 0.
            #xpnew[lostinds] = xpold[lostinds] #just gather at the boundary
            #print(itn, w1.min(),np.sum(xpnew > (x[-1] - 0.1))/float(xpnew.size))
            #print(2*x[-1]/(np.sqrt(Te*charge/mass)))

        xpold = xpnew.copy()
 
        vpold = vpnew.copy()
	
    return (xpnew,vpnew,w1,w2)

def f_source(n_n,Te,dt,w0,f0,w1):
    #for now, just the cold electron neutral piece
    #this is not the same as XGC, doing directly to the particle instead of 
    #going through the grid first
    n_np = np.interp(xp,x,n_n)
    w1new = w1 + n_np*(0.8e-8*np.sqrt(Te)*np.exp(-13.56/Te)*(1./(1+0.01*Te))*1e-6)*dt*f0/w0
    return w1new 

def plot(xp,w1,it):
     plt.figure()
     plt.plot(xp, w1, '.')
     plt.savefig('w1_t' + str(it).zfill(3) + '.png')
	
#def main():
if __name__=="__main__":
    #first, load the mesh grid. x=0 is LFS divertor, x[-1] is LFS midplane
    x = create_1d_grid()
    x = np.linspace(x[0],x[-1],x.size)
    temp = Te*sml_ev2j
    v = np.linspace(-4*np.sqrt(temp/mass),4*np.sqrt(temp/mass),32)
    #next, load the particle data
    marker_den = Np/(x[-1]-x[0])
    t1 = time.time()
    xp,vp,w0,f0,w1,w2 = load_markers(x,mass,ne,Te,Np,marker_den)
    print('load_markers complete, took %0.2f sec' % (time.time()-t1))

    n_n = load_neutrals(file_neutrals)
    #this is ordered from LFS divertor to HFS divertor. Interpolate by index
    #onto x grid

    #now, do the main time loop
    dt = sml_dt*7.9e-5 #put in units of seconds
    eden = np.zeros((x.size,Ntimes))
    #Ntimes = 0
    #simplefilter('error')
    for it in range(Ntimes):
	
        print('Step %d' % it)
        t2 = time.time()
        w1,w2,_  = charge_update(xp,vp,w1,w2,f0)
        print('charge_update complete, took %0.2f sec' % (time.time()-t2))
        t3 = time.time()
        eden[:,it] = calc_eden(x,xp,w0,w1)
        print('calc_eden complete, took %0.2f sec' % (time.time()-t3))
        t4 = time.time()
        xp,vp,w1,w2 = pushe(xp,vp,w1,w2)
        print('pushe complete, took %0.2f sec' % (time.time()-t4))
        #method 1 
        #t5 = time.time()
        #fparticle = calc_f(x,v,xp,vp,w0,w1)
        #print('calc_f complete, took %0.2f sec' % (time.time()-t5))
        #t6 = time.time()
        #w1 = f_source(n_n,Te,dt,w0,f0,w1)
        #print('f_source complete, took %0.2f sec' % (time.time()-t6))
        #f1 = calc_f(x,v,xp,vp,w0,w1)
        #method 2
        fanalytical = np.ones(x.shape)[:,np.newaxis]* get_f0(x,v)[np.newaxis,:]
        fparticle = calc_f(x,v,xp,vp,w0,w1)
        ftotal = fanalytical + fparticle
        t7 = time.time()
        w1 = f_sourcegrid(ftotal,xp,vp,w0,w1,n_n)
        print('f_sourcegrid complete, took %0.2f sec' % (time.time() -t7))
        f1 = calc_f(x,v,xp,vp,w0,w1)

        if np.all(w1 < 0):
 
            print("all w1 negative at time step %d" % it)  

    plot(xp, w1, it)
    plt.figure()
    vth = np.sqrt(Te*sml_ev2j/mass)
    plt.contourf(v/vth,x,f1,100,extend='both',cmap = "Reds")
    plt.ylim([0,20])
    plt.xlabel("$v_\parallel/v_{th}$")
    plt.ylabel("$L_\parallel$")
    plt.figure()
    plt.plot(f1[1,:])
     
