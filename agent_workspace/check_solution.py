from solution import Solution

def run_tests():
    sol = Solution()
    tests = [
        ((["leet","code"], "e"), [0,1]),
        ((["abc","bcd","aaaa","cbc"], "a"), [0,2]),
        ((["abc","bcd","aaaa","cbc"], "z"), []),
    ]
    all_ok = True
    for (words, x), expected in tests:
        out = sol.findWordsContaining(words, x)
        if out != expected:
            print(f"FAIL: words={words}, x={x} => {out} (expected {expected})")
            all_ok = False
        else:
            print(f"OK: words={words}, x={x} => {out}")
    if all_ok:
        print("All tests passed")
    else:
        print("Some tests failed")

if __name__ == '__main__':
    run_tests()
