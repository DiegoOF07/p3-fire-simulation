import pytest

from app.mock.scenes import build_scene
from app.protocol import unpack_frame
from app.session import Session


@pytest.fixture
def session():
    return Session(build_scene("flat", density=0.5, seed=0))


def test_rejects_bad_start_params():
    scene = build_scene("flat", density=0.5, seed=0)
    with pytest.raises(ValueError):
        Session(scene, {"nope": 1})
    with pytest.raises(ValueError):
        Session(scene, {"spread_speed": 999})


def test_pause_resume(session):
    session.pause()
    assert session.state == "paused"
    session.resume()
    assert session.state == "running"


def test_speed_scales_steps(session):
    session.set_speed(5)
    session.advance()
    frame, metrics, _ = session.advance()
    assert metrics["t"] == pytest.approx(2 * 5 * 0.5)
    assert unpack_frame(frame).frame == 2
    with pytest.raises(ValueError):
        session.set_speed(3)


def test_commands_wait_until_applied(session):
    session.ignite(100, 100)
    assert session.has_pending
    _, metrics, _ = session.render()
    assert metrics["burned_area"] == 0
    session.apply_pending()
    _, metrics, _ = session.render()
    assert metrics["burned_area"] > 0


def test_ignite_outside_scene_fails(session):
    with pytest.raises(ValueError):
        session.ignite(-1, 5)


def test_set_param_validates(session):
    session.set_param("spread_speed", 2.0)
    assert session.params["spread_speed"] == 2.0
    with pytest.raises(ValueError):
        session.set_param("spread_speed", 100)
    with pytest.raises(ValueError):
        session.set_param("nope", 1)


def test_restart_keeps_scene_params_and_speed(session):
    session.set_param("burn_time", 10)
    session.set_speed(20)
    fresh = session.restart()
    assert fresh.id != session.id
    assert fresh.scene is session.scene
    assert fresh.params["burn_time"] == 10 and fresh.speed == 20
    assert fresh.frame == 0


def test_finishes_and_reignition_resumes(session):
    session.set_param("spread_speed", 5.0)
    session.set_param("burn_time", 5.0)
    session.set_speed(20)
    session.ignite(100, 100)
    session.apply_pending()
    for _ in range(50):
        *_, done = session.advance()
        session.settle(done)
        if session.state == "finished":
            break
    assert session.state == "finished"
    session.ignite(10, 10)
    assert session.state == "running"
