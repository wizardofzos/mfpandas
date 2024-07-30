import sys
sys.path.append("../src/mfpandas")

from irrdbu00 import IRRDBU00

r = IRRDBU00('../test_irrdbu00_data')
r.parse_fancycli()


def a():
    return r.groups.loc[r.groups.GPBD_NAME=='SYS1']

def b():
    return r.groups[r.groups.GPBD_NAME=='SYS1']

def c():
    return r.groups[r.groups['GPBD_NAME'].to_numpy()=='SYS1']

import time

def dotime():
    start = time.time()
    for i in range(1000):
        z = a()
    elaps = time.time() - start
    print('A: .loc       ', elaps/1000)
    start = time.time()
    for i in range(1000):
        z = b()
    elaps = time.time() - start
    print('B: no .loc    ', elaps/1000)
    start = time.time()
    for i in range(1000):
        z = c()
    elaps = time.time() - start
    print('C: with_numpy ', elaps/1000)

dotime()
