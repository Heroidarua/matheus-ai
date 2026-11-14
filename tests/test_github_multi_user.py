from starlette.requests import Request

from app import github_integration as github


def make_request(session=None):
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/github/status",
        "headers": [],
        "session": session if session is not None else {},
    }
    return Request(scope)


def test_each_browser_session_keeps_its_own_installation_and_repository():
    alice = make_request({
        "github_installation_id": 101,
        "github_account": "alice",
        "github_selected_repo": "alice/private-project",
    })
    bob = make_request({
        "github_installation_id": 202,
        "github_account": "bob",
        "github_selected_repo": "bob/website",
    })

    assert github._installation_id(alice) == 101
    assert github._installation_id(bob) == 202
    assert github._selected_repo(alice) == "alice/private-project"
    assert github._selected_repo(bob) == "bob/website"


def test_disconnect_data_is_session_local():
    alice = make_request({
        "github_installation_id": 101,
        "github_account": "alice",
        "github_selected_repo": "alice/private-project",
    })
    bob = make_request({
        "github_installation_id": 202,
        "github_account": "bob",
        "github_selected_repo": "bob/website",
    })

    for key in ("github_installation_id", "github_account", "github_selected_repo"):
        alice.session.pop(key, None)

    assert "github_installation_id" not in alice.session
    assert bob.session["github_installation_id"] == 202
    assert bob.session["github_selected_repo"] == "bob/website"


def test_proposal_owner_is_unique_per_session():
    alice = make_request()
    bob = make_request()

    alice_owner = github._session_owner(alice)
    bob_owner = github._session_owner(bob)

    assert alice_owner != bob_owner
    assert github._session_owner(alice) == alice_owner
    assert github._session_owner(bob) == bob_owner
