import pytest

from lifeops.moss import create_file_backed_moss_client


@pytest.mark.asyncio
async def test_file_backed_moss_survives_a_new_client_instance(tmp_path) -> None:
    directory = str(tmp_path / "moss-data")

    client = create_file_backed_moss_client(directory)
    await client.preferences.save({"user_id": "u1", "kind": "preference", "content": "hiking"})

    reopened = create_file_backed_moss_client(directory)
    results = await reopened.preferences.search("hiking", filters={"user_id": "u1"})
    assert results
    assert results[0]["content"] == "hiking"


@pytest.mark.asyncio
async def test_file_backed_moss_persists_updates_and_deletes(tmp_path) -> None:
    directory = str(tmp_path / "moss-data")

    client = create_file_backed_moss_client(directory)
    saved = await client.decisions.save({"user_id": "u1", "kind": "decision", "content": "v1"})
    await client.decisions.update(saved["id"], {"content": "v2"})

    reopened = create_file_backed_moss_client(directory)
    results = await reopened.decisions.search("v2", filters={"user_id": "u1"})
    assert results and results[0]["content"] == "v2"

    await reopened.decisions.delete(saved["id"])
    reopened_again = create_file_backed_moss_client(directory)
    results = await reopened_again.decisions.search("v2", filters={"user_id": "u1"})
    assert not results
