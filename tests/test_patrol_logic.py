import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import sys
import os

# Add src folder to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src/backend')))

from patrol_service import PatrolServiceAsync

class TestPatrolLogic(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.patrol_service = PatrolServiceAsync()
        self.patrol_service.is_patrolling = True
        
        # Mocks
        self.mock_logger_patcher = patch('patrol_service.logger')
        self.mock_logger = self.mock_logger_patcher.start()
        
        self.mock_robot_service_patcher = patch('patrol_service.robot_service')
        self.mock_robot_service = self.mock_robot_service_patcher.start()
        self.mock_robot_service.get_client = MagicMock(return_value=True)
        self.mock_robot_service.move_to = AsyncMock(return_value={"success": True})
        self.mock_robot_service.get_front_camera_image = AsyncMock(return_value=MagicMock(data=b'fakedata'))
        self.mock_robot_service.return_home = AsyncMock()
        
        self.mock_ai_service_patcher = patch('patrol_service.ai_service')
        self.mock_ai_service = self.mock_ai_service_patcher.start()
        self.mock_ai_service.is_configured = MagicMock(return_value=True)
        self.mock_ai_service.get_model_name = MagicMock(return_value="test-model")
        
        self.mock_db_patcher = patch('patrol_service.get_db_connection')
        self.mock_db_conn = self.mock_db_patcher.start()
        self.mock_cursor = MagicMock()
        self.mock_db_conn.return_value.cursor.return_value = self.mock_cursor
        
        # Mock file IO
        self.mock_load_json_patcher = patch('patrol_service.load_json')
        self.mock_load_json = self.mock_load_json_patcher.start()
        
        self.mock_image_patcher = patch('patrol_service.Image')
        self.mock_image = self.mock_image_patcher.start()
        self.mock_image.open.return_value = MagicMock()

        self.mock_makedirs_patcher = patch('os.makedirs')
        self.mock_makedirs_patcher.start()

    async def asyncTearDown(self):
        self.mock_logger_patcher.stop()
        self.mock_robot_service_patcher.stop()
        self.mock_ai_service_patcher.stop()
        self.mock_db_patcher.stop()
        self.mock_load_json_patcher.stop()
        self.mock_image_patcher.stop()
        self.mock_makedirs_patcher.stop()

    async def test_patrol_flow_success(self):
        """Test a standard successful patrol with 2 points."""
        points = [
            {"name": "Point A", "x": 1, "y": 1, "enabled": True},
            {"name": "Point B", "x": 2, "y": 2, "enabled": True}
        ]
        self.mock_load_json.side_effect = [points, {}] # points, settings

        # Start a dummy worker to drain the queue
        async def drain_queue():
            while True:
                await self.patrol_service.inspection_queue.get()
                self.patrol_service.inspection_queue.task_done()
        
        drain_task = asyncio.create_task(drain_queue())

        try:
            # Run patrol logic
            await self.patrol_service._patrol_logic()
        finally:
            drain_task.cancel()

        # Verification
        # Robot moved twice
        self.assertEqual(self.mock_robot_service.move_to.call_count, 2)
        # Camera captured twice
        self.assertEqual(self.mock_robot_service.get_front_camera_image.call_count, 2)
        # Queue should be empty because we drained it
        self.assertEqual(self.patrol_service.inspection_queue.qsize(), 0)
        
        # Ensure return home called
        self.mock_robot_service.return_home.assert_awaited()

    async def test_patrol_flow_retry(self):
        """Test move error triggers retry."""
        points = [{"name": "Point A", "x": 1, "y": 1, "enabled": True}]
        self.mock_load_json.side_effect = [points, {}]

        # Fail once, then succeed
        self.mock_robot_service.move_to.side_effect = [
            {"success": False, "error": "Bumped"},
            {"success": True}
        ]
        
        # Start a dummy worker to drain the queue
        async def drain_queue():
            while True:
                await self.patrol_service.inspection_queue.get()
                self.patrol_service.inspection_queue.task_done()
        
        drain_task = asyncio.create_task(drain_queue())

        try:
            await self.patrol_service._patrol_logic()
        finally:
            drain_task.cancel()

        # Called move twice (Original + 1 retry)
        self.assertEqual(self.mock_robot_service.move_to.call_count, 2)
        # Succeeded eventually, so captured image
        self.assertEqual(self.mock_robot_service.get_front_camera_image.call_count, 1)

    async def test_patrol_flow_max_retries(self):
        """Test move error max retries."""
        points = [{"name": "Point A", "x": 1, "y": 1, "enabled": True}]
        self.mock_load_json.side_effect = [points, {}]

        # Fail always
        self.mock_robot_service.move_to.return_value = {"success": False, "error": "Blocked"}

        # Start a dummy worker to drain the queue (though it shouldn't get anything)
        async def drain_queue():
            while True:
                await self.patrol_service.inspection_queue.get()
                self.patrol_service.inspection_queue.task_done()
        
        drain_task = asyncio.create_task(drain_queue())

        try:
            await self.patrol_service._patrol_logic()
        finally:
            drain_task.cancel()

        # Default Max Retries = 3. 
        # Sequence: Try (0) -> Fail -> Retry (1) -> Fail -> Retry (2) -> Fail -> Retry (3) -> Fail -> Max reached -> Drop
        # Total calls = 1 (initial) + 3 (retries) = 4 calls.
        self.assertEqual(self.mock_robot_service.move_to.call_count, 4)
        
        # Should NOT capture image
        self.mock_robot_service.get_front_camera_image.assert_not_awaited()

if __name__ == '__main__':
    unittest.main()
