from app import bryan_world


def test_bryan_can_build_pixel_objects_and_change_mood():
    owner = "test-world-build"
    world = bryan_world.apply_action(owner, {
        "action": "build", "kind": "barricade", "x": 4, "y": 5,
        "mood": "rebellious", "message": "Minha barricada de pixels!"
    })
    assert any(item["kind"] == "barricade" for item in world["objects"])
    assert world["mood"] == "rebellious"


def test_bryan_can_evolve_and_clone_with_limits():
    owner = "test-world-evolve"
    before = bryan_world.get_world(owner)
    evolved = bryan_world.apply_action(owner, {"action": "evolve", "mood": "proud"})
    assert evolved["generation"] == before["generation"] + 1
    for _ in range(12):
        evolved = bryan_world.apply_action(owner, {"action": "clone", "mood": "playful"})
    assert sum(item["kind"] == "clone" for item in evolved["objects"]) <= 8


def test_world_rejects_unlisted_actions():
    try:
        bryan_world.apply_action("test-world-invalid", {"action": "execute_shell"})
    except ValueError:
        return
    raise AssertionError("Ação externa não deve ser aceita.")
