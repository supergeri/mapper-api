
    @pytest.mark.unit
    def test_get_pending_syncs_success(
        self, mock_status, mock_failed, mock_confirm, mock_pending,
        mock_queue, mock_get, mock_run, client
    ):
        """Successfully get pending syncs."""
        mock_run.return_value = [
            {
                "workout_id": TEST_WORKOUT_ID,
                "queued_at": "2024-01-01T00:00:00Z",
                "workouts": {
                    "id": TEST_WORKOUT_ID,
                    "title": "Test Workout",
                    "workout_data": SAMPLE_WORKOUT_DATA,
                    "created_at": "2024-01-01T00:00:00Z",
                }
            }
        ]
        
        response = client.get("/sync/pending?device_type=ios")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "workouts" in data
        assert data["count"] == 1

    @pytest.mark.unit
    def test_get_pending_syncs_with_device_id(
        self, mock_status, mock_failed, mock_confirm, mock_pending,
        mock_queue, mock_get, mock_run, client
    ):
        """Get pending syncs with specific device ID."""
        mock_run.return_value = []
        
        response = client.get(f"/sync/pending?device_type=android&device_id={TEST_DEVICE_ID}")
        
        assert response.status_code == 200

    @pytest.mark.unit
    def test_get_pending_syncs_invalid_device_type(
        self, mock_status, mock_failed, mock_confirm, mock_pending,
        mock_queue, mock_get, mock_run, client
    ):
        """Return 400 for invalid device type."""
        response = client.get("/sync/pending?device_type=invalid")
        
        assert response.status_code == 400

    @pytest.mark.unit
    def test_confirm_sync_success(
        self, mock_status, mock_failed, mock_confirm, mock_pending,
        mock_queue, mock_get, mock_run, client
    ):
        """Successfully confirm sync."""
        mock_run.return_value = {
            "status": "synced",
            "synced_at": "2024-01-01T00:00:00Z"
        }
        
        response = client.post(
            "/sync/confirm",
            json={
                "workout_id": TEST_WORKOUT_ID,
                "device_type": "ios",
                "device_id": TEST_DEVICE_ID
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status"] == "synced"
        assert "synced_at" in data

    @pytest.mark.unit
    def test_confirm_sync_not_found(
        self, mock_status, mock_failed, mock_confirm, mock_pending,
        mock_queue, mock_get, mock_run, client
    ):
        """Return 404 when sync entry not found."""
        mock_run.return_value = None
        
        response = client.post(
            "/sync/confirm",
            json={
                "workout_id": TEST_WORKOUT_ID,
                "device_type": "ios"
            }
        )
        
        assert response.status_code == 404

    @pytest.mark.unit
    def test_report_sync_failed_success(
        self, mock_status, mock_failed, mock_confirm, mock_pending,
        mock_queue, mock_get, mock_run, client
    ):
        """Successfully report sync failure."""
        mock_run.return_value = {
            "status": "failed",
            "failed_at": "2024-01-01T00:00:00Z"
        }
        
        response = client.post(
            "/sync/failed",
            json={
                "workout_id": TEST_WORKOUT_ID,
                "device_type": "android",
                "error": "Network timeout",
                "device_id": TEST_DEVICE_ID
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status"] == "failed"
        assert "failed_at" in data

    @pytest.mark.unit
    def test_report_sync_failed_not_found(
        self, mock_status, mock_failed, mock_confirm, mock_pending,
        mock_queue, mock_get, mock_run, client
    ):
        """Return 404 when sync entry not found for failure report."""
        mock_run.return_value = None
        
        response = client.post(
            "/sync/failed",
            json={
                "workout_id": TEST_WORKOUT_ID,
                "device_type": "garmin",
                "error": "Sync failed"
            }
        )
        
        assert response.status_code == 404

    @pytest.mark.unit
    def test_get_sync_status_success(
        self, mock_status, mock_failed, mock_confirm, mock_pending,
        mock_queue, mock_get, mock_run, client, sample_workout_record
    ):
        """Successfully get sync status for workout."""
        mock_run.side_effect = [
            sample_workout_record,  # First call for get_workout
            {  # Second call for get_workout_sync_status
                "ios": {
                    "status": "synced",
                    "queued_at": "2024-01-01T00:00:00Z",
                    "synced_at": "2024-01-01T01:00:00Z"
                },
                "android": {
                    "status": "pending",
                    "queued_at": "2024-01-01T00:00:00Z"
                },
                "garmin": None
            }
        ]
        
        response = client.get(f"/workouts/{TEST_WORKOUT_ID}/sync-status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "sync_status" in data
        assert data["sync_status"]["ios"]["status"] == "synced"
        assert data["sync_status"]["android"]["status"] == "pending"
        assert data["sync_status"]["garmin"] is None

    @pytest.mark.unit
    def test_get_sync_status_workout_not_found(
        self, mock_status, mock_failed, mock_confirm, mock_pending,
        mock_queue, mock_get, mock_run, client
    ):
        """Return 404 when workout not found."""
        mock_run.return_value = None
        
        response = client.get(f"/workouts/{TEST_WORKOUT_ID}/sync-status")
        
        assert response.status_code == 404


# =============================================================================
# Request/Response Model Tests
# =============================================================================

class TestSyncRequestModels:
    """Tests for Pydantic request/response models."""

    @pytest.mark.unit
    def test_queue_sync_request_valid(self):
        """Valid QueueSyncRequest with all device types."""
        from api.routers.sync import QueueSyncRequest, DeviceType
        
        for device_type in DeviceType:
            request = QueueSyncRequest(device_type=device_type, device_id="device-123")
            assert request.device_type == device_type
            assert request.device_id == "device-123"

    @pytest.mark.unit
    def test_queue_sync_request_optional_device_id(self):
        """QueueSyncRequest with optional device_id."""
        from api.routers.sync import QueueSyncRequest, DeviceType
        
        request = QueueSyncRequest(device_type=DeviceType.IOS)
        assert request.device_id is None

    @pytest.mark.unit
    def test_confirm_sync_request(self):
        """Valid ConfirmSyncRequest."""
        from api.routers.sync import ConfirmSyncRequest, DeviceType
        
        request = ConfirmSyncRequest(
            workout_id="workout-123",
            device_type=DeviceType.ANDROID,
            device_id="device-456"
        )
        assert request.workout_id == "workout-123"
        assert request.device_type == DeviceType.ANDROID
        assert request.device_id == "device-456"

    @pytest.mark.unit
    def test_report_sync_failed_request(self):
        """Valid ReportSyncFailedRequest."""
        from api.routers.sync import ReportSyncFailedRequest, DeviceType
        
        request = ReportSyncFailedRequest(
            workout_id="workout-123",
            device_type=DeviceType.GARMIN,
            error="Connection timeout",
            device_id="device-789"
        )
        assert request.workout_id == "workout-123"
        assert request.device_type == DeviceType.GARMIN
        assert request.error == "Connection timeout"
        assert request.device_id == "device-789"

    @pytest.mark.unit
    def test_sync_to_garmin_request_valid(self):
        """Valid SyncToGarminRequest."""
        from api.routers.sync import SyncToGarminRequest
        
        request = SyncToGarminRequest(
            blocks_json={"blocks": [{"exercises": [{"name": "Push-ups"}]}]},
            workout_title="Test Workout",
            schedule_date="2024-12-25"
        )
        assert request.workout_title == "Test Workout"
        assert request.schedule_date == "2024-12-25"

    @pytest.mark.unit
    def test_sync_to_garmin_request_no_schedule_date(self):
        """SyncToGarminRequest without schedule_date."""
        from api.routers.sync import SyncToGarminRequest
        
        request = SyncToGarminRequest(
            blocks_json={"blocks": []},
            workout_title="Test Workout"
        )
        assert request.schedule_date is None

    @pytest.mark.unit
    def test_sync_to_garmin_request_invalid_date_format(self):
        """SyncToGarminRequest rejects invalid date format."""
        from api.routers.sync import SyncToGarminRequest
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError) as exc_info:
            SyncToGarminRequest(
                blocks_json={"blocks": []},
                workout_title="Test",
                schedule_date="25-12-2024"  # Wrong format
            )
        assert "YYYY-MM-DD" in str(exc_info.value)

    @pytest.mark.unit
    def test_sync_to_garmin_request_invalid_blocks_json(self):
        """SyncToGarminRequest rejects invalid blocks_json."""
        from api.routers.sync import SyncToGarminRequest
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError) as exc_info:
            SyncToGarminRequest(
                blocks_json=[],  # Should be a dict with blocks key
                workout_title="Test"
            )
        assert "dictionary" in str(exc_info.value).lower() or "blocks" in str(exc_info.value).lower()


# =============================================================================
# Device Type Enum Tests
# =============================================================================

class TestDeviceTypeEnum:
    """Tests for DeviceType enum."""

    @pytest.mark.unit
    def test_device_type_values(self):
        """DeviceType enum has correct values."""
        from api.routers.sync import DeviceType
        
        assert DeviceType.IOS.value == "ios"
        assert DeviceType.ANDROID.value == "android"
        assert DeviceType.GARMIN.value == "garmin"

    @pytest.mark.unit
    def test_device_type_from_string(self):
        """Can create DeviceType from string."""
        from api.routers.sync import DeviceType
        
        assert DeviceType("ios") == DeviceType.IOS
        assert DeviceType("android") == DeviceType.ANDROID
        assert DeviceType("garmin") == DeviceType.GARMIN

    @pytest.mark.unit
    def test_device_type_invalid_value(self):
        """Invalid device type raises ValueError."""
        from api.routers.sync import DeviceType
        
        with pytest.raises(ValueError):
            DeviceType("invalid")


# =============================================================================
# Router Configuration Tests
# =============================================================================

class TestSyncRouterConfiguration:
    """Tests for sync router configuration."""

    @pytest.mark.unit
    def test_router_has_device_sync_tag(self, app):
        """Sync router should have Device Sync tag."""
        openapi = app.openapi()
        tags = openapi.get("tags", [])
        tag_names = [t["name"] for t in tags]
        assert "Device Sync" in tag_names

    @pytest.mark.unit
    def test_router_endpoints_exist(self, app):
        """All expected endpoints should be registered."""
        openapi = app.openapi()
        paths = openapi.get("paths", {})
        
        expected_endpoints = [
            "/workouts/{workout_id}/push/ios-companion",
            "/ios-companion/pending",
            "/workouts/{workout_id}/push/android-companion",
            "/android-companion/pending",
            "/workout/sync/garmin",
            "/workouts/{workout_id}/sync",
            "/sync/pending",
            "/sync/confirm",
            "/sync/failed",
            "/workouts/{workout_id}/sync-status",
        ]
        
        for endpoint in expected_endpoints:
            assert endpoint in paths, f"Missing endpoint: {endpoint}"

    @pytest.mark.unit
    def test_ios_push_endpoint_methods(self, app):
        """iOS push endpoint should only accept POST."""
        openapi = app.openapi()
        path = openapi["paths"]["/workouts/{workout_id}/push/ios-companion"]
        assert "post" in path
        assert "get" not in path

    @pytest.mark.unit
    def test_ios_pending_endpoint_methods(self, app):
        """iOS pending endpoint should only accept GET."""
        openapi = app.openapi()
        path = openapi["paths"]["/ios-companion/pending"]
        assert "get" in path
        assert "post" not in path


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Edge case tests for sync router."""

    @pytest.mark.unit
    def test_push_workout_with_superset(self, client):
        """Handle workout with supersets."""
        workout_with_superset = {
            "id": TEST_WORKOUT_ID,
            "title": "Superset Workout",
            "workout_data": {
                "blocks": [
                    {
                        "structure": "superset",
                        "exercises": [
                            {"name": "Bench Press", "reps": 10},
                            {"name": "Rows", "reps": 10},
                        ]
                    }
                ]
            },
            "created_at": "2024-01-01T00:00:00Z",
        }
        
        with patch("api.routers.sync.run_in_threadpool") as mock_run:
            mock_run.return_value = workout_with_superset
            
            with patch("api.routers.sync.update_workout_ios_companion_sync"):
                with patch("api.routers.sync.queue_workout_sync") as mock_queue:
                    mock_queue.return_value = {"status": "pending"}
                    
                    response = client.post(
                        f"/workouts/{TEST_WORKOUT_ID}/push/ios-companion",
                        json={}
                    )
                    
                    assert response.status_code == 200

    @pytest.mark.unit
    def test_garmin_sync_with_supersets(self, mock_client_class, client):
        """Sync workout with supersets to Garmin."""
        mock_client = MagicMock()
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)
        
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        
        payload = {
            "blocks_json": {
                "blocks": [
                    {
                        "exercises": [{"name": "Bench Press", "reps": 10}],
                        "supersets": [
                            {
                                "exercises": [
                                    {"name": "Push-ups", "reps": 15},
                                    {"name": "Pull-ups", "reps": 8},
                                ]
                            }
                        ]
                    }
                ]
            },
            "workout_title": "Superset Workout",
        }
        
        response = client.post("/workout/sync/garmin", json=payload)
        
        assert response.status_code == 200

    @pytest.mark.unit
    def test_transform_workout_with_empty_blocks(self):
        """Handle workout with empty blocks."""
        from api.routers.sync import _transform_workout_to_companion
        import asyncio
        
        workout = {"blocks": []}
        result = asyncio.run(_transform_workout_to_companion(workout, "Empty Workout"))
        
        assert result["name"] == "Empty Workout"
        assert result["intervals"] == []
        assert result["duration"] == 0

    @pytest.mark.unit
    def test_convert_exercise_with_zero_sets(self):
        """Handle exercise with zero sets."""
        from api.routers.sync import convert_exercise_to_interval
        
        exercise = {
            "name": "Test Exercise",
            "reps": 10,
            "sets": 0,  # Zero sets should default to 1
            "rest_sec": 30,
        }
        result = convert_exercise_to_interval(exercise)
        
        # Sets of 0 should be treated as 1 set
        assert result["reps"] == 10  # 10 reps * 1 set

    @pytest.mark.unit
    def test_calculate_duration_with_unknown_kind(self):
        """Handle unknown interval kinds gracefully."""
        from api.routers.sync import calculate_intervals_duration
        
        intervals = [
            {"kind": "unknown", "seconds": 60},
            {"kind": "time", "seconds": 30},
        ]
        result = calculate_intervals_duration(intervals)
        
        # Unknown kinds should be ignored (add 0)
        assert result == 30

    @pytest.mark.unit
    def test_calculate_duration_nested_repeat(self):
        """Handle deeply nested repeat intervals."""
        from api.routers.sync import calculate_intervals_duration
        
        intervals = [{
            "kind": "repeat",
            "reps": 2,
            "intervals": [{
                "kind": "repeat",
                "reps": 3,
                "intervals": [
                    {"kind": "time", "seconds": 10}
                ]
            }]
        }]
        result = calculate_intervals_duration(intervals)
        
        # 2 * (3 * 10) = 60
        assert result == 60


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Tests for error handling in sync router."""

    @pytest.mark.unit
    def test_database_error_handling_ios_push(self, client):
        """Handle database error during iOS push."""
        with patch("api.routers.sync.run_in_threadpool") as mock_run:
            mock_run.side_effect = Exception("Database connection failed")
            
            response = client.post(
                f"/workouts/{TEST_WORKOUT_ID}/push/ios-companion",
                json={}
            )
            
            assert response.status_code == 500

    @pytest.mark.unit
    def test_database_error_handling_get_pending(self, client):
        """Handle database error when getting pending workouts."""
        with patch("api.routers.sync.run_in_threadpool") as mock_run:
            mock_run.side_effect = Exception("Query failed")
            
            response = client.get("/ios-companion/pending")
            
            assert response.status_code == 500

    @pytest.mark.unit
    def test_malformed_workout_data_handling(self, client):
        """Handle malformed workout data gracefully."""
        malformed_workout = {
            "id": TEST_WORKOUT_ID,
            "title": "Malformed",
            "workout_data": None,  # Null workout data
        }
        
        with patch("api.routers.sync.run_in_threadpool") as mock_run:
            mock_run.return_value = malformed_workout
            
            response = client.post(
                f"/workouts/{TEST_WORKOUT_ID}/push/ios-companion",
                json={}
            )
            
            assert response.status_code == 422

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_transform_workout_key_error(self):
        """Handle KeyError during workout transformation."""
        from api.routers.sync import _transform_workout_to_companion
        
        # Missing 'blocks' key
        workout = {"title": "No Blocks"}
        
        with pytest.raises(ValueError):
            await _transform_workout_to_companion(workout, "Test")


# =============================================================================
# Authentication Tests
# =============================================================================

class TestAuthentication:
    """Tests for authentication on sync endpoints."""

    @pytest.mark.unit
    def test_ios_push_requires_auth(self, app):
        """iOS push endpoint should require authentication."""
        # Remove auth override
        app.dependency_overrides = {}
        client = TestClient(app)
        
        response = client.post(
            f"/workouts/{TEST_WORKOUT_ID}/push/ios-companion",
            json={}
        )
        
        assert response.status_code == 401

    @pytest.mark.unit
    def test_garmin_sync_requires_auth(self, app):
        """Garmin sync endpoint should require authentication."""
        # Remove auth override
        app.dependency_overrides = {}
        client = TestClient(app)
        
        response = client.post("/workout/sync/garmin", json={
            "blocks_json": {"blocks": []},
            "workout_title": "Test"
        })
        
        assert response.status_code == 401

    @pytest.mark.unit
    def test_sync_status_requires_auth(self, app):
        """Sync status endpoint should require authentication."""
        # Remove auth override
        app.dependency_overrides = {}
        client = TestClient(app)
        
        response = client.get(f"/workouts/{TEST_WORKOUT_ID}/sync-status")
        
        assert response.status_code == 401


# =============================================================================
# Integration-style Router Tests
# =============================================================================

@pytest.mark.integration
class TestSyncRouterIntegration:
    """Integration-style tests for sync router."""

    @pytest.mark.unit
    def test_full_sync_workflow(self, client):
        """Test complete sync workflow: queue -> pending -> confirm."""
        workout_id = "workflow-test-123"
        
        # Step 1: Queue workout for sync
        with patch("api.routers.sync.run_in_threadpool") as mock_run:
            mock_run.side_effect = [
                {  # get_workout
                    "id": workout_id,
                    "title": "Workflow Test",
                    "workout_data": SAMPLE_WORKOUT_DATA,
                },
                {  # queue_workout_sync
                    "status": "pending",
                    "queued_at": "2024-01-01T00:00:00Z"
                }
            ]
            
            response = client.post(
                f"/workouts/{workout_id}/sync",
                json={"device_type": "ios", "device_id": "device-1"}
            )
            assert response.status_code == 200
        
        # Step 2: Get pending syncs
        with patch("api.routers.sync.run_in_threadpool") as mock_run:
            mock_run.return_value = [
                {
                    "workout_id": workout_id,
                    "queued_at": "2024-01-01T00:00:00Z",
                    "workouts": {
                        "id": workout_id,
                        "title": "Workflow Test",
                        "workout_data": SAMPLE_WORKOUT_DATA,
                        "created_at": "2024-01-01T00:00:00Z",
                    }
                }
            ]
            
            response = client.get("/sync/pending?device_type=ios&device_id=device-1")
            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 1
        
        # Step 3: Confirm sync
        with patch("api.routers.sync.run_in_threadpool") as mock_run:
            mock_run.return_value = {
                "status": "synced",
                "synced_at": "2024-01-01T01:00:00Z"
            }
            
            response = client.post("/sync/confirm", json={
                "workout_id": workout_id,
                "device_type": "ios",
                "device_id": "device-1"
            })
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "synced"

    @pytest.mark.unit
    def test_failed_sync_workflow(self, client):
        """Test sync failure workflow: queue -> pending -> failed."""
        workout_id = "failed-test-456"
        
        with patch("api.routers.sync.run_in_threadpool") as mock_run:
            mock_run.return_value = {
                "status": "failed",
                "failed_at": "2024-01-01T00:00:00Z"
            }
            
            response = client.post("/sync/failed", json={
                "workout_id": workout_id,
                "device_type": "android",
                "error": "Device disconnected",
                "device_id": "device-2"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "failed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
