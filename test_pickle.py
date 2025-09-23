import pickle
d = [1,2]
msg = pickle.dumps(d)
print(msg)
recd = pickle.loads(msg)
print(recd)
