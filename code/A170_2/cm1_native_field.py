#!/usr/bin/env python3
"""Native-stagger W3 subwindow -> time-varying vector field at moving turbine points.
All coordinates are original CM1 km, all times original CM1 seconds. No data scaling.
"""
import numpy as np
from scipy.interpolate import RegularGridInterpolator

class Field:
    def __init__(self, packet, profile='power'):
        if profile not in ('power','wood'): raise ValueError(profile)
        z=np.load(packet)
        self.time=np.asarray(z['time_s'],float)
        self.xh=np.asarray(z['xh_km'],float);self.yh=np.asarray(z['yh_km'],float)
        self.profile=profile
        assert len(self.time)==841 and np.allclose(np.diff(self.time),1)
        zh=np.asarray(z['zh_km'],float);zf=np.asarray(z['zf_km'],float)
        assert np.isclose(zh[0],.05) and np.isclose(zh[1],.15)
        for name,axes in (('u',(self.time,np.asarray(z['yh_km'],float),np.asarray(z['xf_km'],float))),
                          ('v',(self.time,np.asarray(z['yf_km'],float),np.asarray(z['xh_km'],float)))):
            self.__dict__[name+'0']=RegularGridInterpolator(axes,np.asarray(z[name][:,0],float),bounds_error=True)
            self.__dict__[name+'1']=RegularGridInterpolator(axes,np.asarray(z[name][:,1],float),bounds_error=True)
        waxes=(self.time,self.yh,self.xh)
        # w on zf=0,100,200 m: interpolate to velocity levels 50 and 150 m.
        self.w0=RegularGridInterpolator(waxes,.5*(z['w'][:,0]+z['w'][:,1]),bounds_error=True)
        self.w1=RegularGridInterpolator(waxes,.5*(z['w'][:,1]+z['w'][:,2]),bounds_error=True)
        z.close()
    def sample(self,t,x_m,y_m,z_m):
        """Broadcast arrays. x/y are offsets in metres from the selected xh/yh grid point.
        Magnitude profile from two levels; interpolate wind direction circularly.
        Below 50m and above 150m are assumed profile extrapolations.
        """
        t,x_m,y_m,z_m=np.broadcast_arrays(np.asarray(t,float),x_m,y_m,z_m)
        shp=t.shape; zz=z_m.ravel();tt=t.ravel()
        xx=self.xh[self.xidx]+np.asarray(x_m).ravel()/1000
        yy=self.yh[self.yidx]+np.asarray(y_m).ravel()/1000
        xyz=np.stack([tt,yy,xx],axis=1)
        u0=self.u0(xyz);v0=self.v0(xyz);u1=self.u1(xyz);v1=self.v1(xyz)
        s0=np.hypot(u0,v0);s1=np.hypot(u1,v1)
        ratio=np.maximum(s1,.1)/np.maximum(s0,.1)
        if self.profile=='power':
            alpha=np.clip(np.log(ratio)/np.log(3),-.5,.8)
            speed=s0*(np.maximum(zz,1)/50)**alpha
        else:
            r=np.clip(ratio,.2,2.9)
            zm=np.clip(-100/np.log(r/3),55,500)
            def shape(h):
                q=h/zm
                return q*np.exp(1-q)
            speed=s0*shape(np.maximum(zz,1))/shape(50)
        ang0=np.arctan2(v0,u0)
        d=np.angle(np.exp(1j*(np.arctan2(v1,u1)-ang0)))
        ang=ang0+np.clip((zz-50)/100,0,1)*d
        w=self.w0(xyz)+(self.w1(xyz)-self.w0(xyz))*np.clip((zz-50)/100,0,1)
        return np.stack([speed*np.cos(ang),speed*np.sin(ang),w]).reshape((3,)+shp)
    def set_origin(self,iy,ix):
        assert 0<=iy<len(self.yh) and 0<=ix<len(self.xh)
        self.yidx=int(iy);self.xidx=int(ix)
