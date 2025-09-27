# Cube Example
"""
Created on Mon Oct 22 10:04:29 2018

@author: DR.AYAZ
"""

import multiprocessing as mp
import os
import time

def cube(x):
    print(os.getpid())
    return (os.getpid(), x**3)

if __name__ == "__main__":
  start_time = time.time()
  pool = mp.Pool(processes=4)
  results = [pool.apply(cube, args=(x,)) for x in range(1,100)]
  #results = [p.get() for p in results]
  end_time = time.time()
  print(f'Result: {results} \n Process 4 time: {end_time-start_time}')

  start_time = time.time()
  pool = mp.Pool(processes=10)
  results = [pool.apply(cube, args=(x,)) for x in range(1,100)]
  #results = [p.get() for p in results]
  end_time = time.time()
  print(f'Process 10 time: {end_time-start_time}')