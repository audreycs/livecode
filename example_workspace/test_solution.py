from solution import solve

def test_solve():
    assert solve([1, 2, 3]) == 3
    assert solve([5, 1, 9, 3]) == 9
    assert solve([]) is None
    assert solve([42]) == 42
    print('All tests passed!')

if __name__ == '__main__':
    test_solve()