from threading import *
import time

s = Semaphore(2) # creating the semaphore object initialized with 2 threads allowed to access simultaneously.
l = Lock()
# create a lock object here

def wish(name,age):
   s.acquire()  # acquire sempahore instance by the current thread
   for i in range(3):
       # acquire the lock here
       l.acquire()
       print("Hi",name)
       time.sleep(2)
       print("Your age is",age)
       # release the lock here
       l.release()
   s.release() # release semaphore instance by the current thread

t1=Thread(target=wish, args=("Abullah",15))
t2=Thread(target=wish, args=("Muhammad",20))
t3=Thread(target=wish, args=("Abubaker",25))
t4=Thread(target=wish, args=("Omar",30))

t1.start()
t2.start()
t3.start()
t4.start()
t1.join()
t2.join()
t3.join()
t4.join()
