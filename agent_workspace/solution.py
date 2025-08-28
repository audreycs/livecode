from typing import List

class Solution:
    def maxSubarraySum(self, nums: List[int], k: int) -> int:
        """
        Return the maximum sum of a subarray whose length is divisible by k.
        Use prefix sums and keep the minimum prefix sum for each index modulo k.
        """
        n = len(nums)
        # min_prefix[r] stores minimum prefix sum P[i] for indices i with i % k == r
        min_prefix = [float('inf')] * k
        prefix = 0
        # prefix sum at index 0 (no elements) has remainder 0
        min_prefix[0] = 0
        ans = -10**30

        # iterate j from 1..n, prefix is P[j]
        for j, val in enumerate(nums, start=1):
            prefix += val
            r = j % k
            if min_prefix[r] != float('inf'):
                ans = max(ans, prefix - min_prefix[r])
            # update minimal prefix for this remainder
            if prefix < min_prefix[r]:
                min_prefix[r] = prefix

        return ans

# Quick internal tests
if __name__ == '__main__':
    s = Solution()
    print(s.maxSubarraySum([1,2], 1))           # 3
    print(s.maxSubarraySum([-1,-2,-3,-4,-5],4)) # -10
    print(s.maxSubarraySum([-5,1,2,-3,4],2))    # 4
