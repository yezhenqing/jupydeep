import json


async def test_extension_enabled(jp_serverapp):
    # Check if extension is in the extension manager list
    assert "jupydeep" in jp_serverapp.extension_manager.extensions
    # Check if extension is loaded
    extension = jp_serverapp.extension_manager.extensions["jupydeep"]
    assert extension is not None


async def test_extension_loaded(jp_fetch):
    """Test the catalog endpoint of the extension"""
    response = await jp_fetch("jupydeep", "catalog")

    # Check status code
    assert response.code == 200, f"Expected 200, got {response.code}"

    # Parse JSON response correctly
    data = json.loads(response.body.decode("utf-8"))

    # Validate response structure
    assert data["status"] == "success"
    assert "payload" in data

    print("\n✅ Test passed!")
    print(f"   Status: {data['status']}")
    print(f"   Message: {data.get('message', 'N/A')}")
    print(f"   Payload keys: {list(data['payload'].keys())}")
