from threading import *
import time

class BankAccount():
  def __init__(self, name, balance):
    self.name = name
    self.balance = balance

  def __str__(self):
    return self.name

# These accounts are our shared resources
account1 = BankAccount("account1", 100)
account2 = BankAccount("account2", 0)
l = Lock() # creating the lock object

class BankTransferThread(Thread):
  def __init__(self, sender, receiver, amount):
    Thread.__init__(self)
    self.sender = sender
    self.receiver = receiver
    self.amount = amount

  def run(self):
    # Adding Lock to fix the Race Condition
    l.acquire()
    sender_initial_balance = self.sender.balance
    sender_initial_balance -= self.amount
    # Inserting delay to allow switch between threads
    time.sleep(0.001)
    
    self.sender.balance = sender_initial_balance

    receiver_initial_balance = self.receiver.balance
    receiver_initial_balance += self.amount
    
    # Inserting delay to allow switch between threads
    time.sleep(0.001)
    self.receiver.balance = receiver_initial_balance
    l.release()

if __name__ == "__main__":

  threads = []

  for i in range(100):
    threads.append(BankTransferThread(account1, account2, 1))

  for thread in threads:
    thread.start()

  for thread in threads:
    thread.join()

  print('account1 ', account1.balance)
  print('account2 ', account2.balance)