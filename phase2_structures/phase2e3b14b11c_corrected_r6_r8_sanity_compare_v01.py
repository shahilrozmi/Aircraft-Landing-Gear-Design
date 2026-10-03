def pct(new, old): return 100.0*(new-old)/old
r6_stress=412.24
r6_def=5.1439
r6_force=-67348.0
r8_stress=266.91
r8_def=3.4981
r8_force=-67391.0
print('R8 stress vs R6 [%]:', pct(r8_stress,r6_stress))
print('R8 deformation vs R6 [%]:', pct(r8_def,r6_def))
print('R8 brace |F| vs R6 [%]:', pct(abs(r8_force),abs(r6_force)))
