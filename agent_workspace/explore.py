from collections import deque
import itertools

def neighbors(state):
    N=len(state)
    res=[]
    for i in range(N-3):
        a=state[i]; b=state[i+1]; c=state[i+2]; d=state[i+3]
        M=(a+d)/2
        b2=2*M - b
        c2=2*M - c
        new=list(state)
        new[i+1]=b2
        new[i+2]=c2
        res.append(tuple(new))
    return res


def min_sum(start):
    seen=set([tuple(start)])
    dq=deque([tuple(start)])
    min_s=sum(start)
    while dq:
        s=dq.popleft()
        min_s=min(min_s,sum(s))
        for t in neighbors(list(s)):
            if t not in seen:
                seen.add(t)
                dq.append(t)
    return min_s, seen

# try small cases
cases=[(1,5,7,10),(0,1,6,10,14,16),(0,2,5,9)]
for c in cases:
    m,seen = min_sum(c)
    print(c, 'min', m)
    # print reachable count
    print('states', len(seen))

# brute force to find minimal sums for random small sets
import random
for N in range(4,8):
    print('N',N)
    for trial in range(5):
        xs=sorted(random.sample(range(0,10),N))
        m,_=min_sum(xs)
        print(xs,'sum',sum(xs),'min',m)
    print()