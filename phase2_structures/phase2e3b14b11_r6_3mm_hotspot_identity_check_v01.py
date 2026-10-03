from math import sqrt
old=(-5.025296,53.190953,965.183876,415.49)
new=(-5.025680,53.191410,965.185037,411.23)
dx=new[0]-old[0]; dy=new[1]-old[1]; dz=new[2]-old[2]
print('3D hotspot shift [mm]:', sqrt(dx*dx+dy*dy+dz*dz))
print('Stress change [%]:', 100*(new[3]-old[3])/old[3])
