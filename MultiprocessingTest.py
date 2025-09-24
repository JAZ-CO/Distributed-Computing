# only_sleep and crunch_numbers
"""
Created on Mon Oct 22 09:45:22 2018

@author: DR.AYAZ
"""

import os
import time
import threading
import multiprocessing

NUM_WORKERS = 4

def only_sleep():
    """ Do nothing, wait for a timer to expire """
    print("PID: %s, Process Name: %s, Thread Name: %s" % (
        os.getpid(),
        multiprocessing.current_process().name,
        threading.current_thread().name)
    )
    time.sleep(1)
    g_var = os.getpid()

def crunch_numbers():
    """ Do some computations """
    print("PID: %s, Process Name: %s, Thread Name: %s" % (
        os.getpid(),
        multiprocessing.current_process().name,
        threading.current_thread().name)
    )
    x = 0
    while x < 10000000:
        x += 1

if __name__ == "__main__":
  ## Run tasks serially
  start_time = time.time()
  for _ in range(NUM_WORKERS):
      only_sleep()
  end_time = time.time()

  print("Serial time=", end_time - start_time)

  # Run tasks using threads
  start_time = time.time()
  threads = [threading.Thread(target=only_sleep) for _ in range(NUM_WORKERS)]
  [thread.start() for thread in threads]
  [thread.join() for thread in threads]
  end_time = time.time()

  print("Threads time=", end_time - start_time)

  # Run tasks using processes
  start_time = time.time()
  processes = [multiprocessing.Process(target=only_sleep) for x in range(NUM_WORKERS)]
  for p in processes:
      p.start()
  #[process.start() for process in processes]
  for p in processes:
      p.join()
  #[process.join() for process in processes]
  end_time = time.time()

  print("Multiprocessing time=", end_time - start_time)
