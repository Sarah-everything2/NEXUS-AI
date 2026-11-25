import unittest
from unittest.mock import AsyncMock, patch

from tools import manager


class GitHubApprovalTests(unittest.IsolatedAsyncioTestCase):

    async def test_denied_approval_blocks_direct_github_execution(self):
        with patch.object(
            manager, "approve_tool_call", return_value=False
        ) as approval, patch.object(
            manager, "github_call", new_callable=AsyncMock
        ) as github_call:

            result = await manager.execute_tool(
                "github_list_commits",
                owner="test-owner",
                repo="test-repo",
            )

            self.assertIn("cancelled", result.lower())
            approval.assert_called_once()
            github_call.assert_not_awaited()

    async def test_approved_github_execution_calls_allowlisted_tool(self):
        with patch.object(
            manager, "approve_tool_call", return_value=True
        ) as approval, patch.object(
            manager, "github_call", new_callable=AsyncMock
        ) as github_call:

            expected = {"status": "success"}
            github_call.return_value = expected

            result = await manager.execute_tool(
                "github_list_commits",
                owner="test-owner",
                repo="test-repo",
            )

            self.assertEqual(result, expected)
            approval.assert_called_once_with(
                "github_list_commits",
                {"owner": "test-owner", "repo": "test-repo"},
            )
            github_call.assert_awaited_once_with(
                "list_commits",
                {"owner": "test-owner", "repo": "test-repo"},
            )


if __name__ == "__main__":
    unittest.main()
