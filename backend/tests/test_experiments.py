"""End-to-end tests for the Experiment Management API (P6.M1).

Adapted to the real fixtures: owner_auth -> (client, headers, tenant_id), with a
golden dataset created via the datasets API first.
"""
from __future__ import annotations


def _make_dataset(client, headers, name="exp-ds"):
    r = client.post(
        "/api/datasets",
        headers=headers,
        json={
            "name": name,
            "description": "experiment source",
            "examples": [
                {"input": "When does Spain play?", "output": "Spain plays at 20:00."},
                {"input": "Where is the final?", "output": "The final is at MetLife."},
            ],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_experiment_crud_and_run(owner_auth):
    client, headers, _ = owner_auth
    ds_id = _make_dataset(client, headers)

    # Create
    r = client.post(
        "/api/experiments",
        headers=headers,
        json={
            "name": "Test Experiment",
            "dataset_id": ds_id,
            "evaluator_ids": ["llm_judge"],
            "description": "integration",
        },
    )
    assert r.status_code == 201, r.text
    exp = r.json()
    assert exp["name"] == "Test Experiment"
    exp_id = exp["id"]

    # List
    r = client.get("/api/experiments", headers=headers)
    assert r.status_code == 200
    assert any(e["id"] == exp_id for e in r.json())

    # Trigger run
    r = client.post(f"/api/experiments/{exp_id}/run", headers=headers)
    assert r.status_code == 200, r.text
    run = r.json()
    assert run["status"] == "complete"
    assert run["verdict_summary"]["total_items"] == 2
    run_id = run["run_id"]

    # Run detail
    r = client.get(f"/api/experiments/{exp_id}/runs/{run_id}", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) == 2
    assert "llm_judge" in data["items"][0]["verdicts"]


def test_experiment_compare_runs(owner_auth):
    client, headers, _ = owner_auth
    ds_id = _make_dataset(client, headers, name="cmp-ds")
    exp_id = client.post(
        "/api/experiments",
        headers=headers,
        json={"name": "Compare", "dataset_id": ds_id, "evaluator_ids": ["llm_judge"]},
    ).json()["id"]

    run_a = client.post(f"/api/experiments/{exp_id}/run", headers=headers).json()["run_id"]
    run_b = client.post(f"/api/experiments/{exp_id}/run", headers=headers).json()["run_id"]

    r = client.get(
        f"/api/experiments/{exp_id}/compare?run_a={run_a}&run_b={run_b}", headers=headers
    )
    assert r.status_code == 200, r.text
    cmp = r.json()
    assert "delta" in cmp
    assert cmp["winner"] in ("run_a", "run_b", "tie")
    assert "per_evaluator_delta" in cmp


def test_experiment_run_missing_experiment_404(owner_auth):
    client, headers, _ = owner_auth
    r = client.post("/api/experiments/nonexistent/run", headers=headers)
    assert r.status_code == 404


def test_experiment_run_missing_dataset_404(owner_auth):
    """Experiment pointing at a non-existent dataset -> 404 on run."""
    client, headers, _ = owner_auth
    exp_id = client.post(
        "/api/experiments",
        headers=headers,
        json={"name": "Orphan", "dataset_id": "ghost-ds", "evaluator_ids": ["llm_judge"]},
    ).json()["id"]
    r = client.post(f"/api/experiments/{exp_id}/run", headers=headers)
    assert r.status_code == 404


def test_experiment_get_run_wrong_experiment_404(owner_auth):
    client, headers, _ = owner_auth
    ds_id = _make_dataset(client, headers, name="wrong-exp-ds")
    exp_id = client.post(
        "/api/experiments",
        headers=headers,
        json={"name": "E", "dataset_id": ds_id, "evaluator_ids": ["llm_judge"]},
    ).json()["id"]
    run_id = client.post(f"/api/experiments/{exp_id}/run", headers=headers).json()["run_id"]
    # Ask for the run under a different experiment id.
    r = client.get(f"/api/experiments/other-exp/runs/{run_id}", headers=headers)
    assert r.status_code == 404


def test_experiment_compare_missing_run_404(owner_auth):
    client, headers, _ = owner_auth
    ds_id = _make_dataset(client, headers, name="cmp404-ds")
    exp_id = client.post(
        "/api/experiments",
        headers=headers,
        json={"name": "C", "dataset_id": ds_id, "evaluator_ids": ["llm_judge"]},
    ).json()["id"]
    run_a = client.post(f"/api/experiments/{exp_id}/run", headers=headers).json()["run_id"]
    r = client.get(
        f"/api/experiments/{exp_id}/compare?run_a={run_a}&run_b=ghost", headers=headers
    )
    assert r.status_code == 404


def test_experiment_run_skips_empty_input_and_unknown_evaluator(owner_auth):
    """Empty-input examples are skipped; unknown evaluator ids are ignored."""
    client, headers, _ = owner_auth
    r = client.post(
        "/api/datasets",
        headers=headers,
        json={
            "name": "edge-ds",
            "description": "edge cases",
            "examples": [
                {"input": "", "output": "should be skipped"},  # empty input -> skip
                {"input": "Real question?", "output": "Real answer."},
            ],
        },
    )
    assert r.status_code == 201
    ds_id = r.json()["id"]

    exp_id = client.post(
        "/api/experiments",
        headers=headers,
        json={
            "name": "EdgeExp",
            "dataset_id": ds_id,
            # one real evaluator + one bogus id that isn't in the registry
            "evaluator_ids": ["llm_judge", "does_not_exist"],
        },
    ).json()["id"]

    run = client.post(f"/api/experiments/{exp_id}/run", headers=headers).json()
    assert run["status"] == "complete"
    # Only the non-empty example is scored.
    assert run["verdict_summary"]["total_items"] == 1


def test_ab_compare_returns_winner(owner_auth):
    client, headers, _ = owner_auth
    ds_id = _make_dataset(client, headers, name="ab-ds")
    exp_id = client.post(
        "/api/experiments",
        headers=headers,
        json={"name": "AB", "dataset_id": ds_id, "evaluator_ids": ["llm_judge"]},
    ).json()["id"]

    r = client.post(
        f"/api/experiments/{exp_id}/ab-compare",
        headers=headers,
        json={
            "baseline_agent_version": "v1.0",
            "candidate_agent_version": "v1.1",
            "dataset_id": ds_id,
            "evaluator_ids": ["llm_judge"],
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["winner"] in ("baseline", "candidate", "tie")
    assert "cohens_d" in data
    assert "z_score" in data
    assert "statistical_significance" in data
    assert "baseline_pass_rate" in data and "candidate_pass_rate" in data


def test_ab_compare_missing_dataset_404(owner_auth):
    client, headers, _ = owner_auth
    ds_id = _make_dataset(client, headers, name="ab404-ds")
    exp_id = client.post(
        "/api/experiments",
        headers=headers,
        json={"name": "AB404", "dataset_id": ds_id, "evaluator_ids": ["llm_judge"]},
    ).json()["id"]
    r = client.post(
        f"/api/experiments/{exp_id}/ab-compare",
        headers=headers,
        json={
            "baseline_agent_version": "v1",
            "candidate_agent_version": "v2",
            "dataset_id": "ghost-dataset",
            "evaluator_ids": ["llm_judge"],
        },
    )
    assert r.status_code == 404


def test_ab_compare_statistics_with_empty_input_rows(owner_auth):
    """Dataset with an empty-input row exercises the skip path; stats still return."""
    client, headers, _ = owner_auth
    r = client.post(
        "/api/datasets",
        headers=headers,
        json={
            "name": "ab-stats-ds",
            "examples": [
                {"input": "Q1?", "output": "A1"},
                {"input": "Q2?", "output": "A2"},
                {"input": "", "output": "skip me"},
            ],
        },
    )
    ds_id = r.json()["id"]
    exp_id = client.post(
        "/api/experiments",
        headers=headers,
        json={"name": "ABStats", "dataset_id": ds_id, "evaluator_ids": ["llm_judge", "ghost_ev"]},
    ).json()["id"]
    res = client.post(
        f"/api/experiments/{exp_id}/ab-compare",
        headers=headers,
        json={
            "baseline_agent_version": "vA",
            "candidate_agent_version": "vB",
            "dataset_id": ds_id,
            "evaluator_ids": ["llm_judge", "ghost_ev"],
        },
    ).json()
    # 2 non-empty rows -> cohens_d computable (>=2 each side).
    assert isinstance(res["cohens_d"], float)
    assert isinstance(res["statistical_significance"], bool)


def test_ab_compare_single_example_cohens_d_guard(owner_auth):
    """A 1-row dataset makes each side have <2 scores -> Cohen's d guard (0.0)."""
    client, headers, _ = owner_auth
    r = client.post(
        "/api/datasets",
        headers=headers,
        json={"name": "ab-1row", "examples": [{"input": "only?", "output": "one"}]},
    )
    ds_id = r.json()["id"]
    exp_id = client.post(
        "/api/experiments",
        headers=headers,
        json={"name": "AB1", "dataset_id": ds_id, "evaluator_ids": ["llm_judge"]},
    ).json()["id"]
    res = client.post(
        f"/api/experiments/{exp_id}/ab-compare",
        headers=headers,
        json={
            "baseline_agent_version": "a",
            "candidate_agent_version": "b",
            "dataset_id": ds_id,
            "evaluator_ids": ["llm_judge"],
        },
    ).json()
    assert res["cohens_d"] == 0.0  # <2 samples per side


def test_ab_compare_all_empty_inputs_ztest_guard(owner_auth):
    """A dataset whose every row has empty input -> zero scored -> z-test guard."""
    client, headers, _ = owner_auth
    r = client.post(
        "/api/datasets",
        headers=headers,
        json={"name": "ab-allempty", "examples": [{"input": "", "output": "x"}]},
    )
    ds_id = r.json()["id"]
    exp_id = client.post(
        "/api/experiments",
        headers=headers,
        json={"name": "ABE", "dataset_id": ds_id, "evaluator_ids": ["llm_judge"]},
    ).json()["id"]
    res = client.post(
        f"/api/experiments/{exp_id}/ab-compare",
        headers=headers,
        json={
            "baseline_agent_version": "a",
            "candidate_agent_version": "b",
            "dataset_id": ds_id,
            "evaluator_ids": ["llm_judge"],
        },
    ).json()
    assert res["z_score"] == 0.0
    assert res["baseline_pass_rate"] == 0.0
