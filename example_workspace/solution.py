def solve(nums):
    """
    Find the maximum number in the list.
    """
    if not nums:
        return None
    return max(nums)

if __name__ == '__main__':
    # Test the function
    test_nums = [3, 1, 4, 1, 5, 9, 2, 6]
    result = solve(test_nums)
    print(f'Maximum number: {result}')
